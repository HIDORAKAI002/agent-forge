# Dependency and integration notices

Agent Forge's original application code is MIT-licensed. Dependencies are installed separately and retain their own licenses; they are not vendored in this source repository.

| Component | Tested version | License | Usage |
|---|---|---|---|
| Textual | 8.2.8 | MIT | Native terminal UI and interaction framework |
| Rich | see requirements-lock.txt | MIT | Text styling and screenshot export |
| pyte | 0.8.2 | LGPL-3.0 | Imported VT terminal emulator |
| ptyprocess | 0.7.0 | ISC | POSIX pseudo-terminal process backend |
| psutil | 7.2.2 | BSD-3-Clause | Known descendant-process lifecycle tracking |
| Python MCP SDK | 1.30.0 | MIT | Optional stdio project-memory/mail tools |
| pytest / pytest-asyncio | see lock file | MIT / Apache-2.0 | Development tests |

**pyte is LGPLv3, not MIT.** It is used as a separately installed, unmodified library; the app extends its interface in its own module. A bundled/frozen distribution must be reviewed for LGPL notice, source, relinking/replacement and other applicable obligations. This source repository does not claim the dependency is permissively licensed or sublicense it under MIT.

Dependency packages and their installed license files are the authoritative notices. Preserve those notices and satisfy the licenses when redistributing dependencies. Future speech-engine/model dependencies require a separate licensing review.

The UI reference is the user's AI Video Dubbing Textual studio. No dubbing source was copied. Ruflo, Handy, ACP and Beads are integration candidates only; their code is not present in this initial repository.
