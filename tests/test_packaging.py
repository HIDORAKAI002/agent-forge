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
    assert {p.relative_to(tmp_path).as_posix() for p in bundler.collect()}=={'README.md','forge/runtime.py','scripts/build_bundle.py'}

def test_source_bundle_refuses_nested_links(tmp_path,monkeypatch,bundler):
    monkeypatch.setattr(bundler,'ROOT',tmp_path);directory=tmp_path/'forge';directory.mkdir()
    try:(directory/'runtime.py').symlink_to(tmp_path/'outside')
    except OSError:pytest.skip('This host has no symlink privilege')
    with pytest.raises(ValueError,match='linked'):bundler.collect()


def test_source_bundle_includes_only_reviewed_ruflo_lockfiles(tmp_path,monkeypatch,bundler):
    monkeypatch.setattr(bundler,'ROOT',tmp_path)
    for name in ('package.json','package-lock.json','README.md','credentials.json','node_modules/runtime/package.json','nested/package.json'):
        path=tmp_path/'integrations/ruflo'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
    assert {p.relative_to(tmp_path).as_posix() for p in bundler.collect()}=={
        'integrations/ruflo/package.json','integrations/ruflo/package-lock.json','integrations/ruflo/README.md'}


def test_documentation_has_no_unexpected_control_characters():
    root = Path(__file__).resolve().parents[1]
    disallowed = {'\x00', '\x07', '\x08', '\x0b', '\x0c'}
    for doc in (root / 'docs').rglob('*.md'):
        content = doc.read_text(encoding='utf-8')
        for char in disallowed:
            assert char not in content, f"Unexpected control character {char!r} found in {doc.name}"

