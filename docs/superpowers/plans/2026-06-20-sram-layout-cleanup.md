# SRAM Layout A+B Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore 4-tab UI (remove RC Prediction), install deps, wire via detection into Routing Review, fix theme defaults, and sync docs.

**Architecture:** Minimal-invasion Path 1 — remove RC Prediction UI/callbacks only; add `split_metal_via_polygons()` in `core/routing_metrics.py`; call it from `app/routing_review.py` before `compute_for_net()`. RC backend (`rc_model.py`) unchanged; no `rc_prediction` import at startup.

**Tech Stack:** Python 3.8+, Dash 2.0+, Plotly, pytest

**Spec:** `docs/superpowers/specs/2026-06-20-sram-layout-cleanup-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/layout.py` | Modify | Remove RC Prediction tab; default `tab-view`; theme `light` |
| `app/callbacks.py` | Modify | Remove RC Prediction callback registration |
| `core/routing_metrics.py` | Modify | Add `split_metal_via_polygons()` |
| `app/routing_review.py` | Modify | Use splitter in `_run_routing_review()` + viz callbacks |
| `tests/test_routing_metrics.py` | Modify | Add splitter unit tests |
| `README.md` | Modify | 4-tab docs |
| `CLAUDE.md` | Modify | Architecture sync |
| `app/rc_prediction.py` | Modify | Add "UI removed" docstring note only |

---

### Task 1: Install Dependencies

**Files:**
- Read: `requirements.txt`

- [ ] **Step 1: Install packages**

```bash
cd /Users/niexinkai/claudecode/sram_layout
python3 -m pip install -r requirements.txt
```

Expected: all packages install without error (dash, plotly, numpy, shapely, python-pptx, pyyaml, etc.)

- [ ] **Step 2: Verify imports**

```bash
python3 -c "from dash import Dash; import plotly; import shapely; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit** (skip if no git repo at project level — optional)

```bash
git add requirements.txt  # only if changed
git commit -m "chore: install project dependencies"
```

---

### Task 2: Remove RC Prediction Tab

**Files:**
- Modify: `app/layout.py:11,28-30`
- Modify: `app/callbacks.py:537-540`

- [ ] **Step 1: Edit `app/layout.py`**

Remove line 11:
```python
from app.rc_prediction import create_rc_prediction_tab
```

Replace lines 28-36 (the `dcc.Tabs` block) with:
```python
        dcc.Tabs(id='tabs', value='tab-view', children=[
            dcc.Tab(label='Layout View', value='tab-view', children=_create_layout_view_content()),
            dcc.Tab(label='Routing Config', value='tab-routing-config',
                    children=create_routing_config_tab()),
            dcc.Tab(label='Routing Review', value='tab-routing-review',
                    children=create_routing_review_tab()),
            dcc.Tab(label='Report Export', value='tab-export', children=_create_export_content()),
        ], className='eda-tabs'),
```

Also change line 22:
```python
        dcc.Store(id='theme-store', data='light'),
```

- [ ] **Step 2: Edit `app/callbacks.py`**

Delete these three lines at the bottom of `register_callbacks()`:
```python
    from app.rc_prediction import register_rc_prediction_callbacks
    register_rc_prediction_callbacks(app)
```

(Keep `register_routing_config_callbacks` and `register_routing_review_callbacks`.)

- [ ] **Step 3: Verify layout imports**

```bash
python3 -c "from app.layout import create_layout; create_layout(); print('layout OK')"
```

Expected: `layout OK`

- [ ] **Step 4: Commit**

```bash
git add app/layout.py app/callbacks.py
git commit -m "feat(app): remove RC Prediction tab, default to Layout View"
```

---

### Task 3: Add `split_metal_via_polygons` (TDD)

**Files:**
- Modify: `tests/test_routing_metrics.py`
- Modify: `core/routing_metrics.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_routing_metrics.py` after the imports block:

```python
from core.routing_metrics import split_metal_via_polygons


def test_split_metal_via_polygons_separates_layers():
    """Mixed polygon list splits into metals and vias."""
    metals_in = [_rect(0, 0, 10, 1, "met1"), _rect(5, 0, 6, 10, "met2")]
    vias_in = [_via(5.5, 5, layer="via1")]
    all_polys = metals_in + vias_in
    metals, vias = split_metal_via_polygons(all_polys)
    assert len(metals) == 2
    assert len(vias) == 1
    assert metals[0].layer == "met1"
    assert vias[0].layer == "via1"


