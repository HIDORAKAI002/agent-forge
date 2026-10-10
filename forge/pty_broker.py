"""Single-threaded PTY broker: never fork a Python child from the threaded TUI.

stdin: JSON control lines. stdout: raw PTY bytes. stderr: one startup handshake.
Closing the control pipe requests cleanup, including known descendant processes.
"""
from __future__ import annotations
import json
import os
import selectors
import signal
import sys
import time
import psutil
from ptyprocess import PtyProcess


def main():
    child = None
    known: dict[tuple[int, float], psutil.Process] = {}
    stopping = None
    def scan():
        if child is None:
            return
        try:
            parent = psutil.Process(child.pid)
            for proc in [parent, *parent.children(recursive=True)]:
                known[(proc.pid, proc.create_time())] = proc
        except psutil.Error:
            pass
    def signal_known(force=False):
        scan()
        for proc in reversed(list(known.values())):
            try:
                if proc.is_running():
                    proc.kill() if force else proc.terminate()
            except psutil.Error:
                pass
    def stop(*_):
        nonlocal stopping
        if stopping is None:
            stopping = time.monotonic()
            signal_known()
    try:
        config = json.loads(sys.stdin.buffer.readline())
        child = PtyProcess.spawn(config["argv"], cwd=config["cwd"], env=config["env"], dimensions=(config["rows"], config["cols"]))
        print(json.dumps({"ready": True, "pid": child.pid}), file=sys.stderr, flush=True)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        selector = selectors.DefaultSelector()
        selector.register(sys.stdin.fileno(), selectors.EVENT_READ, "control")
        selector.register(child.fd, selectors.EVENT_READ, "pty")
        control = b""
        while True:
            scan()
            if stopping is not None and time.monotonic() - stopping > 1.2:
                signal_known(force=True)
            for key, _ in selector.select(0.08):
                if key.data == "control":
                    chunk = os.read(sys.stdin.fileno(), 65536)
                    if not chunk:
                        selector.unregister(sys.stdin.fileno())
                        stop()
                        continue
                    control += chunk
                    while b"\n" in control:
                        line, control = control.split(b"\n", 1)
                        message = json.loads(line)
                        if message["kind"] == "input" and stopping is None:
                            child.write(message["text"].encode("utf-8"))
                        elif message["kind"] == "resize" and stopping is None:
                            child.setwinsize(message["rows"], message["cols"])
                        elif message["kind"] == "stop":
                            stop()
                else:
                    try:
                        data = os.read(child.fd, 16384)
                    except OSError:
                        data = b""
                    if data:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                    else:
                        try: selector.unregister(child.fd)
                        except KeyError: pass
            if not child.isalive():
                # Drain bytes that arrived just before process exit.
                try:
                    os.set_blocking(child.fd, False)
                    while data := os.read(child.fd, 16384):
                        sys.stdout.buffer.write(data)
                except OSError:
                    pass
                sys.stdout.buffer.flush()
                child.wait()
                code = child.exitstatus if child.exitstatus is not None else 128 + (child.signalstatus or 0)
                return min(code, 255)
    except BaseException as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr, flush=True)
        return 125
    finally:
        signal_known(force=True)
        if child is not None:
            try: child.close(force=True)
            except OSError: pass


if __name__ == "__main__":
    raise SystemExit(main())
