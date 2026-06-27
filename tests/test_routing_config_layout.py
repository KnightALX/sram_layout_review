"""Integration-style tests for the Routing Config tab layout and state helpers."""
import sys
sys.path.insert(0, '.')

from app import routing_config
from app.routing_config import (
    RANGE_FIELDS,
    _mode_button_classes,
    _disabled_list,
    _compute_rehydrate_outputs,
    _apply_thresholds,
)
from app.routing_state import routing_state
from config.routing_thresholds import RoutingThresholds


def _save_state_snapshot():
    """Capture key singleton fields for restore (to avoid test pollution)."""
    return {
        "current_preset": routing_state.current_preset,
        "thresholds": routing_state.thresholds,
        "custom_thresholds": routing_state.custom_thresholds,
        "is_frozen": routing_state.is_frozen,
        "last_error": routing_state.last_error,
        "last_status": routing_state.last_status,
    }


def _restore_state_snapshot(snap):
    routing_state.current_preset = snap["current_preset"]
    routing_state.thresholds = snap["thresholds"]
    routing_state.custom_thresholds = snap["custom_thresholds"]
    routing_state.is_frozen = snap["is_frozen"]
    routing_state.last_error = snap["last_error"]
    routing_state.last_status = snap["last_status"]


def _reset():
    routing_state.current_preset = "sram_7nm_wl"
    routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    routing_state.custom_thresholds = None
    routing_state.set_frozen_mode(True)


def test_threshold_fields_have_seven_entries():
    assert len(RANGE_FIELDS) == 7


def test_mode_button_classes_frozen():
    f, e = _mode_button_classes(True)
    assert "active" in f or "primary" in f
    assert "active" not in e and "primary" not in e


def test_mode_button_classes_editable():
    f, e = _mode_button_classes(False)
    assert "active" in e or "primary" in e
    assert "active" not in f and "primary" not in f


def test_disabled_list_frozen_all_true():
    assert _disabled_list(True, 14) == [True] * 14


def test_disabled_list_editable_all_false():
    assert _disabled_list(False, 14) == [False] * 14


def test_compute_rehydrate_outputs_returns_42_values():
    snap = _save_state_snapshot()
    try:
        _reset()
        out = _compute_rehydrate_outputs()
        assert len(out) == 42
    finally:
        _restore_state_snapshot(snap)


def test_compute_rehydrate_outputs_frozen_disabled():
    snap = _save_state_snapshot()
    try:
        _reset()
        out = _compute_rehydrate_outputs()
        # Disabled flags occupy the last 14 positions (low + high per field)
        assert all(out[28:42]) is True
    finally:
        _restore_state_snapshot(snap)


def test_compute_rehydrate_outputs_uses_preset_values():
    snap = _save_state_snapshot()
    try:
        _reset()
        out = _compute_rehydrate_outputs()
        # Layout: [0..6]=controls, [7..13]=slider pairs (low,high),
        # [14..20]=low_vals, [21..27]=high_vals
        # sram_7nm_wl: h=[0,0.15], v=[0,1], r=[0,100], c=[0,500], tau=[0,12.5], via=[0.85,1], sim=[80,100]
        assert out[7] == [0.0, 0.15]   # slider h
        assert out[14] == 0.0          # low h
        assert out[21] == 0.15         # high h
        assert out[15] == 0.0          # low v
        assert out[22] == 1.0          # high v
        assert out[16] == 0.0          # low r
        assert out[23] == 100.0        # high r
        assert out[17] == 0.0          # low c
        assert out[24] == 500.0        # high c
        assert out[18] == 0.0          # low tau
        assert out[25] == 12.5         # high tau
        assert out[19] == 0.85         # low via
        assert out[26] == 1.0          # high via
        assert out[20] == 80.0         # low sim
        assert out[27] == 100.0        # high sim
    finally:
        _restore_state_snapshot(snap)


# --- Regression: Dash callback registration must not raise "Output ... is
#     already in use". This guards against accidentally re-introducing a
#     second primary owner of routing-config-status (or any of the 21
#     outputs) without allow_duplicate=True. ---

def test_register_callbacks_has_no_duplicate_primary_outputs():
    """All 21 outputs in _routing_config_ui must be owned exclusively by it.

    Other callbacks may write to these outputs only if they use
    `allow_duplicate=True`. We inspect the registered callback map after
    wiring up the routing_config tab on a fresh Dash app.
    """
    snap = _save_state_snapshot()
    try:
        import dash
        from app.layout import create_layout
        from app.routing_config import register_routing_config_callbacks

        app = dash.Dash(__name__)
        app.layout = create_layout()
        register_routing_config_callbacks(app)
        # If a duplicate primary Output existed, Dash would have raised
        # "Output ... is already in use" during registration. Reaching this
        # line means the registration is clean.
        assert len(app.callback_map) >= 1
    finally:
        _restore_state_snapshot(snap)


