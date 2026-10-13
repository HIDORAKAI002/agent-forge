import importlib.util
from pathlib import Path
import pytest

@pytest.fixture
def bundler():
    path=Path(__file__).resolve().parents[1]/'scripts/build_bundle.py'
    spec=importlib.util.spec_from_file_location('forge_bundle_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_source_bundle_excludes_state_and_dependencies(tmp_path,monkeypatch,bundler):
    monkeypatch.setattr(bundler,'ROOT',tmp_path)
    for file in ('README.md','forge/runtime.py','forge/__pycache__/runtime.pyc','.agent-forge/memory.sqlite','.venv/secret.txt','forge/credentials.json','docs/private.env','scripts/build_bundle.py'):
        path=tmp_path/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
    assert {str(p.relative_to(tmp_path)) for p in bundler.collect()}=={'README.md','forge/runtime.py','scripts/build_bundle.py'}

def test_source_bundle_refuses_nested_links(tmp_path,monkeypatch,bundler):
    monkeypatch.setattr(bundler,'ROOT',tmp_path);directory=tmp_path/'forge';directory.mkdir()
    try:(directory/'runtime.py').symlink_to(tmp_path/'outside')
    except OSError:pytest.skip('This host has no symlink privilege')
    with pytest.raises(ValueError,match='linked'):bundler.collect()
