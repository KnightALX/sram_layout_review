# SRAM Layout Review — A+B Cleanup Design Spec

**Date:** 2026-06-20  
**Status:** Approved  
**Scope:** A (UI/docs/startup) + B (Via wiring, theme, RC side-effect cleanup)

---

## Problem Statement

The project has drifted from its intended 4-tab workflow after commit `080ae4e` added an RC Prediction tab as the default landing page. Additional reliability issues prevent accurate via detection in Routing Review and create inconsistent UX (theme defaults, hidden import side effects).

Dependencies are not installed in the local environment, so the app cannot be started or tested without setup.

---

## Goals

1. Restore the intended **4-tab UI**: Layout View → Routing Config → Routing Review → Report Export.
2. Make the application **runnable** (`pip install` + smoke start).
3. Wire **real via polygons** into Routing Review metrics (fix `vias=[]` placeholder).
4. Unify **theme defaults** to Light.
5. Eliminate **RC Prediction import side effects** on app startup.
6. Sync **README.md** and **CLAUDE.md** with the code.

## Non-Goals (deferred to scope C)

- Fixing 3 pre-existing test failures (`test_polygon_distance`, `test_rc_calculator`)
- Removing `suppress_callback_exceptions=True`
- Adding `pytest` to `requirements.txt`
- Deleting `app/rc_prediction.py` backend modules (kept as dead code for now)
- Import-time polygon splitting in `callbacks.py` / `nets_data` schema changes

---

## Recommended Approach: Minimal-Invasion (Path 1)

Remove RC Prediction from the UI only; keep `app/rc_model.py` and `routing_state.get_rc_model()` for default RC calculations. Split metal/via polygons at **compute time** in `routing_review._run_routing_review()` using a new helper in `core/routing_metrics.py`.

---

## Architecture

### Tab Structure (Target)

| Tab | Value | Purpose |
|-----|-------|---------|
| Layout View | `tab-view` | Shape import, visualization, legacy Full Review |
| Routing Config | `tab-routing-config` | Presets, thresholds, golden/batch regex |
| Routing Review | `tab-routing-review` | 6-metric cards, table, directional viz |
| Report Export | `tab-export` | Legacy PPTX/PDF export |

Default tab: `tab-view`.

### Via Data Flow (Fixed)

```
shape file (.txt)
  → core.data_parsing.parse_shape_txt()
  → app_state.nets_data[net].polygons  (metals + vias mixed)
  → split_metal_via_polygons(polygons)
       → metals[], vias[]
  → compute_for_net(name, metals, vias, ...)
       → analyze_via_coverage(metals, vias)
```

Uses existing `is_via_layer()` from `core/visualization.py`.

### RC Model (Unchanged Backend)

- `routing_state.rc_model` provides built-in 7nm defaults.
- `routing_state.custom_rc_model` stays `None` (no UI to set it).
- No import of `app/rc_prediction.py` at startup → no disk auto-load side effect.

### Theme

- `dcc.Store(id='theme-store', data='light')` in `app/layout.py`
- Client JS in `layout_review_app.py` already defaults to `'light'` via localStorage

---

## Component Changes

### `app/layout.py`

- Remove `from app.rc_prediction import create_rc_prediction_tab`
- Remove RC Prediction `dcc.Tab`
- Change `dcc.Tabs` default `value` from `'tab-rc-prediction'` to `'tab-view'`
- Change `theme-store` default from `'dark'` to `'light'`

### `app/callbacks.py`

- Remove `from app.rc_prediction import register_rc_prediction_callbacks`
- Remove `register_rc_prediction_callbacks(app)` call

### `core/routing_metrics.py`

Add exported helper:

```python
def split_metal_via_polygons(polygons: List["Polygon"]) -> Tuple[List["Polygon"], List["Polygon"]]:
    """Split a mixed polygon list into metal shapes and via shapes."""
```

### `app/routing_review.py`

In `_run_routing_review()` and visualization callbacks:

```python
from core.routing_metrics import compute_for_net, split_metal_via_polygons

metals, vias = split_metal_via_polygons(polys)
m = compute_for_net(name, metals, vias, ...)
fig = create_directional_figure(polygons=metals, vias=vias, ...)
```

### Documentation

- `README.md`: 4 tabs, remove RC Prediction workflow, update project status
- `CLAUDE.md`: 4-tab UI, note via wiring, note RC Prediction tab removed

---

## Testing Strategy

| Test | Purpose |
|------|---------|
| `test_split_metal_via_polygons` (new) | Unit test for polygon splitter |
| `test_routing_metrics.py` (existing) | Regression on 6-metric aggregator |
| `test_via_coverage.py` (existing) | Via analyzer regression |
| `test_routing_e2e.py` (existing) | End-to-end routing metrics |
| Manual smoke | `python layout_review_app.py 8050` → 4 tabs, default Layout View |

---

## Acceptance Criteria

- [ ] Browser shows exactly 4 tabs; RC Prediction absent
- [ ] Default tab is Layout View on first load
- [ ] `pip install -r requirements.txt` succeeds; app starts on port 8050
- [ ] Net with overlapping M1/M2 and no via polygon → `missing_via_count > 0`
- [ ] Net with proper via polygons → via coverage reflects actual coverage
- [ ] First-load theme is Light (no dark flash)
- [ ] README and CLAUDE.md describe 4-tab workflow accurately
- [ ] No `app/rc_prediction` import at app startup (grep `callbacks.py` / `layout.py`)

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Via layer names not recognized by `is_via_layer()` | Reuse same helper as visualization; covered by unit test with `via0`/`via1` |
| Legacy Full Review unaffected | Split only in `routing_review.py`; `nets_data` schema unchanged |
| Dead `rc_prediction.py` confuses future devs | Add module docstring note: "UI removed 2026-06-20; backend retained" |

---

## Estimated Effort

~1.5–2 hours total across 4 phases.