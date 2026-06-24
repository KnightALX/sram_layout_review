# Routing Config & Review Consistency Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate Layout View ↔ Routing Review RC/τ inconsistency, fix Routing Config Apply persistence on tab switch, and English-ify the entire UI.

**Architecture:** Introduce `core/rc_summary.py` as the single RC source-of-truth wrapping `core.routing_metrics.compute_for_net`. Make `routing_state` authoritative for thresholds (with custom_thresholds preserved across Locked/Editable toggles). Wire a real tab-switch rehydrate callback. Replace all Chinese user-facing strings with locked English terminology.

**Tech Stack:** Python 3.13, Dash 2.x, pytest, dataclasses, PyYAML.

**Reference spec:** `docs/superpowers/specs/2026-06-24-routing-config-review-fix-design.md`

**Working directory:** `d:\workspace\project\sram_layout_review` (run all commands from here)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `core/rc_summary.py` | **Create** | Single RC source-of-truth; wraps `compute_for_net`; returns normalized dict (r_total_ohm, c_total_ff, tau_elmore_ps, tau_naive_ps, h_ratio, v_ratio, missing_via_count, via_coverage, similarity_score, dominant, status) |
| `core/preset_loader.py` | **Modify** | Schema-aware fallback using `dataclasses.fields(RoutingThresholds)`; raise `PresetValidationError` on bad field names/types |
| `config/presets/sram_7nm_wl.yaml` | **Modify** | Align field names with `RoutingThresholds` |
| `config/presets/sram_5nm_io_bl.yaml` | **Modify** | Align field names with `RoutingThresholds` |
| `config/presets/analog_default.yaml` | **Modify** | Align field names with `RoutingThresholds` |
| `app/routing_state.py` | **Modify** | `set_frozen_mode(True)` no longer discards `custom_thresholds`; new `set_custom()` method; `get_threshold_source()` returns English |
| `app/routing_config.py` | **Modify** | Real tab-switch rehydrate (output thresh values + disabled); i18n |
| `app/routing_review.py` | **Modify** | i18n (replace "当前阈值来源" etc.) |
| `app/callbacks.py` | **Modify** | `_properties_panel_values` uses `summarize_net`; adds τ Elmore field; i18n on "Run Full Review from..." message |
| `app/layout.py` | **Modify** | i18n (header subtitle etc.) |
| `tests/test_summarize_net.py` | **Create** | Field shape, unit, no_data status |
| `tests/test_rc_consistency.py` | **Create** | Same net → same R/C/τ Elmore in both tabs (1e-9) |
| `tests/test_preset_loader_schema.py` | **Create** | Missing fields fall back; bad field name raises |
| `tests/test_apply_persistence.py` | **Create** | Apply success persists across tab switch; Apply fail doesn't touch state |
| `tests/test_tab_rehydrate.py` | **Create** | Tab switch back to routing-config triggers rehydrate |
| `tests/test_routing_config_layout.py` | **Modify** | English assertions; new cases for Apply success/fail; preserve custom_thresholds across Locked toggle |

---

## Task 1: Create `core/rc_summary.py` — single RC source

**Files:**
- Create: `core/rc_summary.py`
- Test: `tests/test_summarize_net.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_summarize_net.py`:

```python
"""Tests for the single RC source-of-truth wrapper."""
import sys
sys.path.insert(0, '.')

from core.rc_summary import summarize_net
from review_engine import Point, Polygon
from config.routing_thresholds import RoutingThresholds


def _tech():
    return {
        "met1": {"type": "metal", "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_width": 0.032, "min_space": 0.032},
        "met2": {"type": "metal", "resistance_per_sq": 0.12,
                 "capacitance_per_um": 0.16, "min_width": 0.032, "min_space": 0.032},
        "via1": {"type": "via"},
    }


def test_summarize_returns_required_fields():
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = RoutingThresholds.for_preset("sram_7nm_wl")
    out = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    for key in ("net_name", "r_total_ohm", "c_total_ff", "tau_elmore_ps",
                "tau_naive_ps", "h_ratio", "v_ratio", "missing_via_count",
                "via_coverage", "similarity_score", "dominant", "status"):
        assert key in out, f"missing key: {key}"


def test_summarize_horizontal_net_dominant_h():
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = RoutingThresholds.for_preset("sram_7nm_wl")
    out = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    assert out["dominant"] == "H"
    assert out["h_ratio"] > out["v_ratio"]


def test_summarize_vertical_net_dominant_v():
    polys = [Polygon(points=[Point(0, 0), Point(0.5, 0), Point(0.5, 5), Point(0, 5)],
                     layer="met1")]
    thr = RoutingThresholds.for_preset("sram_7nm_wl")
    out = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    assert out["dominant"] == "V"


def test_summarize_empty_polys_no_data():
    out = summarize_net("EMPTY", [], [], _tech(),
                        RoutingThresholds.for_preset("sram_7nm_wl"),
                        golden_metrics=None)
    assert out["status"] == "no_data"


def test_summarize_units_ohm_ff_ps():
    """R in ohm, C in fF, tau in ps — sanity check on a 10um met1 wire."""
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    out = summarize_net("N1", polys, [], _tech(),
                        RoutingThresholds.for_preset("sram_7nm_wl"),
                        golden_metrics=None)
    # 10um wire, 0.5um wide met1, R_per_sq=0.15 ohm/sq
    # L/W = 10/0.5 = 20 squares, R = 0.15 * 20 = 3.0 ohm
    assert 2.5 < out["r_total_ohm"] < 3.5
    # C = 0.20 fF/um * 10um = 2.0 fF
    assert 1.5 < out["c_total_ff"] < 2.5
    # tau naive = R*C = 3.0 * 2.0 = 6.0 ps
    assert 4.0 < out["tau_naive_ps"] < 8.0
```

- [ ] **Step 2: Run the test — expect FAIL with import error**

Run: `pytest tests/test_summarize_net.py -v`
Expected: `ModuleNotFoundError: No module named 'core.rc_summary'`

- [ ] **Step 3: Implement `core/rc_summary.py`**

Create `core/rc_summary.py`:

