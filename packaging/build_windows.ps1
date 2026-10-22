# Builds dist/snakktilmeg-windows-x64.zip: the app (PyInstaller, windowed)
# plus a prebuilt whisper.cpp CLI. Models are downloaded on first run.
# Run from any directory on Windows: ./packaging/build_windows.ps1
$ErrorActionPreference = "Stop"

$WhisperRelease = "b5454"
$WhisperZipSha256 = "6ba69e3482d7826214f90a6a9c84ca07782aec1e1d0c6a7c30c994fd5d816ccb"
$WhisperZipUrl = "https://github.com/ggml-org/whisper.cpp/releases/download/$WhisperRelease/whisper-bin-x64.zip"

# Windows PowerShell 5.1 turns native stderr output into errors under "Stop",
# so run external tools with "Continue" and check their exit code instead.
function Invoke-Native([string]$Name, [scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Command } finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

$Root = Split-Path -Parent $PSScriptRoot
$Work = Join-Path $Root "build\package"
$Dist = Join-Path $Root "dist"
$AppDist = Join-Path $Dist "snakktilmeg"
$Zip = Join-Path $Dist "snakktilmeg-windows-x64.zip"

Push-Location $Root
try {
    Remove-Item $Work, $AppDist, $Zip -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $Work | Out-Null

    Write-Host "Downloading whisper.cpp $WhisperRelease"
    $WhisperZip = Join-Path $Work "whisper-bin-x64.zip"
    Invoke-WebRequest $WhisperZipUrl -OutFile $WhisperZip
    $Actual = (Get-FileHash $WhisperZip -Algorithm SHA256).Hash.ToLower()
    if ($Actual -ne $WhisperZipSha256) {
        throw "whisper.cpp download checksum mismatch: $Actual"
    }
    Expand-Archive $WhisperZip -DestinationPath (Join-Path $Work "whisper")

    Write-Host "Building app with PyInstaller"
    Invoke-Native "uv sync" { uv sync --group build }
    Invoke-Native "PyInstaller" { uv run --group build pyinstaller `
        --noconfirm --clean --windowed `
        --name snakktilmeg `
        --distpath $Dist `
        --workpath (Join-Path $Work "pyinstaller") `
        --specpath $Work `
        --hidden-import pynput.keyboard._win32 `
        --hidden-import pynput.mouse._win32 `
        --hidden-import pynput._util.win32 `
        --hidden-import pystray._win32 `
        main.py }

    # Only the CLI and the libraries it loads; the release has other tools.
    $WhisperDist = Join-Path $AppDist "whisper"
    New-Item -ItemType Directory -Force $WhisperDist | Out-Null
    $Release = Join-Path $Work "whisper\Release"
    Copy-Item (Join-Path $Release "whisper-cli.exe") $WhisperDist
    Copy-Item (Join-Path $Release "whisper.dll") $WhisperDist
    Copy-Item (Join-Path $Release "ggml*.dll") $WhisperDist

    Compress-Archive -Path $AppDist -DestinationPath $Zip
    Write-Host "Built $Zip"
}
finally {
    Pop-Location
}
