# SciPlot

SciPlot is a local desktop application for creating clear, publication-style scientific charts from tabular data. It is intended for students, classmates, lab reports, coursework, and lightweight research work.

The project is designed to be simple and offline-first. It does not include accounts, payments, advertising, tracking, cloud storage, or a template marketplace.

## What SciPlot Can Do

- Import data from CSV, TSV, TXT, XLSX, and XLS files.
- Preview imported data in a table before plotting.
- Create common academic charts, including line, scatter, bar, error-bar, histogram, box, violin, and heatmap plots.
- Create advanced scientific visualizations, including density curves, ECDF plots, lollipop plots, 2D density plots, hexbin plots, contour plots, radar charts, polar plots, pie/donut charts, and 3D scatter, line, surface, wireframe, bar, and contour plots.
- Export charts as PNG, SVG, or PDF.
- Save and open SciPlot project files as JSON.
- Import, export, and share local chart template JSON files.
- Restore the last generated chart when the app is opened again.
- Run fully on the user's computer without an internet connection.

## Download and Install

Download the latest release from the [GitHub Releases page](https://github.com/Kevin-kaiquan/SciPlot/releases).

Available release files:

- `SciPlot-Windows-x64.msi`: recommended installer for Windows users.
- `SciPlot-Windows-x64.zip`: portable Windows version.
- `SciPlot-macOS-arm64.dmg`: macOS installer image for Apple Silicon Macs.
- `SciPlot-macOS-intel.dmg`: macOS installer image for Intel Macs.

The Windows installer and portable build include the Python runtime and required scientific libraries. Users do not need to install Python separately when using the release builds.

If you install SciPlot from an MSI or DMG file, you do not need to clone the source code or run any development scripts.

## How to Use the Installed App

### Windows MSI

1. Download `SciPlot-Windows-x64.msi`.
2. Open the installer.
3. Choose the installation folder when the installer asks for a destination.
4. Finish the installation.
5. Launch SciPlot from the Start Menu or from the folder selected during installation.

### Windows Portable ZIP

1. Download `SciPlot-Windows-x64.zip`.
2. Extract the ZIP file to any folder.
3. Open the extracted folder.
4. Run `SciPlot.exe`.

### macOS DMG

1. Download the correct DMG file for your Mac:
   - Apple Silicon: `SciPlot-macOS-arm64.dmg`
   - Intel Mac: `SciPlot-macOS-intel.dmg`
2. Open the DMG file.
3. Drag `SciPlot.app` into `Applications`, or run it directly from the mounted DMG for a quick test.
4. Launch SciPlot from `Applications`.

## Basic Workflow

1. Open SciPlot.
2. Import a data file or load one of the included sample datasets.
3. Check the data preview.
4. Select a chart type.
5. Choose the X, Y, group, error, or Z columns required by that chart type.
6. Adjust titles, labels, style, size, and export settings.
7. Click **Generate Chart**.
8. Export the chart as PNG, SVG, or PDF.

SciPlot starts with an empty workspace on first launch. After the first chart is generated, the next launch restores the most recently generated chart.

## Data Format

Input files should use the first row as column names. Numeric columns are detected automatically.

Example:

```csv
time_s,signal_a,signal_b,error_a,group
0,0.03,0.12,0.02,control
1,0.18,0.21,0.03,control
2,0.31,0.35,0.02,treatment
```

## Customizing from Source Code

Developers can download the source code to change the UI, add chart types, edit templates, or build their own release packages.

### Run the Development Version

Create a virtual environment, install dependencies, and run the app:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\run_dev.ps1
```

If you already built the Windows desktop app with `build_exe.ps1`, the virtual environment and dependencies are usually already prepared.

### Build the Windows Desktop App

Create the packaged Windows application:

```powershell
.\build_exe.ps1
```

### Build the Windows MSI

Build the Windows MSI after the packaged app has been created:

```powershell
.\build_exe.ps1
.\scripts\build_msi.ps1
```

### macOS Release Builds

macOS DMG files are built by GitHub Actions. See `.github/workflows/release.yml` for the Apple Silicon and Intel release build steps.

### Validate Chart Rendering

Check all supported chart types:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_charts.py
```

Validate a packaged Windows build:

```powershell
.\dist\SciPlot\SciPlot.exe --smoke-test
.\dist\SciPlot\SciPlot.exe --gui-smoke
```

## Project Structure

```text
SciPlot/
|-- src/
|   |-- sciplot_app.py          Main Tkinter application and plotting logic
|   `-- sciplot_launcher.py     Packaged app launcher and splash startup
|-- scripts/
|   |-- build_msi.ps1           Builds the Windows MSI installer
|   |-- prepare_icons.py        Converts the logo into platform icon files
|   `-- validate_charts.py      Renders and validates supported chart types
|-- sample_data/                Example datasets for testing and demos
|-- templates/                  Local chart template JSON files
|-- logo/                       SciPlot logo and generated icon files
|-- docs/                       Additional user documentation
|-- .github/workflows/          GitHub Actions release builds
|-- build_exe.ps1               Builds the packaged Windows app
|-- run_dev.ps1                 Runs the development version
|-- requirements.txt            Python dependencies
`-- README.md                   Project overview and usage guide
```

## Templates

Templates are plain JSON files stored locally. They can be edited, imported, exported, and shared without any online account.

## License

No license has been added yet. Add a license before publishing or distributing the project broadly.
