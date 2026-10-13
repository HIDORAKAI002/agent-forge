"""Opt-in real Ollama smoke test. Requires an already-installed model and CLI."""
import argparse,json,os,shutil,tempfile,time
from pathlib import Path
from forge.ollama import OllamaAPI,OllamaHub
from forge.planner import Planner
from forge.terminal import Session

def wait(predicate,timeout=180):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if predicate():return
        time.sleep(.05)
    raise AssertionError('Actual model check timed out')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',default='qwen2.5-coder:1.5b');p.add_argument('--output',default='ollama-validation.json');args=p.parse_args()
    command=shutil.which('ollama')
    if not command:raise SystemExit('Install Ollama and put its CLI on PATH first; this test never runs an installer')
    api=OllamaAPI();model=args.model
    evidence={'model':model,'runtime':'Ollama '+api.inventory()['version'],'actual_daemon':True,'actual_weights':True,'tasks_dispatched':0}
    with tempfile.TemporaryDirectory(prefix='forge-model-validation-') as tmp:
        hub=OllamaHub(Path(tmp));planner=Planner()
        try:
            hub.start('refresh');wait(lambda:(hub.poll() or True) and not hub.busy)
            assert any(m['name']==model for m in hub.inventory['installed']),'Pull the local model first; this test does not download weights'
            hub.start('activate',model);wait(lambda:(hub.poll() or True) and not hub.busy)
            assert hub.activation==model,hub.state;evidence['forge_hub_activation']=hub.state
            response=api.json('/api/chat',{'model':model,'stream':False,'messages':[{'role':'user','content':'Write a Python function add(a,b) returning their sum. Return only code.'}],'options':{'num_predict':128,'temperature':0}},timeout=120)
            text=response['message']['content'];assert 'return' in text;evidence['actual_chat_response']=text
            planner.start(api,model,'Add one unit test for a function add(a,b). Produce exactly one bounded routine task.',[])
            wait(lambda:(planner.poll() or True) and not planner.busy);assert planner.draft,planner.state;evidence['actual_forge_plan']=planner.draft
            child=Session([command,'run',model,'Reply with LOCAL_MODEL_OK only.'],tmp,'actual-ollama',env=dict(os.environ))
            try:
                wait(lambda:(child.drain() or True) and child.status=='exited');assert child.exit_code==0
                evidence['embedded_real_cli_exit_code']=child.exit_code;evidence['embedded_real_cli_output']='\n'.join(child.screen.display).strip()
            finally:child.stop()
            hub.start('unload',model);wait(lambda:(hub.poll() or True) and not hub.busy)
            assert hub.state=='Unloaded · auto-activation off',hub.state
            evidence['unload_completed']=not any(m['name']==model for m in api.inventory()['loaded']);assert evidence['unload_completed']
        finally:hub.close();planner.close()
    Path(args.output).write_text(json.dumps(evidence,indent=2)+'\n');print('Actual model checks passed; no task queued or dispatched.')
if __name__=='__main__':main()
