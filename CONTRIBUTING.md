
# CONTRIBUTING.md

## Contribution Guidelines

This project is structured for deterministic, laboratory-grade behavior. Contributions must preserve clarity, predictability, and traceability.

---

## 1. Design Principles

1. No hidden transformations.
2. No implicit statistical fitting.
3. All numeric transformations must be explicit in UI.
4. Avoid magic behavior.
5. Prefer simple logic over abstraction layers.
6. Maintain interactive performance.

---

## 2. Coding Standards

### General

* Python 3.9+
* PEP8 formatting
* Type hints preferred
* No global state mutations outside `MainWindow`

### Numerical Logic

* Use numpy vectorized operations.
* Guard divisions using `np.errstate`.
* Always mask non-finite values before regression or slope calculations.

### UI Logic

* UI must never silently change data.
* Any transformation must be user-triggered.
* No automatic smoothing.

---

## 3. File Parsing Rules

When modifying CSV parsing:

* Do not remove robust encoding fallback.
* Do not assume UTF-8 only.
* Preserve offset detection.
* Never mutate `df_raw`.

---

## 4. Regression / Cursor Logic Policy

The application uses:

> Line defined strictly by two cursor points.

No statistical fitting is permitted unless added as a clearly separate feature.

---

## 5. Adding New Features

When adding:

* A new transformation mode → extend `_compute_trace_y`
* A new axis control → extend `_apply_scaling`
* A new measurement feature → modify `_on_cursors_changed`

Do not embed logic inside the plotting class unless it is strictly rendering-related.

---

## 6. Performance Rules

* Avoid copying large arrays unnecessarily.
* Use `.to_numpy(copy=False)` where possible.
* Do not loop row-wise over DataFrames.

---

## 7. AI Contribution Policy

If an AI modifies code:

* It must not change numerical meaning silently.
* It must not introduce implicit smoothing.
* It must not alter cursor behavior.
* It must not introduce background threads unless explicitly requested.

All AI-generated changes should:

* Preserve deterministic logic.
* Preserve time scaling behavior.
* Preserve explicit offset toggle.

---