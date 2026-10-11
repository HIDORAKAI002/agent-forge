# Agent Forge

### Your agent workspace. Entirely inside the terminal.

**A full-screen, Claude-Code-style TUI — not Electron, not a browser, and not a pile of detached terminal windows.** Real coding CLIs run inside embedded terminal surfaces, with one shared project store for memory, missions, and agent mail.

![Terminal-native workspace](docs/screenshots/01-workspace.svg)

> v0.3 development foundation. Local Ollama model selection, streaming pulls, preload and first-run onboarding are implemented. The interface and local coordination are implemented. Real provider CLI compatibility, voice input, automatic supervisor planning and enforced cost routing are still being built. Screenshots use labeled demo records; the embedded shell is a real local PTY, not a simulated model session.

## Start

Python **3.11+**, Git, and a UTF-8 terminal. **Linux / WSL first**; macOS uses the same POSIX backend but needs real-device validation. Native Windows PTY support is not implemented yet; use WSL.

```bash
git clone https://github.com/HIDORAKAI002/agent-forge.git
cd agent-forge
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[mcp]'
forge --project /path/to/your/project
```

This repository is private: clone using your existing authorized GitHub login. For development/testing, install `.[mcp,test]` instead. A 120×40 terminal or larger is recommended; 100×36 has a compact layout.

Already inside a project? `forge` uses the current directory. `forge --project /path doctor` prints detected CLI harnesses without opening the TUI. The app does not install or authenticate providers automatically.

## The interface

- **Cyan/violet Nebula** and **amber/rose Ember** themes with terminal-native borders, stippled textures, tabbed views, and a bottom command deck.
- **Agents:** real CLI terminal surfaces; select a session and type directly. `Ctrl+C` reaches the focused CLI.
- **Missions:** guided task editor, a dependency-aware ledger, isolated Git worktrees, and explicit launch/review confirmations.
- **Memory:** project facts, decisions, and handoffs with author/time/trust provenance.
- **Models (F6):** local Ollama library/installed-tag selection, actual streamed download layer %, model activation, RAM/VRAM residency and a persistent first-run guide.
- **Mail:** durable project-local inboxes with explicit acknowledgment.
- **Live status:** actual session/task/memory counts. Unknown quota/cost is labeled unknown, not invented.
- **Keyboard-first:** slash commands, command history, engine/session pickers, F-key tabs, and `Ctrl+Space` back to the composer.

![Real CLI inside the terminal workspace](docs/screenshots/06-embedded-terminal.svg)

## Quick workflow

```text
/launch claude
```

Launches the installed `claude` process inside the TUI. Existing CLI login and permissions remain with that CLI. `codex`, `gemini`, `kimi`, `opencode`, `aider`, and `shell` have built-in interactive profiles. Availability comes from PATH.

```text
/remember decision Run the parser test suite before merging changes.
/task
```

`/task` opens a terminal-native editor. Creating a task only queues it. `/run TASK_ID` asks before starting a CLI in an isolated worktree from committed HEAD. The project must be the Git repository root and tracked/untracked changes must be committed or stashed first.

An agent exit code of zero means **needs-review**, not “correct.” Inspect the worktree diff, run the required checks, and use `/approve TASK_ID` to record human approval. **Approval does not merge work.** Integrate prerequisite changes manually before dependent implementation tasks.

Automated task argument templates currently exist for Claude (`-p`), Codex (`exec`), and Gemini (`-p`). They are version-sensitive and need actual-provider validation. Other built-in CLIs are interactive-only until their automation interface is verified. No permission-bypass flags are added.

## Ollama / local operator

The first launch automatically opens **Models** with a project-local tutorial. Press **F6** or `/models` anytime. `/tutorial` reopens the guide; **Finish / skip tutorial** hides it without installing anything.

1. **Install Ollama** using the visible platform instructions. Linux / WSL:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
   Review the installer before running it. macOS: use the official installer at https://ollama.com/download. **Setup shell** opens a real shell but never types or executes an installer. No fictional installation percentage is shown.
