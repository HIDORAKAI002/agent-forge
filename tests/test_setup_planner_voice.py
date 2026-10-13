import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import pytest
from forge.credentials import Credentials, SERVICE
from forge.settings import Preferences, PALETTES
from forge.planner import Planner, DispatchBatch, queue_plan, validate_plan
from forge.profiles import Profile, profiles, recommend
from forge.runtime import Runtime
from forge.voice import Voice

class Vault:
    def __init__(self):self.values={}
    def get_password(self,service,provider):return self.values.get((service,provider))
    def set_password(self,service,provider,value):self.values[service,provider]=value
    def delete_password(self,service,provider):self.values.pop((service,provider),None)


def test_keys_scoped_to_provider_and_not_serialized(project):
    keys=Credentials(Vault());value='TEST_ONLY_FAKE_KEY_NOT_A_CREDENTIAL'
    keys.save('claude',value,persistent=True)
    assert keys.environment('claude')=={'ANTHROPIC_API_KEY':value}
    assert keys.environment('codex')=={}
    assert keys.environment('aider-local')=={}
    assert keys.environment('shell')=={}
    assert value not in json.dumps(Preferences().data)
    keys.remove('claude');assert keys.get('claude') is None
    keys.save('gemini',value);keys.close();assert not keys.memory


def test_no_plaintext_vault_fallback_and_backend_errors_do_not_leak_secrets():
    keys=Credentials();keys.backend=None
    with pytest.raises(ValueError,match='No supported OS vault'):keys.save('codex','TEST_ONLY_KEY',True)
    with pytest.raises(ValueError):keys.save('claude','\nTEST_ONLY_KEY')
    class BrokenVault(Vault):
        def set_password(self,*args):raise RuntimeError(args[-1])
    keys=Credentials(BrokenVault())
    with pytest.raises(ValueError) as error:keys.save('claude','TEST_ONLY_DO_NOT_LEAK',True)
    assert 'TEST_ONLY_DO_NOT_LEAK' not in str(error.value)


def test_codex_auth_uses_pipe_not_args_or_pty(monkeypatch):
    keys=Credentials(Vault());keys.save('codex','TEST_ONLY_OPENAI_KEY',True)
    captured={}
    monkeypatch.setattr('forge.credentials.shutil.which',lambda _: '/fixture/codex')
    def run(argv,**kwargs):
        captured.update(argv=argv,**kwargs);return SimpleNamespace(returncode=0)
    monkeypatch.setattr('forge.credentials.subprocess.run',run)
    keys.codex_login()
    end=time.monotonic()+2
    while keys.busy and time.monotonic()<end:time.sleep(.01)
    assert 'TEST_ONLY_OPENAI_KEY' not in ' '.join(captured['argv'])
    assert captured['input']=='TEST_ONLY_OPENAI_KEY\n'
    assert 'cli_auth_credentials_store="keyring"' in captured['argv']
    assert 'completed' in keys.events.get_nowait()


def test_saved_themes_and_routing_policy(project):
    pref=Preferences();pref.data['theme']='forest';pref.save()
    assert Preferences().data['theme']=='forest' and len(PALETTES)==8
    folder=project/'.agent-forge';folder.mkdir(exist_ok=True)
    (folder/'routing.json').write_text(json.dumps({'claude':'strong','gemini':'free'}))
    registry=profiles(project)
    assert registry['claude'].tier=='strong' and registry['gemini'].tier=='free'
    available=[Profile('strong','strong',('/bin/sh',),('/bin/sh','{prompt}'),'strong'),Profile('free','free',('/bin/sh',),('/bin/sh','{prompt}'),'free')]
    assert recommend(available,'routine')=='free'
    assert recommend(available,'high')=='strong'


@pytest.mark.parametrize('value',[{}, {'tasks':[]}, {'tasks':[{'title':'x','instructions':'y','risk':'routine','depends_on':[0]}]}, {'tasks':[{'title':'x','instructions':'y','risk':'routine','depends_on':[True]}]}, {'tasks':[{'title':'x','instructions':'y','risk':'unsafe','depends_on':[]}]}])
def test_plan_rejects_bad_graphs(value):
    with pytest.raises(ValueError):validate_plan(value)


