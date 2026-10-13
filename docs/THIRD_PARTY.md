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

Dependency packages and their installed license files are the authoritative notices. Preserve those notices and satisfy the licenses when redistributing dependencies. Optional speech-engine/model dependencies require their own notices and redistribution review.

The UI reference is the user's AI Video Dubbing Textual studio. No dubbing source was copied. Handy, ACP and Beads remain references. Ruflo is a separately installed runtime integration as of v0.5; none of their upstream source is vendored.


## v0.4 optional dependencies and adapters

- **keyring 25.7.0**: separately installed Python credential-store client; retain its MIT license and backend dependency notices. Only approved native OS vault backends are used; no file fallback.
- **faster-whisper 1.2.1**: MIT transcription code, separately installed through the voice extra. CTranslate2, sounddevice, PortAudio, NumPy, PyAV, ONNX Runtime, Hugging Face tooling and model weights have their own notices/licenses. Installer includes their installed license files; this repository does not relicense them.
- **sounddevice 0.5.6**: optional separately installed PortAudio client; retain its MIT license and system PortAudio notices. No system audio library is silently installed.
- **Aider**: optional external executable adapter; no Aider source or executable is bundled. Its own license, dependencies and provider policies apply.
- **Handy**, **whisper.cpp**: researched references only; no source has been copied. Handy's code license does not grant its branding rights.

Before creating a frozen/bundled binary, audit the complete dependency graph, speech-model licenses and existing LGPL obligations. The current installer uses separately installed Python distributions, not a proprietary frozen bundle.

## v0.5 runtime adapters

- Ruflo 3.56.9 / @claude-flow/cli: MIT upstream; invoked as an optional separately installed MCP service. Audit reference commit `55e2c9011c20d25e347a175427ca8084dacde40c`. No Ruflo source is vendored. Its transitive dependencies and downloaded model assets have their own licenses.
- Bubblewrap: LGPL-2.0-or-later upstream executable, installed separately by users/distributions, not vendored. Actual test version 0.11.0. Local test builds and libcap artifacts are not included in this repo.
- pywinpty: MIT, platform-conditional Python dependency for native Windows ConPTY; tested API audit version 3.0.5. Real Windows CI is required before claiming native validation.

Upstream: https://github.com/ruvnet/ruflo · https://github.com/containers/bubblewrap · https://github.com/andfoy/pywinpty
