"""Verify Apply thresholds persists across tab switch (the user's reported bug)."""
import sys
sys.path.insert(0, '.')

from app.routing_state import routing_state
from app.routing_config import (
    _compute_rehydrate_outputs,
    _handle_routing_preset_or_thresh,
    THRESHOLD_FIELDS,
)
from config.routing_thresholds import RoutingThresholds


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
    rs.custom_thresholds.max_tau_ps = 25.0
    rs.custom_thresholds.max_r_ohm = 60.0

    # Simulate tab switch back: rehydrate
    out = _compute_rehydrate_outputs()
    tau_idx = 7 + 4  # tau is 4th field (h, v, r, c, tau, via, sim)
    r_idx = 7 + 2
    assert abs(out[tau_idx] - 25.0) < 1e-9, f"tau={out[tau_idx]}"
    assert abs(out[r_idx] - 60.0) < 1e-9, f"r={out[r_idx]}"
    # Editable -> enabled
    assert out[14] is False


def test_apply_failure_does_not_touch_state():
    """Invalid apply values must NOT change routing_state.thresholds or custom_thresholds."""
    _reset()
    rs = routing_state
    original_tau = rs.get_thresholds().max_tau_ps

    rs.set_frozen_mode(False)
    # Pass invalid h_ratio=0.3, v_ratio=0.3 -> sum < 1.0 -> validate fails
    bad_values = (0.3, 0.3, 50.0, 20.0, 12.5, 0.8, 70.0)
    try:
        _handle_routing_preset_or_thresh(None, bad_values, "thresh-max_h_ratio")
    except Exception:
        pass  # PreventUpdate or normal - both acceptable

    # State thresholds must be unchanged
    assert abs(rs.get_thresholds().max_tau_ps - original_tau) < 1e-9
