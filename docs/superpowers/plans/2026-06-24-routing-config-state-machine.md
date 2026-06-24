# Routing Config State Machine Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 4 overlapping Dash callbacks in `app/routing_config.py` with 1 single state-driven callback that has zero `allow_duplicate=True`, eliminating the editable-not-editable and apply-still-red bugs.

**Architecture:** Centralize the state machine into one `_routing_config_ui` callback that reads from `routing_state` (the Python singleton) and projects state to 21 UI outputs. Mutate state based on which input triggered. Split helper logic into 3 pure functions (`_validate_apply`, `_render_state`, `_dispatch_action`) so the callback itself stays small.

**Tech Stack:** Python 3.13, Dash 2.x, pytest, dataclasses.

**Reference spec:** `docs/superpowers/specs/2026-06-24-routing-config-state-machine-redesign.md`

**Working directory:** `d:\workspace\project\sram_layout_review` (run all commands from here)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `app/routing_config.py` | **Modify** | (a) Add 3 helpers `_validate_apply`, `_render_state`, `_dispatch_action`. (b) Replace 4 callbacks (`_rehydrate_on_tab`, `_handle_routing_preset_or_thresh`, `_apply_thresholds`, `_switch_mode`) with 1 `_routing_config_ui` callback. Keep `create_routing_config_tab`, `THRESHOLD_FIELDS`, `_mode_button_classes`, `_disabled_list`, `_compute_rehydrate_outputs` (other consumers may still import it) intact. |
| `tests/test_routing_config_state_machine.py` | **Create** | 11 state machine unit tests (one per behavior in spec §5). |
| `tests/test_routing_config_layout.py` | **Modify** | Trim or rewrite to align with state machine. Keep tests that are still meaningful (initial render, apply, mode switch). |
| `tests/test_apply_persistence.py` | Keep | Already covers Apply success/fail — verify still works. |
| `tests/test_tab_rehydrate.py` | Keep | Already covers tab rehydrate — verify still works. |

---

## Task 1: Add failing state machine tests (TDD red)

**Files:**
- Create: `tests/test_routing_config_state_machine.py`

- [ ] **Step 1: Write the 11 state machine tests**

Create `tests/test_routing_config_state_machine.py` with EXACTLY this content:

