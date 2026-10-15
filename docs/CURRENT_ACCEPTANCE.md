# Current acceptance status

**This is a usable local-first development build, not an all-platform production/security release.** No consumer Pro subscription is required. The remaining gates below are real work, not credentials that can be skipped to turn tests green.

## Newly executed checks

- **131 passed, zero failed, 14 skipped** in the actual Linux/Python 3.13 regression, with all opt-in Bubblewrap and pinned Ruflo 3.56.9 tests enabled. Native Windows skips are not passes. [Machine-readable evidence](LOCAL_ACCEPTANCE.json) binds the tested source tree, not just the unchanged package version.
- Earlier actual Ollama 0.6.8 / Qwen2.5-Coder 1.5B CPU activation, generation, schema-valid bounded plan, embedded CLI and observed unload. No provider keys, paid API calls, queueing or dispatch in this check. [Evidence](OLLAMA_VALIDATION.json).
- Earlier actual Aider 0.86.2 + that local model edited one authorized file through Runtime/worktree dispatch; `add(2,3)==5`. Original project unchanged, status `needs-review`, no automatic commit or merge, normal native confirmations retained. This was **not** enforced-Aider/cache/auth compatibility or a coding benchmark. [Evidence](AIDER_VALIDATION.json).
- Earlier fresh user-local installation: actual outer TUI, persistent memory, nested shell writing a verified file, return to composer and confirmed zero-status exit. [Evidence](INSTALLED_VALIDATION.json). Repeat with `scripts/validate_install.py` using the installed environment's Python.
- Read-only `/doctor` and machine-readable `doctor --full` checks. Explicit loopback/kernel probes passed in the prepared local-model environment; a prerequisite check is not a generation or project-permission certification. [Instructions](READINESS.md).

## Native Windows is NOT release-ready

Latest fully read native results: source `507d827232df96558195304444305267f8b66467`, [Windows 3.11/3.13 run](https://github.com/HIDORAKAI002/agent-forge/actions/runs/38666720249): **61 passed, seven failed, four skipped on each Python version**. These results are failures, not approval for later commits. Subsequent source commits need their own reports.

Disposable native API probes established that DACL-only grant/restore preserves original inherited flags, but changing filesystem integrity labels changes them, even when full security-descriptor control flags are preserved. New experimental boundaries therefore no longer lower project filesystem labels. They instead attempt a medium-integrity LPAC child token, verify the AppContainer SID before/after, and retain the LPAC ALL APPLICATION PACKAGES opt-out. A real denial test covers files granted broadly to ordinary AppContainers.

**This approach is not accepted:** native process tests fail with Windows error **1314, required token privilege not held**, before the child is resumed. The grant/restore-only test passes, but that is not end-to-end process/recovery acceptance. Earlier low-integrity process runs failed isolated console output and exact label restoration. The latest startup refusal prevents those gates being tested; it does not prove they are fixed. There is no automatic elevation, privilege granting or unrestricted fallback. Legacy journals with restoration mismatches are retained, not silently discarded.

Enforcement remains experimental and disabled by default. Do not use the experimental switch with valuable data or grant the application powerful OS privileges to force tests green. A supported standard-user design must pass actual isolated console input/output, filesystem denial, exact restoration, interruption/descendant cleanup, runtime/network/local-Ollama compatibility and wider escape tests before release. Standard Windows ConPTY terminal support is separate; macOS enforcement is unavailable. Independent security review remains open.

CI reporting requires a completed pytest record, zero process exit status, a matching source commit and actual passing tests. Interrupted, skipped-only, stale or invalid reports cannot be labeled passing. Both Windows matrix jobs run independently.

## Ruflo and accounts

The full **advertised catalog** is exposed through the reviewed sandboxed CLI and Setup gateway. Actual memory store/retrieve/list/delete roundtrips, workflow create/list, task create/list, swarm initialize/status and empty agent listing were exercised in a disposable namespace, with no model agents started. Actual terminal execution verifies project writes, approved reference reads, denied paths and inherited-secret filtering. Creating a workflow or task is not executing it. This does **not** certify every upstream backend or supply optional models, services, unsupported upstream implementations, cloud billing or authorization. Forge SQLite remains authoritative.

Local Ollama needs no account/key or consumer Pro subscription. Cloud inference needs a compatible provider key and its required billing/access; arbitrary provider API formats are not interchangeable. Microphone permission is a local OS permission, not a provider credential. Voice and OS-vault storage are optional; Codex native API-key authentication retains its documented vault requirement. Actual microphones, supported vaults and desired cloud CLI/accounts still need their own acceptance checks.

## New reproducibility and error handling

- The optional runtime now includes an exact npm dependency lock, not just a CLI version pin. A clean `npm ci` replay installed 616 packages successfully; [runtime setup](RUFLO_RUNTIME.md) explains explicitly approved installs and runtime grants. No dependency/model binaries or credentials are bundled. This is not a dependency security audit.
- Explicit unsupported/not-implemented/error responses in both structured and JSON text results fail the reviewed batch and stop subsequent calls. User data and prose are not recursively treated as failure instructions. Timeouts/errors still do not roll back writes.
- The source bundle includes only the three reviewed runtime manifest/documentation files, excluding nested packages, dependencies and arbitrary credential JSON.
- Existing model/Aider/installed-launcher artifacts above are earlier real checks, not new inference/device tests in this pass. The current 131-pass regression is separately source-bound. Native Windows skips remain unaccepted.
