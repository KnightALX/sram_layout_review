"""Verify Apply thresholds persists across tab switch (the user's reported bug).

Compact 2-column redesign: RangeSlider values are 7 `[low, high]` pairs (not
14 flat numbers). The slider's always-visible tooltip is the single source for
displayed values; there are no separate low/high text badges anymore.
"""
import sys
sys.path.insert(0, '.')

from app.routing_state import routing_state
from app.routing_config import (
    _compute_rehydrate_outputs,
    _handle_routing_preset_or_thresh,
)
from config.routing_thresholds import Range, RoutingThresholds


def _reset():
    routing_state.current_preset = "sram_7nm_wl"
    routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    routing_state.custom_thresholds = None
    routing_state.set_frozen_mode(True)


def test_apply_then_tab_switch_persists_values():
    """Apply + tab switch + rehydrate must show the applied values."""
    _reset()
    rs = routing_state

    # Simulate Apply: user enters Editable, modifies tau, calls Apply
    rs.set_frozen_mode(False)
    if rs.custom_thresholds is None:
        rs.custom_thresholds = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    old_tau = rs.custom_thresholds.tau_ps
    old_r = rs.custom_thresholds.r_ohm
    rs.custom_thresholds.tau_ps = Range(old_tau.low, 25.0)
    rs.custom_thresholds.r_ohm = Range(old_r.low, 60.0)

    # Simulate tab switch back: rehydrate
    out = _compute_rehydrate_outputs()
    # Compact 2-column redesign: 14-element tuple
    # Layout: [0..6]=mode/status controls, [7..13]=7 slider pairs (low,high)
    # tau_ps is the 5th field (0-based 4): slider at 7+4=11
    # r_ohm is the 3rd field (0-based 2): slider at 7+2=9
    assert abs(out[11][1] - 25.0) < 1e-9, f"tau high={out[11]}"
    assert abs(out[9][1] - 60.0) < 1e-9, f"r high={out[9]}"
    # Editable -> mode buttons: editable btn is primary
    assert "btn-primary" in out[1]


def test_apply_failure_does_not_touch_state():
    """Invalid apply values must NOT change routing_state.thresholds or custom_thresholds."""
    _reset()
    rs = routing_state
    original_tau = rs.get_thresholds().tau_ps.high

    rs.set_frozen_mode(False)
    # Pass invalid h_ratio.high=0.3, v_ratio.high=0.3 -> sum < 1.0 -> validate fails
    # 7 [low, high] pairs for h_ratio, v_ratio, r_ohm, c_ff, tau_ps, via_coverage, similarity
    bad_pairs = [
        [0.0, 0.3],
        [0.0, 0.3],
        [0.0, 50.0],
        [0.0, 20.0],
        [0.0, 12.5],
        [0.8, 1.0],
        [70.0, 100.0],
    ]
    try:
        _handle_routing_preset_or_thresh(None, bad_pairs, "input-h_ratio-high")
    except Exception:
        pass  # PreventUpdate or normal - both acceptable

    # State thresholds must be unchanged
    assert abs(rs.get_thresholds().tau_ps.high - original_tau) < 1e-9
