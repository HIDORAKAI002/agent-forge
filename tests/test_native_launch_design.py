"""Portable guards do not replace actual Windows kernel acceptance."""
import ast
from pathlib import Path


def test_child_integrity_is_verified_without_privilege_or_integrity_changes():
    path=Path(__file__).parents[1]/'forge/windows_isolation.py';source=path.read_text();tree=ast.parse(source)
    functions={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
    verify=ast.get_source_segment(source,functions['prepare_lpac_integrity'])
    assert 'SetTokenInformation' not in source and 'CreateAppContainerToken' not in source
    assert 'OpenProcessToken(process,0x8,' in verify
    assert 'brokered writable workspace is required' in verify
    launch=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='NativeProcess')
    code=ast.get_source_segment(source,launch)
    assert 'attribute(0x20009,caps)' in code and 'attribute(0x2000F,W.DWORD(1))' in code
    assert code.index('prepare_lpac_integrity(self.process')<code.index('k.ResumeThread(')
    supported=ast.get_source_segment(source,functions['supported'])
    assert "FORGE_WINDOWS_ISOLATION_EXPERIMENTAL" in supported
