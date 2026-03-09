
# REFACTORING_PLAN.md

## Objective

Modularize the single-file architecture without changing behavior.

---

## Phase 1 — Split by Responsibility

Proposed structure:

```id="k3ab8z"
project/
│
├── main.py
├── ui/
│   ├── main_window.py
│   ├── trace_row.py
│
├── plot/
│   └── dual_axis_plot.py
│
├── data/
│   ├── dataset.py
│   ├── parser.py
│   ├── transform.py
│
└── utils/
    └── regression.py
```

---

## Phase 2 — Extract Data Layer

Move:

* `DataSet`
* CSV parsing logic
* Offset handling
* Numeric coercion

Into `data/`.

---

## Phase 3 — Extract Plot Layer

Move:

* `DualAxisPlot`
* Crosshair logic
* Cursor logic

Into `plot/`.

---

## Phase 4 — Extract UI Layer

Move:

* `TraceRow`
* Layout code
* Scaling controls

Into `ui/`.

---

## Phase 5 — Add Configuration Persistence

Add optional:

* JSON config file
* Last used trace selections
* Last used time unit

---

## Phase 6 — Add Plugin Hooks (Optional)

Introduce transform registry:

```id="olndv5"
TRANSFORM_REGISTRY = {
    "Raw": raw_func,
    "1/col": reciprocal_func,
    ...
}
```

Allows future extension without editing core logic.

---

## Refactoring Constraints

* Must preserve numerical outputs exactly.
* Must preserve cursor slope logic.
* Must preserve offset toggle semantics.
* Must not introduce silent behavioral changes.

---

# VERSION.md

## Versioning Scheme

Semantic Versioning:

```id="ymw50x"
MAJOR.MINOR.PATCH
```

---

## Current Version

```id="7yz4zi"
1.0.0
```

### 1.0.0 Definition

* Robust MR-Basic CSV parsing
* Offset detection + toggle
* Dual-axis plotting (4+4 traces)
* Derived column transforms
* Time unit scaling
* Manual/auto axis scaling
* Crosshair
* Two cursor markers
* Direct slope/intercept calculation from cursor points
* No statistical fitting
* Hide controls panel
* Individual trace colors

---

## Future Version Targets

### 1.1.0

* Save/restore configuration
* Export visible region

### 1.2.0

* Optional statistical regression mode (explicit toggle)

### 2.0.0

* Modularized multi-file architecture

---