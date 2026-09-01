[CmdletBinding()]
param(
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
$buildRoot = Join-Path $projectRoot "build"
$distPath = Join-Path $projectRoot "dist"
$outputName = "CursorFence"
$outputDir = Join-Path $distPath $outputName
$releaseZip = Join-Path $distPath "CursorFence-windows-x64.zip"
$iconPath = Join-Path $projectRoot "resources\CursorFence.ico"

if (-not $SkipSetup -or -not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $projectRoot "setup.ps1")
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $distPath | Out-Null
& $pythonPath (Join-Path $projectRoot "tools\create_icon.py") --output $iconPath

# Directory mode avoids unpacking a large archive on every launch and lets
# Windows/antivirus tools inspect the bundled DLLs normally. Remove only the
# explicitly generated output directory before rebuilding.
if (Test-Path -LiteralPath $outputDir) {
    Remove-Item -LiteralPath $outputDir -Recurse -Force
}
if (Test-Path -LiteralPath $releaseZip) {
    Remove-Item -LiteralPath $releaseZip -Force
}

& $pythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name $outputName `
    --icon $iconPath `
    --add-data "$iconPath;resources" `
    --version-file (Join-Path $projectRoot "resources\version_info.txt") `
    --collect-all pystray `
    --exclude-module PIL.AvifImagePlugin `
    --exclude-module PIL.WebPImagePlugin `
    --distpath $distPath `
    --workpath (Join-Path $buildRoot "pyinstaller") `
    --specpath $buildRoot `
    (Join-Path $projectRoot "cursor_fence.py")

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败（退出码：$LASTEXITCODE）。"
}

Compress-Archive -Path $outputDir -DestinationPath $releaseZip -CompressionLevel Optimal

Write-Host ""
Write-Host "完成：$outputDir\CursorFence.exe" -ForegroundColor Green
Write-Host "发布包：$releaseZip" -ForegroundColor Green
