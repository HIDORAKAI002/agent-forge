# Current acceptance status

## Working and verified

- Linux project-write/reference-read enforcement and actual upstream Ruflo discovery, schema validation, review, execution and result display.
- Real local regression: 94 passed, 12 native-Windows skips; see LOCAL_ACCEPTANCE.json.
- The real outer-TUI/nested-shell test passed three consecutive runs after synchronizing on committed memory rather than merely echoed input.

## Native Windows is NOT release-ready

Last native readback for source `309789e72e82faba2a927a11f83242478172bd93`: Windows/Python 3.13 had 38 passes, 2 failures, 4 skips. Run: https://github.com/HIDORAKAI002/agent-forge/actions/runs/38578586718

Git write protection, approved read access, external write/read denial, crash recovery and a late-junction escape check passed their assertions. Exact original ACL restoration and isolated interactive ConPTY startup still failed. The cleanup changes did not resolve these two failures. A further guard uses the same named-filesystem security query as the external test before removing the recovery journal; it still requires native CI, not Linux skips. The backend remains experimental and disabled by default. Standard-user/runtime compatibility, adversarial ACL mutation, network/local-Ollama and wider escape checks remain required.

## Ruflo scope

The advertised catalog is exposed through the reviewed CLI and Setup gateway. This does not certify every upstream backend or supply missing upstream functionality, optional dependencies, cloud billing or authorization. Forge SQLite remains authoritative and review gates remain in force.

## Accounts

Local Ollama requires no provider account/key or consumer Pro subscription. Cloud inference requires a compatible provider API key and whatever billing/access that provider requires. Microphone permission is a local OS permission, not a provider credential. OS secret storage and voice input are optional; Codex native key-auth integration has its documented vault requirement.
