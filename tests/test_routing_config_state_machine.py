"""State machine unit tests for the single-callback routing config UI.

These tests are pure-Python: they directly import the 3 helpers
(_validate_apply, _render_state, _dispatch_action) from app.routing_config.
No Dash server required.
"""
import sys
sys.path.insert(0, '.')

from app import routing_config
from app.routing_state import routing_state
from app.routing_config import (
    THRESHOLD_FIELDS,
    _validate_apply,
    _render_state,
    _dispatch_action,
)
from config.routing_thresholds import RoutingThresholds


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


# 3. validate: None values are skipped, fall back to current state

def test_validate_apply_none_falls_back_to_current():
    _reset_state()
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
    assert all(out[14:21]) is True
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
    assert all(d is False for d in out[14:21])
    assert out[11] == 25.0


# 7. render: thresh input differs from state -> unsaved badge visible

def test_render_state_unsaved_badge_when_input_differs():
    _reset_state()
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
    inputs = [0.5] + [getattr(routing_state.custom_thresholds, n)
                      for n, *_ in THRESHOLD_FIELDS[1:]]
    out = _render_state(inputs)
    badge = out[4]
    assert badge is not None
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
    badge = out[4]
    assert badge is not None
    style = badge.style if hasattr(badge, "style") else {}
    assert style.get("display") == "none" or badge.children in ("", [], None)


# 9. dispatch: preset change in frozen mode -> state.thresholds updated, custom cleared

def test_dispatch_preset_change_in_frozen():
    _reset_state()
    assert routing_state.current_preset == "sram_7nm_wl"
    _dispatch_action("routing-preset.value", "sram_5nm_io_bl", None)
    assert routing_state.current_preset == "sram_5nm_io_bl"
    assert routing_state.thresholds.max_h_ratio == 1.0
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
    assert routing_state.custom_thresholds is not None
    assert routing_state.custom_thresholds.max_tau_ps == 99.0


# 12. dispatch: mode-editable click -> sets frozen=False, copies preset if no custom

def test_dispatch_editable_click_copies_preset():
    _reset_state()
    assert routing_state.is_frozen is True
    _dispatch_action("mode-editable.n_clicks", None, None)
    assert routing_state.is_frozen is False
    assert routing_state.custom_thresholds is not None
    assert routing_state.custom_thresholds.max_h_ratio == 0.15


# 13. dispatch: apply with valid values -> state.custom_thresholds updated, is_frozen=False

def test_dispatch_apply_valid():
    _reset_state()
    vals = (0.5, 0.7, 100.0, 500.0, 12.5, 0.85, 80.0)
    _dispatch_action("btn-apply-thresholds.n_clicks", None, vals)
    assert routing_state.custom_thresholds is not None
    assert routing_state.custom_thresholds.max_h_ratio == 0.5
    assert routing_state.is_frozen is False


# 14. dispatch: apply with invalid values -> state unchanged, last_error set

def test_dispatch_apply_invalid_keeps_state():
    _reset_state()
    original_thr = routing_state.thresholds
    original_custom = routing_state.custom_thresholds
    vals = (0.3, 0.3, 100.0, 500.0, 12.5, 0.85, 80.0)
    _dispatch_action("btn-apply-thresholds.n_clicks", None, vals)
    assert routing_state.thresholds is original_thr
    assert routing_state.custom_thresholds is original_custom
    assert routing_state.last_error is not None


# 15. dispatch: thresh value change -> no state mutation

def test_dispatch_thresh_value_no_mutation():
    _reset_state()
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
    original_custom = routing_state.custom_thresholds
    _dispatch_action("thresh-max_tau_ps.value", 25.0, None)
    assert routing_state.custom_thresholds is original_custom
    assert routing_state.custom_thresholds.max_tau_ps == 12.5