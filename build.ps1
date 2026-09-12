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
$portableName = "CursorFence-Portable"
$portableExe = Join-Path $distPath "$portableName.exe"
$portableZip = Join-Path $distPath "$portableName-windows-x64.zip"
$installerExe = Join-Path $distPath "CursorFence-Installer.exe"
$iconPath = Join-Path $projectRoot "resources\CursorFence.ico"

if (-not $SkipSetup -or -not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $projectRoot "setup.ps1")
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $distPath | Out-Null
& $pythonPath (Join-Path $projectRoot "tools\create_icon.py") --output $iconPath --preview (Join-Path $projectRoot "resources\CursorFence.png")

# Directory mode avoids unpacking a large archive on every launch and lets
# Windows/antivirus tools inspect the bundled DLLs normally. Remove only the
# explicitly generated output directory before rebuilding.
if (Test-Path -LiteralPath $outputDir) {
    Remove-Item -LiteralPath $outputDir -Recurse -Force
}
foreach ($path in @($portableExe, $portableZip, $installerExe)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
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

# A single-file portable build is convenient for users who explicitly want
# one EXE.  The installed build below uses the onedir output for faster,
# steadier startup and normal Windows uninstall registration.
& $pythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $portableName `
    --icon $iconPath `
    --add-data "$iconPath;resources" `
    --version-file (Join-Path $projectRoot "resources\version_info.txt") `
    --collect-all pystray `
    --exclude-module PIL.AvifImagePlugin `
    --exclude-module PIL.WebPImagePlugin `
    --distpath $distPath `
    --workpath (Join-Path $buildRoot "pyinstaller-portable") `
    --specpath $buildRoot `
    (Join-Path $projectRoot "cursor_fence.py")

if ($LASTEXITCODE -ne 0) {
    throw "Portable EXE 打包失败（退出码：$LASTEXITCODE）。"
}

Compress-Archive -Path $portableExe -DestinationPath $portableZip -CompressionLevel Optimal

$issPath = Join-Path $projectRoot "installer\CursorFence.iss"
$isccPath = $null
$isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($null -ne $isccCommand) {
    $isccPath = $isccCommand.Source
} else {
    $knownIscc = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($knownIscc) {
        $isccPath = [string]$knownIscc
    }
}
if ($isccPath) {
    & $isccPath "/DMyAppVersion=0.2.2" $issPath
    if ($LASTEXITCODE -ne 0) {
        throw "安装包打包失败（退出码：$LASTEXITCODE）。"
    }
} else {
    Write-Warning "未找到 Inno Setup（ISCC.exe），已跳过安装包；安装包会由 CI 或安装 Inno Setup 后生成。"
}

Write-Host ""
Write-Host "完成：$outputDir\CursorFence.exe" -ForegroundColor Green
Write-Host "便携单文件：$portableExe" -ForegroundColor Green
Write-Host "便携 ZIP：$portableZip" -ForegroundColor Green
if (Test-Path -LiteralPath $installerExe) {
    Write-Host "安装包：$installerExe" -ForegroundColor Green
}