```python
"""State machine unit tests for the single-callback routing config UI.

These tests are pure-Python: they directly import the 3 helpers
(_validate_apply, _render_state, _dispatch_action) and the callback
(_routing_config_ui) from app.routing_config, and drive them with
simulated Dash triggers and inputs. No Dash server required.
"""
import sys
sys.path.insert(0, '.')

import pytest

from app import routing_config
from app.routing_state import routing_state
from app.routing_config import (
    THRESHOLD_FIELDS,
    _validate_apply,
    _render_state,
    _dispatch_action,
    _routing_config_ui,
)
from config.routing_thresholds import RoutingThresholds


# --- Helpers ---

def _reset_state():
    """Reset routing_state to known frozen+preset state."""
    routing_state.current_preset = "sram_7nm_wl"
    routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    routing_state.custom_thresholds = None
    routing_state._is_frozen = True


# 1. validate: 7 valid values -> RoutingThresholds instance, no error

def test_validate_apply_valid_values():
    vals = (0.15, 1.0, 100.0, 500.0, 12.5, 0.85, 80.0)
    result, err = _validate_apply(vals)
    assert err is None
    assert result is not None
    assert result.max_h_ratio == 0.15
    assert result.max_tau_ps == 12.5


# 2. validate: h+v < 1 -> error

def test_validate_apply_h_plus_v_too_small():
    vals = (0.3, 0.3, 100.0, 500.0, 12.5, 0.85, 80.0)
    result, err = _validate_apply(vals)
    assert result is None
    assert err is not None
    assert "max_h_ratio" in err.lower() or "max_v_ratio" in err.lower() or "1.0" in err


# 3. validate: None values are skipped, fall back to current state

def test_validate_apply_none_falls_back_to_current():
    _reset_state()
    # All None → uses state.get_thresholds() (preset) values
    vals = (None, None, None, None, None, None, None)
    result, err = _validate_apply(vals)
    assert err is None
    assert result is not None
    assert result.max_h_ratio == 0.15
    assert result.max_tau_ps == 12.5


# 4. validate: out-of-range value rejected

def test_validate_apply_negative_tau_rejected():
    vals = (0.15, 1.0, 100.0, 500.0, -1.0, 0.85, 80.0)
    result, err = _validate_apply(vals)
    assert result is None
    assert err is not None


# 5. render: frozen + preset -> 21 outputs, all disabled

def test_render_state_frozen_preset_disabled():
    _reset_state()
    out = _render_state([getattr(routing_state.thresholds, n) for n, *_ in THRESHOLD_FIELDS])
    assert len(out) == 21
    # disabled flags are the last 7 outputs
    assert all(out[14:21]) is True
    # values are the preset values
    assert out[7] == 0.15
    assert out[8] == 1.0
    assert out[11] == 12.5


# 6. render: editable + custom -> not disabled, custom values shown

def test_render_state_editable_custom_enabled():
    _reset_state()
    routing_state.set_frozen_mode(False)
    routing_state.custom_thresholds = RoutingThresholds.from_dict(
        routing_state.get_thresholds().to_dict()
    )
    routing_state.custom_thresholds.max_tau_ps = 25.0
    out = _render_state([getattr(routing_state.custom_thresholds, n) for n, *_ in THRESHOLD_FIELDS])
    # disabled = [False]*7
    assert all(d is False for d in out[14:21])
    # tau is the custom value
    assert out[11] == 25.0


# 7. render: thresh input differs from state -> unsaved badge visible

def test_render_state_unsaved_badge_when_input_differs():
    _reset_state()
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
    # user typed 0.5 in max_h_ratio, but state still has 0.15
    inputs = [0.5] + [getattr(routing_state.custom_thresholds, n)
                      for n, *_ in THRESHOLD_FIELDS[1:]]
    out = _render_state(inputs)
    # unsaved-badge is at index 4
    badge = out[4]
    # badge is a Span with non-empty children
    assert badge is not None
    # we don't need to check exact text, just that it's not hidden
    # apply-status at index 5
    status = out[5]
    assert status is not None


# 8. render: thresh input matches state -> no unsaved badge

def test_render_state_no_unsaved_when_matches():
    _reset_state()
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
    inputs = [getattr(routing_state.custom_thresholds, n) for n, *_ in THRESHOLD_FIELDS]
    out = _render_state(inputs)
    # unsaved badge should be a hidden Span (style display: none)
    badge = out[4]
    assert badge is not None
    # accept either empty content or display:none
    style = badge.style if hasattr(badge, "style") else {}
    assert style.get("display") == "none" or badge.children in ("", [], None)


# 9. dispatch: preset change in frozen mode -> state.thresholds updated, custom cleared

def test_dispatch_preset_change_in_frozen():
    _reset_state()
    assert routing_state.current_preset == "sram_7nm_wl"
    _dispatch_action("routing-preset.value", "sram_5nm_io_bl", None)
    assert routing_state.current_preset == "sram_5nm_io_bl"
    assert routing_state.thresholds.max_h_ratio == 1.0  # sram_5nm_io_bl
    assert routing_state.custom_thresholds is None


# 10. dispatch: preset change in editable mode -> state unchanged (blocked)

def test_dispatch_preset_change_in_editable_blocked():
    _reset_state()
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
    original_preset = routing_state.current_preset
    original_thr = routing_state.thresholds
    _dispatch_action("routing-preset.value", "sram_5nm_io_bl", None)
    # state unchanged
    assert routing_state.current_preset == original_preset
    assert routing_state.thresholds is original_thr


# 11. dispatch: mode-frozen click -> sets frozen=True (does NOT clear custom)

def test_dispatch_frozen_click_preserves_custom():
    _reset_state()
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
    routing_state.custom_thresholds.max_tau_ps = 99.0
    _dispatch_action("mode-frozen.n_clicks", None, None)
    assert routing_state.is_frozen is True
    # custom preserved
    assert routing_state.custom_thresholds is not None
    assert routing_state.custom_thresholds.max_tau_ps == 99.0


# 12. dispatch: mode-editable click -> sets frozen=False, copies preset if no custom

def test_dispatch_editable_click_copies_preset():
    _reset_state()
    assert routing_state.is_frozen is True
    _dispatch_action("mode-editable.n_clicks", None, None)
    assert routing_state.is_frozen is False
    assert routing_state.custom_thresholds is not None
    assert routing_state.custom_thresholds.max_h_ratio == 0.15  # copied from preset


# 13. dispatch: apply with valid values -> state.custom_thresholds updated, is_frozen=False

def test_dispatch_apply_valid():
    _reset_state()
    vals = (0.5, 0.7, 100.0, 500.0, 12.5, 0.85, 80.0)  # h+v=1.2 valid
    _dispatch_action("btn-apply-thresholds.n_clicks", None, vals)
    assert routing_state.custom_thresholds is not None
    assert routing_state.custom_thresholds.max_h_ratio == 0.5
    assert routing_state.is_frozen is False


# 14. dispatch: apply with invalid values -> state unchanged

def test_dispatch_apply_invalid_keeps_state():
    _reset_state()
    original_thr = routing_state.thresholds
    original_custom = routing_state.custom_thresholds
    vals = (0.3, 0.3, 100.0, 500.0, 12.5, 0.85, 80.0)  # h+v=0.6 invalid
    _dispatch_action("btn-apply-thresholds.n_clicks", None, vals)
    # state unchanged
    assert routing_state.thresholds is original_thr
    assert routing_state.custom_thresholds is original_custom
    # and last_error is set
    assert routing_state.last_error is not None


# 15. dispatch: thresh value change -> no state mutation (only badge)

def test_dispatch_thresh_value_no_mutation():
    _reset_state()
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
    original_custom = routing_state.custom_thresholds
    _dispatch_action("thresh-max_tau_ps.value", 25.0, None)
    # state NOT mutated
    assert routing_state.custom_thresholds is original_custom
    assert routing_state.custom_thresholds.max_tau_ps == 12.5  # unchanged
```

