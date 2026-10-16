"""Exercise the actual forge command inside an outer PTY, not just Pilot events."""
import os
import sys
import time
import shlex
from forge.terminal import Session
from forge.store import Store


def wait(session, predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        session.drain()
        if predicate(): return
        time.sleep(0.025)
    raise AssertionError(f"Real CLI/PTY interaction timed out: status={session.status} exit={session.exit_code} screen={chr(10).join(session.screen.display)[-1400:]!r}")


def test_actual_forge_command_receives_terminal_bytes(project):
    outer = Session([sys.executable, "-I", "-m", "forge", "--project", str(project)], str(project), "forge", rows=50, cols=160)
    try:
        wait(outer, lambda: "AGENT / FORGE" in "\n".join(outer.screen.display))
        outer.write("/remember fact REAL_TUI_BYTE_INPUT\r")
        # Seeing typed characters is not proof that Input.Submitted completed.
        verification = Store(project)
        try:wait(outer, lambda: bool(verification.memories("REAL_TUI_BYTE_INPUT")))
        finally:verification.close()
        outer.write("/launch shell\r")
        wait(outer, lambda: "Embedded PTY / native input" in "\n".join(outer.screen.display))
        marker=project/'real-nested-shell-result.txt'
        command = (f'echo RAW_NESTED_SHELL_OK & echo executed>"{marker}"' if os.name == 'nt' else
                   "printf 'RAW_NESTED_SHELL_OK\\n'; printf 'executed' > "+shlex.quote(str(marker)))
        outer.write(command + "\r")
        wait(outer, lambda: marker.exists() and marker.read_text().strip() == 'executed' and "RAW_NESTED_SHELL_OK" in "\n".join(outer.screen.display))
        time.sleep(0.3)
        ctrl_space = '\x1b[32;5u' if os.name == 'nt' else '\x00'
        outer.write(ctrl_space)  # actual Ctrl+Space byte / sequence
        time.sleep(0.5)
        outer.write("/remember fact RAW_RETURN_TO_COMPOSER\r")
        verification = Store(project)
        try:
            wait(outer, lambda: bool(verification.memories("RAW_RETURN_TO_COMPOSER")))
        finally:
            verification.close()
        time.sleep(0.3)
        outer.write(ctrl_space)
        time.sleep(0.5)
        outer.write("/quit\r")
        wait(outer, lambda: "CLOSE WORKSPACE" in "\n".join(outer.screen.display))
        time.sleep(0.15)
        outer.write("y")  # Explicit, priority modal confirmation key.
        wait(outer, lambda: outer.status == "exited")
        assert outer.exit_code == 0
    finally:
        outer.stop()
        try: wait(outer, lambda: outer.status == "exited")
        except AssertionError: pass
