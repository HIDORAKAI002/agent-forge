"""Explicit access to the pinned upstream MCP catalog, never an execution authority.

Unlike the small trusted-host memory bridge, every broad-catalog MCP server runs
inside the reviewed project sandbox. No provider secrets or host HOME are passed.
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from .ruflo import VERSION, safe_environment
from .sandbox import Sandbox
from .settings import Preferences

MAX_REQUEST_BYTES = 100_000
MAX_RESULT_BYTES = 1_000_000
MAX_REQUESTS = 20


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def validate_requests(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_REQUESTS:
        raise ValueError('Provide 1–20 explicit Ruflo requests in a JSON array')
    if len(canonical(value).encode()) > MAX_REQUEST_BYTES:
        raise ValueError('Ruflo request batch exceeds 100 KB')
    for item in value:
        if not isinstance(item, dict) or set(item) != {'tool', 'arguments'}:
            raise ValueError('Each request must contain exactly tool and arguments')
        if not isinstance(item['tool'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}', item['tool']):
            raise ValueError('Invalid upstream tool name')
        if not isinstance(item['arguments'], dict):
            raise ValueError('Tool arguments must be an object')
    return json.loads(canonical(value))  # Own immutable-by-caller snapshot.


def validate_arguments(schema, arguments):
    # Never retrieve network schemas while validating an upstream tool definition.
    def local_only(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('$ref', '$dynamicRef', '$recursiveRef') and (not isinstance(child, str) or not child.startswith('#')):
                    raise ValueError('External JSON Schema references are not supported')
                local_only(child)
        elif isinstance(value, list):
            for child in value: local_only(child)
    local_only(schema)
    from jsonschema.validators import validator_for
    validator = validator_for(schema)
    validator.check_schema(schema)
    try: validator(schema).validate(arguments)
    except Exception:
        # Validation errors can interpolate argument values (possibly secrets).
        raise ValueError('Arguments do not match the advertised upstream schema') from None


def review_digest(project, policy, catalog, requests):
    snapshot = {'version': VERSION, 'project': str(Path(project).resolve()),
                'policy': policy, 'requests': requests,
                'schemas': {r['tool']: catalog[r['tool']] for r in requests}}
    return hashlib.sha256(canonical(snapshot).encode()).hexdigest()


def bounded_result(result):
    value = result.model_dump(mode='json', exclude_none=True)
    if len(canonical(value).encode()) > MAX_RESULT_BYTES:
        raise ValueError('Upstream result exceeds 1 MB; result suppressed')
    return value


class RufloToolSession:
    """One sandboxed server; stateful tools share this server for the whole batch."""
    def __init__(self, project, *, command=None):
        self.sandbox = Sandbox(project)
        self.project = self.sandbox.project
        self.command = command or os.environ.get('FORGE_RUFLO_BIN') or shutil.which('ruflo')
        self.catalog = {}
        self.session = None
        self.policy = None
        self.audit_root = Preferences().root / 'ruflo-reviews'

    def launch_spec(self):
        if not self.sandbox.policy['enabled']:
            raise ValueError('Broad Ruflo tools require enforced project isolation; no host-side fallback')
        if not self.command:
            raise ValueError(f'Install pinned ruflo@{VERSION} first')
        if self.audit_root.resolve().is_relative_to(self.project):
            raise ValueError('Ruflo review records must stay outside the writable project')
        env = safe_environment(Path('/tmp/forge-home') if os.name != 'nt' else self.audit_root / 'home', self.project)
        resolved = shutil.which(self.command, path=env.get('PATH', ''))
        if not resolved or Path(resolved).resolve().is_relative_to(self.project):
            raise ValueError('Ruflo runtime must be installed outside the writable project')
        argv = [str(Path(resolved).resolve()), 'mcp', 'start', '--transport', 'stdio']
        if os.name == 'nt':
            from .platform_support import windows_command
            argv, env = windows_command(argv, env)
        if any(Path(p).is_absolute() and Path(p).resolve().is_relative_to(self.project) for p in argv[:2]):
            raise ValueError('Ruflo runtime entrypoint overlaps writable project')
        # Use the SAME boundary for version detection; a version command is code too.
        version_argv, version_env = self.sandbox.wrap([argv[0], *argv[1:2], '--version'] if os.name == 'nt' else [argv[0], '--version'], self.project, env)
        checked = subprocess.run(version_argv, cwd=self.project, env=version_env,
                                 capture_output=True, text=True, timeout=30)
        if checked.returncode or not re.search(rf'\bv{re.escape(VERSION)}\b', checked.stdout):
            raise ValueError('Pinned Ruflo runtime cannot execute inside the boundary; review its read-only runtime grants')
        self.policy = json.loads(canonical(self.sandbox.policy))
        return self.sandbox.wrap(argv, self.project, env)

    @asynccontextmanager
    async def connect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        argv, env = self.launch_spec()
        parameters = StdioServerParameters(command=argv[0], args=argv[1:], env=env, cwd=str(self.project))
        with open(os.devnull, 'w') as err:
            async with stdio_client(parameters, errlog=err) as streams:
                async with ClientSession(*streams) as session:
                    await asyncio.wait_for(session.initialize(), 60)
                    tools = {}; cursor = None; seen = set()
                    for _ in range(100):
                        page = await asyncio.wait_for(session.list_tools(cursor=cursor), 30)
                        for tool in page.tools:
                            if tool.name in tools: raise ValueError('Duplicate upstream tool name')
                            tools[tool.name] = tool.model_dump(mode='json', exclude_none=True)
                        cursor = page.nextCursor
                        if not cursor: break
                        if cursor in seen: raise ValueError('Repeated upstream pagination cursor')
                        seen.add(cursor)
                    else: raise ValueError('Upstream catalog pagination exceeded limit')
                    if not tools or len(canonical(tools).encode()) > 5_000_000:
                        raise ValueError('Invalid or excessive upstream catalog')
                    self.session = session; self.catalog = tools
                    try: yield self
                    finally: self.session = None

    def prepare(self, requests):
        if self.session is None: raise ValueError('Ruflo tool session is not connected')
        requests = validate_requests(requests)
        for request in requests:
            if request['tool'] not in self.catalog: raise ValueError('Tool is not advertised by the pinned server')
            validate_arguments(self.catalog[request['tool']]['inputSchema'], request['arguments'])
        return requests, review_digest(self.project, self.policy, self.catalog, requests)

    def audit(self, digest, tool, status):
        # No arguments, results or exception messages in persistent audit records.
        if self.audit_root.is_symlink(): raise ValueError('Refusing linked review storage')
        self.audit_root.mkdir(mode=0o700, exist_ok=True)
        path = self.audit_root / (digest + '.jsonl')
        if path.is_symlink(): raise ValueError('Refusing linked review record')
        record = {'time': time.time(), 'review': digest, 'tool': tool, 'status': status, 'version': VERSION}
        with path.open('a', encoding='utf-8') as f: f.write(canonical(record) + '\n')
        if os.name != 'nt': path.chmod(0o600)

    async def execute(self, requests, approval, *, timeout=120):
        requests, digest = self.prepare(requests)
        if approval != digest:
            raise ValueError('Explicit review digest does not match this tool batch, schemas and permissions')
        # Changing on-disk grants cannot silently enlarge a running server's scope.
        if Sandbox(self.project).policy != self.policy:
            raise ValueError('Permissions changed; reconnect and review again')
        if type(timeout) not in (int, float) or not 1 <= timeout <= 300:
            raise ValueError('Timeout must be 1–300 seconds per tool')
        results = []
        for request in requests:
            tool = request['tool']; self.audit(digest, tool, 'started')
            try:
                raw = await asyncio.wait_for(self.session.call_tool(tool, request['arguments']), timeout)
                value = bounded_result(raw)
                failed = raw.isError
                payload = raw.structuredContent
                if isinstance(payload, dict) and (payload.get('success') is False or payload.get('error')): failed = True
                for content in raw.content:
                    if getattr(content, 'type', '') != 'text': continue
                    try: payload = json.loads(content.text)
                    except (ValueError, TypeError): continue
                    if isinstance(payload, dict) and (payload.get('success') is False or payload.get('error')): failed = True
                status = 'upstream-error' if failed else 'returned'
                self.audit(digest, tool, status)
                results.append({'tool': tool, 'failed': failed, 'result': value})
                if failed: break  # No continuing after upstream failure.
            except BaseException:
                self.audit(digest, tool, 'failed-or-cancelled')
                # A tool timeout does NOT mean its side effects were rolled back.
                raise
        return results


async def cli(project, operation, requests_path=None, approval=None):
    requests = None
    if operation == 'run':
        path = Path(requests_path)
        if not path.is_file(): raise ValueError('Requests must be a regular JSON file')
        with path.open('rb') as f: raw = f.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES: raise ValueError('Request file exceeds 100 KB')
        requests = validate_requests(json.loads(raw.decode('utf-8')))
    async with RufloToolSession(project).connect() as connection:
        if operation == 'tools':
            result = {'version': VERSION, 'advertised_not_certified': True, 'tools': list(connection.catalog.values())}
        else:
            requests, digest = connection.prepare(requests)
            if not approval:
                # Do not repeat raw arguments, which may contain sensitive values.
                result = {'review_digest': digest, 'tools': [r['tool'] for r in requests],
                          'project': str(connection.project), 'permissions': connection.policy,
                          'executed': False, 'warning': 'Inspect your request file and tool schemas. Approval permits all listed calls, including writes, commands and approved network use. No provider keys are forwarded. Errors/timeouts do not roll back side effects.'}
            else:
                result = {'review_digest': digest, 'results': await connection.execute(requests, approval)}
        text = json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + '\n'
        print(text, end='')
        return 1 if operation == 'run' and approval and any(row['failed'] for row in result['results']) else 0
