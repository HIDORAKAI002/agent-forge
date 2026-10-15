# Public launch and contributor report

## Evidence baseline

This report describes source commit `96792b561bb75bfcf19f37e9522f7e8d32500de2`; the launch documentation commit is separate. It is an early-access engineering report, not security certification or a claim all platforms/backends pass.

| Recorded run | Passed | Failed | Skipped | Scope |
| --- | ---: | ---: | ---: | --- |
| Local acceptance | 138 | 0 | 14 | Real Linux kernel / pinned Ruflo prerequisites enabled; platform skips remain |
| GitHub Linux Python 3.13 | 135 | 0 | 17 | CI baseline; optional checks differ from local acceptance |
| GitHub Windows Python 3.13 | 61 | 7 | 7 | Native Windows test selection including experimental isolation; **not accepted** |

Sources: [local JSON](LOCAL_ACCEPTANCE.json), [current acceptance](CURRENT_ACCEPTANCE.md), [CI run 38670293509](https://github.com/HIDORAKAI002/agent-forge/actions/runs/38670293509). Machine-readable CI reports are published on the `validation` branch under `docs/ci/`, not inferred from screenshots. These are recorded baseline results, not a claim about every later documentation commit.

## What was actually demonstrated

An actual local Aider 0.86.2 + Ollama 0.6.8 / Qwen2.5-Coder 1.5B CPU workflow edited a calculator and README inside the hardened Linux assigned-worktree boundary. Assertions checked both outputs; originals were unchanged and the task remained `needs-review`. There was no automatic model commit/merge or paid call. Host networking was explicitly approved, not restricted to provider domains. See [enforced coding evidence](ENFORCED_CODING_VALIDATION.json).

Native CLI sessions, project memory/mail, review-gated tasks/worktrees, local model management, optional dictation and a reviewed pinned Ruflo gateway are implemented. Discovery of the advertised Ruflo catalog does **not** certify every upstream backend.

## Open release blockers

1. **Windows isolation:** ordinary ConPTY terminals are separate from enforced folder access. The experimental LPAC launch refuses before resume because its token is not medium-integrity; a brokered writable workspace/console architecture remains necessary. Raising integrity or unrestricted fallback is refused. Keep the feature disabled by default.
2. **Upstream backend acceptance:** reproduce each Ruflo family with its actual dependencies and record success/failure/unsupported cases. No blanket 'full upstream certified' claim.
3. **Real-machine/device matrix:** normal-user Windows installs and terminals, microphone/local transcription, OS vaults and macOS behavior.
4. **Security review:** expand adversarial boundary/link/process tests and obtain independent review. Passing a finite suite is not proof of perfect isolation.

## Publication preparation

Added contribution/credits/security guides, test instructions, issue/PR templates, explicit help-wanted issues, resource attribution and a LinkedIn launch kit. Public-source claims should remain scoped to the evidence above. A targeted snapshot secret scan is not a full Git-history security audit; do not describe it as one.

Start at [CONTRIBUTING.md](../CONTRIBUTING.md). Fork, reproduce and open a focused PR. No paid account is required for baseline contributions.