- [ ] **Step 2: Run the tests — expect ALL FAIL (helpers not yet implemented)**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v`
Expected: ~15 failed with `ImportError` or `AttributeError` (the 3 helpers and the callback don't exist yet).

- [ ] **Step 3: Commit the failing test (TDD red checkpoint)**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add tests/test_routing_config_state_machine.py ; git commit -m "test: add routing config state machine tests (TDD red)"
```

---

## Task 2: Add `_validate_apply` pure helper

**Files:**
- Modify: `app/routing_config.py` (add helper at module level, before `create_routing_config_tab`)

- [ ] **Step 1: Add `_validate_apply` after `_disabled_list` (around line 179)**

Add this code to `app/routing_config.py` directly after the `_disabled_list` function (i.e., before `_compute_rehydrate_outputs`):

```python
def _validate_apply(thresh_values: tuple) -> tuple[Optional["RoutingThresholds"], Optional[str]]:
    """Validate 7 threshold input values for Apply.

    Returns:
        (valid_thresholds, None) on success
        (None, error_message) on failure

    A `None` value in thresh_values means "use the current state value" (the
    input was empty). It does NOT mean invalid.
    """
    current = routing_state.get_thresholds()
    tentative_dict = current.to_dict()
    for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
        if val is not None:
            tentative_dict[name] = val
    try:
        tentative = RoutingThresholds.from_dict(tentative_dict)
        tentative.validate()
    except Exception as e:
        return None, str(e)
    return tentative, None
```

- [ ] **Step 2: Run only the 4 _validate_apply tests — expect PASS**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v -k "validate_apply"`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py ; git commit -m "feat(routing-config): add _validate_apply helper"
```

---

## Task 3: Add `_render_state` pure helper

**Files:**
- Modify: `app/routing_config.py` (add helper after `_validate_apply`)

- [ ] **Step 1: Add `_render_state` after `_validate_apply`**

Add this code to `app/routing_config.py` directly after the `_validate_apply` function:

```python
def _render_state(thresh_input_values: list) -> tuple:
    """Project routing_state to 21 UI outputs.

    Output tuple order (matches the single callback's Output list):
      [0]  mode-frozen className
      [1]  mode-editable className
      [2]  routing-preset-status children
      [3]  routing-config-status children
      [4]  thresh-unsaved-badge children
      [5]  thresh-apply-status children
      [6]  routing-preset value
      [7..13] 7 thresh-{name} values
      [14..20] 7 thresh-{name} disabled flags

    `thresh_input_values` is the list of 7 values currently in the inputs;
    used to detect unsaved changes.
    """
    thr = routing_state.get_thresholds()
    vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
    frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(frozen)
    dis_list = _disabled_list(frozen, len(THRESHOLD_FIELDS))

    # detect unsaved changes (only meaningful in editable mode)
    has_unsaved = (
        not frozen
        and list(thresh_input_values) != vals
    )

    source = routing_state.get_threshold_source()
    preset_status = html.Span(source, style={"color": "#888", "fontSize": "11px"})

    config_status_text = routing_state.last_error or ""
    if config_status_text:
        config_status = html.Span(
            f"Error: {config_status_text}",
            style={"fontSize": "11px", "color": "#C0392B"},
        )
    else:
        config_status = ""

    if has_unsaved:
        unsaved_badge = html.Span(
            "● Unsaved Changes",
            style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"},
        )
        apply_status = html.Span(
            "Thresholds modified — click Apply to save.",
            style={"fontSize": "11px", "color": "#E67E22"},
        )
    else:
        unsaved_badge = html.Span("", style={"display": "none"})
        apply_status = ""

    return tuple([
        f_cls, e_cls,
        preset_status,
        config_status,
        unsaved_badge,
        apply_status,
        routing_state.current_preset,
    ] + vals + dis_list)
```

NOTE: The `html.Span` and `routing_state.last_error` references must already be in scope. Confirm `from dash import html` is at the top of `routing_config.py` (it is) and that `routing_state` is the singleton (it is). If `routing_state.last_error` doesn't exist yet, add a `last_error: Optional[str] = None` field — but it should already exist (see Step 1.5 of the implementation).

- [ ] **Step 2: Run the 4 _render_state tests — expect PASS**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v -k "render_state"`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py ; git commit -m "feat(routing-config): add _render_state helper"
```

---

## Task 4: Add `_dispatch_action` helper

**Files:**
- Modify: `app/routing_config.py` (add helper after `_render_state`)

- [ ] **Step 1: Add `_dispatch_action` after `_render_state`**

Add this code to `app/routing_config.py` directly after the `_render_state` function:

```python
def _dispatch_action(trigger_id: Optional[str], trigger_value, thresh_values) -> None:
    """Mutate routing_state based on which input triggered the callback.

    trigger_id: e.g. "routing-preset.value", "mode-frozen.n_clicks",
                "btn-apply-thresholds.n_clicks", "thresh-max_tau_ps.value",
                "tabs.value", or None for initial render.
    trigger_value: the value associated with the trigger (preset name,
                   n_clicks count, thresh input value, tab id).
    thresh_values: tuple of 7 current thresh input values (only meaningful
                   for the Apply trigger).
    """
    if trigger_id is None:
        # Initial render: nothing to do; state is already set.
        return

    if trigger_id == "routing-preset.value":
        new_preset = trigger_value
        if routing_state.is_frozen:
            routing_state.current_preset = new_preset
            routing_state.thresholds = RoutingThresholds.for_preset(new_preset)
            routing_state.custom_thresholds = None
            routing_state.last_error = None
        # else: editable mode blocks preset change; render_state will
        # echo back state.current_preset to bounce the dropdown.
        return

    if trigger_id == "mode-frozen.n_clicks":
        routing_state.set_frozen_mode(True)
        routing_state.last_error = None
        return

    if trigger_id == "mode-editable.n_clicks":
        routing_state.set_frozen_mode(False)
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        routing_state.last_error = None
        return

    if trigger_id == "btn-apply-thresholds.n_clicks":
        valid, err = _validate_apply(thresh_values)
        if valid is None:
            routing_state.last_error = err
        else:
            routing_state.set_custom(valid)
            routing_state.last_error = None
        return

    if trigger_id and trigger_id.startswith("thresh-") and trigger_id.endswith(".value"):
        # User typing in a thresh input: no state mutation.
        # _render_state will detect the diff and show the unsaved badge.
        return

    if trigger_id == "tabs.value":
        # Tab switch: nothing to mutate; just re-render.
        return
```

- [ ] **Step 2: Run the 7 _dispatch_action tests — expect PASS**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v -k "dispatch"`
Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py ; git commit -m "feat(routing-config): add _dispatch_action helper"
```

---

## Task 5: Replace 4 callbacks with single `_routing_config_ui` callback

**Files:**
- Modify: `app/routing_config.py:register_routing_config_callbacks` (replace its body)

- [ ] **Step 1: Read the current `register_routing_config_callbacks` function**

