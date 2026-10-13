"""ConPTY broker. Win32 Job Object is process cleanup, not a security sandbox."""
import ctypes
from ctypes import wintypes
import json,os,queue,sys,threading,time
import psutil

def job_for(pid):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    class Basic(ctypes.Structure):
        _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]
    class IO(ctypes.Structure):_fields_=[(n,ctypes.c_ulonglong) for n in ['ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount']]
    class Limits(ctypes.Structure):_fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
    k.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];k.CreateJobObjectW.restype=wintypes.HANDLE
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
    k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    job=k.CreateJobObjectW(None,None);process=k.OpenProcess(0x0100|0x0001,False,pid)
    info=Limits();info.BasicLimitInformation.LimitFlags=0x2000 # KILL_ON_JOB_CLOSE
    try:
        if not job or not process or not k.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)) or not k.AssignProcessToJobObject(job,process):raise OSError(ctypes.get_last_error(),'Unable to establish Windows cleanup job')
    except BaseException:
        if job:k.CloseHandle(job)
        raise
    finally:
        if process:k.CloseHandle(process)
    return k,job

def main():
    from winpty import PtyProcess,Backend
    from .platform_support import windows_command
    child=None;job=None;kernel=None;exit_code=125
    controls=queue.Queue();outputs=queue.Queue(maxsize=2000)
    def control_reader():
        try:
            for line in sys.stdin.buffer:controls.put(json.loads(line))
        finally:controls.put({'kind':'stop'})
    def reader():
        try:
            while True:
                text=child.read(4096)
                if text:outputs.put(text)
        except (EOFError,OSError):pass
        finally:outputs.put(None)
    try:
        config=json.loads(sys.stdin.buffer.readline())
        argv,env=windows_command(config['argv'],config['env'])
        child=PtyProcess.spawn(argv,cwd=config['cwd'],env=env,dimensions=(config['rows'],config['cols']),backend=str(Backend.ConPTY))
        try:kernel,job=job_for(child.pid)
        except OSError:
            if child.isalive():raise
        print(json.dumps({'ready':True,'pid':child.pid,'backend':'ConPTY'}),file=sys.stderr,flush=True)
        threading.Thread(target=control_reader,daemon=True).start();threading.Thread(target=reader,daemon=True).start()
        stopping=False;exited_at=None
        while True:
            try:
                message=controls.get_nowait()
                if message['kind']=='input' and not stopping:child.write(message['text'])
                elif message['kind']=='resize' and not stopping:child.setwinsize(message['rows'],message['cols'])
                elif message['kind']=='stop':
                    stopping=True
                    if job:kernel.CloseHandle(job);job=None
            except queue.Empty:pass
            try:text=outputs.get(timeout=.03)
            except queue.Empty:
                if not child.isalive():
                    if exited_at is None:exited_at=time.monotonic()
                    if time.monotonic()-exited_at>2:break
                continue
            if text is None:break
            sys.stdout.buffer.write(text.encode('utf-8'));sys.stdout.buffer.flush()
        exit_code=(child.exitstatus if child.exitstatus is not None else 1)&255
    except BaseException as error:
        print(json.dumps({'error':str(error)}),file=sys.stderr,flush=True);exit_code=125
    finally:
        if job:kernel.CloseHandle(job)
        # The isolated broker owns all ConPTY handles. Let the OS reclaim them;
        # interpreter finalizers race pywinpty's native reader on child exit.
        # Job closure above kills any surviving descendants before termination.
        sys.stdout.flush();sys.stderr.flush()
        os._exit(exit_code)
if __name__=='__main__':raise SystemExit(main())
