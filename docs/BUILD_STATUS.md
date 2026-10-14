# Build status and release boundaries

## v0.5 hardening

- Git metadata is read-only to agent sessions; parent Git worktree/status helpers are boundary-constrained with hooks/fsmonitor disabled. An actual malicious checkout-filter attempt could not write outside the project.
- Trusted Ruflo state/home/index is stored outside the writable project in per-project user configuration. Host-service executable/runtime entrypoints inside the writable project are refused; project/relative PATH entries are removed.
- First remote run exposed sandbox host-policy startup and Windows path/shutdown failures. Fixes are submitted for new CI validation; old results are not release acceptance.

## v0.5 additions

- Real pinned Ruflo 3.56.9 MCP bridge: derived memory indexing, SmartRetrieval, canonical record rehydration and advisory routing used as Ollama planning context. Actual MCP indexing/retrieval/routing tested. No upstream agent executor is enabled.
- Linux/WSL Bubblewrap filesystem enforcement: project writable, approved references read-only, other user paths hidden, network blocked unless explicitly allowed, fail-closed behavior and secret environment filtering. Eight real kernel permission checks passed. Runtime-tree and temporary-space exceptions are documented.
- Native Windows ConPTY broker, Job Object cleanup, Windows workspace locking, safe standard npm-shim resolution and PowerShell installer added. Four native Windows tests must pass on Windows; Linux skips are not passes.
- Automated Linux/Windows/Ruflo CI and source-commit-tagged validation records. See [CHECKLIST.md](CHECKLIST.md).


## v0.4 implemented

- User-local installer with isolated package environment and a temporary `agent-command` launcher; source checkout is not required after installation. Optional voice dependencies use `FORGE_VOICE=1`. Supported bash/zsh profiles get a backed-up managed PATH block; `FORGE_CONFIGURE_PATH=0` disables profile changes. Other shells get manual PATH instructions.
- Eight saved palettes: Nebula, Ember, Forest, Ocean, Sakura, Solar, Glacier, Graphite.
- Confirmed in-app official installers for Claude, Codex and Gemini; npm prerequisites are checked and no sudo is added.
- Masked provider-key setup for Claude, Codex and Gemini. Session-only storage or approved OS keyring backends; no plaintext-file fallback. Keys are scoped to their CLI environment. Codex key authentication is explicitly invoked through a non-echoed pipe with its own keyring setting forced on.
- Local Ollama supervisor planning: structured 1–8-task DAG, editable draft, explicit queue approval, transparent profile assignment.
- User-labeled strong/free/economy/local routing. High-risk work prefers strong; routine work prefers local/free. Labels are not performance or price guarantees; provider quotas are intentionally not part of this release.
- Approved batch dispatch: up to 20 queued tasks per approval, at most two task sessions, prerequisite review gates, command-change revocation, no automatic retry/merge. Pause stops future launches, not running CLIs.
- Aider-backed local coding profile for the selected Ollama model. Requires the separately installed Aider CLI; normal native confirmations stay enabled, and automatic commits are disabled.
- Optional faster-whisper CPU/int8 dictation, microphone start/stop, maximum 60 seconds, editable transcript and explicit insertion target. Insertion never presses Enter. Initial speech-model download asks first; later inference uses local weights.

## Not completed / not claimed production-ready

- Native Windows device/provider combinations beyond the passing 3.11/3.13 native CI suite remain unverified.
- Native Windows/macOS OS sandbox is still missing. Linux/WSL Bubblewrap is implemented and tested; OFF mode remains unrestricted, and worktrees by themselves are never a sandbox.
- Broad Ruflo catalog access is now available through an explicitly reviewed sandboxed CLI gateway, separate from the TUI memory/routing bridge. Not every upstream backend is implemented or certified; no arbitrary credentials or host access are forwarded. Ruflo is not a second authoritative Forge scheduler or memory store.
- Actual provider CLI account validation, broader Aider coding/sandbox validation, OS keyring/device behavior and microphone device testing remain separate from fixture-based automated tests.

## Verified evidence

- Real Aider 0.86.2 in Python 3.12.15 + Qwen2.5-Coder 1.5B performed one authorized file edit through Runtime/worktree dispatch. Result stayed needs-review; add(2,3)=5; original unchanged; no automatic commit/merge. Native confirmation policy was not disabled.

- All five CI suites passed source `636c6be`: Linux 76 passed each; native Windows 19 passed each; actual Ruflo one passed. Skips are documented separately.
- Actual Ollama 0.6.8 + Qwen2.5-Coder 1.5B CPU activation, generation, schema-validated plan, embedded CLI and confirmed unload; no paid provider. Tiny 0.5B invalid plan rejected.
- The workspace was restored from an older snapshot on continuation; latest code was recovered from GitHub rather than overwriting it. Model evidence was retained from committed session events.

- 64 automated tests on Linux/Python 3.13.
- Actual isolated installer and standalone `agent-command` outer-PTY/nested-shell smoke test.
- Actual tiny.en CPU/int8 public-audio transcription and the Forge RAM-buffer-to-editable-draft pipeline. Microphone was not used. PyAV is constrained to `<17` because newer versions failed the file-input test.
- Fifteen actual Textual UI states inspected individually, including eight themes and compact setup. Planner drafts in screenshots are explicitly labeled fixtures.

## Voice candidates

- [Handy](https://github.com/cjpais/Handy): complete cross-platform offline dictation application; MIT code, separate branding restrictions. Suitable companion app/reference rather than another desktop shell embedded into this TUI.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): MIT Python/CTranslate2 transcription backend used by the optional voice extra. Speech weights/dependencies retain their own licenses.
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp): MIT native alternative with microphone examples and CPU/GPU backends; not vendored here.

References: [Ruflo](https://github.com/ruvnet/ruflo), [Claude authentication](https://code.claude.com/docs/en/authentication), [Codex authentication](https://developers.openai.com/codex/auth/), [Gemini authentication](https://geminicli.com/docs/get-started/authentication/), [Aider + Ollama](https://aider.chat/docs/llms/ollama.html), [Aider options](https://aider.chat/docs/config/options.html).

## Broader Ruflo gateway and startup hardening

- Pinned runtime catalog discovery, schema validation, exact batch approval bound to tool definitions/arguments/workspace/permissions, redacted review audit, bounded outputs and timeouts. One MCP server per batch; no unrestricted host fallback.
- Actual `memory_stats`, `workflow_list` and `terminal_execute` used inside the boundary, including successful project write/approved reference read and blocked unapproved access. This is not a pass for all 381 advertised tools.
- Isolated Python startup for brokers and generated launchers prevents project package/startup-file/PYTHONPATH injection into trusted host processes.
- Native Windows filesystem enforcement remains unfinished and explicitly fail-closed. API-key use does not require consumer Pro subscriptions; optional OS vaults and microphones are not provider accounts.
