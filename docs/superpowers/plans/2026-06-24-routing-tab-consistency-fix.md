# Routing Tab Consistency & Thresholds Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix RC value inconsistencies (ensure legacy path for default tau/R/C match with Properties), make Routing Config presets always valid/no-red, implement explicit Locked/Editable mode with reliable Apply and tab persistence, ensure changes visible in Review, and make entire UI 100% professional English with consistent style.

**Architecture:** Two pipelines share nets_data; Routing Review defaults to legacy RC calc (no rc_model unless explicit custom); RoutingState owns is_frozen + get_thresholds(); single _routing_config_ui callback handles mode/preset/thresh/apply + rehydrate on tab switch to Config; Review always reads get_thresholds() and shows source + value/threshold; all UI strings English-only using existing theme.

**Tech Stack:** Python/Dash, dataclasses, pytest, existing theme/assets.

---

### Task 1: Ensure RC default path matches legacy Properties (R/C/tau identical)

**Files:**
- Modify: `app/routing_review.py` (in _run_routing_review)
- Modify: `core/routing_metrics.py` (docstring if needed)
- Test: `tests/test_routing_metrics.py`

- [ ] **Step 1: Update _run_routing_review to force legacy for default**
```python
# In app/routing_review.py around line 607
rc_model_to_use = routing_state.custom_rc_model if routing_state.custom_rc_model else None
# (already mostly there; ensure comment explains "force legacy for Properties match")
```

- [ ] **Step 2: Run existing RC consistency test to baseline**
Run: `python -m pytest tests/test_routing_metrics.py::test_compute_for_net_default_path_matches_legacy_rc -q --tb=short`

Expected: PASS (or note if needs update)

- [ ] **Step 3: Add/enhance full equality test between Properties and Review**
```python
# In tests/test_routing_metrics.py (add if not present)
def test_rc_values_match_between_properties_and_routing_review():
    # Simulate upload + engine RC (like Layout View Properties)
    # ... (use existing _rebuild_engine_from_nets pattern)
    engine_rc = ...  # total_resistance, total_capacitance, tau_rc
    review_m = compute_for_net(..., rc_model=None)
    assert review_m["r_total"] == pytest.approx(engine_rc.total_resistance)
    assert review_m["c_total"] == pytest.approx(engine_rc.total_capacitance)
    assert review_m["effective_tau_ps"] == pytest.approx(engine_rc.tau_rc)
```

