import json
from pathlib import Path
import pytest
from forge.health import diagnose,probe_ollama


def test_health_has_no_state_changes_or_secret_values(tmp_path,monkeypatch):
    project=tmp_path/'project';project.mkdir()
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'never-created'))
    monkeypatch.setenv('OPENAI_API_KEY','FAKE_SECRET_SHOULD_NOT_APPEAR')
    monkeypatch.setenv('HTTPS_PROXY','http://FAKE_PROXY_PASSWORD@example.invalid')
    report=diagnose(project)
    text=json.dumps(report)
    assert 'FAKE_SECRET' not in text and 'FAKE_PROXY_PASSWORD' not in text
    assert not (tmp_path/'never-created').exists() and list(project.iterdir())==[]
    assert report['ollama']['status']=='not-probed'
    assert report['requirements']['consumer_pro_subscription'] is False
    assert report['ready_for']['local'] is False


@pytest.mark.parametrize('url',['https://example.com','http://example.com','http://user:password@127.0.0.1:11434','http://127.0.0.1/?secret=abc','http://127.0.0.1/path'])
def test_health_probe_refuses_remote_or_credential_urls(url):
    with pytest.raises(ValueError,match='loopback'):probe_ollama(url)


def test_ollama_probe_validates_schema_without_echoing_names(monkeypatch):
    class Response:
        def __init__(self,value):self.value=value
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return json.dumps(self.value).encode()
    class Opener:
        def open(self,request,timeout):
            assert not request.has_header('Authorization')
            return Response({'version':'test'} if request.full_url.endswith('/version') else {'models':[{'name':'PRIVATE_MODEL_NAME'}]})
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    report=probe_ollama()
    assert report['status']=='reachable' and report['installed_model_count']==1
    assert 'PRIVATE_MODEL_NAME' not in json.dumps(report)


def test_missing_project_is_not_core_ready(tmp_path):
    report=diagnose(tmp_path/'missing')
    assert report['project_exists'] is False and report['ready_for']['core'] is False
    assert not (tmp_path/'missing').exists()


def test_doctor_cli_full_is_read_only_and_has_machine_exit_status(tmp_path,capsys):
    from forge.__main__ import main
    missing=tmp_path/'missing'
    assert main(['--project',str(missing),'doctor','--full','--require','core'])==1
    report=json.loads(capsys.readouterr().out)
    assert report['ready_for']['core'] is False and not missing.exists()


async def test_doctor_command_does_not_read_keys_or_probe_network(tmp_path,monkeypatch):
    from forge.tui import ForgeApp
    from forge import health
    app=ForgeApp(tmp_path)
    monkeypatch.setattr(health,'probe_ollama',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Unexpected network probe')))
    monkeypatch.setattr(app.runtime.credentials,'get',lambda *a:(_ for _ in ()).throw(AssertionError('Unexpected credential read')))
    try:
        async with app.run_test(size=(140,45)) as pilot:
            await pilot.pause();app.execute('/doctor');await pilot.pause()
            assert not app.runtime.sessions
            assert app.ui('#conversation').display
    finally:
        app.tool_gateway.close();app.ruflo.close();app.ollama.close();app.planner.close();app.voice.close();app.runtime.close()


def test_actual_loopback_probe_rejects_redirect_and_oversized_body():
    import threading
    from http.server import BaseHTTPRequestHandler,HTTPServer
    class Handler(BaseHTTPRequestHandler):
        mode='redirect'
        hits=[]
        def log_message(self,*args):pass
        def do_GET(self):
            self.hits.append(self.path)
            if self.mode=='redirect':
                self.send_response(302);self.send_header('Location','http://127.0.0.1:1/SHOULD_NOT_FOLLOW');self.end_headers()
            else:
                self.send_response(200);self.end_headers();self.wfile.write(b' '*65537)
    server=HTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}'
        assert probe_ollama(url)['status']=='unavailable'
        assert Handler.hits==['/api/version']
        Handler.mode='oversized';Handler.hits=[]
        assert probe_ollama(url)['status']=='unavailable'
        assert Handler.hits==['/api/version']
    finally:
        server.shutdown();thread.join(2);server.server_close()
