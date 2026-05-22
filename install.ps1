param(
  [switch]$Daily,
  [switch]$Weekly,
  [switch]$NoSchedule
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Schedule = if ($NoSchedule) { "none" } elseif ($Daily) { "daily" } else { "weekly" }
$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

$env:PYTHONPATH = "$ScriptDir/src" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })
& $Python -m codex_coach.cli install --source-root "$ScriptDir" --schedule "$Schedule"

Write-Host ""
Write-Host "Codex Coach installed."
Write-Host "Restart Codex, then ask: Coach my Codex usage"
Write-Host "CLI: codex-coach doctor"