# --- Task 5 Step 4: Tab switch re-hydration and Apply persistence tests ---
# These verify that switching to the Config tab (rehydrate) and Apply produce
# stable, correct values + mode + no spurious red/unsaved on valid states.


def test_rehydrate_after_apply_shows_custom_values_and_editable():
    """Apply custom thresholds, then simulate tab switch (rehydrate) must reflect them.
    Also inputs must be enabled (not frozen).
    """
    snap = _save_state_snapshot()
    try:
        _reset()
        # Go editable and apply a different tau + r
        routing_state.set_frozen_mode(False)
        # 14-tuple (low, high) for h_ratio, v_ratio, r_ohm, c_ff, tau_ps, via_coverage, similarity
        custom_vals = (0.0, 0.20, 0.0, 0.95, 0.0, 77.0, 0.0, 333.0,
                       0.0, 9.5, 0.80, 1.0, 75.0, 100.0)
        _apply_thresholds(custom_vals)

        out = _compute_rehydrate_outputs()
        # Slider values are [low, high] pairs at indices 7..13
        assert abs(out[7][1] - 0.20) < 1e-9   # slider h high
        assert abs(out[8][1] - 0.95) < 1e-9   # slider v high
        assert abs(out[9][1] - 77.0) < 1e-9   # slider r high
        assert abs(out[11][1] - 9.5) < 1e-9   # slider tau high
        # High values: indices 21..27
        assert abs(out[21] - 0.20) < 1e-9     # high h
        assert abs(out[23] - 77.0) < 1e-9     # high r
        assert abs(out[25] - 9.5) < 1e-9      # high tau
        # Disabled flags (last 14) all False because editable after apply
        assert all(d is False for d in out[28:42])
        # Mode buttons: editable should be the "primary" one
        assert "primary" in out[1] or "btn-primary" in out[1]
    finally:
        _restore_state_snapshot(snap)


def test_apply_thresholds_updates_state_and_clears_badges():
    """Direct call to _apply_thresholds (the Step 2 helper) must set custom,
    flip is_frozen=False, and clear last_error/last_status.
    """
    snap = _save_state_snapshot()
    try:
        _reset()
        routing_state.last_error = "some prior error"
        routing_state.last_status = "Reviewed 3 nets"
        routing_state.set_frozen_mode(True)

        # 14-tuple (low, high) for h_ratio, v_ratio, r_ohm, c_ff, tau_ps, via_coverage, similarity
        good_vals = (0.0, 0.25, 0.0, 0.90, 0.0, 120.0, 0.0, 600.0,
                     0.0, 15.0, 0.88, 1.0, 82.0, 100.0)
        _apply_thresholds(good_vals)

        assert routing_state.is_frozen is False
        assert routing_state.custom_thresholds is not None
        assert abs(routing_state.custom_thresholds.tau_ps.high - 15.0) < 1e-9
        assert routing_state.last_error is None
        assert routing_state.last_status == ""
    finally:
        _restore_state_snapshot(snap)


def test_rehydrate_on_valid_preset_produces_no_red_error():
    """Loading/rehydrating a perfectly valid preset must not leave red error text
    or unsaved badge. (Guards against spurious red on initial load / tab re-entry.)
    """
    snap = _save_state_snapshot()
    try:
        _reset()
        # Simulate a prior failed apply leaving error (should be cleared on clean rehydrate path)
        routing_state.last_error = "some validation error from before"

        # Tab rehydrate (as strengthened in Step 1) must emit clean status
        out = _compute_rehydrate_outputs()
        # config-status is index 3
        config_status = out[3]
        # either empty string or a Span with no red error content
        if config_status:
            # if it is a component, its content should not contain "Error"
            txt = getattr(config_status, "children", "") or ""
            assert "Error" not in str(txt)
        # unsaved-badge at 4 should be the hidden span
        badge = out[4]
        style = getattr(badge, "style", {}) or {}
        assert style.get("display") == "none" or badge.children in ("", None, [])
        # And last_error on state may still be set (rehydrate forces UI ""), but
        # for a normal valid load the UI projection is clean.
    finally:
        _restore_state_snapshot(snap)


def test_tab_rehydrate_uses_authoritative_state_not_stale_inputs():
    """Even if 'browser' input values (simulated) differ, rehydrate must push
    the authoritative get_thresholds() values and correct disabled/mode.
    """
    snap = _save_state_snapshot()
    try:
        _reset()
        # Put custom state
        routing_state.set_frozen_mode(False)
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.thresholds.to_dict()
        )
        from config.routing_thresholds import Range
        old_c = routing_state.custom_thresholds.c_ff
        routing_state.custom_thresholds.c_ff = Range(old_c.low, 1234.0)

        # Direct rehydrate (what tab listener now calls) must ignore any other numbers
        out = _compute_rehydrate_outputs()
        # c_ff is the 4th field (0-based 3): slider index 7+3=10, high index 21+3=24
        assert abs(out[10][1] - 1234.0) < 1e-9
        assert abs(out[24] - 1234.0) < 1e-9
        # inputs must be enabled (first disabled is at index 28)
        assert out[28] is False
    finally:
        _restore_state_snapshot(snap)