- [ ] **Step 4: Run the new test**
Run: `python -m pytest tests/test_routing_metrics.py::test_rc_values_match_between_properties_and_routing_review -q --tb=line`

Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add tests/test_routing_metrics.py app/routing_review.py
git commit -m "test: ensure default RC path in Review matches Properties (R/C/tau)"
```

### Task 2: Make all presets valid + prevent red on import/load

**Files:**
- Modify: `config/routing_thresholds.py` (ensure _BUILTIN_PRESETS valid)
- Modify: `config/presets/*.yaml` (if needed)
- Modify: `app/routing_config.py` (THRESHOLD_FIELDS, load logic)

- [ ] **Step 1: Verify current presets pass validate()**
Run: `python -c "
from config.routing_thresholds import RoutingThresholds, _BUILTIN_PRESETS
from config.preset_loader import load_preset_yaml, list_yaml_presets
for name in _BUILTIN_PRESETS:
    t = RoutingThresholds.for_preset(name)
    t.validate()
    print(name, 'OK')
for name in list_yaml_presets():
    t = load_preset_yaml(name)
    t.validate()
    print(name, 'OK')
print('All presets valid')
"`

Expected: All OK (no exceptions)

- [ ] **Step 2: Update THRESHOLD_FIELDS if any min/max cause false invalid (e.g. allow 0/1 exactly)**
```python
# In app/routing_config.py
THRESHOLD_FIELDS = [
    ("max_h_ratio", "Max H Ratio (WL gate)", "0.0", "1.0", "0.01"),
    ("max_v_ratio", "Max V Ratio (IO gate)", "0.0", "1.0", "0.01"),
    # ... others unchanged
]
```

- [ ] **Step 3: Ensure load/switch paths do not trigger red (use direct state values)**
# (Already in _render_state / rehydrate; add test later)

- [ ] **Step 4: Run preset tests**
Run: `python -m pytest tests/test_routing_thresholds.py tests/test_preset_loader.py -q --tb=no`

Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add config/routing_thresholds.py app/routing_config.py
git commit -m "fix(config): make presets always valid; widen ratio bounds to prevent false red on load"
```

### Task 3: Implement explicit Locked/Editable mode in Config

**Files:**
- Modify: `app/routing_config.py` (create_routing_config_tab + _routing_config_ui)
- Modify: `app/routing_state.py` (if needed for helpers)

- [ ] **Step 1: Add toggle buttons in layout**
```python
# In create_routing_config_tab (after preset dropdown)
html.Div([
    html.Button("Locked", id="mode-locked", className=...),
    html.Button("Editable", id="mode-editable", className=...),
], style={"display": "flex", ...})
```

- [ ] **Step 2: Add mode switch logic in callback**
```python
# In _routing_config_ui
if trigger_id == "mode-locked.n_clicks":
    routing_state.set_frozen_mode(True)
elif trigger_id == "mode-editable.n_clicks":
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(routing_state.thresholds.to_dict())
    routing_state.set_frozen_mode(False)
# then re-render via _render_state
```

- [ ] **Step 3: Wire disabled on inputs based on is_frozen**
```python
# In input creation
disabled = routing_state.is_frozen
```

- [ ] **Step 4: Test mode toggle + disabled**
Run: `python -m pytest tests/test_routing_config_layout.py -q --tb=short -k "mode or locked or editable"`

Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add app/routing_config.py
git commit -m "feat(config): add Locked/Editable toggle with disabled inputs"
```

### Task 4: Fix tab switch re-hydration + Apply persistence

**Files:**
- Modify: `app/routing_config.py`
- Test: `tests/test_routing_config_layout.py`

- [ ] **Step 1: Strengthen tab rehydrate to output all current values + disabled + mode**
```python
# Add/ensure in _routing_config_ui when tab == "tab-routing-config"
thr = routing_state.get_thresholds()
vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
frozen = routing_state.is_frozen
dis_list = _disabled_list(frozen, n_fields)
# output to all thresh-* values + disabled
# output mode button classes
```

- [ ] **Step 2: Make Apply always commit + clear + set mode correctly**
```python
# In apply path
if valid:
    routing_state.custom_thresholds = valid
    routing_state.set_frozen_mode(False)  # or True if locked
    # clear unsaved badge, set status
```

- [ ] **Step 3: Add test for rehydrate + apply persistence across "tab switch"**
```python
# In tests/test_routing_config_layout.py
def test_tab_rehydrate_and_apply_persist():
    # set state, simulate tab, check outputs match, apply, check Review would see it
    ...
```

- [ ] **Step 4: Run the test**
Run: `python -m pytest tests/test_routing_config_layout.py::test_tab_rehydrate_and_apply_persist -q --tb=line`

Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add app/routing_config.py tests/test_routing_config_layout.py
git commit -m "fix(config): reliable tab rehydrate + Apply persistence for thresholds/mode"
```

### Task 5: Ensure Review always reflects applied thresholds + source

**Files:**
- Modify: `app/routing_review.py` (ensure _build_ uses get_thresholds + source)

- [ ] **Step 1: Add/update source banner and value/threshold in cards/table**
```python
# Already has _build_threshold_source and C column; ensure uses
thr = routing_state.get_thresholds()
# for cards: pass threshold= f"{getattr(thr, 'max_c_ff')}"
# table C: f"{m['c_total']:.1f} / {thr.max_c_ff:.1f}"
```

- [ ] **Step 2: Run Review tests**
Run: `python -m pytest tests/test_routing_review.py tests/test_routing_metrics.py -q --tb=no`

Expected: PASS (add if missing assertions for source/threshold display)

- [ ] **Step 3: Commit**
```bash
git add app/routing_review.py
git commit -m "feat(review): always show applied source + value/threshold from state"
```

### Task 6: Full UI English audit + style unification

**Files:**
- Modify: `app/layout.py`, `app/routing_config.py`, `app/routing_review.py`, `app/callbacks.py` (any Chinese strings)

- [ ] **Step 1: Audit and replace any Chinese with English**
```python
# Search for Chinese; replace e.g.
# "冻结" -> "Locked"
# "可编辑" -> "Editable"
# etc. (use professional terms)
```

- [ ] **Step 2: Unify button/card styles**
```python
# Ensure all use same classes from theme, e.g. className="btn btn-primary btn-sm"
```

- [ ] **Step 3: Run full layout/config/review tests**
Run: `python -m pytest tests/test_routing_config_layout.py tests/test_routing_review.py -q --tb=no`

Expected: PASS

- [ ] **Step 4: Manual spot check in code**
Run: `grep -r "[\u4e00-\u9fff]" app/ --include="*.py" || echo "No Chinese found"`

Expected: No output (clean)

- [ ] **Step 5: Commit**
```bash
git add app/*.py
git commit -m "chore(ui): remove all Chinese; unify English + button styles across tabs"
```

### Task 7: Add missing tests + run full suite

**Files:**
- Test updates in existing routing tests

- [ ] **Step 1: Add test for no-red on valid preset load**
```python
def test_no_red_on_valid_preset_load():
    # load preset, render, assert no red classes or "Invalid" in status
```

- [ ] **Step 2: Add test for Locked vs Editable Apply effect in Review**
```python
def test_locked_vs_editable_apply_reflected_in_review():
    # set locked/editable + apply, check review source + gates use correct thr
```

- [ ] **Step 3: Run full relevant test suite**
Run: `python -m pytest tests/ -q -k "routing or threshold or rc or config" --tb=line`

Expected: All PASS (no failures)

- [ ] **Step 4: Commit**
```bash
git add tests/
git commit -m "test: add coverage for no-red, mode apply, English UI"
```

### Task 8: Manual verification + final cleanup

**Files:** (none, or minor docs)

- [ ] **Step 1: Start app and basic smoke**
Run: `./start.sh` (in background if needed) or `python layout_review_app.py`

Expected: App starts at http://localhost:8050 without errors

- [ ] **Step 2: End-to-end manual flows**
- Upload shapes on Layout View → check Properties R/C/tau
- Go to Routing Config → switch presets → no red on valid
- Toggle Locked/Editable → inputs disabled/enabled
- Edit in Editable → Apply → tab switch away/back → values persist
- Run Review → check source banner English, C card/column with /thresh, gates use applied values
- Switch tabs multiple times → no apply失效

- [ ] **Step 3: Run full test suite + lint**
Run: `python -m pytest tests/ -q --tb=no; python -m ruff check .`

Expected: All green

- [ ] **Step 4: Commit any final tweaks**
```bash
git add -u
git commit -m "chore: final manual verification + cleanup"
```

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-24-routing-tab-consistency-fix.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach? (Or any tweaks to the plan first.) 

If Subagent-Driven: next I will start Task 1 with implementer subagent.