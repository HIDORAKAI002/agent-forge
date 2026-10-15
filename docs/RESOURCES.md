# Resources, evidence and credits

This index distinguishes software used by Agent Forge from platform documentation and records. It is not an endorsement by upstream authors. Original Forge code is MIT; upstream software, optional packages and model weights retain their own licenses. Consult [THIRD_PARTY.md](THIRD_PARTY.md), `pyproject.toml`, `requirements-lock.txt`, `docs/voice-tested-requirements.txt` and `integrations/ruflo/package-lock.json` for exact declared/resolved dependencies; the npm lock includes transitive packages.

## Project and reproducibility

- [Source, installation and architecture](../README.md)
- [Contributor guide](../CONTRIBUTING.md) · [contributors/testers](../CONTRIBUTORS.md)
- [Test guide](TESTING.md) · [launch report](LAUNCH_REPORT.md)
- [Current acceptance](CURRENT_ACCEPTANCE.md) · [local suite JSON](LOCAL_ACCEPTANCE.json)
- [Actual enforced local coding](ENFORCED_CODING_VALIDATION.json)
- [Windows isolation analysis](WINDOWS_ISOLATION.md) · [Ruflo gateway evidence](RUFLO_GATEWAY_VALIDATION.json)
- [GitHub CI](https://github.com/HIDORAKAI002/agent-forge/actions) · [help-wanted issues](https://github.com/HIDORAKAI002/agent-forge/issues)

## Runtime / development software

- [Python](https://www.python.org/) and [SQLite](https://www.sqlite.org/)
- [Textual](https://textual.textualize.io/) / [Rich](https://rich.readthedocs.io/) terminal UI; [pyte](https://github.com/selectel/pyte) terminal emulation
- [psutil](https://github.com/giampaolo/psutil), [ptyprocess](https://github.com/pexpect/ptyprocess), [pywinpty](https://github.com/andfoy/pywinpty), [pywin32](https://github.com/mhammond/pywin32)
- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk), [jsonschema](https://python-jsonschema.readthedocs.io/)
- [Ollama](https://ollama.com/) and optional [Aider](https://aider.chat/); the recorded local coding trial used [Qwen2.5-Coder 1.5B](https://ollama.com/library/qwen2.5-coder:1.5b)
- [Pinned Ruflo npm package](https://www.npmjs.com/package/ruflo/v/3.56.9) and [integration instructions](RUFLO_RUNTIME.md)
- [Bubblewrap](https://github.com/containers/bubblewrap) Linux namespace isolation
- Optional local speech: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [sounddevice](https://python-sounddevice.readthedocs.io/), [PyAV](https://pyav.org/), [Hugging Face](https://huggingface.co/) model downloads
- Optional [keyring](https://keyring.readthedocs.io/) OS credential integration
- [Git](https://git-scm.com/), [Git worktrees](https://git-scm.com/docs/git-worktree), [GitHub Actions](https://docs.github.com/en/actions), [pytest](https://docs.pytest.org/)

## Platform engineering references

- [Microsoft pseudoconsole / ConPTY](https://learn.microsoft.com/en-us/windows/console/creating-a-pseudoconsole-session)
- [Microsoft AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
- [Windows mandatory integrity control](https://learn.microsoft.com/en-us/windows/win32/secauthz/mandatory-integrity-control)

## Launch assets

The launch carousel uses original text/layout and a fresh screenshot of the actual Forge UI in a disposable demo with no connected live provider. It does not fabricate agent activity. Generation uses Pillow and ReportLab; no stock photography or third-party logos are used. The UI snapshot and baseline test numbers are labeled separately. See [launch copy and asset notes](launch/README.md).
