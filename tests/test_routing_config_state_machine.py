"""State machine unit tests for the single-callback routing config UI.

These tests are pure-Python: they directly import the 3 helpers
(_validate_apply, _render_state, _dispatch_action) from app.routing_config.
No Dash server required.

Compact 2-column redesign: each RangeSlider exposes its `value` as a
`[low, high]` list. So `_validate_apply` and `_render_state` now receive a
list of 7 `[low, high]` pairs (not a flat 14-element list of numbers).
"""
import sys
sys.path.insert(0, '.')

from app import routing_config
from app.routing_state import routing_state
from app.routing_config import (
    RANGE_FIELDS,
    _validate_apply,
    _render_state,
    _dispatch_action,
)
from config.routing_thresholds import Range, RoutingThresholds


def _save_state_snapshot():
    """Capture key singleton fields for restore (to avoid test pollution)."""
    return {
        "current_preset": routing_state.current_preset,
        "thresholds": routing_state.thresholds,
        "custom_thresholds": routing_state.custom_thresholds,
        "is_frozen": routing_state.is_frozen,
        "golden_regex": routing_state.golden_regex,
        "batch_regex": routing_state.batch_regex,
        "last_error": routing_state.last_error,
        "last_status": routing_state.last_status,
    }


def _restore_state_snapshot(snap):
    routing_state.current_preset = snap["current_preset"]
    routing_state.thresholds = snap["thresholds"]
    routing_state.custom_thresholds = snap["custom_thresholds"]
    routing_state.is_frozen = snap["is_frozen"]  # direct ok in test restore
    routing_state.golden_regex = snap["golden_regex"]
    routing_state.batch_regex = snap["batch_regex"]
    routing_state.last_error = snap["last_error"]
    routing_state.last_status = snap["last_status"]
    # Note: do not restore review results here; tests focus on config state


def _reset_state():
    """Reset routing_state to known frozen+preset state."""
    routing_state.current_preset = "sram_7nm_wl"
    routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    routing_state.custom_thresholds = None
    routing_state.set_frozen_mode(True)


def _pairs_from_thresholds(t):
    """Helper: build 7 [low, high] pairs from a RoutingThresholds instance."""
    return [[getattr(t, fld["name"]).low,
             getattr(t, fld["name"]).high] for fld in RANGE_FIELDS]


# 1. validate: 7 valid pairs -> RoutingThresholds instance, no error