def test_split_metal_via_polygons_empty():
    metals, vias = split_metal_via_polygons([])
    assert metals == []
    assert vias == []


def test_split_metal_via_polygons_via0_layer():
    """via0 (poly contact) must be recognized as a via layer."""
    polys = [_rect(0, 0, 2, 2, "met1"), _via(1, 1, layer="via0")]
    metals, vias = split_metal_via_polygons(polys)
    assert len(metals) == 1
    assert len(vias) == 1
    assert vias[0].layer == "via0"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_routing_metrics.py::test_split_metal_via_polygons_separates_layers -v
```

Expected: FAIL — `ImportError: cannot import name 'split_metal_via_polygons'`

- [ ] **Step 3: Implement `split_metal_via_polygons`**

Add to `core/routing_metrics.py` after the imports (before `_bbox_aspect`):

```python
from core.visualization import is_via_layer


def split_metal_via_polygons(polygons: List["Polygon"]) -> Tuple[List["Polygon"], List["Polygon"]]:
    """Split a mixed polygon list into metal shapes and via shapes.

    Shape files store all layers in one list. Routing review must pass
    metals and vias separately to analyze_via_coverage().
    """
    metals: List["Polygon"] = []
    vias: List["Polygon"] = []
    for poly in polygons:
        if is_via_layer(poly.layer):
            vias.append(poly)
        else:
            metals.append(poly)
    return metals, vias
