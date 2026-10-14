# Native Windows filesystem boundary — acceptance build, not release-enabled

The new native implementation uses a Less Privileged AppContainer (LPAC), not WSL, a working-directory convention, or a process-cleanup Job Object alone. It is behind `FORGE_WINDOWS_ISOLATION_EXPERIMENTAL=1` until real Windows acceptance tests and recovery/escape checks pass. Do not describe it as production-ready based on Linux skips.

- Windows 10 build 17763+; pywin32 and built-in AppContainer/ConPTY APIs. No consumer Pro account, WSL or third-party kernel driver.
- One protected process tree per user at a time. A trusted lock outside granted folders prevents concurrent permission mutation. Parallel protected Windows trees are not supported in this first backend.
- Unique temporary profile/SID per tree. Project objects are read/write; Git control files read-only for agents. Parent Git helpers use the same OS boundary, serialized before agents.
- Approved references and non-system CLI runtime folders are read-only grants. No whole-user-home grant. Runtime grants must be explicitly reviewed; granting an installed runtime requires permission to edit its ACL. Unsupported permissions fail closed—no automatic elevation.
- Temporary project ACL entries and low-integrity labels are journaled before modification, restored after the complete Job Object tree exits, and recovered on the next launch after interruption. Linked/reparse/hard-linked grant inputs are refused.
- Child environment drops unrelated keys and startup hooks. Selected managed provider keys may still be intentionally passed to their corresponding CLI.
- Networking is blocked by default. Explicit host-network approval uses AppContainer network capabilities; loopback access additionally needs an administrator-approved OS exemption for that unique profile. The backend never disables the firewall or requests automatic elevation.
- Real isolated ConPTY for interactive CLI sessions; isolated standard I/O for MCP and parent-side helpers.

Remaining acceptance gates include native test results, post-launch junction/hard-link attempts, descendant cleanup, interruption recovery, standard-user/runtime compatibility, and local Ollama loopback behavior. A failed cleanup retains its journal and does not silently run unrestricted.
