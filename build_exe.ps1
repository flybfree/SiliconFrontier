param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Preserve the editable configuration when a clean build replaces the package.
$runtimeSettings = Join-Path $PSScriptRoot "dist\SiliconFrontier\settings.json"
$settingsBackup = Join-Path $env:TEMP "SiliconFrontier-settings-backup.json"
if (Test-Path $runtimeSettings) {
    Copy-Item -LiteralPath $runtimeSettings -Destination $settingsBackup -Force
}

$pythonCandidates = @()
if ($env:VIRTUAL_ENV) {
    $pythonCandidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
}
$pythonCandidates += (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")
$pythonCandidates += Get-ChildItem (Join-Path $env:LocalAppData "Programs\Python") -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -ExpandProperty FullName
$pythonExe = $pythonCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $pythonExe) {
    throw "No usable python.exe found. Activate a virtual environment or install Python first."
}

if ($Clean) {
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist\SiliconFrontier") { Remove-Item -Recurse -Force "dist\SiliconFrontier" }
    if (Test-Path "dist\SiliconFrontier.exe") { Remove-Item -Force "dist\SiliconFrontier.exe" }
}

& $pythonExe -m PyInstaller --noconfirm SiliconFrontier.spec

$builtSettings = Join-Path $PSScriptRoot "dist\SiliconFrontier\settings.json"
if (Test-Path $settingsBackup) {
    Copy-Item -LiteralPath $settingsBackup -Destination $builtSettings -Force
    Remove-Item -LiteralPath $settingsBackup -Force
} elseif (-not (Test-Path $builtSettings)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "settings.example.json") -Destination $builtSettings -Force
}
