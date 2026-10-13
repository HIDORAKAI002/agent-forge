"""Provider-scoped credentials: OS vault or memory, never project JSON/logs.

Do not call repr() on secrets or include them in shell arguments. Native CLIs
remain trusted processes and retain their own authentication policies.
"""
from __future__ import annotations
import os
import threading
import subprocess
import queue
import shutil

PROVIDERS = {
    'claude': ('Anthropic / Claude Code', 'ANTHROPIC_API_KEY'),
    'codex': ('OpenAI / Codex', 'OPENAI_API_KEY'),
    'gemini': ('Google / Gemini CLI', 'GEMINI_API_KEY'),
}
INSTALL_COMMANDS={
    'claude':'curl -fsSL https://claude.ai/install.sh | bash',
    'codex':'npm install -g @openai/codex',
    'gemini':'npm install -g @google/gemini-cli',
}
if os.name=='nt':INSTALL_COMMANDS['claude']='irm https://claude.ai/install.ps1 | iex'
SERVICE='agent-forge.provider-keys'
ALLOWED_VAULTS=('keyring.backends.macOS','keyring.backends.Windows','keyring.backends.SecretService','keyring.backends.kwallet')

class Credentials:
    def __init__(self, backend=None):
        self.memory={};self.lock=threading.RLock();self.events=queue.Queue();self.busy=False;self.closed=False
        self.backend=backend
        if backend is None:
            try:
                import keyring
                candidate=keyring.get_keyring()
                candidates=getattr(candidate,'backends',[candidate])
                self.backend=next((b for b in candidates if type(b).__module__.startswith(ALLOWED_VAULTS) and b.priority>0),None)
            except Exception:
                self.backend=None
        self.storage_label='OS credential store available' if self.backend else 'Session-only storage; no supported OS vault detected'

    def _check(self, provider):
        if provider not in PROVIDERS: raise ValueError('Supported key setup: Claude, Codex or Gemini. Other CLIs use native login.')

    def get(self, provider):
        self._check(provider)
        with self.lock:
            if provider in self.memory: return self.memory[provider]
        if self.backend:
            try: return self.backend.get_password(SERVICE,provider)
            except Exception: raise ValueError('OS credential store is unavailable or locked; use session-only storage') from None
        return None

    def save(self, provider, value, persistent=False):
        self._check(provider)
        if not isinstance(value,str) or not value.strip() or len(value)>4096 or any(ord(c)<33 for c in value):
            raise ValueError('Enter a nonempty API key without whitespace or control characters')
        if persistent:
            if not self.backend: raise ValueError('No supported OS vault; choose session-only storage')
            try: self.backend.set_password(SERVICE,provider,value)
            except Exception: raise ValueError('OS vault could not save the key; no plaintext fallback was used') from None
        with self.lock: self.memory[provider]=value

    def remove(self, provider):
        self._check(provider)
        if self.backend:
            try:
                if self.backend.get_password(SERVICE,provider): self.backend.delete_password(SERVICE,provider)
            except Exception: raise ValueError('Could not remove the OS-vault key; unlock the vault and retry') from None
        with self.lock: self.memory.pop(provider,None)

    def environment(self, engine):
        if engine not in PROVIDERS: return {}
        value=self.get(engine)
        return {PROVIDERS[engine][1]:value} if value else {}

    def save_async(self,provider,value,persistent):
        if self.busy: raise ValueError('Credential operation in progress')
        self.busy=True
        def worker():
            try:
                self.save(provider,value,persistent)
                result='Key saved to OS vault' if persistent else 'Key saved for this session only'
            except Exception as error: result=str(error)
            if not self.closed: self.events.put(result)
            self.busy=False
        threading.Thread(target=worker,daemon=True,name='forge-credentials').start()

    def codex_login(self):
        """Feed key via an un-echoed pipe, not a PTY or command-line argument.
        Force Codex's own credential-store setting to keyring; no auth.json fallback.
        """
        if self.busy: raise ValueError('Credential operation in progress')
        key=self.get('codex')
        if not key: raise ValueError('Save an OpenAI key first')
        if not self.backend: raise ValueError('Codex API-key login requires an available OS vault here; otherwise use native codex login')
        if not shutil.which('codex'): raise ValueError('Install Codex before authenticating')
        self.busy=True
        def worker():
            try:
                argv=['codex','-c','cli_auth_credentials_store="keyring"','login','--with-api-key']
                kwargs={}
                if os.name=='nt':
                    from .platform_support import windows_command
                    argv,env=windows_command(argv,dict(os.environ));kwargs['env']=env
                result=subprocess.run(argv,input=key+'\n',text=True,capture_output=True,timeout=40,**kwargs)
                message='Codex CLI authentication completed' if result.returncode==0 else 'Codex authentication failed; inspect native CLI setup (provider output suppressed to protect credentials)'
            except Exception: message='Codex authentication could not complete; check CLI version and OS vault'
            if not self.closed:self.events.put(message)
            self.busy=False
        threading.Thread(target=worker,daemon=True,name='forge-codex-auth').start()

    def close(self):
        self.closed=True
        with self.lock:self.memory.clear()
