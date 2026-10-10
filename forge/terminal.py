"""Real POSIX PTYs, incrementally decoded output and a VT terminal surface."""
from __future__ import annotations
import codecs
from copy import deepcopy
import os
import queue
import json
import subprocess
import sys
import threading
from uuid import uuid4
import pyte


class ForgeScreen(pyte.HistoryScreen):
    """Keep the primary screen intact while programs use an alternate screen."""
    def __init__(self, columns: int, lines: int):
        self.primary = None
        super().__init__(columns, lines, history=1000)

    def set_mode(self, *modes, **kwargs):
        if kwargs.get("private") and any(mode in (47, 1047, 1049) for mode in modes):
            if self.primary is None:
                self.primary = deepcopy((self.buffer, self.cursor, self.margins, self.history))
                self.erase_in_display(2)
                self.cursor_position(1, 1)
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs):
        if kwargs.get("private") and any(mode in (47, 1047, 1049) for mode in modes) and self.primary is not None:
            self.buffer, self.cursor, self.margins, self.history = self.primary
            self.primary = None
        super().reset_mode(*modes, **kwargs)


class Session:
    def __init__(self, argv: list[str], cwd: str, engine: str, *, task_id: str | None = None, rows: int = 24, cols: int = 90, env: dict | None = None):
        if os.name == "nt":
            raise ValueError("Native Windows PTY backend is not implemented yet. Run Agent Forge in WSL.")
        self.id = str(uuid4())
        self.engine, self.cwd, self.task_id = engine, cwd, task_id
        self.status, self.exit_code, self.cancelled = "running", None, False
        self.events: queue.Queue[tuple[str, str | int]] = queue.Queue(maxsize=2000)
        self.screen = ForgeScreen(cols, rows)
        self.stream = pyte.Stream(self.screen)
        self.process = subprocess.Popen([sys.executable, "-m", "forge.pty_broker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self._control_lock = threading.Lock()
        self._control(dict(argv=argv, cwd=cwd, env=env or dict(os.environ), rows=rows, cols=cols))
        handshake = json.loads(self.process.stderr.readline())
        if not handshake.get("ready"):
            self.process.wait(timeout=5)
            raise ValueError(handshake.get("error", "PTY broker failed"))
        self.worker = threading.Thread(target=self._read, daemon=True)
        self.worker.start()

    def _control(self, message: dict):
        with self._control_lock:
            self.process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            self.process.stdin.flush()

    def _read(self):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        try:
            while True:
                data = self.process.stdout.read(4096)
                if not data:
                    break
                decoded = decoder.decode(data)
                if decoded:
                    self.events.put(("data", decoded))
        except (EOFError, OSError):
            pass
        finally:
            tail = decoder.decode(b"", final=True)
            if tail:
                self.events.put(("data", tail))
            code = self.process.wait()
            self.events.put(("exit", code))

    def write(self, text: str):
        if self.status != "running" or self.process.poll() is not None:
            raise ValueError("Session has exited")
        if len(text) > 65536:
            raise ValueError("Input chunk exceeds 64 KiB")
        self._control(dict(kind="input", text=text))

    def resize(self, rows: int, cols: int):
        rows, cols = max(2, min(rows, 200)), max(2, min(cols, 500))
        if self.screen.lines == rows and self.screen.columns == cols:
            return
        self.screen.resize(lines=rows, columns=cols)
        if self.status == "running" and self.process.poll() is None:
            try:
                self._control(dict(kind="resize", rows=rows, cols=cols))
            except (BrokenPipeError, OSError):
                pass

    def drain(self) -> list[tuple[str, str | int]]:
        result = []
        for _ in range(200):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            result.append((kind, value))
            if kind == "data":
                self.stream.feed(str(value))
            else:
                self.status, self.exit_code = "exited", int(value)
        return result

    def stop(self):
        if self.status == "running":
            self.cancelled = True
            try:
                self._control(dict(kind="stop"))
            except (BrokenPipeError, OSError):
                pass
