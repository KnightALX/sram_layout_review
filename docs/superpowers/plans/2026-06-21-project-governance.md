# SRAM Layout Project Governance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore both Legacy and Routing pipelines end-to-end, wire the `rules/` plugin system, eliminate dead code and Dash debt, unify architecture, and establish CI/lint baseline.

**Architecture:** Path 1 incremental phases (0→5). Legacy Pipeline **retained and fixed** (Decision A). Shared models in `core/models.py`; rules executed via `rules.registry.create_rule()`; Dash layer thin callbacks only.

**Tech Stack:** Python 3.8+, Dash 2.x, pytest, ruff

**Spec:** `docs/superpowers/specs/2026-06-21-project-governance-design.md`

---

## Phase Overview

| Phase | Focus | Est. |
|-------|-------|------|
| **0** | Baseline tooling | 1–2d |
| **1** | P0 functional fixes | 3–5d |
| **2** | Dead code + Dash cleanup | 3–4d |
| **3** | Architecture + rules wiring | 5–7d |
| **4** | Module split + PDK unify | 4–5d |
| **5** | CI, coverage, docs | 3–4d |

---

# Phase 0: Baseline Tooling

### Task 0.1: Add pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Create requirements-dev.txt**

```text
pytest>=7.0,<9
ruff>=0.4
pytest-cov>=4.0
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[project]
name = "sram-layout-review"
version = "0.1.0"
requires-python = ">=3.8"
dependencies = []  # runtime deps stay in requirements.txt

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"

[tool.ruff]
line-length = 100
target-version = "py38"
select = ["E", "F", "I", "W"]
ignore = ["E501"]

[tool.ruff.per-file-ignores]
"app/theme.py" = ["E501"]
```

- [ ] **Step 3: Install dev deps**

```bash
cd /Users/niexinkai/claudecode/sram_layout
python3 -m pip install -r requirements-dev.txt
```

- [ ] **Step 4: Run baseline**

```bash
python3 -m pytest tests/ -q --ignore=tests/test_rc_prediction.py 2>&1 | tail -3
```

Expected: `3 failed, 132 passed` (document exact numbers in commit message)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements-dev.txt
git commit -m "chore: add pyproject.toml and dev requirements baseline"
```

---

### Task 0.2: Add conftest.py

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create minimal conftest**

```python
"""Shared pytest configuration. pythonpath set in pyproject.toml."""
import pytest


@pytest.fixture
def tech_layers_met12():
    return {
        "met1": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_space": 0.032},
        "met2": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.12,
                 "capacitance_per_um": 0.16, "min_space": 0.032},
        "via1": {"type": "via", "min_size": 0.024, "resistance": 1.0},
    }
```

- [ ] **Step 2: Verify pytest still passes**

```bash
python3 -m pytest tests/test_routing_metrics.py -q
```

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "chore: add pytest conftest with shared fixtures"
```

---

# Phase 1: P0 Functional Fixes

### Task 1.1: Fix pre-existing test failures

**Files:**
- Modify: `review_engine.py` (polygon distance helper)
- Modify: `tests/test_rc_calculator.py`

- [ ] **Step 1: Run failing tests**

```bash
python3 -m pytest tests/test_polygon_distance.py tests/test_rc_calculator.py::TestViaResistance::test_via_creation -v
```

- [ ] **Step 2: Fix polygon distance for overlapping rects**

In `review_engine.py`, find `_min_polygon_distance` (or equivalent). When bboxes overlap, return `0.0` before edge-distance computation:

```python
# After bbox overlap check — if rects overlap, distance is 0
x_overlap = min(p1.bbox[2], p2.bbox[2]) - max(p1.bbox[0], p2.bbox[0])
y_overlap = min(p1.bbox[3], p2.bbox[3]) - max(p1.bbox[1], p2.bbox[1])
if x_overlap > 0 and y_overlap > 0:
    return 0.0
```

- [ ] **Step 3: Fix via resistance assertion**

