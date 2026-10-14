"""Secret-free, read-only readiness checks. No provider authentication or installs."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

CORE_MODULES=('textual','pyte','psutil')
OPTIONAL_MODULES=('mcp','jsonschema','keyring','faster_whisper','sounddevice')
HARNESS_COMMANDS=('claude','codex','gemini','kimi','opencode','aider','ollama','git','node')


def module_available(name):
    try:return importlib.util.find_spec(name) is not None
    except (ImportError,ValueError,AttributeError):return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Readiness probes never follow redirects')


def probe_ollama(endpoint='http://127.0.0.1:11434',*,timeout=2):
    """Only a direct loopback HTTP probe, without proxies, credentials or redirects."""
    parsed=urllib.parse.urlsplit(endpoint)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','::1','localhost') or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('Readiness probes require a credential-free loopback endpoint')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def read(path):
        request=urllib.request.Request(endpoint.rstrip('/')+path,headers={'Accept':'application/json'})
        with opener.open(request,timeout=timeout) as response:
            raw=response.read(65537)
        if len(raw)>65536:raise ValueError('Readiness response exceeds its limit')
        value=json.loads(raw)
        if not isinstance(value,dict):raise ValueError('Invalid readiness response')
        return value
    try:
        version=read('/api/version');tags=read('/api/tags')
        models=tags.get('models')
        if not isinstance(version.get('version'),str) or not isinstance(models,list) or any(not isinstance(m,dict) or not isinstance(m.get('name'),str) for m in models):
            raise ValueError('Invalid Ollama response')
        # Do not publish custom model names, URLs or arbitrary server text.
        return {'status':'reachable','installed_model_count':len(models),'authentication':'not-required-for-local-use','generation_tested':False}
    except (OSError,ValueError,urllib.error.URLError):
        return {'status':'unavailable','installed_model_count':None,'action':'Start local Ollama and retry; no provider login is needed.'}


def probe_linux_isolation():
    executable=shutil.which('bwrap')
    if not executable:return {'status':'unavailable','action':'Install Bubblewrap; no unrestricted fallback is used.'}
    argv=[executable,'--unshare-all','--unshare-user','--cap-drop','ALL','--new-session','--die-with-parent']
    for raw in ('/usr','/bin','/sbin','/lib','/lib64'):
        p=Path(raw)
        if p.exists():argv+=['--symlink',os.readlink(p),raw] if p.is_symlink() else ['--ro-bind',raw,raw]
    argv+=['--dev','/dev','--tmpfs','/tmp','--','/usr/bin/true']
    try:
        result=subprocess.run(argv,env={'PATH':'/usr/bin:/bin'},stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        return {'status':'passed' if result.returncode==0 else 'blocked','project_permissions_tested':False,'action':'Review project permissions before launching agents.' if result.returncode==0 else 'Host policy or capabilities blocked isolation; use a compatible host. Do not disable host protections.'}
    except (OSError,subprocess.TimeoutExpired):
        return {'status':'blocked','project_permissions_tested':False,'action':'Isolation startup failed or timed out; no unrestricted fallback is used.'}


def diagnose(project,*,ollama=False,isolation=False):
    """Report capabilities, not model quality, billing or untested security claims."""
    path=Path(project).expanduser()
    exists=path.is_dir()
    modules={name:module_available(name) for name in (*CORE_MODULES,*OPTIONAL_MODULES)}
    terminal_module='winpty' if os.name=='nt' else 'ptyprocess'
    modules[terminal_module]=module_available(terminal_module)
    tools={name:bool(shutil.which(name)) for name in HARNESS_COMMANDS}
    core=exists and sys.version_info>=(3,11) and all(modules[m] for m in (*CORE_MODULES,terminal_module))
    if sys.platform.startswith('linux'):
        boundary=probe_linux_isolation() if isolation else {'status':'installed-not-runtime-tested' if shutil.which('bwrap') else 'unavailable','action':'Use --probe-isolation to check kernel startup, then review project permissions.'}
        boundary['backend']='bubblewrap'
    elif os.name=='nt':
        boundary={'backend':'native-windows-lpac','status':'experimental-not-release-ready','action':'Native console and permission-restoration acceptance gates remain unresolved. Enforced mode is disabled by default.'}
    else:
        boundary={'backend':None,'status':'unsupported','action':'Enforced filesystem isolation is unavailable on this platform.'}
    local=probe_ollama() if ollama else {'status':'not-probed','installed_model_count':None,'action':'Use --probe-ollama for a local-only service check.'}
    local_ready=tools['ollama'] and local['status']=='reachable' and local['installed_model_count']>0
    return {
        'schema_version':1,
        'platform':'windows' if os.name=='nt' else 'linux' if sys.platform.startswith('linux') else sys.platform,
        'python_supported':sys.version_info>=(3,11),
        'project_exists':exists,
        'modules':modules,
        'executables':tools,
        'ollama':local,
        'isolation':boundary,
        'ready_for':{'core':bool(core),'local':bool(core and local_ready),'local_coding':bool(core and local_ready and tools['aider']),'isolation':bool(core and boundary['status']=='passed')},
        'requirements':{'consumer_pro_subscription':False,'local_provider_account':False,'cloud_models':'Compatible provider key and provider-required billing/access; not every API format is supported.','voice':'Optional local model plus OS microphone permission; no provider account required.','credential_vault':'Optional for session keys; Codex native key-auth retains its documented vault requirement.'},
        'limits':['Readiness checks do not generate text, authenticate cloud providers, certify upstream Ruflo backends, or approve project access.','Ruflo requires the pinned runtime and MCP dependencies; tool discovery and every call remain permission/review gated.','Availability is not an end-to-end coding-quality or security certification.'],
    }
