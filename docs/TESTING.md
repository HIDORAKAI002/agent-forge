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

Use a **normal, non-administrator** account, Python 3.11+, Git and Windows Terminal/PowerShell on a supported ConPTY Windows build. Start in a disposable checkout; do not run isolation experiments against your real work.

```powershell
git clone https://github.com/HIDORAKAI002/agent-forge.git
cd agent-forge
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[mcp,test]"
.\.venv\Scripts\python.exe -m pytest -q tests/test_windows.py tests/test_store.py tests/test_health.py
.\.venv\Scriptsorge.exe --project C:\path	o\disposable-project
```

Report fresh installation, shell startup/output, resizing, Unicode/space paths, interrupt, normal exit and child cleanup. Confirm the UI does not claim native Windows enforcement is release-ready. The PowerShell installer is documented in [INSTALL_BUNDLE.md](INSTALL_BUNDLE.md).

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
