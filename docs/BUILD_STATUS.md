# Build status and release boundaries

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

- Native Windows support: requires a ConPTY backend, Windows process-tree cleanup, a replacement for POSIX project locking, native install scripts and real Windows CI/device tests. WSL works through the existing Linux backend.
- Enforced OS sandbox: existing PTYs run with the user's permissions. Worktrees isolate changes, **not** filesystem/network/command permissions. A container/VM adapter needs scoped mounts, credentials, network policy and adversarial escape tests before it can be called a sandbox.
- Ruflo integration: no Ruflo source or package is imported. Ruflo is an optional orchestration/memory/routing reference from the original request, not another name for this application. Audit specific components and their licenses before integrating; do not introduce competing authoritative schedulers or memory stores.
- Actual provider CLI account validation, real Ollama coding/model validation, OS keyring/device behavior and microphone device testing remain separate from fixture-based automated tests.

## Verified in this environment

- 64 automated tests on Linux/Python 3.13.
- Actual isolated installer and standalone `agent-command` outer-PTY/nested-shell smoke test.
- Actual tiny.en CPU/int8 public-audio transcription and the Forge RAM-buffer-to-editable-draft pipeline. Microphone was not used. PyAV is constrained to `<17` because newer versions failed the file-input test.
- Fifteen actual Textual UI states inspected individually, including eight themes and compact setup. Planner drafts in screenshots are explicitly labeled fixtures.

## Voice candidates

- [Handy](https://github.com/cjpais/Handy): complete cross-platform offline dictation application; MIT code, separate branding restrictions. Suitable companion app/reference rather than another desktop shell embedded into this TUI.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): MIT Python/CTranslate2 transcription backend used by the optional voice extra. Speech weights/dependencies retain their own licenses.
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp): MIT native alternative with microphone examples and CPU/GPU backends; not vendored here.

References: [Ruflo](https://github.com/ruvnet/ruflo), [Claude authentication](https://code.claude.com/docs/en/authentication), [Codex authentication](https://developers.openai.com/codex/auth/), [Gemini authentication](https://geminicli.com/docs/get-started/authentication/), [Aider + Ollama](https://aider.chat/docs/llms/ollama.html), [Aider options](https://aider.chat/docs/config/options.html).
