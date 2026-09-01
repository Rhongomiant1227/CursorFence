 [CmdletBinding()]
param(
    [string]$PythonExecutable
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    $preferredPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"
    if (-not [string]::IsNullOrWhiteSpace($PythonExecutable)) {
        & $PythonExecutable -m venv $venvPath
    } elseif (Test-Path -LiteralPath $preferredPython) {
        # Prefer the official CPython install when available. It bundles a
        # self-contained Tcl/Tk runtime, which makes PyInstaller builds far
        # more portable than some Conda installations.
        & $preferredPython -m venv $venvPath
    } elseif ($null -ne (Get-Command py -ErrorAction SilentlyContinue)) {
        $pyLauncher = Get-Command py -ErrorAction Stop
        & $pyLauncher.Source -3 -m venv $venvPath
    } else {
        $pythonCommand = Get-Command python -ErrorAction Stop
        & $pythonCommand.Source -m venv $venvPath
    }
}

& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -r (Join-Path $projectRoot "requirements-dev.txt")

Write-Host "虚拟环境已准备：$venvPath"
Write-Host "依赖已安装。运行 .\run.ps1 启动程序，或运行 .\build.ps1 生成 EXE。"
