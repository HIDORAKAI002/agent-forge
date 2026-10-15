# Current acceptance status

**This is a usable local-first development build, not an all-platform production/security release.** No consumer Pro subscription is required. The remaining gates below are real work, not credentials that can be skipped to turn tests green.

## Newly executed checks

- **138 passed, zero failed, 14 skipped** in the actual Linux/Python 3.13 regression, with all opt-in Bubblewrap and pinned Ruflo 3.56.9 tests enabled. Native Windows skips are not passes. [Machine-readable evidence](LOCAL_ACCEPTANCE.json) binds the tested source tree, not just the unchanged package version.
- Earlier actual Ollama 0.6.8 / Qwen2.5-Coder 1.5B CPU activation, generation, schema-valid bounded plan, embedded CLI and observed unload. No provider keys, paid API calls, queueing or dispatch in this check. [Evidence](OLLAMA_VALIDATION.json).
- Earlier actual Aider 0.86.2 + that local model edited one authorized file through Runtime/worktree dispatch; `add(2,3)==5`. Original project unchanged, status `needs-review`, no automatic commit or merge, normal native confirmations retained. This was **not** enforced-Aider/cache/auth compatibility or a coding benchmark. [Evidence](AIDER_VALIDATION.json).
- Earlier fresh user-local installation: actual outer TUI, persistent memory, nested shell writing a verified file, return to composer and confirmed zero-status exit. [Evidence](INSTALLED_VALIDATION.json). Repeat with `scripts/validate_install.py` using the installed environment's Python.
- Read-only `/doctor` and machine-readable `doctor --full` checks. Explicit loopback/kernel probes passed in the prepared local-model environment; a prerequisite check is not a generation or project-permission certification. [Instructions](READINESS.md).

## Native Windows is NOT release-ready

Latest fully read native prototype result: source `cbb073d318ba4e042f37c4506598c17036c07fb1`, [Windows 3.13 run](https://github.com/HIDORAKAI002/agent-forge/actions/runs/38669098415): **61 passed, eight failed, four skipped**. This is a failed research prototype, not acceptance for the final cleanup or later source commits.

Two approaches have now been ruled out on actual Windows: raising a low AppContainer token after creation needs unavailable privilege 1314, and creating the AppContainer token before launching still produces a non-medium token. An initial missing token-adjustment access right was corrected and re-tested before drawing that conclusion. The precreated-token prototype and all token-integrity modification calls have been removed. The suspended child is now checked read-only and refused before resume when its integrity is incompatible; no request for powerful privileges, automatic elevation or unrestricted fallback is made.

Disposable native API probes established that DACL-only grant/restore preserves original inherited flags, but changing filesystem integrity labels changes them. New boundaries do not modify those filesystem labels. The grant/restore-only test passes, but that is not end-to-end process/recovery acceptance. Earlier low-integrity runs failed isolated console output and label restoration; current refusal does not prove either fixed. Legacy mismatched recovery journals remain retained.

**A brokered writable-workspace and compatible low-integrity console design is still required and unimplemented.** It must preserve user-owned filesystem security, reconcile only approved project edits, handle cancellations/conflicts and pass actual native file-denial, console, exact restoration, interruption/descendant cleanup, coordinator-state protection, runtime/network/local-Ollama and wider escape tests. Standard Windows ConPTY terminal support is separate. Enforcement stays experimental and disabled by default; do not use its switch on valuable data or grant powerful privileges to force tests green. macOS enforcement and independent security review remain open.

CI reporting requires a completed pytest record, zero process exit status, a matching source commit and actual passing tests. Interrupted, skipped-only, stale or invalid reports cannot be labeled passing. Both Windows matrix jobs run independently.

## Ruflo and accounts

The full **advertised catalog** is exposed through the reviewed sandboxed CLI and Setup gateway. Actual memory store/retrieve/list/delete roundtrips, workflow create/list, task create/list, swarm initialize/status and empty agent listing were exercised in a disposable namespace, with no model agents started. Actual terminal execution verifies project writes, approved reference reads, denied paths and inherited-secret filtering. Creating a workflow or task is not executing it. This does **not** certify every upstream backend or supply optional models, services, unsupported upstream implementations, cloud billing or authorization. Forge SQLite remains authoritative.

Local Ollama needs no account/key or consumer Pro subscription. Cloud inference needs a compatible provider key and its required billing/access; arbitrary provider API formats are not interchangeable. Microphone permission is a local OS permission, not a provider credential. Voice and OS-vault storage are optional; Codex native API-key authentication retains its documented vault requirement. Actual microphones, supported vaults and desired cloud CLI/accounts still need their own acceptance checks.

## New reproducibility and error handling

- The optional runtime now includes an exact npm dependency lock, not just a CLI version pin. A clean `npm ci` replay installed 616 packages successfully; [runtime setup](RUFLO_RUNTIME.md) explains explicitly approved installs and runtime grants. No dependency/model binaries or credentials are bundled. This is not a dependency security audit.
- Explicit unsupported/not-implemented/error responses in both structured and JSON text results fail the reviewed batch and stop subsequent calls. User data and prose are not recursively treated as failure instructions. Timeouts/errors still do not roll back writes.
- The source bundle includes only the three reviewed runtime manifest/documentation files, excluding nested packages, dependencies and arbitrary credential JSON.
- Existing model/Aider/installed-launcher artifacts above are earlier real checks, not new inference/device tests in this pass. The current 138-pass regression is separately source-bound. Native Windows skips remain unaccepted.

## Additional completed hardening and coding checks

- Linux/WSL agents cannot write `.agent-forge` coordinator SQLite, task/approval/configuration records or other managed worktrees. An assigned task has only its own worktree writable; the original project and the assigned `.git` control file are read-only. An interactive project-root shell can edit project source, but not coordinator state/worktrees. Trusted parent Git setup remains separately constrained and can prepare worktrees.
- Pre-existing hard-linked project files are refused before enforced launches: read-only path overlays alone do not stop writable aliases. Copy such files instead of weakening the gate. The scan is bounded to 100,000 regular file entries and does not follow directory symlinks. Concurrent host-side filesystem mutation is unsupported.
- Real kernel tests verify denied SQLite/profile/approval/Git-file/original-project/other-worktree writes, allowed assigned-tree edits and the hardlink refusal. Enforced agents report handoffs in terminal output or via an explicitly attached trusted host MCP service; they do not directly update coordinator storage.
- Real multi-file worker processes pass success, nonzero-exit, dependency-review, cancellation, preserved-partial-edit and reopen-without-rerun tests. These deterministic fixtures are not model-quality evidence.
- Separately, actual Aider 0.86.2 and local Ollama/Qwen2.5-Coder 1.5B edited **two authorized files inside the stricter Linux boundary**. Arithmetic assertions and exact README contents passed; originals stayed unchanged; status was `needs-review`, with no model commit/merge or disabled CLI confirmations. [Source-bound evidence](ENFORCED_CODING_VALIDATION.json). This uses explicitly approved host networking to reach local Ollama, not a loopback-only firewall. Repeat with `scripts/validate_local_coding.py`; this remains a smoke test, not a coding benchmark or Windows acceptance.

Parent-side Git commands, including repository filters, are also denied coordinator/profile/approval/original-source/sibling-worktree writes. Their only persistent writable paths are Git metadata and, for checkout, one explicitly assigned existing empty worktree target. A real kernel regression tests both allowed writes and denied authority/source/sibling writes.
