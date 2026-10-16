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


def process_liveness(pid: int):
    try:
        proc = psutil.Process(pid)
        return proc, proc.create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None, None


def is_same_process_alive(proc, create_time: float) -> bool:
    if proc is None:
        return False
    try:
        return proc.is_running() and proc.create_time() == create_time
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


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
    commands=[[sys.executable,'-I','-m','forge','--project',str(project)]]
    if os.environ.get('FORGE_WINDOWS_INSTALL_TEST_BIN'):
        commands.append(['cmd.exe','/d','/c',str(Path(os.environ['FORGE_WINDOWS_INSTALL_TEST_BIN'])/'agent-command.cmd'),'--project',str(project)])
    malicious=project/'forge';malicious.mkdir();(malicious/'__init__.py').write_text('raise RuntimeError("PROJECT_IMPORT_INJECTION")')
    (project/'sitecustomize.py').write_text('raise RuntimeError("PROJECT_STARTUP_INJECTION")')
    env['PYTHONPATH']=str(project)
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


@pytest.mark.parametrize("folder_name", [
    "project_ascii",
    "project with spaces",
    "project_測試_unicode_éà",
])
def test_native_conpty_paths(tmp_path, folder_name):
    project = tmp_path / folder_name
    project.mkdir(parents=True)
    marker = project / "marker.txt"
    code = f'import os, pathlib; pathlib.Path({str(marker)!r}).write_text(os.getcwd(), encoding="utf-8"); print("PATH_OK", flush=True)'
    s = Session([sys.executable, "-c", code], str(project), "test-path")
    try:
        wait(s, lambda: "PATH_OK" in "\n".join(s.screen.display))
        wait(s, lambda: s.status == "exited")
        assert s.exit_code == 0
        assert marker.exists()
        assert Path(marker.read_text(encoding="utf-8")).resolve() == project.resolve()
    finally:
        s.stop()


def test_native_conpty_resize_transitions(tmp_path):
    code = (
        'import os, sys\n'
        'print("READY", flush=True)\n'
        'while True:\n'
        '    line = sys.stdin.readline()\n'
        '    if not line or "QUIT" in line: break\n'
        '    size = os.get_terminal_size()\n'
        '    print(f"SIZE={size.lines},{size.columns}", flush=True)\n'
    )
    s = Session([sys.executable, "-c", code], str(tmp_path), "test-resize", rows=24, cols=80)
    try:
        wait(s, lambda: "READY" in "\n".join(s.screen.display))
        s.resize(36, 120)
        time.sleep(0.3)
        s.write("CHECK\r")
        wait(s, lambda: "SIZE=36,120" in "\n".join(s.screen.display))
        s.resize(20, 70)
        time.sleep(0.3)
        s.write("CHECK\r")
        wait(s, lambda: "SIZE=20,70" in "\n".join(s.screen.display))
        s.resize(24, 80)
        time.sleep(0.3)
        s.write("CHECK\r")
        wait(s, lambda: "SIZE=24,80" in "\n".join(s.screen.display))
        s.write("QUIT\r")
        wait(s, lambda: s.status == "exited")
        assert s.exit_code == 0
    finally:
        s.stop()


def test_native_conpty_unicode_roundtrip(tmp_path):
    marker = tmp_path / "unicode_echo.txt"
    code = (
        'import sys, pathlib\n'
        'sys.stdin.reconfigure(encoding="utf-8")\n'
        'sys.stdout.reconfigure(encoding="utf-8")\n'
        'print("READY_UNICODE", flush=True)\n'
        'line = sys.stdin.readline().strip()\n'
        f'pathlib.Path({str(marker)!r}).write_text(line, encoding="utf-8")\n'
        'print("ECHO=" + line, flush=True)\n'
    )
    s = Session([sys.executable, "-X", "utf8", "-c", code], str(tmp_path), "test-unicode")
    sample_text = "Accented: élève / Cyrillic: Привет / CJK: 漢字 測試"
    full_unicode = "Accented: élève / Cyrillic: Привет / CJK: 漢字 測試 / Indic: हिन्दी"
    try:
        wait(s, lambda: "READY_UNICODE" in "\n".join(s.screen.display))
        s.write(full_unicode + "\r\n")
        wait(s, lambda: marker.exists() and marker.read_text(encoding="utf-8") == full_unicode)
        wait(s, lambda: sample_text in "\n".join(s.screen.display))
        wait(s, lambda: s.status == "exited")
        assert s.exit_code == 0
    finally:
        s.stop()


def test_native_conpty_ctrl_c_interrupt(tmp_path):
    code = (
        'import sys, time\n'
        'print("STARTING_LOOP", flush=True)\n'
        'try:\n'
        '    while True: time.sleep(0.1)\n'
        'except KeyboardInterrupt:\n'
        '    print("INTERRUPT_CAUGHT", flush=True)\n'
        'line = sys.stdin.readline()\n'
        'print("AFTER_INTERRUPT=" + line.strip(), flush=True)\n'
    )
    s = Session([sys.executable, "-c", code], str(tmp_path), "test-ctrl-c")
    try:
        wait(s, lambda: "STARTING_LOOP" in "\n".join(s.screen.display))
        s.write("\x03")
        wait(s, lambda: "INTERRUPT_CAUGHT" in "\n".join(s.screen.display))
        s.write("RESUMED\r\n")
        wait(s, lambda: "AFTER_INTERRUPT=RESUMED" in "\n".join(s.screen.display))
        wait(s, lambda: s.status == "exited")
        assert s.exit_code == 0
    finally:
        s.stop()


