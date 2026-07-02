# SciPlot

SciPlot 是一個面向學生、課堂和實驗報告場景的 Windows 本地科研繪圖工具。它不包含模板市場、付費購買、賬號系統或商業追蹤功能。

## 功能

- 導入 CSV、TSV、TXT、Excel 數據。
- 數據表格預覽。
- 生成折線圖、散點圖、柱狀圖、誤差棒、直方圖、箱線圖、相關熱圖。
- 套用免費科研圖模板。
- 導出 PNG、SVG、PDF。
- 保存和載入 `.json` 項目文件。
- 保存、導入、導出本地模板 JSON。

## 運行

打包完成後直接運行：

```powershell
E:\Sci_Plot\dist\SciPlot\SciPlot.exe
```

這是便攜版資料夾應用。分享給同學時請複製整個 `dist\SciPlot` 文件夾，不要只單獨複製 `SciPlot.exe`。

首次啟動會先顯示「SciPlot 正在啟動」窗口。由於需要載入 Pandas、Matplotlib 等科研繪圖依賴，第一次進入主界面可能需要約 20-40 秒。

開發模式運行：

```powershell
.\run_dev.ps1
```

## 構建 exe

```powershell
.\build_exe.ps1
```

腳本會在 `E:\Sci_Plot\.venv` 建立虛擬環境，依賴緩存在 `E:\Sci_Plot\.pip-cache`，構建輸出在 `E:\Sci_Plot\dist`。
PyInstaller、Matplotlib 和 Python bytecode 的運行/構建緩存也會放在 `E:\Sci_Plot\runtime`。

## 驗證

```powershell
E:\Sci_Plot\dist\SciPlot\SciPlot.exe --smoke-test
E:\Sci_Plot\dist\SciPlot\SciPlot.exe --gui-smoke
```

兩個命令退出碼為 `0` 即表示打包後的繪圖流程和 GUI 初始化通過。

## 數據格式

第一行應為欄位名稱。數值欄會被自動識別。示例文件在：

```text
sample_data/example_measurements.csv
```

## 模板

模板保存在：

```text
templates/
```

模板是普通 JSON 文件，可以在同學之間免費共享。