def test_local_planner_validates_model_and_structured_response():
    class API:
        def inventory(self):return {'installed':[{'name':'fixture:local'}]}
        def json(self,path,body,timeout):
            assert path=='/api/chat' and body['format']['type']=='object'
            assert body['stream'] is False
            return {'message':{'content':json.dumps({'tasks':[{'title':'Fixture: tests','instructions':'Add tests and report checks','risk':'routine','depends_on':[]}]})}}
    planner=Planner();planner.start(API(),'fixture:local','Test the parser',[])
    end=time.monotonic()+2
    while planner.busy and time.monotonic()<end:planner.poll();time.sleep(.01)
    assert planner.draft[0]['title']=='Fixture: tests'
    planner.close()


def test_queue_and_dispatch_are_separate_and_prerequisites_need_review(project):
    runtime=Runtime(project)
    try:
        runtime.profiles={'fixture':Profile('fixture','Fixture CLI',('/bin/sh',),('/bin/sh','-c','printf fixture'),'free')}
        draft=validate_plan({'tasks':[{'title':'First fixture','instructions':'Print fixture','risk':'routine','depends_on':[]},{'title':'Second fixture','instructions':'Print fixture','risk':'routine','depends_on':[0]}]})
        tasks=queue_plan(runtime,draft)
        assert not runtime.sessions and tasks[1]['dependencies']==[tasks[0]['id']]
        batch=DispatchBatch();batch.tick(runtime);assert not runtime.sessions
        batch.authorize(runtime,tasks);batch.tick(runtime)
        assert len(runtime.sessions)==1
        end=time.monotonic()+3
        while time.monotonic()<end:
            runtime.poll()
            if runtime.store.task(tasks[0]['id'])['status']=='needs-review':break
            time.sleep(.02)
        batch.tick(runtime);assert len(runtime.sessions)==1
        runtime.approve(tasks[0]['id'])
        batch.tick(runtime);assert len(runtime.sessions)==2
        batch.pause();assert not batch.grants
    finally:runtime.close()


def test_dispatch_limits_two_tasks_and_revokes_changed_command(project):
    runtime=Runtime(project)
    try:
        runtime.profiles={'fixture':Profile('fixture','Fixture',('/bin/sh',),('/bin/sh','-c','sleep 2'),'free')}
        tasks=[runtime.store.create_task('Fixture '+str(i),'No real provider','fixture') for i in range(3)]
        batch=DispatchBatch();batch.authorize(runtime,tasks);batch.tick(runtime)
        assert sum(s.status=='running' for s in runtime.sessions.values())==2
        assert len(batch.grants)==1
        runtime.profiles['fixture']=Profile('fixture','Changed',('/bin/sh',),('/bin/sh','-c','printf changed'),'strong')
        batch.tick(runtime)
        assert not batch.grants and batch.errors
    finally:runtime.close()


def test_local_coding_profile_uses_selected_ollama_model(project):
    folder=project/'.agent-forge';folder.mkdir(exist_ok=True)
    (folder/'ollama.json').write_text(json.dumps({'selected_model':'fixture:local'}))
    profile=profiles(project)['aider-local']
    assert profile.tier=='local'
    assert 'ollama_chat/fixture:local' in profile.argv
    assert '--message' in profile.task_argv
    assert '--yes-always' not in profile.task_argv
    assert '--no-auto-commits' in profile.task_argv


def test_voice_microphone_capture_is_bounded_and_no_text_is_executed(tmp_path,monkeypatch):
    import sys
    class Stop(Exception):pass
    class Stream:
        active=False
        def __init__(self,**kwargs):
            assert kwargs['samplerate']==16000 and kwargs['channels']==1
            self.callback=kwargs['callback']
        def start(self):self.active=True;self.callback(b'\0'*32000,16000,None,None)
        def stop(self):self.active=False
        def close(self):pass
    monkeypatch.setitem(sys.modules,'sounddevice',SimpleNamespace(RawInputStream=Stream,CallbackStop=Stop))
    voice=Voice(tmp_path);voice.model=object();voice.start()
    end=time.monotonic()+2
    while voice.busy and time.monotonic()<end:time.sleep(.01)
    assert voice.recording and voice.seconds==1
    voice.stop(False)
    while voice.busy and time.monotonic()<end:time.sleep(.01)
    assert not voice.chunks and voice.model_name is None
    voice.close()


