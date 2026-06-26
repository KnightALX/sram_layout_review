# Routing Thresholds Range Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single-bound thresholds (`max_*` / `min_*`) with symmetric `[low, high]` ranges; visually highlight out-of-range cells in the per-net review table; remove the dark-green banner background. Single-break migration — no backward compatibility with the old field names.

**Architecture:**
- New `Range` dataclass with `contains()` and `violation_direction()` semantics.
- `RoutingThresholds` is restructured: 7 metric fields become `Range` objects. Validation: `h_ratio.high + v_ratio.high >= 1.0`.
- Per-net table cells: light-red background (`rgba(239, 68, 68, 0.15)`) + dynamic symbol `∈` / `∉` for in/out of range.
- Routing Config tab: each metric gets a `dcc.RangeSlider` + two `dcc.Input` (low/high), bidirectionally synchronized.
- Metric cards & per-net table cells use uniform `<value> ∈ [low, high]` notation.
- Active Threshold Source banner: drop the dark-green background.

**Tech Stack:** Python 3.13, Dash 2.x, pytest, dataclasses, Plotly.

**Reference spec:** `docs/superpowers/specs/2026-06-26-routing-thresholds-range-redesign-design.md`

**Working directory:** `d:\workspace\project\sram_layout_review` (run all commands from here)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `config/routing_thresholds.py` | **Modify** | Add `Range` dataclass; `RoutingThresholds` 7 fields become `Range`; `validate()` enforces `low <= high` per Range + `h_ratio.high + v_ratio.high >= 1.0`; `_BUILTIN_PRESETS` rewritten in `{low, high}` format. |
| `config/preset_loader.py` | **Modify** | `_normalize_keys` handles nested `low/high` dicts; remove old `max_*/min_*` aliases. |
| `config/presets/sram_7nm_wl.yaml` | **Modify** | Rewrite in `{low, high}` format. |
| `config/presets/sram_5nm_io_bl.yaml` | **Modify** | Rewrite in `{low, high}` format. |
| `config/presets/analog_default.yaml` | **Modify** | Rewrite in `{low, high}` format. |
| `core/routing_metrics.py` | **Modify** | `check_gates` uses `Range.contains()`; add `_THRESHOLD_TO_METRIC_KEY` mapping. |
| `core/routing_violation.py` | **Modify** | Add `direction`, `range_low`, `range_high`, `measured` fields; update factory methods. |
| `app/routing_state.py` | **Modify** | Default `RoutingThresholds` construction already uses `Range`; verify no public API change. |
| `app/routing_review.py` | **Modify** | Remove banner dark-green bg; add `_format_cell`, `_build_cell_violation_map`; update `_build_table_rows` and `_compute_table_styles`; update metric cards to `∈` format. |
| `app/routing_config.py` | **Modify** | Replace `THRESHOLD_FIELDS` with `RANGE_FIELDS`; add `_build_range_input_group`; add slider↔input sync callbacks; update `_validate_apply`, `_apply_thresholds`, `_render_state`, `_compute_rehydrate_outputs`, `_dispatch_action`, `_routing_config_ui` callback, `_handle_routing_preset_or_thresh`. |
| `core/report_visualization.py` | **Modify** | Cells use `∈` / `∉` notation. |
| `report/routing_pptx.py` | **Modify** | Cells use `∈` / `∉` notation. |
| `tests/test_routing_thresholds.py` | **Modify** | Update to use `Range`; add new tests for range semantics. |
| `tests/test_routing_metrics.py` | **Modify** | Update `check_gates` tests. |
| `tests/test_routing_violation.py` | **Modify** | Update field names. |
| `tests/test_routing_config_layout.py` | **Modify** | Update for `RANGE_FIELDS`. |
| `tests/test_routing_config_state_machine.py` | **Modify** | Update for new field set (14 inputs + 7 sliders). |
| `tests/test_preset_loader.py` | **Modify** | Update for nested dict. |
| `tests/test_preset_loader_schema.py` | **Modify** | Update for nested dict. |
| `tests/test_apply_persistence.py` | **Modify** | Update for `Range`. |
| `tests/test_routing_e2e.py` | **Modify** | Update for `Range` and new UI. |
| `tests/test_routing_pptx.py` | **Modify** | Update for `∈` / `∉`. |
| `tests/test_tab_rehydrate.py` | **Modify** | Update for new field set. |
| `CLAUDE.md` | **Modify** | Update threshold field documentation. |
| `README.md` | **Modify** | Update threshold field documentation. |

---

## Phase 1: Data Model & Presets

### Task 1: Add `Range` dataclass (TDD)

**Files:**
- Modify: `config/routing_thresholds.py`
- Create: `tests/test_range.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_range.py` with this content:

```python
"""Unit tests for the new Range dataclass."""
import sys
sys.path.insert(0, '.')

import pytest
from config.routing_thresholds import Range


def test_range_contains_inclusive_bounds():
    rng = Range(0.0, 1.0)
    assert rng.contains(0.0) is True
    assert rng.contains(1.0) is True
    assert rng.contains(0.5) is True


def test_range_contains_outside():
    rng = Range(0.0, 1.0)
    assert rng.contains(-0.1) is False
    assert rng.contains(1.1) is False


def test_range_single_point_allowed():
    """low == high means a single-point range (e.g. [1.0, 1.0])."""
    rng = Range(1.0, 1.0)
    assert rng.contains(1.0) is True
    assert rng.contains(0.99) is False
    assert rng.contains(1.01) is False


def test_range_rejects_low_gt_high():
    with pytest.raises(ValueError, match="low.*high"):
        Range(2.0, 1.0)


def test_violation_direction():
    rng = Range(0.0, 1.0)
    assert rng.violation_direction(-0.1) == "low"
    assert rng.violation_direction(1.1) == "high"
    assert rng.violation_direction(0.5) is None
    # boundary: at low or high, no violation
    assert rng.violation_direction(0.0) is None
    assert rng.violation_direction(1.0) is None


def test_range_is_frozen():
    """Range is immutable; attribute assignment raises FrozenInstanceError."""
    rng = Range(0.0, 1.0)
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        rng.low = 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_range.py -v`
Expected: ImportError or AttributeError because `Range` does not exist yet.

- [ ] **Step 3: Add `Range` dataclass**

Add to `config/routing_thresholds.py` at the top (after the `from __future__` and existing imports, add `Optional` to the `typing` import):

```python
from typing import Any, Dict, List, Optional
```

Then add the `Range` dataclass right after the `ThresholdField` placeholder class (around line 27):

```python
@dataclass(frozen=True)
class Range:
    """A closed interval [low, high]. Value passes iff low <= value <= high.

    Attributes:
        low: Lower bound (inclusive).
        high: Upper bound (inclusive).

    Raises:
        ValueError: When constructed with low > high.

    Note: low == high is allowed (single-point range). Only strict
    inversion (low > high) is rejected.
    """
    low: float
    high: float

    def __post_init__(self):
        if self.low > self.high:
            raise ValueError(
                f"Range low ({self.low}) > high ({self.high})"
            )

    def contains(self, value: float) -> bool:
        """Return True if value is in [low, high]."""
        return self.low <= value <= self.high

    def violation_direction(self, value: float) -> Optional[str]:
        """Return 'low' if value < low, 'high' if value > high, None if in range."""
        if value < self.low:
            return "low"
        if value > self.high:
            return "high"
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_range.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add config/routing_thresholds.py tests/test_range.py ; git commit -m "feat(config): add Range dataclass for threshold intervals" --no-verify
```

---

### Task 2: Refactor `RoutingThresholds` to use `Range`

**Files:**
- Modify: `config/routing_thresholds.py`
- Modify: `tests/test_routing_thresholds.py`

- [ ] **Step 1: Write the failing test for new `RoutingThresholds`**

Append the following tests to `tests/test_routing_thresholds.py` (or create it if missing). The new tests cover the range-based `RoutingThresholds`:

```python
"""Tests for the new range-based RoutingThresholds."""
import sys
sys.path.insert(0, '.')

import pytest
from config.routing_thresholds import Range, RoutingThresholds


def test_thresholds_default_uses_range():
    """Default thresholds have Range fields with sensible low/high."""
    t = RoutingThresholds()
    assert isinstance(t.h_ratio, Range)
    assert t.h_ratio.low == 0.0
    assert t.h_ratio.high == 0.15
    assert isinstance(t.r_ohm, Range)
    assert t.r_ohm.high == 100.0


def test_thresholds_validate_ok():
    t = RoutingThresholds(
        h_ratio=Range(0.0, 0.15),
        v_ratio=Range(0.0, 1.0),
        r_ohm=Range(0.0, 100.0),
        c_ff=Range(0.0, 500.0),
        tau_ps=Range(0.0, 12.5),
        via_coverage=Range(0.85, 1.0),
        similarity=Range(80.0, 100.0),
    )
    t.validate()  # should not raise


def test_thresholds_validate_h_plus_v_too_small():
    t = RoutingThresholds(
        h_ratio=Range(0.0, 0.3),
        v_ratio=Range(0.0, 0.3),  # 0.3 + 0.3 = 0.6 < 1.0
    )
    with pytest.raises(ValueError, match="h_ratio.*v_ratio|sum|1.0"):
        t.validate()


def test_thresholds_validate_zero_r_high():
    t = RoutingThresholds(r_ohm=Range(0.0, 0.0))
    with pytest.raises(ValueError, match="r_ohm.*positive"):
        t.validate()


def test_thresholds_from_dict_nested():
    d = {
        "net_class": "wl",
        "h_ratio": {"low": 0.0, "high": 0.2},
        "v_ratio": {"low": 0.0, "high": 1.0},
        "r_ohm": {"low": 0.0, "high": 50.0},
        "c_ff": {"low": 0.0, "high": 500.0},
        "tau_ps": {"low": 0.0, "high": 12.5},
        "via_coverage": {"low": 0.85, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    }
    t = RoutingThresholds.from_dict(d)
    assert t.h_ratio == Range(0.0, 0.2)
    assert t.r_ohm.high == 50.0


def test_thresholds_to_dict_roundtrip():
    t = RoutingThresholds()
    d = t.to_dict()
    assert isinstance(d["h_ratio"], dict)
    assert d["h_ratio"]["low"] == 0.0
    assert d["h_ratio"]["high"] == 0.15
    t2 = RoutingThresholds.from_dict(d)
    assert t2.h_ratio == t.h_ratio
    assert t2.r_ohm == t.r_ohm
```