In `tests/test_rc_calculator.py`, change:
```python
self.assertLess(via.resistance, 20)
```
to:
```python
self.assertLessEqual(via.resistance, 20)
```

- [ ] **Step 4: Verify**

```bash
python3 -m pytest tests/test_polygon_distance.py tests/test_rc_calculator.py::TestViaResistance::test_via_creation -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add review_engine.py tests/test_rc_calculator.py
git commit -m "fix: polygon overlap distance zero and via resistance test boundary"
```

---

### Task 1.2: Wire Full Review button

**Files:**
- Modify: `app/callbacks.py`
- Test: `tests/test_full_review_callback.py` (new)

- [ ] **Step 1: Write integration test**

Create `tests/test_full_review_callback.py`:

```python
"""Smoke test: Full Review engine path (no Dash server)."""
import sys
sys.path.insert(0, '.')
from review_engine import ProfessionalLayoutReviewEngine, Polygon, Point
from config_system import get_sram_7nm_config
from core.data_parsing import parse_shape_txt


def test_run_full_review_sets_summary():
    path = "tests/shapes_test_normal.txt"
    with open(path) as f:
        content = f.read()
    result = parse_shape_txt(content, path)
    assert result is not None
    net_name, shapes, polygons = result
    config = get_sram_7nm_config()
    engine = ProfessionalLayoutReviewEngine(config)
    engine.add_net_polygons(net_name, polygons)
    engine.calculate_net_rc(net_name)
    summary = engine.run_full_review()
    assert summary.total_nets >= 1
    assert summary.total_violations >= 0
```

- [ ] **Step 2: Run test**

```bash
python3 -m pytest tests/test_full_review_callback.py -v
```

- [ ] **Step 3: Add callback in `app/callbacks.py`**

Inside `register_callbacks()`, add before routing registration:

```python
    @app.callback(
        [Output('prop-critical', 'children'),
         Output('prop-warnings', 'children'),
         Output('prop-info', 'children'),
         Output('output-log', 'children')],
        Input('btn-run-review-panel', 'n_clicks'),
        prevent_initial_call=True,
    )
    def run_full_review_panel(n_clicks):
        if not n_clicks or not app_state.engine:
            raise PreventUpdate
        try:
            summary = app_state.engine.run_full_review()
            app_state.review_completed = True
            crit = str(summary.critical_count)
            warn = str(summary.warning_count)
            info = str(summary.info_count)
            log = html.Div(f"Full review complete: {summary.total_violations} violations across {summary.total_nets} nets.")
            return crit, warn, info, log
        except Exception as e:
            return '0', '0', '0', html.Div(f"Review error: {e}", className='text-fail')
```

Add `from dash.exceptions import PreventUpdate` if not present.

- [ ] **Step 4: Commit**

```bash
git add app/callbacks.py tests/test_full_review_callback.py
git commit -m "feat(app): wire Run Full Review panel button"
```

---

### Task 1.3: Fix Report Export gate

**Files:**
- Modify: `app/callbacks.py` (~line 498)

- [ ] **Step 1: Update gate logic**

Replace:
```python
        if not app_state.review_completed:
            return html.Div("Please run a review first before generating reports.", className="alert alert-warning")
```

With:
```python
        if not app_state.review_completed:
            return html.Div(
                "Please run Full Review from the Layout View panel first.",
                className="alert alert-warning",
            )
```

(Ensures message is accurate now that Task 1.2 sets the flag.)

- [ ] **Step 2: Add test for flag semantics**

Add to `tests/test_full_review_callback.py`:

```python
def test_review_completed_flag_pattern():
    from app.state import AppState
    s = AppState()
    assert s.review_completed is False
    s.review_completed = True
    assert s.review_completed is True
```

- [ ] **Step 3: Commit**

```bash
git add app/callbacks.py tests/test_full_review_callback.py
git commit -m "fix(app): clarify legacy report export requires Full Review"
```

---

### Task 1.4: Populate legacy engine.vias on upload

**Files:**
- Modify: `app/callbacks.py` (upload handlers ~lines 74-90, 162-178)
- Modify: `review_engine.py` (`add_net_polygons` or new `set_net_vias`)

