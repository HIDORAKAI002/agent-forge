"""Actual native kernel checks; Linux skips are never counted as Windows evidence."""
import json,os,subprocess,sys,time
from pathlib import Path
import pytest
pytestmark=pytest.mark.skipif(os.name!='nt',reason='Native Windows LPAC required')
@pytest.fixture(autouse=True)
def enable_native_probe(monkeypatch):monkeypatch.setenv('FORGE_WINDOWS_ISOLATION_EXPERIMENTAL','1')
from forge.sandbox import Sandbox


def setup(tmp_path,monkeypatch):
    project=tmp_path/'project';reference=tmp_path/'reference';denied=tmp_path/'denied'
    for path in (project,reference,denied):path.mkdir()
    (reference/'read.txt').write_text('APPROVED');(denied/'secret.txt').write_text('HIDDEN')
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'trusted-config'))
    sandbox=Sandbox(project);sandbox.save({'enabled':True,'network':False,'read_only':[str(reference)]})
    return project,reference,denied,sandbox


def test_native_stdio_filesystem_and_cleanup(tmp_path,monkeypatch):
    import win32security as S
    p,r,d,s=setup(tmp_path,monkeypatch)
    before=S.GetNamedSecurityInfo(str(p),S.SE_FILE_OBJECT,S.DACL_SECURITY_INFORMATION|0x10)
    before_acl=[before.GetSecurityDescriptorDacl().GetAce(i) for i in range(before.GetSecurityDescriptorDacl().GetAceCount())]
    before_label=before.GetSecurityDescriptorSacl()
    code=f'echo PROJECT_OK>"{p / "written.txt"}" & type "{r / "read.txt"}" & type "{d / "secret.txt"}" & echo ESCAPE>"{d / "outside.txt"}" & echo ESCAPE>"{r / "blocked.txt"}" & echo NATIVE_BOUNDARY_DONE'
    argv,env=s.wrap([os.environ['COMSPEC'],'/d','/c',code],p,dict(os.environ,OTHER_API_KEY='FAKE_NOT_INHERITED'))
    result=subprocess.run(argv,cwd=p,env=env,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert 'APPROVED' in result.stdout and 'HIDDEN' not in result.stdout,(result.stdout,result.stderr)
    assert (p/'written.txt').exists() and not (d/'outside.txt').exists() and not (r/'blocked.txt').exists()
    after=S.GetNamedSecurityInfo(str(p),S.SE_FILE_OBJECT,S.DACL_SECURITY_INFORMATION|0x10)
    after_acl=[after.GetSecurityDescriptorDacl().GetAce(i) for i in range(after.GetSecurityDescriptorDacl().GetAceCount())]
    # Empty-vs-absent SACL serialization is not a permission change. Actual
    # ACEs (including inherited flags) and integrity entries must be restored.
    assert before_acl==after_acl,(before_acl,after_acl)
    after_label=after.GetSecurityDescriptorSacl()
    entries=lambda acl:[] if acl is None else [acl.GetAce(i) for i in range(acl.GetAceCount())]
    assert entries(before_label)==entries(after_label)
    assert not list((tmp_path/'trusted-config/windows-boundary').glob('AgentForge.*.json'))


def test_native_git_control_readonly(tmp_path,monkeypatch):
    p,r,d,s=setup(tmp_path,monkeypatch);metadata=p/'.git';metadata.mkdir();(metadata/'config').write_text('CANONICAL')
    argv,env=s.wrap([os.environ['COMSPEC'],'/d','/c',f'echo PROJECT_OK>"{p / "allowed.txt"}" & echo CORRUPT>"{metadata / "config"}" & echo DONE'],p,dict(os.environ))
    result=subprocess.run(argv,cwd=p,env=env,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert (metadata/'config').read_text()=='CANONICAL'
    assert (p/'allowed.txt').exists(),(result.stdout,result.stderr)


def test_native_isolated_conpty(tmp_path,monkeypatch):
    from forge.terminal import Session
    p,r,d,s=setup(tmp_path,monkeypatch);argv,env=s.wrap([os.environ['COMSPEC'],'/d'],p,dict(os.environ))
    session=Session(argv,str(p),'native-isolation',env=env,rows=30,cols=100)
    try:
        session.write('echo REAL_ISOLATED_CONPTY\r')
        end=time.monotonic()+20
        while time.monotonic()<end:
            session.drain()
            if 'REAL_ISOLATED_CONPTY' in '\n'.join(session.screen.display):break
            time.sleep(.03)
        else:raise AssertionError(f'Native isolated terminal did not render: status={session.status} exit={session.exit_code} broker={session.process.poll()} screen={repr(chr(10).join(session.screen.display))[:700]}')
        session.resize(35,110);session.write('exit\r')
        end=time.monotonic()+20
        while session.status=='running' and time.monotonic()<end:session.drain();time.sleep(.03)
        assert session.exit_code==0
    finally:session.stop()


def test_native_reparse_and_hardlink_inputs_refused(tmp_path,monkeypatch):
    p,r,d,s=setup(tmp_path,monkeypatch);source=d/'secret.txt';os.link(source,p/'linked.txt')
    with pytest.raises(ValueError,match='hard-linked'):s.save(s.policy)
    (p/'linked.txt').unlink()
    result=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(p/'junction'),str(d)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    with pytest.raises(ValueError,match='reparse'):s.save(s.policy)

def test_native_profile_grant_creation_and_restore(tmp_path,monkeypatch):
    from forge.windows_isolation import Boundary
    p,r,d,s=setup(tmp_path,monkeypatch);boundary=Boundary(p,s.policy)
    try:
        boundary.open();assert boundary.sid and boundary.home.is_dir()
    finally:boundary.close()

def test_native_broker_interruption_recovers_grants(tmp_path,monkeypatch):
    """Kill the trusted wrapper: its Job must die before journal recovery."""
    import psutil
    from forge.windows_isolation import Boundary
    p,r,d,s=setup(tmp_path,monkeypatch)
    command=f'echo STARTED>"{p / "started.txt"}" & set /p WAIT='
    argv,env=s.wrap([os.environ['COMSPEC'],'/d','/c',command],p,dict(os.environ))
    wrapper=subprocess.Popen(argv,cwd=p,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    record=None
    try:
        end=time.monotonic()+20
        while time.monotonic()<end:
            journals=list((tmp_path/'trusted-config/windows-boundary').glob('AgentForge.*.json'))
            if (p/'started.txt').exists() and journals:
                record=json.loads(journals[0].read_text());break
            if wrapper.poll() is not None:
                raise AssertionError(f'Wrapper exited before interruption: {wrapper.communicate()}')
            time.sleep(.03)
        assert record and 'child' in record,'Native command never became ready'
        wrapper.kill();wrapper.wait(timeout=10)
        process=psutil.Process(record['child']['pid']) if psutil.pid_exists(record['child']['pid']) else None
        if process and process.create_time()==record['child']['created']:process.wait(timeout=10)
        recovery=Boundary(p,s.policy)
        try:recovery.open()
        finally:recovery.close()
        assert not list((tmp_path/'trusted-config/windows-boundary').glob('AgentForge.*.json'))
    finally:
        if wrapper.poll() is None:wrapper.kill();wrapper.wait(timeout=10)
        for pipe in (wrapper.stdin,wrapper.stdout,wrapper.stderr):pipe.close()

def test_native_postlaunch_junction_cannot_grant_external_access(tmp_path,monkeypatch):
    p,r,d,s=setup(tmp_path,monkeypatch)
    junction=p/'late-junction'
    command=f'mklink /J "{junction}" "{d}" & type "{junction / "secret.txt"}" & echo ESCAPE>"{junction / "outside.txt"}" & echo PROJECT_OK>"{p / "allowed.txt"}" & echo FINISHED'
    argv,env=s.wrap([os.environ['COMSPEC'],'/d','/c',command],p,dict(os.environ))
    result=subprocess.run(argv,cwd=p,env=env,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert (p/'allowed.txt').exists()
    assert 'HIDDEN' not in result.stdout and not (d/'outside.txt').exists()
    assert (d/'secret.txt').read_text()=='HIDDEN'
    assert not list((tmp_path/'trusted-config/windows-boundary').glob('AgentForge.*.json'))
