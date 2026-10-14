"""Native Windows LPAC process boundary. No WSL, cwd-only claims or fallback.

One protected process tree per user at a time: ACL/label grants are transient.
The gate and recovery journal live outside all writable/granted trees. Refuse
linked/hard-linked inputs rather than following them while changing security.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
import codecs,json,os,shutil,sys,threading,time,uuid
from pathlib import Path
from contextlib import contextmanager
from .platform_support import WorkspaceLock
from .settings import Preferences

SPEC='FORGE_WINDOWS_BOUNDARY'
READ=0x1200A9
WRITE_DENY=0xD0156
MODIFY=0x1301BF  # No DELETE_CHILD, WRITE_DAC or WRITE_OWNER.
LABEL_INFO=0x10


def unlinked(path):
    path=Path(path).absolute()
    for p in (path,*path.parents):
        if p.exists() and p.lstat().st_file_attributes & 0x400:
            raise ValueError('Native boundary refuses reparse points in granted paths')
    return path


def paths(root):
    unlinked(root)
    result=[Path(root)]
    for directory,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            path=Path(directory)/name;unlinked(path)
            if path.is_file() and path.stat().st_nlink>1:
                raise ValueError('Native boundary refuses hard-linked grant inputs')
            result.append(path)
    if len(result)>100_000:raise ValueError('Native grant tree exceeds 100,000 objects')
    return result


def supported():
    if os.name!='nt':raise ValueError('Native Windows is required')
    if os.environ.get('FORGE_WINDOWS_ISOLATION_EXPERIMENTAL')!='1':raise ValueError('Native Windows isolation is experimental; not release-enabled until native acceptance gates pass')
    if sys.getwindowsversion().build<17763:raise ValueError('Windows 10 build 17763+ is required')
    import win32file,win32security  # Explicit installer dependency, no driver/elevation.
    for name in ('CreateAppContainerProfile','DeleteAppContainerProfile','GetAppContainerFolderPath'):
        getattr(C.WinDLL('userenv'),name)
    getattr(C.WinDLL('kernel32'),'CreatePseudoConsole')


class Boundary:
    def __init__(self,project,policy,protect_git=True):
        supported();self.project=unlinked(Path(project).resolve(strict=True));self.policy=policy;self.protect_git=protect_git
        if self.project==Path(self.project.anchor):raise ValueError('Native writable project must not be a disk root')
        if str(self.project).startswith('\\\\'):raise ValueError('UNC projects are not supported by native isolation')
        self.root=unlinked(Preferences().root/'windows-boundary');self.root.mkdir(mode=0o700,exist_ok=True)
        if self.root.is_relative_to(self.project):raise ValueError('Windows gate must be outside project')
        self.lock=None;self.record=None;self.sid=None;self.home=None
        self.name='AgentForge.'+uuid.uuid4().hex
        self.userenv=C.WinDLL('userenv',use_last_error=True)
        self.userenv.CreateAppContainerProfile.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p,W.DWORD,C.POINTER(C.c_void_p)];self.userenv.CreateAppContainerProfile.restype=C.c_long
        self.userenv.DeleteAppContainerProfile.argtypes=[W.LPCWSTR];self.userenv.DeleteAppContainerProfile.restype=C.c_long
        self.userenv.GetAppContainerFolderPath.argtypes=[W.LPCWSTR,C.POINTER(C.c_void_p)];self.userenv.GetAppContainerFolderPath.restype=C.c_long

    def write_record(self):
        path=self.root/(self.name+'.json');temp=path.with_suffix('.tmp');unlinked(path);unlinked(temp)
        temp.write_text(json.dumps(self.record,ensure_ascii=True));temp.replace(path)

    @staticmethod
    @contextmanager
    def handle(path):
        import win32file,win32con
        unlinked(path)
        h=win32file.CreateFile(str(path),0x20000|0x40000|0x80000,
                                   win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE|win32con.FILE_SHARE_DELETE,
                                   None,win32con.OPEN_EXISTING,0x02000000|0x00200000,None)
        try:yield h
        finally:h.Close()

    @staticmethod
    def identity(handle):
        import win32file
        info=win32file.GetFileInformationByHandle(handle)
        if info[0]&0x400:raise ValueError('Reparse object changed during boundary setup')
        if info[7]>1:raise ValueError('Hard-linked object changed during boundary setup')
        return f'{info[4]}:{info[8]}:{info[9]}'

    @staticmethod
    def label(handle):
        import win32security as S
        sd=S.GetSecurityInfo(handle,S.SE_FILE_OBJECT,LABEL_INFO)
        return S.ConvertSecurityDescriptorToStringSecurityDescriptor(sd,1,S.SACL_SECURITY_INFORMATION)

    @staticmethod
    def set_label(handle,text):
        import win32security as S
        sd=S.ConvertStringSecurityDescriptorToSecurityDescriptor(text or 'S:',1)
        S.SetSecurityInfo(handle,S.SE_FILE_OBJECT,LABEL_INFO,None,None,None,sd.GetSecurityDescriptorSacl())

    @staticmethod
    def grant(handle,sid,mask,denied=0,inherit=False):
        import win32security as S
        sd=S.GetSecurityInfo(handle,S.SE_FILE_OBJECT,S.DACL_SECURITY_INFORMATION)
        acl=sd.GetSecurityDescriptorDacl()
        if acl is None:raise ValueError('NULL DACL grant inputs are refused')
        flags=3 if inherit else 0
        # PyACL insertion automatically reallocates and canonicalizes ACE order.
        if denied:acl.AddAccessDeniedAceEx(S.ACL_REVISION_DS,flags,denied,sid)
        acl.AddAccessAllowedAceEx(S.ACL_REVISION_DS,flags,mask,sid)
        S.SetSecurityInfo(handle,S.SE_FILE_OBJECT,S.DACL_SECURITY_INFORMATION,None,None,acl,None)

    @staticmethod
    def revoke(handle,sid):
        import win32security as S
        sd=S.GetSecurityInfo(handle,S.SE_FILE_OBJECT,S.DACL_SECURITY_INFORMATION);acl=sd.GetSecurityDescriptorDacl()
        if acl is None:raise ValueError('Unexpected NULL DACL during cleanup')
        for i in reversed(range(acl.GetAceCount())):
            ace=acl.GetAce(i)
            try:same=bytes(ace[-1])==bytes(sid)
            except (TypeError,ValueError):same=False
            if same:acl.DeleteAce(i)
        S.SetSecurityInfo(handle,S.SE_FILE_OBJECT,S.DACL_SECURITY_INFORMATION,None,None,acl,None)

    def restore(self,record):
        import win32security as S
        sid=S.ConvertStringSidToSid(record['sid']);project=Path(record['project'])
        original={item['identity']:item['label'] for item in record['objects'] if item['project']}
        # Only original approved roots; no walk through junctions created by a child.
        items={item['path']:item['project'] for item in record['objects']}
        if project.exists():
            for directory,dirs,files in os.walk(project,followlinks=False):
                dirs[:]=[name for name in dirs if not (Path(directory)/name).lstat().st_file_attributes&0x400]
                for name in ['']+files:
                    p=Path(directory)/name
                    if p.exists() and not p.lstat().st_file_attributes&0x400:items[str(p)]=True
        for raw,is_project in sorted(items.items(),key=lambda pair:len(Path(pair[0]).parts)):
            p=Path(raw)
            if not p.exists():continue
            # Do not follow replaced directories, including a replaced ancestor.
            unlinked(p)
            with self.handle(p) as h:
                identity=self.identity(h);self.revoke(h,sid)
                if is_project:self.set_label(h,original.get(identity,'S:(ML;;NW;;;ME)'))
        if record.get('loopback'):
            import subprocess
            result=subprocess.run(['CheckNetIsolation.exe','LoopbackExempt','-d','-n='+record['name']],capture_output=True,timeout=15)
            if result.returncode:raise ValueError('Native loopback cleanup failed; recovery record retained')
        status=self.userenv.DeleteAppContainerProfile(record['name'])
        if status<0:raise OSError(status,'Could not remove native boundary profile; recovery journal retained')
        (self.root/(record['name']+'.json')).unlink(missing_ok=True)

    def open(self):
        import psutil,win32security as S
        gate=unlinked(self.root/'gate.lock')
        try:self.lock=WorkspaceLock(gate)
        except ValueError:raise ValueError('Native Windows isolation permits one protected process tree at a time; wait for the current tree to exit') from None
        try:
            for path in self.root.glob('AgentForge.*.json'):
                unlinked(path);old=json.loads(path.read_text());pid=old['owner_pid']
                try:live=psutil.Process(pid).create_time()==old['owner_time']
                except psutil.Error:live=False
                if live:raise ValueError('An older native boundary still owns grants; refusing to alter them')
                self.restore(old)
            grants=[]
            # Non-system CLI runtimes are explicit read-only grants, not whole-home access.
            for raw in self.policy['read_only']:
                p=unlinked(Path(raw).resolve(strict=True))
                if p==Path(p.anchor) or p.is_relative_to(self.project) or self.project.is_relative_to(p):
                    raise ValueError('Native runtime/reference grants must not overlap the writable project or disk roots')
                if self.root.is_relative_to(p):raise ValueError('Native gate/journal must not be readable through a runtime/reference grant')
                if p not in grants:grants.append(p)
            metadata=self.project/'.git'
            if metadata.exists() and not metadata.is_dir():raise ValueError('Native protected projects require in-project Git metadata')
            # Snapshot integrity labels BEFORE any inheritable label changes.
            objects=[]
            for p,is_project in [(p,True) for p in paths(self.project)]+[(p,False) for root in grants for p in paths(root)]:
                with self.handle(p) as h:objects.append({'path':str(p),'project':is_project,'identity':self.identity(h),'label':self.label(h) if is_project else None})
            sid_pointer=C.c_void_p()
            result=self.userenv.CreateAppContainerProfile(self.name,self.name,'Temporary Agent Forge project boundary',None,0,C.byref(sid_pointer))
            if result<0:raise OSError(result,'CreateAppContainerProfile failed; no unrestricted fallback')
            advapi=C.WinDLL('advapi32',use_last_error=True)
            advapi.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(C.c_void_p)];advapi.ConvertSidToStringSidW.restype=W.BOOL
            text_pointer=C.c_void_p()
            try:
                if not advapi.ConvertSidToStringSidW(sid_pointer,C.byref(text_pointer)):raise C.WinError(C.get_last_error())
                self.sid=S.ConvertStringSidToSid(C.wstring_at(text_pointer.value))
            finally:
                if text_pointer.value:C.WinDLL('kernel32').LocalFree(C.c_void_p(text_pointer.value))
                advapi.FreeSid(C.c_void_p(sid_pointer.value))
            self.record={'name':self.name,'sid':S.ConvertSidToStringSid(self.sid),'project':str(self.project),'owner_pid':os.getpid(),'owner_time':psutil.Process().create_time(),'objects':objects}
            self.write_record()
            home_pointer=C.c_void_p();result=self.userenv.GetAppContainerFolderPath(self.record['sid'],C.byref(home_pointer))
            if result<0:raise OSError(result,'GetAppContainerFolderPath failed')
            try:self.home=Path(C.wstring_at(home_pointer.value))/'LocalState';self.home.mkdir(exist_ok=True)
            finally:C.WinDLL('ole32').CoTaskMemFree(C.c_void_p(home_pointer.value))
            for item in objects:
                p=Path(item['path']);is_project=item['project'];control=is_project and self.protect_git and (p==metadata or p.is_relative_to(metadata))
                with self.handle(p) as h:
                    if self.identity(h)!=item['identity']:raise ValueError('Grant object changed during native setup')
                    self.grant(h,self.sid,READ if control or not is_project else MODIFY,
                               WRITE_DENY if control or not is_project else 0xC0000,inherit=is_project and p.is_dir())
                    if is_project:self.set_label(h,'S:(ML;OICI;NW;;;LW)' if p.is_dir() else 'S:(ML;;NW;;;LW)')
            if self.policy['network']:
                # AppContainer loopback access requires an administrator-approved OS rule.
                # No automatic elevation, global firewall disabling or silent allowance.
                import subprocess
                self.record['loopback']=True;self.write_record()
                r=subprocess.run(['CheckNetIsolation.exe','LoopbackExempt','-a','-n='+self.name],capture_output=True,timeout=15)
                if r.returncode:raise ValueError('Approved native loopback rule could not be installed; use an administrator-approved setup, not unrestricted fallback')
                self.record['loopback']=True;self.write_record()
            return self
        except BaseException:
            self.close();raise

    def close(self):
        try:
            if self.record:
                self.restore(self.record);self.record=None
        finally:
            if self.lock:self.lock.close();self.lock=None


class COORD(C.Structure):_fields_=[('X',C.c_short),('Y',C.c_short)]
class SI(C.Structure):
    _fields_=[('cb',W.DWORD),('lpReserved',W.LPWSTR),('lpDesktop',W.LPWSTR),('lpTitle',W.LPWSTR),*[(n,W.DWORD) for n in ('dwX','dwY','dwXSize','dwYSize','dwXCountChars','dwYCountChars','dwFillAttribute','dwFlags')],('wShowWindow',W.WORD),('cbReserved2',W.WORD),('lpReserved2',C.c_void_p),('hStdInput',W.HANDLE),('hStdOutput',W.HANDLE),('hStdError',W.HANDLE)]
class SIEX(C.Structure):_fields_=[('StartupInfo',SI),('lpAttributeList',C.c_void_p)]
class PI(C.Structure):_fields_=[('hProcess',W.HANDLE),('hThread',W.HANDLE),('dwProcessId',W.DWORD),('dwThreadId',W.DWORD)]
class SID_ATTRIBUTES(C.Structure):_fields_=[('Sid',C.c_void_p),('Attributes',W.DWORD)]
class CAPS(C.Structure):_fields_=[('AppContainerSid',C.c_void_p),('Capabilities',C.POINTER(SID_ATTRIBUTES)),('CapabilityCount',W.DWORD),('Reserved',W.DWORD)]


class NativeProcess:
    def __init__(self,argv,cwd,env,boundary,*,pty=False,rows=24,cols=90):
        import subprocess,win32security as S
        self.k=C.WinDLL('kernel32',use_last_error=True);self.handles=[];self.pseudo=None;self.process=None;self.job=None;self.decoder=codecs.getincrementaldecoder('utf-8')('replace');self.closed=False;self.final_code=None
        k=self.k
        prototypes={
            'CreatePipe':([C.POINTER(W.HANDLE),C.POINTER(W.HANDLE),C.c_void_p,W.DWORD],W.BOOL),
            'CloseHandle':([W.HANDLE],W.BOOL),'SetHandleInformation':([W.HANDLE,W.DWORD,W.DWORD],W.BOOL),
            'InitializeProcThreadAttributeList':([C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
            'UpdateProcThreadAttribute':([C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
            'DeleteProcThreadAttributeList':([C.c_void_p],None),
            'CreateProcessW':([W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.c_void_p,C.POINTER(PI)],W.BOOL),
            'TerminateProcess':([W.HANDLE,W.UINT],W.BOOL),
            'ResumeThread':([W.HANDLE],W.DWORD),'WaitForSingleObject':([W.HANDLE,W.DWORD],W.DWORD),
            'GetExitCodeProcess':([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
            'ReadFile':([W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p],W.BOOL),
            'WriteFile':([W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p],W.BOOL),
            'TerminateJobObject':([W.HANDLE,W.UINT],W.BOOL),
            'QueryInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL),
            'CreatePseudoConsole':([COORD,W.HANDLE,W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)],C.c_long),
            'ResizePseudoConsole':([W.HANDLE,COORD],C.c_long),'ClosePseudoConsole':([W.HANDLE],None),
        }
        for name,(args,restype) in prototypes.items():getattr(k,name).argtypes=args;getattr(k,name).restype=restype
        def pipe():
            r=W.HANDLE();w=W.HANDLE()
            if not k.CreatePipe(C.byref(r),C.byref(w),None,0):raise C.WinError(C.get_last_error())
            self.handles.extend([r.value,w.value]);return r.value,w.value
        child_input,self.input=pipe();self.output,child_output=pipe();self.error=None
        si=SIEX();si.StartupInfo.cb=C.sizeof(si);attrs=3 if pty else 3
        size=C.c_size_t();k.InitializeProcThreadAttributeList(None,attrs,0,C.byref(size));buffer=C.create_string_buffer(size.value);si.lpAttributeList=C.cast(buffer,C.c_void_p)
        if not k.InitializeProcThreadAttributeList(si.lpAttributeList,attrs,0,C.byref(size)):raise C.WinError(C.get_last_error())
        def attribute(number,value):
            if not k.UpdateProcThreadAttribute(si.lpAttributeList,0,number,C.byref(value),C.sizeof(value),None,None):raise OSError(C.get_last_error(),f'Native process attribute {number:#x} failed')
        sidbuf=C.create_string_buffer(bytes(boundary.sid));caps=CAPS(C.cast(sidbuf,C.c_void_p),None,0,0);cap_sid_buffers=[]
        if boundary.policy['network']:
            cap_sid_buffers=[C.create_string_buffer(bytes(S.ConvertStringSidToSid(sid))) for sid in ('S-1-15-3-1','S-1-15-3-3')]
            cap_array=(SID_ATTRIBUTES*2)(*[SID_ATTRIBUTES(C.cast(buf,C.c_void_p),4) for buf in cap_sid_buffers]);caps.Capabilities=cap_array;caps.CapabilityCount=2
        try:
            attribute(0x20009,caps);attribute(0x2000F,W.DWORD(1)) # LPAC: opt out of ALL APPLICATION PACKAGES.
            if pty:
                pseudo=W.HANDLE();result=k.CreatePseudoConsole(COORD(cols,rows),child_input,child_output,0,C.byref(pseudo))
                if result<0:raise OSError(result,'CreatePseudoConsole failed')
                self.pseudo=pseudo.value
                # HPCON value is passed directly, NOT a pointer to the handle.
                if not k.UpdateProcThreadAttribute(si.lpAttributeList,0,0x20016,C.c_void_p(self.pseudo),C.sizeof(W.HANDLE),None,None):raise OSError(C.get_last_error(),'Native pseudo-console attribute failed')
                inherit=False
            else:
                self.error,child_error=pipe();si.StartupInfo.dwFlags=0x100;si.StartupInfo.hStdInput=child_input;si.StartupInfo.hStdOutput=child_output;si.StartupInfo.hStdError=child_error
                inherited=(W.HANDLE*3)(child_input,child_output,child_error)
                for h in inherited:
                    if not k.SetHandleInformation(h,1,1):raise C.WinError(C.get_last_error())
                attribute(0x20002,inherited);inherit=True
            env=dict(env);env.pop(SPEC,None);env.pop('FORGE_WINDOWS_ISOLATION_EXPERIMENTAL',None);env.pop('FORGE_CONFIG_HOME',None);env.update(HOME=str(boundary.home),USERPROFILE=str(boundary.home),LOCALAPPDATA=str(boundary.home),APPDATA=str(boundary.home),TEMP=str(boundary.home),TMP=str(boundary.home))
            environment=C.create_unicode_buffer('\0'.join(f'{key}={value}' for key,value in sorted(env.items()))+'\0\0')
            command=C.create_unicode_buffer(subprocess.list2cmdline(argv));pi=PI()
            executable=shutil.which(argv[0],path=env.get('PATH','')) or argv[0]
            if not k.CreateProcessW(executable,command,None,None,inherit,0x80000|0x400|0x4,environment,str(cwd),C.byref(si),C.byref(pi)):raise OSError(C.get_last_error(),'CreateProcessW under native LPAC failed')
            self.process=pi.hProcess;self.pid=pi.dwProcessId;self.handles.extend([pi.hProcess,pi.hThread])
            from .windows_broker import job_for
            _,self.job=job_for(self.pid)
            if k.ResumeThread(pi.hThread)==0xFFFFFFFF:raise C.WinError(C.get_last_error())
            for h in (child_input,child_output,*([] if pty else [child_error])):
                k.CloseHandle(h);self.handles.remove(h)
        except BaseException:
            self.close();raise
        finally:k.DeleteProcThreadAttributeList(si.lpAttributeList)

    def read_bytes(self,handle,count=4096):
        buffer=C.create_string_buffer(count);done=W.DWORD()
        if not self.k.ReadFile(handle,buffer,count,C.byref(done),None):raise EOFError
        if not done.value:raise EOFError
        return buffer.raw[:done.value]
    def read(self,count=4096):return self.decoder.decode(self.read_bytes(self.output,count))
    def write(self,text):self.write_bytes(text.encode('utf-8'))
    def write_bytes(self,data):
        while data:
            done=W.DWORD()
            if not self.k.WriteFile(self.input,data,len(data),C.byref(done),None):raise OSError('Native input pipe closed')
            data=data[done.value:]
    def isalive(self):return not self.closed and self.k.WaitForSingleObject(self.process,0)==258
    @property
    def exitstatus(self):
        if self.final_code is not None:return self.final_code
        code=W.DWORD();self.k.GetExitCodeProcess(self.process,C.byref(code));return None if code.value==259 else code.value
    def setwinsize(self,rows,cols):
        if self.pseudo and self.k.ResizePseudoConsole(self.pseudo,COORD(cols,rows))<0:raise OSError('Native console resize failed')
    def close(self):
        if self.closed:return
        if self.job:
            self.k.TerminateJobObject(self.job,125)
            class Accounting(C.Structure):
                _fields_=[(name,C.c_longlong) for name in ('TotalUserTime','TotalKernelTime','ThisPeriodTotalUserTime','ThisPeriodTotalKernelTime')]+[(name,W.DWORD) for name in ('TotalPageFaultCount','TotalProcesses','ActiveProcesses','TotalTerminatedProcesses')]
            info=Accounting();end=time.monotonic()+5
            while True:
                if not self.k.QueryInformationJobObject(self.job,1,C.byref(info),C.sizeof(info),None):raise C.WinError(C.get_last_error())
                if info.ActiveProcesses==0:break
                if time.monotonic()>end:raise OSError('Native process tree still alive; grants must not be restored')
                time.sleep(.03)
            self.k.CloseHandle(self.job);self.job=None
        if self.process and self.isalive():
            self.k.TerminateProcess(self.process,125);self.k.WaitForSingleObject(self.process,5000)
        if self.process:self.final_code=self.exitstatus
        self.closed=True
        if self.pseudo:
            # Reader must drain concurrently; closing ConPTY can otherwise wait forever.
            pseudo=self.pseudo;self.pseudo=None
            thread=threading.Thread(target=lambda:self.k.ClosePseudoConsole(pseudo),daemon=True);thread.start();thread.join(2)
        for h in self.handles:self.k.CloseHandle(h)
        self.handles=[]


def main():
    from .platform_support import windows_command
    spec=json.loads(os.environ[SPEC]);argv,env=windows_command(sys.argv[1:],dict(os.environ));boundary=None;child=None;exit_code=125
    phase='grant setup'
    try:
        boundary=Boundary(spec['project'],spec['policy'],spec['protect_git']).open()
        phase='process creation'
        child=NativeProcess(argv,Path.cwd(),env,boundary)
        def output(handle,target):
            try:
                while True:os.write(target,child.read_bytes(handle))
            except (EOFError,OSError):pass
        def input():
            try:
                while data:=os.read(sys.stdin.fileno(),4096):child.write_bytes(data)
            except OSError:pass
        threads=[threading.Thread(target=output,args=(child.output,sys.stdout.fileno()),daemon=True),threading.Thread(target=output,args=(child.error,sys.stderr.fileno()),daemon=True)]
        for t in threads:t.start()
        threading.Thread(target=input,daemon=True).start()
        while child.isalive():time.sleep(.03)
        exit_code=child.exitstatus
        for t in threads:t.join(2)
    except BaseException as error:
        message=f'Native boundary failed during {phase}: {type(error).__name__}, OS code {getattr(error, "winerror", getattr(error, "errno", None))}, detail {str(error)[:250]}; no unrestricted fallback.\n'
        os.write(sys.stderr.fileno(),message.encode('utf-8'))
    finally:
        if child:child.close()
        try:
            if boundary:boundary.close()
        except BaseException:
            os.write(sys.stderr.fileno(),b'Native boundary cleanup failed; recovery record retained.\n');exit_code=125
        os._exit(exit_code & 255)

if __name__=='__main__':main()
