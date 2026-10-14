# Accounts, API keys and local permissions

- Local Ollama inference needs no provider account, API key or consumer Pro subscription. Model downloads need network access initially; inference runs on the machine's hardware.
- Cloud providers issue API keys through their own accounts. Consumer chat subscriptions are separate from API access, billing and rate limits. A free tier is not a billing guarantee.
- Only a compatible provider adapter/CLI can use a pasted key. Keys for arbitrary providers are not interchangeable.
- Forge's session-only key storage needs no OS-vault login. Optional persistent storage uses the operating system's credential store; there is no plaintext fallback. This is not a cloud subscription.
- Codex's separate native API-key login currently requires the supported OS vault in Forge. This limitation does not apply to local Ollama or session-only Claude/Gemini keys. The built-in Codex environment variable alone is not claimed to authenticate the native CLI.
- Microphone permission is necessary only for optional dictation. No microphone account or microphone password is needed. Recording must be initiated explicitly.
- Windows filesystem isolation is independent of terminal support. The native ConPTY backend works; a Job Object cleans up processes but does not restrict filesystem access.
- Merely choosing a working directory, checking paths in Python, or using a Git worktree does not stop a native child process from reading other folders. A real OS boundary must constrain child and grandchild processes, handles, network, links and runtime access.
- A native Windows LPAC implementation is now in an **experimental acceptance build**, not release-enabled. See [native Windows isolation](WINDOWS_ISOLATION.md). Enforced launches must fail closed there; do not turn isolation off as an automatic fallback.

## Broad upstream Ruflo access

`agent-command --project PROJECT ruflo tools` lists the catalog advertised by installed, pinned Ruflo 3.56.9 **inside an enforced sandbox**. The audited memory bridge in the TUI remains a separate, small trusted-host integration.

`agent-command --project PROJECT ruflo run --requests-file requests.json` previews a batch without calling its tools. The request file is an array, for example:

```json
[
  {"tool": "memory_stats", "arguments": {}},
  {"tool": "workflow_list", "arguments": {}}
]
```

Inspect the request file and advertised schemas. Repeat with `--approve EXACT_REVIEW_DIGEST` to authorize those specific calls. The digest binds the pinned version, complete selected tool definitions, arguments, project and sandbox policy. All requests are validated before the first tool call. Each batch uses one MCP server, preserving in-process state across its calls. Limits: 20 calls, 100 KB total request JSON, 1 MB per result, 120 seconds per tool by default. Calls stop after an upstream MCP error; previous writes are not rolled back. Timeouts close the session and are failures, not proof of rollback.

No provider keys, host HOME, SSH agent or ambient cloud credentials are forwarded. Do not put credentials in request JSON or terminal command strings: upstream tools may persist their own inputs/history in the project, even though Forge review records exclude arguments and results. Broader tools cannot access arbitrary host folders. Network stays blocked unless the user explicitly approved host networking in project permissions. Key-bearing files inside the project or explicitly approved references are still readable by the upstream tools. Keep credentials out of those files or keep networking blocked; folder grants are not a secret scrubber. Paid/cloud tools without accessible credentials remain unavailable; the gateway does not silently authenticate, add funds or invent free access.

The pinned Node/Ruflo installations must be in read-only system runtime paths or explicitly approved, bounded read-only runtime grants. An absent runtime grant is an error, not permission to run outside isolation. A dependency may require more resources than the current grant policy permits. Read the tool's result: advertising a tool is not a certification that its backend, model, browser or external service is installed or implemented.

The actual pinned runtime advertised 381 tools during inspection. This is **catalog coverage**, not 381 completed end-to-end acceptance tests. Forge does not replace upstream no-op/unsupported implementations. Full production Windows enforcement and certification of every upstream backend remain separate unfinished work.

## Interface workflow

Setup → Ruflo tools offers isolated catalog discovery, name filtering, read-only tool schemas, editable JSON arguments, separate approval and a read-only result viewer. `/ruflo tools` opens this workflow. No upstream result automatically creates or dispatches Forge tasks. Discovery initializes a sandboxed server; calling a tool needs its own explicit approval.