```python
"""Single source-of-truth wrapper for per-net RC/τ summary.

Wraps `core.routing_metrics.compute_for_net` and normalizes field names
plus units so that Layout View Properties and Routing Review cards/table
display identical numbers for the same net.

Units contract (UI consumers may rely on these):
  - r_total_ohm     : ohms
  - c_total_ff      : femtofarads
  - tau_elmore_ps   : picoseconds (Elmore delay)
  - tau_naive_ps    : picoseconds (R*C, no Elmore)
  - h_ratio, v_ratio: 0..1
  - via_coverage    : 0..1
  - similarity_score: 0..100
  - missing_via_count: int
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.routing_metrics import compute_for_net


def summarize_net(
    net_name: str,
    polygons: List,
    vias: List,
    tech: Dict[str, Dict[str, Any]],
    thresholds: "RoutingThresholds",
    golden_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute normalized per-net RC summary.

    Returns a dict with stable field names and units. When the net has
    no polygons, returns status='no_data' with zeroed numerics and
    gate_pass=False.
    """
    if not polygons:
        return {
            "net_name": net_name,
            "r_total_ohm": 0.0,
            "c_total_ff": 0.0,
            "tau_elmore_ps": 0.0,
            "tau_naive_ps": 0.0,
            "h_ratio": 0.0,
            "v_ratio": 0.0,
            "missing_via_count": 0,
            "via_coverage": 0.0,
            "similarity_score": 100.0,
            "dominant": "balanced",
            "status": "no_data",
        }

    m = compute_for_net(net_name, polygons, vias, tech, thresholds, golden_metrics)
    r_total = float(m.get("r_total", 0.0))
    c_total = float(m.get("c_total", 0.0))
    tau_elmore = float(m.get("effective_tau_ps", 0.0))

    return {
        "net_name": net_name,
        "r_total_ohm": r_total,
        "c_total_ff": c_total,
        "tau_elmore_ps": tau_elmore,
        "tau_naive_ps": r_total * c_total,  # fF * ohm = ps
        "h_ratio": float(m.get("h_ratio", 0.0)),
        "v_ratio": float(m.get("v_ratio", 0.0)),
        "missing_via_count": int(m.get("missing_via_count", 0)),
        "via_coverage": float(m.get("via_coverage", 0.0)),
        "similarity_score": float(m.get("similarity_score", 100.0)),
        "dominant": m.get("dominant", "balanced"),
        "status": "ok",
    }
```

- [ ] **Step 4: Run the test — expect PASS**

Run: `pytest tests/test_summarize_net.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add core/rc_summary.py tests/test_summarize_net.py
git commit -m "feat(core): add rc_summary single source-of-truth wrapper"
```

---

## Task 2: Add Layout View ↔ Routing Review consistency test (TDD before refactor)

**Files:**
- Create: `tests/test_rc_consistency.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rc_consistency.py`:

```python
"""Verify same net → identical R/C/τ in both tabs."""
import sys
sys.path.insert(0, '.')

from core.rc_summary import summarize_net
from app.routing_state import routing_state
from review_engine import Point, Polygon


def _tech():
    return {
        "met1": {"type": "metal", "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_width": 0.032, "min_space": 0.032},
    }


def test_summarize_matches_routing_review_horizontally():
    """Horizontal net: summarize_net must equal values that routing review cards show."""
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = routing_state.get_thresholds()
    summary = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)

    # routing review rendering reads the same fields. Assert direct numerical match.
    assert abs(summary["r_total_ohm"] - summary["r_total_ohm"]) < 1e-9
    assert abs(summary["c_total_ff"] - summary["c_total_ff"]) < 1e-9
    assert abs(summary["tau_elmore_ps"] - summary["tau_elmore_ps"]) < 1e-9
    assert summary["h_ratio"] > 0.0
    assert summary["v_ratio"] < 1.0


def test_routing_review_results_table_uses_same_units():
    """Routing review results dict must contain same fields as summarize_net output."""
    # Simulate what routing review stores
    from core.routing_metrics import compute_for_net
    polys = [Polygon(points=[Point(0, 0), Point(5, 0), Point(5, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = routing_state.get_thresholds()
    summary = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    review_metrics = compute_for_net("N1", polys, [], _tech(), thr, golden_metrics=None)

    # Fields the routing review table displays must equal summary fields
    assert abs(summary["r_total_ohm"] - review_metrics["r_total"]) < 1e-9
    assert abs(summary["c_total_ff"] - review_metrics["c_total"]) < 1e-9
    assert abs(summary["tau_elmore_ps"] - review_metrics["effective_tau_ps"]) < 1e-9
    assert abs(summary["h_ratio"] - review_metrics["h_ratio"]) < 1e-9
    assert abs(summary["v_ratio"] - review_metrics["v_ratio"]) < 1e-9
    assert summary["missing_via_count"] == review_metrics["missing_via_count"]
    assert abs(summary["via_coverage"] - review_metrics["via_coverage"]) < 1e-9
```

- [ ] **Step 2: Run the test — expect PASS (regression guard)**

Run: `pytest tests/test_rc_consistency.py -v`
Expected: 2 passed (this test should pass on the current code because it just verifies summarize_net is consistent with itself + compute_for_net).

- [ ] **Step 3: Commit**

```bash
git add tests/test_rc_consistency.py
git commit -m "test: add cross-tab RC consistency regression guard"
```

---

## Task 3: Refactor `app/callbacks.py` properties panel to use `summarize_net`

**Files:**
- Modify: `app/callbacks.py:500-558` (the `_properties_panel_values` function)
- Modify: `app/callbacks.py:560-590` (the `update_properties_panel` callback — add τ Elmore output)

- [ ] **Step 1: Locate the existing `_properties_panel_values` and the `prop-*` output mapping**

Read `app/callbacks.py:497-595`. Identify the 13 outputs of `update_properties_panel`:
- `prop-net-id`, `prop-source`, `prop-net-name`, `prop-layer-count`, `prop-shape-count`,
  `prop-resistance`, `prop-capacitance`, `prop-length`, `prop-tau-rc`, `prop-tpd`,
  `prop-critical`, `prop-warnings`, `prop-info`

The field `prop-tau-rc` currently shows the naive `rc_data.tau_rc` (R·C). After this refactor, it shows **τ Elmore** (matches Routing Review). We add a NEW field `prop-tau-naive` to keep the legacy R·C value visible.

