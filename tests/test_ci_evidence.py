"""CI publication must reject stale, interrupted, skipped-only or invalid runs."""
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('ci_report',Path(__file__).parents[1]/'.github/scripts/ci_report.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('status,code,sha,tests,failures,skips,expected',[
    ('completed',0,'current',3,0,1,'passed'),
    ('completed',1,'current',3,0,0,'failed'),
    ('running',None,'current',3,0,0,'failed'),
    ('completed',0,'old',3,0,0,'failed'),
    ('completed',0,'current',3,1,0,'failed'),
    ('completed',0,'current',3,0,3,'failed'),
    ('completed',0,'current',0,0,0,'failed'),
])
def test_report_requires_completed_successful_current_execution(tmp_path,monkeypatch,status,code,sha,tests,failures,skips,expected):
    monkeypatch.setenv('GITHUB_SHA','current')
    execution=tmp_path/'execution.json';execution.write_text(json.dumps({'status':status,'exit_code':code,'source_commit':sha}))
    junit=tmp_path/'junit.xml';junit.write_text(f'<testsuites><testsuite tests="{tests}" failures="{failures}" skipped="{skips}"/></testsuites>')
    report=module.build_report('unit',junit,execution)
    assert report['status']==expected
    assert report['passed']==tests-failures-skips


def test_report_missing_and_invalid_evidence_fails_closed(tmp_path):
    junit=tmp_path/'junit.xml';execution=tmp_path/'execution.json'
    assert module.build_report('unit',junit,execution)['status']=='failed'
    execution.write_text('{}');junit.write_text('not xml')
    assert module.build_report('unit',junit,execution)['status']=='failed'
