"""Build a source-only installer bundle; excludes local state, keys and environments."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TOP_FILES={'.gitignore','LICENSE','README.md','pyproject.toml','requirements-lock.txt'}
SOURCE_DIRS={'forge','tests','scripts','.github','docs','integrations'}
EXCLUDE={'__pycache__','.pytest_cache','.git','.venv','node_modules','.agent-forge'}
EXTENSIONS={'forge':{'.py'},'tests':{'.py'},'scripts':{'.py','.ps1','.sh'},'.github':{'.py','.yml','.yaml'},'docs':{'.md','.json','.txt','.svg'},'integrations':{'.json','.md'}}

def collect():
    files=[]
    for item in ROOT.iterdir():
        if item.is_symlink():continue
        if item.is_file() and item.name in TOP_FILES:files.append(item)
        elif item.is_dir() and item.name in SOURCE_DIRS:
            for path in item.rglob('*'):
                relative=path.relative_to(ROOT)
                if any(part in EXCLUDE for part in relative.parts):continue
                if item.name=='integrations' and (len(relative.parts)!=3 or relative.parts[1]!='ruflo' or path.name not in ('package.json','package-lock.json','README.md')):continue
                if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent!=ROOT):raise ValueError('Refusing linked bundle source')
                if path.is_file() and path.suffix in EXTENSIONS[item.name]:files.append(path)
    return sorted(files)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='agent-forge-source.zip');p.add_argument('--source-commit',required=True);args=p.parse_args()
    if len(args.source_commit)!=40 or any(c not in '0123456789abcdef' for c in args.source_commit):raise SystemExit('Use a full lowercase source commit SHA')
    files=collect();manifest={'source_commit':args.source_commit,'format':'source-only installation bundle','files':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files},'excluded':'Credentials, workspace data, virtual environments, caches and dependencies are never bundled.'}
    with zipfile.ZipFile(args.output,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:bundle.write(path,'agent-forge/'+str(path.relative_to(ROOT)))
        bundle.writestr('agent-forge/BUNDLE_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    print(f'Built source bundle: {len(files)} files; no local state or dependencies')
if __name__=='__main__':main()
