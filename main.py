# main.py
# Quick MR-Basic Plotter (PySide6 + pyqtgraph + pandas)
#
# Changes in this revision:
# - Slight grey plot background (setConfigOption)
# - Reworked trace selection UI so column dropdowns are wide and readable:
#     each slot is a row widget (HBox), not a cramped grid.
# - Compact color button (tiny square)
# - Column dropdowns have tooltips (full text)
#
# Install:
#   python -m pip install PySide6 pyqtgraph pandas numpy
# Run:
#   python main.py

import sys
import io
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

import numpy as np
import pandas as pd

from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg


@dataclass
class DataSet:
    df_raw: pd.DataFrame
    meta: Dict[str, str]
    offsets: Optional[pd.Series] = None


def make_demo_dataset(n: int = 5000) -> DataSet:
    x = np.linspace(0, 100, n)
    df = pd.DataFrame({
        "RowLabel": ["DATA"] * n,
        "Time [Sec.]": x,
        "sin [a.u.]": np.sin(x / 5),
        "cos [a.u.]": np.cos(x / 5),
        "noise [a.u.]": 0.2 * np.random.randn(n),
        "trend [a.u.]": 0.01 * x,
    })
    meta = {"Source": "Demo data (no file loaded)", "Rows": str(n)}
    return DataSet(df_raw=df, meta=meta, offsets=None)


# -----------------------------
# Robust file reading / parsing
# -----------------------------

def _read_text_robust(path: str) -> str:
    b = open(path, "rb").read()
    b = b.replace(b"\x0b", b" ")
    b = b.replace(b"\x00", b" ")
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def _looks_like_table_header(line: str) -> bool:
    s = line.strip("\n")
    if "," not in s:
        return False
    if s.count(",") < 5:
        return False
    if ":" in s and s.count(",") <= 1:
        return False
    return True


def _parse_meta_lines(lines: List[str]) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    title_set = False
    note_i = 1
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if ":" in s:
            k, v = s.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k:
                meta[k] = v
            else:
                meta[f"Note {note_i}"] = v
                note_i += 1
        else:
            if not title_set:
                meta["Title"] = s
                title_set = True
            else:
                meta[f"Note {note_i}"] = s
                note_i += 1
    return meta


