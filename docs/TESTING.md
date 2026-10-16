# Testing and acceptance contributions

Record `git rev-parse HEAD`, OS/build, architecture, Python version, terminal, exact command, passed/failed/skipped counts and redacted logs. A skipped test is not acceptance. No cloud API account or Pro subscription is needed for baseline tests. Optional local models require downloads and adequate hardware; microphone access is an OS permission, not an account credential.

## Linux / WSL baseline

```bash
git clone https://github.com/HIDORAKAI002/agent-forge.git
cd agent-forge
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[mcp,test]'
python -m pytest -q
```

Real Bubblewrap and Ruflo checks require their documented prerequisites and opt-in environment settings; inspect tests and [current acceptance](CURRENT_ACCEPTANCE.md). Do not claim skipped kernel/upstream tests passed. See [Ruflo runtime](RUFLO_RUNTIME.md) and the pinned integration lock, rather than installing an arbitrary latest release.

## Native Windows baseline (no WSL)

Use a **normal, non-administrator** account, Python 3.11+, Git and Windows Terminal/PowerShell on a supported ConPTY Windows build. Verify your token is non-elevated before running:

```powershell
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
# Must return False
```

Ensure `FORGE_WINDOWS_ISOLATION_EXPERIMENTAL` is unset. Always test in a disposable directory to avoid modifying real work.

### Developer checkout execution

```powershell
git clone https://github.com/rxmna8502/agent-forge.git
cd agent-forge
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp,credentials,test]"
.\.venv\Scripts\python.exe -m pytest -q tests/test_windows.py tests/test_store.py tests/test_health.py
.\.venv\Scripts\python.exe -I -m forge --project "C:\path\to\disposable-project"
```

### User-local installer execution

For end-user testing without developer tools in PATH, run the managed installer into a disposable location:

```powershell
$env:FORGE_INSTALL_ROOT = "C:\path\to\disposable-install"
$env:FORGE_BIN_ROOT = "C:\path\to\disposable-bin"
$env:FORGE_CONFIGURE_PATH = "0"
.\scripts\install.ps1
& "$env:FORGE_BIN_ROOT\agent-command.cmd" --project "C:\path\to\disposable-project"
```

### Expected terminal behaviors
- **Startup and output:** Welcome banner, prompt and terminal output render correctly.
- **Resize:** Dynamic window resizing updates both rows and columns without display corruption.
- **Unicode and spaces:** Paths containing spaces and non-ASCII characters open and save correctly.
- **Ctrl+C interrupt:** Pressing Ctrl+C interrupts the active foreground command and cleanly returns control without killing the parent Forge session or workspace.
- **Teardown and cleanup:** Exiting or stopping the session terminates all owned child processes (verified via Win32 Job Objects).
- **Workspace lock:** Workspace lock is released cleanly upon exit.

### Advanced Windows isolation work: disposable VM only

Read [WINDOWS_ISOLATION.md](WINDOWS_ISOLATION.md) first. `tests/test_windows_isolation.py` enables experimental behavior internally and exercises permission changes on test paths. Only systems developers using a disposable Windows VM/snapshot should run that experimental suite. The recorded suite has real failures. Do not raise integrity, elevate to hide failures, grant SeTcbPrivilege, change user-file ACLs manually, or replace failure with unrestricted execution. A new brokered workspace/console architecture is required before release acceptance.

## What needs real-machine testing?

GitHub-hosted Windows runners already execute on Windows; they are not Linux simulations. Consumer PCs add standard-user policies, Windows versions, terminal hosts, antivirus/enterprise restrictions, installers, microphones and credential vaults. You can contribute baseline reports without provider accounts. Optional cloud-provider acceptance needs only the authentication that provider supports (API billing is separate from a Pro subscription); never publish keys or passwords.

## Report checklist

- [ ] Exact commit, OS/build, architecture, Python and terminal
- [ ] Fresh disposable checkout and documented prerequisites
- [ ] Commands and separate passed / failed / skipped counts
- [ ] Expected vs actual behavior and minimal reproduction
- [ ] No keys, access tokens, recordings, usernames/private paths or proprietary data
- [ ] No claim that a discovered tool or mocked check proves its backend works