async def test_setup_masked_key_and_theme_changes(project):
    from forge.tui import ForgeApp
    from textual.widgets import Input,Select,TabbedContent
    app=ForgeApp(project)
    try:
        async with app.run_test(size=(150,50)) as pilot:
            await pilot.pause()
            assert app.ui('#tabs',TabbedContent).active=='setup'
            app.ui('#setup-theme',Select).value='sakura';await pilot.pause()
            assert app.palette=='sakura'
            widget=app.ui('#provider-key',Input)
            assert widget.password
            widget.value='TEST_ONLY_MASKED_KEY'
            app.setup_action('setup-save-key');await pilot.pause(.2)
            assert widget.value==''
            assert app.runtime.credentials.get('claude')=='TEST_ONLY_MASKED_KEY'
            assert 'TEST_ONLY_MASKED_KEY' not in json.dumps(app.runtime.store.events())
            assert not app.ui('#command',Input).history
            widget.value='TEST_ONLY_UNSAVED_KEY'
            app.ui('#key-provider',Select).value='codex'
            await pilot.pause()
            assert widget.value==''
    finally:app.runtime.close()


async def test_voice_draft_never_auto_submits_and_can_fill_goal(project):
    from forge.tui import ForgeApp,DictationScreen
    from textual.widgets import TextArea
    app=ForgeApp(project)
    try:
        async with app.run_test(size=(150,50)) as pilot:
            app.show_voice_draft('Fixture dictation: add parser tests')
            await pilot.pause()
            assert isinstance(app.screen,DictationScreen)
            assert not app.runtime.sessions
            await pilot.click('#voice-goal');await pilot.pause()
            assert app.ui('#planner-goal',TextArea).text=='Fixture dictation: add parser tests'
            assert not app.runtime.sessions
    finally:app.runtime.close()


def test_installer_rejects_command_injection_and_existing_unmanaged_command(tmp_path):
    import subprocess
    script=Path(__file__).resolve().parents[1]/'scripts/install.sh'
    env=dict(os.environ,FORGE_COMMAND='bad;name',FORGE_INSTALL_ROOT=str(tmp_path/'app'),FORGE_BIN_ROOT=str(tmp_path/'bin'))
    result=subprocess.run(['bash',str(script)],env=env,capture_output=True,text=True)
    assert result.returncode!=0 and 'Invalid command' in result.stderr
    env['FORGE_COMMAND']='agent-command';(tmp_path/'bin').mkdir()
    (tmp_path/'bin/agent-command').write_text('not our app')
    result=subprocess.run(['bash',str(script)],env=env,capture_output=True,text=True)
    assert result.returncode!=0 and 'not managed' in result.stderr


def test_runtime_injects_only_corresponding_managed_key(project):
    runtime=Runtime(project)
    try:
        runtime.credentials.save('claude','TEST_ONLY_RUNTIME_KEY')
        runtime.profiles['claude']=Profile('claude','Key fixture',('/bin/sh','-c','test -n "$ANTHROPIC_API_KEY" && printf KEY_SCOPE_OK'))
        session=runtime.launch('claude')
        end=time.monotonic()+3
        while session.status=='running' and time.monotonic()<end:runtime.poll();time.sleep(.02)
        assert 'KEY_SCOPE_OK' in '\n'.join(session.screen.display)
        assert not runtime.credentials.environment('shell')
        assert 'TEST_ONLY_RUNTIME_KEY' not in json.dumps(runtime.store.events())
    finally:runtime.close()


async def test_provider_installer_requires_approval_and_cancel_runs_nothing(project):
    from forge.tui import ForgeApp,ConfirmScreen
    app=ForgeApp(project)
    try:
        async with app.run_test(size=(150,50)) as pilot:
            app.setup_action('setup-install-cli');await pilot.pause()
            assert isinstance(app.screen,ConfirmScreen)
            assert 'https://claude.ai/install.sh' in app.screen.body
            assert not app.runtime.sessions
            await pilot.press('n');await pilot.pause()
            assert not app.runtime.sessions
    finally:app.runtime.close()
