$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $projectRoot "setup.ps1")
}

& $pythonPath -c "import PIL, pystray" 2>$null
if ($LASTEXITCODE -ne 0) {
    & (Join-Path $projectRoot "setup.ps1")
}

& $pythonPath (Join-Path $projectRoot "cursor_fence.py")
