$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtual environment not found. Run .\build_exe.ps1 first, or create .venv manually." -ForegroundColor Yellow
    exit 1
}

$env:MPLCONFIGDIR = Join-Path $Root "runtime\matplotlib"
& $VenvPython (Join-Path $Root "src\sciplot_app.py")