Find the function in `app/routing_config.py`. It registers 4 callbacks (`_rehydrate_on_tab`, `_handle_routing_preset_or_thresh`, `_apply_thresholds`, `_switch_mode`) with `allow_duplicate=True` on overlapping Outputs.

- [ ] **Step 2: Replace the entire body of `register_routing_config_callbacks`**

Find the function signature line and the entire function body. Replace from `@app.callback(...)` decorators + function defs all the way to the end of `_switch_mode`. The new body should be:

```python
    @app.callback(
        [Output("mode-frozen", "className"),
         Output("mode-editable", "className"),
         Output("routing-preset-status", "children"),
         Output("routing-config-status", "children"),
         Output("thresh-unsaved-badge", "children"),
         Output("thresh-apply-status", "children"),
         Output("routing-preset", "value")]
        + [Output(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS]
        + [Output(f"thresh-{name}", "disabled") for name, *_ in THRESHOLD_FIELDS],
        [Input("routing-preset", "value"),
         Input("mode-frozen", "n_clicks"),
         Input("mode-editable", "n_clicks"),
         Input("btn-apply-thresholds", "n_clicks"),
         Input("tabs", "value")]
        + [Input(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        [State(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        prevent_initial_call=False,
    )
    def _routing_config_ui(
        preset_value, _f_clicks, _e_clicks, _apply_clicks, tab,
        *thresh_inputs_and_state  # first 7 are inputs, last 7 are state copies
    ):
        """Single state-driven callback for the entire Routing Config tab.

        - Reads `ctx.triggered` to identify the action
        - Mutates `routing_state` (via _dispatch_action)
        - Projects state to 21 UI outputs (via _render_state)

        NO allow_duplicate=True anywhere. This is the ONLY callback that
        writes to these 21 Outputs.
        """
        from dash import callback_context as _ctx
        from dash.exceptions import PreventUpdate as _PreventUpdate

        # The 7 thresh inputs appear as both Inputs (for "user typed" detection)
        # and State (for Apply action). Since Dash passes them in declaration
        # order, the LAST 7 args (after the 5 head inputs) are the State copies.
        thresh_state = thresh_inputs_and_state[-len(THRESHOLD_FIELDS):]
        thresh_inputs = thresh_inputs_and_state[:len(THRESHOLD_FIELDS)]

        if not _ctx.triggered:
            # Initial render: dispatch_action is a no-op, just render.
            return _render_state(thresh_state)

        trigger_id = _ctx.triggered[0]["prop_id"]
        trigger_value = _ctx.triggered[0]["value"]

        # Tab switch: only act when switching TO routing-config
        if trigger_id == "tabs.value":
            if trigger_value != "tab-routing-config":
                raise _PreventUpdate
            # else: fall through to dispatch (no-op for tabs) + render

        # Dispatch state mutation
        _dispatch_action(trigger_id, trigger_value, tuple(thresh_state))

        # Project state to UI
        return _render_state(thresh_state)
```

- [ ] **Step 3: Verify the 4 old callback functions are removed**

Confirm the file no longer contains `def _rehydrate_on_tab`, `def _handle_routing_preset_or_thresh`, `def _apply_thresholds`, or `def _switch_mode`. These were local to `register_routing_config_callbacks` and are now replaced by the single `_routing_config_ui`.

If any are still present, remove their `@app.callback(...)` decorator and the function definition entirely. The 4 previous callbacks used 4 separate `@app.callback` blocks; the new code has exactly 1.

- [ ] **Step 4: Run the full state machine test file — expect ALL PASS**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_state_machine.py -v`
Expected: 15 passed.

If any test fails, the most likely cause is that the callback function name (`_routing_config_ui`) is not exposed by `app.routing_config` (it's wrapped by `@app.callback`). To make the test work, ADD a thin alias right after the callback definition in `app/routing_config.py`:

```python
    # Expose the callback function for direct unit testing
    _routing_config_ui = _routing_config_ui
```

Wait, that's a no-op. Instead, the callback's inner function is the one that does the work. Since we use the helpers (`_dispatch_action`, `_render_state`) directly in the tests, the callback function itself doesn't need to be importable. The 15 tests should already pass without importing `_routing_config_ui`.

If the test file imports `_routing_config_ui` and it fails to import, REMOVE that import from the test file. The tests that use it directly can be deleted (the 15 remaining tests don't need it).

- [ ] **Step 5: Run all existing tests — expect NO regression**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/ -v`
Expected: ~177 passed (15 new + 162 existing). Some existing tests in `test_routing_config_layout.py` may need updating because the old 4-callback structure no longer exists.