2. **Start server** launches the installed `ollama serve` inside a real embedded terminal, bound to the configured loopback endpoint. If Ollama already runs as a service, just **Refresh**.
3. **Choose a tag**, e.g. `qwen2.5-coder:1.5b`, `qwen2.5-coder:3b`, or `qwen2.5-coder:7b`; any valid local tag works. Enter on an installed table row copies its tag into the selector. Model size comes from the server, not an invented RAM guarantee.
4. **Pull + use** asks permission for the network/download and RAM load. Forge streams `/api/pull`, verifies the model appears in the local inventory, preloads it and verifies `/api/ps` before saving the selected operator. **Use installed** skips the download.
5. **Open chat** embeds the actual `ollama run MODEL` process. This is a local conversation, **not an autonomous coding harness**: selecting a model does not grant file-editing tools or enable supervisor planning.

The chosen operator persists in `.agent-forge/ollama.json`. Once explicitly activated, an installed selection preloads automatically on project reopen when the local Ollama server is reachable. Start the server through the guide if it is not already running. A missing selection is **never auto-downloaded**. **Unload** sets keep-alive to zero and turns off automatic activation, preserving the selection. Server keep-alive after activation is five minutes; Ollama may evict models sooner under memory pressure. Auto-activation happens on reopen, not continuous GPU pinning.

### Honest progress and resource meters

- The percentage and bar are **current-layer bytes completed / layer total**, not a fabricated whole-model percentage. Known-layer bytes are summed separately; new layers can increase the known denominator.
- Manifest lookup, integrity verification, installer execution and RAM loading have **no measurable percentage** and are labeled indeterminate. A layer reaching 100% does not mean activation is complete.
- Host RAM percentage/free GB is actual `psutil` data. Project-filesystem free space is labeled separately and is not assumed to be Ollama's model-storage disk.
- Loaded model bytes and VRAM bytes come from `/api/ps`. **GPU residency %** means `size_vram / size`, not GPU compute utilization or a GPU memory-capacity percentage.
- Cancel stops local stream consumption and prevents committing a new selection. An accepted Ollama server operation may finish independently; inspect server status. Cancelling does not promise to reclaim cached blobs.

`OLLAMA_HOST` defaults to `http://127.0.0.1:11434`. Only loopback HTTP endpoints (`localhost`, `127.0.0.1`, `::1`) are accepted. API requests bypass environment proxies and refuse redirects. Models with remote/cloud metadata and explicit cloud tags are excluded. Downloading still contacts Ollama's registry; **local generation is not offline installation**. Ollama and its model licenses are separate from this repository.

