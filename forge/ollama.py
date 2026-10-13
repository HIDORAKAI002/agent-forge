"""Loopback-only Ollama inventory, streamed pulls and persistent local selection.

Workers only emit events. The TUI owns settings writes and activation decisions.
No installer is executed, no model is pulled until the user confirms.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
import urllib.request
from urllib.parse import urlsplit
from .store import managed


def bytes_text(value: int) -> str:
    for scale, unit in ((10**9, 'GB'), (10**6, 'MB'), (10**3, 'KB')):
        if value >= scale:
            return f'{value / scale:.1f} {unit}'
    return f'{value} B'


def model_name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9._-]+)?', value) or len(value) > 160 or '..' in value or value.lower().endswith((':cloud', '-cloud')):
        raise ValueError('Choose a local Ollama model tag, e.g. qwen2.5-coder:3b; cloud tags are not supported')
    return value


def local_model(item: dict) -> bool:
    name = item.get('name') or item.get('model', '')
    try:
        model_name(name)
        return not item.get('remote_host') and not item.get('remote_model')
    except ValueError:
        return False


def endpoint(value: str | None = None) -> str:
    value = value or os.environ.get('OLLAMA_HOST') or 'http://127.0.0.1:11434'
    if '://' not in value:
        value = 'http://' + value
    parsed = urlsplit(value)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Local models require a loopback HTTP OLLAMA_HOST (default http://127.0.0.1:11434)')
    port = parsed.port or 11434
    host = '[::1]' if parsed.hostname == '::1' else parsed.hostname
    return f'http://{host}:{port}'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Refusing an Ollama API redirect away from the configured local endpoint')


class OllamaAPI:
    def __init__(self, host: str | None = None):
        self.host = endpoint(host)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        self.response = None

    def request(self, path: str, body=None, timeout=3):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.host + path, data=data, headers={'Content-Type': 'application/json'})
        return self.opener.open(req, timeout=timeout)

    def json(self, path: str, body=None, timeout=3):
        with self.request(path, body, timeout) as response:
            result = json.loads(response.read(8 * 1024 * 1024))
        if result.get('error'):
            raise ValueError(result['error'])
        return result

    def inventory(self):
        version = self.json('/api/version').get('version', 'unknown')
        installed = [m for m in self.json('/api/tags').get('models', []) if local_model(m)]
        loaded = [m for m in self.json('/api/ps').get('models', []) if local_model(m)]
        return {'version': version, 'installed': installed, 'loaded': loaded}

    def pull(self, model: str, emit, cancel: threading.Event):
        success = False
        with self.request('/api/pull', {'model': model_name(model), 'stream': True}, timeout=120) as response:
            self.response = response
            try:
                for line in response:
                    if cancel.is_set():
                        raise ValueError('Download cancelled locally; Ollama may finish an already accepted server operation')
                    if len(line) > 1024 * 1024:
                        raise ValueError('Oversized Ollama stream event')
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get('error'):
                        raise ValueError(event['error'])
                    emit('progress', event)
                    if event.get('status') == 'success':
                        success = True
                        break
            finally:
                self.response = None
        if not success:
            raise ValueError('Ollama pull ended without a verified success event')

    def warm(self, model: str):
        # Empty prompt is the documented preload operation, not a generation task.
        self.json('/api/generate', {'model': model, 'stream': False, 'keep_alive': '5m'}, timeout=120)

    def unload(self, model: str):
        self.json('/api/generate', {'model': model, 'stream': False, 'keep_alive': 0}, timeout=30)

    def cancel(self):
        response = self.response
        if response:
            try:
                response.close()
            except OSError:
                pass


def read_settings(directory: Path) -> dict:
    path = managed(directory, 'ollama.json')
    defaults = {'selected_model': None, 'auto_activate': False, 'tutorial_completed': False}
    if path.exists():
        if path.stat().st_size > 16384:
            raise ValueError('Ollama settings file is too large')
        value = json.loads(path.read_text())
        if value.get('selected_model'):
            defaults['selected_model'] = model_name(value['selected_model'])
        for key in ('auto_activate', 'tutorial_completed'):
            defaults[key] = value.get(key) is True
    return defaults


def write_settings(directory: Path, value: dict):
    destination = managed(directory, 'ollama.json')
    temporary = managed(directory, 'ollama.json.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(destination)


class OllamaHub:
    def __init__(self, directory: Path, host: str | None = None):
        self.directory = directory
        self.settings = read_settings(directory)
        self.api = OllamaAPI(host)
        self.events = queue.Queue()
        self.cancelled = threading.Event()
        self.closed = False
        self.busy = False
        self.state = 'Not checked'
        self.inventory = {'version': 'unknown', 'installed': [], 'loaded': []}
        self.online = False
        self.layers: dict[str, tuple[int, int]] = {}
        self.progress = {'status': 'No download started'}
        self.activation = None
        self.pending_model = None
        self._resume_checked = False

    def save(self):
        write_settings(self.directory, self.settings)

    def start(self, operation: str, model: str | None = None):
        if self.closed:
            return
        if self.busy:
            raise ValueError('An Ollama operation is already running; cancel or wait')
        if operation not in ('refresh', 'pull', 'activate', 'unload'):
            raise ValueError('Unknown Ollama operation')
        if operation != 'refresh':
            model = model_name(model or '')
        self.cancelled.clear()
        self.busy = True
        self.state = {'refresh': 'Checking local server', 'pull': 'Downloading', 'activate': 'Loading into memory', 'unload': 'Unloading'}[operation]
        self.pending_model = model
        if operation != 'refresh':
            self._resume_checked = True
        if operation == 'pull':
            self.layers.clear()
            self.progress = {'status': 'Requesting manifest'}
        if operation == 'unload':
            self.settings['auto_activate'] = False
            self.save()
        threading.Thread(target=self._work, args=(operation, model), daemon=True, name='forge-ollama').start()

    def _work(self, operation, model):
        def emit(kind, value):
            if not self.closed:
                self.events.put((kind, value))
        try:
            if operation == 'pull':
                self.api.pull(model, emit, self.cancelled)
            if self.cancelled.is_set() or self.closed:
                raise ValueError('Operation cancelled; selection was not changed')
            if operation in ('pull', 'activate'):
                snapshot = self.api.inventory()
                names = {m.get('name', m.get('model')) for m in snapshot['installed']}
                if model not in names and model + ':latest' not in names:
                    raise ValueError('Selected model is not installed locally; pull it first')
                # Normalize untagged names to what Ollama actually reports.
                if model not in names:
                    model += ':latest'
                emit('phase', 'Loading into memory (percentage unavailable)')
                if self.cancelled.is_set() or self.closed:
                    raise ValueError('Operation cancelled')
                self.api.warm(model)
            elif operation == 'unload':
                self.api.unload(model)
            snapshot = self.api.inventory()
            if operation == 'unload':
                # An acknowledgement can precede actual residency clearing.
                deadline=time.monotonic()+10
                while any(m.get('name',m.get('model'))==model for m in snapshot['loaded']):
                    if self.cancelled.is_set() or self.closed:raise ValueError('Unload confirmation cancelled')
                    if time.monotonic()>=deadline:raise ValueError('Unload requested but model is still reported loaded; refresh to check residency')
                    time.sleep(.1);snapshot=self.api.inventory()
            if self.cancelled.is_set() or self.closed:
                raise ValueError('Operation cancelled; no automatic activation recorded')
            if operation in ('pull', 'activate'):
                if not any(m.get('name', m.get('model')) == model for m in snapshot['loaded']):
                    raise ValueError('Preload completed but model is not reported loaded; check RAM and server logs')
                emit('activated', model)
            emit('inventory', snapshot)
            emit('done', operation)
        except Exception as error:
            emit('error', str(error))

    def poll(self):
        changed = False
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            changed = True
            if kind == 'progress':
                self.progress = value
                digest = value.get('digest')
                if digest and value.get('total'):
                    total = max(0, int(value['total']))
                    self.layers[digest] = (min(total, max(0, int(value.get('completed', 0)))), total)
            elif kind == 'phase':
                self.state = value
            elif kind == 'inventory':
                self.inventory = value
                self.online = True
            elif kind == 'activated':
                if self.cancelled.is_set() or self.closed:
                    continue
                self.activation = value
                self.settings.update(selected_model=value, auto_activate=True)
                self.save()
            elif kind == 'done':
                self.busy = False
                if self.cancelled.is_set():
                    self.state = 'Cancelled · selection unchanged; check server for residual work'
                    continue
                self.state = 'Ready' if value in ('pull', 'activate') else 'Local server connected'
                if value == 'unload':
                    self.activation = None
                    self.state = 'Unloaded · auto-activation off'
            elif kind == 'error':
                self.busy = False
                self.state = 'Error: ' + value[:450]
                if self.pending_model is None:
                    self.online = False
        if self.online and not self.busy and not self._resume_checked:
            self._resume_checked = True
            model = self.settings.get('selected_model')
            if model and self.settings['auto_activate']:
                # Never automatically pull a missing model.
                if any(m.get('name', m.get('model')) == model for m in self.inventory['installed']):
                    self.start('activate', model)
        return changed

    def cancel(self):
        self.cancelled.set()
        # Closing a response can block; never do it on the TUI thread.
        threading.Thread(target=self.api.cancel, daemon=True).start()
        self.state = 'Cancelling · server work may finish; no selection will be saved'

    def close(self):
        self.closed = True
        self.cancel()

    def progress_text(self):
        phase = self.progress.get('status', 'Waiting')
        digest = self.progress.get('digest')
        if digest in self.layers and self.state == 'Downloading':
            completed, total = self.layers[digest]
            percent = completed / total * 100
            blocks = int(percent // 5)
            bar = '━' * blocks + '─' * (20 - blocks)
            downloaded = sum(v[0] for v in self.layers.values())
            known_total = sum(v[1] for v in self.layers.values())
            return f'{bar} {percent:5.1f}% current layer · {bytes_text(completed)}/{bytes_text(total)}\nKnown layers: {bytes_text(downloaded)}/{bytes_text(known_total)} · {phase} (not an overall model %)'
        return f'{self.state}\nPull phase: {phase} · manifest / verification / loading have no measurable percentage'
