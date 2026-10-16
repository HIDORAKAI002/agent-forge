param([switch]$Voice)
$ErrorActionPreference = 'Stop'
$command = if ($env:FORGE_COMMAND) { $env:FORGE_COMMAND } else { 'agent-command' }
if ($command -notmatch '^[a-z][a-z0-9-]{0,39}$' -or $command -match '^(con|prn|aux|nul|com[0-9]|lpt[0-9])$') { throw 'Invalid launch command name' }
$root = if ($env:FORGE_INSTALL_ROOT) { $env:FORGE_INSTALL_ROOT } else { Join-Path $env:LOCALAPPDATA 'AgentForge' }
$bin = if ($env:FORGE_BIN_ROOT) { $env:FORGE_BIN_ROOT } else { Join-Path $env:LOCALAPPDATA 'AgentForgeBin' }
function SafePath($path) {
    $p = [IO.Path]::GetFullPath($path)
    while ($p) {
        if (Test-Path $p) { if ((Get-Item -Force $p).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing linked install path: $p" } }
        $parent = Split-Path -Parent $p
        if ($parent -eq $p) { break }; $p = $parent
    }
}
SafePath $root; SafePath $bin
New-Item -ItemType Directory -Force $root,$bin | Out-Null
$launcher = Join-Path $bin "$command.cmd"
if ((Test-Path $launcher) -and -not ((Get-Content -Raw $launcher).StartsWith('REM Agent Forge managed launcher'))) { throw 'Refusing to overwrite unrelated command' }
$source = Split-Path -Parent $PSScriptRoot
$python = if ($env:FORGE_PYTHON) { $env:FORGE_PYTHON } elseif (Get-Command python.exe -ErrorAction SilentlyContinue) { 'python.exe' } else { 'py' }
& $python -I -c 'import sys;assert sys.version_info >= (3,11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11+ first' }
$venv = Join-Path $root 'venv'; SafePath $venv
& $python -I -m venv $venv
if ($LASTEXITCODE -ne 0) { throw 'Unable to create package environment' }
$exe = Join-Path $venv 'Scripts\python.exe'
$extras = 'mcp,credentials'; if ($Voice -or $env:FORGE_VOICE -eq '1') { $extras += ',voice' }
& $exe -I -m pip install --upgrade "$source`[$extras`]"
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed' }
$entry = $exe
[IO.File]::WriteAllText($launcher, "REM Agent Forge managed launcher`r`n@echo off`r`nchcp 65001 >nul`r`n`"$entry`" -I -m forge %*", [Text.UTF8Encoding]::new($false))
if ($env:FORGE_CONFIGURE_PATH -ne '0') {
    $old = [Environment]::GetEnvironmentVariable('Path','User')
    if (-not (($old -split ';') -contains $bin)) {
        Set-Content (Join-Path $root 'user-path-backup.txt') $old
        [Environment]::SetEnvironmentVariable('Path',(([string]$old).TrimEnd(';')+';'+$bin).TrimStart(';'),'User')
    }
}
$env:Path = "$bin;$env:Path"
Write-Host "Installed. Temporary command: $command. New terminal: $command --project C:\path\to\project"
Write-Host "Current PowerShell: & '$launcher'. Provider CLIs and Ollama are separate, confirmed installs. No WSL required for the TUI. Windows OS sandbox is not available."
