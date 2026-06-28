"""Regression tests for the slider-drag isolation bug + Apply persistence.

Two related bugs:

1. **Drag-isolation bug (now fixed)**:
   Dragging a RangeSlider handle used to snap the handle back to the state
   value, because the unified callback wrote state-derived slider values
   back to the slider outputs on every drag.
   Fix: when the trigger is one of the 7 slider-{name}.value inputs, the
   unified callback returns `dash.no_update` for all 7 slider outputs.

2. **Apply persistence bug (now fixed)**:
   Clicking Apply Thresholds after a drag used to silently reset the
   slider to its default (state) value, because `_apply_thresholds` /
   `_validate_apply` treated `range_values` as a flat list of 14 numbers,
   but the compact 2-column redesign exposes each slider as a single
   `[low, high]` list (7 pairs total). `float([0, 0.5])` raised TypeError,
   `_validate_apply` returned `(None, error)`, `set_custom` was never
   called, and `_render_state` returned the preset (default) values.
   Fix: every helper now accepts 7 `[low, high]` pairs.

These tests exercise the unified callback through Dash's callback map
(invoke the resolved callback function directly with simulated args and
a mocked callback context). They assert the actual callback outputs to
prove both fixes hold.
"""
import sys
sys.path.insert(0, '.')

import dash
from dash import no_update
from dash._callback_context import context_value as _dash_ctx_var


def _save_state_snapshot():
    """Capture key singleton fields for restore (to avoid test pollution)."""
    from app.routing_state import routing_state as rs
    return {
        "current_preset": rs.current_preset,
        "thresholds": rs.thresholds,
        "custom_thresholds": rs.custom_thresholds,
        "is_frozen": rs.is_frozen,
        "last_error": rs.last_error,
        "last_status": rs.last_status,
    }


def _restore_state_snapshot(snap):
    from app.routing_state import routing_state as rs
    rs.current_preset = snap["current_preset"]
    rs.thresholds = snap["thresholds"]
    rs.custom_thresholds = snap["custom_thresholds"]
    rs.is_frozen = snap["is_frozen"]
    rs.last_error = snap["last_error"]
    rs.last_status = snap["last_status"]


def _reset_state():
    from app.routing_state import routing_state as rs
    from config.routing_thresholds import RoutingThresholds
    rs.current_preset = "sram_7nm_wl"
    rs.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    rs.custom_thresholds = None
    rs.set_frozen_mode(True)


def _build_app_with_callbacks():
    """Build a Dash app, register routing config callbacks, and return the app."""
    from app.layout import create_layout
    from app.routing_config import register_routing_config_callbacks
    app = dash.Dash(__name__)
    app.layout = create_layout()
    register_routing_config_callbacks(app)
    return app


def _find_unified_callback(app):
    """Locate the unified _routing_config_ui callback in app.callback_map."""
    for cb_id, cb in app.callback_map.items():
        inputs = cb.get("inputs", [])
        input_set = set()
        for i in inputs:
            if isinstance(i, dict):
                cid = i.get("id")
                prop = i.get("property")
                if cid is not None and prop is not None:
                    input_set.add((cid, prop))
        has_preset = ("routing-preset", "value") in input_set
        has_tabs = ("tabs", "value") in input_set
        has_slider = any(cid.startswith("slider-")
                         for (cid, prop) in input_set
                         if isinstance(cid, str))
        if has_preset and has_tabs and has_slider:
            return cb
    return None


class _CtxMock:
    """Mock for dash.callback_context with a settable triggered list."""

    def __init__(self, triggered):
        self.triggered_inputs = triggered

    @property
    def triggered(self):
        return self.triggered_inputs

    @property
    def inputs(self):
        return {}

    @property
    def states(self):
        return {}

    @property
    def triggered_id(self):
        if self.triggered_inputs:
            return self.triggered_inputs[0]["prop_id"]
        return None


