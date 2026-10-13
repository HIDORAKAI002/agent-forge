"""Real ConPTY tests run only on native Windows; never simulated as Linux passes."""
import os,sys,time,subprocess,json
from pathlib import Path
import psutil,pytest
pytestmark=pytest.mark.skipif(os.name!='nt',reason='Native Windows required')
from forge.terminal import Session

def wait(s,predicate,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        s.drain()
        if predicate():return
        time.sleep(.03)
    raise AssertionError('ConPTY timed out: '+ '\n'.join(s.screen.display)[-2000:])

def test_native_conpty_input_resize_and_exit(tmp_path):
    code='import os;print("WINDOWS_CONPTY_READY",flush=True);v=input();print("VALUE="+v,flush=True);input();print("GEOMETRY="+str(os.get_terminal_size()),flush=True)'
    s=Session([sys.executable,'-c',code],str(tmp_path),'test',rows=30,cols=100)
    try:
        wait(s,lambda:'WINDOWS_CONPTY_READY' in '\n'.join(s.screen.display));s.write('REAL_INPUT\r');wait(s,lambda:'VALUE=REAL_INPUT' in '\n'.join(s.screen.display))
        s.resize(35,110);time.sleep(.3);s.write('\r');wait(s,lambda:s.status=='exited');assert s.exit_code==0
        assert 'columns=110' in '\n'.join(s.screen.display)
    finally:s.stop()

def test_native_job_cleanup_kills_descendant(tmp_path):
    pidfile=tmp_path/'child.pid'
    code=f'import subprocess,sys,time,pathlib;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);pathlib.Path({str(pidfile)!r}).write_text(str(p.pid));print("SPAWNED",flush=True);time.sleep(60)'
    s=Session([sys.executable,'-c',code],str(tmp_path),'cleanup')
    try:
        wait(s,lambda:pidfile.exists());pid=int(pidfile.read_text());s.stop();wait(s,lambda:s.status=='exited')
        end=time.monotonic()+5
        while psutil.pid_exists(pid) and time.monotonic()<end:time.sleep(.05)
        assert not psutil.pid_exists(pid)
    finally:s.stop()

def test_windows_runtime_and_lock(tmp_path):
    from forge.runtime import Runtime
    r=Runtime(tmp_path)
    try:
        assert r.profiles['shell'].available
        with pytest.raises(ValueError):Runtime(tmp_path)
        s=r.launch('shell');s.write('echo NATIVE_CMD_SHELL\r')
        end=time.monotonic()+15
        while time.monotonic()<end:
            r.poll()
            if 'NATIVE_CMD_SHELL' in '\n'.join(s.screen.display):break
            time.sleep(.03)
        else:raise AssertionError('Native shell input failed')
    finally:r.close()

def test_native_tui_and_installed_launcher(tmp_path):
    project=tmp_path/'project';project.mkdir();env=dict(os.environ,FORGE_CONFIG_HOME=str(tmp_path/'trusted-config'))
    commands=[[sys.executable,'-m','forge','--project',str(project)]]
    if os.environ.get('FORGE_WINDOWS_INSTALL_TEST_BIN'):
        commands.append(['cmd.exe','/d','/c',str(Path(os.environ['FORGE_WINDOWS_INSTALL_TEST_BIN'])/'agent-command.cmd'),'--project',str(project)])
    from forge.store import Store
    for i,argv in enumerate(commands):
        s=Session(argv,str(project),'real-tui',rows=50,cols=160,env=env)
        try:
            wait(s,lambda:'AGENT / FORGE' in '\n'.join(s.screen.display),30)
            marker=f'WINDOWS_REAL_TUI_{i}';s.write('/remember fact '+marker+'\r')
            store=Store(project)
            try:wait(s,lambda:bool(store.memories(marker)),20)
            finally:store.close()
            s.write('/quit\r');wait(s,lambda:s.status=='exited',20);assert s.exit_code==0
        finally:s.stop()