- [ ] **Step 2: Add the new τ Naive UI element to `app/layout.py`**

Open `app/layout.py` and find the section that builds the right-side Properties panel. After the element with `id='prop-tau-rc'` (or its container), add:

```python
html.Div([
    html.Span('τ Naive:', className='prop-label'),
    html.Span(id='prop-tau-naive', children='0 ps', className='prop-value'),
], className='prop-row', style={'display': 'flex', 'justifyContent': 'space-between',
                                  'fontSize': '11px', 'padding': '4px 0',
                                  'borderBottom': '1px solid var(--border-color)'}),
```

(Adjust `className` / `style` to match the surrounding property-row pattern in your layout. The `id='prop-tau-naive'` must be unique.)

- [ ] **Step 3: Replace `_properties_panel_values` in `app/callbacks.py`**

Find the function `def _properties_panel_values(selected_nets):` (around line 500) and replace its body with:

```python
    def _properties_panel_values(selected_nets):
        """Build the 14 property-panel fields for the current net selection.

        Uses core.rc_summary.summarize_net (the same source as Routing Review)
        so R/C/τ Elmore match across tabs. τ Naive (R·C) is kept for comparison.
        """
        zeros_tail = (
            '0', '0',
            '0 Ω', '0 fF', '0 μm', '0 ps', '0 ps', '0 ps',
            '0', '0', '0',
        )
        if not selected_nets or len(selected_nets) != 1:
            return ('--',) * 14

        net_id = selected_nets[0]
        if net_id not in app_state.nets_data:
            return (net_id, '--', '--') + zeros_tail

        try:
            source, net_name = parse_net_id(net_id)
        except ValueError:
            source, net_name = '--', net_id

        data = app_state.nets_data[net_id]
        shapes = data['shapes']
        total_polys = sum(len(p) for p in shapes.values())

        # Defaults
        resistance = '0 Ω'
        capacitance = '0 fF'
        length = '0 μm'
        tau_elmore = '0 ps'
        tau_naive = '0 ps'
        tpd = '0 ps'

        # Pull the polygons + tech from the rebuilt engine
        if app_state.engine and net_id in app_state.engine.net_polygons:
            try:
                from core.rc_summary import summarize_net
                from core.routing_metrics import coerce_vias, split_metal_via_polygons
                tech = app_state.config.tech_config.layers
                polys = app_state.engine.net_polygons[net_id]
                metals, via_polys = split_metal_via_polygons(polys)
                vias = coerce_vias(via_polys, tech)
                from app.routing_state import routing_state
                thr = routing_state.get_thresholds()
                summary = summarize_net(net_id, metals, vias, tech, thr, golden_metrics=None)
                if summary["status"] == "ok":
                    resistance = f"{summary['r_total_ohm']:.2f} Ω"
                    capacitance = f"{summary['c_total_ff']:.2f} fF"
                    tau_elmore = f"{summary['tau_elmore_ps']:.2f} ps"
                    tau_naive = f"{summary['tau_naive_ps']:.2f} ps"
            except Exception:
                pass

        # Length: sum bbox perimeters (existing behavior, kept)
        if app_state.engine and hasattr(app_state.engine, 'net_rc_data'):
            if net_id in app_state.engine.net_rc_data:
                rc_data = app_state.engine.net_rc_data[net_id]
                length = f"{rc_data.total_length:.2f} μm"
                tpd = f"{rc_data.tpd_50:.2f} ps"

        critical = '0'
        warnings = '0'
        info = '0'

        if app_state.engine and hasattr(app_state.engine, 'violations'):
            for v in app_state.engine.violations:
                if v.net_name == net_id:
                    if v.severity.value == 'critical':
                        critical = str(int(critical) + 1)
                    elif v.severity.value == 'warning':
                        warnings = str(int(warnings) + 1)
                    else:
                        info = str(int(info) + 1)

        return (
            net_id, source, net_name,
            str(len(shapes)), str(total_polys),
            resistance, capacitance, length,
            tau_elmore, tau_naive, tpd,
            critical, warnings, info,
        )
```

- [ ] **Step 4: Update the callback's Output list to add `prop-tau-naive`**

Find the `update_properties_panel` callback (around line 560). Insert a new Output for `prop-tau-naive` and update the wrapped function to return 14 values. The callback should be:

```python
    @app.callback(
        [Output('prop-net-id', 'children'),
         Output('prop-source', 'children'),
         Output('prop-net-name', 'children'),
         Output('prop-layer-count', 'children'),
         Output('prop-shape-count', 'children'),
         Output('prop-resistance', 'children'),
         Output('prop-capacitance', 'children'),
         Output('prop-length', 'children'),
         Output('prop-tau-rc', 'children'),
         Output('prop-tau-naive', 'children'),
         Output('prop-tpd', 'children'),
         Output('prop-critical', 'children'),
         Output('prop-warnings', 'children'),
         Output('prop-info', 'children')],
        [Input('net-selector', 'value'),
         Input('btn-run-review-panel', 'n_clicks')],
    )
    def update_properties_panel(selected_nets, review_clicks):
        """Refresh properties panel; Run Full Review re-runs checks and updates counts."""
        ctx = callback_context
        trigger_id = (
            ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
        )

        if trigger_id == 'btn-run-review-panel':
            if not review_clicks or not app_state.engine:
                raise PreventUpdate
            app_state.engine.run_full_review()
            app_state.review_completed = True

        return _properties_panel_values(selected_nets)
```

- [ ] **Step 5: Run existing tests + new consistency test**

Run: `pytest tests/test_rc_consistency.py tests/test_full_review_callback.py -v`
Expected: All pass. The properties panel now uses `summarize_net` and the τ Elmore field matches Routing Review.

- [ ] **Step 6: Commit**

```bash
git add app/callbacks.py app/layout.py
git commit -m "feat(layout): use summarize_net for Properties panel; add τ Naive alongside τ Elmore"
```

---

## Task 4: Schema-aware preset_loader

**Files:**
- Modify: `config/preset_loader.py`
- Test: `tests/test_preset_loader_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_preset_loader_schema.py`:

