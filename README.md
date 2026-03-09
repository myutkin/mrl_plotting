This is a vibecoded app. The code is entirely written by AI, and so are the README and other docs. I do not take credit for it except a couple of evenings that I spent guiding AI to write it and for realizing the need for such an app. You are free to take it and do whatever you wish. As I do not take credit, nor do I take any responsibility for the app actions, crashes etc. Text below explains what it is.
---
Below is a structured `README.md` suitable for both human developers and AI agents. It explains architecture, design decisions, implemented features, and extension points clearly and unambiguously.

You can save this as `README.md` in your project root.

---

# Quick MR-Basic Plotter

A lightweight interactive plotting application for rapid inspection and measurement of MR-Basic core flood data files.

Built with:

* **PySide6** (Qt GUI framework)
* **pyqtgraph** (high-performance plotting)
* **pandas / numpy** (data handling)

This tool is designed for **fast exploratory visualization**, not publication-quality plotting.

---

# 1. Purpose

The application enables:

* Loading MR-Basic CSV-style files with complex headers
* Dual Y-axis plotting (left + right)
* Up to 8 simultaneous traces (4 per axis)
* Simple derived-column transforms
* Manual or automatic axis scaling
* Interactive crosshair
* Two draggable cursor markers (A/B)
* Direct slope/intercept calculation between A and B
* Optional offset correction
* Selectable time display units (sec/min/hr/day)

The workflow is optimized for laboratory analysis and quick physical interpretation.

---

# 2. Project Architecture Overview

The application is organized into **four logical layers**:

```
┌──────────────────────────────┐
│          GUI Layer           │
│  (MainWindow, TraceRow UI)   │
└──────────────────────────────┘
                │
┌──────────────────────────────┐
│        Plotting Layer        │
│       (DualAxisPlot)         │
└──────────────────────────────┘
                │
┌──────────────────────────────┐
│     Data Transformation      │
│ (prepare_timeseries_dataframe)│
└──────────────────────────────┘
                │
┌──────────────────────────────┐
│         File Parsing         │
│      (load_mrbasic_csv)      │
└──────────────────────────────┘
```

Each layer has clearly defined responsibilities.

---

# 3. File Structure

All logic currently resides in:

```
main.py
```

Internal structure:

| Component                        | Responsibility                                     |
| -------------------------------- | -------------------------------------------------- |
| `DataSet`                        | Container for raw dataframe, metadata, and offsets |
| `load_mrbasic_csv()`             | Robust parsing of MR-Basic CSV files               |
| `prepare_timeseries_dataframe()` | Offset application and row filtering               |
| `DualAxisPlot`                   | Plot canvas, dual axes, crosshair, cursor handling |
| `TraceRow`                       | UI widget for configuring a single trace slot      |
| `MainWindow`                     | Application controller and GUI assembly            |

---

# 4. Implemented Features

## 4.1 File Handling

* Robust text decoding:

  * UTF-8
  * UTF-8-SIG
  * CP1252
  * Latin-1 fallback
* Strips problematic control characters
* Automatically detects:

  * Header section
  * Metadata block
  * Column names + units
  * Offsets row
  * Zero Voltage row
* Offsets optionally applied via checkbox
* Metadata displayed in GUI

---

## 4.2 Plotting Capabilities

### Dual Axis

* Left Y-axis: up to 4 traces
* Right Y-axis: up to 4 traces
* Shared X-axis

### Time Unit Scaling

User-selectable display units:

* seconds
* minutes
* hours
* days

Scaling affects:

* Plot X values
* Cursor readout
* Δx
* Slope calculation

Data remains stored internally in seconds.

---

## 4.3 Trace Configuration (8 Slots)

Each trace slot supports:

* Column A selection
* Transform mode:

  * Raw
  * 1/col
  * k*col
  * colA - colB
* Optional second column (for subtraction)
* Scalar multiplier k
* Individually selectable color