def _make_unique(names: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for n in names:
        base = n if n else "Unnamed"
        if base not in seen:
            seen[base] = 1
            out.append(base)
        else:
            seen[base] += 1
            out.append(f"{base} ({seen[base]})")
    return out


def _build_column_names(header_rows: pd.DataFrame) -> List[str]:
    def norm(x) -> str:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return ""
        return str(x).strip()

    r0 = [norm(v) for v in header_rows.iloc[0].tolist()]
    r1 = [norm(v) for v in header_rows.iloc[1].tolist()]

    colnames: List[str] = []
    for j, (name, unit) in enumerate(zip(r0, r1)):
        if j == 0 and name == "":
            name = "RowLabel"
        if unit in ("", "____________"):
            unit = ""
        if name == "":
            name = f"Col{j}"
        colnames.append(f"{name} [{unit}]" if unit else name)

    return _make_unique(colnames)


def _drop_empty_trailing_columns(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.dropna(axis=1, how="all")
    bad = [c for c in df2.columns if isinstance(c, str) and c.strip() == ""]
    if bad:
        df2 = df2.drop(columns=bad)
    return df2


def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if str(c) == "RowLabel":
            out[c] = out[c].astype(str).str.strip()
        else:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _extract_offsets(df_raw: pd.DataFrame) -> Optional[pd.Series]:
    if "RowLabel" not in df_raw.columns:
        return None
    labels = df_raw["RowLabel"].astype(str).str.strip().str.lower()
    m = labels == "offsets"
    if not m.any():
        return None
    row = df_raw.loc[m].iloc[0]
    offsets = row.drop(labels=["RowLabel"], errors="ignore")
    offsets = pd.to_numeric(offsets, errors="coerce")
    return offsets


def _filter_data_rows(df_raw: pd.DataFrame) -> pd.DataFrame:
    if "RowLabel" not in df_raw.columns:
        return df_raw.copy()
    labels = df_raw["RowLabel"].astype(str).str.strip().str.lower()
    drop = labels.isin({"zero voltage", "offsets"})
    return df_raw.loc[~drop].copy()


def load_mrbasic_csv(path: str) -> DataSet:
    text = _read_text_robust(path)
    lines = text.splitlines(True)

    table_start = None
    for i, line in enumerate(lines):
        if _looks_like_table_header(line):
            table_start = i
            break
    if table_start is None:
        raise ValueError("Could not detect CSV table header row.")

    meta = _parse_meta_lines(lines[:table_start])
    meta["File"] = path
    meta["Table starts at line"] = str(table_start + 1)

    buf = io.StringIO(text)
    header_rows = pd.read_csv(
        buf,
        skiprows=table_start,
        nrows=4,
        header=None,
        sep=r"\s*,\s*",
        engine="python",
        dtype=str,
        keep_default_na=False,
    )
    colnames = _build_column_names(header_rows)

    buf2 = io.StringIO(text)
    df = pd.read_csv(
        buf2,
        skiprows=table_start + 4,
        header=None,
        names=colnames,
        sep=r"\s*,\s*",
        engine="python",
        na_values=["NaN", "nan", "NAN", ""],
        keep_default_na=True,
    )

    df = _drop_empty_trailing_columns(df)
    df = _coerce_numeric_columns(df)

    offsets = _extract_offsets(df)
    meta["Offsets detected"] = "Yes" if offsets is not None else "No"
    meta["Rows (raw table)"] = str(len(df))
    meta["Cols (raw table)"] = str(len(df.columns))

    return DataSet(df_raw=df, meta=meta, offsets=offsets)


# -----------------------------
# Data prep / transformations
# -----------------------------

def prepare_timeseries_dataframe(ds: DataSet, apply_offsets: bool) -> pd.DataFrame:
    df = _filter_data_rows(ds.df_raw).reset_index(drop=True)

    if apply_offsets and ds.offsets is not None:
        for c, off in ds.offsets.items():
            if c in df.columns and str(c) != "RowLabel":
                if pd.isna(off):
                    continue
                # OFFSET SIGN HERE (flip if needed):
                df[c] = df[c] - float(off)

    return df


def numeric_columns(df: pd.DataFrame) -> List[str]:
    cols = []
    for c in df.columns:
        if c == "RowLabel":
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(str(c))
    return cols


# -----------------------------
# Plot widget
# -----------------------------

class DualAxisPlot(pg.GraphicsLayoutWidget):
    sig_mouse_moved = QtCore.Signal(float, float, float)
    sig_cursors_changed = QtCore.Signal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.plot_item = self.addPlot(row=0, col=0)
        self.plot_item.showGrid(x=True, y=True, alpha=0.2)

        self.right_vb = pg.ViewBox()
        self.plot_item.scene().addItem(self.right_vb)
        self.plot_item.getAxis("right").setStyle(showValues=True)
        self.plot_item.showAxis("right")
        self.plot_item.getAxis("right").linkToView(self.right_vb)
        self.right_vb.setXLink(self.plot_item.vb)
        self.plot_item.vb.sigResized.connect(self._update_views)

        self.left_traces: List[Optional[pg.PlotDataItem]] = [None] * 4
        self.right_traces: List[Optional[pg.PlotDataItem]] = [None] * 4

        self.left_fit: Optional[pg.PlotDataItem] = None
        self.right_fit: Optional[pg.PlotDataItem] = None

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(width=1))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(width=1))
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.addItem(self.h_line, ignoreBounds=True)

        self.measure_enabled = False
        self.target_a = pg.TargetItem(pos=(0, 0), movable=True, pen=pg.mkPen(width=2))
        self.target_b = pg.TargetItem(pos=(0, 0), movable=True, pen=pg.mkPen(width=2))
        self.target_a.setVisible(False)
        self.target_b.setVisible(False)
        self.plot_item.addItem(self.target_a)
        self.plot_item.addItem(self.target_b)

        self.target_a.sigPositionChanged.connect(self._emit_target_positions)
        self.target_b.sigPositionChanged.connect(self._emit_target_positions)

        self._move_proxy = pg.SignalProxy(self.plot_item.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved)
        self._click_proxy = pg.SignalProxy(self.plot_item.scene().sigMouseClicked, rateLimit=60, slot=self._on_mouse_clicked)

    def _update_views(self):
        self.right_vb.setGeometry(self.plot_item.vb.sceneBoundingRect())
        self.right_vb.linkedViewChanged(self.plot_item.vb, self.right_vb.XAxis)

    def clear_traces(self):
        for i, it in enumerate(self.left_traces):
            if it is not None:
                self.plot_item.removeItem(it)
                self.left_traces[i] = None
        for i, it in enumerate(self.right_traces):
            if it is not None:
                self.right_vb.removeItem(it)
                self.right_traces[i] = None
        self.clear_fit_lines()

    def clear_fit_lines(self):
        if self.left_fit is not None:
            self.plot_item.removeItem(self.left_fit)
            self.left_fit = None
        if self.right_fit is not None:
            self.right_vb.removeItem(self.right_fit)
            self.right_fit = None

    def set_left_trace(self, slot: int, x: np.ndarray, y: np.ndarray, pen: pg.QtGui.QPen):
        old = self.left_traces[slot]
        if old is not None:
            self.plot_item.removeItem(old)
        self.left_traces[slot] = self.plot_item.plot(x, y, pen=pen)

    def set_right_trace(self, slot: int, x: np.ndarray, y: np.ndarray, pen: pg.QtGui.QPen):
        old = self.right_traces[slot]
        if old is not None:
            self.right_vb.removeItem(old)
        item = pg.PlotDataItem(x, y, pen=pen)
        self.right_vb.addItem(item)
        self.right_traces[slot] = item

    def set_left_fit_line(self, x: np.ndarray, y: np.ndarray, pen: pg.QtGui.QPen):
        if self.left_fit is not None:
            self.plot_item.removeItem(self.left_fit)
        self.left_fit = self.plot_item.plot(x, y, pen=pen)

    def set_right_fit_line(self, x: np.ndarray, y: np.ndarray, pen: pg.QtGui.QPen):
        if self.right_fit is not None:
            self.right_vb.removeItem(self.right_fit)
        item = pg.PlotDataItem(x, y, pen=pen)
        self.right_vb.addItem(item)
        self.right_fit = item

    def set_autorange(self, axis: str, enabled: bool):
        if axis == "x":
            self.plot_item.enableAutoRange(x=enabled, y=False)
            self.right_vb.enableAutoRange(x=enabled, y=False)
        elif axis == "yl":
            self.plot_item.enableAutoRange(x=False, y=enabled)
        elif axis == "yr":
            self.right_vb.enableAutoRange(x=False, y=enabled)
        else:
            raise ValueError(axis)

    def set_manual_range(self, axis: str, lo: float, hi: float):
        if lo >= hi:
            return
        if axis == "x":
            self.plot_item.setXRange(lo, hi, padding=0.0)
            self.right_vb.setXRange(lo, hi, padding=0.0)
        elif axis == "yl":
            self.plot_item.setYRange(lo, hi, padding=0.0)
        elif axis == "yr":
            self.right_vb.setYRange(lo, hi, padding=0.0)
        else:
            raise ValueError(axis)

    def enable_measurement_cursors(self, enabled: bool):
        self.measure_enabled = enabled
        self.target_a.setVisible(enabled)
        self.target_b.setVisible(enabled)
        if enabled:
            (xmin, xmax), (ymin, ymax) = self.plot_item.viewRange()
            xmin, xmax = float(xmin), float(xmax)
            ymin, ymax = float(ymin), float(ymax)
            if np.isfinite(xmin) and np.isfinite(xmax) and xmax > xmin and np.isfinite(ymin) and np.isfinite(ymax) and ymax > ymin:
                xa = xmin + 0.25 * (xmax - xmin)
                xb = xmin + 0.75 * (xmax - xmin)
                ya = ymin + 0.50 * (ymax - ymin)
                yb = ymin + 0.50 * (ymax - ymin)
                self.target_a.setPos((xa, ya))
                self.target_b.setPos((xb, yb))
            self._emit_target_positions()

    def target_positions_left(self) -> Tuple[float, float, float, float]:
        pa = self.target_a.pos()
        pb = self.target_b.pos()
        return float(pa.x()), float(pa.y()), float(pb.x()), float(pb.y())

    def map_left_point_to_right_y(self, x: float, y_left: float) -> float:
        p_scene = self.plot_item.vb.mapViewToScene(QtCore.QPointF(x, y_left))
        p_right = self.right_vb.mapSceneToView(p_scene)
        return float(p_right.y())

    def _emit_target_positions(self):
        if not self.measure_enabled:
            return
        xA, yLA, xB, yLB = self.target_positions_left()
        self.sig_cursors_changed.emit(xA, yLA, xB, yLB)

    def _on_mouse_clicked(self, evt):
        if not self.measure_enabled:
            return
        mouse_event = evt[0]
        pos = mouse_event.scenePos()
        if not self.plot_item.sceneBoundingRect().contains(pos):
            return
        p_left = self.plot_item.vb.mapSceneToView(pos)
        x = float(p_left.x())
        yL = float(p_left.y())

        if mouse_event.button() == QtCore.Qt.LeftButton:
            self.target_a.setPos((x, yL))
        elif mouse_event.button() == QtCore.Qt.RightButton:
            self.target_b.setPos((x, yL))
        else:
            return
        self._emit_target_positions()

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if not self.plot_item.sceneBoundingRect().contains(pos):
            return
        mouse_point_left = self.plot_item.vb.mapSceneToView(pos)
        x = float(mouse_point_left.x())
        y_left = float(mouse_point_left.y())
        mouse_point_right = self.right_vb.mapSceneToView(pos)
        y_right = float(mouse_point_right.y())
        self.v_line.setPos(x)
        self.h_line.setPos(y_left)
        self.sig_mouse_moved.emit(x, y_left, y_right)


