# Check a user installation

The placeholder launcher is `agent-command`. Install Forge outside the project before enabling enforcement. Provider CLIs and Ollama remain separately approved installs; core installation does not silently install or authenticate them.

## Read-only setup checks

```sh
agent-command --project /path/to/project doctor --full
agent-command --project /path/to/project doctor --full --require core
agent-command --project /path/to/project doctor --full --probe-ollama --require local
agent-command --project /path/to/project doctor --full --probe-isolation --require isolation
```

`--require` returns a nonzero exit status when its gate is unmet. Use `local_coding` to require Aider in addition to the local chat prerequisites. These checks do not generate text, execute provider CLIs, read API-key values, unlock a credential vault, install dependencies, or approve folder access. `doctor --full` does not create project state or preferences. The old `doctor` harness-list JSON is retained for compatibility.

Only `--probe-ollama` contacts a service: a direct, credential-free loopback connection with proxies disabled, no redirects, bounded response sizes and timeouts. It reports model count, not custom model names. A reachable service is not proof of generation quality. Use Models to pull/select a compatible model and perform an actual chat/coding test.

`--probe-isolation` runs a bounded Linux Bubblewrap startup probe with no network, no project mount and no ambient environment/keys. Passing it does not approve or test a particular project's references. Host-policy failures remain failures; do not disable host protections to force a pass.

In the interface, `/doctor` displays dependency and setup status without network requests or key access. `/help` lists the command. Optional voice/MCP/vault modules can be missing without preventing the base terminal interface from running; their corresponding features still require them.

## Honest platform boundaries

Native Windows terminal support and native filesystem enforcement are separate capabilities. The LPAC backend remains experimental and disabled by default until its actual native filesystem-restoration and console/runtime acceptance gates pass. macOS enforcement is not implemented. A health report never converts those into passing security claims.

Local Ollama requires no consumer Pro subscription or provider account. Cloud models require a compatible key and the provider's required billing/access. Microphone permission is an OS permission, not a cloud account. OS vault storage is optional overall; Codex native key-auth has a separate documented vault requirement.

For actual launcher input and durable effects rather than prerequisite availability alone, use `scripts/validate_install.py` with the installed environment’s Python; see [installation checks](INSTALL_BUNDLE.md). Latest evidence and unresolved release gates are in [current acceptance](CURRENT_ACCEPTANCE.md).

## Real enforced local coding smoke test

With an existing Aider install on PATH and local Ollama/model already available:

```sh
agent-command --project /path/to/project doctor --full --probe-isolation
python scripts/validate_local_coding.py --read-only-runtime /absolute/aider/runtime --output local-coding-validation.json
```

Repeat `--read-only-runtime` for separate Python/runtime prefixes as needed; grant only reviewed runtime directories, not your home. The script creates a disposable Git project, explicitly allows **host networking** for local Ollama, runs a two-file task, checks bounded generated code, preserves native confirmations and never approves/merges results. It does not install providers, download weights, request paid inference or certify coding quality. Enforced agents cannot directly update `.agent-forge`; use terminal handoffs or an explicitly attached trusted host MCP service.
