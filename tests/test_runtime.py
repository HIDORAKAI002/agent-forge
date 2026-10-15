import json
import os
from pathlib import Path
import sys
import time
import pytest
from forge.runtime import Runtime
from forge.profiles import profiles, recommend
from forge.terminal import ForgeScreen
import pyte


def wait(runtime, predicate):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        runtime.poll()
        if predicate(): return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for real local PTY fixture")


def test_real_pty_input_and_controlling_terminal(project):
    runtime = Runtime(project)
    try:
        session = runtime.launch("shell")
        session.write("printf 'FORGE_PTY_OK\\n'\n")
        wait(runtime, lambda: "FORGE_PTY_OK" in "\n".join(session.screen.display))
        session.write("test -t 0 && test -r /dev/tty && printf 'CONTROLLING_TTY_OK\\n'\n")
        wait(runtime, lambda: "CONTROLLING_TTY_OK" in "\n".join(session.screen.display))
        session.resize(30, 100)
        assert session.screen.columns == 100
        session.write("exit\n")
        wait(runtime, lambda: session.status == "exited")
        assert session.exit_code == 0
        with pytest.raises(ValueError): session.write("oops")
    finally: runtime.close()


def test_parallel_fixture_agents_use_worktrees_and_shared_handoffs(project, tmp_path_factory):
    bin_dir = tmp_path_factory.mktemp("agents")
    for name in ("fixture-a", "fixture-b"):
        script = bin_dir / name
        script.write_text(f"#!{sys.executable}\nimport os\nfrom pathlib import Path\nfrom forge.store import Store\nPath('{name}.txt').write_text('fixture only')\ns=Store(os.environ['FORGE_PROJECT'])\ns.remember('Finished {name}', 'handoff', '{name}')\ns.close()\nprint('FIXTURE_DONE')\n")
        script.chmod(0o755)
    config = project / ".agent-forge"; config.mkdir()
    (config / "profiles.json").write_text(json.dumps([dict(id=name, argv=[str(bin_dir / name)], task_argv=[str(bin_dir / name), "{prompt}"], tier="local") for name in ("fixture-a", "fixture-b")]))
    runtime = Runtime(project)
    try:
        a = runtime.store.create_task("A", "Bounded fixture A", "fixture-a")
        b = runtime.store.create_task("B", "Bounded fixture B", "fixture-b")
        runtime.run_task(a["id"]); runtime.run_task(b["id"])
        wait(runtime, lambda: all(t["status"] == "needs-review" for t in runtime.store.tasks()))
        assert len(runtime.store.memories()) == 2
        assert all(not m["verified"] for m in runtime.store.memories())
        for t in runtime.store.tasks():
            assert (Path(t["worktree"]) / f"{t['engine']}.txt").exists()
            assert not (project / f"{t['engine']}.txt").exists()
        runtime.approve(a["id"])
        assert runtime.store.task(a["id"])["status"] == "done"
        with pytest.raises(ValueError): runtime.run_task(a["id"])
    finally: runtime.close()


def test_same_project_single_owner(project):
    runtime = Runtime(project)
    try:
        with pytest.raises(ValueError, match="already owns"): Runtime(project)
    finally: runtime.close()


def test_dirty_repo_blocks_worktree_dispatch(project):
    config = project / ".agent-forge"; config.mkdir()
    (config / "profiles.json").write_text(json.dumps([dict(id="fixture", argv=[sys.executable], task_argv=[sys.executable, "-c", "print('ok')"])]))
    runtime = Runtime(project)
    try:
        task = runtime.store.create_task("T", "P", "fixture")
        (project / "README.md").write_text("dirty")
        with pytest.raises(ValueError, match="Commit or stash"): runtime.run_task(task["id"])
        assert not runtime.sessions
    finally: runtime.close()


def test_recovery_does_not_rerun_interrupted_task(project):
    runtime = Runtime(project)
    task = runtime.store.create_task("T", "P", "claude")
    runtime.store.update_task(task["id"], status="running")
    # Simulate a process crash: release resources without graceful Runtime.close.
    runtime.store.close(); runtime.lock_file.close()
    resumed = Runtime(project)
    try:
        assert resumed.store.task(task["id"])["status"] == "failed"
        assert not resumed.sessions
    finally: resumed.close()


def test_alternate_screen_preserves_primary():
    screen = ForgeScreen(40, 8); stream = pyte.Stream(screen)
    stream.feed("PRIMARY")
    stream.feed("\x1b[?1049h\x1b[2J\x1b[HALTERNATE")
    assert "ALTERNATE" in screen.display[0]
    stream.feed("\x1b[?1049l")
    assert "PRIMARY" in screen.display[0]