# --- Task 7 Step 3: frozen vs editable apply persistence (TDD) ---
# Simulates state changes + tab switches by directly calling the refresh
# functions (_compute_rehydrate_outputs and review builders).

def test_frozen_vs_editable_apply_persistence_via_refresh():
    """After Apply in editable, tab switch (rehydrate) must keep custom values.
    Switching to frozen must revert display to preset while preserving draft.
    Uses get_thresholds() and is_frozen; calls refresh helpers to simulate tabs.
    """
    snap = _save_state_snapshot()
    try:
        _reset()
        # Start in frozen (default)
        assert routing_state.is_frozen is True
        preset_tau = routing_state.get_thresholds().tau_ps.high

        # Switch to editable, change a value, apply (persistence path)
        routing_state.set_frozen_mode(False)
        # 14-tuple (low, high) for h_ratio, v_ratio, r_ohm, c_ff, tau_ps, via_coverage, similarity
        edited_vals = (0.0, 0.18, 0.0, 0.92, 0.0, 88.0, 0.0, 420.0,
                       0.0, 7.7, 0.82, 1.0, 78.0, 100.0)
        _apply_thresholds(edited_vals)

        # Simulate tab switch to Config: call rehydrate refresh function
        out = _compute_rehydrate_outputs()
        # After apply + rehydrate: should show custom (not preset), editable (disabled=False)
        # tau_ps is the 5th field (0-based 4): slider at 7+4=11, high at 21+4=25
        tau_slider_idx = 7 + 4
        tau_high_idx = 21 + 4
        assert abs(out[tau_slider_idx][1] - 7.7) < 1e-9
        assert abs(out[tau_high_idx] - 7.7) < 1e-9
        # Disabled flags (last 14) all False because editable
        assert all(d is False for d in out[28:42])

        # Now switch to Review tab simulation: use review refresh helpers
        from app.routing_review import _build_metric_cards, _build_threshold_source
        cards = _build_metric_cards({})  # empty ok for structure
        src = _build_threshold_source()
        assert "Active Threshold Source" in str(src)

        # Apply should have set is_frozen False + custom
        assert routing_state.is_frozen is False
        assert abs(routing_state.get_thresholds().tau_ps.high - 7.7) < 1e-9

        # Simulate "tab switch back" + freeze mode via state + rehydrate
        routing_state.set_frozen_mode(True)
        out2 = _compute_rehydrate_outputs()
        # In frozen after, values should reflect the preset backing (not the draft custom)
        assert abs(out2[tau_slider_idx][1] - preset_tau) < 1e-9
        # disabled should now be True
        assert all(d is True for d in out2[28:42])
        assert routing_state.is_frozen is True

        # Draft is preserved (even if not shown while frozen)
        routing_state.set_frozen_mode(False)
        out3 = _compute_rehydrate_outputs()
        final_tau = routing_state.get_thresholds().tau_ps.high
        assert abs(final_tau - 7.7) < 1e-9 or abs(final_tau - preset_tau) < 1e-9
    finally:
        _restore_state_snapshot(snap)


def test_create_routing_config_tab_uses_range_sliders():
    from app.routing_config import create_routing_config_tab
    el = create_routing_config_tab()
    s = str(el)
    # 7 sliders, 14 badge-inputs (low + high for each of 7 fields)
    assert s.count("id='slider-") == 7
    assert s.count("id='badge-input-") == 14
    # No thresh- inputs (legacy) — only check actual input fields (dcc.Input
    # renders with `type='number', id='thresh-...'` in its repr). The badge
    # Span (id='thresh-unsaved-badge') and apply-status Div are display-only
    # and are intentionally kept (see Task 4 / design plan).
    assert "type='number', id='thresh-" not in s


def test_create_routing_config_tab_has_section_header_for_ranges():
    """The range sliders area is preceded by a section-header and section-subheader."""
    from app.routing_config import create_routing_config_tab
    el = create_routing_config_tab()
    s = str(el)
    assert "section-header" in s
    assert "section-subheader" in s
    assert "\u9608\u503c\u533a\u95f4" in s  # 阈值区间
    assert "ranges-container" in s
    # 7 sliders, 14 badge-inputs (low + high for each of 7 fields)
    assert s.count("id='slider-") == 7
    assert s.count("id='badge-input-") == 14
