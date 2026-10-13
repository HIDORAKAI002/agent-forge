# Install the source bundle

This is a source-only installer bundle, not a standalone native executable. Downloaded package dependencies require internet. No provider CLI, Ollama, model weights or voice package is silently installed.

Prerequisites: Python 3.11+, Git and a UTF-8 terminal. Aider is a separate optional CLI; Aider 0.86.2 requires Python 3.10–3.12, so keep its environment separate when Forge uses Python 3.13.

## Linux / WSL

Extract the ZIP, enter its `agent-forge` directory, then:

```bash
bash scripts/install.sh
```

Open a new terminal or follow the printed PATH instructions, then:

```bash
agent-command
```

## Native Windows, without WSL

Extract the ZIP, enter its `agent-forge` directory in PowerShell, then:

```powershell
& .\scripts\install.ps1
agent-command
```

The installer does not alter PowerShell execution policy. If a device policy disallows scripts, obtain an approved installation method from the device administrator rather than bypassing it.

## Optional setup

- Configure a provider's API key or native CLI login in Setup; an API key is not a subscription login.
- For local models, install Ollama separately, start its loopback server, and use Models → Pull + use. No API key is needed for a local Ollama model.
- For local file editing, install Aider separately in its compatible Python environment and put its launcher on PATH. The selected Ollama model becomes the local coding profile.
- Voice is opt-in (`FORGE_VOICE=1` on bash or `-Voice` on PowerShell).
- Enforced folder boundaries currently require Linux/WSL Bubblewrap and explicit setup approval. Native Windows terminal support works without WSL, but native Windows filesystem enforcement is not implemented.

`BUNDLE_MANIFEST.json` identifies the source commit and SHA-256 of included files. No user credentials, project memory/database, installed environment, model weights or account data are included.
