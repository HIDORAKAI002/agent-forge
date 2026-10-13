"""Pinned optional Ruflo MCP: derived memory index + advisory routing, not execution authority."""
import asyncio,hashlib,json,os,queue,shutil,subprocess,threading
from pathlib import Path
from .store import managed
from .settings import Preferences
VERSION='3.56.9'
TOOLS={'memory_store','memory_search','memory_retrieve','memory_stats','hooks_model-route'}

def safe_environment(home):
    env={k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','LANG','LC_ALL','TMP','TEMP','APPDATA','LOCALAPPDATA')}
    env.update(HOME=str(home),USERPROFILE=str(home),XDG_CONFIG_HOME=str(home/'config'),XDG_CACHE_HOME=str(home/'cache'),RUFLO_AUTO_UPDATE='false',CLAUDE_FLOW_AUTO_UPDATE='false',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
    return env

def decode_result(result):
    if result.isError:raise ValueError('Ruflo tool returned an error')
    if result.structuredContent is not None:return result.structuredContent
    for item in result.content:
        if getattr(item,'type',None)=='text':
            if len(item.text)>1_000_000:raise ValueError('Ruflo result exceeds limit')
            value=json.loads(item.text)
            if isinstance(value,dict) and (value.get('success') is False or value.get('error')):raise ValueError('Ruflo operation failed; Forge state is unchanged')
            return value
    raise ValueError('Ruflo returned no structured result')

class RufloBridge:
    def __init__(self,store):
        self.store=store;self.enabled=False;self.connected=False;self.state='OFF / optional pinned Ruflo integration';self.jobs=queue.Queue(maxsize=10);self.events=queue.Queue();self.closing=False;self.loop=None;self.task=None;self.worker=None;self.indexed={};self.busy=False
        self.root=Preferences().root/'ruflo-state'/hashlib.sha256(str(store.project.resolve()).encode()).hexdigest();self.command=os.environ.get('FORGE_RUFLO_BIN') or shutil.which('ruflo')
    def enable(self):
        if self.enabled:return
        if not self.command:raise ValueError(f'Install Node.js 20+ and npm install -g ruflo@{VERSION} first')
        if self.root.resolve().is_relative_to(self.store.project.resolve()):raise ValueError('Ruflo host state must be outside the writable project')
        for path in (self.root.parent,self.root):
            if path.is_symlink():raise ValueError('Refusing linked Ruflo host state')
            path.mkdir(mode=0o700,exist_ok=True)
        home=managed(self.root,'home');home.mkdir(exist_ok=True)
        env=safe_environment(home)
        from .platform_support import windows_command
        argv=[self.command,'--version']
        if os.name=='nt':argv,env=windows_command(argv,env)
        version=subprocess.run(argv,env=env,cwd=self.root,capture_output=True,text=True,timeout=15)
        if version.returncode or f'v{VERSION}' not in version.stdout:raise ValueError(f'Ruflo version must be {VERSION}; unreviewed versions are refused')
        self.closing=False;self.enabled=True;self.state='Connecting to pinned Ruflo MCP';self.worker=threading.Thread(target=lambda:asyncio.run(self._run()),daemon=True);self.worker.start()
    def request(self,kind,goal=''):
        if not self.connected:raise ValueError('Ruflo is not connected; enable it and wait for Ready')
        if self.busy:raise ValueError('Ruflo operation is already running')
        if kind not in ('sync','search','context'):raise ValueError('Unsupported Ruflo operation')
        if kind!='sync' and (not isinstance(goal,str) or not goal.strip() or len(goal)>4000):raise ValueError('Ruflo query/goal must be 1–4000 characters')
        self.busy=True;self.jobs.put_nowait((kind,goal,self.store.memories(limit=500)));self.state='Ruflo '+kind+' running'
    async def _run(self):
        self.loop=asyncio.get_running_loop();self.task=asyncio.current_task()
        try:
            from mcp import ClientSession,StdioServerParameters
            from mcp.client.stdio import stdio_client
            env=safe_environment(self.root/'home');argv=[self.command,'mcp','start','--transport','stdio','--tools',','.join(sorted(TOOLS))]
            if os.name=='nt':
                from .platform_support import windows_command
                argv,env=windows_command(argv,env)
            parameters=StdioServerParameters(command=argv[0],args=argv[1:],env=env,cwd=str(self.root))
            # Suppress upstream diagnostic text: it is not a trusted instruction stream.
            with open(os.devnull,'w') as err:
                async with stdio_client(parameters,errlog=err) as streams:
                    async with ClientSession(*streams) as session:
                        await asyncio.wait_for(session.initialize(),45)
                        available={t.name for t in (await asyncio.wait_for(session.list_tools(),30)).tools}
                        if not TOOLS.issubset(available):raise ValueError('Required audited Ruflo tools are missing')
                        self.connected=True;self.state=f'Ready / Ruflo {VERSION}; memory index + advisory routing';self.events.put(('ready',{}))
                        async def call(name,args):
                            if name not in TOOLS:raise ValueError('Ruflo tool is not allowlisted')
                            return decode_result(await asyncio.wait_for(session.call_tool(name,args),60))
                        while not self.closing:
                            try:kind,goal,memories=self.jobs.get_nowait()
                            except queue.Empty:await asyncio.sleep(.1);continue
                            try:
                                for memory in memories:
                                    value=json.dumps(memory,sort_keys=True);digest=hashlib.sha256(value.encode()).hexdigest()
                                    if self.indexed.get(memory['id'])!=digest:
                                        await call('memory_store',{'key':'forge-'+memory['id'],'value':memory['text'],'namespace':'forge','tags':[memory['kind'],memory['author']],'provenance_type':'user_claim' if memory['verified'] else 'agent_output','upsert':True});self.indexed[memory['id']]=digest
                                data={'goal':goal,'indexed':len(memories)}
                                if kind!='sync':
                                    result=await call('memory_search',{'query':goal,'namespace':'forge','limit':20,'threshold':0,'smart':True})
                                    # Rehydrate ONLY current canonical rows. Never trust indexed content/verification flags.
                                    canonical={m['id']:m for m in self.store.memories(limit=500)}
                                    keys=[r.get('key','')[6:] for r in result.get('results',[]) if isinstance(r,dict) and isinstance(r.get('key'),str) and r['key'].startswith('forge-')]
                                    data['memories']=[canonical[k] for k in dict.fromkeys(keys) if k in canonical]
                                    data['retrieval_backend']=result.get('backend','not reported')
                                if kind=='context':data['route_hint']=await call('hooks_model-route',{'task':goal,'preferCost':True})
                                self.events.put((kind,data));self.state=f'Ready / indexed {len(memories)} canonical memories'
                            except Exception:
                                self.events.put(('error',{'message':'Ruflo operation failed or timed out; no task was dispatched'}));self.state='Operation failed; no dispatch'
                            finally:self.busy=False
        except asyncio.CancelledError:pass
        except BaseException:
            if not self.closing:self.events.put(('error',{'message':'Ruflo MCP connection failed; inspect the pinned installation'}));self.state='Disconnected / no silent fallback'
        finally:self.connected=False;self.enabled=False;self.busy=False
    def poll(self):
        out=[]
        while not self.events.empty():out.append(self.events.get_nowait())
        return out
    def close(self):
        self.closing=True
        if self.loop and self.task and self.loop.is_running():
            try:self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:pass
        if self.worker and threading.current_thread()!=self.worker:self.worker.join(timeout=3)
        self.state='OFF / Ruflo disconnected'