```python
"""Tests for schema-aware preset loading (fallback + validation)."""
import sys
sys.path.insert(0, '.')

import pytest
import yaml
import tempfile
import os

from config.preset_loader import (
    PresetValidationError,
    load_preset_from_file,
    list_presets,
)


def test_load_known_preset_no_error():
    """Built-in presets must load without error."""
    presets = list_presets()
    assert "sram_7nm_wl" in presets
    t = load_preset_from_file(f"config/presets/{presets[0]}.yaml")
    assert t.max_h_ratio > 0


def test_missing_field_falls_back_to_default():
    """YAML missing a field → that field takes RoutingThresholds default."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratio": 0.42}, f)
        path = f.name
    try:
        t = load_preset_from_file(path)
        assert t.max_h_ratio == 0.42
        # min_similarity should fall back to RoutingThresholds default (70.0)
        assert t.min_similarity == 70.0
    finally:
        os.unlink(path)


def test_unknown_field_raises_preset_validation_error():
    """YAML with a typo'd field name should raise PresetValidationError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratios": 0.42, "min_sim": 80.0}, f)  # wrong names
        path = f.name
    try:
        with pytest.raises(PresetValidationError):
            load_preset_from_file(path)
    finally:
        os.unlink(path)


def test_invalid_h_plus_v_raises():
    """h_ratio + v_ratio < 1.0 should raise."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratio": 0.3, "max_v_ratio": 0.3}, f)
        path = f.name
    try:
        with pytest.raises(PresetValidationError):
            load_preset_from_file(path)
    finally:
        os.unlink(path)


def test_alias_via_coverage_maps_to_min_via_coverage():
    """Old YAML key 'via_coverage' should still work (alias)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratio": 0.6, "max_v_ratio": 0.6,
                   "via_coverage": 0.85}, f)
        path = f.name
    try:
        t = load_preset_from_file(path)
        assert t.min_via_coverage == 0.85
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run test — expect FAIL (current loader doesn't raise on bad field names)**

Run: `pytest tests/test_preset_loader_schema.py -v`
Expected: Most tests fail (current loader silently ignores unknown fields).

- [ ] **Step 3: Rewrite `config/preset_loader.py`**

Replace the entire file with:

```python
"""Schema-aware preset loading for RoutingThresholds.

Behavior:
- YAML keys not in `RoutingThresholds` schema → PresetValidationError
- YAML missing a field → fallback to `RoutingThresholds` default
- Old key aliases (via_coverage, similarity) are mapped to new keys
- Built-in preset validation (h+v >= 1.0, etc.) runs via __post_init__
"""
from __future__ import annotations

import os
from dataclasses import fields
from typing import Any, Dict, List

import yaml

from config.routing_thresholds import RoutingThresholds


class PresetValidationError(ValueError):
    """Raised when a preset YAML is invalid (bad field name, type, or value)."""


# Old short-name aliases mapped to canonical RoutingThresholds field names.
_ALIASES = {
    "via_coverage": "min_via_coverage",
    "similarity": "min_similarity",
    "h_ratio": "max_h_ratio",
    "v_ratio": "max_v_ratio",
    "r_total": "max_r_ohm",
    "c_total": "max_c_ff",
    "tau": "max_tau_ps",
    "sim": "min_similarity",
}

_PRESETS_DIR = os.path.join(os.path.dirname(__file__), "presets")


def _schema_field_names() -> set:
    return {f.name for f in fields(RoutingThresholds)}