def test_validate_apply_valid_values():
    snap = _save_state_snapshot()
    try:
        # 7 [low, high] pairs for h_ratio, v_ratio, r_ohm, c_ff, tau_ps, via_coverage, similarity
        pairs = [
            [0.0, 0.15], [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result, err = _validate_apply(pairs)
        assert err is None
        assert result is not None
        assert result.h_ratio.high == 0.15
        assert result.tau_ps.high == 12.5
    finally:
        _restore_state_snapshot(snap)


# 2. validate: h+v < 1 -> error

def test_validate_apply_h_plus_v_too_small():
    snap = _save_state_snapshot()
    try:
        # h_ratio.high=0.3, v_ratio.high=0.3 -> 0.6 < 1.0, should fail
        pairs = [
            [0.0, 0.3], [0.0, 0.3], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        result, err = _validate_apply(pairs)
        assert result is None
        assert err is not None
    finally:
        _restore_state_snapshot(snap)


# 3. validate: None values are skipped, fall back to current state

def test_validate_apply_none_falls_back_to_current():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        # 7 [None, None] pairs fall back to current state's Range values
        pairs = [[None, None]] * 7
        result, err = _validate_apply(pairs)
        assert err is None
        assert result is not None
        assert result.h_ratio.high == 0.15
        assert result.tau_ps.high == 12.5
    finally:
        _restore_state_snapshot(snap)


# 4. validate: out-of-range value rejected

def test_validate_apply_negative_tau_rejected():
    snap = _save_state_snapshot()
    try:
        # tau_ps.high=-1.0 -> invalid (negative)
        pairs = [
            [0.0, 0.15], [0.0, 1.0], [0.0, 100.0], [0.0, 500.0],
            [0.0, -1.0], [0.85, 1.0], [80.0, 100.0],
        ]
        result, err = _validate_apply(pairs)
        assert result is None
        assert err is not None
    finally:
        _restore_state_snapshot(snap)


# 5. render: frozen + preset -> 14 outputs, mode buttons reflect frozen

def test_render_state_frozen_preset_disabled():
    """Compact redesign: 14-element tuple; frozen mode sets `btn-primary` on frozen btn."""
    snap = _save_state_snapshot()
    try:
        _reset_state()
        # Pass 7 [low, high] pairs (matching RANGE_FIELDS)
        pairs = _pairs_from_thresholds(routing_state.thresholds)
        out = _render_state(pairs)
        assert len(out) == 14
        # Mode buttons: frozen is primary, editable is secondary
        assert "btn-primary" in out[0]
        assert "btn-secondary" in out[1]
        # Slider values are [low, high] pairs at 7..13
        assert out[7] == [0.0, 0.15]
        assert out[8] == [0.0, 1.0]
        assert out[11] == [0.0, 12.5]
    finally:
        _restore_state_snapshot(snap)


# 6. render: editable + custom -> custom values shown in slider pairs

def test_render_state_editable_custom_enabled():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        routing_state.set_frozen_mode(False)
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
        # Mutate tau_ps.high
        old_tau = routing_state.custom_thresholds.tau_ps
        routing_state.custom_thresholds.tau_ps = Range(old_tau.low, 25.0)
        pairs = _pairs_from_thresholds(routing_state.custom_thresholds)
        out = _render_state(pairs)
        # tau_ps is the 5th field (0-based 4): slider at 11
        assert out[11] == [0.0, 25.0]
        # Mode buttons: editable is primary now
        assert "btn-primary" in out[1]
    finally:
        _restore_state_snapshot(snap)


# 7. render: thresh input differs from state -> unsaved badge visible

def test_render_state_unsaved_badge_when_input_differs():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        routing_state.set_frozen_mode(False)
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        # Build 7 input pairs from custom, then change the first (h_ratio.high) to 0.5
        pairs = _pairs_from_thresholds(routing_state.custom_thresholds)
        pairs[0] = [0.0, 0.5]  # h_ratio: [low, high] = [0.0, 0.5]
        out = _render_state(pairs)
        badge = out[4]
        assert badge is not None
        status = out[5]
        assert status is not None
    finally:
        _restore_state_snapshot(snap)


# 8. render: thresh input matches state -> no unsaved badge

def test_render_state_no_unsaved_when_matches():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        routing_state.set_frozen_mode(False)
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        pairs = _pairs_from_thresholds(routing_state.custom_thresholds)
        out = _render_state(pairs)
        badge = out[4]
        assert badge is not None
        style = badge.style if hasattr(badge, "style") else {}
        assert style.get("display") == "none" or badge.children in ("", [], None)
    finally:
        _restore_state_snapshot(snap)


# 9. dispatch: preset change in frozen mode -> state.thresholds updated, custom cleared

def test_dispatch_preset_change_in_frozen():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        assert routing_state.current_preset == "sram_7nm_wl"
        _dispatch_action("routing-preset.value", "sram_5nm_io_bl", None)
        assert routing_state.current_preset == "sram_5nm_io_bl"
        # sram_5nm_io_bl has h_ratio.high=1.0 (IO is vertical-dominant)
        assert routing_state.thresholds.h_ratio.high == 1.0
        assert routing_state.custom_thresholds is None
    finally:
        _restore_state_snapshot(snap)


# 10. dispatch: preset change in editable mode -> state unchanged (blocked)

def test_dispatch_preset_change_in_editable_blocked():
    snap = _save_state_snapshot()
    try:
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
    finally:
        _restore_state_snapshot(snap)


# 11. dispatch: mode-frozen click -> sets frozen=True (does NOT clear custom)

def test_dispatch_frozen_click_preserves_custom():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        routing_state.set_frozen_mode(False)
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        old_tau = routing_state.custom_thresholds.tau_ps
        routing_state.custom_thresholds.tau_ps = Range(old_tau.low, 99.0)
        _dispatch_action("mode-frozen.n_clicks", None, None)
        assert routing_state.is_frozen is True
        assert routing_state.custom_thresholds is not None
        assert routing_state.custom_thresholds.tau_ps.high == 99.0
        # Authoritative get returns preset (not the draft) even though custom present
        assert routing_state.get_thresholds().tau_ps.high == 12.5
    finally:
        _restore_state_snapshot(snap)


# 12. dispatch: mode-editable click -> sets frozen=False, copies preset if no custom

def test_dispatch_editable_click_copies_preset():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        assert routing_state.is_frozen is True
        _dispatch_action("mode-editable.n_clicks", None, None)
        assert routing_state.is_frozen is False
        assert routing_state.custom_thresholds is not None
        assert routing_state.custom_thresholds.h_ratio.high == 0.15
    finally:
        _restore_state_snapshot(snap)


# 13. dispatch: apply with valid values -> state.custom_thresholds updated, is_frozen=False

def test_dispatch_apply_valid():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        # 7 [low, high] pairs; h_ratio.high=0.5, v_ratio.high=0.7
        pairs = [
            [0.0, 0.5], [0.0, 0.7], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        _dispatch_action("btn-apply-thresholds.n_clicks", None, pairs)
        assert routing_state.custom_thresholds is not None
        assert routing_state.custom_thresholds.h_ratio.high == 0.5
        assert routing_state.is_frozen is False
    finally:
        _restore_state_snapshot(snap)


# 14. dispatch: apply with invalid values -> state unchanged, last_error set

def test_dispatch_apply_invalid_keeps_state():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        original_thr = routing_state.thresholds
        original_custom = routing_state.custom_thresholds
        # h_ratio.high=0.3, v_ratio.high=0.3 -> sum 0.6 < 1.0, invalid
        pairs = [
            [0.0, 0.3], [0.0, 0.3], [0.0, 100.0], [0.0, 500.0],
            [0.0, 12.5], [0.85, 1.0], [80.0, 100.0],
        ]
        _dispatch_action("btn-apply-thresholds.n_clicks", None, pairs)
        assert routing_state.thresholds is original_thr
        assert routing_state.custom_thresholds is original_custom
        assert routing_state.last_error is not None
    finally:
        _restore_state_snapshot(snap)


# 15. dispatch: thresh value change -> no state mutation

def test_dispatch_thresh_value_no_mutation():
    snap = _save_state_snapshot()
    try:
        _reset_state()
        routing_state.set_frozen_mode(False)
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        original_custom = routing_state.custom_thresholds
        _dispatch_action("input-tau_ps-high.value", 25.0, None)
        assert routing_state.custom_thresholds is original_custom
        assert routing_state.custom_thresholds.tau_ps.high == 12.5
    finally:
        _restore_state_snapshot(snap)
