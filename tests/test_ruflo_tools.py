import asyncio,json,os,shutil,sys
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from forge.ruflo_tools import (RufloToolSession,validate_requests,validate_arguments,
                              review_digest,bounded_result)

SCHEMA={'type':'object','properties':{'value':{'type':'string'}},'required':['value'],'additionalProperties':False}
CATALOG={'example':{'name':'example','description':'Example','inputSchema':SCHEMA}}

def test_bounded_requests_and_no_in_place_mutation():
    raw=[{'tool':'example','arguments':{'value':'original'}}];copy=validate_requests(raw)
    raw[0]['arguments']['value']='changed';assert copy[0]['arguments']['value']=='original'
    for value in ([],[{}],[{'tool':'bad name','arguments':{}}],[{'tool':'example','arguments':[]}]):
        with pytest.raises(ValueError):validate_requests(value)
    with pytest.raises(ValueError):validate_requests([{'tool':'example','arguments':{'value':'x'*100001}}])
    with pytest.raises(ValueError):validate_requests([{'tool':'example','arguments':{'value':float('nan')}}])

def test_schema_validation_does_not_fetch_external_refs_or_echo_secrets():
    validate_arguments(SCHEMA,{'value':'works'})
    for key in ('$ref','$dynamicRef','$recursiveRef'):
        with pytest.raises(ValueError,match='External'):validate_arguments({key:'https://untrusted.invalid/schema'}, {})
    with pytest.raises(ValueError) as error:validate_arguments(SCHEMA,{'sensitive':'FAKE_DO_NOT_ECHO'})
    assert 'FAKE_DO_NOT_ECHO' not in str(error.value)

def test_review_binds_commands_schemas_policy_and_workspace(tmp_path):
    request=[{'tool':'example','arguments':{'value':'ok'}}];policy={'enabled':True,'read_only':[],'network':False}
    digest=review_digest(tmp_path,policy,CATALOG,request)
    assert len(digest)==64
    assert digest!=review_digest(tmp_path,{**policy,'network':True},CATALOG,request)
    assert digest!=review_digest(tmp_path/'other',policy,CATALOG,request)
    assert digest!=review_digest(tmp_path,policy,{**CATALOG,'example':{**CATALOG['example'],'description':'changed'}},request)
    assert digest!=review_digest(tmp_path,policy,CATALOG,[{'tool':'example','arguments':{'value':'changed'}}])

def test_full_gateway_requires_isolation_before_launch(tmp_path,monkeypatch):
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'trusted'))
    project=tmp_path/'project';project.mkdir();connection=RufloToolSession(project,command='not-installed')
    with pytest.raises(ValueError,match='require enforced'):connection.launch_spec()

class Reply:
    def __init__(self,error=False):self.isError=error;self.structuredContent=None;self.content=[]
    def model_dump(self,**kwargs):return {'isError':self.isError,'content':[{'type':'text','text':'FAKE_RESULT_SECRET'}]}

async def test_approval_failure_ordering_and_audit_redaction(tmp_path,monkeypatch):
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'trusted'))
    project=tmp_path/'project';project.mkdir();connection=RufloToolSession(project)
    connection.policy=connection.sandbox.policy;connection.catalog=CATALOG
    class Client:
        calls=[]
        async def call_tool(self,name,args):self.calls.append(name);return Reply(error=True)
    client=Client();connection.session=client
    requests=[{'tool':'example','arguments':{'value':'FAKE_ARGUMENT_SECRET'}}]*2
    _,digest=connection.prepare(requests)
    with pytest.raises(ValueError,match='review digest'):await connection.execute(requests,'wrong')
    assert client.calls==[]
    result=await connection.execute(requests,digest)
    assert client.calls==['example'] and len(result)==1
    records=(connection.audit_root/(digest+'.jsonl')).read_text()
    assert 'FAKE_ARGUMENT_SECRET' not in records and 'FAKE_RESULT_SECRET' not in records
    assert 'upstream-error' in records
    monkeypatch.setattr('forge.ruflo_tools.Sandbox',lambda _:NS(policy={'changed':True}))
    with pytest.raises(ValueError,match='Permissions changed'):await connection.execute(requests,digest)

