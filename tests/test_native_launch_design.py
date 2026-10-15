"""Portable structural guards; actual Windows kernel tests remain mandatory."""
import ast
from pathlib import Path


def test_container_integrity_is_verified_not_raised_after_process_creation():
    path=Path(__file__).parents[1]/'forge/windows_isolation.py'
    tree=ast.parse(path.read_text())
    functions={node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    verify=ast.get_source_segment(path.read_text(),functions['prepare_lpac_integrity'])
    assert 'verify_container_token' in verify and 'SetTokenInformation' not in verify
    launch=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='NativeProcess')
    source=ast.get_source_segment(path.read_text(),launch)
    assert 'primary_container_token(boundary,caps)' in source
    assert 'api.CreateProcessAsUserW(token,' in source
    assert 'k.CreateProcessW(' not in source
    assert 'attribute(0x2000F,W.DWORD(1))' in source
    assert 'attribute(0x20009,caps)' not in source
    assert source.index('prepare_lpac_integrity(self.process')<source.index('k.ResumeThread(')


def test_restricted_parent_token_requests_default_adjustment_before_lowering():
    source=(Path(__file__).parents[1]/'forge/windows_isolation.py').read_text()
    assert 'kernel.GetCurrentProcess(),0x008B' in source
    assert "if level<8192:raise ValueError" in source
    assert 'if level>8192:' in source