def test_configured_cost_tier_policy_is_only_recommendation(project):
    config = project / ".agent-forge"; config.mkdir()
    (config / "profiles.json").write_text(json.dumps([dict(id="local-worker", argv=[sys.executable], task_argv=[sys.executable, "-c", "{prompt}"], tier="local"), dict(id="strong-worker", argv=[sys.executable], task_argv=[sys.executable, "-c", "{prompt}"], tier="strong")]))
    available = list(profiles(project).values())
    assert recommend(available, "routine") == "local-worker"
    assert recommend(available, "high") == "strong-worker"


def test_stop_terminates_a_real_process_group(project):
    runtime = Runtime(project)
    try:
        session = runtime.launch("shell")
        session.write("sleep 30 & wait\n")
        time.sleep(0.1)
        session.stop()
        wait(runtime, lambda: session.status == "exited")
        assert session.cancelled
    finally: runtime.close()


@pytest.mark.parametrize('worker_exit,expected',[(0,'needs-review'),(7,'failed')])
def test_multifile_verification_preserves_original_and_dependency_gate(project,worker_exit,expected):
    """Actual process/file/test effects, not an AI-quality or cloud assertion."""
    config=project/'.agent-forge';config.mkdir()
    code='''from pathlib import Path
import subprocess,sys
Path('arithmetic.py').write_text('def add(a,b): return a+b\\n')
Path('test_arithmetic.py').write_text('from arithmetic import add\\nassert add(2,3)==5\\n')
Path('CHANGELOG.md').write_text('Added tested addition\\n')
checked=subprocess.run([sys.executable,'test_arithmetic.py'])
assert checked.returncode==0
print('MULTIFILE_TESTS_PASSED',flush=True)
'''+f'raise SystemExit({worker_exit})\n'
    (config/'profiles.json').write_text(json.dumps([{'id':'fixture-multifile','argv':[sys.executable],
        'task_argv':[sys.executable,'-I','-c',code],'tier':'local'}]))
    runtime=Runtime(project)
    try:
        task=runtime.store.create_task('Multi-file fixture','Write and verify three fixture files','fixture-multifile')
        dependent=runtime.store.create_task('Dependent','Must not run before review','fixture-multifile',dependencies=[task['id']])
        session=runtime.run_task(task['id'])
        wait(runtime,lambda:runtime.store.task(task['id'])['status']==expected)
        assert session.exit_code==worker_exit
        assert 'MULTIFILE_TESTS_PASSED' in '\n'.join(session.screen.display)
        saved=runtime.store.task(task['id']);tree=Path(saved['worktree'])
        for name in ('arithmetic.py','test_arithmetic.py','CHANGELOG.md'):
            assert (tree/name).is_file() and not (project/name).exists()
        with pytest.raises(ValueError,match='human approval'):runtime.run_task(dependent['id'])
        if worker_exit:
            with pytest.raises(ValueError,match='awaiting review'):runtime.approve(task['id'])
    finally:runtime.close()
    reopened=Runtime(project)
    try:
        assert reopened.store.task(task['id'])['status']==expected
        assert not reopened.sessions
        assert (tree/'CHANGELOG.md').is_file()
    finally:reopened.close()


def test_cancelled_multifile_task_survives_restart_without_rerun(project):
    config=project/'.agent-forge';config.mkdir()
    code="from pathlib import Path; import time; Path('partial-a.txt').write_text('preserve A'); Path('partial-b.txt').write_text('preserve B'); print('CANCEL_READY',flush=True); time.sleep(60); Path('must-not-run.txt').write_text('bad')"
    (config/'profiles.json').write_text(json.dumps([{'id':'fixture-cancel','argv':[sys.executable],
        'task_argv':[sys.executable,'-I','-c',code],'tier':'local'}]))
    runtime=Runtime(project)
    try:
        task=runtime.store.create_task('Cancellation fixture','Preserve partial edits','fixture-cancel')
        session=runtime.run_task(task['id'])
        wait(runtime,lambda:'CANCEL_READY' in '\n'.join(session.screen.display))
        tree=Path(runtime.store.task(task['id'])['worktree'])
        session.stop();wait(runtime,lambda:runtime.store.task(task['id'])['status']=='cancelled')
        assert (tree/'partial-a.txt').read_text()=='preserve A'
        assert (tree/'partial-b.txt').read_text()=='preserve B'
        assert not (tree/'must-not-run.txt').exists()
    finally:runtime.close()
    reopened=Runtime(project)
    try:
        assert reopened.store.task(task['id'])['status']=='cancelled' and not reopened.sessions
        with pytest.raises(ValueError,match='new task to retry'):reopened.run_task(task['id'])
        assert not (tree/'must-not-run.txt').exists()
        assert not (project/'partial-a.txt').exists() and not (project/'partial-b.txt').exists()
    finally:reopened.close()
