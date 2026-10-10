"""Canonical, project-local SQLite state shared by the TUI, CLI and MCP clients."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sqlite3
import threading
from datetime import datetime, timezone
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate(value: str, name: str, maximum: int = 16000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise ValueError(f"Invalid {name}")
    return value.strip()


def managed(root: Path, name: str) -> Path:
    target = root / name
    if target.is_symlink():
        raise ValueError(f"Refusing managed symbolic link: {name}")
    return target


class Store:
    def __init__(self, project: str | Path):
        self.project = Path(project).expanduser().resolve(strict=True)
        if not self.project.is_dir():
            raise ValueError("Project must be a directory")
        self.directory = managed(self.project, ".agent-forge")
        self.directory.mkdir(mode=0o700, exist_ok=True)
        for name in ("state.sqlite", "state.sqlite-wal", "state.sqlite-shm", "memory.md", "workspace.lock"):
            managed(self.directory, name)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.directory / "state.sqlite", timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, kind TEXT NOT NULL, text TEXT NOT NULL, author TEXT NOT NULL, verified INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL, read_at TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
        """)
        self._projection()

    def _event(self, kind: str, payload: dict):
        self.db.execute("INSERT INTO events(created_at,kind,payload) VALUES(?,?,?)", (now(), kind, json.dumps(payload)))

    def memories(self, query: str = "", limit: int = 100) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT * FROM memories ORDER BY created_at DESC, rowid DESC").fetchall()
        result = [dict(row) | {"verified": bool(row["verified"])} for row in rows]
        return [row for row in result if query.casefold() in f"{row['text']} {row['kind']} {row['author']}".casefold()][:max(1, min(limit, 500))]

    def _projection(self):
        # Always serialize generated snapshots with database writers.
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                content = "# Shared project memory\n\nGenerated from SQLite. Read freely; contribute using forge memory add or MCP. Do not edit this projection.\n\n"
                for item in self.memories(limit=500):
                    content += f"## {item['kind']} · {'verified' if item['verified'] else 'unverified'}\n\n{item['text']}\n\n{item['author']} · {item['created_at']} · {item['id']}\n\n"
                target = managed(self.directory, "memory.md")
                temporary = self.directory / f".memory-{uuid4()}.tmp"
                with temporary.open("x", encoding="utf-8") as output:
                    if os.name != "nt":
                        os.chmod(temporary, 0o600)
                    output.write(content)
                os.replace(temporary, target)
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise

    def remember(self, text: str, kind: str = "handoff", author: str = "agent", verified: bool = False) -> dict:
        if kind not in {"fact", "decision", "handoff"}:
            raise ValueError("Memory kind: fact, decision or handoff")
        item = dict(id=str(uuid4()), kind=kind, text=validate(text, "memory"), author=validate(author, "author", 120), verified=bool(verified), created_at=now())
        with self.lock, self.db:
            self.db.execute("INSERT INTO memories VALUES(?,?,?,?,?,?)", (item["id"], kind, item["text"], item["author"], int(item["verified"]), item["created_at"]))
            self._event("memory.added", item)
        self._projection()
        return item

    def tasks(self) -> list[dict]:
        with self.lock:
            return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM tasks ORDER BY rowid DESC")]

    def task(self, identifier: str) -> dict:
        matches = [task for task in self.tasks() if task["id"].startswith(identifier)]
        if len(matches) != 1:
            raise ValueError("Unknown or ambiguous task ID; use its full ID or a unique prefix")
        return matches[0]

    def create_task(self, title: str, prompt: str, engine: str, risk: str = "routine", dependencies: list[str] | None = None) -> dict:
        if risk not in {"routine", "high"}:
            raise ValueError("Risk must be routine or high")
        dependencies = dependencies or []
        if len(dependencies) > 30:
            raise ValueError("Too many task dependencies")
        resolved = list(dict.fromkeys(self.task(dep)["id"] for dep in dependencies))
        task = dict(id=str(uuid4()), title=validate(title, "title", 180), prompt=validate(prompt, "prompt"), engine=validate(engine, "engine", 80), risk=risk, dependencies=resolved, status="queued", created_at=now(), worktree=None, session_id=None, note="")
        with self.lock, self.db:
            self.db.execute("INSERT INTO tasks VALUES(?,?)", (task["id"], json.dumps(task)))
            self._event("task.created", task)
        return task

    def update_task(self, identifier: str, **patch) -> dict:
        with self.lock, self.db:
            task = self.task(identifier)
            if "id" in patch:
                raise ValueError("Task identity is immutable")
            task.update(patch)
            self.db.execute("UPDATE tasks SET payload=? WHERE id=?", (json.dumps(task), task["id"]))
            self._event("task.updated", dict(id=task["id"], patch=patch))
            return task

    def ready(self, identifier: str) -> dict:
        task = self.task(identifier)
        if task["status"] != "queued":
            raise ValueError("Only queued tasks can run. Create a new task to retry; old work is preserved.")
        if any(self.task(dep)["status"] != "done" for dep in task["dependencies"]):
            raise ValueError("Prerequisite tasks need human approval first")
        return task

    def send(self, sender: str, recipient: str, text: str) -> dict:
        item = dict(id=str(uuid4()), sender=validate(sender, "sender", 120), recipient=validate(recipient, "recipient", 120), text=validate(text, "message"), created_at=now(), read_at=None)
        with self.lock, self.db:
            self.db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", tuple(item.values()))
            self._event("mail.sent", item)
        return item

    def inbox(self, recipient: str) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.db.execute("SELECT * FROM messages WHERE recipient=? AND read_at IS NULL ORDER BY rowid LIMIT 100", (validate(recipient, "recipient", 120),))]

    def acknowledge(self, identifier: str, recipient: str):
        with self.lock, self.db:
            result = self.db.execute("UPDATE messages SET read_at=? WHERE id=? AND recipient=? AND read_at IS NULL", (now(), identifier, recipient))
            if not result.rowcount:
                raise ValueError("Unknown, already acknowledged or differently addressed message")
            self._event("mail.ack", dict(id=identifier, recipient=recipient))

    def events(self, limit: int = 15) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]

    def close(self):
        self.db.close()
