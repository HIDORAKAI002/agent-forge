import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from forge.ollama import OllamaAPI, OllamaHub, endpoint, model_name, local_model, read_settings, write_settings


@pytest.fixture
def ollama_server():
    state = {'installed': False, 'loaded': False, 'requests': [], 'mode': 'ok', 'delay': 0}
    model = {'name': 'fixture:local', 'size': 2_000_000, 'size_vram': 1_000_000, 'details': {'parameter_size': 'fixture', 'quantization_level': 'TEST'}}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            state['requests'].append((self.path, None))
            data = {'/api/version': {'version': 'HTTP-fixture'}, '/api/tags': {'models': ([model] if state['installed'] else []) + [{'name': 'hidden:latest', 'remote_host': 'https://cloud.example'}]}, '/api/ps': {'models': [model] if state['loaded'] else []}}.get(self.path, {})
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(data).encode())
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['requests'].append((self.path, body))
            self.send_response(200); self.end_headers()
            if self.path == '/api/pull':
                events = [{'status':'pulling manifest'}, {'status':'pulling abc','digest':'abc','total':1000,'completed':250}, {'status':'pulling abc','digest':'abc','total':1000,'completed':1000}, {'status':'pulling def','digest':'def','total':2000,'completed':500}, {'status':'verifying sha256 digest'}]
                if state['mode'] == 'error': events.append({'error':'disk full'})
                elif state['mode'] != 'eof': events.append({'status':'success'})
                try:
                    for event in events:
                        if event.get('status') == 'success':
                            state['installed'] = True
                        self.wfile.write(json.dumps(event).encode()+b'\n'); self.wfile.flush()
                        time.sleep(state['delay'])
                    state['installed'] = state['mode'] == 'ok'
                except (BrokenPipeError, ConnectionResetError): pass
            else:
                state['loaded'] = body.get('keep_alive') != 0
                self.wfile.write(b'{"done":true}')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    yield f'http://127.0.0.1:{server.server_port}', state
    server.shutdown(); server.server_close()


def finish(hub, timeout=5):
    end = time.monotonic()+timeout
    while time.monotonic()<end:
        hub.poll()
        if not hub.busy: return
        time.sleep(.01)
    raise AssertionError('worker did not finish')


@pytest.mark.parametrize('host', ['https://127.0.0.1:11434','http://example.com:11434','http://127.0.0.1@evil.test','http://u:p@localhost','http://localhost/path','http://localhost?redirect=evil'])
def test_remote_hosts_rejected(host):
    with pytest.raises(ValueError): endpoint(host)


@pytest.mark.parametrize('model', ['x;touch /tmp/a','$(whoami)', '-x', 'x:cloud', 'x-cloud', '../model', 'https://example.com/model'])
def test_invalid_or_cloud_models_rejected(model):
    with pytest.raises(ValueError): model_name(model)


def test_pull_stream_real_layer_percent_and_failure(ollama_server):
    host,state = ollama_server
    api=OllamaAPI(host); seen=[]
    api.pull('fixture:local',lambda kind,event: seen.append(event),threading.Event())
    assert seen[1]['completed']/seen[1]['total'] == .25
    assert seen[3]['digest']=='def' and seen[-1]['status']=='success'
    assert state['requests'][-1][1]['stream'] is True
    state['mode']='eof'
    with pytest.raises(ValueError, match='without a verified success'): api.pull('fixture:local',lambda *_:None,threading.Event())
    state['mode']='error'
    with pytest.raises(ValueError, match='disk full'): api.pull('fixture:local',lambda *_:None,threading.Event())


def test_pull_autoactivates_persists_and_unloads(tmp_path, ollama_server):
    host,state = ollama_server; hub=OllamaHub(tmp_path,host)
    try:
        hub.start('pull','fixture:local'); finish(hub)
        assert hub.state=='Ready'
        assert hub.settings['selected_model']=='fixture:local'
        assert hub.settings['auto_activate']
        assert read_settings(tmp_path)['selected_model']=='fixture:local'
        assert len(hub.inventory['installed'])==1  # remote model excluded
        assert hub.inventory['loaded']
        generates=[b for p,b in state['requests'] if p=='/api/generate']
        assert generates[-1]=={'model':'fixture:local','stream':False,'keep_alive':'5m'}
        hub.start('unload','fixture:local'); finish(hub)
        assert not hub.settings['auto_activate'] and not state['loaded']
    finally: hub.close()


def test_saved_selection_autoactivates_but_never_downloads(tmp_path,ollama_server):
    host,state=ollama_server
    write_settings(tmp_path,{'selected_model':'fixture:local','auto_activate':True,'tutorial_completed':True})
    hub=OllamaHub(tmp_path,host); state['installed']=True
    try:
        hub.start('refresh'); finish(hub)
        assert state['loaded'] and hub.activation=='fixture:local'
        assert not any(p=='/api/pull' for p,b in state['requests'])
    finally: hub.close()
    state['requests'].clear(); state['installed']=False; state['loaded']=False
    hub=OllamaHub(tmp_path,host)
    try:
        hub.start('refresh'); finish(hub)
        assert not any(p in ('/api/pull','/api/generate') for p,b in state['requests'])
    finally: hub.close()


