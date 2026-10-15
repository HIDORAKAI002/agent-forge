"""Fail-closed Bubblewrap filesystem boundary; trusted policy outside the project."""
from pathlib import Path
import hashlib,json,os,shutil,sys
from .settings import Preferences

BASE_RUNTIME=('/usr','/bin','/sbin','/lib','/lib64')
BASE_CONFIG=('/etc/ld.so.cache','/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf','/etc/ssl/certs')

class Sandbox:
    def __init__(self,project):
        self.project=Path(project).resolve(strict=True)
        root=Preferences().root/'permissions'
        if root.is_symlink():raise ValueError('Refusing linked permissions directory')
        root.mkdir(mode=0o700,exist_ok=True)
        self.path=root/(hashlib.sha256(str(self.project).encode()).hexdigest()+'.json')
        if self.path.is_symlink():raise ValueError('Refusing symlinked permission storage')
        self.policy={'enabled':False,'read_only':[],'network':False}
        if self.path.exists():
            data=json.loads(self.path.read_text());self.policy=self.validate(data)
    def validate(self,data):
        if not isinstance(data,dict) or type(data.get('enabled')) is not bool or type(data.get('network')) is not bool:raise ValueError('Invalid sandbox policy')
        grants=data.get('read_only',[])
        if not isinstance(grants,list) or len(grants)>20:raise ValueError('Maximum 20 read-only grants')
        resolved=[]
        for raw in grants:
            if not isinstance(raw,str) or '\0' in raw:raise ValueError('Invalid read-only path')
            p=Path(raw).expanduser().resolve(strict=True)
            if not p.is_dir() or p==Path(p.anchor) or p.is_relative_to(self.project) or self.project.is_relative_to(p):raise ValueError('Reference grants must be separate bounded directories, not the project, its parent or a disk root')
            if str(p) not in resolved:resolved.append(str(p))
        return {'enabled':data['enabled'],'read_only':resolved,'network':data['network']}
    def save(self,data):
        policy=self.validate(data)
        if policy['enabled']:
            if self.path.is_relative_to(self.project):raise ValueError('Permission storage must be outside writable project')
            if os.name=='nt':
                from .windows_isolation import supported,unlinked,paths
                supported();unlinked(self.project)
                for root in [self.project,*map(Path,policy['read_only'])]:paths(root)
            elif sys.platform.startswith('linux'):
                if not shutil.which('bwrap'):raise ValueError('Install Bubblewrap before enabling isolation; no unsandboxed fallback')
            else:raise ValueError('Enforced isolation is unavailable on this platform')
            if Path(__file__).resolve().is_relative_to(self.project):raise ValueError('Install Forge outside the writable project before enabling isolation')
        tmp=self.path.with_suffix('.tmp')
        if tmp.is_symlink():raise ValueError('Refusing symlinked permission temporary file')
        with tmp.open('w') as f:json.dump(policy,f,indent=2)
        if os.name!='nt':tmp.chmod(0o600)
        tmp.replace(self.path);self.policy=policy
    def protected_state(self,cwd):
        """Host-owned state is not an agent-write API; only assigned trees write."""
        state=self.project/'.agent-forge'
        if state.is_symlink():raise ValueError('Linked coordinator state is not supported')
        worktree=None
        if state.exists():
            if not state.is_dir():raise ValueError('Coordinator state must be a directory')
            trees=state/'worktrees'
            if trees.is_symlink():raise ValueError('Linked worktree storage is not supported')
            current=Path(cwd).resolve(strict=True)
            if current.is_relative_to(trees):
                relative=current.relative_to(trees)
                if not relative.parts:raise ValueError('Choose one assigned worktree, not its storage directory')
                candidate=trees/relative.parts[0]
                if candidate.is_symlink():raise ValueError('Linked assigned worktree is not supported')
                worktree=candidate
        return state,worktree

    def refuse_hardlinked_project_files(self):
        # A read-only bind is path-based. A pre-existing writable hardlink alias
        # to Git/state/reference data would otherwise bypass that overlay.
        count=0
        for directory,dirs,files in os.walk(self.project,followlinks=False):
            for name in files:
                path=Path(directory)/name
                if path.is_symlink():continue  # Existing external symlinks stay hidden by mounts.
                count+=1
                if count>100_000:raise ValueError('Protected project exceeds 100,000 files')
                if path.stat().st_nlink>1:raise ValueError('Enforced projects refuse hard-linked files; copy the file instead')

    def wrap(self,argv,cwd,environment,credentials=None,*,protect_control=True,writable_worktree=None):
        if not self.policy['enabled']:return argv,environment
        if os.name=='nt':
            from .windows_isolation import SPEC,supported,unlinked
            supported()
            if Path(__file__).resolve().is_relative_to(self.project) or self.path.is_relative_to(self.project):raise ValueError('Native runtime/policy must stay outside writable project')
            current=unlinked(Path(cwd).resolve(strict=True))
            if not current.is_relative_to(self.project):raise ValueError('Native working directory must stay in project')
            clean={k:environment[k] for k in ('PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','USERPROFILE','LOCALAPPDATA','APPDATA','LANG','LC_ALL','TERM','COLORTERM') if k in environment}
            clean.update(credentials or {})
            if self.policy['network'] and 'OLLAMA_API_BASE' in environment:clean['OLLAMA_API_BASE']=environment['OLLAMA_API_BASE']
            clean.update(FORGE_PROJECT=str(self.project),GIT_OPTIONAL_LOCKS='0')
            clean['FORGE_CONFIG_HOME']=str(self.path.parent.parent.resolve())
            clean['FORGE_WINDOWS_ISOLATION_EXPERIMENTAL']='1'
            clean[SPEC]=json.dumps({'project':str(self.project),'policy':self.policy,'protect_git':protect_control})
            return [sys.executable,'-I','-m','forge.windows_isolation',*argv],clean
        if not sys.platform.startswith('linux') or not (bwrap:=shutil.which('bwrap')):raise ValueError('Sandbox unavailable; refusing to launch without enforcement')
        if Path(__file__).resolve().is_relative_to(self.project):raise ValueError('Forge installation overlaps writable project')
        if self.path.is_relative_to(self.project):raise ValueError('Sandbox permission storage overlaps writable project')
        current=Path(cwd).resolve(strict=True)
        if not current.is_relative_to(self.project):raise ValueError('Sandbox working directory must stay in project')
        self.refuse_hardlinked_project_files()
        state,worktree=self.protected_state(current)
        state.mkdir(mode=0o700,exist_ok=True)
        git_target=None
        if writable_worktree is not None:
            if protect_control:raise ValueError('Writable Git setup scope is parent-only')
            git_target=Path(writable_worktree).absolute()
            if git_target.is_symlink() or git_target.parent!=state/'worktrees' or git_target.resolve(strict=True)!=git_target or not git_target.is_dir():
                raise ValueError('Git setup scope must be one existing managed worktree')
        args=[bwrap,'--die-with-parent','--new-session','--unshare-all','--unshare-user','--cap-drop','ALL']
        if self.policy['network']:args+=['--share-net']
        # These standard runtime trees are read-only, not a bind of the host root.
        for raw in BASE_RUNTIME:
            p=Path(raw)
            if p.exists():
                if p.is_symlink():args+=['--symlink',os.readlink(p),raw]
                else:args+=['--ro-bind',raw,raw]
        for raw in BASE_CONFIG:
            if Path(raw).exists():args+=['--ro-bind',str(Path(raw).resolve()),raw]
        args+=['--dev','/dev','--tmpfs','/tmp','--dir','/tmp/forge-home']
        for raw in self.policy['read_only']:
            if Path(raw).is_symlink() or str(Path(raw).resolve(strict=True))!=raw:raise ValueError('Read-only grant changed; review and save permissions again')
            args+=['--ro-bind',raw,raw]
        args+=['--ro-bind' if not protect_control or worktree else '--bind',str(self.project),str(self.project)]
        # Agents may edit source, not Git control files consumed by trusted helpers.
        metadata=self.project/'.git'
        if metadata.is_symlink():raise ValueError('Linked Git metadata is not supported in enforced mode')
        if metadata.exists():
            if not metadata.is_dir():raise ValueError('Enforced projects require in-project Git metadata')
            args+=['--ro-bind' if protect_control else '--bind',str(metadata),str(metadata)]
        if state.exists():
            args+=['--ro-bind',str(state),str(state)]
            if git_target:args+=['--bind',str(git_target),str(git_target)]
            if protect_control and worktree:
                args+=['--bind',str(worktree),str(worktree)]
                control=worktree/'.git'
                if control.is_symlink():raise ValueError('Linked worktree Git control is refused')
                if control.exists():args+=['--ro-bind',str(control),str(control)]
        args+=['--chdir',str(current)]
        # Drop inherited secrets, SSH sockets, startup hooks and arbitrary environment.
        clean={k:environment[k] for k in ('PATH','LANG','LC_ALL','TERM','COLORTERM') if k in environment}
        clean.update(HOME='/tmp/forge-home',TMPDIR='/tmp',FORGE_PROJECT=str(self.project))
        clean.update(credentials or {})
        if protect_control:clean['GIT_OPTIONAL_LOCKS']='0'
        if self.policy['network'] and 'OLLAMA_API_BASE' in environment:clean['OLLAMA_API_BASE']=environment['OLLAMA_API_BASE']
        return args+['--',*argv],clean
    def summary(self):
        if not self.policy['enabled']:return 'ACTIVE: OFF / host filesystem and network permissions; review choices to apply enforcement'
        return 'NEW SESSIONS: ENFORCED / project writable; references read-only'+f" · network {'allowed (host network)' if self.policy['network'] else 'blocked'} · {len(self.policy['read_only'])} reference grants"