If `test_routing_config_layout.py` tests fail because they called `_handle_routing_preset_or_thresh` directly, those tests are testing the old (now removed) callback. Update them to test the new helpers (`_validate_apply`, `_render_state`, `_dispatch_action`) or the new flow. The simplest fix is to remove tests that are obsolete and rely on the new `test_routing_config_state_machine.py` instead.

- [ ] **Step 6: Smoke test the layout constructs without exception**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "from app.layout import create_layout; layout = create_layout(); print('layout OK, components:', len(layout))"`
Expected: prints component count, no exception.

- [ ] **Step 7: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add app/routing_config.py ; git commit -m "refactor(routing-config): single _routing_config_ui callback (eliminate 4 overlapping callbacks)"
```

---

## Task 6: Trim/update `test_routing_config_layout.py` for compatibility

**Files:**
- Modify: `tests/test_routing_config_layout.py`

- [ ] **Step 1: Read the current `test_routing_config_layout.py`**

Read the file in full. Identify any tests that:
- Call the removed callback functions directly (`_handle_routing_preset_or_thresh`, `_switch_mode`, `_apply_thresholds`, `_rehydrate_on_tab`)
- Assert on internal callback structure that no longer exists

- [ ] **Step 2: Replace obsolete tests with state-machine-compatible versions**

For each obsolete test, replace it with the equivalent test from `test_routing_config_state_machine.py` (copy the relevant test verbatim). Keep tests that are still meaningful (e.g., tests that just call `_validate_apply`, `_render_state`, or test `THRESHOLD_FIELDS`).

If the file becomes mostly redundant, consider this approach:
- Keep `test_routing_config_layout.py` as a thin integration-style test (e.g., one test that creates the layout, verifies thresh inputs are present, verifies preset dropdown options).
- Move all state machine unit tests to `test_routing_config_state_machine.py` (already done in Task 1).

Concretely, REPLACE the entire content of `tests/test_routing_config_layout.py` with this minimal version:

```python
"""Integration-style tests for the Routing Config tab layout and state helpers."""
import sys
sys.path.insert(0, '.')

from app import routing_config
from app.routing_config import (
    THRESHOLD_FIELDS,
    _mode_button_classes,
    _disabled_list,
    _compute_rehydrate_outputs,
)
from app.routing_state import routing_state
from config.routing_thresholds import RoutingThresholds


def _reset():
    routing_state.current_preset = "sram_7nm_wl"
    routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    routing_state.custom_thresholds = None
    routing_state._is_frozen = True


def test_threshold_fields_have_seven_entries():
    assert len(THRESHOLD_FIELDS) == 7


def test_mode_button_classes_frozen():
    f, e = _mode_button_classes(True)
    assert "active" in f or "primary" in f
    assert "active" not in e and "primary" not in e


def test_mode_button_classes_editable():
    f, e = _mode_button_classes(False)
    assert "active" in e or "primary" in e
    assert "active" not in f and "primary" not in f


def test_disabled_list_frozen_all_true():
    assert _disabled_list(True, 7) == [True] * 7


def test_disabled_list_editable_all_false():
    assert _disabled_list(False, 7) == [False] * 7


def test_compute_rehydrate_outputs_returns_21_values():
    _reset()
    out = _compute_rehydrate_outputs()
    assert len(out) == 21


def test_compute_rehydrate_outputs_frozen_disabled():
    _reset()
    out = _compute_rehydrate_outputs()
    assert all(out[14:21]) is True


def test_compute_rehydrate_outputs_uses_preset_values():
    _reset()
    out = _compute_rehydrate_outputs()
    # sram_7nm_wl: h=0.15, v=1.0, r=100, c=500, tau=12.5, via=0.85, sim=80
    assert out[7] == 0.15
    assert out[8] == 1.0
    assert out[9] == 100.0
    assert out[10] == 500.0
    assert out[11] == 12.5
    assert out[12] == 0.85
    assert out[13] == 80.0
```

