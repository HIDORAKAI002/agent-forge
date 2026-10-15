"""Native ACL API experiment on disposable folders; never user data.

Only ACE flags/control bits and generic errors are reported, not paths/SIDs.
"""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import tempfile


def main():
    import win32security as S
    from forge.windows_isolation import Boundary,LABEL_INFO,READ
    fake=S.ConvertStringSidToSid('S-1-15-2-234123-912345-817263-92341-551231-99341-98721')
    def view(path):
        sd=S.GetNamedSecurityInfo(str(path),S.SE_FILE_OBJECT,S.DACL_SECURITY_INFORMATION|LABEL_INFO)
        acl=sd.GetSecurityDescriptorDacl()
        return sd,[acl.GetAce(i) for i in range(acl.GetAceCount())]
    results={}
    with tempfile.TemporaryDirectory(prefix='forge-acl-api-check-') as temporary:
        for method in ('noop','kernel','file','nt','grant-kernel','grant-file','grant-nt','label-kernel','combined-kernel','combined-file','combined-nt'):
            p=Path(temporary)/method;p.mkdir();original,entries=view(p)
            try:
                with Boundary.handle(p) as handle:
                    if 'grant' in method or 'combined' in method:Boundary.grant(handle,fake,READ,inherit=True)
                    if 'label' in method or 'combined' in method:Boundary.set_label(handle,'S:(ML;OICI;NW;;;LW)')
                    if method!='noop':
                        if 'label' in method or 'combined' in method:
                            label=S.ConvertSecurityDescriptorToStringSecurityDescriptor(original,1,S.SACL_SECURITY_INFORMATION)
                            Boundary.set_label(handle,label)
                        if method.endswith('file'):S.SetFileSecurity(str(p),S.DACL_SECURITY_INFORMATION,original)
                        elif method.endswith('nt'):
                            native=C.WinDLL('ntdll');native.NtSetSecurityObject.argtypes=[W.HANDLE,W.DWORD,C.c_void_p];native.NtSetSecurityObject.restype=C.c_long
                            raw=C.create_string_buffer(bytes(original));status=native.NtSetSecurityObject(int(handle),S.DACL_SECURITY_INFORMATION,raw)
                            if status<0:raise OSError(status,'Native security restore failed')
                        else:S.SetKernelObjectSecurity(handle,S.DACL_SECURITY_INFORMATION,original)
                after,actual=view(p)
                results[method]={'exact':entries==actual,'before_flags':[a[0][1] for a in entries],'after_flags':[a[0][1] for a in actual],'before_control':original.GetSecurityDescriptorControl()[0],'after_control':after.GetSecurityDescriptorControl()[0]}
            except Exception as error:results[method]={'error':type(error).__name__,'code':getattr(error,'winerror',getattr(error,'errno',None))}
    Path('windows-security-probe.json').write_text(json.dumps(results,indent=2)+'\n')
    print('Completed disposable native ACL API probe; not production acceptance.')


if __name__=='__main__':main()
