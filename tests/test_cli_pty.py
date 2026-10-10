"""Exercise the actual forge command inside an outer PTY, not just Pilot events."""
import sys
import time
from forge.terminal import Session
from forge.store import Store


def wait(session, predicate):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        session.drain()
        if predicate(): return
        time.sleep(0.025)
    raise AssertionError("Real CLI/PTY interaction timed out")


def test_actual_forge_command_receives_terminal_bytes(project):
    outer = Session([sys.executable, "-m", "forge", "--project", str(project)], str(project), "forge", rows=50, cols=160)
    try:
        wait(outer, lambda: "AGENT / FORGE" in "\n".join(outer.screen.display))
        outer.write("/remember fact REAL_TUI_BYTE_INPUT\r")
        wait(outer, lambda: "REAL_TUI_BYTE_INPUT" in "\n".join(outer.screen.display))
        outer.write("/launch shell\r")
        wait(outer, lambda: "Embedded PTY / native input" in "\n".join(outer.screen.display))
        outer.write("printf 'RAW_NESTED_SHELL_OK\\n'\r")
        wait(outer, lambda: "RAW_NESTED_SHELL_OK" in "\n".join(outer.screen.display))
        time.sleep(0.15)
        outer.write("\x00")  # actual Ctrl+Space byte, not a synthetic Pilot key
        time.sleep(0.15)
        outer.write("/remember fact RAW_RETURN_TO_COMPOSER\r")
        verification = Store(project)
        try:
            wait(outer, lambda: bool(verification.memories("RAW_RETURN_TO_COMPOSER")))
        finally:
            verification.close()
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
