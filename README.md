# SciPlot

SciPlot is a cross-platform desktop application for turning tabular data into clear, publication-ready scientific figures. It is designed for students, classes, laboratory reports, and lightweight research workflows.

SciPlot is offline-first. It has no accounts, payments, advertising, analytics, cloud storage, or template marketplace. The only automatic network request is the optional GitHub release update check.

## Highlights

- Native desktop interface built with PySide6 and Qt.
- Immediate startup status window while scientific libraries load, with protection against duplicate launches.
- Dockable, movable, closable, and resizable data, plot, style, layout, and template panels.
- English, Traditional Chinese, and Simplified Chinese user interfaces.
- Background data import, project save/load, figure export, update checks, and installer downloads.
- Undo and redo for generated figure settings and manually moved labels or colorbars.
- Drag-and-drop data and project files.
- Direct dragging of the title, X label, Y label, legend, and colorbar in the figure preview.
- Collision-aware colorbar layouts with right, left, top, bottom, hidden, spacing, and manual-position controls.
- Versioned `.sciplot` project files with compressed embedded data and backward-compatible legacy JSON import.
- Automatic restoration of the last generated figure without silently accepting a changed source file.
- PNG, SVG, and PDF export with a guard against unsafe bitmap sizes.

## Supported Data

SciPlot imports:

- CSV
- TSV
- TXT and DAT tables
- XLSX
- XLS

The first row should contain column names. Numeric columns are detected automatically. Common UTF-8, GB18030, and Windows text encodings are supported.

## Supported Charts

SciPlot currently includes 32 chart types:

- Line, step, area, stacked area, scatter, bubble, bar, horizontal bar, and error-bar charts.
- Histogram, kernel density, ECDF, box, violin, stem, and lollipop charts.
- Correlation heatmap, 2D histogram, hexbin, contour, and filled contour charts.
- Radar, polar line, polar scatter, pie, and donut charts.
- 3D scatter, line, surface, wireframe, bar, and contour charts.

Chart-specific controls appear only when they are relevant. For example, 3D camera controls are hidden for a line chart, and error-column selection is shown only for an error-bar chart.

## Download and Install

Download the latest release from the [GitHub Releases page](https://github.com/Kevin-kaiquan/SciPlot/releases).

Available packages:

- `SciPlot-Windows-x64.msi`: Windows installer with a selectable installation folder, Start Menu entry, and desktop shortcut.
- `SciPlot-Windows-x64.zip`: portable Windows application.
- `SciPlot-macOS-arm64.dmg`: Apple Silicon macOS disk image.
- `SciPlot-macOS-intel.dmg`: Intel macOS disk image.

Release packages include Python and all scientific dependencies. Users do not need to install Python.

Current community builds are not code-signed or notarized. Download them only from the official Releases page and compare them with `SHA256SUMS.txt`. Windows may show SmartScreen; select **More info > Run anyway** after verifying the download. On macOS, Control-click SciPlot and select **Open**, or allow it from **System Settings > Privacy & Security** after verifying the DMG.

## Basic Workflow

1. Open SciPlot.
2. Select **Import Data**, drag a supported file into the window, or load the sample data.
3. Choose a chart type and the required data columns in the left Plot panel.
4. Adjust visual settings in the right Style and Layout panels.
5. Select **Generate Figure**.
6. Select **Move Labels and Colorbar** and drag the title, axis labels, legend, or colorbar if their automatic positions are not suitable.
7. Export PNG, SVG, or PDF, or save a `.sciplot` project.

SciPlot starts with an empty figure workspace on first launch. After a figure has been generated, the next launch restores that figure and its data. If a large source file changed after the previous session, SciPlot refuses to silently recreate the old figure with different data.

## Keyboard Shortcuts

| Action | Shortcut |
|---|---|
| New workspace | `Ctrl+N` |
| Import data | `Ctrl+O` |
| Open project | `Ctrl+Alt+O` |
| Save project | `Ctrl+S` |
| Generate figure | `Ctrl+Enter` |
| Export figure | `Ctrl+E` |
| Move labels and colorbar | `Ctrl+L` |
| Undo / redo | `Ctrl+Z` / `Ctrl+Y` |

On macOS, Qt maps standard shortcuts to the corresponding Command-key conventions where applicable.

## Updates

SciPlot can check the official GitHub Releases feed after launch, at most once every 24 hours. Automatic checks can be disabled from the Tools menu. A successful check does not display a dialog when the installed version is current. When a release is available, SciPlot can download the correct MSI or DMG package and open it.

## Run from Source

Python 3.11 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\run_dev.ps1
```

The source application uses PySide6, pandas, NumPy, SciPy, Matplotlib, openpyxl, and xlrd.

## Build Windows Packages

Build the portable application:

```powershell
.\build_exe.ps1
```

Build the MSI after the portable application:

```powershell
.\scripts\build_msi.ps1
```

The MSI version is read from `src/sciplot/version.py`; it is not maintained separately.

## Validate the Project

```powershell
.\.venv\Scripts\python.exe -m compileall -q .\src .\scripts
.\.venv\Scripts\python.exe .\scripts\validate_charts.py
.\.venv\Scripts\python.exe .\src\sciplot_app.py --smoke-test
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe .\src\sciplot_app.py --gui-smoke
```

Continuous Integration runs the chart engine, export, project-format, and Qt GUI checks on Windows and macOS for pushes and pull requests. Tagged releases additionally build and test Windows MSI/ZIP and both macOS DMG architectures before one release job publishes all assets.

## Project Structure

```text
SciPlot/
|-- src/
|   |-- sciplot/
|   |   |-- app.py             Qt application startup and smoke tests
|   |   |-- main_window.py     Dockable PySide6 desktop interface
|   |   |-- plotting.py        Backend-independent scientific chart engine
|   |   |-- data_io.py         CSV, text, and Excel import
|   |   |-- project_io.py      Project and session persistence
|   |   |-- updater.py         GitHub release update service
|   |   |-- drag.py            Interactive label movement
|   |   |-- i18n.py            English and Chinese UI text
|   |   `-- models.py          Stable chart IDs and plot settings
|   |-- sciplot_app.py         Development compatibility entry point
|   `-- sciplot_launcher.py    Packaged application entry point
|-- scripts/
|   |-- build_msi.ps1          Windows MSI builder
|   |-- prepare_icons.py       Cross-platform icon generation
|   |-- validate_charts.py     Chart and project-format validation
|   `-- check_release_version.py
|-- sample_data/               Included example datasets
|-- templates/                 Shareable local JSON style templates
|-- logo/                      Application branding and platform icons
|-- docs/                      User documentation
|-- .github/workflows/         CI and release builds
|-- build_exe.ps1              Windows portable build
|-- run_dev.ps1                Development launcher
`-- requirements.txt           Pinned Python dependencies
```

## Templates

Templates contain visual settings only. They do not contain source paths or project data and can be imported, exported, edited, and shared without an account.

## License

No license has been selected yet. Add a license before broad public distribution so that users and contributors have clear permission to use, modify, and redistribute SciPlot.
