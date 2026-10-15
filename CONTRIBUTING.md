# Contributing to Agent Forge

Welcome! Fork the repository, reproduce an issue, and send a pull request. Test reports and documentation improvements are valuable contributions too. No paid provider subscription is required for baseline tests or local-model workflows.

**Early access, not a security-certified release.** Read [launch report](docs/LAUNCH_REPORT.md), [testing](docs/TESTING.md), and [Windows isolation status](docs/WINDOWS_ISOLATION.md) before choosing work.

## Where we need help

| Area | Useful contribution | Acceptance expectation |
| --- | --- | --- |
| Windows systems engineering | Design a brokered writable workspace and console architecture for LPAC | Actual standard-user Windows denial/allow tests; never raise integrity or silently fall back |
| Windows testing | Fresh install, ConPTY, resize, interrupt, shutdown, spaces/Unicode paths | OS/build, terminal, Python, exact commit and redacted reproduction |
| Ruflo | Backend-by-backend integration evidence | Real results, prerequisites and unsupported cases; catalog discovery alone is not acceptance |
| Security / Linux | Namespace, worktree, link and permission regression tests | Demonstrate outside reads/writes denied and approved references read-only |
| Device testing | Optional microphone, local transcription and credential-vault behavior | Real device/OS evidence; no account passwords or recordings in issues |
| First contributions | Onboarding, documentation, accessibility, reproducible bug reports | Small focused changes with verifiable instructions |

## Development

1. Fork and clone your fork. Create a feature branch.
2. Use Python 3.11+ in a virtual environment; install `python -m pip install -e ".[mcp,test]"`.
3. Run the appropriate commands in [TESTING.md](docs/TESTING.md). Missing prerequisites and skipped tests are not passing acceptance.
4. Keep a PR focused. Explain what changed, why, platform, exact test commands and results. Include regression tests for fixes.
5. Open a PR against `main`; link an issue or explain a small standalone change. Maintainer review is required. Please do not commit secrets, recordings, model weights, virtual environments or project-state databases.

## Safety rules

Do not remove review gates, automatically merge agent changes, enable paid calls, forward managed keys into upstream tools, weaken isolation, or convert failures to silent unrestricted launches. Experimental Windows isolation is for disposable developer VMs only, not valuable projects. Error/timeout does not roll back tool writes. Read [SECURITY.md](SECURITY.md) before reporting a vulnerability.

By contributing, you agree your original contributions are licensed under this repository's MIT license. Retain third-party notices. No corporate affiliation or experience level is required. Be respectful, constructive and specific; no harassment or publishing private information.
