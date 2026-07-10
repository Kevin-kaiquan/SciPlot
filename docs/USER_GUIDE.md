# SciPlot User Guide

## Workspace

SciPlot opens directly into the figure workspace. The left dock contains data and chart-column controls. The right dock contains style, layout, and template controls. Both docks can be resized, moved, floated, closed, and restored from the View menu.

The startup window appears before the scientific libraries are loaded, so it remains clear that SciPlot is running. The first launch after installation may take longer while the operating system scans the packaged dependencies. Starting SciPlot again while it is already opening or running displays a single-instance notice instead of launching another copy.

## Import Data

Use **File > Import Data**, the toolbar button, or drag a CSV, TSV, TXT, DAT, XLSX, or XLS file into the window. SciPlot displays the imported table in the Data Preview tab and suggests X, Y, error, Z, and group columns from common column names.

## Generate a Figure

1. Select a chart type.
2. Select the visible chart-specific columns.
3. Set titles and axis labels.
4. Adjust the Style and Layout panels.
5. Select **Generate Figure** or press `Ctrl+Enter`.

For line and step charts, SciPlot warns when repeated X values are present without a group column because unrelated series could otherwise be connected.

## Move Labels and Colorbar

For charts with a color scale, use **Colorbar position** and **Colorbar spacing** in the Layout panel to place it on the right, left, top, or bottom, or hide it. Automatic placement uses the top for 3D charts and the right for 2D charts because those positions remain readable across more preview sizes. SciPlot also reserves additional space around 3D axes so the colorbar does not cover coordinate labels.

Select **Move Labels and Colorbar** or press `Ctrl+L`. Drag any of these items directly in the preview:

- Figure title
- X-axis label
- Y-axis label
- Legend
- Colorbar

Moved positions are saved in projects, templates, and the last-session state and are reproduced in PNG, SVG, and PDF exports. Use **Reset Moved Positions** to return to automatic placement. Moves support undo and redo.

## Missing Values

The Style panel provides three explicit policies:

- **Drop incomplete rows**: default and scientifically conservative.
- **Interpolate**: fills numeric gaps before plotting.
- **Treat as zero**: use only when a missing value genuinely means zero.

Area charts no longer convert missing values to zero unless this policy is selected.

## Projects

SciPlot 3 projects use the `.sciplot` extension. A project is a compressed, versioned container containing data and figure settings. Shared projects store only the original source file name, not the sender's local absolute path. Legacy SciPlot JSON projects remain readable.

## Export

Use **Export Figure** or `Ctrl+E` and select PNG, SVG, or PDF.

- PNG is suitable for slides, documents, and raster publication workflows.
- SVG is suitable for vector editing and browser-compatible workflows.
- PDF is suitable for vector publication and print workflows.

SciPlot rejects PNG dimensions that could exhaust system memory. DPI mainly affects PNG and rasterized content inside vector formats.

## Updates

Automatic release checks run at most once every 24 hours and can be disabled in the Tools menu. SciPlot remains fully usable offline. Update packages are downloaded from the official GitHub repository.

## Troubleshooting

- Current release packages are unsigned. Download only from the official GitHub Releases page and verify `SHA256SUMS.txt`. For a verified Windows package blocked by SmartScreen, use **More info > Run anyway**. For a verified macOS package blocked by Gatekeeper, Control-click SciPlot and choose **Open**, or use **System Settings > Privacy & Security**.
- If a chart fails, verify that the selected columns contain valid numeric data for that chart type.
- If a contour or surface chart fails, provide at least three non-collinear X/Y points.
- If a pie chart fails, values must be non-negative and have a positive total.
- If an old session is not restored, its original large source file may have moved or changed.
- Startup errors are written to the application's writable runtime data directory rather than the installation folder.
