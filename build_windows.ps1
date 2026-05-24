param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$AppName = "CribbageGame",
    [string]$ZipName = "CribbageGame-Windows-Test.zip",
    [switch]$OneFile,
    [switch]$SkipPip,
    [switch]$Clean,
    [switch]$NoPiper,
    [switch]$AllowUnsupportedPython
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

    $pyVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    $pyMajorMinor = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if (-not $AllowUnsupportedPython -and $pyMajorMinor -notin @("3.10", "3.11")) {
        throw "Unsupported Python for Windows packaging ($pyVersion). Use Python 3.10 or 3.11, or pass -AllowUnsupportedPython."
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

    $piperArgs = @()
    if (-not $NoPiper) {
        & $PythonExe -c "import importlib.util as u; import sys; sys.exit(0 if u.find_spec('piper') else 1)"
        $hasPiper = ($LASTEXITCODE -eq 0)

        & $PythonExe -c "import importlib.util as u; import sys; sys.exit(0 if u.find_spec('onnxruntime') else 1)"
        $hasOnnxRuntime = ($LASTEXITCODE -eq 0)

        if ($hasPiper -and $hasOnnxRuntime) {
            $piperArgs += "--collect-all"
            $piperArgs += "piper"
            $piperArgs += "--collect-all"
            $piperArgs += "onnxruntime"
            Write-Host "Bundling Piper + ONNXRuntime (toggleable at runtime)."
        }
        else {
            Write-Host "Piper/ONNXRuntime not installed; building without bundling them."
        }
    }
    else {
        Write-Host "NoPiper specified; building without bundling Piper/ONNXRuntime."
    }

    & $PythonExe -m PyInstaller --noconfirm --clean --console $bundleMode --name $AppName `
        --add-data "assets;assets" `
        --add-data "uptacamp_settings.json;." `
        --add-data "bert_voice_models;bert_voice_models" `
        $piperArgs `
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