def test_native_conpty_exit_code_propagation(tmp_path):
    s0 = Session([sys.executable, "-c", "import sys; sys.exit(0)"], str(tmp_path), "exit-zero")
    try:
        wait(s0, lambda: s0.status == "exited")
        assert s0.exit_code == 0
    finally:
        s0.stop()

    s42 = Session([sys.executable, "-c", "import sys; sys.exit(42)"], str(tmp_path), "exit-nonzero")
    try:
        wait(s42, lambda: s42.status == "exited")
        assert s42.exit_code == 42
    finally:
        s42.stop()


def test_native_job_cleanup_verified_with_create_time(tmp_path):
    pidfile = tmp_path / "descendant.pid"
    code = (
        'import subprocess, sys, time, pathlib\n'
        'p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
        f'pathlib.Path({str(pidfile)!r}).write_text(str(p.pid))\n'
        'print("DESCENDANT_SPAWNED", flush=True)\n'
        'time.sleep(60)\n'
    )
    s = Session([sys.executable, "-c", code], str(tmp_path), "cleanup-verified")
    try:
        wait(s, lambda: pidfile.exists())
        pid = int(pidfile.read_text().strip())
        proc, create_time = process_liveness(pid)
        assert proc is not None and is_same_process_alive(proc, create_time)
        s.stop()
        wait(s, lambda: s.status == "exited")
        end = time.monotonic() + 5
        while is_same_process_alive(proc, create_time) and time.monotonic() < end:
            time.sleep(0.05)
        assert not is_same_process_alive(proc, create_time)
    finally:
        s.stop()


def test_native_job_cleanup_on_broker_exit(tmp_path):
    pidfile = tmp_path / "orphan.pid"
    code = (
        'import subprocess, sys, time, pathlib\n'
        'p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
        f'pathlib.Path({str(pidfile)!r}).write_text(str(p.pid))\n'
        'print("ORPHAN_READY", flush=True)\n'
        'sys.exit(0)\n'
    )
    s = Session([sys.executable, "-c", code], str(tmp_path), "orphan-test")
    try:
        wait(s, lambda: pidfile.exists())
        pid = int(pidfile.read_text().strip())
        proc, create_time = process_liveness(pid)
        assert proc is not None
        wait(s, lambda: s.status == "exited")
        end = time.monotonic() + 5
        while is_same_process_alive(proc, create_time) and time.monotonic() < end:
            time.sleep(0.05)
        assert not is_same_process_alive(proc, create_time)
    finally:
        s.stop()


def test_powershell_installer_refuses_invalid_command_name(tmp_path):
    ps1 = Path(__file__).resolve().parents[1] / "scripts/install.ps1"
    run_root = tmp_path / "install_run"
    run_root.mkdir()
    env = dict(
        os.environ,
        FORGE_INSTALL_ROOT=str(run_root / "install"),
        FORGE_BIN_ROOT=str(run_root / "bin"),
        FORGE_CONFIGURE_PATH="0",
        FORGE_COMMAND="con",
    )
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                         capture_output=True, text=True, env=env)
    assert res.returncode != 0
    assert "Invalid launch command name" in (res.stderr + res.stdout)


def test_powershell_installer_refuses_unmanaged_collision(tmp_path):
    ps1 = Path(__file__).resolve().parents[1] / "scripts/install.ps1"
    run_root = tmp_path / "install_run"
    bin_dir = run_root / "bin"
    bin_dir.mkdir(parents=True)
    unmanaged = bin_dir / "agent-command.cmd"
    unmanaged.write_text("@echo off\necho unmanaged\n")
    env = dict(
        os.environ,
        FORGE_INSTALL_ROOT=str(run_root / "install"),
        FORGE_BIN_ROOT=str(bin_dir),
        FORGE_CONFIGURE_PATH="0",
        FORGE_COMMAND="agent-command",
    )
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                         capture_output=True, text=True, env=env)
    assert res.returncode != 0
    assert "Refusing to overwrite unrelated command" in (res.stderr + res.stdout)


def test_powershell_installer_disposable_run(tmp_path):
    ps1 = Path(__file__).resolve().parents[1] / "scripts/install.ps1"
    run_root = tmp_path / "install_with spaces"
    run_root.mkdir()
    install_dir = run_root / "app install"
    bin_dir = run_root / "launcher bin"
    env = dict(
        os.environ,
        FORGE_INSTALL_ROOT=str(install_dir),
        FORGE_BIN_ROOT=str(bin_dir),
        FORGE_CONFIGURE_PATH="0",
        FORGE_COMMAND="forge-test-cmd",
        FORGE_PYTHON=sys.executable,
    )
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                         capture_output=True, text=True, env=env, timeout=240)
    assert res.returncode == 0
    launcher = bin_dir / "forge-test-cmd.cmd"
    assert launcher.exists()
    content = launcher.read_text(encoding="utf-8")
    assert content.startswith("REM Agent Forge managed launcher")
    # Managed rerun must succeed
    res_rerun = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                               capture_output=True, text=True, env=env, timeout=240)
    assert res_rerun.returncode == 0