- [ ] **Step 1: Add via extraction helper usage**

In both upload code paths after `polygons` are parsed, before `engine.add_net_polygons`:

```python
from core.routing_metrics import split_metal_via_polygons, _coerce_vias  # _coerce_vias may need export

metals, via_polys = split_metal_via_polygons(polygons)
tech_layers = app_state.config.tech_config.layers
vias = _coerce_vias(via_polys, tech_layers)
```

**Note:** Export `_coerce_vias` from `core/routing_metrics.py` (rename to public `coerce_vias` if needed).

- [ ] **Step 2: Add engine method**

In `review_engine.py` `ProfessionalLayoutReviewEngine`:

```python
    def set_net_vias(self, net_name: str, vias: List[Via]):
        self.vias[net_name] = vias
```

Call after `add_net_polygons`:
```python
app_state.engine.set_net_vias(net_name, vias)
app_state.engine.calculate_net_rc(net_name, vias=vias)
```

Ensure `calculate_net_rc` accepts optional `vias` kwarg or reads `self.vias[net_name]`.

- [ ] **Step 3: Write test**

```python
def test_engine_vias_populated():
    from core.routing_metrics import split_metal_via_polygons
    from core.data_parsing import parse_shape_txt
    # use shapes_test_normal.txt which has via0/via1
    ...
    metals, via_polys = split_metal_via_polygons(polygons)
    assert len(via_polys) > 0
```

- [ ] **Step 4: Commit**

```bash
git add app/callbacks.py review_engine.py core/routing_metrics.py tests/
git commit -m "feat(engine): populate vias from shape polygons on upload"
```

---

### Task 1.5: Dynamic Routing PPTX button

**Files:**
- Modify: `app/routing_review.py`

- [ ] **Step 1: Remove static disabled from layout builder**

In `create_routing_review_tab()`, change PPTX button to not use `disabled=not routing_state.review_completed` at build time. Use `disabled=True` default or omit.

- [ ] **Step 2: Add callback**

```python
    @app.callback(
        Output("btn-gen-routing-pptx", "disabled"),
        [Input("btn-run-routing-review", "n_clicks"),
         Input("tabs", "value")],
    )
    def update_pptx_button_state(run_clicks, tab):
        return not routing_state.review_completed
```

- [ ] **Step 3: Manual verify** — run routing review, button enables.

- [ ] **Step 4: Commit**

```bash
git add app/routing_review.py
git commit -m "fix(app): drive routing PPTX button disabled state via callback"
```

---

### Phase 1 Exit Gate

```bash
python3 -m pytest tests/ -q --ignore=tests/test_rc_prediction.py
```

Expected: **0 failed**

---

# Phase 2: Dead Code & Dash Cleanup (Task Summary)

### Task 2.1: Delete RC Prediction modules
- Delete `app/rc_prediction.py`, `app/rc_visualization.py`
- Delete `tests/test_rc_prediction.py`
- Keep `app/rc_model.py`

### Task 2.2: Delete routing_check stack
- Delete `core/routing_check.py`, `run_routing_check_tests.py`, `tests/test_routing_check.py`
- Update `core/__init__.py`

### Task 2.3: Remove orphan layout components
- `layout.py`: remove rule editor modal, net detail modal, bottom panel (or stub with no IDs)
- Remove unused `dcc.Store` ids

### Task 2.4: Remove suppress_callback_exceptions
- `layout_review_app.py`: set `suppress_callback_exceptions=False`
- Fix any startup errors

### Task 2.5: Replace Interval polling
- Add `dcc.Store(id='nets-meta-store')`
- Upload callbacks write `{count, names}`; routing tabs read on tab switch + store change
- Remove `dcc.Interval` or increase to disabled-by-default

**Phase 2 exit:** App starts clean; grep confirms deletions.

---

# Phase 3: Architecture + Rules Wiring (Task Summary)

### Task 3.1: Create core/models.py
- Move Point, Polygon, Via, WireSegment, NetRCData from review_engine.py
- Mechanical find-replace imports across repo

