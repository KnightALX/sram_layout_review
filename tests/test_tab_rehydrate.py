"""Verify that switching back to the routing-config tab triggers a rehydrate."""
import sys
sys.path.insert(0, '.')


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


def test_rehydrate_outputs_after_state_change():
    """Simulate the user applying custom values, switching to another tab,
    then switching back. Rehydrate must reflect the applied state.
    """
    from app.routing_config import _compute_rehydrate_outputs
    from app.routing_state import routing_state as global_routing_state
    from config.routing_thresholds import Range, RoutingThresholds

    snap = _save_state_snapshot()
    try:
        # Reset
        global_routing_state.current_preset = "sram_7nm_wl"
        global_routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
        global_routing_state.custom_thresholds = None
        global_routing_state.set_frozen_mode(True)

        # User enters Editable and applies a custom value
        global_routing_state.set_frozen_mode(False)
        if global_routing_state.custom_thresholds is None:
            global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
                global_routing_state.get_thresholds().to_dict()
            )
        old_tau = global_routing_state.custom_thresholds.tau_ps
        global_routing_state.custom_thresholds.tau_ps = Range(old_tau.low, 88.0)

        # "Tab switch back" = calling rehydrate directly (callback body is the same)
        out = _compute_rehydrate_outputs()

        # Layout: [0..6]=controls, [7..13]=slider pairs (low,high),
        # [14..20]=low_vals, [21..27]=high_vals, [28..41]=disabled flags
        # tau_ps is the 5th field (0-based 4): slider at 7+4=11, high at 21+4=25
        tau_slider_idx = 7 + 4
        tau_high_idx = 21 + 4
        assert abs(out[tau_slider_idx][1] - 88.0) < 1e-9, (
            f"expected 88.0, got {out[tau_slider_idx]} - rehydrate did not surface custom value"
        )
        assert abs(out[tau_high_idx] - 88.0) < 1e-9
        # Editable -> inputs enabled (disabled flags at 28..41)
        assert out[28] is False
    finally:
        _restore_state_snapshot(snap)


def test_rehydrate_outputs_frozen_shows_preset_even_with_custom_draft():
    """When frozen but a custom draft exists, rehydrate shows preset (UI hides draft)."""
    from app.routing_config import _compute_rehydrate_outputs
    from app.routing_state import routing_state as global_routing_state
    from config.routing_thresholds import Range, RoutingThresholds

    snap = _save_state_snapshot()
    try:
        global_routing_state.current_preset = "sram_7nm_wl"
        global_routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
        global_routing_state.set_frozen_mode(True)
        # Inject a draft directly (simulating user previously edited)
        global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
            global_routing_state.get_thresholds().to_dict()
        )
        old_tau = global_routing_state.custom_thresholds.tau_ps
        global_routing_state.custom_thresholds.tau_ps = Range(old_tau.low, 88.0)

        # Use public setter (replaces previous direct _is_frozen access)
        global_routing_state.set_frozen_mode(True)

        out = _compute_rehydrate_outputs()
        # tau_ps is the 5th field (0-based 4): slider at 11, high at 25
        tau_slider_idx = 7 + 4
        tau_high_idx = 21 + 4
        preset_tau = RoutingThresholds.for_preset("sram_7nm_wl").tau_ps.high
        assert abs(out[tau_slider_idx][1] - preset_tau) < 1e-9
        assert abs(out[tau_high_idx] - preset_tau) < 1e-9
        # Frozen -> inputs disabled (disabled flags at 28..41)
        assert out[28] is True
        # The draft is preserved in state
        assert global_routing_state.custom_thresholds.tau_ps.high == 88.0
    finally:
        _restore_state_snapshot(snap)