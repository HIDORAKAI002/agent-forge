import concurrent.futures
import pytest
from forge.store import Store


def test_memory_provenance_and_reopen(project):
    store = Store(project)
    store.remember("Run tests", "decision", "user", True)
    store.remember("Changed parser", "handoff", "codex")
    store.close()
    reopened = Store(project)
    assert len(reopened.memories()) == 2
    assert reopened.memories()[0]["verified"] is False
    assert "Run tests" in (project / ".agent-forge/memory.md").read_text()
    reopened.close()


def test_memory_validation_and_search(project):
    store = Store(project)
    with pytest.raises(ValueError): store.remember("", "fact")
    with pytest.raises(ValueError): store.remember("data", "wrong")
    store.remember("Parser invariant", "fact")
    assert len(store.memories("parser")) == 1
    assert len(store.memories("absent")) == 0
    store.close()


def test_dependencies_and_no_implicit_approval(project):
    store = Store(project)
    a = store.create_task("Plan", "Plan it", "claude")
    b = store.create_task("Build", "Build it", "codex", dependencies=[a["id"][:8]])
    with pytest.raises(ValueError, match="approval"): store.ready(b["id"])
    store.update_task(a["id"], status="needs-review")
    with pytest.raises(ValueError): store.ready(b["id"])
    store.update_task(a["id"], status="done")
    assert store.ready(b["id"])["id"] == b["id"]
    with pytest.raises(ValueError): store.create_task("Bad", "Bad", "claude", dependencies=["unknown"])
    store.close()


def test_mail_ack_and_identity_boundary(project):
    store = Store(project)
    message = store.send("claude", "codex", "Check the interface")
    assert len(store.inbox("codex")) == 1
    assert not store.inbox("other")
    with pytest.raises(ValueError): store.acknowledge(message["id"], "other")
    store.acknowledge(message["id"], "codex")
    assert not store.inbox("codex")
    with pytest.raises(ValueError): store.acknowledge(message["id"], "codex")
    store.close()


def test_independent_clients_do_not_reset_running_tasks(project):
    a, b = Store(project), Store(project)
    task = a.create_task("T", "P", "claude")
    a.update_task(task["id"], status="running")
    b.remember("Shared handoff")
    assert b.task(task["id"])["status"] == "running"
    assert len(a.memories()) == 1
    a.close(); b.close()


def test_concurrent_writers_keep_all_memories(project):
    a, b = Store(project), Store(project)
    def write(index):
        (a if index % 2 else b).remember(f"fact-{index}", "fact", "fixture")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write, range(20)))
    assert len(a.memories()) == 20
    assert (project / ".agent-forge/memory.md").read_text().count("## fact") == 20
    a.close(); b.close()


def test_managed_symlinks_rejected(tmp_path):
    outside = tmp_path / "outside"; outside.mkdir()
    project = tmp_path / "project"; project.mkdir()
    (project / ".agent-forge").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"): Store(project)