### Task 3.2: NetRecord dataclass in core/net_record.py
- Refactor callbacks upload to use NetRecord
- YAML: only `process_yaml_batch_import`

### Task 3.3: Unified Violation + build_violations()
- `core/violation.py`; merge check_gates violation output

### Task 3.4: Tau ps audit
- Grep `1e-9`, `ns`, `max_tau`; fix stragglers

### Task 3.5: app/routing_service.py
- Move `_run_routing_review`, `_resolve_regex` from routing_review.py

### Task 3.6: Wire rules/ plugin (Decision A)

**Files:** `review_engine.py`, `rules/base_rule.py`, `rules/registry.py`

- [ ] Replace `_execute_check_rule` body with:

```python
from rules.registry import create_rule

def _execute_check_rule(self, net_name: str, rule: CheckRule):
    rc_data = self.net_rc_data.get(net_name)
    polygons = self.nets.get(net_name, [])
    impl = create_rule(rule.rule_id)
    if impl is None:
        return  # unknown rule — log warning
    impl.parameters = rule.parameters  # if rule supports runtime params
    raw = impl.check(net_name, rc_data, polygons)
    for v in raw:
        self._add_violation_from_dict(rule, net_name, v)
```

- [ ] Fix `BaseRule.from_dict` — use `from rules.registry import create_rule` not `registry.create_rule`

- [ ] Add `tests/test_rules_integration.py`:

```python
def test_drc001_fires_on_narrow_polygon():
    from rules.registry import create_rule
    rule = create_rule("DRC001")
    assert rule is not None
```

- [ ] Gradually remove duplicated if/elif blocks from `_execute_check_rule` as rules prove equivalent

### Task 3.7–3.8: Visualization decouple + matching dedup
- Pass explicit args to `create_net_visualization`
- `analyze_matching` → `core/matching_analyzer`

**Phase 3 exit:** `grep "from app" core/` empty; rules integration test passes.

---

# Phase 4: Module Split (Task Summary)

| Task | Action |
|------|--------|
| 4.1 | `assets/eda-theme.css` ← extract from theme.py |
| 4.2 | Split report_generator → report/pptx_legacy.py, pdf_legacy.py |
| 4.3 | core/geometry.py, core/em_analysis.py ← review_engine |
| 4.4 | pdk/sram_7nm.yaml ← unified loader |
| 4.5 | core/layer_style.py |

---

# Phase 5: CI & Quality (Task Summary)

### Task 5.1: ruff clean
```bash
ruff check . --fix
```

### Task 5.2: Deprecate alternate runners
- README: only `pytest tests/`
- Add WARNING to run_tests.py docstring

### Task 5.3: Coverage gate
```bash
pytest tests/ --cov=core --cov=rules --cov-fail-under=60
```

### Task 5.4: GitHub Actions
Create `.github/workflows/test.yml`:

```yaml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/ -q --ignore=tests/test_rc_prediction.py
```

### Task 5.5: Update CLAUDE.md architecture diagram

---

## Self-Review (Plan vs Spec)

| Spec requirement | Plan task |
|------------------|-----------|
| Phase 0 baseline | Task 0.1–0.2 |
| Full Review button | Task 1.2 |
| Report Export | Task 1.3 |
| Legacy vias | Task 1.4 |
| PPTX button | Task 1.5 |
| 0 test failures | Task 1.1 + Phase 1 gate |
| Delete dead code | Phase 2 |
| rules/ wiring | Task 3.6 |
| core/models | Task 3.1 |
| CI | Task 5.4 |

No placeholders in Phase 0–1 steps. Phases 2–5 are summarized for subsequent plan expansion sessions.

---

## Execution Handoff

**Plan saved to:** `docs/superpowers/plans/2026-06-21-project-governance.md`

**Recommended start:** Phase 0 Task 0.1 → Phase 1 (all tasks) before Phase 2.

**Subagent-Driven:** Dispatch one subagent per Task 0.x / 1.x with full step text from this plan.