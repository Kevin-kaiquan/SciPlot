# SciPlot

SciPlot is a local Windows desktop application for creating publication-ready scientific plots from tabular data. It is designed for students, coursework, lab reports, and lightweight research workflows.

SciPlot does not include a template marketplace, paid templates, accounts, payment features, advertising, or user tracking.

## Features

- Import CSV, TSV, TXT, XLSX, and XLS data files.
- Preview imported data in a table.
- Create line charts, scatter plots, bar charts, error-bar plots, histograms, box plots, and correlation heatmaps.
- Create advanced scientific figures including density curves, ECDF plots, violin plots, lollipop plots, 2D density plots, hexbin plots, contour plots, radar charts, polar plots, pie/donut charts, and 3D scatter/line/surface/wireframe/bar/contour plots.
- Apply built-in scientific plot templates, including SciPlot Classic.
- Export figures as PNG, SVG, or PDF.
- Save and load SciPlot project files as JSON.
- Import, export, and share local template JSON files.
- Run fully locally on Windows.

## Project Structure

```text
src/                         Application source code
docs/                        User documentation
scripts/                     Validation and maintenance scripts
sample_data/                 Example input data
templates/                   Built-in plot templates
requirements.txt             Python dependencies
build_exe.ps1                Windows exe build script
run_dev.ps1                  Development launcher
.github/workflows/           CI and release packaging workflows
```

Generated folders such as `.venv/`, `build/`, `dist/`, `runtime/`, `exports/`, and `output/` are intentionally ignored by Git.

## Run From Source

First build the local virtual environment and install dependencies:

```powershell
.\build_exe.ps1
```

Then run the development version:

```powershell
.\run_dev.ps1
```

## Build The Windows App

Run:

```powershell
.\build_exe.ps1
```

The script creates a local virtual environment under:

```text
E:\Sci_Plot\.venv
```

It also keeps pip, Matplotlib, Python bytecode, and PyInstaller cache files inside the project folder as much as possible.

The packaged application is generated at:

```text
E:\Sci_Plot\dist\SciPlot\SciPlot.exe
```

## Portable Distribution

SciPlot is packaged as a portable folder application. To share it with another Windows user, copy the entire folder:

```text
E:\Sci_Plot\dist\SciPlot
```

Do not copy only `SciPlot.exe`; the executable needs the `_internal` folder and bundled resources next to it.

On first launch, SciPlot shows a startup window while it loads Pandas, Matplotlib, and other scientific plotting dependencies. The first startup can take around 20 to 40 seconds on some machines.

## GitHub Releases

Tagged releases are built by GitHub Actions:

- `SciPlot-Windows-x64.zip` contains the Windows portable app with `SciPlot.exe`.
- `SciPlot-macOS-arm64.zip` contains the macOS `.app` bundle for Apple Silicon.
- `SciPlot-macOS-intel.zip` contains the macOS `.app` bundle for Intel Macs.

To publish a release, push a version tag such as:

```powershell
git tag v2.0.0
git push origin v2.0.0
```

The release workflow builds both platforms and attaches the downloadable archives to the GitHub release.

## Validation

After building the app, run:

```powershell
E:\Sci_Plot\dist\SciPlot\SciPlot.exe --smoke-test
E:\Sci_Plot\dist\SciPlot\SciPlot.exe --gui-smoke
```

Both commands should exit with code `0`.

To validate every supported chart type from source, run:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_charts.py
```

## Data Format

Input files should use the first row as column names. Numeric columns are detected automatically.

Example:

```csv
time_s,signal_a,signal_b,error_a,group
0,0.03,0.12,0.02,control
1,0.18,0.21,0.03,control
```

An example dataset is available at:

```text
sample_data/example_measurements.csv
sample_data/example_surface_grid.csv
```

## Templates

Templates are plain JSON files stored in:

```text
templates/
```

They can be edited, imported, exported, and shared without any online account or marketplace.

## License

No license has been added yet. Add a license before publishing or distributing the project broadly.