def test_use_missing_does_not_pull_and_cancel_does_not_select(tmp_path,ollama_server):
    host,state=ollama_server; hub=OllamaHub(tmp_path,host)
    try:
        hub.start('activate','fixture:local'); finish(hub)
        assert 'not installed locally' in hub.state
        assert not any(p=='/api/pull' for p,b in state['requests'])
        state['delay']=.15
        hub.start('pull','fixture:local'); time.sleep(.08); hub.cancel(); finish(hub)
        assert hub.settings['selected_model'] is None
        assert not state['loaded']
    finally: hub.close()


def test_progress_unknown_phases_and_per_layer_not_global(tmp_path,ollama_server):
    hub=OllamaHub(tmp_path,ollama_server[0]); hub.state='Downloading'
    hub.events.put(('progress',{'status':'pulling abc','digest':'abc','total':1000,'completed':250})); hub.poll()
    assert '25.0%' in hub.progress_text() and 'not an overall model %' in hub.progress_text()
    hub.events.put(('progress',{'status':'verifying sha256 digest'})); hub.poll()
    assert 'no measurable percentage' in hub.progress_text()
    hub.close()


def test_settings_symlink_and_remote_metadata_rejected(tmp_path):
    outside=tmp_path/'outside'; outside.write_text('{}')
    (tmp_path/'ollama.json').symlink_to(outside)
    with pytest.raises(ValueError,match='symbolic link'): read_settings(tmp_path)
    assert not local_model({'name':'ordinary:latest','remote_model':'remote'})
    assert not local_model({'name':'something:cloud'})


async def test_model_tutorial_confirmation_and_activation(project,ollama_server,monkeypatch):
    from forge.tui import ForgeApp, ConfirmScreen
    from textual.widgets import Input, TabbedContent, DataTable
    monkeypatch.setenv('OLLAMA_HOST',ollama_server[0])
    app=ForgeApp(project)
    try:
        async with app.run_test(size=(150,50)) as pilot:
            await pilot.pause(.3)
            assert app.ui('#tabs',TabbedContent).active=='models'
            assert app.ui('#model-tutorial').display
            app.ui('#model-tag',Input).value='fixture:local'
            app.model_action('model-pull')
            await pilot.pause()
            assert isinstance(app.screen,ConfirmScreen)
            assert not any(p=='/api/pull' for p,b in ollama_server[1]['requests'])
            await pilot.press('y'); await pilot.pause(.7)
            assert app.ollama.settings['selected_model']=='fixture:local'
            assert app.ui('#model-table',DataTable).row_count==1
            assert app.runtime.profiles['ollama'].argv==('ollama','run','fixture:local')
            assert app.runtime.profiles['ollama'].task_argv is None
            app.model_action('model-tutorial-done')
            assert not app.ui('#model-tutorial').display
            app.execute('/tutorial')
            app.refresh_models()
            assert app.ui('#model-tutorial').display
            assert not app.runtime.sessions  # warm API is not a shell/coding task
    finally: app.runtime.close()

async def test_open_chat_runs_cli_with_selected_model_and_loopback_env(project,ollama_server,monkeypatch,tmp_path):
    import os
    from forge.tui import ForgeApp
    from textual.widgets import Input
    executable=tmp_path/'ollama'
    executable.write_text('#!/bin/sh\nprintf "LOCAL_OLLAMA_CLI_FIXTURE %s %s %s\\n" "$1" "$2" "$OLLAMA_HOST"\nread line\nprintf "INPUT:%s\\n" "$line"\n')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH',str(tmp_path)+os.pathsep+os.environ['PATH'])
    monkeypatch.setenv('OLLAMA_HOST',ollama_server[0])
    ollama_server[1]['installed']=True
    app=ForgeApp(project)
    try:
        async with app.run_test(size=(150,50)) as pilot:
            await pilot.pause(.3)
            app.ui('#model-tag',Input).value='fixture:local'
            app.start_model('activate','fixture:local')
            await pilot.pause(.5)
            assert app.ollama.settings['selected_model']=='fixture:local'
            app.model_action('model-chat'); await pilot.pause(.3)
            session=app.runtime.session(app.active)
            output='\n'.join(session.screen.display)
            assert 'LOCAL_OLLAMA_CLI_FIXTURE run fixture:local' in output
            assert ollama_server[0] in output
            session.write('hello fixture\n'); await pilot.pause(.3)
            assert 'INPUT:hello fixture' in '\n'.join(session.screen.display)
    finally: app.runtime.close()


def test_api_refuses_redirects(ollama_server):
    from forge.ollama import NoRedirect
    with pytest.raises(ValueError,match='redirect'):
        NoRedirect().redirect_request(None,None,302,None,None,'http://outside.test')


def test_fast_cli_startup_output_survives_blank_bottom_resize():
    import pyte
    from forge.terminal import ForgeScreen
    screen=ForgeScreen(90,24)
    pyte.Stream(screen).feed('FAST_CLI_STARTUP\r\n')
    screen.resize(lines=23,columns=111)
    assert screen.display[0].startswith('FAST_CLI_STARTUP')
    assert screen.cursor.y==1
