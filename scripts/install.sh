#!/usr/bin/env bash
# User-local, dependency-isolated installer. Run from an authorized repository clone.
set -euo pipefail
if [[ ${OS:-} == Windows_NT ]]; then
  echo 'Native Windows is not supported yet. Run this installer inside WSL.' >&2; exit 1
fi
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON=${FORGE_PYTHON:-python3}
COMMAND_NAME=${FORGE_COMMAND:-agent-command}
INSTALL_ROOT=${FORGE_INSTALL_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/agent-forge}
BIN_ROOT=${FORGE_BIN_ROOT:-$HOME/.local/bin}
[[ "$COMMAND_NAME" =~ ^[a-zA-Z][a-zA-Z0-9_-]{0,47}$ ]] || { echo 'Invalid command placeholder/name' >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo 'Install Python 3.11+ first.' >&2; exit 1; }
"$PYTHON" -I -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
[[ ! -L "$INSTALL_ROOT" ]] || { echo 'Refusing symlinked install directory' >&2; exit 1; }
mkdir -p -- "$INSTALL_ROOT" "$BIN_ROOT"
chmod 700 -- "$INSTALL_ROOT"
VENV="$INSTALL_ROOT/venv"
[[ ! -L "$VENV" ]] || { echo 'Refusing symlinked application environment' >&2; exit 1; }
DEST="$BIN_ROOT/$COMMAND_NAME"
[[ ! -L "$DEST" ]] || { echo 'Refusing to overwrite a symlink command' >&2; exit 1; }
if [[ -e "$DEST" ]] && ! grep -q '^# Agent Forge managed launcher$' "$DEST"; then
  echo 'Command already exists and is not managed by Agent Forge. Choose FORGE_COMMAND.' >&2; exit 1
fi
echo '[1/3] Preparing isolated application environment'
[[ -x "$VENV/bin/python" ]] || "$PYTHON" -I -m venv "$VENV"
EXTRAS='mcp,credentials'
[[ ${FORGE_VOICE:-0} != 1 ]] || EXTRAS+=',voice'
echo '[2/3] Installing application and selected dependencies'
# Regular installation copies package files: the source checkout can be removed afterward.
"$VENV/bin/python" -I -m pip install "$ROOT[$EXTRAS]"
echo '[3/3] Creating single-command launcher'
TARGET="$VENV/bin/python" LAUNCHER="$DEST" "$VENV/bin/python" -I - <<'PY'
import os, shlex
from pathlib import Path
p=Path(os.environ['LAUNCHER'])
p.write_text('#!/usr/bin/env bash\n# Agent Forge managed launcher\nexec '+shlex.quote(os.environ['TARGET'])+' -I -m forge "$@"\n')
p.chmod(0o700)
PY
printf '\nInstalled. Temporary launch command: %s\n' "$COMMAND_NAME"
if [[ :$PATH: != *:"$BIN_ROOT":* ]]; then
  printf 'Add this directory to PATH: %s\n' "$BIN_ROOT"
  printf 'Current shell: export PATH=%q:"$PATH"\n' "$BIN_ROOT"
fi
printf 'Run %q --project /path/to/project\n' "$DEST"
if [[ ${FORGE_CONFIGURE_PATH:-1} == 1 ]]; then
  BIN_ROOT="$BIN_ROOT" "$VENV/bin/python" -I - <<'PY'
import os, shlex
from pathlib import Path
home=Path.home()
shell=Path(os.environ.get('SHELL','/bin/bash')).name
names=['.zshrc'] if shell=='zsh' else ['.bashrc','.profile'] if shell=='bash' else []
block='\n# BEGIN AGENT FORGE PATH\nexport PATH='+shlex.quote(os.environ['BIN_ROOT'])+':"$PATH"\n# END AGENT FORGE PATH\n'
for name in names:
    p=home/name
    if p.is_symlink():
        print('Skipped symlinked shell profile:',name)
        continue
    text=p.read_text() if p.exists() else ''
    if '# BEGIN AGENT FORGE PATH' not in text:
        if p.exists():
            backup=p.with_name(p.name+'.agent-forge-backup')
            if not backup.exists() and not backup.is_symlink():
                backup.write_text(text);backup.chmod(0o600)
        p.write_text(text+block)
if names: print('PATH configured for new shells. In the current shell, use the export command printed above.')
else: print('Configure PATH manually for your shell; no profile was modified.')
PY
fi
echo 'Provider CLIs, Ollama and speech models are separate installs. Setup shows instructions; no system installer was silently run.'
if [[ ${FORGE_VOICE:-0} == 1 ]]; then echo 'Linux microphone capture may also require your distribution’s PortAudio package. No sudo commands were run.'; fi
