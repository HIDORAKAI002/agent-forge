import json,os,shutil,subprocess,sys,time
from pathlib import Path
import pytest
from forge.platform_support import WorkspaceLock,windows_command
from forge.sandbox import Sandbox
from forge.ruflo import safe_environment,decode_result,RufloBridge

def test_cross_platform_lock(tmp_path):
    path=tmp_path/'lock';lock=WorkspaceLock(path)
    with pytest.raises(ValueError):WorkspaceLock(path)
    lock.close();WorkspaceLock(path).close()

def test_standard_npm_shim_resolves_without_shell(tmp_path,monkeypatch):
    shim=tmp_path/'tool.cmd';entry=tmp_path/'node_modules'/'tool'/'main.js';entry.parent.mkdir(parents=True);entry.write_text('')
    shim.write_text('@echo off\n"%dp0%\\node.exe" "%dp0%\\node_modules\\tool\\main.js" %*')
    node=tmp_path/'node.exe';node.write_text('')
    monkeypatch.setattr(shutil,'which',lambda x:str(shim) if x=='tool' else None)
    attack='" & echo INJECTION > escaped.txt & "'
    argv,env=windows_command(['tool',attack],{'PATH':'TEST'})
    assert argv==[str(node),str(entry),attack];assert env=={'PATH':'TEST'}

def test_arbitrary_batch_shim_refused(tmp_path,monkeypatch):
    p=tmp_path/'bad.cmd';p.write_text('@echo off\necho %*')
    monkeypatch.setattr(shutil,'which',lambda _:str(p))
    with pytest.raises(ValueError,match='native executable'):windows_command(['bad','task'],{})

def test_sandbox_config_and_secret_scoping(tmp_path,monkeypatch):
    project=tmp_path/'project';project.mkdir();references=tmp_path/'reference';references.mkdir()
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'trusted-user-config'))
    monkeypatch.setattr(shutil,'which',lambda p:'/usr/bin/bwrap' if p=='bwrap' else None)
    s=Sandbox(project)
    if not sys.platform.startswith('linux'):return
    s.save({'enabled':True,'read_only':[str(references)],'network':False})
    argv,env=s.wrap(['/usr/bin/python3','-c','print(1)'],project,{'PATH':'/usr/bin','SSH_AUTH_SOCK':'secret-socket','OTHER_API_KEY':'not-approved'}, {'ANTHROPIC_API_KEY':'FAKE_SCOPED_KEY'})
    assert 'FAKE_SCOPED_KEY' not in json.dumps(argv)
    assert env['ANTHROPIC_API_KEY']=='FAKE_SCOPED_KEY' and 'SSH_AUTH_SOCK' not in env and 'OTHER_API_KEY' not in env
    assert '--unshare-all' in argv and '--share-net' not in argv
    assert '--ro-bind' in argv and '--bind' in argv and '/proc' not in argv
    with pytest.raises(ValueError):s.save({'enabled':True,'read_only':[str(tmp_path)],'network':False})
    monkeypatch.setattr(shutil,'which',lambda _:None)
    with pytest.raises(ValueError,match='refusing'):s.wrap(['/bin/sh'],project,{})

def test_policy_cannot_live_in_agent_writable_project(tmp_path,monkeypatch):
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'user-config'))
    s=Sandbox(tmp_path)
    with pytest.raises(ValueError,match='outside writable'):s.save({'enabled':True,'read_only':[],'network':False})