Color defaults use a high-contrast palette.

---

## 4.4 Scaling Controls

For each axis:

* Auto-scale toggle
* Manual min/max entry

Axes:

* X
* Left Y
* Right Y

---

## 4.5 Interactive Measurement

### Crosshair

* Tracks mouse position
* Displays x, yL, yR in status bar

### Two Cursors (A/B)

* Left click → Cursor A
* Right click → Cursor B
* Draggable
* Independent of plotted traces

### Output

For cursors A and B:

* Coordinates in display units
* Δx
* Δy (left axis scale)
* Δy (right axis scale)

### Line Through A and B

The tool computes:

```
m = (yB − yA) / (xB − xA)
b = yA − m·xA
```

Separately for left and right axis scales.

No statistical fitting is performed.
No regression against data points.
No R².

This is intentional for rapid visual analysis.

---

# 5. Internal Logic Details

## 5.1 Data Flow

1. Raw CSV parsed into DataFrame.
2. Offsets optionally applied.
3. Derived traces computed dynamically.
4. X scaled according to selected time unit.
5. Plot updated.

No data mutation occurs during plotting.

---

## 5.2 Time Scaling Implementation

Scaling factor:

| Unit    | Factor  |
| ------- | ------- |
| seconds | 1       |
| minutes | 1/60    |
| hours   | 1/3600  |
| days    | 1/86400 |

Axis SI prefix scaling is disabled to prevent `900 × 10⁻³ h` formatting.

---

## 5.3 Derived Column Evaluation

Implemented modes:

* Raw → `A`
* 1/col → `1/A`
* k*col → `k*A`
* colA-colB → `A - B`

Operations use numpy vectorized arithmetic.
Division errors handled via `np.errstate`.

---

## 5.4 Cursor-Based Line Calculation

Slope and intercept computed purely from cursor positions.
Independent of trace data.

Edge case:

* If Δx ≈ 0 → slope undefined.

---

# 6. User Interface Structure

Main layout:

```
┌───────────────────────────────┐
│ Toolbar (Hide Controls)       │
├──────────────┬────────────────┤
│ Controls     │ Plot Area      │
│ Panel        │                │
│              │ + Δ Box        │
└──────────────┴────────────────┘
```

Controls panel contains:

* Metadata
* Data prep
* Axis/trace configuration
* Scaling
* Measurement
* Apply button

Controls panel can be hidden to maximize plot space.

---

# 7. Design Philosophy

This application prioritizes:

* Speed
* Clarity
* Deterministic behavior
* Manual interpretability

It deliberately avoids:

* Automatic smoothing
* Implicit statistical fitting
* Hidden transformations
* Publication formatting features

It is a laboratory instrument interface, not a figure generator.

---

# 8. Extensibility Points

Future enhancements could include:

* Multi-trace regression
* Export visible window to CSV
* Save/restore trace configurations
* Session persistence
* Region selection tool
* Moving average / filtering options
* Trace visibility toggle
* Trace renaming
* Plot legend control
* Batch file comparison

Architecture supports these without refactoring core layers.

---

# 9. Installation

```bash
python -m pip install PySide6 pyqtgraph pandas numpy
python main.py
```

Cross-platform:

* Linux
* Windows

---

# 10. Known Limitations

* All logic in single file
* No persistent settings
* No undo history
* No large-dataset streaming (loads fully into memory)
* No plugin architecture

---

# 11. Intended Usage Context

This tool is intended for:

* Core flood experiments
* Pressure/flow transient inspection
* Quick slope estimation
* Comparative analysis of multiple channels
* Lab-side data inspection

It is not intended for publication figure production.

---

If you would like, I can next generate:

* A versioned README (v1.0 tagged)
* A CONTRIBUTING.md for AI-assisted development
* A technical design document (TDD) for long-term maintenance
* A minimal refactoring plan to split into modules without breaking functionality