```

Ensure `Tuple` is imported from `typing` (already present in file).

- [ ] **Step 4: Run all new splitter tests**

```bash
python3 -m pytest tests/test_routing_metrics.py -k "split_metal_via" -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add core/routing_metrics.py tests/test_routing_metrics.py
git commit -m "feat(core): add split_metal_via_polygons helper"
```

---

### Task 4: Wire Vias into Routing Review

**Files:**
- Modify: `app/routing_review.py` (~lines 415-550)

- [ ] **Step 1: Add import at top of `app/routing_review.py`**

Find the existing import from `core.routing_metrics` and extend it:

```python
from core.routing_metrics import compute_for_net, split_metal_via_polygons
```

(If `compute_for_net` is imported inside a function, add `split_metal_via_polygons` there instead — match existing style.)

- [ ] **Step 2: Fix visualization callback (picker-only path, ~line 415)**

Replace:
```python
                polys = net_data.get("polygons", [])
                m = routing_state.batch_results.get(selected_net)
                if m:
                    fig = create_directional_figure(
                        polygons=polys, vias=[],
```

With:
```python
                polys = net_data.get("polygons", [])
                metals, vias = split_metal_via_polygons(polys)
                m = routing_state.batch_results.get(selected_net)
                if m:
                    fig = create_directional_figure(
                        polygons=metals, vias=vias,
```

- [ ] **Step 3: Fix visualization callback (run-button path, ~line 454)**

Same replacement pattern:
```python
            polys = net_data.get("polygons", [])
            metals, vias = split_metal_via_polygons(polys)
            m = routing_state.batch_results.get(viz_net)
            if m:
                fig = create_directional_figure(
                    polygons=metals, vias=vias,
```

- [ ] **Step 4: Fix `_run_routing_review()` golden path (~line 526)**

Replace:
```python
        g_polys = g_data.get("polygons", [])
        g_vias = []  # to be populated when Via support is wired up
        m = compute_for_net(golden_name, g_polys, g_vias, tech_layers, thresholds,
```

With:
```python
        g_polys = g_data.get("polygons", [])
        g_metals, g_vias = split_metal_via_polygons(g_polys)
        m = compute_for_net(golden_name, g_metals, g_vias, tech_layers, thresholds,
```

- [ ] **Step 5: Fix `_run_routing_review()` batch loop (~line 545)**

Replace:
```python
        polys = data.get("polygons", [])
        vias = []
        m = compute_for_net(name, polys, vias, tech_layers, thresholds,
```

With:
```python
        polys = data.get("polygons", [])
        metals, vias = split_metal_via_polygons(polys)
        m = compute_for_net(name, metals, vias, tech_layers, thresholds,
```

- [ ] **Step 6: Add integration test for missing-via detection**

Add to `tests/test_routing_metrics.py`:

```python
def test_compute_for_net_detects_missing_via_from_mixed_polygons():
    """Overlapping met1+met2 without via polygon → missing_via_count > 0."""
    # Same geometry as tests/shapes_test_missing_via.txt (scaled to µm)
    met1 = _rect(0, 0, 2, 4, "met1")
    met2 = _rect(0, 0, 2, 4, "met2")
    mixed = [met1, met2]  # no via — passed as single list like nets_data
    metals, vias = split_metal_via_polygons(mixed)
    assert len(vias) == 0
    t = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("MISSING_VIA", metals, vias, _tech_layers(), t, golden_metrics=None)
    assert m["missing_via_count"] > 0
    assert m["via_coverage"] < 1.0
```

- [ ] **Step 7: Run routing tests**

```bash
python3 -m pytest tests/test_routing_metrics.py tests/test_via_coverage.py tests/test_routing_e2e.py -q
```

Expected: all PASSED (no regressions)

- [ ] **Step 8: Commit**

```bash
git add app/routing_review.py tests/test_routing_metrics.py
git commit -m "feat(routing): wire via polygons into routing review metrics"
```

---

### Task 5: RC Side-Effect Note

**Files:**
- Modify: `app/rc_prediction.py:1-15`

- [ ] **Step 1: Update module docstring**

Replace the opening docstring with:

```python
"""RC Prediction tab — BACKEND ONLY (UI removed 2026-06-20).

This module is no longer registered in the Dash app. The RC model backend
(`RCModelConfig`, persistence helpers) is retained for `routing_state.get_rc_model()`.
Do not import this module from layout.py or callbacks.py — it has a module-level
disk auto-load side effect.
"""
```

- [ ] **Step 2: Verify no startup import**

```bash
grep -r "rc_prediction" app/layout.py app/callbacks.py layout_review_app.py
```

Expected: no matches

- [ ] **Step 3: Commit**

```bash
git add app/rc_prediction.py
git commit -m "docs: mark rc_prediction as backend-only after tab removal"
```

---

### Task 6: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `README.md`**

Changes:
1. Remove any RC Prediction tab references from the tab table and workflow sections.
2. Confirm tab list is exactly: Layout View / Routing Config / Routing Review / Report Export.
3. Update **项目状态** section:
   ```markdown
   - **2026-06-20**: 移除 RC Prediction Tab；接入 Via 检测；默认 Tab 改为 Layout View。
   - **2026-06-01**: Routing review rewrite 完成。
   ```
4. Remove or update the line about `vias=[]` placeholder under **下次迭代** — via wiring is now done.

- [ ] **Step 2: Update `CLAUDE.md`**

Changes:
1. Line 53: change "4-tab UI" confirmation (already says 4-tab — verify no RC Prediction mention).
2. Add under Known quirks / architecture:
   ```markdown
   - RC Prediction tab removed (2026-06-20). `routing_state.get_rc_model()` uses built-in defaults only.
   - `split_metal_via_polygons()` in `core/routing_metrics.py` splits mixed polygons before routing review.
   ```
3. Remove any reference to RC Prediction Tab as an active UI entry point.

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: sync README and CLAUDE for 4-tab layout and via wiring"
```

---

### Task 7: Smoke Test & Acceptance

**Files:** none (verification only)

- [ ] **Step 1: Start the app**

```bash
cd /Users/niexinkai/claudecode/sram_layout
python3 layout_review_app.py 8050
```

Expected console output includes `URL: http://localhost:8050`

- [ ] **Step 2: Manual acceptance checklist**

| Check | Expected |
|-------|----------|
| Tab count | 4 (no RC Prediction) |
| Default tab | Layout View |
| Theme | Light on first load |
| Upload `tests/shapes_test_missing_via.txt` | Net loads in Layout View |
| Run Routing Review | `missing_via_count > 0` for overlapping metals |

- [ ] **Step 3: Run full pytest suite (informational)**

```bash
python3 -m pytest tests/ -q --tb=line 2>&1 | tail -5
```

Note: 3 pre-existing failures are acceptable (out of scope C). New tests must pass.

- [ ] **Step 4: Final commit** (if any fixups needed)

```bash
git add -A
git commit -m "chore: A+B cleanup complete — 4-tab UI, via wiring, theme fix"
```

---

## Self-Review Checklist

| Spec Requirement | Task |
|------------------|------|
| Remove RC Prediction tab | Task 2 |
| Default tab Layout View | Task 2 |
| Install deps + start app | Task 1, Task 7 |
| Via wiring | Task 3, Task 4 |
| Theme light default | Task 2 |
| No rc_prediction startup import | Task 2, Task 5 |
| Docs sync | Task 6 |
| Acceptance tests | Task 3, Task 4, Task 7 |

No placeholders. All code blocks are complete and copy-pasteable.