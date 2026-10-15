# Native Windows filesystem boundary — acceptance build, not release-enabled

The new native implementation uses a Less Privileged AppContainer (LPAC), not WSL, a working-directory convention, or a process-cleanup Job Object alone. It is behind `FORGE_WINDOWS_ISOLATION_EXPERIMENTAL=1` until real Windows acceptance tests and recovery/escape checks pass. Do not describe it as production-ready based on Linux skips.

- Windows 10 build 17763+; pywin32 and built-in AppContainer/ConPTY APIs. No consumer Pro account, WSL or third-party kernel driver.
- One protected process tree per user at a time. A trusted lock outside granted folders prevents concurrent permission mutation. Parallel protected Windows trees are not supported in this first backend.
- Unique temporary profile/SID per tree. Project objects are read/write; Git control files read-only for agents. Parent Git helpers use the same OS boundary, serialized before agents.
- Approved references and non-system CLI runtime folders are read-only grants. No whole-user-home grant. Runtime grants must be explicitly reviewed; granting an installed runtime requires permission to edit its ACL. Unsupported permissions fail closed—no automatic elevation.
- Temporary project ACL entries and low-integrity labels are journaled before modification, restored after the complete Job Object tree exits, and recovered on the next launch after interruption. Linked/reparse/hard-linked grant inputs are refused.
- Child environment drops unrelated keys and startup hooks. Selected managed provider keys may still be intentionally passed to their corresponding CLI.
- Networking is blocked by default. Explicit host-network approval uses AppContainer network capabilities; loopback access additionally needs an administrator-approved OS exemption for that unique profile. The backend never disables the firewall or requests automatic elevation.
- Separate attempted ConPTY and standard-I/O paths. **Isolated ConPTY is not accepted:** output/input still fail on native CI. Standard-I/O access assertions work, but exact permission restoration still fails, so that path is not release-ready either.

Remaining acceptance gates include native test results, post-launch junction/hard-link attempts, descendant cleanup, interruption recovery, standard-user/runtime compatibility, and local Ollama loopback behavior. A failed cleanup retains its journal and does not silently run unrestricted.

## Acceptance findings

Native CI found that appending denial ACEs after inherited project grants did not protect Git metadata. The implementation now inserts explicit profile denials first using the Windows SDDL parser and avoids automatic inheritance propagation during setup. Original project DACLs are journaled and restored after process-tree termination; do not edit host ACLs concurrently while a boundary is active. Crash recovery checks the recorded child process identity before restoring grants. These changes require native CI readback; they are not a release-enable decision. The isolated interactive ConPTY startup gate is still unresolved.

Current native readback still changes original inherited ACE flags during restoration and fails isolated console output. The recovery journal remains instead of silently declaring success. See [current acceptance](CURRENT_ACCEPTANCE.md); do not enable this backend for valuable user data based on the existence of its implementation.
