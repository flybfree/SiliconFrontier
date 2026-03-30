param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

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
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

& $pythonExe -m PyInstaller --noconfirm SiliconFrontier.spec