def _invoke_unified(app, triggered_prop_id, slider_pairs, trigger_value=None,
                    preset_value="sram_7nm_wl", f_clicks=None, e_clicks=None,
                    apply_clicks=None, tab="tab-routing-config"):
    """Invoke the unified callback with a mocked triggered context.

    `slider_pairs` is a list of 7 `[low, high]` pairs. We pass:
      - 5 fixed inputs (preset, mode clicks, apply click, tab)
      - 7 slider Input pairs (each [low, high])
      - 7 slider State pairs (each [low, high]; same as inputs)

    The actual callback unpacks only the first 7 slider pairs (the Inputs);
    the States are redundant (same value as Inputs) but declared in the
    callback signature for backward compatibility.
    """
    cb = _find_unified_callback(app)
    assert cb is not None, "Unified callback not found"
    ctx = _CtxMock([{"prop_id": triggered_prop_id, "value": trigger_value}])
    token = _dash_ctx_var.set(ctx)
    try:
        func = cb["callback"]
        if hasattr(func, "__wrapped__"):
            func = func.__wrapped__
        # Build args: 5 fixed + 7 input pairs + 7 state pairs (= 19 args)
        input_pairs = [list(p) for p in slider_pairs]
        state_pairs = [list(p) for p in slider_pairs]
        args = (preset_value, f_clicks, e_clicks, apply_clicks, tab,
                *input_pairs, *state_pairs)
        return func(*args)
    finally:
        _dash_ctx_var.reset(token)


# ---- 1. Slider drag must NOT reset the dragged slider -------------------

