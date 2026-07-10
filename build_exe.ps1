$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"

$env:PIP_CACHE_DIR = Join-Path $Root ".pip-cache"
$env:MPLCONFIGDIR = Join-Path $Root "runtime\matplotlib"
$env:PYTHONPYCACHEPREFIX = Join-Path $Root "runtime\pycache"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $Root "runtime\pyinstaller"
$env:TEMP = Join-Path $Root "runtime\temp"
$env:TMP = $env:TEMP
$env:PYTHONNOUSERSITE = "1"
foreach ($directory in @($env:PIP_CACHE_DIR, $env:MPLCONFIGDIR, $env:PYTHONPYCACHEPREFIX, $env:PYINSTALLER_CONFIG_DIR, $env:TEMP)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

if (-not (Test-Path $Python)) {
    python -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Pip install -r (Join-Path $Root "requirements.txt")
& $Python (Join-Path $Root "scripts\prepare_icons.py")

& $PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "SciPlot" `
    --icon (Join-Path $Root "logo\SciPlot.ico") `
    --hidden-import "matplotlib.backends.backend_qtagg" `
    --hidden-import "matplotlib.backends.backend_agg" `
    --hidden-import "matplotlib.backends.backend_pdf" `
    --hidden-import "matplotlib.backends.backend_svg" `
    --hidden-import "scipy.stats" `
    --hidden-import "PySide6.QtSvg" `
    --hidden-import "openpyxl" `
    --hidden-import "xlrd" `
    --exclude-module "tkinter" `
    --distpath (Join-Path $Root "dist") `
    --workpath (Join-Path $Root "build") `
    --specpath $Root `
    --add-data "$Root\sample_data;sample_data" `
    --add-data "$Root\templates;templates" `
    --add-data "$Root\logo;logo" `
    (Join-Path $Root "src\sciplot_launcher.py")

$DistApp = Join-Path $Root "dist\SciPlot"
Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $DistApp "README.md") -Force
Copy-Item -LiteralPath (Join-Path $Root "docs") -Destination (Join-Path $DistApp "docs") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Root "sample_data") -Destination (Join-Path $DistApp "sample_data") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Root "templates") -Destination (Join-Path $DistApp "templates") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Root "logo") -Destination (Join-Path $DistApp "logo") -Recurse -Force

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host (Join-Path $Root "dist\SciPlot\SciPlot.exe")
