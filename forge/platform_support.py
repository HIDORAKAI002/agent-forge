"""Platform boundaries: lock ownership and Windows npm-shim launching."""
import os
from pathlib import Path

class WorkspaceLock:
    def __init__(self,path:Path):
        self.file=path.open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.file.seek(0,2)
                if self.file.tell()==0:self.file.write(b'\0');self.file.flush()
                self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();raise ValueError('Another Agent Forge workspace already owns this project') from None
    def close(self):
        if self.file.closed:return
        if os.name=='nt':
            import msvcrt
            self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
        self.file.close()

def windows_command(argv,env):
    """Resolve standard npm .cmd shims to native Node; never parse a task via cmd.exe."""
    import re,shutil
    resolved=shutil.which(argv[0]) or argv[0]
    if Path(resolved).suffix.lower() not in ('.cmd','.bat'):return argv,env
    shim=Path(resolved)
    text=shim.read_text(encoding='utf-8',errors='replace')
    match=re.search(r'"(?:%dp0%|%~dp0)[\\/](?P<entry>[^"\r\n]+\.(?:js|mjs|cjs))"',text,re.IGNORECASE)
    if not match:raise ValueError('This batch shim is not a standard Node/npm launcher. Configure its native executable explicitly; task text is never interpolated through cmd.exe.')
    entry=(shim.parent/Path(match['entry'].replace('\\','/'))).resolve(strict=True)
    if not entry.is_relative_to(shim.parent.resolve()):raise ValueError('npm shim entry escapes its install directory')
    node=shim.parent/'node.exe'
    executable=str(node) if node.is_file() else shutil.which('node.exe') or shutil.which('node')
    if not executable:raise ValueError('Node.js is required for this npm CLI')
    return [executable,str(entry),*argv[1:]],env

def native_commandline(argv):
    """MSVCRT quoting for programs; preserve one explicitly supplied cmd payload.

    cmd.exe does not interpret MSVCRT's backslash-escaped quotes. Never turn
    provider argument arrays into shell scripts or join extra payload arguments.
    """
    import subprocess
    if Path(argv[0]).name.lower() != 'cmd.exe':
        return subprocess.list2cmdline(argv)
    for index, arg in enumerate(argv[1:], 1):
        if arg.lower() in ('/c', '/k'):
            if len(argv) != index + 2:
                raise ValueError('cmd requires exactly one explicit command payload')
            prefix = argv[:index]
            if not any(item.lower() == '/s' for item in prefix):
                prefix = [*prefix, '/s']
            return subprocess.list2cmdline([*prefix, arg]) + ' "' + argv[index+1] + '"'
    return subprocess.list2cmdline(argv)
