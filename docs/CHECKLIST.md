# Integration checklist — v0.5

Checked means implemented and supported by the stated evidence, not that every provider/device/security scenario is solved.

## Completed

- [x] Audit Ruflo entrypoints, schemas, license and version; pin 3.56.9.
- [x] Connect the actual Ruflo stdio MCP service; no provider secrets inherited.
- [x] Build a derived semantic memory index; canonical Forge records retain identity/trust.
- [x] Test actual memory retrieval and advisory model routing without agent execution.
- [x] Feed retrieved context/routing hints into the existing review-gated planning workflow.
- [x] Implement one writable project + explicit read-only reference grants on Linux/WSL.
- [x] Test project writes, approved reads, blocked reference writes, hidden-path reads/writes, symlink escapes, network denial and inherited-secret removal with real Bubblewrap.
- [x] Keep permission policy and Ruflo host state outside agent-writable storage; no unsandboxed fallback.
- [x] Protect Git control metadata from agent edits; constrain parent Git helpers and test hostile filters/hooks.
- [x] Add reviewed GUI permissions, per-session isolation labels and grant-revoking policy changes.
- [x] Implement Windows ConPTY, workspace locking, Job Object cleanup and native npm entrypoint resolution.
- [x] Write a user-local native PowerShell installer and placeholder launcher.
- [x] Add four real Windows acceptance tests and automatic CI result publication.
- [x] Re-test the standalone Linux installer/launcher and existing regressions.

## Acceptance gates still open

- [x] Native Windows 3.11/3.13 CI for `636c6be`: 19 passed, two skipped each; all four native acceptance tests passed. Later changes still require new reports.
- [x] Linux 3.11/3.13 CI for `636c6be`: 76 passed, five skipped each; actual Ruflo: one passed.
- [ ] Implement and adversarially test equivalent native Windows folder isolation. ConPTY/Job Objects alone do not restrict filesystem access.
- [x] Validate actual local Ollama/Qwen2.5-Coder 1.5B CPU activation, generation, bounded planning, embedded CLI and confirmed unload.
- [x] Validate a real Aider 0.86.2 + Ollama 1.5B coding task through Runtime/worktree dispatch: add(2,3)=5, needs-review, original unchanged, no automatic commit/merge.
- [ ] Validate real provider accounts, broader Aider coding and sandbox/cache/auth combinations.
- [ ] Test microphones, OS credential stores and macOS behavior on actual devices.
- [ ] Independent security review and wider escape tests; current Linux checks are meaningful, not an absolute security guarantee.

## Deliberately not claimed

- Every upstream Ruflo backend certified: broader catalog access exists only through the reviewed sandboxed gateway; optional dependencies and unsupported implementations are not magically supplied.
- Automatic retries, paid-model authorization or merges without human policy/review.
- Domain-only network firewall when host networking is permitted.
- A service that continues coding after this agent session stops. CI can run and publish test results independently, but it does not autonomously redesign the application.

## Automatic verification

A push to `main` starts Linux, native Windows and pinned-Ruflo CI when GitHub Actions is enabled. Each suite publishes a bounded JSON record to `validation:docs/ci/` with its source commit and run URL. Do not mark a gate passed using a record for an older commit. If repository/organization policy blocks Actions or write-scoped CI tokens, that is an external blocker—not a test pass.

## First remote run and hardening

Commit `f6721f5`: live Ruflo passed; Linux sandbox startup failed on Ubuntu 24.04 host policy; Windows found a Path/string error and native ConPTY interpreter-shutdown crash. These are failures, not passes. Current changes enforce user namespaces explicitly, use Ubuntu 22.04 integration runners without disabling host security, normalize Windows disk paths, and terminate the isolated ConPTY broker after Job cleanup without racing native-reader finalizers. New adversarial Git/state tests pass locally; remote acceptance must be checked for the new commit. Restricted hosts still fail closed.

## Real-model follow-up

The 1.5B model passed the functional smoke test; 0.5B generated invalid dependencies, correctly refused without execution. This is not a coding-quality benchmark. Ollama can acknowledge unload before `/api/ps` clears: Forge now waits for observed residency removal, with bounded timeout/cancellation. Evidence and repeatable opt-in script are included.

- [x] Add a state-free source installer bundle, manifest hashes and native Windows/Linux installation instructions.

- [x] Refuse agent-writable Ruflo executables/entrypoints and remove project/relative directories from the host service PATH.
- [x] Install the source ZIP into a fresh user-local environment and test the real outer TUI, persistent memory, nested shell and confirmed exit.

## Broader Ruflo follow-up

- [x] Inspect the pinned runtime's complete advertised MCP catalog (381 tools observed).
- [x] Add an explicit full-catalog gateway requiring enforced project isolation, no ambient keys and exact batch-review digest.
- [x] Bind approval to arguments, tool definitions, project and permissions; validate every request before executing any.
- [x] Keep upstream errors and timeouts visible; do not imply rollback or full backend implementation.
- [ ] Certify every upstream tool/backend end-to-end; optional dependencies and upstream unsupported operations remain real limitations.
- [ ] Native Windows filesystem enforcement (not supplied by ConPTY/Job Objects, no unrestricted fallback).
- [x] Launch trusted Python brokers and generated application commands in isolated Python mode; project `forge/`, `sitecustomize.py` and `PYTHONPATH` must not replace host-side code.