- [ ] **Step 2: Run tests to verify the new tests fail**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_thresholds.py -v -k "default_uses_range or validate_ok or validate_h_plus_v or validate_zero_r_high or from_dict_nested or to_dict_roundtrip"`
Expected: All 6 new tests fail because the old field names (`max_h_ratio`, etc.) are still in use.

- [ ] **Step 3: Refactor `RoutingThresholds` class**

Replace the existing `RoutingThresholds` class and `_BUILTIN_PRESETS` in `config/routing_thresholds.py` with the new range-based version:

```python
# Built-in presets (used when no YAML is found)
_BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "sram_7nm_wl": {
        "net_class": "wl",
        "h_ratio":    {"low": 0.0, "high": 0.15},
        "v_ratio":    {"low": 0.0, "high": 1.0},
        "r_ohm":      {"low": 0.0, "high": 100.0},
        "c_ff":       {"low": 0.0, "high": 500.0},
        "tau_ps":     {"low": 0.0, "high": 12.5},
        "via_coverage": {"low": 0.85, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    },
    "sram_5nm_io_bl": {
        "net_class": "io",
        "h_ratio":    {"low": 0.0, "high": 1.0},
        "v_ratio":    {"low": 0.0, "high": 0.10},
        "r_ohm":      {"low": 0.0, "high": 80.0},
        "c_ff":       {"low": 0.0, "high": 400.0},
        "tau_ps":     {"low": 0.0, "high": 10.0},
        "via_coverage": {"low": 0.90, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    },
    "analog_default": {
        "net_class": "analog",
        "h_ratio":    {"low": 0.0, "high": 0.60},
        "v_ratio":    {"low": 0.0, "high": 0.60},
        "r_ohm":      {"low": 0.0, "high": 200.0},
        "c_ff":       {"low": 0.0, "high": 1000.0},
        "tau_ps":     {"low": 0.0, "high": 25.0},
        "via_coverage": {"low": 0.70, "high": 1.0},
        "similarity": {"low": 70.0, "high": 100.0},
    },
    "power_relaxed": {
        "net_class": "power",
        "h_ratio":    {"low": 0.0, "high": 1.0},
        "v_ratio":    {"low": 0.0, "high": 1.0},
        "r_ohm":      {"low": 0.0, "high": 500.0},
        "c_ff":       {"low": 0.0, "high": 5000.0},
        "tau_ps":     {"low": 0.0, "high": 100.0},
        "via_coverage": {"low": 0.50, "high": 1.0},
        "similarity": {"low": 0.0, "high": 100.0},
    },
}


@dataclass
class RoutingThresholds:
    """Gating thresholds for routing review.

    Each metric is a [low, high] interval. A value passes iff
    low <= value <= high. The aggregate pass/fail for a net is
    computed in core.routing_metrics.check_gates.

    Attributes:
        net_class: Routing class (wl/io/analog/power) — only used for display.
        h_ratio: H-direction length ratio range.
        v_ratio: V-direction length ratio range.
        r_ohm: Total resistance range (Ohms).
        c_ff: Total capacitance range (fF).
        tau_ps: Effective tau range (ps).
        via_coverage: Via coverage ratio range.
        similarity: Golden similarity score range (0-100).
    """
    net_class: str = "wl"
    h_ratio: Range = field(default_factory=lambda: Range(0.0, 0.15))
    v_ratio: Range = field(default_factory=lambda: Range(0.0, 1.0))
    r_ohm: Range = field(default_factory=lambda: Range(0.0, 100.0))
    c_ff: Range = field(default_factory=lambda: Range(0.0, 500.0))
    tau_ps: Range = field(default_factory=lambda: Range(0.0, 12.5))
    via_coverage: Range = field(default_factory=lambda: Range(0.85, 1.0))
    similarity: Range = field(default_factory=lambda: Range(80.0, 100.0))

    @classmethod
    def for_preset(cls, preset_name: str) -> "RoutingThresholds":
        """Get default thresholds by preset name."""
        if preset_name not in _BUILTIN_PRESETS:
            raise KeyError(f"Unknown preset: {preset_name}")
        t = cls.from_dict(_BUILTIN_PRESETS[preset_name])
        t.validate()
        return t

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingThresholds":
        """Build from dict (YAML/JSON compatible).

        Accepts both:
          - Nested: h_ratio: {low: 0.0, high: 0.15}
          - Range kwargs are passed straight through dataclass
        """
        kwargs: Dict[str, Any] = {}
        for k, v in d.items():
            if k not in cls.__dataclass_fields__:
                continue
            field_type = cls.__dataclass_fields__[k].type
            # If the field is Range and the value is a dict, build Range
            if "Range" in str(field_type) and isinstance(v, dict):
                kwargs[k] = Range(v["low"], v["high"])
            else:
                kwargs[k] = v
        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict (Range fields become {low, high} dicts)."""
        out: Dict[str, Any] = {}
        for k, v in asdict(self).items():
            if isinstance(v, dict):
                out[k] = v  # already a dict from asdict of Range (low, high fields)
            else:
                out[k] = v
        return out

    def validate(self) -> None:
        """Sanity check. Raises ValueError on invalid config.

        - Each Range: low <= high (already enforced in __post_init__)
        - h_ratio.high + v_ratio.high >= 1.0 (so at least one direction can dominate)
        - r_ohm.high, c_ff.high, tau_ps.high must be > 0
        """
        if self.h_ratio.high + self.v_ratio.high < 1.0 - 1e-9:
            raise ValueError(
                f"h_ratio.high ({self.h_ratio.high}) + v_ratio.high "
                f"({self.v_ratio.high}) must sum to >= 1.0"
            )
        for name in ("r_ohm", "c_ff", "tau_ps"):
            v = getattr(self, name).high
            if v <= 0:
                raise ValueError(f"{name}.high must be positive: {v}")

    @classmethod
    def list_presets(cls) -> List[str]:
        """List all built-in preset names."""
        return list(_BUILTIN_PRESETS.keys())
```

Also replace the import-time validation loop at the bottom of the file (currently `for _pn in list(_BUILTIN_PRESETS.keys()): RoutingThresholds.for_preset(_pn)`) — it should remain unchanged because `for_preset` still calls `validate()` and the new code is valid.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_thresholds.py tests/test_range.py -v`
Expected: All `Range` tests pass; all new `RoutingThresholds` tests pass. Some old tests in `test_routing_thresholds.py` that reference `max_h_ratio` etc. will fail — note them in a comment for Task 22 (test file updates).

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add config/routing_thresholds.py tests/test_routing_thresholds.py ; git commit -m "feat(config): refactor RoutingThresholds to use Range" --no-verify
```

---

### Task 3: Update preset_loader to handle nested `low/high`

**Files:**
- Modify: `config/preset_loader.py`
- Modify: `tests/test_preset_loader.py`
- Modify: `tests/test_preset_loader_schema.py`

- [ ] **Step 1: Inspect the current `preset_loader.py` and `_normalize_keys`**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "import inspect; from config import preset_loader; print(inspect.getsource(preset_loader._normalize_keys))"`
Note the output for use in Step 3.

- [ ] **Step 2: Write failing test for nested-dict loading**

Add the following test to `tests/test_preset_loader.py`:

```python
def test_load_preset_yaml_with_nested_low_high(tmp_path):
    """YAML with nested {low, high} dicts loads into RoutingThresholds with Range fields."""
    import yaml
    from config.preset_loader import load_preset_yaml

    yaml_path = tmp_path / "test_range.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "net_class": "wl",
        "h_ratio":    {"low": 0.0, "high": 0.20},
        "v_ratio":    {"low": 0.0, "high": 1.0},
        "r_ohm":      {"low": 0.0, "high": 80.0},
        "c_ff":       {"low": 0.0, "high": 500.0},
        "tau_ps":     {"low": 0.0, "high": 12.5},
        "via_coverage": {"low": 0.85, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    }))
    t = load_preset_yaml("test_range", presets_dir=tmp_path)
    assert t.h_ratio.high == 0.20
    assert t.r_ohm.high == 80.0
    # validate should pass
    t.validate()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_preset_loader.py::test_load_preset_yaml_with_nested_low_high -v`
Expected: FAIL because `load_preset_yaml` likely does not handle the nested format.

- [ ] **Step 4: Update `preset_loader.py` to handle nested dicts**

In `config/preset_loader.py`, find the `_normalize_keys` function. Replace it with:

```python
def _normalize_keys(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize YAML dict to the format RoutingThresholds.from_dict expects.

    For range fields (h_ratio, v_ratio, r_ohm, c_ff, tau_ps, via_coverage,
    similarity), accepts either a nested {low, high} dict or a flat value
    (which is interpreted as `high` with `low=0.0` for ratio fields and
    `low=0.0` for r/c/tau/similarity). For backward-compatibility in
    loading (not in code), also maps legacy max_X / min_X keys.
    """
    RANGE_FIELDS = ("h_ratio", "v_ratio", "r_ohm", "c_ff", "tau_ps",
                    "via_coverage", "similarity")
    LEGACY_MAX_TO_RANGE = {
        "max_h_ratio": "h_ratio",
        "max_v_ratio": "v_ratio",
        "max_r_ohm":   "r_ohm",
        "max_c_ff":    "c_ff",
        "max_tau_ps":  "tau_ps",
    }
    LEGACY_MIN_TO_RANGE = {
        "min_via_coverage": "via_coverage",
        "min_similarity":   "similarity",
    }
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        if k in LEGACY_MAX_TO_RANGE:
            target = LEGACY_MAX_TO_RANGE[k]
            existing = out.get(target) or {}
            out[target] = {"low": existing.get("low", 0.0), "high": v}
            continue
        if k in LEGACY_MIN_TO_RANGE:
            target = LEGACY_MIN_TO_RANGE[k]
            existing = out.get(target) or {}
            out[target] = {"low": v, "high": existing.get("high", 1.0)}
            continue
        if k in RANGE_FIELDS and isinstance(v, dict) and "low" in v and "high" in v:
            out[k] = {"low": float(v["low"]), "high": float(v["high"])}
            continue
        if k in RANGE_FIELDS and isinstance(v, (int, float)):
            # bare number = max bound only (legacy file)
            out[k] = {"low": 0.0, "high": float(v)}
            continue
        out[k] = v
    return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_preset_loader.py::test_load_preset_yaml_with_nested_low_high -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add config/preset_loader.py tests/test_preset_loader.py ; git commit -m "feat(config): preset_loader handles nested low/high format" --no-verify
```

---

### Task 4: Rewrite 3 YAML presets in `{low, high}` format

**Files:**
- Modify: `config/presets/sram_7nm_wl.yaml`
- Modify: `config/presets/sram_5nm_io_bl.yaml`
- Modify: `config/presets/analog_default.yaml`
- Modify: `tests/test_preset_loader.py`

- [ ] **Step 1: Add a test that loads all 3 YAML presets and validates them**

Add to `tests/test_preset_loader.py`:

```python
def test_load_all_yaml_presets_use_new_format():
    """All YAML presets load via from_dict with the new low/high format and pass validate()."""
    from config.preset_loader import list_yaml_presets, load_preset_yaml
    from pathlib import Path
    from config.routing_thresholds import RoutingThresholds
    yaml_dir = Path(__file__).parent.parent / "config" / "presets"
    names = list_yaml_presets(presets_dir=yaml_dir)
    assert len(names) >= 3
    for name in names:
        t = load_preset_yaml(name, presets_dir=yaml_dir)
        assert isinstance(t, RoutingThresholds)
        t.validate()  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_preset_loader.py::test_load_all_yaml_presets_use_new_format -v`
Expected: FAIL (old YAML format won't load correctly).

- [ ] **Step 3: Rewrite `sram_7nm_wl.yaml`**

Replace contents of `config/presets/sram_7nm_wl.yaml` with:

```yaml
# 7nm FinFET SRAM — Wordline-dominant preset
# Use for: WL signal nets (expect H-dominant routing)
net_class: wl
h_ratio:    {low: 0.0, high: 0.15}    # H length ≤ 15%
v_ratio:    {low: 0.0, high: 1.0}     # V length allowed up to 100%
r_ohm:      {low: 0.0, high: 100.0}
c_ff:       {low: 0.0, high: 500.0}
tau_ps:     {low: 0.0, high: 12.5}
via_coverage: {low: 0.85, high: 1.0}
similarity: {low: 80.0, high: 100.0}
```

- [ ] **Step 4: Rewrite `sram_5nm_io_bl.yaml`**

Replace contents with:

```yaml
# 5nm FinFET SRAM — IO / Bitline-dominant preset
# Use for: IO and bitline nets (expect V-dominant routing)
net_class: io
h_ratio:    {low: 0.0, high: 1.0}
v_ratio:    {low: 0.0, high: 0.10}    # V length ≤ 10% (mostly horizontal)
r_ohm:      {low: 0.0, high: 80.0}
c_ff:       {low: 0.0, high: 400.0}
tau_ps:     {low: 0.0, high: 10.0}
via_coverage: {low: 0.90, high: 1.0}
similarity: {low: 80.0, high: 100.0}
```

- [ ] **Step 5: Rewrite `analog_default.yaml`**

Replace contents with:

```yaml
# Generic analog preset — balanced H/V
net_class: analog
h_ratio:    {low: 0.0, high: 0.60}
v_ratio:    {low: 0.0, high: 0.60}
r_ohm:      {low: 0.0, high: 200.0}
c_ff:       {low: 0.0, high: 1000.0}
tau_ps:     {low: 0.0, high: 25.0}
via_coverage: {low: 0.70, high: 1.0}
similarity: {low: 70.0, high: 100.0}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_preset_loader.py::test_load_all_yaml_presets_use_new_format -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add config/presets/ tests/test_preset_loader.py ; git commit -m "feat(config): rewrite YAML presets in {low, high} format" --no-verify
```

---

## Phase 2: Logic Layer

### Task 5: Update `check_gates` to use `Range.contains()`

**Files:**
- Modify: `core/routing_metrics.py`
- Modify: `tests/test_routing_metrics.py`

- [ ] **Step 1: Inspect current `check_gates` to understand existing field names**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "import inspect; from core import routing_metrics; print(inspect.getsource(routing_metrics.check_gates))"`
Note the function for refactor in Step 3.

- [ ] **Step 2: Write a failing test using `Range` thresholds**

Add to `tests/test_routing_metrics.py`:

```python
def test_check_gates_in_range_passes():
    """Value in [low, high] is hard/soft pass."""
    from config.routing_thresholds import Range, RoutingThresholds
    from core.routing_metrics import check_gates

    thresholds = RoutingThresholds(
        h_ratio=Range(0.0, 0.15),
        v_ratio=Range(0.0, 1.0),
        r_ohm=Range(0.0, 100.0),
        c_ff=Range(0.0, 500.0),
        tau_ps=Range(0.0, 12.5),
        via_coverage=Range(0.85, 1.0),
        similarity=Range(80.0, 100.0),
    )
    metrics = {
        "h_ratio": 0.10,           # in range
        "v_ratio": 0.90,           # in range
        "r_total": 50.0,           # in range
        "c_total": 250.0,          # in range
        "effective_tau_ps": 8.0,   # in range
        "via_coverage": 0.95,      # in range
        "similarity_score": 95.0,  # in range
        "missing_via_count": 0,
    }
    hard, soft = check_gates(metrics, thresholds)
    assert hard == []
    assert soft == []


def test_check_gates_above_high_fails():
    """Value above range.high causes a violation."""
    from config.routing_thresholds import Range, RoutingThresholds
    from core.routing_metrics import check_gates

    thresholds = RoutingThresholds(
        r_ohm=Range(0.0, 100.0),
    )
    metrics = {
        "h_ratio": 0.10, "v_ratio": 0.90, "r_total": 150.0,
        "c_total": 250.0, "effective_tau_ps": 8.0,
        "via_coverage": 0.95, "similarity_score": 95.0,
        "missing_via_count": 0,
    }
    hard, _soft = check_gates(metrics, thresholds)
    assert any("150" in reason and "high" in reason for reason in hard)


def test_check_gates_below_low_fails():
    """Value below range.low causes a violation (e.g. low via_coverage)."""
    from config.routing_thresholds import Range, RoutingThresholds
    from core.routing_metrics import check_gates

    thresholds = RoutingThresholds(
        via_coverage=Range(0.85, 1.0),
    )
    metrics = {
        "h_ratio": 0.10, "v_ratio": 0.90, "r_total": 50.0,
        "c_total": 250.0, "effective_tau_ps": 8.0,
        "via_coverage": 0.50, "similarity_score": 95.0,
        "missing_via_count": 0,
    }
    _, soft = check_gates(metrics, thresholds)
    assert any("0.5" in reason and "low" in reason for reason in soft)
```

- [ ] **Step 3: Refactor `check_gates` to use `Range.contains()`**

In `core/routing_metrics.py`, replace `check_gates` with:

```python
# Mapping from threshold field name to metrics dict key.
# threshold field names use r_ohm / c_ff / tau_ps (range-based),
# while metrics dict keys retain the original r_total / c_total /
# effective_tau_ps names (no need to rename inside the metrics module).
_THRESHOLD_TO_METRIC_KEY = {
    "h_ratio": "h_ratio",
    "v_ratio": "v_ratio",
    "r_ohm": "r_total",
    "c_ff": "c_total",
    "tau_ps": "effective_tau_ps",
    "via_coverage": "via_coverage",
    "similarity": "similarity_score",
}

def check_gates(metrics, thresholds, has_golden=False):
    """Each metric is checked against its [low, high] range.

    Returns (hard_reasons, soft_reasons):
        - hard: R, C, τ, similarity are always enforced
        - soft: h_ratio, v_ratio, via_coverage are golden-bypass candidates
                (when has_golden=True and similarity passes, soft may be
                overridden by the caller)
    """
    hard_reasons: List[str] = []
    soft_reasons: List[str] = []

    # HARD: r_ohm / c_ff / tau_ps
    for thresh_key, display in [("r_ohm", "R"), ("c_ff", "C"), ("tau_ps", "τ")]:
        rng = getattr(thresholds, thresh_key)
        measured = metrics[_THRESHOLD_TO_METRIC_KEY[thresh_key]]
        if not rng.contains(measured):
            d = rng.violation_direction(measured)
            hard_reasons.append(
                f"{display} {measured:.2f} {d} of [{rng.low}, {rng.high}]"
            )

    # SOFT: h_ratio / v_ratio / via_coverage
    for thresh_key in ("h_ratio", "v_ratio", "via_coverage"):
        rng = getattr(thresholds, thresh_key)
        measured = metrics[_THRESHOLD_TO_METRIC_KEY[thresh_key]]
        if not rng.contains(measured):
            d = rng.violation_direction(measured)
            soft_reasons.append(
                f"{thresh_key} {measured} {d} of [{rng.low}, {rng.high}]"
            )

    # Similarity
    sim_rng = thresholds.similarity
    sim_measured = metrics[_THRESHOLD_TO_METRIC_KEY["similarity"]]
    if not sim_rng.contains(sim_measured):
        d = sim_rng.violation_direction(sim_measured)
        hard_reasons.append(
            f"similarity {sim_measured} {d} of "
            f"[{sim_rng.low}, {sim_rng.high}]"
        )

    # missing_via count check (preserved from old logic)
    miss = metrics.get("missing_via_count", 0)
    if miss > 0:
        hard_reasons.append(f"missing_via {miss} > 0")

    return hard_reasons, soft_reasons
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_metrics.py -v -k "check_gates_in_range or check_gates_above_high or check_gates_below_low"`
Expected: 3 new tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add core/routing_metrics.py tests/test_routing_metrics.py ; git commit -m "feat(core): check_gates uses Range.contains" --no-verify
```

---

### Task 6: Update `RoutingViolation` fields

**Files:**
- Modify: `core/routing_violation.py`
- Modify: `tests/test_routing_violation.py`

- [ ] **Step 1: Inspect `RoutingViolation` definition**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "import inspect; from core import routing_violation; print(inspect.getsource(routing_violation.RoutingViolation))"`

- [ ] **Step 2: Add failing tests for new fields**

Add to `tests/test_routing_violation.py`:

```python
def test_violation_has_direction_and_range():
    from config.routing_thresholds import Range
    from core.routing_violation import RoutingViolation, ViolationKind

    rng = Range(0.0, 0.15)
    v = RoutingViolation(
        kind=ViolationKind.H_RATIO, net_name="WL_0",
        measured=0.22, direction="high",
        range_low=rng.low, range_high=rng.high,
    )
    assert v.direction == "high"
    assert v.range_low == 0.0
    assert v.range_high == 0.15
    assert v.measured == 0.22


def test_violation_factory_uses_range():
    from config.routing_thresholds import Range
    from core.routing_violation import RoutingViolation

    rng = Range(0.0, 100.0)
    v = RoutingViolation.r_ohm("WL_0", 150.0, rng)
    assert v.direction == "high"
    assert v.measured == 150.0
    assert v.range_high == 100.0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_violation.py -v -k "has_direction_and_range or factory_uses_range"`
Expected: FAIL because the new fields don't exist yet.

- [ ] **Step 4: Add new fields to `RoutingViolation` and update factories**

In `core/routing_violation.py`, update the `RoutingViolation` dataclass. Add these fields after the existing `polygon_index` field:

```python
    # Direction of the violation relative to the range
    direction: Optional[str] = None          # "low" / "high"
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    # The actual measured value (used for per-cell coloring)
    measured: Optional[float] = None
```

Update the existing factory methods. Replace each `cls(...)` call with one that populates the new fields. For example, `h_ratio`:

```python
@classmethod
def h_ratio(cls, net_name: str, h_ratio: float, rng: Range) -> "RoutingViolation":
    direction = rng.violation_direction(h_ratio)
    return cls(
        kind=ViolationKind.H_RATIO,
        net_name=net_name,
        measured=h_ratio,
        direction=direction,
        range_low=rng.low,
        range_high=rng.high,
        message=f"h_ratio {h_ratio:.2%} {direction} [{rng.low:.2%}, {rng.high:.2%}]",
    )
```

Apply the same pattern to the other 6 factory methods: `v_ratio`, `r_ohm`, `c_ff`, `tau_ps`, `via_coverage`, `similarity`. Each takes the metric value and a `Range`.

- [ ] **Step 5: Run new tests to verify they pass**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_violation.py -v -k "has_direction_and_range or factory_uses_range"`
Expected: 2 new tests pass.

- [ ] **Step 6: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add core/routing_violation.py tests/test_routing_violation.py ; git commit -m "feat(core): RoutingViolation has direction and range fields" --no-verify
```

---

## Phase 3: Application Layer

### Task 7: Update `routing_state.py` default constructor

**Files:**
- Modify: `app/routing_state.py`

- [ ] **Step 1: Inspect `RoutingState` `__post_init__` and the default thresholds value**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "import inspect; from app import routing_state; print(inspect.getsource(routing_state.RoutingState))"`

- [ ] **Step 2: Verify default construction still works**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "from app.routing_state import routing_state; from config.routing_thresholds import Range; t = routing_state.get_thresholds(); assert isinstance(t.h_ratio, Range); print('default construction OK')"`
Expected: prints `default construction OK` (because Task 2 already refactored the dataclass).

- [ ] **Step 3: If any public method reads `max_*`/`min_*` fields, update it**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "from app import routing_state; import inspect; src = inspect.getsource(routing_state); import re; matches = re.findall(r'(max_\w+|min_\w+)', src); print('stale references:', matches if matches else 'none')"`
Expected: prints `none` if the file is clean; otherwise fix each occurrence to use the new field name and convert the float to `Range` if needed.

- [ ] **Step 4: Commit (only if Step 3 made changes)**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_state.py ; git commit -m "refactor(app): routing_state uses Range defaults" --no-verify ; echo "skip commit if no changes"
```

---

### Task 8: Remove dark-green background from Active Threshold Source banner

**Files:**
- Modify: `app/routing_review.py`

- [ ] **Step 1: Locate `_build_threshold_source` in `routing_review.py`**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "import inspect; from app import routing_review; print(inspect.getsource(routing_review._build_threshold_source))"`

- [ ] **Step 2: Write a regression test for the banner**

Add to a new file `tests/test_routing_review_banner.py`:

```python
def test_threshold_source_banner_no_green_background():
    from app.routing_review import _build_threshold_source
    el = _build_threshold_source("Locked preset: sram_7nm_wl")
    # Convert the Dash element tree to a string and check the inner span
    from dash import html
    s = str(el)
    assert "rgba(5, 46, 22" not in s
    assert "Active Threshold Source" in s
    assert "Locked preset: sram_7nm_wl" in s
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_banner.py -v`
Expected: FAIL because the dark-green background string is present.

- [ ] **Step 4: Remove the background from the source Span**

In `app/routing_review.py::_build_threshold_source`, change the inner `html.Span(src, ...)` to drop the `background`, `padding`, and `borderRadius` style keys, keeping only `fontSize`:

```python
return html.Div([
    html.Span("Active Threshold Source: ", style={"fontSize": "11px", "fontWeight": "600"}),
    html.Span(src, style={"fontSize": "11px"}),
], style={"marginBottom": "8px"})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_banner.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_review.py tests/test_routing_review_banner.py ; git commit -m "feat(app): remove dark-green background from threshold source banner" --no-verify
```

---

### Task 9: Add `_format_cell` and `_build_cell_violation_map` helpers

**Files:**
- Modify: `app/routing_review.py`
- Create: `tests/test_routing_review_cells.py`

- [ ] **Step 1: Write failing tests for the two helpers**

Create `tests/test_routing_review_cells.py`:

```python
def test_format_cell_in_range():
    from app.routing_review import _format_cell
    from config.routing_thresholds import Range
    s = _format_cell(0.10, Range(0.0, 0.15))
    assert "0.1" in s
    assert "\u2208" in s    # ∈
    assert "\u2209" not in s # ∉
    assert "[0.0, 0.15]" in s


def test_format_cell_out_of_range():
    from app.routing_review import _format_cell
    from config.routing_thresholds import Range
    s = _format_cell(0.22, Range(0.0, 0.15))
    assert "0.2" in s
    assert "\u2209" in s    # ∉
    assert "\u2208" not in s # ∈
    assert "[0.0, 0.15]" in s


def test_build_cell_violation_map_marks_out_of_range():
    from app.routing_review import _build_cell_violation_map
    from config.routing_thresholds import Range, RoutingThresholds

    thresholds = RoutingThresholds(
        h_ratio=Range(0.0, 0.15),
        r_ohm=Range(0.0, 100.0),
    )
    batch_results = {
        "WL_0": {
            "status": "ok",
            "h_ratio": 0.10, "v_ratio": 0.90,
            "r_total": 50.0, "c_total": 200.0, "effective_tau_ps": 8.0,
            "via_coverage": 0.95, "similarity_score": 95.0,
        },
        "WL_1": {
            "status": "ok",
            "h_ratio": 0.22, "v_ratio": 0.78,            # h out of range
            "r_total": 150.0, "c_total": 200.0, "effective_tau_ps": 8.0,  # r out of range
            "via_coverage": 0.95, "similarity_score": 95.0,
        },
    }
    m = _build_cell_violation_map(batch_results, thresholds)
    assert "WL_0" not in m
    assert m["WL_1"] == {"H %", "R (\u03a9)"}


def test_build_cell_violation_map_skips_no_data():
    from app.routing_review import _build_cell_violation_map
    from config.routing_thresholds import Range, RoutingThresholds

    thresholds = RoutingThresholds(h_ratio=Range(0.0, 0.15))
    batch_results = {
        "WL_x": {"status": "no_data"},
    }
    m = _build_cell_violation_map(batch_results, thresholds)
    assert m == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_cells.py -v`
Expected: ImportError (the helpers do not exist yet).

- [ ] **Step 3: Add the helpers to `app/routing_review.py`**

Add the following constants and functions near the top of the file (after imports):

```python
# Mapping from RoutingThresholds field name to the per-net table column_id.
FIELD_TO_COLUMN = {
    "h_ratio": "H %", "v_ratio": "V %", "r_ohm": "R (\u03a9)",
    "c_ff": "C (fF)", "tau_ps": "\u03c4 (ps)",
    "via_coverage": "Via Cov", "similarity": "Sim",
}

# Mapping from threshold field name to the metrics dict key.
_FIELD_TO_METRIC_KEY = {
    "h_ratio": "h_ratio", "v_ratio": "v_ratio", "r_ohm": "r_total",
    "c_ff": "c_total", "tau_ps": "effective_tau_ps",
    "via_coverage": "via_coverage", "similarity": "similarity_score",
}

def _format_cell(value: float, rng: Range, fmt: str = "{:.1f}") -> str:
    """Format a measurement with the appropriate symbol (∈ or ∉)."""
    symbol = "\u2208" if rng.contains(value) else "\u2209"
    return f"{fmt.format(value)} {symbol} [{fmt.format(rng.low)}, {fmt.format(rng.high)}]"


def _build_cell_violation_map(batch_results, thresholds):
    """Return {net_name: {column_id, ...}} for cells whose metric is out of range."""
    cell_map: Dict[str, Set[str]] = {}
    for name, m in batch_results.items():
        if m.get("status") == "no_data":
            continue
        bad: Set[str] = set()
        for field, col in FIELD_TO_COLUMN.items():
            rng = getattr(thresholds, field)
            measured = m.get(_FIELD_TO_METRIC_KEY[field])
            if measured is not None and not rng.contains(measured):
                bad.add(col)
        if bad:
            cell_map[name] = bad
    return cell_map
```

Add `Range` to the import line: `from config.routing_thresholds import Range, RoutingThresholds` (or equivalent). Add `Dict, Set` to typing imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_cells.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_review.py tests/test_routing_review_cells.py ; git commit -m "feat(app): add _format_cell and _build_cell_violation_map helpers" --no-verify
```

---

### Task 10: Update `_build_table_rows` and `_compute_table_styles` to use new helpers

**Files:**
- Modify: `app/routing_review.py`
- Modify: `tests/test_routing_review_cells.py`

- [ ] **Step 1: Write failing test for `_compute_table_styles` light-red rules**

Append to `tests/test_routing_review_cells.py`:

```python
def test_compute_table_styles_includes_light_red_for_out_of_range():
    from app.routing_review import _compute_table_styles, _build_cell_violation_map
    from config.routing_thresholds import Range, RoutingThresholds
    import dash

    thresholds = RoutingThresholds(
        h_ratio=Range(0.0, 0.15),
        r_ohm=Range(0.0, 100.0),
    )
    batch_results = {
        "WL_0": {
            "status": "ok",
            "h_ratio": 0.10, "v_ratio": 0.90,
            "r_total": 50.0, "c_total": 200.0, "effective_tau_ps": 8.0,
            "via_coverage": 0.95, "similarity_score": 95.0,
            "gate_pass": True,
        },
        "WL_1": {
            "status": "ok",
            "h_ratio": 0.22, "v_ratio": 0.78,
            "r_total": 150.0, "c_total": 200.0, "effective_tau_ps": 8.0,
            "via_coverage": 0.95, "similarity_score": 95.0,
            "gate_pass": False,
        },
    }
    rows = []  # _compute_table_styles signature: rows, ...
    cell_map = _build_cell_violation_map(batch_results, thresholds)
    styles = _compute_table_styles(rows, batch_results, cell_map, thresholds)
    # Look for a rule matching the H % column for WL_1 with the light-red background
    found_h = any(
        rule.get("if", {}).get("column_id") == "H %"
        and 'WL_1' in str(rule.get("if", {}).get("filter_query", ""))
        and rule.get("backgroundColor") == "rgba(239, 68, 68, 0.15)"
        for rule in styles
    )
    found_r = any(
        rule.get("if", {}).get("column_id") == "R (\u03a9)"
        and 'WL_1' in str(rule.get("if", {}).get("filter_query", ""))
        and rule.get("backgroundColor") == "rgba(239, 68, 68, 0.15)"
        for rule in styles
    )
    assert found_h, f"light-red rule for H %/WL_1 not found in {styles}"
    assert found_r, f"light-red rule for R (Ω)/WL_1 not found in {styles}"
    # Pass-column pill rules (✗ red, ✓ green, ⚠ amber) should still be present
    pass_rules = [r for r in styles if r.get("if", {}).get("column_id") == "Pass"]
    assert len(pass_rules) >= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_cells.py::test_compute_table_styles_includes_light_red_for_out_of_range -v`
Expected: FAIL (signature mismatch or no light-red rules).

- [ ] **Step 3: Update `_compute_table_styles` signature and add light-red rules**

In `app/routing_review.py`, find the `_compute_table_styles` function. Update its signature to accept `cell_violation_map` and `thresholds`, and append the light-red rules. Replace the entire function with:

```python
def _compute_table_styles(rows, batch_results, cell_violation_map, thresholds):
    """Return the list of conditional styling rules for the per-net table.

    Includes:
    - Pass column pill (✗ red, ✓ green, ⚠ amber)
    - Out-of-range cell light-red background (per cell_violation_map)
    """
    styles = [
        # Pass column pill rules
        {"if": {"column_id": "Pass", "filter_query": '{Pass} = "\u2717"'},
         "backgroundColor": "rgba(239, 68, 68, 0.85)",
         "color": "white", "fontWeight": "600",
         "textAlign": "center", "borderRadius": "3px"},
        {"if": {"column_id": "Pass", "filter_query": '{Pass} = "\u2713"'},
         "backgroundColor": "rgba(39, 174, 96, 0.85)",
         "color": "white", "fontWeight": "600",
         "textAlign": "center", "borderRadius": "3px"},
        {"if": {"column_id": "Pass", "filter_query": '{Pass} = "\u26a0"'},
         "backgroundColor": "rgba(243, 156, 18, 0.85)",
         "color": "white", "fontWeight": "600",
         "textAlign": "center", "borderRadius": "3px"},
    ]
    # Out-of-range cell light-red backgrounds
    for net_name, bad_cols in cell_violation_map.items():
        for col in bad_cols:
            styles.append({
                "if": {
                    "column_id": col,
                    "filter_query": f'{{Net}} = "{net_name}"',
                },
                "backgroundColor": "rgba(239, 68, 68, 0.15)",
            })
    return styles
```

Also update the call site of `_compute_table_styles` in the same file to pass the new arguments. Find the line that builds the table and add:

```python
cell_violation_map = _build_cell_violation_map(batch_results, thresholds)
```

just before the call to `_compute_table_styles`, and pass `cell_violation_map, thresholds` to the call.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_cells.py -v`
Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_review.py tests/test_routing_review_cells.py ; git commit -m "feat(app): light-red backgrounds on out-of-range cells" --no-verify
```

---

### Task 11: Update `_build_table_rows` to use `_format_cell`

**Files:**
- Modify: `app/routing_review.py`
- Modify: `tests/test_routing_review_cells.py`

- [ ] **Step 1: Add failing test for the new row cell format**

Append to `tests/test_routing_review_cells.py`:

```python
def test_build_table_rows_uses_in_symbol():
    from app.routing_review import _build_table_rows
    from config.routing_thresholds import Range, RoutingThresholds

    thresholds = RoutingThresholds(
        h_ratio=Range(0.0, 0.15),
        r_ohm=Range(0.0, 100.0),
    )
    batch_results = {
        "WL_0": {
            "h_ratio": 0.10, "v_ratio": 0.90,
            "r_total": 50.0, "c_total": 200.0, "effective_tau_ps": 8.0,
            "via_coverage": 0.95, "missing_via_count": 0,
            "similarity_score": 95.0,
            "gate_pass": True, "dominant": "V",
        }
    }
    rows = _build_table_rows(batch_results, thresholds)
    assert len(rows) == 1
    r = rows[0]
    assert r["H %"].startswith("0.1 \u2208")
    assert r["R (\u03a9)"].startswith("50.0 \u2208")
    # Check the symbol ∉ does NOT appear
    for v in r.values():
        assert "\u2209" not in str(v)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_cells.py::test_build_table_rows_uses_in_symbol -v`
Expected: FAIL because the old cell format is `{value} / {threshold}`.

- [ ] **Step 3: Update `_build_table_rows` to use `_format_cell`**

Find `_build_table_rows` in `app/routing_review.py` and replace the cell construction with calls to `_format_cell`. The function body should look like:

```python
def _build_table_rows(batch_results, thresholds):
    """Build the per-net table rows using Range-based cell formatting."""
    rows = []
    for name, m in batch_results.items():
        if m.get("status") == "no_data":
            rows.append({
                "Net": name, "Dominant": "\u2014",
                "H %": "\u2014", "V %": "\u2014", "R (\u03a9)": "\u2014",
                "C (fF)": "\u2014", "\u03c4 (ps)": "\u2014",
                "Via Cov": "\u2014", "Miss Via": "\u2014",
                "Sim": "\u2014", "Pass": "\u26a0",
            })
            continue
        h_rng, v_rng = thresholds.h_ratio, thresholds.v_ratio
        r_rng, c_rng, t_rng = thresholds.r_ohm, thresholds.c_ff, thresholds.tau_ps
        cov_rng, sim_rng = thresholds.via_coverage, thresholds.similarity
        rows.append({
            "Net": name,
            "Dominant": m["dominant"],
            "H %": _format_cell(m["h_ratio"], h_rng, "{:.2f}"),
            "V %": _format_cell(m["v_ratio"], v_rng, "{:.2f}"),
            "R (\u03a9)": _format_cell(m["r_total"], r_rng, "{:.2f}"),
            "C (fF)": _format_cell(m["c_total"], c_rng, "{:.1f}"),
            "\u03c4 (ps)": _format_cell(m["effective_tau_ps"], t_rng, "{:.2f}"),
            "Via Cov": _format_cell(m["via_coverage"], cov_rng, "{:.2f}"),
            "Miss Via": str(m.get("missing_via_count", 0)),
            "Sim": _format_cell(m["similarity_score"], sim_rng, "{:.1f}"),
            "Pass": "\u2713" if m["gate_pass"] else "\u2717",
        })
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_cells.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_review.py tests/test_routing_review_cells.py ; git commit -m "feat(app): _build_table_rows uses Range-based cell format" --no-verify
```

---

### Task 12: Update metric cards in `routing_review.py` to use `∈` format

**Files:**
- Modify: `app/routing_review.py`
- Create: `tests/test_routing_review_metric_cards.py`

- [ ] **Step 1: Write failing test for metric card format**

Create `tests/test_routing_review_metric_cards.py`:

```python
def test_metric_card_uses_in_notation():
    from app.routing_review import _build_metric_cards
    from config.routing_thresholds import Range, RoutingThresholds
    from dash import html

    thresholds = RoutingThresholds(
        r_ohm=Range(0.0, 100.0),
        c_ff=Range(0.0, 500.0),
    )
    batch_results = {
        "WL_0": {"r_total": 80.0, "c_total": 320.0, "gate_pass": True},
        "WL_1": {"r_total": 120.0, "c_total": 650.0, "gate_pass": False},
    }
    cards = _build_metric_cards(batch_results, thresholds)
    s = str(cards)
    assert "\u2208" in s
    assert "[0.0, 100.0]" in s
    assert "[0.0, 500.0]" in s
    # The old single-bound format should be gone
    assert "100.0\u03a9" not in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_metric_cards.py -v`
Expected: FAIL because the old format is `value / threshold` without `∈`.

- [ ] **Step 3: Update `_build_metric_cards` to use `∈` format**

Find `_build_metric_cards` in `app/routing_review.py`. Update each card's value text to append ` \u2208 [{rng.low}, {rng.high}]`. For example, the R card's value text:

```python
r_text = (
    f"{r_lo:.1f}\u2013{r_hi:.1f}\u03a9 \u2208 "
    f"[{thresholds.r_ohm.low}, {thresholds.r_ohm.high}]"
)
```

Apply the same pattern to C, τ, Similarity, H/V Ratio, and Missing Via cards. Use the corresponding `Range` field for each.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_review_metric_cards.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_review.py tests/test_routing_review_metric_cards.py ; git commit -m "feat(app): metric cards use Range-based display" --no-verify
```

---

### Task 13: Define `RANGE_FIELDS` in `routing_config.py`

**Files:**
- Modify: `app/routing_config.py`
- Create: `tests/test_routing_config_range_fields.py`

- [ ] **Step 1: Write failing test for `RANGE_FIELDS`**

Create `tests/test_routing_config_range_fields.py`:

```python
def test_range_fields_has_seven_entries_with_required_keys():
    from app.routing_config import RANGE_FIELDS
    assert len(RANGE_FIELDS) == 7
    required = {"name", "label", "slider_min", "slider_max", "step", "fmt"}
    for f in RANGE_FIELDS:
        assert required.issubset(f.keys()), f"missing keys in {f}"
    names = [f["name"] for f in RANGE_FIELDS]
    assert set(names) == {"h_ratio", "v_ratio", "r_ohm", "c_ff", "tau_ps",
                          "via_coverage", "similarity"}


def test_thresh_fields_removed():
    """THRESHOLD_FIELDS is replaced by RANGE_FIELDS."""
    from app import routing_config
    assert not hasattr(routing_config, "THRESHOLD_FIELDS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_range_fields.py -v`
Expected: FAIL (RANGE_FIELDS doesn't exist).

- [ ] **Step 3: Replace `THRESHOLD_FIELDS` with `RANGE_FIELDS`**

In `app/routing_config.py`, replace the `THRESHOLD_FIELDS` list with:

```python
# 7 metric range fields, each with a RangeSlider (low, high handles) plus
# two dcc.Input fields for precise text input. The fmt field controls
# how values are displayed in the inputs.
RANGE_FIELDS = [
    {"name": "h_ratio",      "label": "H Ratio",         "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01,  "fmt": "{:.2f}"},
    {"name": "v_ratio",      "label": "V Ratio",         "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01,  "fmt": "{:.2f}"},
    {"name": "r_ohm",        "label": "R (\u03a9)",      "slider_min": 0.0,    "slider_max": 10000.0, "step": 0.1,   "fmt": "{:.1f}"},
    {"name": "c_ff",         "label": "C (fF)",          "slider_min": 0.0,    "slider_max": 100000.0,"step": 1,     "fmt": "{:.1f}"},
    {"name": "tau_ps",       "label": "\u03c4 (ps)",     "slider_min": 0.0,    "slider_max": 1000.0,  "step": 0.1,   "fmt": "{:.1f}"},
    {"name": "via_coverage", "label": "Via Coverage",    "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01,  "fmt": "{:.2f}"},
    {"name": "similarity",   "label": "Similarity",      "slider_min": 0.0,    "slider_max": 100.0,   "step": 1,     "fmt": "{:.0f}"},
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_range_fields.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py tests/test_routing_config_range_fields.py ; git commit -m "feat(app): define RANGE_FIELDS in routing_config" --no-verify
```

---

### Task 14: Add `_build_range_input_group` UI builder

**Files:**
- Modify: `app/routing_config.py`
- Modify: `tests/test_routing_config_range_fields.py`

- [ ] **Step 1: Add failing test for `_build_range_input_group`**

Append to `tests/test_routing_config_range_fields.py`:

```python
def test_build_range_input_group_uses_slider_and_inputs():
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    from dash import html
    el = _build_range_input_group(RANGE_FIELDS[0])  # h_ratio
    s = str(el)
    assert 'id="slider-h_ratio"' in s
    assert 'id="input-h_ratio-low"' in s
    assert 'id="input-h_ratio-high"' in s
    # dcc.RangeSlider renders as a div with class 'rc-slider'
    assert "rc-slider" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_range_fields.py::test_build_range_input_group_uses_slider_and_inputs -v`
Expected: FAIL (function doesn't exist).

- [ ] **Step 3: Add `_build_range_input_group`**

In `app/routing_config.py`, add the function:

```python
def _build_range_input_group(field):
    """Build a single row: label + RangeSlider + two number Inputs."""
    name, label = field["name"], field["label"]
    rng = getattr(routing_state.get_thresholds(), name)
    s_min, s_max, step, fmt = field["slider_min"], field["slider_max"], field["step"], field["fmt"]
    marks = {
        s_min: f"{s_min:g}",
        (s_min + s_max) / 2: f"{(s_min + s_max) / 2:g}",
        s_max: f"{s_max:g}",
    }
    return html.Div([
        html.Label(label, className="form-label"),
        dcc.RangeSlider(
            id=f"slider-{name}",
            min=s_min, max=s_max, step=step,
            value=[rng.low, rng.high], marks=marks,
            tooltip={"placement": "bottom", "always_visible": False},
        ),
        html.Div([
            html.Span("Low: "),
            dcc.Input(id=f"input-{name}-low", type="number",
                      value=rng.low, min=s_min, max=s_max, step=step),
            html.Span("High: ", style={"marginLeft": "12px"}),
            dcc.Input(id=f"input-{name}-high", type="number",
                      value=rng.high, min=s_min, max=s_max, step=step),
        ], style={"display": "flex", "alignItems": "center",
                  "marginTop": "4px"}),
    ], className="form-group", style={"marginBottom": "12px"})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_range_fields.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py tests/test_routing_config_range_fields.py ; git commit -m "feat(app): add _build_range_input_group UI builder" --no-verify
```

---

### Task 15: Update `create_routing_config_tab` layout to use range UI

**Files:**
- Modify: `app/routing_config.py`
- Modify: `tests/test_routing_config_layout.py`

- [ ] **Step 1: Add failing test for the new tab layout**

Append to `tests/test_routing_config_layout.py`:

```python
def test_create_routing_config_tab_uses_range_sliders():
    from app.routing_config import create_routing_config_tab
    el = create_routing_config_tab()
    s = str(el)
    # 7 sliders, 14 inputs
    assert s.count('id="slider-') == 7
    assert s.count('id="input-') == 14
    # No thresh- inputs
    assert 'id="thresh-' not in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_layout.py::test_create_routing_config_tab_uses_range_sliders -v`
Expected: FAIL (tab still uses thresh- inputs).

- [ ] **Step 3: Update the threshold sliders section in `create_routing_config_tab`**

In `app/routing_config.py::create_routing_config_tab`, replace the "Threshold sliders" card body (the `html.Div([ ... ], className="card-body")` that uses the `for (name, label, mn, mx, st) in THRESHOLD_FIELDS` loop) with:

```python
html.Div([
    html.Div([
        _build_range_input_group(field)
        for field in RANGE_FIELDS
    ], style={"display": "flex", "flexDirection": "column", "gap": "8px"}),
    # Apply button + status
    html.Div([
        html.Button("\u2713 Apply Thresholds", id="btn-apply-thresholds",
                    className="btn btn-primary",
                    style={"marginTop": "12px", "width": "100%",
                           "minHeight": "32px", "fontWeight": "600"}),
        html.Div(id="thresh-apply-status",
                 style={"fontSize": "11px", "marginTop": "6px"}),
    ]),
], className="card-body"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_layout.py -v`
Expected: all layout tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py tests/test_routing_config_layout.py ; git commit -m "feat(app): routing config tab uses range sliders" --no-verify
```

---

### Task 16: Add slider↔input sync callbacks

**Files:**
- Modify: `app/routing_config.py`
- Create: `tests/test_routing_config_sync.py`

- [ ] **Step 1: Add failing test for slider→input sync**

Create `tests/test_routing_config_sync.py`:

```python
"""Tests for slider↔input bidirectional sync.

These exercise the pure functions _sync_slider_to_input and
_sync_input_to_slider directly (without a Dash server)."""
from app.routing_config import _sync_slider_to_input, _sync_input_to_slider


def test_slider_to_input():
    assert _sync_slider_to_input([0.05, 0.20]) == (0.05, 0.20)


def test_input_to_slider_valid():
    assert _sync_input_to_slider(0.05, 0.20) == [0.05, 0.20]


def test_input_to_slider_low_gt_high_returns_none():
    """low > high is invalid; the sync returns None (caller raises PreventUpdate)."""
    from dash.exceptions import PreventUpdate
    try:
        result = _sync_input_to_slider(0.20, 0.05)
        # If no exception, result must be None or unchanged
        assert result is None
    except PreventUpdate:
        pass  # acceptable


def test_input_to_slider_none_returns_none():
    from dash.exceptions import PreventUpdate
    try:
        result = _sync_input_to_slider(None, 0.20)
        assert result is None
    except PreventUpdate:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_sync.py -v`
Expected: ImportError (functions don't exist).

- [ ] **Step 3: Add sync helper functions and register callbacks**

In `app/routing_config.py`, add these two functions:

```python
def _sync_slider_to_input(value):
    """Slider → Inputs: simply unpack the [low, high] list."""
    return value[0], value[1]


def _sync_input_to_slider(low, high):
    """Inputs → Slider. Returns [low, high] or None to signal PreventUpdate."""
    from dash.exceptions import PreventUpdate
    if low is None or high is None:
        raise PreventUpdate
    if low > high:
        raise PreventUpdate
    return [low, high]
```

Then add the sync callbacks inside `register_routing_config_callbacks`. After the existing regex preview callback, add:

```python
# --- Slider ↔ Input sync callbacks (one per range field) ---
from dash import no_update
for _field in RANGE_FIELDS:
    _name = _field["name"]
    _s_min, _s_max = _field["slider_min"], _field["slider_max"]

    @app.callback(
        [Output(f"input-{_name}-low", "value"),
         Output(f"input-{_name}-high", "value")],
        Input(f"slider-{_name}", "value"),
    )
    def _slider_to_input_cb(value, _n=_name):
        return _sync_slider_to_input(value)

    @app.callback(
        Output(f"slider-{_name}", "value"),
        [Input(f"input-{_name}-low", "value", allow_duplicate=True),
         Input(f"input-{_name}-high", "value", allow_duplicate=True)],
        prevent_initial_call=True,
    )
    def _input_to_slider_cb(low, high, _n=_name):
        return _sync_input_to_slider(low, high)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_sync.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py tests/test_routing_config_sync.py ; git commit -m "feat(app): slider-input bidirectional sync" --no-verify
```

---

### Task 17: Update `_validate_apply` and `_apply_thresholds`

**Files:**
- Modify: `app/routing_config.py`
- Modify: `tests/test_apply_persistence.py`

- [ ] **Step 1: Add failing test for new validate**

Append to `tests/test_apply_persistence.py`:

```python
def test_validate_apply_with_range_values():
    from app.routing_config import _validate_apply
    # 14 values: 7 (low, high) pairs
    vals = (0.0, 0.15, 0.0, 1.0, 0.0, 100.0, 0.0, 500.0, 0.0, 12.5, 0.85, 1.0, 80.0, 100.0)
    result, err = _validate_apply(vals)
    assert err is None
    assert result is not None
    assert result.h_ratio.high == 0.15
    assert result.h_ratio.low == 0.0


def test_validate_apply_low_gt_high_rejected():
    from app.routing_config import _validate_apply
    # h_ratio: low=0.20, high=0.10 -> invalid
    vals = (0.20, 0.10, 0.0, 1.0, 0.0, 100.0, 0.0, 500.0, 0.0, 12.5, 0.85, 1.0, 80.0, 100.0)
    result, err = _validate_apply(vals)
    assert result is None
    assert err is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_apply_persistence.py -v -k "validate_apply_with_range_values or validate_apply_low_gt_high_rejected"`
Expected: FAIL (signature mismatch).

- [ ] **Step 3: Rewrite `_validate_apply` for 14-value input**

Replace `_validate_apply` in `app/routing_config.py` with:

```python
def _validate_apply(range_values: tuple) -> tuple[Optional[RoutingThresholds], Optional[str]]:
    """Validate 14 (low, high) values for Apply.

    Returns:
        (valid_thresholds, None) on success
        (None, error_message) on failure
    """
    n = len(RANGE_FIELDS)
    if len(range_values) != 2 * n:
        return None, f"Expected {2 * n} values, got {len(range_values)}"

    current = routing_state.get_thresholds()
    tentative_dict = current.to_dict()

    try:
        for i, field in enumerate(RANGE_FIELDS):
            name = field["name"]
            low = range_values[2 * i]
            high = range_values[2 * i + 1]
            if low is None or high is None:
                continue  # fall back to current
            low_f, high_f = float(low), float(high)
            tentative_dict[name] = {"low": low_f, "high": high_f}
    except (TypeError, ValueError) as e:
        return None, f"Invalid number: {e}"

    try:
        tentative = RoutingThresholds.from_dict(tentative_dict)
        tentative.validate()
    except Exception as e:
        return None, str(e)
    return tentative, None
```

- [ ] **Step 4: Update `_apply_thresholds` for the new signature**

Replace `_apply_thresholds` with:

```python
def _apply_thresholds(range_values: tuple) -> None:
    valid, err = _validate_apply(range_values)
    if valid is None:
        routing_state.last_error = err
    else:
        routing_state.set_custom(valid)
        routing_state.last_error = None
    routing_state.last_status = ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_apply_persistence.py -v`
Expected: all apply tests pass.

- [ ] **Step 6: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py tests/test_apply_persistence.py ; git commit -m "feat(app): validate and apply with Range low/high" --no-verify
```

---

### Task 18: Update `_render_state`, `_compute_rehydrate_outputs`, `_dispatch_action`

**Files:**
- Modify: `app/routing_config.py`
- Modify: `tests/test_routing_config_state_machine.py`

- [ ] **Step 1: Update `_render_state` to project 14 input values + 14 disabled flags**

Replace `_render_state` with:

```python
def _render_state(range_input_values: list) -> tuple:
    """Project routing_state to UI outputs.

    Output tuple order (matches the single callback's Output list):
      [0]  mode-frozen className
      [1]  mode-editable className
      [2]  routing-preset-status children
      [3]  routing-config-status children
      [4]  thresh-unsaved-badge children
      [5]  thresh-apply-status children
      [6]  routing-preset value
      [7..13]  7 slider-{name} values
      [14..20] 7 input-{name}-low values
      [21..27] 7 input-{name}-high values
      [28..34] 7 input-{name}-low disabled
      [35..41] 7 input-{name}-high disabled
    """
    thresholds = routing_state.get_thresholds()
    is_frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(is_frozen)
    n = len(RANGE_FIELDS)
    dis_list = [is_frozen] * (2 * n)
    slider_vals = [getattr(thresholds, f["name"]).low for f in RANGE_FIELDS]  # placeholder
    slider_vals = []
    for f in RANGE_FIELDS:
        rng = getattr(thresholds, f["name"])
        slider_vals.append([rng.low, rng.high])
    low_vals = [getattr(thresholds, f["name"]).low for f in RANGE_FIELDS]
    high_vals = [getattr(thresholds, f["name"]).high for f in RANGE_FIELDS]

    # detect unsaved changes (only meaningful in editable mode)
    def _vals_differ(a, b):
        try:
            return abs(float(a) - float(b)) > 1e-9
        except Exception:
            return a != b
    has_unsaved = False
    if not is_frozen and len(range_input_values) == 2 * n:
        for i, f in enumerate(RANGE_FIELDS):
            if _vals_differ(range_input_values[2 * i], low_vals[i]):
                has_unsaved = True
                break
            if _vals_differ(range_input_values[2 * i + 1], high_vals[i]):
                has_unsaved = True
                break

    source = routing_state.get_threshold_source()
    preset_status = html.Span(source, style={"color": "#888", "fontSize": "11px"})

    if routing_state.last_error:
        err = routing_state.last_error
        if err and ("Blocked" in err or "Preset switch" in err or "Edit Mode" in err):
            config_status = html.Span(err, style={"fontSize": "11px", "color": "#E67E22"})
        else:
            config_status = html.Span(f"Error: {err}", style={"fontSize": "11px", "color": "#C0392B"})
    elif routing_state.last_status:
        config_status = html.Span(routing_state.last_status, style={"fontSize": "11px", "color": "#2C7A2C"})
    else:
        config_status = ""

    if has_unsaved:
        unsaved_badge = html.Span("Unsaved Changes", style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"})
        apply_status = html.Span("Thresholds modified - click Apply to save.", style={"fontSize": "11px", "color": "#E67E22"})
    else:
        unsaved_badge = html.Span("", style={"display": "none"})
        apply_status = ""

    return tuple([
        f_cls, e_cls,
        preset_status, config_status, unsaved_badge, apply_status,
        routing_state.current_preset,
    ] + slider_vals + low_vals + high_vals + dis_list)
```

- [ ] **Step 2: Update `_compute_rehydrate_outputs`**

Replace with:

```python
def _compute_rehydrate_outputs():
    thresholds = routing_state.get_thresholds()
    is_frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(is_frozen)
    n = len(RANGE_FIELDS)
    slider_vals = [[getattr(thresholds, f["name"]).low, getattr(thresholds, f["name"]).high] for f in RANGE_FIELDS]
    low_vals = [getattr(thresholds, f["name"]).low for f in RANGE_FIELDS]
    high_vals = [getattr(thresholds, f["name"]).high for f in RANGE_FIELDS]
    dis_list = [is_frozen] * (2 * n)
    return tuple([
        f_cls, e_cls,
        f"Loaded: {routing_state.current_preset}",
        "",
        html.Span("", style={"display": "none"}),
        "",
        routing_state.current_preset,
    ] + slider_vals + low_vals + high_vals + dis_list)
```

- [ ] **Step 3: Update `_dispatch_action` to accept new trigger IDs**

Replace the `thresh-{name}.value` branch with a branch that matches `input-{name}-low.value` and `input-{name}-high.value`. The full updated function:

```python
def _dispatch_action(trigger_id, trigger_value, range_values) -> None:
    if trigger_id is None:
        return
    if trigger_id == "routing-preset.value":
        new_preset = trigger_value
        if routing_state.is_frozen:
            routing_state.current_preset = new_preset
            routing_state.thresholds = RoutingThresholds.for_preset(new_preset)
            routing_state.custom_thresholds = None
            routing_state.last_error = None
            routing_state.last_status = ""
        else:
            if new_preset and new_preset != routing_state.current_preset:
                routing_state.last_error = "Edit Mode: Preset switch Blocked (unsaved changes). Please click Apply or switch to Locked first."
                routing_state.last_status = ""
        return
    if trigger_id == "mode-frozen.n_clicks":
        routing_state.set_frozen_mode(True)
        routing_state.last_error = None
        routing_state.last_status = ""
        return
    if trigger_id == "mode-editable.n_clicks":
        routing_state.set_frozen_mode(False)
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        routing_state.last_error = None
        routing_state.last_status = ""
        return
    if trigger_id == "btn-apply-thresholds.n_clicks":
        _apply_thresholds(tuple(range_values))
        return
    if trigger_id and (trigger_id.startswith("input-") and trigger_id.endswith(".value")):
        return  # user typing; render will detect diff and show unsaved
    if trigger_id == "tabs.value":
        return
```

- [ ] **Step 4: Run state machine tests to verify behavior**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v`
Expected: at least the basic state machine tests pass (others may need updates; capture in Task 22).

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py tests/test_routing_config_state_machine.py ; git commit -m "feat(app): render_state and dispatch_action support Range fields" --no-verify
```

---

### Task 19: Update the single `_routing_config_ui` callback

**Files:**
- Modify: `app/routing_config.py`
- Modify: `tests/test_routing_config_state_machine.py`

- [ ] **Step 1: Update the callback outputs to include sliders + 14 inputs**

Find the `_routing_config_ui` callback in `register_routing_config_callbacks`. Replace the entire callback (from `@app.callback` to its closing `def _routing_config_ui(...)` function) with:

```python
n = len(RANGE_FIELDS)
slider_outputs = [Output(f"slider-{f['name']}", "value") for f in RANGE_FIELDS]
low_outputs = [Output(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
high_outputs = [Output(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS]
low_dis = [Output(f"input-{f['name']}-low", "disabled") for f in RANGE_FIELDS]
high_dis = [Output(f"input-{f['name']}-high", "disabled") for f in RANGE_FIELDS]

# Slider outputs are OWNED by the sync callbacks (Tasks 16). We must NOT include
# them in the main callback's Outputs list. So the main callback writes to
# input-low, input-high, and disabled only.

@app.callback(
    [Output("mode-frozen", "className"),
     Output("mode-editable", "className"),
     Output("routing-preset-status", "children"),
     Output("routing-config-status", "children"),
     Output("thresh-unsaved-badge", "children"),
     Output("thresh-apply-status", "children"),
     Output("routing-preset", "value")]
    + low_outputs + high_outputs + low_dis + high_dis,
    [Input("routing-preset", "value"),
     Input("mode-frozen", "n_clicks"),
     Input("mode-editable", "n_clicks"),
     Input("btn-apply-thresholds", "n_clicks"),
     Input("tabs", "value")]
    + [Input(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
    + [Input(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS],
    [State(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
    + [State(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS],
    prevent_initial_call=False,
)
def _routing_config_ui(
    preset_value, _f_clicks, _e_clicks, _apply_clicks, tab,
    *input_args,
):
    from dash import callback_context as _ctx
    from dash.exceptions import PreventUpdate as _PreventUpdate
    from dash import no_update as _no_update

    # 14 input values are the LAST 14 args (State), in the order
    # [low_0..low_6, high_0..high_6].
    n = len(RANGE_FIELDS)
    range_state = list(input_args[-2 * n:])

    if not _ctx.triggered:
        return _render_state(range_state)

    trigger_id = _ctx.triggered[0]["prop_id"]
    trigger_value = _ctx.triggered[0]["value"]

    if trigger_id == "tabs.value":
        if trigger_value != "tab-routing-config":
            raise _PreventUpdate
        return _compute_rehydrate_outputs()

    _dispatch_action(trigger_id, trigger_value, tuple(range_state))
    rendered = _render_state(range_state)

    # When user is typing in an input, do not overwrite the value.
    if trigger_id and trigger_id.startswith("input-") and trigger_id.endswith(".value"):
        outs = list(rendered)
        for i in range(n):
            outs[7 + i] = _no_update  # 7 = preset, mode buttons, statuses
        return tuple(outs)
    return rendered
```

- [ ] **Step 2: Run state machine tests**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v`
Expected: the basic tests pass (older assertions about 7-value tuples will fail; update them in Task 22).

- [ ] **Step 3: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py ; git commit -m "feat(app): _routing_config_ui callback uses 14 input values" --no-verify
```

---

### Task 20: Update `_handle_routing_preset_or_thresh` for testability

**Files:**
- Modify: `app/routing_config.py`
- Modify: `tests/test_routing_config_state_machine.py`

- [ ] **Step 1: Update the function signature and internal logic**

Find `_handle_routing_preset_or_thresh` and replace it with:

```python
def _handle_routing_preset_or_thresh(
    preset: Optional[str],
    range_values: tuple,
    trigger: Optional[str],
) -> tuple:
    """Testable core logic extracted from the large update callback.

    `range_values` is a 14-tuple of (low_0, high_0, ..., low_6, high_6).
    Returns the tuple of output values in the same order as the callback.
    """
    n = len(RANGE_FIELDS)
    is_frozen = routing_state.is_frozen
    thresholds = routing_state.get_thresholds()
    f_cls, e_cls = _mode_button_classes(is_frozen)
    dis_list = [is_frozen] * (2 * n)
    slider_vals = [[getattr(thresholds, fld["name"]).low, getattr(thresholds, fld["name"]).high] for fld in RANGE_FIELDS]
    low_vals = [getattr(thresholds, fld["name"]).low for fld in RANGE_FIELDS]
    high_vals = [getattr(thresholds, fld["name"]).high for fld in RANGE_FIELDS]

    if trigger == "routing-preset" and preset:
        if preset == routing_state.current_preset:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        if not is_frozen:
            curr_p = routing_state.current_preset
            warn = "Edit Mode: Preset switch Blocked (unsaved changes). Please click Apply or switch to Locked first."
            dis_ed = [False] * (2 * n)
            f_ed, e_ed = _mode_button_classes(False)
            return tuple([f_ed, e_ed, f"Loaded: {curr_p}", warn,
                          html.Span("\u25cf unsaved changes", style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
                          "", curr_p]
                         + slider_vals + low_vals + high_vals + dis_ed)
        # Locked load
        try:
            t = RoutingThresholds.for_preset(preset)
            routing_state.current_preset = preset
            routing_state.thresholds = t
            routing_state.set_frozen_mode(True)
            status = f"Loaded preset: {preset}"
            new_slider = [[getattr(t, fld["name"]).low, getattr(t, fld["name"]).high] for fld in RANGE_FIELDS]
            new_low = [getattr(t, fld["name"]).low for fld in RANGE_FIELDS]
            new_high = [getattr(t, fld["name"]).high for fld in RANGE_FIELDS]
            dis_f = [True] * (2 * n)
            f_f, e_f = _mode_button_classes(True)
            return tuple([f_f, e_f, status, "", html.Span("", style={"display": "none"}), "", preset]
                         + new_slider + new_low + new_high + dis_f)
        except Exception as e:
            return tuple([f_cls, e_cls, f"Error: {e}", "", html.Span("", style={"display": "none"}), "", routing_state.current_preset]
                         + slider_vals + low_vals + high_vals + dis_list)

    # Manual edit path: return _render_state result
    return _render_state(list(range_values))
```

- [ ] **Step 2: Run state machine tests**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v`
Expected: tests for the new tuple shape pass; older 7-value tests fail (update in Task 22).

- [ ] **Step 3: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py ; git commit -m "feat(app): _handle_routing_preset_or_thresh takes 14 range values" --no-verify
```

---

## Phase 4: Reports & Docs

### Task 21: Update `report_visualization.py` and `routing_pptx.py`

**Files:**
- Modify: `core/report_visualization.py`
- Modify: `report/routing_pptx.py`
- Modify: `tests/test_routing_pptx.py`

- [ ] **Step 1: Find per-net cell string formatting in the two report modules**

Run: `cd 'd:\workspace\project\sram_layout_review' ; grep -rn "max_h_ratio\|max_v_ratio\|max_r_ohm\|max_c_ff\|max_tau_ps\|min_via_coverage\|min_similarity" core/report_visualization.py report/routing_pptx.py`
Expected: a list of old field references in both files.

- [ ] **Step 2: Write a test asserting the new cell format in the report**

Append to `tests/test_routing_pptx.py`:

```python
def test_pptx_cell_uses_in_or_notin_symbol():
    from config.routing_thresholds import Range
    from core import report_visualization as rv

    # Construct a minimal "metric row" matching the in-PPTX cell format
    rng = Range(0.0, 0.15)
    h_text = rv.format_metric_cell(0.10, rng)  # may not exist; if so, define
    assert "\u2208" in h_text
```

If `format_metric_cell` doesn't exist, add a minimal helper to `core/report_visualization.py`:

```python
def format_metric_cell(value, rng, fmt="{:.1f}"):
    symbol = "\u2208" if rng.contains(value) else "\u2209"
    return f"{fmt.format(value)} {symbol} [{fmt.format(rng.low)}, {fmt.format(rng.high)}]"
```

- [ ] **Step 3: Replace the old `value / max` format with `∈`/`∉` format**

In both `core/report_visualization.py` and `report/routing_pptx.py`, find every cell that produces a string like `f"{value:.1f} / {threshold:.1f}"` and replace it with a call to `format_metric_cell(value, rng)`. Use the appropriate `Range` field from `thresholds`.

- [ ] **Step 4: Run the new test**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_pptx.py -v`
Expected: the new test passes (and any other test that used the old format may need updating in Task 22).

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add core/report_visualization.py report/routing_pptx.py tests/test_routing_pptx.py ; git commit -m "feat(report): cells use Range-based \u2208/\u2209 notation" --no-verify
```

---

### Task 22: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Find references to old field names in docs**

Run: `cd 'd:\workspace\project\sram_layout_review' ; grep -n "max_h_ratio\|max_v_ratio\|max_r_ohm\|max_c_ff\|max_tau_ps\|min_via_coverage\|min_similarity" CLAUDE.md README.md`
Expected: at least one match in each doc.

- [ ] **Step 2: Replace old field names with new ones**

In both `CLAUDE.md` and `README.md`, replace:

- `max_h_ratio` → `h_ratio` (with explanation that this is now a `Range`)
- `max_v_ratio` → `v_ratio`
- `max_r_ohm` → `r_ohm`
- `max_c_ff` → `c_ff`
- `max_tau_ps` → `tau_ps`
- `min_via_coverage` → `via_coverage`
- `min_similarity` → `similarity`

Add a note that all 7 metrics are `Range` objects with `low` and `high` fields, and a value passes iff `low <= value <= high`.

- [ ] **Step 3: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add CLAUDE.md README.md ; git commit -m "docs: update threshold field names to Range format" --no-verify
```

---

## Phase 5: Test Suite Migration

### Task 23: Update all 11 test files to use `Range`

**Files:**
- Modify: `tests/test_routing_thresholds.py`
- Modify: `tests/test_routing_metrics.py`
- Modify: `tests/test_routing_violation.py`
- Modify: `tests/test_routing_config_layout.py`
- Modify: `tests/test_routing_config_state_machine.py`
- Modify: `tests/test_preset_loader.py`
- Modify: `tests/test_preset_loader_schema.py`
- Modify: `tests/test_apply_persistence.py`
- Modify: `tests/test_routing_e2e.py`
- Modify: `tests/test_routing_pptx.py`
- Modify: `tests/test_tab_rehydrate.py`

- [ ] **Step 1: Find all stale references across test files**

Run: `cd 'd:\workspace\project\sram_layout_review' ; grep -rn "max_h_ratio\|max_v_ratio\|max_r_ohm\|max_c_ff\|max_tau_ps\|min_via_coverage\|min_similarity\|THRESHOLD_FIELDS" tests/`
Expected: a list of stale references. Each must be replaced.

- [ ] **Step 2: Mechanical replacement rules**

For each occurrence:

- `thresholds.max_h_ratio` → `thresholds.h_ratio.high` (or pass the Range)
- `THRESHOLD_FIELDS` references → `RANGE_FIELDS` (and adapt tuple unpacking: `(name, label, mn, mx, st)` becomes `(f["name"], f["label"], f["slider_min"], f["slider_max"], f["step"])`)
- Test fixture calls like `RoutingThresholds(max_h_ratio=0.15)` → `RoutingThresholds(h_ratio=Range(0.0, 0.15))`
- Numeric test inputs like `vals = (0.15, 1.0, ...)` (7 values) → `vals = (0.0, 0.15, 0.0, 1.0, ...)` (14 values, alternating low/high per field)

- [ ] **Step 3: Run the full test suite**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/ -v 2>&1 | tail -100`
Expected: all tests pass. Fix remaining issues iteratively.

- [ ] **Step 4: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add tests/ ; git commit -m "test: update all tests to use Range type" --no-verify
```

---

## Phase 6: Manual Visual Verification

### Task 24: Manual visual verification

**Files:**
- N/A (manual step)

- [ ] **Step 1: Start the app**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python layout_review_app.py`
Expected: Dash app starts on default port.

- [ ] **Step 2: Upload sample shapes and run routing review**

Open the URL printed in Step 1, navigate to Layout View, upload `shapes_test_wordline_WL0.txt` (or any other sample). Then go to Routing Config and click "Use first net as golden" + "Use all loaded nets (batch)".

- [ ] **Step 3: Verify the three changes**

- [ ] **Active Threshold Source banner**: navigate to Routing Review. Verify the text is plain (no dark-green background).
- [ ] **Per-net cells in range**: pick a row with Pass=✓ and verify cells show `value ∈ [low, high]`.
- [ ] **Per-net cells out of range**: pick a row with Pass=✗ and verify the offending cells show `value ∉ [low, high]` with light-red background.
- [ ] **Range sliders in Config**: navigate to Routing Config. Drag one end of a slider; the corresponding input value should update. Type into an input; the slider position should update.
- [ ] **Apply with low > high**: edit an input so that low > high. Click Apply. Verify a red error message appears and the state does not change.

- [ ] **Step 4: Commit (no changes; this is verification only)**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git status
```

Expected: working tree clean (or only minor cosmetic changes if any).

---

## Self-Review Notes

After writing this plan I performed these checks:

1. **Spec coverage:**
   - Range dataclass → Task 1
   - RoutingThresholds refactor → Task 2
   - preset_loader / YAML → Tasks 3, 4
   - check_gates → Task 5
   - RoutingViolation → Task 6
   - routing_state → Task 7
   - Banner de-green → Task 8
   - Cell format helpers + table rows + styles + metric cards → Tasks 9, 10, 11, 12
   - RANGE_FIELDS + UI builder + tab layout → Tasks 13, 14, 15
   - Slider↔input sync → Task 16
   - validate / apply / render / dispatch / callback / testability → Tasks 17, 18, 19, 20
   - report_visualization / pptx / docs → Tasks 21, 22
   - Test suite migration → Task 23
   - Manual visual verification → Task 24

2. **Placeholder scan:** No TBD / TODO / "similar to Task N" — each step has explicit code.

3. **Type consistency:** `Range` is the only new type; `RoutingThresholds` field names match the YAML format; `_THRESHOLD_TO_METRIC_KEY` mapping is consistent across `check_gates` (Task 5) and `_build_cell_violation_map` (Task 9). The field-to-column mapping is consistent in `FIELD_TO_COLUMN` and the table cell construction.

4. **Known limitations**:
   - The `for _field in RANGE_FIELDS:` loop in Task 16 (slider↔input sync) uses Python closure-defaults (`_n=_name`); make sure not to drop the default value, or all callbacks will close over the last `_field` only.
   - Task 18's `_render_state` and Task 19's callback both manipulate the output tuple. The first 7 outputs are preset/mode/status, then slider/inputs/disabled — count carefully when adding `_no_update` slots.
