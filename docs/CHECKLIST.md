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
- [x] Keep permission policy outside agent-writable storage; no unsandboxed fallback.
- [x] Add reviewed GUI permissions, per-session isolation labels and grant-revoking policy changes.
- [x] Implement Windows ConPTY, workspace locking, Job Object cleanup and native npm entrypoint resolution.
- [x] Write a user-local native PowerShell installer and placeholder launcher.
- [x] Add four real Windows acceptance tests and automatic CI result publication.
- [x] Re-test the standalone Linux installer/launcher and existing regressions.

## Acceptance gates still open

- [ ] Confirm Windows 3.11/3.13 CI passes for the current source commit. Linux skips do not count.
- [ ] Confirm remote Linux and live-Ruflo CI passes for the current source commit.
- [ ] Implement and adversarially test equivalent native Windows folder isolation. ConPTY/Job Objects alone do not restrict filesystem access.
- [ ] Validate real provider accounts and local Ollama/Aider combinations, including sandbox cache/auth behavior.
- [ ] Test microphones, OS credential stores and macOS behavior on actual devices.
- [ ] Independent security review and wider escape tests; current Linux checks are meaningful, not an absolute security guarantee.

## Deliberately not claimed

- Every upstream Ruflo feature integrated: browser/federation/autopilot/hive-mind executors are not enabled.
- Automatic retries, paid-model authorization or merges without human policy/review.
- Domain-only network firewall when host networking is permitted.
- A service that continues coding after this agent session stops. CI can run and publish test results independently, but it does not autonomously redesign the application.

## Automatic verification

A push to `main` starts Linux, native Windows and pinned-Ruflo CI when GitHub Actions is enabled. Each suite publishes a bounded JSON record to `validation:docs/ci/` with its source commit and run URL. Do not mark a gate passed using a record for an older commit. If repository/organization policy blocks Actions or write-scoped CI tokens, that is an external blocker—not a test pass.