def test_ruflo_environment_does_not_inherit_secrets(tmp_path,monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','FAKE');monkeypatch.setenv('GITHUB_TOKEN','FAKE');monkeypatch.setenv('SSH_AUTH_SOCK','FAKE')
    env=safe_environment(tmp_path)
    assert 'ANTHROPIC_API_KEY' not in env and 'GITHUB_TOKEN' not in env and 'SSH_AUTH_SOCK' not in env
    assert env['HOME']==str(tmp_path)

def test_ruflo_result_error_and_missing_install(project,monkeypatch):
    from types import SimpleNamespace as S
    with pytest.raises(ValueError):decode_result(S(isError=True,structuredContent=None,content=[]))
    monkeypatch.delenv('FORGE_RUFLO_BIN',raising=False);monkeypatch.setattr(shutil,'which',lambda _:None)
    from forge.store import Store
    store=Store(project);bridge=RufloBridge(store)
    try:
        with pytest.raises(ValueError,match='3.56.9'):bridge.enable()
        with pytest.raises(ValueError,match='not connected'):bridge.request('context','test')
        assert store.tasks()==[]
    finally:bridge.close();store.close()

def test_actual_sandbox_permissions(tmp_path,monkeypatch):
    if os.environ.get('FORGE_SANDBOX_TESTS')!='1':pytest.skip('Real sandbox test explicitly enabled in Linux CI')
    assert shutil.which('bwrap'),'Bubblewrap must be installed for integration testing'
    p=tmp_path/'project';r=tmp_path/'reference';d=tmp_path/'denied'
    for f in (p,r,d):f.mkdir()
    (r/'read').write_text('read');(d/'secret').write_text('hidden');(p/'escape').symlink_to(d)
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'trusted-config'));s=Sandbox(p)
    grants=[str(r)]
    if not Path(sys.executable).resolve().is_relative_to(Path('/usr')):grants.append(str(Path(sys.base_prefix).resolve()))
    s.save({'enabled':True,'read_only':grants,'network':False})
    code=f'''import pathlib,socket,os
p=pathlib.Path({str(p)!r});r=pathlib.Path({str(r)!r});d=pathlib.Path({str(d)!r})
(p/'written').write_text('ok');assert (r/'read').read_text()=='read';assert 'OTHER_KEY' not in os.environ
for target,writing in [(r/'cannot-write',True),(d/'secret',False),(p/'escape/secret',False),(d/'cannot-write',True)]:
 try:target.write_text('bad') if writing else target.read_text()
 except OSError:pass
 else:raise AssertionError('Sandbox boundary escaped')
try:socket.create_connection(('1.1.1.1',443),timeout=1)
except OSError:pass
else:raise AssertionError('Network not blocked')
print('SANDBOX_ENFORCED')
'''
    argv,env=s.wrap([str(Path(sys.executable).resolve()),'-c',code],p,dict(os.environ,OTHER_KEY='FAKE'))
    result=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert 'SANDBOX_ENFORCED' in result.stdout

async def test_permissions_and_ruflo_controls_require_confirmation(project):
    from forge.tui import ForgeApp
    app=ForgeApp(project)
    try:
        async with app.run_test(size=(150,50)) as pilot:
            await pilot.pause();app.setup_action('setup-ruflo-connect');await pilot.pause();await pilot.press('n');await pilot.pause()
            assert not app.ruflo.enabled
            app.setup_action('setup-sandbox-save');await pilot.pause();await pilot.press('n');await pilot.pause()
            assert not app.runtime.sandbox.policy['enabled']
    finally:app.ruflo.close();app.ollama.close();app.voice.close();app.runtime.close()

def test_actual_ruflo_bridge(project,monkeypatch):
    if os.environ.get('FORGE_RUFLO_TESTS')!='1':pytest.skip('Pinned live Ruflo integration explicitly enabled in dedicated CI')
    from forge.store import Store
    store=Store(project);memory=store.remember('Run parser tests before review','decision','user',True);bridge=RufloBridge(store)
    def wait(fn):
        end=time.monotonic()+150
        while time.monotonic()<end:
            if fn():return
            time.sleep(.1)
        raise AssertionError(bridge.state)
    try:
        bridge.enable();wait(lambda:bridge.connected);bridge.poll();bridge.request('context','Add parser tests');wait(lambda:not bridge.busy)
        result=next(v for k,v in bridge.poll() if k=='context')
        assert memory['id'] in [m['id'] for m in result['memories']]
        assert result['route_hint']['model'] and store.tasks()==[]
    finally:bridge.close();store.close()
