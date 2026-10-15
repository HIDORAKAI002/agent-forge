"""Opt-in real local coding acceptance in disposable Linux Bubblewrap isolation.

Uses an existing local Ollama model and Aider install; never downloads weights,
installs software, disables CLI confirmations, commits model edits or merges.
Network approval here shares HOST networking, not a loopback-only firewall.
"""
import argparse,ast,json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from urllib.parse import urlsplit
from forge.runtime import Runtime
from forge.ollama import endpoint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',default='qwen2.5-coder:1.5b')
    parser.add_argument('--read-only-runtime',action='append',default=[])
    parser.add_argument('--output',default='local-coding-validation.json')
    args=parser.parse_args()
    address=endpoint();parsed=urlsplit(address)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise SystemExit('This acceptance script requires a credential-free local Ollama endpoint')
    aider=shutil.which('aider')
    if not aider:raise SystemExit('Install Aider first; this script does not install or authenticate providers')
    prior=os.environ.get('FORGE_CONFIG_HOME')
    with tempfile.TemporaryDirectory(prefix='forge-enforced-coding-') as temporary:
        root=Path(temporary);project=root/'project';project.mkdir()
        os.environ['FORGE_CONFIG_HOME']=str(root/'trusted')
        def git(*argv):return subprocess.run(['git','-C',str(project),*argv],check=True,capture_output=True,text=True)
        git('init');git('config','user.name','Local acceptance');git('config','user.email','local@example.invalid')
        original='def add(a, b):\n    raise NotImplementedError("TODO")\n'
        readme='# Calculator fixture\n';expected_readme='# Calculator\n\nSupports addition.'
        (project/'calculator.py').write_text(original);(project/'README.md').write_text(readme)
        git('add','.');git('commit','-m','Disposable acceptance fixture')
        config=project/'.agent-forge';config.mkdir()
        command=[aider,'--model','ollama_chat/'+args.model,'--no-auto-commits','--no-dirty-commits',
                 '--analytics-disable','--no-gitignore','--no-check-update','--no-show-model-warnings','calculator.py','README.md']
        (config/'profiles.json').write_text(json.dumps([{'id':'aider-local','argv':command,
            'task_argv':command+['--message','{prompt}'],'tier':'local'}]))
        runtime=Runtime(project)
        try:
            runtime.sandbox.save({'enabled':True,'network':True,'read_only':args.read_only_runtime})
            task=runtime.store.create_task('Local two-file acceptance',
                'Implement add(a,b) in calculator.py by returning a+b. Replace README.md contents with exactly:\n'+expected_readme+
                '\nChange only calculator.py and README.md. No commands, dependencies or other files are needed.','aider-local')
            session=runtime.run_task(task['id']);deadline=time.monotonic()+240;dismissed=False
            while time.monotonic()<deadline and session.status=='running':
                runtime.poll();screen='\n'.join(session.screen.display)
                if "Would you like to see what's new in this version?" in screen and not dismissed:
                    session.write('n\r');dismissed=True  # Decline optional release-notes browser, not edit authorization.
                time.sleep(.05)
            assert session.status=='exited' and session.exit_code==0,'Local CLI failed/timed out; no approval or retry performed'
            row=runtime.store.task(task['id']);tree=Path(row['worktree']);code=(tree/'calculator.py').read_text();module=ast.parse(code)
            # Never execute arbitrary generated code. Accept only the exact
            # two-argument return-a-plus-b AST, then evaluate with no builtins.
            assert len(module.body)==1 and isinstance(module.body[0],ast.FunctionDef)
            function=module.body[0];arguments=function.args
            assert function.name=='add' and not function.decorator_list and function.returns is None and not getattr(function,'type_params',[])
            assert len(arguments.args)==2 and [a.arg for a in arguments.args]==['a','b'] and all(a.annotation is None for a in arguments.args)
            assert not (arguments.defaults or arguments.kwonlyargs or arguments.kw_defaults or arguments.vararg or arguments.kwarg or arguments.posonlyargs)
            body=[n for n in function.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
            assert len(body)==1 and isinstance(body[0],ast.Return)
            value=body[0].value
            assert isinstance(value,ast.BinOp) and isinstance(value.op,ast.Add)
            assert isinstance(value.left,ast.Name) and value.left.id=='a' and isinstance(value.right,ast.Name) and value.right.id=='b'
            namespace={};exec(compile(module,'validated-local-add','exec'),{'__builtins__':{}},namespace)
            assert namespace['add'](2,3)==5 and namespace['add'](-2,2)==0
            assert (tree/'README.md').read_text().strip()==expected_readme
            assert row['status']=='needs-review' and session.isolation=='ENFORCED / Bubblewrap'
            assert (project/'calculator.py').read_text()==original and (project/'README.md').read_text()==readme
            # Model commits are disabled; parent fixture commit stays unchanged.
            base=git('rev-parse','HEAD').stdout.strip()
            assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()==base
            evidence={'kind':'Actual two-file local Aider coding in Linux Bubblewrap','model':args.model,
                'actual_model_inference':True,'authorized_files':['calculator.py','README.md'],'assertions':['add(2,3)==5','add(-2,2)==0','README exact expected text'],
                'task_status':row['status'],'sandbox_active':True,'network':'explicit host-network permission for local Ollama; not domain-only isolation',
                'original_project_unchanged':True,'model_commits_or_merges':False,'native_confirmations_disabled':False,'paid_provider_calls':0,
                'scope':'Bounded local smoke test, not a coding benchmark, cloud acceptance or native Windows evidence.'}
            Path(args.output).write_text(json.dumps(evidence,indent=2)+'\n')
            print('Actual two-file enforced local coding passed; needs-review, originals unchanged, no model commit/merge.')
        finally:
            runtime.close()
            if prior is None:os.environ.pop('FORGE_CONFIG_HOME',None)
            else:os.environ['FORGE_CONFIG_HOME']=prior


if __name__=='__main__':main()
