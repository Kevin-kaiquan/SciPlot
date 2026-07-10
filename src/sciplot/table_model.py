from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class PandasTableModel(QAbstractTableModel):
    def __init__(self, dataframe: pd.DataFrame | None = None, max_rows: int = 10000, max_columns: int = 200) -> None:
        super().__init__()
        self.max_rows = max_rows
        self.max_columns = max_columns
        self._frame = dataframe if dataframe is not None else pd.DataFrame()

    def set_dataframe(self, dataframe: pd.DataFrame) -> None:
        self.beginResetModel()
        self._frame = dataframe
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else min(len(self._frame), self.max_rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else min(len(self._frame.columns), self.max_columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        value = self._frame.iat[index.row(), index.column()]
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.7g}"
        return str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and section < len(self._frame.columns):
            return str(self._frame.columns[section])
        return str(section + 1)
