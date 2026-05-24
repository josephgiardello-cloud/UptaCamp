param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$AppName = "CribbageGame",
    [string]$ZipName = "CribbageGame-Windows-Test.zip",
    [switch]$OneFile,
    [switch]$SkipPip,
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($repoRoot)) {
    $repoRoot = (Get-Location).Path
}

Push-Location $repoRoot
try {
    if (-not (Test-Path $PythonExe)) {
        throw "Python executable not found at '$PythonExe'. Create the venv first or pass -PythonExe."
    }

    if ($Clean) {
        if (Test-Path ".\build") { Remove-Item ".\build" -Recurse -Force }
        if (Test-Path ".\dist") { Remove-Item ".\dist" -Recurse -Force }
        if (Test-Path ".\$AppName.spec") { Remove-Item ".\$AppName.spec" -Force }
        if (Test-Path ".\$ZipName") { Remove-Item ".\$ZipName" -Force }
    }

    if (-not $SkipPip) {
        & $PythonExe -m pip install --upgrade pip
        & $PythonExe -m pip install pyinstaller
    }

    $bundleMode = if ($OneFile) { "--onefile" } else { "--onedir" }

    & $PythonExe -m PyInstaller --noconfirm --clean --windowed $bundleMode --name $AppName `
        --add-data "assets;assets" `
        --add-data "uptacamp_settings.json;." `
        --add-data "bert_voice_models;bert_voice_models" `
        main.py

    if (Test-Path ".\$ZipName") {
        Remove-Item ".\$ZipName" -Force
    }

    if ($OneFile) {
        $zipInput = ".\dist\$AppName.exe"
    }
    else {
        $zipInput = ".\dist\$AppName\*"
    }

    Compress-Archive -Path $zipInput -DestinationPath ".\$ZipName" -Force

    Write-Host "Build complete. Artifact:"
    Get-Item ".\$ZipName" | Select-Object FullName, Length, LastWriteTime | Format-List
}
finally {
    Pop-Location
}