async def test_tool_timeout_is_a_failure_not_rollback(tmp_path,monkeypatch):
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'trusted'));project=tmp_path/'project';project.mkdir()
    connection=RufloToolSession(project);connection.policy=connection.sandbox.policy;connection.catalog=CATALOG
    class Client:
        async def call_tool(self,*args):raise asyncio.TimeoutError
    connection.session=Client();requests=[{'tool':'example','arguments':{'value':'ok'}}];_,digest=connection.prepare(requests)
    with pytest.raises(asyncio.TimeoutError):await connection.execute(requests,digest)
    assert 'failed-or-cancelled' in (connection.audit_root/(digest+'.jsonl')).read_text()

def test_upstream_result_size_bound():
    class Huge:
        def model_dump(self,**kwargs):return {'content':'x'*1000001}
    with pytest.raises(ValueError,match='1 MB'):bounded_result(Huge())

async def test_actual_ruflo_broad_catalog_inside_boundary(tmp_path,monkeypatch):
    if os.environ.get('FORGE_RUFLO_FULL_TESTS')!='1':pytest.skip('Real pinned Ruflo plus Bubblewrap required')
    assert sys.platform.startswith('linux') and shutil.which('bwrap')
    project=tmp_path/'project';project.mkdir();reference=tmp_path/'reference';reference.mkdir();(reference/'read.txt').write_text('APPROVED_REFERENCE')
    denied=tmp_path/'denied';denied.mkdir();(denied/'secret').write_text('UNAPPROVED')
    monkeypatch.setenv('FORGE_CONFIG_HOME',str(tmp_path/'trusted'));monkeypatch.setenv('ANTHROPIC_API_KEY','FAKE_NEVER_FORWARD')
    connection=RufloToolSession(project);grants=[str(reference)]
    for runtime in (Path(os.environ['FORGE_RUFLO_BIN']).resolve().parents[3],Path(shutil.which('node')).resolve().parent.parent):
        # Runtime grants intentionally separate from user data.
        if not runtime.is_relative_to(Path('/usr')) and runtime!=Path('/') and str(runtime) not in grants:grants.append(str(runtime))
    connection.sandbox.save({'enabled':True,'read_only':grants,'network':False})
    async with connection.connect():
        assert len(connection.catalog)>300
        assert {'terminal_execute','memory_stats','workflow_list','swarm_init','agent_spawn'}.issubset(connection.catalog)
        requests=[{'tool':'memory_stats','arguments':{}},{'tool':'workflow_list','arguments':{}}]
        _,digest=connection.prepare(requests);results=await connection.execute(requests,digest)
        assert len(results)==2 and all(not row['result'].get('isError') for row in results)
        # Exercise a REAL upstream command tool, not a mocked subprocess adapter.
        import shlex
        code=f'''import pathlib,os
p=pathlib.Path({str(project)!r});r=pathlib.Path({str(reference)!r});d=pathlib.Path({str(denied)!r})
assert 'ANTHROPIC_API_KEY' not in os.environ
(p/'upstream-wrote.txt').write_text('ok')
assert (r/'read.txt').read_text()=='APPROVED_REFERENCE'
for path,write in [(r/'blocked.txt',True),(d/'secret',False),(d/'outside.txt',True)]:
 try:path.write_text('escape') if write else path.read_text()
 except OSError:pass
 else:raise AssertionError('Upstream escaped project boundary')
print('REAL_RUFLO_BOUNDARY_OK')
'''
        # /usr/bin/python3 belongs to the read-only system runtime, no Python venv grant.
        requests=[{'tool':'terminal_execute','arguments':{'command':shlex.join(['/usr/bin/python3','-c',code]),'timeout':15000,'captureOutput':True}}]
        _,digest=connection.prepare(requests);results=await connection.execute(requests,digest)
        assert 'REAL_RUFLO_BOUNDARY_OK' in json.dumps(results),json.dumps(results)[:500]
        assert (project/'upstream-wrote.txt').read_text()=='ok'
        assert not (denied/'outside.txt').exists() and not (reference/'blocked.txt').exists()
