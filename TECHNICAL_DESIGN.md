
## 1. System Overview

The application is a single-process GUI tool built around three core subsystems:

```id="md53hb"
Data Parsing
→ Data Preparation
→ Interactive Plot Rendering
```

---

## 2. Data Model

### DataSet

```id="nsv7gf"
@dataclass
class DataSet:
    df_raw: pd.DataFrame
    meta: Dict[str, str]
    offsets: Optional[pd.Series]
```

### df_raw

Contains:

* Full parsed CSV table
* Includes Zero Voltage and Offsets rows

### df_plot

Derived from `df_raw` using:

```id="v3urgh"
prepare_timeseries_dataframe(...)
```

Applies:

* Row filtering
* Optional offset correction

---

## 3. Plot Architecture

### DualAxisPlot

Responsibilities:

* Maintain left and right ViewBox
* Handle crosshair
* Handle A/B cursor targets
* Emit cursor position signals

It does NOT:

* Interpret data
* Apply transformations
* Apply offsets

---

## 4. Data Transformation Layer

Function:

```id="wwj69q"
_compute_trace_y(...)
```

Supported modes:

* Raw
* 1/col
* k*col
* colA-colB

All transforms operate on numpy arrays.

---

## 5. Time Scaling

Time scaling is a display-layer transformation only.

```id="0vdl0h"
_scale_x(x_seconds)
```

Scaling affects:

* Plot X values
* Cursor values
* Δx
* Slope calculation

Original data remains in seconds.

---

## 6. Measurement System

Two `TargetItem` objects:

* Cursor A
* Cursor B

Slope defined as:

```id="sz3o1v"
m = (yB − yA) / (xB − xA)
b = yA − m·xA
```

Computed independently for:

* Left axis scale
* Right axis scale

No statistical fitting performed.

---

## 7. Axis Scaling

Manual scaling applied via:

```id="d6p9u5"
set_manual_range(axis, lo, hi)
```

Auto-scaling uses pyqtgraph’s `enableAutoRange`.

SI prefix auto-scaling disabled for X axis.

---

## 8. Performance Characteristics

* Entire dataset loaded into memory.
* Plotting uses vectorized numpy arrays.
* No streaming or chunk loading.
* Suitable for moderately large datasets (tens to hundreds of thousands of rows).

---