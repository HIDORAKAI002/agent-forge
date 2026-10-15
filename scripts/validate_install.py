"""Opt-in real installed-launcher smoke test, using a disposable local workspace.

Run with the installed Forge environment's Python. No provider/model or account
is used. It opens a real terminal, executes a fixed shell command in a temporary
project, verifies durable memory/file effects, then explicitly confirms exit.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import tempfile
import time
from forge.terminal import Session
from forge.store import Store


def validate(launcher,timeout=20):
    launcher=Path(launcher).expanduser().resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='forge-installed-check-') as temporary:
        root=Path(temporary);project=root/'project';project.mkdir()
        env=dict(os.environ,FORGE_CONFIG_HOME=str(root/'config'))
        argv=[str(launcher),'--project',str(project)]
        if os.name=='nt' and launcher.suffix.lower() in ('.cmd','.bat'):
            # Session's npm-shim resolver intentionally refuses arbitrary batch
            # files. This is an explicitly supplied managed installer launcher.
            payload='"'+str(launcher)+'" --project "'+str(project)+'"'
            argv=[os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',payload]
        session=Session(argv,str(project),'installed-check',env=env,rows=50,cols=160)
        def wait(predicate):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                session.drain()
                if predicate():return
                time.sleep(.03)
            raise AssertionError(f'Installed terminal check timed out: status={session.status}, exit={session.exit_code}')
        def remembered(text):
            store=Store(project)
            try:wait(lambda:bool(store.memories(text)))
            finally:store.close()
        try:
            wait(lambda:'AGENT / FORGE' in '\n'.join(session.screen.display))
            session.write('/remember fact INSTALLED_LAUNCHER_MEMORY\r');remembered('INSTALLED_LAUNCHER_MEMORY')
            session.write('/doctor\r');time.sleep(.3)
            session.write('/launch shell\r')
            wait(lambda:'Embedded PTY / native input' in '\n'.join(session.screen.display))
            marker=project/'executed.txt'
            command=(f'echo INSTALLED_NESTED_SHELL_OK & echo executed>"{marker}"' if os.name=='nt' else
                     "printf 'INSTALLED_NESTED_SHELL_OK\\n'; printf 'executed' > "+shlex.quote(str(marker)))
            session.write(command+'\r')
            wait(lambda:marker.exists() and marker.read_text().strip()=='executed' and 'INSTALLED_NESTED_SHELL_OK' in '\n'.join(session.screen.display))
            time.sleep(.15);session.write('\x00');time.sleep(.15)
            session.write('/remember fact INSTALLED_RETURN_TO_COMPOSER\r');remembered('INSTALLED_RETURN_TO_COMPOSER')
            session.write('/quit\r');wait(lambda:'CLOSE WORKSPACE' in '\n'.join(session.screen.display))
            time.sleep(.15);session.write('y');wait(lambda:session.status=='exited')
            assert session.exit_code==0
            return {'platform':'windows' if os.name=='nt' else 'posix','actual_outer_tui':True,'persistent_memory':True,'nested_shell_file_execution':True,'returned_to_composer':True,'confirmed_exit_code':0,'credentials_used':False,'scope':'Installed-terminal functional smoke test; not filesystem isolation, cloud-provider or coding-quality acceptance.'}
        finally:
            session.stop()
            try:wait(lambda:session.status=='exited')
            except AssertionError:pass


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--launcher',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=validate(args.launcher)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print('Installed terminal, memory, nested shell and confirmed exit passed.')


if __name__=='__main__':main()
