# SciPlot

SciPlot is a local desktop application for creating publication-ready scientific plots from tabular data. It is designed for students, coursework, lab reports, and lightweight research workflows.

SciPlot does not include a template marketplace, paid templates, accounts, payment features, advertising, or user tracking.

## Features

- Import CSV, TSV, TXT, XLSX, and XLS data files.
- Preview imported data in a table.
- Create common plots such as line, scatter, bar, error-bar, histogram, box, violin, and heatmap figures.
- Create advanced scientific figures including density curves, ECDF plots, lollipop plots, 2D density plots, hexbin plots, contour plots, radar charts, polar plots, pie/donut charts, and 3D scatter/line/surface/wireframe/bar/contour plots.
- Export figures as PNG, SVG, or PDF with predictable canvas size.
- Save and load SciPlot project files as JSON.
- Import, export, and share local template JSON files.
- Restore the last generated chart on the next launch.
- Run fully locally without online services.

## Downloads

Tagged releases are built by GitHub Actions and published on the GitHub Releases page.

- `SciPlot-Windows-x64.msi` is the recommended Windows installer.
- `SciPlot-Windows-x64.zip` is a portable Windows build.
- `SciPlot-macOS-arm64.dmg` is the macOS installer image for Apple Silicon.
- `SciPlot-macOS-intel.dmg` is the macOS installer image for Intel Macs.

The Windows installer and portable build include the Python runtime and required scientific libraries.

## Usage

1. Install SciPlot or extract the portable Windows archive.
2. Launch SciPlot.
3. Import a data file or load the included sample dataset.
4. Select the chart type, data columns, and style options.
5. Click **Generate Chart**.
6. Export the figure as PNG, SVG, or PDF.

SciPlot starts with an empty workspace on first launch. After a chart is generated, the next launch restores the last generated chart.

The Windows MSI installer shows a destination folder step, so users can choose where SciPlot is installed.

## Development

Install dependencies and build the local desktop package:

```powershell
.\build_exe.ps1
```

Run the development version:

```powershell
.\run_dev.ps1
```

Build the Windows MSI after the portable app has been built:

```powershell
.\scripts\build_msi.ps1
```

Validate all supported chart types:

```powershell
.\.venv\Scripts\python.exe .\scripts\validate_charts.py
```

Validate a packaged Windows build:

```powershell
.\dist\SciPlot\SciPlot.exe --smoke-test
.\dist\SciPlot\SciPlot.exe --gui-smoke
```

## Data Format

Input files should use the first row as column names. Numeric columns are detected automatically.

Example:

```csv
time_s,signal_a,signal_b,error_a,group
0,0.03,0.12,0.02,control
1,0.18,0.21,0.03,control
```

Sample datasets are included in the repository for basic line charts and 3D/contour examples.

## Templates

Templates are plain JSON files. They can be edited, imported, exported, and shared without any online account or marketplace.

## License

No license has been added yet. Add a license before publishing or distributing the project broadly.