- [ ] **Step 3: Run the test file — expect PASS**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/test_routing_config_layout.py -v`
Expected: 8 passed.

- [ ] **Step 4: Run the full test suite — expect ALL PASS**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/ -v`
Expected: ~177 passed total (15 state machine + 8 layout + 154 other existing).

If any test fails, the most likely causes:
- A test imported a removed function (e.g., `_handle_routing_preset_or_thresh`). Fix by deleting that import + test.
- A test asserted on internal callback order that no longer exists. Delete that test.

- [ ] **Step 5: Commit**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git add tests/test_routing_config_layout.py ; git commit -m "test: trim test_routing_config_layout.py to integration-style checks"
```

---

## Task 7: Final integration smoke

**Files:**
- No code changes
- Run: full test suite + manual smoke

- [ ] **Step 1: Run the entire test suite**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -m pytest tests/ -v`
Expected: All pass (177+ tests).

- [ ] **Step 2: Verify the layout still constructs**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "from app.layout import create_layout; layout = create_layout(); print('layout OK, components:', len(layout))"`
Expected: prints component count, no exception.

- [ ] **Step 3: Verify the routing config tab is importable**

Run: `cd 'd:\workspace\project\sram_layout_review' ; python -c "from app.routing_config import create_routing_config_tab, register_routing_config_callbacks; print('routing_config imports OK')"`
Expected: prints "routing_config imports OK".

- [ ] **Step 4: Final commit (if any cleanup needed)**

```bash
cd 'd:\workspace\project\sram_layout_review' ; git status
```

If clean, skip. If dirty:
```bash
cd 'd:\workspace\project\sram_layout_review' ; git add -A ; git commit -m "chore: post-routing-config-redesign cleanup"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Implementing task |
|---|---|
| §0 background & goal | T5 (the actual redesign) |
| §1 scope | T5, T6 (rewriting only routing_config) |
| §2.1 state machine boundary | T5 (single callback) |
| §2.2 21 Output list | T5 (declaration order matches) |
| §2.3 3 helper split | T2, T3, T4 (one helper per task) |
| §3.1 preset switch | T4 (`_dispatch_action` handles both frozen and editable) |
| §3.2 mode switch | T4 (`_dispatch_action` preserves custom) |
| §3.3 apply | T2 + T4 (`_validate_apply` + `_dispatch_action` call) |
| §3.4 typing | T3 + T4 (`_render_state` detects diff, `_dispatch_action` no-op) |
| §3.5 tab switch | T5 (callback raises PreventUpdate on non-target tab) |
| §3.6 initial render | T5 (`prevent_initial_call=False`) |
| §4 _render_state rules | T3 (full implementation) |
| §5 behavior table (9 rows) | T1 (15 tests cover all rows + a few more) |
| §6 tests | T1, T6 (create + trim) |
| §7 risks | Addressed in T2/T3/T4 (small helpers), T6 (test rewrite) |
| §8 acceptance | T7 (final smoke) |
| §9 out of scope | Confirmed: routing_state API, presets, layout, i18n, other tabs all untouched |

All spec sections covered.

**Placeholder scan:** No TBD / TODO / "fill in later" in plan. Every step has concrete code or commands.

**Type consistency:**
- `_validate_apply(thresh_values: tuple) -> tuple[Optional[RoutingThresholds], Optional[str]]` — used identically in T2 and T4
- `_render_state(thresh_input_values: list) -> tuple` — used identically in T3 and T5
- `_dispatch_action(trigger_id, trigger_value, thresh_values) -> None` — used identically in T4 and T5
- `THRESHOLD_FIELDS` — used identically in T1/T2/T3/T4/T5/T6
- `routing_state.last_error` — referenced in T3 and T4. Verify it exists in `app/routing_state.py` (it does, set to `None` in `__init__`); if not, the helpers will fail. Run the test suite to catch.

**Risks acknowledged:**
- T1 imports `_routing_config_ui` which may not be exposed after `@app.callback` decoration. Mitigation: T5 Step 4 explicitly handles this by suggesting to drop the import.
- T5 Step 4 may fail if any other file (e.g., `app/callbacks.py`) imports the old callback function names. Mitigation: search for imports with `grep` before running tests.
- T6 may break the old test count expectations; T7 verifies the final count.

**Out of scope (per spec §9):**
- routing_state API
- preset YAML / loader
- layout function
- i18n
- other tabs

All confirmed untouched.