# -----------------------------
# UI helpers / styling
# -----------------------------

DERIVE_MODES = ["Raw", "1/col", "k*col", "colA-colB"]

DEFAULT_SLOT_COLORS_HEX = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
]


def qcolor_from_hex(hexstr: str) -> QtGui.QColor:
    c = QtGui.QColor(hexstr)
    return c if c.isValid() else QtGui.QColor("red")


def make_pen(color: QtGui.QColor, width: int = 2, dashed: bool = False) -> pg.QtGui.QPen:
    pen = pg.mkPen(color=color, width=width)
    if dashed:
        pen.setStyle(QtCore.Qt.DashLine)
    return pen


def linear_regression(x: np.ndarray, y: np.ndarray) -> Optional[Tuple[float, float, float]]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]
    if x.size < 2:
        return None
    x_mean = x.mean()
    y_mean = y.mean()
    sxx = np.sum((x - x_mean) ** 2)
    if sxx == 0:
        return None
    sxy = np.sum((x - x_mean) * (y - y_mean))
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    y_hat = slope * x + intercept
    ss_res = np.sum((y - y_hat) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return float(slope), float(intercept), float(r2)


class TraceRow(QtWidgets.QWidget):
    """
    One trace slot row:
      [Label] [Col A (wide)] [Mode] [k] [Col B (wide)] [Color tiny]
    """
    changed = QtCore.Signal()

    def __init__(self, label: str, default_color: QtGui.QColor, parent=None):
        super().__init__(parent=parent)
        self.label = label
        self.color = default_color

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.lbl = QtWidgets.QLabel(label)
        self.lbl.setMinimumWidth(18)
        lay.addWidget(self.lbl)

        self.cbA = QtWidgets.QComboBox()
        self._configure_wide_combo(self.cbA)
        lay.addWidget(self.cbA, 3)  # stretch

        self.cbMode = QtWidgets.QComboBox()
        self.cbMode.addItems(["(none)"] + DERIVE_MODES)
        self.cbMode.setMaximumWidth(55)
        lay.addWidget(self.cbMode, 0)

        self.kspin = QtWidgets.QDoubleSpinBox()
        self.kspin.setRange(-1e9, 1e9)
        self.kspin.setDecimals(6)
        self.kspin.setSingleStep(0.1)
        self.kspin.setValue(1.0)
        self.kspin.setMaximumWidth(55)
        lay.addWidget(self.kspin, 0)

        self.cbB = QtWidgets.QComboBox()
        self._configure_wide_combo(self.cbB)
        lay.addWidget(self.cbB, 3)  # stretch

        self.btnColor = QtWidgets.QPushButton("")
        self.btnColor.setToolTip("Choose color")
        self.btnColor.setFixedSize(18, 18)  # tiny square
        self._apply_btn_color()
        lay.addWidget(self.btnColor, 0)

        self.cbA.currentIndexChanged.connect(self._emit_changed)
        self.cbMode.currentIndexChanged.connect(self._on_mode_changed)
        self.kspin.valueChanged.connect(self._emit_changed)
        self.cbB.currentIndexChanged.connect(self._emit_changed)
        self.btnColor.clicked.connect(self._choose_color)

        self._on_mode_changed()

    def _configure_wide_combo(self, cb: QtWidgets.QComboBox):
        # Ensures combobox is willing to be wide and displays more text
        cb.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        cb.setMinimumWidth(150)
        cb.setMinimumContentsLength(30)
        cb.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        cb.setEditable(False)

        # Tooltip always shows current full text
        cb.currentTextChanged.connect(lambda t, _cb=cb: _cb.setToolTip(t))

    def _apply_btn_color(self):
        self.btnColor.setStyleSheet(f"background-color: {self.color.name()}; border: 1px solid #666;")

    def _choose_color(self):
        chosen = QtWidgets.QColorDialog.getColor(self.color, self, f"Choose color for {self.label}")
        if not chosen.isValid():
            return
        self.color = chosen
        self._apply_btn_color()
        self.changed.emit()

    def _on_mode_changed(self):
        mode = self.cbMode.currentText()
        # Enable/disable k and B based on mode
        self.kspin.setEnabled(mode == "k*col")
        self.cbB.setEnabled(mode == "colA-colB")
        self._emit_changed()

    def _emit_changed(self):
        self.changed.emit()

    def set_columns(self, cols: List[str]):
        # Preserve selection where possible
        prevA = self.cbA.currentText()
        prevB = self.cbB.currentText()

        for cb, include_none in ((self.cbA, True), (self.cbB, True)):
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("(none)")
            for c in cols:
                cb.addItem(c)
            cb.blockSignals(False)

        if prevA and prevA in [self.cbA.itemText(i) for i in range(self.cbA.count())]:
            self.cbA.setCurrentText(prevA)
        if prevB and prevB in [self.cbB.itemText(i) for i in range(self.cbB.count())]:
            self.cbB.setCurrentText(prevB)

    def get_config(self):
        return {
            "A": self.cbA.currentText(),
            "mode": self.cbMode.currentText(),
            "k": float(self.kspin.value()),
            "B": self.cbB.currentText(),
            "color": self.color,
        }


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Plot theme:
        # Change THIS line for background shade:
        pg.setConfigOption("background", (245, 245, 245))  # slightly grey
        pg.setConfigOption("foreground", "k")

        self.setWindowTitle("Quick MR-Basic Plotter")
        self.resize(1450, 900)

        self.dataset: DataSet = make_demo_dataset()
        self.df_plot: pd.DataFrame = prepare_timeseries_dataframe(self.dataset, apply_offsets=True)
        self._available_cols: List[str] = numeric_columns(self.df_plot)

        self.slot_colors: List[QtGui.QColor] = [qcolor_from_hex(h) for h in DEFAULT_SLOT_COLORS_HEX]

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        outer_layout = QtWidgets.QVBoxLayout(central)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        # --- Top toolbar row ---
        toolbar_layout = QtWidgets.QHBoxLayout()
        self.btn_toggle_controls = QtWidgets.QPushButton("Hide Controls")
        toolbar_layout.addWidget(self.btn_toggle_controls)
        toolbar_layout.addStretch(1)
        outer_layout.addLayout(toolbar_layout)

        # --- Splitter ---
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        outer_layout.addWidget(self.splitter, 1)

        # --- Controls panel ---
        self.controls_widget = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(self.controls_widget)
        controls_layout.setContentsMargins(6, 6, 6, 6)
        controls_layout.setSpacing(8)

        # REMOVE any previous setMinimumWidth calls
        # controls.setMinimumWidth(...)  <-- DO NOT USE

        # --- Plot panel ---
        self.plot_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(self.plot_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Add widgets to splitter
        self.splitter.addWidget(self.controls_widget)
        self.splitter.addWidget(self.plot_widget)

        # Give plot more stretch priority
        self.splitter.setStretchFactor(0, 0)  # controls
        self.splitter.setStretchFactor(1, 1)  # plot

        # Initial size ratio (adjust if desired)
        self.splitter.setSizes([420, 1200])

        self.plot = DualAxisPlot()
        right_layout.addWidget(self.plot, 1)
        self.plot.plot_item.getAxis("bottom").enableAutoSIPrefix(False)

        self.delta_box = QtWidgets.QGroupBox("Cursors / Δ / Regression")
        delta_layout = QtWidgets.QVBoxLayout(self.delta_box)
        self.delta_text = QtWidgets.QPlainTextEdit()
        self.delta_text.setReadOnly(True)
        self.delta_text.setMaximumHeight(240)
        delta_layout.addWidget(self.delta_text)
        right_layout.addWidget(self.delta_box, 0)

        self.status = QtWidgets.QStatusBar()
        self.setStatusBar(self.status)
        self.plot.sig_mouse_moved.connect(self._update_status)
        self.plot.sig_cursors_changed.connect(self._on_cursors_changed)

        self._make_menu()

        # Metadata
        self.meta_box = QtWidgets.QGroupBox("Header / Metadata")
        meta_layout = QtWidgets.QVBoxLayout(self.meta_box)
        self.meta_text = QtWidgets.QPlainTextEdit()
        self.meta_text.setReadOnly(True)
        self.meta_text.setMaximumHeight(220)
        meta_layout.addWidget(self.meta_text)
        controls_layout.addWidget(self.meta_box)

        # Data prep
        self.prep_box = QtWidgets.QGroupBox("Data Prep")
        prep_layout = QtWidgets.QHBoxLayout(self.prep_box)
        self.chk_offsets = QtWidgets.QCheckBox("Apply Offsets (if present)")
        self.chk_offsets.setChecked(self.dataset.offsets is not None)
        prep_layout.addWidget(self.chk_offsets)
        prep_layout.addStretch(1)
        controls_layout.addWidget(self.prep_box)

        # Axes / traces
        self.sel_box = QtWidgets.QGroupBox("Axes / Traces")
        sel_v = QtWidgets.QVBoxLayout(self.sel_box)

        # X selector row
        xrow = QtWidgets.QHBoxLayout()
        xrow.addWidget(QtWidgets.QLabel("X (bottom)"))
        self.cb_x = QtWidgets.QComboBox()
        self.cb_x.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.cb_x.setMinimumWidth(420)
        self.cb_x.setMinimumContentsLength(50)
        self.cb_x.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cb_x.currentTextChanged.connect(lambda t: self.cb_x.setToolTip(t))
        xrow.addWidget(self.cb_x, 1)
        sel_v.addLayout(xrow)

        # Time units row
        trow = QtWidgets.QHBoxLayout()
        trow.addWidget(QtWidgets.QLabel("Time units"))
        self.cb_time_units = QtWidgets.QComboBox()
        self.cb_time_units.addItems(["seconds", "minutes", "hours", "days"])
        self.cb_time_units.setToolTip("Scale X axis display units (does not modify data)")
        self.cb_time_units.setMaximumWidth(140)
        trow.addWidget(self.cb_time_units)
        trow.addStretch(1)
        sel_v.addLayout(trow)

        self.cb_time_units.currentIndexChanged.connect(self.refresh_plot_only)

        sel_v.addWidget(QtWidgets.QLabel("Trace slots: A, mode, k, B, color"))

        self.trace_rows: List[TraceRow] = []
        labels = ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]
        for i, lab in enumerate(labels):
            tr = TraceRow(lab, self.slot_colors[i])
            tr.changed.connect(self.refresh_plot_only)
            self.trace_rows.append(tr)
            sel_v.addWidget(tr)

        controls_layout.addWidget(self.sel_box)

        # Scaling
        self.scale_box = QtWidgets.QGroupBox("Scaling")
        sc = QtWidgets.QGridLayout(self.scale_box)

        self.x_auto = QtWidgets.QCheckBox("Auto X")
        self.x_auto.setChecked(True)
        sc.addWidget(self.x_auto, 0, 0)
        self.x_lo = QtWidgets.QLineEdit()
        self.x_hi = QtWidgets.QLineEdit()
        self.x_lo.setPlaceholderText("X min")
        self.x_hi.setPlaceholderText("X max")
        sc.addWidget(self.x_lo, 0, 1)
        sc.addWidget(self.x_hi, 0, 2)

        self.yl_auto = QtWidgets.QCheckBox("Auto Y (left)")
        self.yl_auto.setChecked(True)
        sc.addWidget(self.yl_auto, 1, 0)
        self.yl_lo = QtWidgets.QLineEdit()
        self.yl_hi = QtWidgets.QLineEdit()
        self.yl_lo.setPlaceholderText("YL min")
        self.yl_hi.setPlaceholderText("YL max")
        sc.addWidget(self.yl_lo, 1, 1)
        sc.addWidget(self.yl_hi, 1, 2)

        self.yr_auto = QtWidgets.QCheckBox("Auto Y (right)")
        self.yr_auto.setChecked(True)
        sc.addWidget(self.yr_auto, 2, 0)
        self.yr_lo = QtWidgets.QLineEdit()
        self.yr_hi = QtWidgets.QLineEdit()
        self.yr_lo.setPlaceholderText("YR min")
        self.yr_hi.setPlaceholderText("YR max")
        sc.addWidget(self.yr_lo, 2, 1)
        sc.addWidget(self.yr_hi, 2, 2)

        controls_layout.addWidget(self.scale_box)

        # Measurement
        self.measure_box = QtWidgets.QGroupBox("Measurement")
        mb = QtWidgets.QVBoxLayout(self.measure_box)
        self.chk_measure = QtWidgets.QCheckBox("Enable A/B point cursors (Left click=A, Right click=B)")
        mb.addWidget(self.chk_measure)
        controls_layout.addWidget(self.measure_box)

        # Apply
        self.btn_apply = QtWidgets.QPushButton("Apply selections / ranges")
        controls_layout.addWidget(self.btn_apply)
        controls_layout.addStretch(1)

        # Signals
        self.btn_apply.clicked.connect(self.refresh_everything)
        self.chk_offsets.toggled.connect(self.refresh_everything)

        self.x_auto.toggled.connect(self.refresh_plot_only)
        self.yl_auto.toggled.connect(self.refresh_plot_only)
        self.yr_auto.toggled.connect(self.refresh_plot_only)
        self.cb_x.currentIndexChanged.connect(self.refresh_plot_only)

        self.chk_measure.toggled.connect(self._toggle_measurement)

        # Load initial UI
        self.btn_toggle_controls.clicked.connect(self._toggle_controls)

        self._load_dataset_into_ui(self.dataset)
        self.refresh_everything()
        self._toggle_measurement(False)

    def _time_scale_factor(self) -> float:
        """Multiply seconds by this to get selected display unit."""
        unit = getattr(self, "cb_time_units", None)
        if unit is None:
            return 1.0
        u = self.cb_time_units.currentText()
        if u == "seconds":
            return 1.0
        if u == "minutes":
            return 1.0 / 60.0
        if u == "hours":
            return 1.0 / 3600.0
        if u == "days":
            return 1.0 / 86400.0
        return 1.0

    def _time_unit_label(self) -> str:
        u = getattr(self, "cb_time_units", None)
        if u is None:
            return "sec"
        t = self.cb_time_units.currentText()
        return {"seconds": "sec", "minutes": "min", "hours": "h", "days": "d"}.get(t, "sec")

    def _scale_x(self, x_seconds: np.ndarray) -> np.ndarray:
        return x_seconds * self._time_scale_factor()

    def _toggle_controls(self):
        if self.controls_widget.isVisible():
            self.controls_widget.setVisible(False)
            self.btn_toggle_controls.setText("Show Controls")
        else:
            self.controls_widget.setVisible(True)
            self.btn_toggle_controls.setText("Hide Controls")
            self.splitter.setSizes([420, 1200])

    def _make_menu(self):
        file_menu = self.menuBar().addMenu("&File")
        act_open = QtGui.QAction("&Open MR-Basic CSV...", self)
        act_open.triggered.connect(self.open_file)
        file_menu.addAction(act_open)
        act_demo = QtGui.QAction("&Load Demo Data", self)
        act_demo.triggered.connect(self.load_demo)
        file_menu.addAction(act_demo)
        file_menu.addSeparator()
        act_exit = QtGui.QAction("E&xit", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

    def load_demo(self):
        self.dataset = make_demo_dataset()
        self._load_dataset_into_ui(self.dataset)
        self.refresh_everything()

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Data File", "", "Data Files (*.csv *.txt);;All Files (*)"
        )
        if not path:
            return
        try:
            ds = load_mrbasic_csv(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load error", f"Failed to load:\n{e}")
            return
        self.dataset = ds
        self._load_dataset_into_ui(self.dataset)
        self.refresh_everything()

    def _load_dataset_into_ui(self, ds: DataSet):
        self.meta_text.setPlainText("\n".join([f"{k}: {v}" for k, v in ds.meta.items()]))

        self.chk_offsets.blockSignals(True)
        self.chk_offsets.setChecked(ds.offsets is not None)
        self.chk_offsets.blockSignals(False)

        # Prepare plot df
        self.df_plot = prepare_timeseries_dataframe(ds, apply_offsets=self.chk_offsets.isChecked())
        self._available_cols = numeric_columns(self.df_plot)

        # Fill X
        self.cb_x.blockSignals(True)
        self.cb_x.clear()
        for c in self._available_cols:
            self.cb_x.addItem(c)
        self.cb_x.blockSignals(False)

        # Choose default X
        preferred_x = None
        for c in self._available_cols:
            lc = c.lower()
            if lc.startswith("time") and "[sec" in lc:
                preferred_x = c
                break
        if preferred_x is None:
            for candidate in ("Time [Sec.]", "Time", "time", "t", "x"):
                if candidate in self._available_cols:
                    preferred_x = candidate
                    break
        if preferred_x and preferred_x in self._available_cols:
            self.cb_x.setCurrentText(preferred_x)
        elif self.cb_x.count() > 0:
            self.cb_x.setCurrentIndex(0)

        # Fill trace rows
        for tr in self.trace_rows:
            tr.set_columns(self._available_cols)
            tr.cbMode.setCurrentText("(none)")
            tr.kspin.setValue(1.0)

        # Demo defaults
        if "sin [a.u.]" in self._available_cols:
            self.trace_rows[0].cbA.setCurrentText("sin [a.u.]")
            self.trace_rows[0].cbMode.setCurrentText("Raw")
        if "cos [a.u.]" in self._available_cols:
            self.trace_rows[1].cbA.setCurrentText("cos [a.u.]")
            self.trace_rows[1].cbMode.setCurrentText("Raw")

    def refresh_everything(self):
        # Re-prepare df_plot with offsets toggle
        self.df_plot = prepare_timeseries_dataframe(self.dataset, apply_offsets=self.chk_offsets.isChecked())
        self._available_cols = numeric_columns(self.df_plot)

        # Preserve X if possible
        prev_x = self.cb_x.currentText()
        self.cb_x.blockSignals(True)
        self.cb_x.clear()
        for c in self._available_cols:
            self.cb_x.addItem(c)
        if prev_x in self._available_cols:
            self.cb_x.setCurrentText(prev_x)
        elif self.cb_x.count() > 0:
            self.cb_x.setCurrentIndex(0)
        self.cb_x.blockSignals(False)

        # Update trace columns (preserve selections)
        for tr in self.trace_rows:
            tr.set_columns(self._available_cols)

        self.refresh_plot_only()

    def _parse_float(self, w: QtWidgets.QLineEdit) -> Optional[float]:
        s = w.text().strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    def _apply_scaling(self):
        x_auto = self.x_auto.isChecked()
        self.plot.set_autorange("x", x_auto)
        if not x_auto:
            lo = self._parse_float(self.x_lo)
            hi = self._parse_float(self.x_hi)
            if lo is not None and hi is not None:
                self.plot.set_manual_range("x", lo, hi)

        yl_auto = self.yl_auto.isChecked()
        self.plot.set_autorange("yl", yl_auto)
        if not yl_auto:
            lo = self._parse_float(self.yl_lo)
            hi = self._parse_float(self.yl_hi)
            if lo is not None and hi is not None:
                self.plot.set_manual_range("yl", lo, hi)

        yr_auto = self.yr_auto.isChecked()
        self.plot.set_autorange("yr", yr_auto)
        if not yr_auto:
            lo = self._parse_float(self.yr_lo)
            hi = self._parse_float(self.yr_hi)
            if lo is not None and hi is not None:
                self.plot.set_manual_range("yr", lo, hi)

    def _compute_trace_y(self, df: pd.DataFrame, cfg: dict) -> Optional[np.ndarray]:
        colA = cfg["A"]
        mode = cfg["mode"]
        k = cfg["k"]
        colB = cfg["B"]

        if mode == "(none)" or colA == "(none)" or colA not in df.columns:
            return None

        a = df[colA].to_numpy(copy=False)

        if mode == "Raw":
            return a
        if mode == "1/col":
            with np.errstate(divide="ignore", invalid="ignore"):
                return 1.0 / a
        if mode == "k*col":
            return float(k) * a
        if mode == "colA-colB":
            if colB == "(none)" or colB not in df.columns:
                return None
            b = df[colB].to_numpy(copy=False)
            return a - b
        return None

    def refresh_plot_only(self):
        self.plot.clear_traces()

        df = self.df_plot
        if df is None or df.empty:
            return

        x_col = self.cb_x.currentText()
        if x_col not in df.columns:
            return
        #x = df[x_col].to_numpy(copy=False)
        x_seconds = df[x_col].to_numpy(copy=False)
        x = self._scale_x(x_seconds)
        # Update bottom axis label with unit
        self.plot.plot_item.setLabel(
            "bottom",
            text=f"{x_col} ({self._time_unit_label()})"
        )

        # Plot all slots
        for idx, tr in enumerate(self.trace_rows):
            cfg = tr.get_config()
            y = self._compute_trace_y(df, cfg)
            if y is None:
                continue
            pen = make_pen(cfg["color"], width=2)
            if idx < 4:
                self.plot.set_left_trace(idx, x, y, pen)
            else:
                self.plot.set_right_trace(idx - 4, x, y, pen)

        self._apply_scaling()

        if self.chk_measure.isChecked():
            xA, yLA, xB, yLB = self.plot.target_positions_left()
            self._on_cursors_changed(xA, yLA, xB, yLB)
        else:
            self.plot.clear_fit_lines()

    def _toggle_measurement(self, enabled: bool):
        self.plot.enable_measurement_cursors(enabled)
        if enabled:
            xA, yLA, xB, yLB = self.plot.target_positions_left()
            self._on_cursors_changed(xA, yLA, xB, yLB)
        else:
            self.delta_text.setPlainText("")
            self.plot.clear_fit_lines()

    @QtCore.Slot(float, float, float)
    def _update_status(self, x: float, y_left: float, y_right: float):
        #self.status.showMessage(f"x={x:.6g} | yL={y_left:.6g} | yR={y_right:.6g}")
        unit = self._time_unit_label()
        self.status.showMessage(f"x={x:.6g} {unit} | yL={y_left:.6g} | yR={y_right:.6g}")

    @QtCore.Slot(float, float, float, float)
    def _on_cursors_changed(self, xA: float, yLA: float, xB: float, yLB: float):
        # y on right axis at the cursor points (same screen locations, mapped to right axis scale)
        yRA = self.plot.map_left_point_to_right_y(xA, yLA)
        yRB = self.plot.map_left_point_to_right_y(xB, yLB)

        dx = xB - xA
        dyL = yLB - yLA
        dyR = yRB - yRA

        unit = self._time_unit_label() if hasattr(self, "_time_unit_label") else ""

        # Line through two cursor points (no fitting)
        eps = 1e-15
        if abs(dx) < eps:
            # Vertical line in x: slope is infinite/undefined
            left_line = "Left line (A→B): vertical (Δx≈0), slope undefined"
            right_line = "Right line (A→B): vertical (Δx≈0), slope undefined"
            mL = bL = mR = bR = None
        else:
            mL = dyL / dx
            bL = yLA - mL * xA

            mR = dyR / dx
            bR = yRA - mR * xA

            left_line = f"Left line (A→B):  yL = {mL:.6g} * x + {bL:.6g}"
            right_line = f"Right line (A→B): yR = {mR:.6g} * x + {bR:.6g}"

        out = [
            f"A: x={xA:.6g} {unit}  yL={yLA:.6g}  yR={yRA:.6g}",
            f"B: x={xB:.6g} {unit}  yL={yLB:.6g}  yR={yRB:.6g}",
            "",
            f"Δx  = {dx:.6g} {unit}",
            f"ΔyL = {dyL:.6g}   (left axis scale)",
            f"ΔyR = {dyR:.6g}   (right axis scale)",
            "",
            left_line,
            right_line,
        ]
        self.delta_text.setPlainText("\n".join(out))

    def _fit_first_active(self, axis: str, x_col: str, x1: float, x2: float):
        df = self.df_plot
        if x_col not in df.columns:
            return None
        # x = df[x_col].to_numpy(copy=False)
        x_seconds = df[x_col].to_numpy(copy=False)
        x = self._scale_x(x_seconds)

        slots = range(0, 4) if axis == "left" else range(4, 8)
        chosen = None
        chosen_cfg = None

        for idx in slots:
            cfg = self.trace_rows[idx].get_config()
            y = self._compute_trace_y(df, cfg)
            if y is None:
                continue
            chosen = idx
            chosen_cfg = cfg
            break
        if chosen is None or chosen_cfg is None:
            return None

        y = self._compute_trace_y(df, chosen_cfg)
        m = np.isfinite(x) & np.isfinite(y) & (x >= x1) & (x <= x2)
        if m.sum() < 2:
            return None

        xw = x[m]
        yw = y[m]
        reg = linear_regression(xw, yw)
        if reg is None:
            return None
        slope, intercept, r2 = reg

        xf = np.array([x1, x2], dtype=float)
        yf = slope * xf + intercept

        name = self._describe_trace(chosen_cfg)
        color = chosen_cfg["color"]
        return name, slope, intercept, r2, xf, yf, color

    def _describe_trace(self, cfg: dict) -> str:
        colA = cfg["A"]
        mode = cfg["mode"]
        k = cfg["k"]
        colB = cfg["B"]
        if mode == "Raw":
            return colA
        if mode == "1/col":
            return f"1/({colA})"
        if mode == "k*col":
            return f"{k:g}*({colA})"
        if mode == "colA-colB":
            return f"({colA})-({colB})"
        return colA


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()