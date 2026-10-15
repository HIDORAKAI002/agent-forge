# Current acceptance status

**This is a usable local-first development build, not an all-platform production/security release.** No consumer Pro subscription is required. The remaining gates below are real work, not credentials that can be skipped to turn tests green.

## Newly executed checks

- **113 passed, zero failed, 13 skipped** in the actual Linux/Python 3.13 regression, with all opt-in Bubblewrap and pinned Ruflo 3.56.9 tests enabled. Native Windows skips are not passes. [Machine-readable evidence](LOCAL_ACCEPTANCE.json) binds the tested source tree, not just the unchanged package version.
- Actual Ollama 0.6.8 / Qwen2.5-Coder 1.5B CPU activation, generation, schema-valid bounded plan, embedded CLI and observed unload. No provider keys, paid API calls, queueing or dispatch in this check. [Evidence](OLLAMA_VALIDATION.json).
- Actual Aider 0.86.2 + that local model edited one authorized file through Runtime/worktree dispatch; `add(2,3)==5`. Original project unchanged, status `needs-review`, no automatic commit or merge, normal native confirmations retained. This was **not** enforced-Aider/cache/auth compatibility or a coding benchmark. [Evidence](AIDER_VALIDATION.json).
- Fresh user-local installation: actual outer TUI, persistent memory, nested shell writing a verified file, return to composer and confirmed zero-status exit. [Evidence](INSTALLED_VALIDATION.json). Repeat with `scripts/validate_install.py` using the installed environment's Python.
- Read-only `/doctor` and machine-readable `doctor --full` checks. Explicit loopback/kernel probes passed in the prepared local-model environment; a prerequisite check is not a generation or project-permission certification. [Instructions](READINESS.md).

## Remote CI baseline, not acceptance for every later commit

Source `408395fbf3e1820967d847904a595ea8fc0d0938`: [GitHub Actions run](https://github.com/HIDORAKAI002/agent-forge/actions/runs/38655729930).

- Linux 3.11 and 3.13: 101 passed, 16 skipped each.
- Actual pinned Ruflo integration suite: three passed.
- Windows 3.11: 44 passed, **seven failed**, four skipped.
- Windows 3.13 published only a partial failing result: four passed, three failed. It is **not** complete acceptance. Matrix fail-fast is now disabled so one failed job does not cancel its peer.

CI reporting now also requires a completed pytest execution record, zero process exit status, a matching source commit and actual passing tests. Interrupted, skipped-only, stale or invalid reports cannot be labeled passing. Each new commit still needs its own CI readback.

## Native Windows is NOT release-ready

Standard native Windows ConPTY terminals, process cleanup and installation are separate from the LPAC filesystem boundary. The experimental boundary still fails **exact original ACL restoration** (inherited ACE flags change) and **isolated console output/input**. File-access denial assertions alone do not make its cleanup safe. The unsuccessful bootstrap-token console experiment has been removed rather than retained as a purported fix.

Enforcement remains experimental and disabled by default. Cleanup mismatches retain the recovery journal; there is no silent unrestricted fallback. Standard-user/runtime compatibility, wider escapes, concurrent host mutation, network/local-Ollama behavior and independent security review remain open. macOS enforcement is unavailable.

## Ruflo and accounts

The full **advertised catalog** is exposed through the reviewed sandboxed CLI and Setup gateway. Actual memory, workflow and terminal tools were exercised with project-write/reference-read/denied-path/secret-filtering assertions. This does **not** certify every upstream backend or supply optional models, services, unsupported upstream implementations, cloud billing or authorization. Forge SQLite remains authoritative.

Local Ollama needs no account/key or consumer Pro subscription. Cloud inference needs a compatible provider key and its required billing/access; arbitrary provider API formats are not interchangeable. Microphone permission is a local OS permission, not a provider credential. Voice and OS-vault storage are optional; Codex native API-key authentication retains its documented vault requirement. Actual microphones, supported vaults and desired cloud CLI/accounts still need their own acceptance checks.
