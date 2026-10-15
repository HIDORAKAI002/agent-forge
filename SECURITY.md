# Security policy

Agent Forge v0.5 is an early-access development build, not a security-certified release. Linux/WSL enforcement has recorded tests, not a guarantee against every escape. Native Windows enforcement is unfinished and disabled by default; macOS enforcement is unavailable. Native terminal support does not imply filesystem isolation.

## Reporting privately

Do not post credentials, private paths/data, or a working exploit against user data in a public issue. Use GitHub's **Report a vulnerability** option in this repository's Security tab if available. If that option is unavailable, contact the maintainer through the public contact methods on [their GitHub profile](https://github.com/HIDORAKAI002) and request a private channel before sending sensitive details. No private contact address is invented here.

Include affected commit, OS/build, minimal reproduction on disposable data, impact, expected boundary and redacted logs. Ordinary non-sensitive bugs can use the issue templates. No response SLA or bug bounty is promised.

## Safe use

Use disposable projects initially. Review folder and network grants. Network approval exposes host networking, not a provider-domain firewall. Reference/project files may themselves contain secrets. Existing sessions retain their old permissions. Review upstream calls and model edits; failures/timeouts do not undo writes. Do not enable experimental Windows isolation on valuable files, run as administrator to bypass failures, grant SeTcbPrivilege, or accept unrestricted fallback. Maintain independent backups.