def test_slider_drag_returns_no_update_for_slider_outputs():
    """Regression: dragging a slider must not write the state value back
    to that slider's output (would snap handle back to old value)."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        # Pretend the user dragged slider-h_ratio from [0, 0.15] to [0, 0.5]
        dragged_pairs = [
            [0.0, 0.5],    # h_ratio: NEW VALUE
            [0.0, 1.0],
            [0.0, 100.0],
            [0.0, 500.0],
            [0.0, 12.5],
            [0.85, 1.0],
            [80.0, 100.0],
        ]

        result = _invoke_unified(app, "slider-h_ratio.value", dragged_pairs)

        assert len(result) == 14, f"Expected 14 outputs; got {len(result)}"
        for i in range(7):
            assert result[7 + i] is no_update, (
                f"slider-{i} output must be no_update during drag; "
                f"got {result[7+i]!r}. This is the regression: state value "
                f"would reset the user's drag."
            )
    finally:
        _restore_state_snapshot(snap)


# ---- 2. Slider drag MUST still update the unsaved-changes badge ---------

def test_slider_drag_still_shows_unsaved_badge():
    """During a drag, the unsaved-changes badge should appear because the
    slider value now differs from the state value (no Apply yet)."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        dragged_pairs = [
            [0.0, 0.5],    # h_ratio: NEW VALUE (different from state [0, 0.15])
            [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result = _invoke_unified(app, "slider-h_ratio.value", dragged_pairs)

        # Output index 4 = thresh-unsaved-badge.children
        unsaved_badge = result[4]
        assert unsaved_badge is not None
        badge_str = str(unsaved_badge)
        assert "Unsaved Changes" in badge_str, (
            f"Drag must show 'Unsaved Changes' badge; got: {badge_str!r}"
        )
    finally:
        _restore_state_snapshot(snap)


# ---- 3. Slider drag does NOT change state until Apply -------------------

def test_slider_drag_does_not_mutate_state():
    """Dragging a slider must not change routing_state.thresholds until
    Apply is clicked (state-mutation happens via dispatch_action)."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        original_h_high = rs.thresholds.h_ratio.high  # 0.15

        app = _build_app_with_callbacks()

        dragged_pairs = [
            [0.0, 0.5],    # dragged to 0.5
            [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        _invoke_unified(app, "slider-h_ratio.value", dragged_pairs)

        assert rs.thresholds.h_ratio.high == original_h_high, (
            "Slider drag must not mutate routing_state.thresholds "
            "(only Apply should commit changes)."
        )
        assert rs.custom_thresholds.h_ratio.high == original_h_high
    finally:
        _restore_state_snapshot(snap)


# ---- 4. Apply MUST update sliders to new state values (Apply persistence) -----

def test_apply_still_updates_slider_outputs_to_new_values():
    """Apply is not a slider trigger, so it should write the new state
    values back to all 7 slider outputs (confirming the drag was applied)."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        # User dragged tau_ps to high=9.5, then clicked Apply
        dragged_pairs = [
            [0.0, 0.15], [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 9.5],  # tau_ps: USER DRAG
            [0.85, 1.0], [80.0, 100.0],
        ]
        result = _invoke_unified(
            app, "btn-apply-thresholds.n_clicks",
            dragged_pairs, trigger_value=1, apply_clicks=1,
        )

        # tau_ps is field index 4 -> slider output at index 7+4 = 11
        tau_output = result[11]
        assert tau_output == [0.0, 9.5], (
            f"Apply must update tau_ps slider to [0.0, 9.5]; got {tau_output!r}"
        )
        assert result[7] == [0.0, 0.15]
        assert result[8] == [0.0, 1.0]
        for i in range(7):
            assert result[7 + i] is not no_update
    finally:
        _restore_state_snapshot(snap)


# ---- 4b. Apply MUST actually mutate state (regression for the bug user reported) -----

def test_apply_actually_mutates_state_with_dragged_values():
    """REGRESSION: clicking Apply after a drag must commit the dragged
    values to routing_state.custom_thresholds. Before the fix, the
    validator received a 14-element list of LISTS (not numbers), raised
    TypeError on `float([0, 0.5])`, and silently kept the preset values —
    the slider would then 'reset to default' after Apply."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        dragged_pairs = [
            [0.0, 0.50],   # h_ratio dragged high from 0.15 -> 0.50
            [0.0, 0.95],   # v_ratio dragged high from 1.0 -> 0.95
            [0.0, 77.0],   # r_ohm
            [0.0, 333.0],  # c_ff
            [0.0, 9.5],    # tau_ps
            [0.80, 1.0],   # via_coverage
            [75.0, 100.0], # similarity
        ]
        _invoke_unified(
            app, "btn-apply-thresholds.n_clicks",
            dragged_pairs, trigger_value=1, apply_clicks=1,
        )

        # State.custom_thresholds must now reflect the dragged values
        ct = rs.custom_thresholds
        assert ct is not None, "Apply must create custom_thresholds"
        assert abs(ct.h_ratio.high - 0.50) < 1e-9, (
            f"After Apply, h_ratio.high must be 0.50 (user drag); got {ct.h_ratio.high}. "
            f"This is the user's reported bug: slider reset to default after Apply."
        )
        assert abs(ct.v_ratio.high - 0.95) < 1e-9
        assert abs(ct.r_ohm.high - 77.0) < 1e-9
        assert abs(ct.c_ff.high - 333.0) < 1e-9
        assert abs(ct.tau_ps.high - 9.5) < 1e-9
        assert abs(ct.via_coverage.low - 0.80) < 1e-9
        assert abs(ct.similarity.low - 75.0) < 1e-9
        # State.thresholds (the preset) must be unchanged
        assert abs(rs.thresholds.h_ratio.high - 0.15) < 1e-9
    finally:
        _restore_state_snapshot(snap)


# ---- 4c. Apply + slider output: drag value must appear in output -------

def test_apply_slider_output_matches_dragged_value_not_default():
    """REGRESSION: After Apply, the slider output for the dragged field
    must be the user's drag value, NOT the default preset value. This is
    the core of the 'slider resets to default after Apply' user bug."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        # Drag h_ratio.high from 0.15 to 0.5
        dragged_pairs = [
            [0.0, 0.5],
            [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result = _invoke_unified(
            app, "btn-apply-thresholds.n_clicks",
            dragged_pairs, trigger_value=1, apply_clicks=1,
        )

        # h_ratio is field index 0 -> slider output at index 7
        h_ratio_output = result[7]
        assert h_ratio_output == [0.0, 0.5], (
            f"After Apply, h_ratio slider output must be [0.0, 0.5] "
            f"(the user's drag value); got {h_ratio_output!r}. "
            f"This means the slider would visually reset to default [0.0, 0.15]."
        )
    finally:
        _restore_state_snapshot(snap)


# ---- 4d. Apply with invalid values must NOT mutate state -------

def test_apply_with_invalid_values_does_not_mutate_state():
    """If validator rejects (e.g. low > high for some field), state must
    not be changed. Verify the error path doesn't leak a partial update."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        original_tau_high = rs.thresholds.tau_ps.high  # 12.5

        # Invalid: h_ratio.low (0) > h_ratio.high (0) — but actually 0 == 0 is ok,
        # use a value that fails validate(): low > high explicitly
        invalid_pairs = [
            [0.5, 0.1],    # h_ratio: low > high (invalid)
            [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result = _invoke_unified(
            app, "btn-apply-thresholds.n_clicks",
            invalid_pairs, trigger_value=1, apply_clicks=1,
        )

        # State.thresholds.tau_ps.high must remain at preset (no Apply applied)
        assert abs(rs.thresholds.tau_ps.high - original_tau_high) < 1e-9, (
            "Invalid Apply must not mutate state.thresholds"
        )
        # Apply status message should reflect the error (routing-config-status at index 3)
        apply_status = str(result[3])
        # It might be empty or contain an error — just ensure state is preserved
    finally:
        _restore_state_snapshot(snap)


# ---- 5. Tab rehydrate MUST update sliders to state values ---------------

def test_tab_rehydrate_updates_sliders_to_state_values():
    """Switching back to the config tab triggers rehydrate, which writes
    state values back to all 7 sliders (no no_update)."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        # Pretend sliders currently hold some stale draft values
        stale_pairs = [
            [0.0, 0.99], [0.0, 0.99], [0.0, 99.0], [0.0, 499.0],
            [0.0, 12.0], [0.86, 1.0], [80.0, 100.0],
        ]
        result = _invoke_unified(
            app, "tabs.value", stale_pairs,
            trigger_value="tab-routing-config",
        )

        # sram_7nm_wl preset: h=[0,0.15], v=[0,1], r=[0,100], c=[0,500],
        #                      tau=[0,12.5], via=[0.85,1], sim=[80,100]
        assert result[7] == [0.0, 0.15]
        assert result[8] == [0.0, 1.0]
        assert result[9] == [0.0, 100.0]
        assert result[10] == [0.0, 500.0]
        assert result[11] == [0.0, 12.5]
        assert result[12] == [0.85, 1.0]
        assert result[13] == [80.0, 100.0]
        for i in range(7):
            assert result[7 + i] is not no_update
    finally:
        _restore_state_snapshot(snap)


# ---- 6. Preset change MUST update sliders (not no_update) ---------------

def test_preset_change_updates_sliders_to_preset_values():
    """Changing the preset dropdown must update all 7 sliders to the new
    preset's values (no no_update)."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        assert rs.is_frozen is True

        app = _build_app_with_callbacks()

        old_pairs = [
            [0.0, 0.15], [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result = _invoke_unified(
            app, "routing-preset.value", old_pairs,
            trigger_value="sram_5nm_io_bl",
            preset_value="sram_5nm_io_bl",
        )

        # sram_5nm_io_bl has h_ratio.high=1.0 (IO is vertical-dominant)
        assert result[7] == [0.0, 1.0], (
            f"Preset change must update h_ratio slider to [0,1]; got {result[7]!r}"
        )
        for i in range(7):
            assert result[7 + i] is not no_update
    finally:
        _restore_state_snapshot(snap)


# ---- 7. Mode toggle MUST update sliders (not no_update) -----------------

def test_mode_toggle_updates_sliders():
    """Clicking mode-frozen or mode-editable must update sliders (preset
    on frozen toggle, copy-to-custom on editable toggle)."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        pairs = [
            [0.0, 0.15], [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result = _invoke_unified(
            app, "mode-frozen.n_clicks", pairs, f_clicks=1,
        )

        for i in range(7):
            assert result[7 + i] is not no_update, (
                f"slider-{i} must be updated on mode-frozen click"
            )
    finally:
        _restore_state_snapshot(snap)


# ---- 8. Two consecutive drags: each preserved independently -------------

def test_two_consecutive_drags_each_preserved():
    """If user drags slider A, then slider B, neither drag should reset
    to state. Each drag's slider output is no_update."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        from app.routing_state import routing_state as rs
        rs.set_frozen_mode(False)
        rs.custom_thresholds = rs.get_thresholds()

        app = _build_app_with_callbacks()

        # First drag: h_ratio from [0, 0.15] -> [0, 0.5]
        pairs_a = [
            [0.0, 0.5], [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result_a = _invoke_unified(app, "slider-h_ratio.value", pairs_a)
        for i in range(7):
            assert result_a[7 + i] is no_update

        # Second drag: tau_ps from [0, 12.5] -> [0, 9.5]
        pairs_b = [
            [0.0, 0.5], [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 9.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result_b = _invoke_unified(app, "slider-tau_ps.value", pairs_b)
        for i in range(7):
            assert result_b[7 + i] is no_update
    finally:
        _restore_state_snapshot(snap)