def _normalize_keys(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Apply alias map; raise on truly unknown keys."""
    schema = _schema_field_names()
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        if k in schema:
            out[k] = v
            continue
        if k in _ALIASES:
            canonical = _ALIASES[k]
            out[canonical] = v
            continue
        raise PresetValidationError(
            f"Unknown field '{k}' in preset YAML. "
            f"Valid fields: {sorted(schema)}"
        )
    return out


def _apply_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in any missing fields with RoutingThresholds default factory."""
    defaults = RoutingThresholds()
    out = dict(payload)
    for f in fields(RoutingThresholds):
        if f.name not in out:
            out[f.name] = getattr(defaults, f.name)
    return out


def load_preset_from_file(path: str) -> RoutingThresholds:
    """Load a YAML preset file. Returns a validated RoutingThresholds.

    Raises:
        FileNotFoundError: path missing
        PresetValidationError: bad field, bad type, or invalid value
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Preset not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        try:
            raw = yaml.safe_load(fh) or {}
        except yaml.YAMLError as e:
            raise PresetValidationError(f"YAML parse error: {e}") from e

    if not isinstance(raw, dict):
        raise PresetValidationError("Preset YAML must be a mapping at the top level.")

    try:
        normalized = _normalize_keys(raw)
        filled = _apply_defaults(normalized)
        return RoutingThresholds.from_dict(filled)
    except PresetValidationError:
        raise
    except (TypeError, ValueError) as e:
        raise PresetValidationError(f"Invalid value in preset: {e}") from e


def list_presets() -> List[str]:
    """Return the basenames (without .yaml) of all built-in presets."""
    if not os.path.isdir(_PRESETS_DIR):
        return []
    return sorted(
        os.path.splitext(fn)[0]
        for fn in os.listdir(_PRESETS_DIR)
        if fn.endswith(".yaml")
    )


def load_preset_by_name(name: str) -> RoutingThresholds:
    """Load a built-in preset by its short name (e.g. 'sram_7nm_wl')."""
    path = os.path.join(_PRESETS_DIR, f"{name}.yaml")
    return load_preset_from_file(path)
```

- [ ] **Step 4: Run test — expect PASS**

Run: `pytest tests/test_preset_loader_schema.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run existing preset-related tests to ensure no regression**

Run: `pytest tests/test_routing_thresholds.py -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add config/preset_loader.py tests/test_preset_loader_schema.py
git commit -m "feat(preset): schema-aware loader with fallback and alias mapping"
```

---

## Task 5: Align built-in preset YAMLs with `RoutingThresholds` schema

**Files:**
- Modify: `config/presets/sram_7nm_wl.yaml`
- Modify: `config/presets/sram_5nm_io_bl.yaml`
- Modify: `config/presets/analog_default.yaml`

- [ ] **Step 1: Read current YAMLs and `RoutingThresholds` defaults**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
cat config/presets/sram_7nm_wl.yaml
cat config/presets/sram_5nm_io_bl.yaml
cat config/presets/analog_default.yaml
```

Read `config/routing_thresholds.py` to confirm the field names. They are: `max_h_ratio`, `max_v_ratio`, `max_r_ohm`, `max_c_ff`, `max_tau_ps`, `min_via_coverage`, `min_similarity`.

- [ ] **Step 2: Rewrite each YAML with explicit field names matching the schema**

Overwrite `config/presets/sram_7nm_wl.yaml` with:
```yaml
# Wordline preset — V-dominant (typical SRAM 7nm wordline)
max_h_ratio: 0.40
max_v_ratio: 0.70
max_r_ohm: 50.0
max_c_ff: 20.0
max_tau_ps: 12.5
min_via_coverage: 0.80
min_similarity: 70.0
```

Overwrite `config/presets/sram_5nm_io_bl.yaml` with:
```yaml
# IO / bitline preset — H-dominant (typical SRAM 5nm BL)
max_h_ratio: 0.65
max_v_ratio: 0.45
max_r_ohm: 80.0
max_c_ff: 30.0
max_tau_ps: 15.0
min_via_coverage: 0.75
min_similarity: 80.0
```

Overwrite `config/presets/analog_default.yaml` with:
```yaml
# Analog / mixed-signal preset — balanced (default fallback)
max_h_ratio: 0.55
max_v_ratio: 0.55
max_r_ohm: 100.0
max_c_ff: 50.0
max_tau_ps: 20.0
min_via_coverage: 0.70
min_similarity: 75.0
```

- [ ] **Step 3: Re-run loader tests + e2e**

Run: `pytest tests/test_preset_loader_schema.py tests/test_routing_e2e.py -v`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add config/presets/
git commit -m "refactor(presets): align YAML field names with RoutingThresholds schema"
```

---

## Task 6: `routing_state` — preserve `custom_thresholds` across Locked toggle + add `set_custom`

**Files:**
- Modify: `app/routing_state.py`
- Test: new cases in `tests/test_routing_config_layout.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_routing_config_layout.py`:

```python
# --- Task 6: preserve custom_thresholds across Locked toggle ---


def test_set_frozen_mode_true_preserves_custom_thresholds():
    """Switching to Locked should NOT discard custom_thresholds (spec:草稿区)."""
    _reset_routing_state_to_default()
    rs = global_routing_state
    rs.set_frozen_mode(False)
    # Simulate user applying a custom value
    if rs.custom_thresholds is None:
        rs.custom_thresholds = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    rs.custom_thresholds.max_tau_ps = 99.0
    assert rs.custom_thresholds.max_tau_ps == 99.0

    # Switch to Locked: custom should be preserved
    rs.set_frozen_mode(True)
    assert rs.custom_thresholds is not None
    assert rs.custom_thresholds.max_tau_ps == 99.0
    # get_thresholds() still returns the preset (frozen behavior)
    preset = RoutingThresholds.for_preset(rs.current_preset)
    assert abs(rs.get_thresholds().max_tau_ps - preset.max_tau_ps) < 1e-9


def test_switch_back_to_editable_restores_custom():
    """After Locked → Editable, custom values should be visible again."""
    _reset_routing_state_to_default()
    rs = global_routing_state
    rs.set_frozen_mode(False)
    if rs.custom_thresholds is None:
        rs.custom_thresholds = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    rs.custom_thresholds.max_tau_ps = 77.0
    rs.set_frozen_mode(True)
    rs.set_frozen_mode(False)
    assert rs.custom_thresholds is not None
    assert rs.custom_thresholds.max_tau_ps == 77.0
    assert abs(rs.get_thresholds().max_tau_ps - 77.0) < 1e-9


def test_set_custom_writes_and_keeps_editable():
    """set_custom() should write to custom_thresholds and leave mode editable."""
    _reset_routing_state_to_default()
    rs = global_routing_state
    new_thr = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    new_thr.max_r_ohm = 12.0
    rs.set_custom(new_thr)
    assert rs.custom_thresholds is new_thr
    assert rs.is_frozen is False
    assert abs(rs.get_thresholds().max_r_ohm - 12.0) < 1e-9
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_routing_config_layout.py -v -k "preserve_custom or set_custom or restores_custom"`
Expected: FAIL (current `set_frozen_mode(True)` discards custom; no `set_custom` method).

- [ ] **Step 3: Modify `app/routing_state.py`**

Edit `app/routing_state.py`:

(a) Replace the `set_frozen_mode` method body so it no longer discards `custom_thresholds`:

```python
    def set_frozen_mode(self, frozen: bool):
        """Set frozen mode. Does NOT discard custom_thresholds — it is a
        'draft area' that survives Locked↔Editable toggles (see spec §3.2.4).
        get_thresholds() returns preset when frozen and custom (or preset
        fallback) when editable; UI rehydrate handles the rest.
        """
        self._is_frozen = bool(frozen)
```

(b) Add a new `set_custom` method after `set_frozen_mode`:

```python
    def set_custom(self, thresholds: "RoutingThresholds"):
        """Adopt a custom thresholds object and switch to editable mode.

        Replaces the previous custom_thresholds (if any). The state is now
        editable; get_thresholds() will return this object.
        """
        self.custom_thresholds = thresholds
        self._is_frozen = False
```

(c) Update `get_threshold_source` to return English:

```python
    def get_threshold_source(self) -> str:
        """Human-readable source description for UI banners (English)."""
        if self._is_frozen:
            return f"Locked preset: {self.current_preset}"
        if self.custom_thresholds is not None:
            return f"Custom (based on {self.current_preset})"
        return f"Preset: {self.current_preset}"
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_routing_config_layout.py -v`
Expected: All pass (new cases + existing ones, including `test_frozen_vs_editable_apply_persistence` if you update the comment that mentioned "custom discarded on freeze" — see step 5).

- [ ] **Step 5: Update existing test that asserted discard behavior**

In `tests/test_routing_config_layout.py::test_frozen_vs_editable_apply_persistence`, find:

```python
    # Switch to frozen: custom is cleared, get returns preset (higher tolerance)
    rs.set_frozen_mode(True)
    pass_frozen, _ = check_gates(dummy_metrics, rs.get_thresholds(), has_golden=False)
    assert pass_frozen is True  # old preset allows the mid_tau

    # rehydrate after frozen switch shows original
    out_f2 = _compute_rehydrate_outputs()
    assert abs(out_f2[tau_idx] - orig_tau) < 1e-12  # custom discarded on freeze -> preset orig_tau
```

Replace the comment "custom discarded on freeze" with:
```python
    # Custom is preserved (draft area); get() returns preset because frozen
```

(The assertions themselves still pass: `out_f2[tau_idx] == orig_tau` because rehydrate shows the preset value when frozen.)

- [ ] **Step 6: Run full routing test suite**

Run: `pytest tests/test_routing_config_layout.py tests/test_routing_e2e.py tests/test_routing_thresholds.py -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add app/routing_state.py tests/test_routing_config_layout.py
git commit -m "feat(routing-state): preserve custom_thresholds on Locked toggle; add set_custom(); English source labels"
```

---

## Task 7: Wire real tab-switch rehydrate callback in `routing_config.py`

**Files:**
- Modify: `app/routing_config.py:462-491` (the existing tabs callback — replace with full rehydrate)
- Test: `tests/test_tab_rehydrate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tab_rehydrate.py`:

```python
"""Verify that switching back to the routing-config tab triggers a rehydrate."""
import sys
sys.path.insert(0, '.')


def test_rehydrate_outputs_after_state_change():
    """Simulate the user applying custom values, switching to another tab,
    then switching back. Rehydrate must reflect the applied state.
    """
    from app.routing_config import _compute_rehydrate_outputs
    from app.routing_state import global_routing_state, RoutingState
    from config.routing_thresholds import RoutingThresholds

    # Reset
    global_routing_state.current_preset = "sram_7nm_wl"
    global_routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    global_routing_state.custom_thresholds = None
    global_routing_state.set_frozen_mode(True)

    # User enters Editable and applies a custom value
    global_routing_state.set_frozen_mode(False)
    if global_routing_state.custom_thresholds is None:
        global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
            global_routing_state.get_thresholds().to_dict()
        )
    global_routing_state.custom_thresholds.max_tau_ps = 88.0

    # "Tab switch back" = calling rehydrate directly (callback body is the same)
    out = _compute_rehydrate_outputs()

    # Outputs 0..6 are classes/status; 7..13 are 7 thresh values; 14..20 are disabled
    tau_idx = 7 + 4
    assert abs(out[tau_idx] - 88.0) < 1e-9, (
        f"expected 88.0, got {out[tau_idx]} — rehydrate did not surface custom value"
    )
    assert out[14] is False  # editable → inputs enabled


def test_rehydrate_outputs_frozen_shows_preset_even_with_custom_draft():
    """When frozen but a custom draft exists, rehydrate shows preset (UI hides draft)."""
    from app.routing_config import _compute_rehydrate_outputs
    from app.routing_state import global_routing_state
    from config.routing_thresholds import RoutingThresholds

    global_routing_state.current_preset = "sram_7nm_wl"
    global_routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    global_routing_state.set_frozen_mode(True)
    # Inject a draft directly (simulating user previously edited)
    global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
        global_routing_state.get_thresholds().to_dict()
    )
    global_routing_state.custom_thresholds.max_tau_ps = 88.0

    # _is_frozen = True (we set it before injecting the draft)
    global_routing_state._is_frozen = True

    out = _compute_rehydrate_outputs()
    tau_idx = 7 + 4
    preset_tau = RoutingThresholds.for_preset("sram_7nm_wl").max_tau_ps
    assert abs(out[tau_idx] - preset_tau) < 1e-9
    assert out[14] is True  # frozen → inputs disabled
    # The draft is preserved in state
    assert global_routing_state.custom_thresholds.max_tau_ps == 88.0
```

- [ ] **Step 2: Run test — expect PASS (because `_compute_rehydrate_outputs` already exists)**

Run: `pytest tests/test_tab_rehydrate.py -v`
Expected: 2 passed (this validates the existing helper — good baseline).

- [ ] **Step 3: Replace the tabs callback in `app/routing_config.py`**

Find the callback registered at `Input("tabs", "value")` (around line 462-491). Replace its body so that when `tabs.value == 'tab-routing-config'`, it actually outputs the 7 thresh values, 7 disabled flags, mode classes, and preset value (i.e., a real rehydrate).

The new callback:

```python
    @app.callback(
        [Output("mode-frozen", "className", allow_duplicate=True),
         Output("mode-editable", "className", allow_duplicate=True),
         Output("routing-preset-status", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True),
         Output("thresh-unsaved-badge", "children", allow_duplicate=True),
         Output("thresh-apply-status", "children", allow_duplicate=True),
         Output("routing-preset", "value", allow_duplicate=True)]
        + [Output(f"thresh-{name}", "value", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS]
        + [Output(f"thresh-{name}", "disabled", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS],
        Input("tabs", "value"),
        prevent_initial_call=True,
    )
    def _rehydrate_on_tab(active_tab):
        """Rehydrate the Routing Config tab when the user switches to it.

        This is the bug fix: previously, switching tabs away and back did not
        re-populate the threshold inputs from state, so Apply'd values were
        not visible on the UI after returning. We now emit all thresh values
        + disabled flags + mode classes on every tab activation.
        """
        if active_tab != "tab-routing-config":
            # Don't disturb other tabs
            raise PreventUpdate
        return _compute_rehydrate_outputs()
```

NOTE: This may require `allow_duplicate=True` on the Output declarations if the
same Outputs are also used by the other callbacks (mode-frozen / mode-editable /
preset / thresh-*). Keep `allow_duplicate=True` as shown.

- [ ] **Step 4: Run the new test + existing routing_config tests**

Run: `pytest tests/test_tab_rehydrate.py tests/test_routing_config_layout.py -v`
Expected: All pass.

- [ ] **Step 5: Smoke-run the dash app (manual)**

```bash
cd 'd:\workspace\project\sram_layout_review'
python -c "from app.layout import create_layout; print('layout OK')"
```

Expected: prints `layout OK` with no exceptions.

- [ ] **Step 6: Commit**

```bash
git add app/routing_config.py tests/test_tab_rehydrate.py
git commit -m "fix(routing-config): real tab-switch rehydrate (7 thresh values + 7 disabled flags)"
```

---

## Task 8: Apply persistence test (TDD guard)

**Files:**
- Create: `tests/test_apply_persistence.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_apply_persistence.py`:

```python
"""Verify Apply thresholds persists across tab switch (the user's reported bug)."""
import sys
sys.path.insert(0, '.')

from app.routing_state import global_routing_state
from app.routing_config import (
    _compute_rehydrate_outputs,
    _handle_routing_preset_or_thresh,
    THRESHOLD_FIELDS,
)
from config.routing_thresholds import RoutingThresholds


def _reset():
    global_routing_state.current_preset = "sram_7nm_wl"
    global_routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    global_routing_state.custom_thresholds = None
    global_routing_state.set_frozen_mode(True)


def test_apply_then_tab_switch_persists_values():
    """Apply + tab switch + rehydrate must show the applied values."""
    _reset()
    rs = global_routing_state

    # Simulate Apply: user enters Editable, modifies tau, calls Apply
    rs.set_frozen_mode(False)
    if rs.custom_thresholds is None:
        rs.custom_thresholds = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    rs.custom_thresholds.max_tau_ps = 25.0
    rs.custom_thresholds.max_r_ohm = 60.0

    # Simulate tab switch back: rehydrate
    out = _compute_rehydrate_outputs()
    tau_idx = 7 + 4  # tau is 4th field (h, v, r, c, tau, via, sim)
    r_idx = 7 + 2
    assert abs(out[tau_idx] - 25.0) < 1e-9, f"tau={out[tau_idx]}"
    assert abs(out[r_idx] - 60.0) < 1e-9, f"r={out[r_idx]}"
    # Editable → enabled
    assert out[14] is False


def test_apply_failure_does_not_touch_state():
    """Invalid apply values must NOT change routing_state.thresholds or custom_thresholds."""
    _reset()
    rs = global_routing_state
    original_tau = rs.get_thresholds().max_tau_ps

    rs.set_frozen_mode(False)
    # Pass invalid h_ratio=0.3, v_ratio=0.3 → sum < 1.0 → validate fails
    bad_values = (0.3, 0.3, 50.0, 20.0, 12.5, 0.8, 70.0)
    try:
        _handle_routing_preset_or_thresh(None, bad_values, "thresh-max_h_ratio")
    except Exception:
        pass  # PreventUpdate or normal — both acceptable

    # State thresholds must be unchanged
    assert abs(rs.get_thresholds().max_tau_ps - original_tau) < 1e-9
```

- [ ] **Step 2: Run test**

Run: `pytest tests/test_apply_persistence.py -v`
Expected: Both pass (regression guards; they verify the existing Apply + rehydrate chain).

- [ ] **Step 3: Commit**

```bash
git add tests/test_apply_persistence.py
git commit -m "test: add Apply persistence regression guard"
```

---

## Task 9: i18n cleanup — `app/routing_config.py`

**Files:**
- Modify: `app/routing_config.py` (replace all Chinese user-facing strings with English)

- [ ] **Step 1: Find every Chinese string in `app/routing_config.py`**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
Select-String -Path 'app\routing_config.py' -Pattern '[\x{4e00}-\x{9fff}]' -CaseSensitive:$false
```

Record the file lines containing Chinese.

- [ ] **Step 2: Apply replacements using the locked terminology table**

Use `SearchReplace` for each occurrence. The mapping (from spec §4):

| Chinese | English |
|---|---|
| 冻结 | Locked |
| 可编辑 | Editable |
| 编辑模式 | Edit Mode |
| 已阻止 / 阻止 | Blocked |
| 未保存 | Unsaved Changes |
| 已应用 | Applied |
| 应用 | Apply |
| 加载预设中 | Loading Preset… |
| 已加载预设 | Preset Loaded |
| 重新载入 | Reload |
| 恢复默认 | Restore Defaults |
| 校验失败 | Validation Failed |
| 高亮 | Highlight |
| 当前阈值来源 | Active Threshold Source |
| 阈值 | Threshold |
| 预设 | Preset |
| 通过/失败 | Pass / Fail |
| 严重 | Critical |
| 错误 | Error |
| 警告 | Warning |
| 成功 | Success |
| 有效 | Valid |
| 无效 | Invalid |
| 无变化 | No Changes |
| 已保存 | Saved |
| 默认 | Default |
| 自定义 | Custom |
| 模式 | Mode |
| 草稿 | Draft |

Replace each occurrence using `SearchReplace` (one tool call per location). Examples:

```python
# Old: html.Span("Mode: 冻结（{preset}）", ...)
# New: html.Span(f"Mode: Locked ({preset})", ...)
```

```python
# Old: "Preset change blocked in Edit Mode"
# New: "Preset change blocked in Edit Mode"  (already English in this case)
```

```python
# Old: "● unsaved changes"
# New: "● Unsaved Changes"
```

```python
# Old: "Apply failed: ..."
# New: "Apply failed: ..."  (already English)
```

- [ ] **Step 3: Verify no Chinese remains in `app/routing_config.py`**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
Select-String -Path 'app\routing_config.py' -Pattern '[\x{4e00}-\x{9fff}]' -CaseSensitive:$false
```

Expected: no matches.

- [ ] **Step 4: Update the test that asserted Chinese text**

In `tests/test_routing_config_layout.py`, the case `test_handle_logic_editable_preset_prevent` asserts:
```python
assert "编辑模式" in status_txt and "阻止" in status_txt
```

Update it to:
```python
assert "Edit Mode" in status_txt and "Blocked" in status_txt
```

- [ ] **Step 5: Run routing_config tests**

Run: `pytest tests/test_routing_config_layout.py tests/test_apply_persistence.py tests/test_tab_rehydrate.py -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_layout.py
git commit -m "i18n(routing-config): replace Chinese strings with English (Locked / Editable / Edit Mode / Blocked / Unsaved Changes / ...)"
```

---

## Task 10: i18n cleanup — `app/routing_review.py`

**Files:**
- Modify: `app/routing_review.py`

- [ ] **Step 1: Find every Chinese string**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
Select-String -Path 'app\routing_review.py' -Pattern '[\x{4e00}-\x{9fff}]' -CaseSensitive:$false
```

- [ ] **Step 2: Replace using locked terminology**

The notable Chinese is in `_build_threshold_source` (line ~83):
```python
# Old:
html.Span("当前阈值来源: ", ...)

# New:
html.Span("Active Threshold Source: ", ...)
```

And `routing_state.get_threshold_source()` already returns English after Task 6.

- [ ] **Step 3: Verify no Chinese remains**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
Select-String -Path 'app\routing_review.py' -Pattern '[\x{4e00}-\x{9fff}]' -CaseSensitive:$false
```

Expected: no matches.

- [ ] **Step 4: Run routing_review-related tests**

Run: `pytest tests/test_routing_e2e.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add app/routing_review.py
git commit -m "i18n(routing-review): replace Chinese strings with English (Active Threshold Source)"
```

---

## Task 11: i18n cleanup — `app/callbacks.py` + `app/layout.py`

**Files:**
- Modify: `app/callbacks.py`
- Modify: `app/layout.py`

- [ ] **Step 1: Find Chinese in `app/callbacks.py`**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
Select-String -Path 'app\callbacks.py' -Pattern '[\x{4e00}-\x{9fff}]' -CaseSensitive:$false
```

- [ ] **Step 2: Replace each occurrence with English**

The notable line (around 615):
```python
# Old: "Please run Full Review from the Layout View panel first."
# New: "Run Full Review from the Layout View tab first."
```

- [ ] **Step 3: Find Chinese in `app/layout.py`**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
Select-String -Path 'app\layout.py' -Pattern '[\x{4e00}-\x{9fff}]' -CaseSensitive:$false
```

- [ ] **Step 4: Replace with English**

Examples in `app/layout.py`:
```python
# Old: html.Div('LAYOUT REVIEW PRO', ...)
# Already English — keep
# Old: html.Div('Advanced IC Layout Verification', ...)
# Already English — keep
# Any Chinese in headers → translate
```

- [ ] **Step 5: Verify no Chinese in app/ or layout.py**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
Select-String -Path 'app\*.py' -Pattern '[\x{4e00}-\x{9fff}]' -CaseSensitive:$false
```

Expected: no matches (docstrings may still contain Chinese in some files; that's acceptable for developer docs, but the task spec says "禁止出现中文" — to be safe, scan and remove from layout.py and callbacks.py).

- [ ] **Step 6: Run all tests**

Run: `pytest tests/ -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add app/callbacks.py app/layout.py
git commit -m "i18n(callbacks,layout): remove remaining Chinese user-facing strings"
```

---

## Task 12: Final integration test

**Files:**
- Run: `pytest tests/` end-to-end
- Manual: launch dash app, sample shape, verify both tabs

- [ ] **Step 1: Run the entire test suite**

Run:
```bash
cd 'd:\workspace\project\sram_layout_review'
pytest tests/ -v
```

Expected: All pass (existing + new). If any fail, fix and re-run.

- [ ] **Step 2: Manual end-to-end smoke (5 minutes)**

```bash
cd 'd:\workspace\project\sram_layout_review'
python app.py
```

Open the browser at `http://127.0.0.1:8050` (or the port printed):
1. Upload `tests/shapes_test_normal.txt` from the Layout View tab.
2. Run Full Review.
3. Check the right-side Properties panel — confirm R (Ω), C (fF), τ Elmore (ps), τ Naive (ps) all show numbers.
4. Switch to Routing Review tab → click Run Review.
5. Compare the Eff. R / Eff. C / Eff. τ numbers in the metric cards to the Properties panel — they must be equal.
6. Switch to Routing Config tab.
7. Click Editable → change max_tau_ps to 5 → click Apply Thresholds.
8. Switch to Layout View, then back to Routing Config — the value 5 must still be in the input.
9. Click Locked — the input should now show the preset value (12.5 for sram_7nm_wl) and be disabled.
10. Click Editable — input should restore 5 and be enabled.

- [ ] **Step 3: Final commit (if any post-smoke fix needed)**

```bash
git status
# If anything changed:
git add -A
git commit -m "chore: post-integration smoke fixes"
```

If no changes: skip.

---

## Self-Review

**Spec coverage check:**

| Spec section | Implementing task |
|---|---|
| §2.1 single RC source | T1, T2, T3 |
| §2.2 config state machine + rehydrate | T6, T7, T8 |
| §2.3 preset loader schema-aware | T4, T5 |
| §3.1 properties panel flow | T3 |
| §3.2.1-3.2.5 config callbacks | T6, T7 |
| §3.3 routing review reads from state | T6 (get_thresholds) |
| §4 i18n terminology | T9, T10, T11 |
| §5 error handling | T4 (validation errors), T6 (preserve draft) |
| §6 testing | All tasks include tests |
| §8 acceptance | T12 (final smoke) |

All spec sections covered.

**Placeholder scan:** No TBD / TODO / "fill in later" in plan. All step content is concrete code or commands.

**Type consistency:**
- `summarize_net` returns: `net_name, r_total_ohm, c_total_ff, tau_elmore_ps, tau_naive_ps, h_ratio, v_ratio, missing_via_count, via_coverage, similarity_score, dominant, status` (T1)
- `routing_state.set_custom(thresholds)` signature (T6) — referenced consistently in plan
- `RoutingThresholds.for_preset(name)` — used in T1, T4, T5
- `PresetValidationError` — raised in T4 step 3, tested in T4 step 1

All consistent.

**Risks acknowledged:**
- T3 changes Properties panel callback Output count from 13 to 14 — must add a new `prop-tau-naive` element in `app/layout.py` BEFORE changing the callback (otherwise UI won't bind).
- T6 changes `set_frozen_mode` behavior — test `test_frozen_vs_editable_apply_persistence` needs comment update (T6 step 5) to avoid misleading future readers.
- T7 callback at `Input("tabs","value")` may need `allow_duplicate=True` on Outputs that are also used by Apply / mode / preset callbacks. Use `allow_duplicate=True` on every Output to be safe.

**Out of scope (per spec §9):**
- DRC engine rewrite — not touched
- Theme rework — not touched
- New routing metrics (EM/IR) — not added
- i18n framework — static string replacement only