Official references: [Linux setup](https://docs.ollama.com/linux), [streamed pull](https://docs.ollama.com/api/pull), [installed inventory](https://docs.ollama.com/api/tags), [loaded models](https://docs.ollama.com/api/ps), [preload / unload](https://docs.ollama.com/api/generate), [Qwen2.5-Coder tags](https://ollama.com/library/qwen2.5-coder).

![Ollama terminal model hub — HTTP test fixture, not a real inference run](docs/screenshots/10-ollama-hub.svg)

## Command deck

| Command / key | Action |
|---|---|
| `/models`, F6 | Local model hub |
| `/tutorial` | Reopen first-run guide |
| `/ollama pull MODEL`, `/ollama use MODEL` | Confirm download or installed activation |
| `/ollama refresh`, `chat`, `serve`, `setup`, `unload`, `cancel` | Ollama lifecycle controls |
| `/launch ENGINE` | Embed a real CLI |
| `/focus SESSION_ID` | Return to a session; IDs accept unique prefixes |
| `/sessions`, `/engines` | Inspect sessions or configured harnesses |
| `/stop SESSION_ID` | Confirm cleanup of the session and known descendants |
| `/task` | Guided mission editor |
| `/task ENGINE TITLE :: INSTRUCTIONS` | Queue a bounded task |
| `/tasks`, `/run TASK_ID` | Inspect or explicitly launch work |
| `/approve TASK_ID` | Record human review; no merge |
| `/remember KIND TEXT` | Add a human-submitted verified fact/decision/handoff |
| `/memory [QUERY]` | Inspect/filter shared memory |
| `/send FROM TO TEXT` | Send durable project-local mail |
| `/inbox NAME` | Select an agent inbox |
| `/ack FULL_MESSAGE_ID RECIPIENT` | Acknowledge handled mail |
| `/route routine` or `/route high` | Recommend a user-configured tier; never auto-dispatch |
| `/theme nebula` or `/theme ember` | Change the palette |
| `/help`, F1 | Open the command deck |
| F2 / F3 / F4 / F5 | Agents / missions / memory / mail |
| Ctrl+Space | Return to slash-command input |
| Ctrl+Q, `/quit` | Confirm stopping active sessions and exit |
| Y / N / Esc in a confirmation | Explicit accept / reject; Cancel is the safe default |

## Shared project memory and agent tools

```
project/.agent-forge/
  state.sqlite           # canonical memory, task/mail/event ledger
  memory.md              # generated readable summary, latest 500 records
  workspace.lock         # one active TUI owns a project
  ollama.json            # selected local operator, auto-activation, tutorial state
  profiles.json          # optional custom CLI/model profiles
  worktrees/<task-id>/    # preserved task workspaces
```

Add `.agent-forge/` to your project's `.gitignore` if appropriate. Initialization deliberately does not rewrite your repository configuration, CLAUDE.md, AGENTS.md or GEMINI.md.

Every agent can contribute through the shared CLI:

```bash
forge --project /absolute/project/path memory list --query parser
forge --project /absolute/project/path memory add \
  --kind handoff --author codex --text 'Changed the parser; test results attached.'
```

Task prompts include current shared context and this contribution path. Interactive CLIs are not magically forced to use it: attach the shared MCP server or configure project instructions explicitly.

### MCP

Configure each compatible CLI using its official stdio-MCP settings. Use the **absolute installed Python path**:

```json
{
  "command": "/absolute/path/to/.venv/bin/python",
  "args": ["-m", "forge", "--project", "/absolute/project/path", "mcp"]
}
```

Tools: `memory_search`, `memory_add`, `task_list`, `message_send`, `message_inbox`, `message_ack`.

Independent clients share the same SQLite database. Agent entries are always **unverified**. Author/sender/recipient labels are self-reported routing labels, not cryptographic identities. Human TUI submissions are marked verified by explicit submission, not by an automated truth checker. All agents attached to a project share one local trust boundary. Mail requires polling; delivery does not silently inject text into another agent's terminal.

## Custom CLIs, DeepSeek/Kimi models and routing

A **model is not a CLI harness**. Use a supported harness that exposes the desired provider/model through its documented configuration, or register a trusted custom command. Do not assume a separate official CLI exists for every model vendor.

Create `.agent-forge/profiles.json`, for example:

```json
[
  {
    "id": "local-worker",
    "label": "My local coding worker",
    "argv": ["/absolute/path/to/my-worker"],
    "task_argv": ["/absolute/path/to/my-worker", "--prompt", "{prompt}"],
    "tier": "local"
  },
  {
    "id": "claude",
    "label": "Claude Code / primary",
    "argv": ["claude"],
    "task_argv": ["claude", "-p", "{prompt}"],
    "tier": "strong"
  }
]
```

This is a schema example: `my-worker` must actually exist and implement the arguments. Commands are argv arrays, not shell-evaluated strings. Reload the app after configuration changes. Credentials belong in provider-managed authentication or your process environment, never in memory or profile files.

`/route` prioritizes local/economy tiers for routine tasks and strong tiers for high-risk work. **This is a transparent, user-configured recommendation policy, not an automatic planner, live-price router, budget enforcer or guarantee of free usage.** Built-in tiers default to unknown until configured.

## Safety and compatibility

- **Not an OS sandbox.** Worktrees reduce edit collisions; a CLI can still access anything allowed by its OS account. Native provider approvals remain authoritative.
- No automatic paid-model calls, merges, pushes, provider installation, remote listener or telemetry.
- Only use trusted projects and CLIs. A custom executable/profile is executable code, not a safe document.
- Terminal output is rendered through a VT emulator, not written directly into the parent terminal; OSC clipboard/link escape sequences are not executed by the renderer. Full modern terminal protocol coverage is not guaranteed.
- Cursor movement, truecolor/ANSI styles, resize, UTF-8 input, standard control/navigation keys, bracketed paste and primary/alternate screen handling are implemented. Advanced mouse reporting, Kitty graphics/keyboard extensions, sixel, native ConPTY and advanced scrollback navigation are not implemented.
- Ctrl+Q, F1–F6 and Ctrl+Space are reserved by the host. They are not passed through to a focused CLI. Avoid putting secrets into command history, tasks, mail, memory or screenshots.
- A dedicated, single-threaded PTY broker avoids forkpty from the multi-threaded TUI. Stop terminates known descendants and escalates if necessary. Malicious or independently detached processes can escape lifecycle tracking; this is not a security boundary.
- Memory, tasks and mail persist locally; live terminal sessions do not resume after app restart. Interrupted tasks are marked failed and never rerun automatically. Existing worktrees are preserved for manual inspection.
- The Markdown file is a derived projection. A crash can make it temporarily stale; SQLite remains authoritative and reopening regenerates it. Symlink checks at managed entry points do not eliminate local filesystem races.

## Development / validation

```bash
pip install -e '.[mcp,test]'
python -m pytest -q
python scripts/capture_tui.py
python scripts/capture_ollama.py
```

**v0.3 validation: 44 tests passed on Linux / Python 3.13**, including the original terminal/memory/MCP regressions and Ollama fixtures. Six new actual TUI states were visually inspected, including a compact 100×36 model hub.

The tests cover persistent memory, concurrent writers, dependencies, mail acknowledgment, project ownership, real Linux PTY input/controlling TTY, resize, cancellation, parallel **fixture** agents in worktrees, alternate screens, explicit routing policy, guided TUI editing, keyboard focus, compact layout, and **two actual stdio MCP clients**.

Ollama tests use a real loopback HTTP fixture server with streamed NDJSON, error/EOF/cancellation cases, persisted activation, auto-resume, remote/cloud rejection and TUI confirmations. No real Ollama model was downloaded or inferred here.

No provider account or real Claude/Codex/Gemini model was used in these tests. Those compatibility checks are the next milestone. `requirements-lock.txt` records the tested environment; the editable project itself is installed separately. The capture script exports nine actual Textual screen states; a local shell is real, while demo memory/task/mail records are explicitly labeled.

## Next build steps

1. Validate installed Claude/Codex/Gemini/Kimi versions and permission/resume behavior on real machines.
2. Add a supervised natural-language planner, acceptance tests, explicit handoff rules and bounded retries — still one authoritative scheduler.
3. Attach project memory/mail MCP automatically only with consent, preserving existing provider configuration.
4. Integrate audited Ruflo modules behind the coordinator interface; no competing memory/scheduler authorities.
5. Add live usage accounting, quota checks and enforceable spending gates before automatic model selection.
6. Add local voice capture + transcription (audited permissive components inspired by Handy), inserting an editable draft without auto-executing it.
7. Native Windows ConPTY, protocol coverage/scrollback, accessibility, migrations/backups and packaging.

## Design references and license

The terminal UX direction follows the user's [AI Video Dubbing](https://github.com/HIDORAKAI002/ai-video-dubbing) Textual studio: live workspace, side rail, and bottom slash-command input. This implementation is original; it does not include the unrelated dubbing pipeline or the earlier Electron prototype.

Integration candidates, **not vendored**: [Ruflo](https://github.com/ruvnet/ruflo), [Handy](https://github.com/cjpais/Handy), [Agent Client Protocol](https://github.com/agentclientprotocol/agent-client-protocol), [Beads](https://github.com/gastownhall/beads).

Original code: MIT. Dependencies and any future speech models retain their own licenses; notably, pyte is LGPLv3 and is separately installed. See [third-party notices](docs/THIRD_PARTY.md) before bundling a distribution. Do not copy GPL/AGPL voice-app source into a differently licensed distribution without reviewing the obligations.
