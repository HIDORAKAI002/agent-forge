"""Optional local microphone dictation; transcript is a draft, never execution."""
from __future__ import annotations
import importlib.util
import queue
import threading
import time
from pathlib import Path

MODELS=('tiny.en','base.en','small.en','tiny','base','small')
class Voice:
    def __init__(self,cache:Path):
        self.cache=cache;self.model=None;self.model_name=None;self.stream=None;self.chunks=[];self.lock=threading.Lock();self.events=queue.Queue();self.closed=False;self.busy=False;self.recording=False;self.started=0;self.state='Not prepared';self.seconds=0
    @property
    def available(self):return bool(importlib.util.find_spec('sounddevice') and importlib.util.find_spec('faster_whisper'))
    def prepare(self,name):
        if name not in MODELS:raise ValueError('Unsupported speech model')
        if self.busy or self.recording:raise ValueError('Finish the current voice operation first')
        if not self.available:raise ValueError('Install the optional voice dependencies: rerun install.sh with FORGE_VOICE=1')
        self.busy=True;self.state='Loading/downloading speech model; percentage unavailable'
        def worker():
            try:
                from faster_whisper import WhisperModel
                self.cache.mkdir(parents=True,exist_ok=True,mode=0o700)
                model=WhisperModel(name,device='cpu',compute_type='int8',download_root=str(self.cache))
                if not self.closed:self.model=model;self.model_name=name;self.events.put(('ready','Local speech model ready'))
            except Exception:self.events.put(('error','Speech model could not load; check dependencies, disk and network.'))
            self.busy=False
        threading.Thread(target=worker,daemon=True,name='forge-speech-model').start()
    def start(self):
        if self.closed:return
        if self.busy or self.recording:raise ValueError('Voice operation already active')
        if self.model is None:raise ValueError('Prepare a speech model first')
        self.busy=True;self.chunks=[];self.seconds=0;self.state='Opening microphone'
        def worker():
            try:
                import sounddevice as sd
                def callback(indata,frames,timestamp,status):
                    if self.closed:raise sd.CallbackStop
                    with self.lock:
                        if sum(map(len,self.chunks))>=16000*2*60:raise sd.CallbackStop
                        self.chunks.append(bytes(indata))
                        self.seconds=sum(map(len,self.chunks))/(16000*2)
                    if status:self.events.put(('warning','Microphone reported dropped/overflowed audio; review the transcript'))
                stream=sd.RawInputStream(samplerate=16000,channels=1,dtype='int16',callback=callback)
                if self.closed:stream.close();return
                self.stream=stream;self.started=time.monotonic();stream.start();self.recording=True
                self.events.put(('recording','Recording locally · stop to transcribe · maximum 60 seconds'))
            except Exception:self.events.put(('error','Microphone could not open. Check device access and PortAudio installation.'))
            self.busy=False
        threading.Thread(target=worker,daemon=True,name='forge-microphone').start()
    def stop(self,transcribe=True):
        if self.busy:raise ValueError('Voice operation in progress')
        self.recording=False;self.busy=True;self.state='Transcribing locally' if transcribe else 'Stopping microphone'
        def worker():
            try:
                stream=self.stream
                if stream:stream.stop();stream.close();self.stream=None
                with self.lock:audio=b''.join(self.chunks);self.chunks=[]
                if transcribe and audio and not self.closed:
                    import numpy as np
                    segments,_=self.model.transcribe(np.frombuffer(audio,dtype=np.int16).astype(np.float32)/32768,beam_size=5,vad_filter=True)
                    text=' '.join(s.text.strip() for s in segments).strip()[:12000]
                    if not self.closed:self.events.put(('draft',text))
                elif not self.closed:self.events.put(('ready','Recording discarded' if not transcribe else 'No audio captured'))
            except Exception:
                if not self.closed:self.events.put(('error','Local transcription failed; no text was submitted'))
            self.busy=False
        threading.Thread(target=worker,daemon=True,name='forge-dictation').start()
    def poll(self):
        result=[]
        while not self.events.empty():
            kind,value=self.events.get_nowait();result.append((kind,value));self.state=value if kind!='draft' else 'Transcript ready · awaiting review'
        if self.recording and self.stream is not None and not self.stream.active and not self.busy:self.stop()
        return result
    def close(self):
        self.closed=True
        if self.stream and not self.busy:
            try:self.stop(False)
            except Exception:pass
        with self.lock:self.chunks=[]
