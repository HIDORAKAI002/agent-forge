import subprocess
import pytest

@pytest.fixture
def project(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "README.md").write_text("Fixture project\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture"], check=True, capture_output=True)
    return tmp_path

@pytest.fixture(autouse=True)
def isolate_user_preferences(tmp_path,monkeypatch):
    monkeypatch.setenv("FORGE_CONFIG_HOME",str(tmp_path/"user-preferences"))
