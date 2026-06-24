"""Verify that switching back to the routing-config tab triggers a rehydrate."""
import sys
sys.path.insert(0, '.')


def test_rehydrate_outputs_after_state_change():
    """Simulate the user applying custom values, switching to another tab,
    then switching back. Rehydrate must reflect the applied state.
    """
    from app.routing_config import _compute_rehydrate_outputs
    # The module exports `routing_state`; alias to match plan.
    from app.routing_state import routing_state as global_routing_state
    from config.routing_thresholds import RoutingThresholds

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
    global_routing_state.custom_thresholds.max_tau_ps = 88.0

    # "Tab switch back" = calling rehydrate directly (callback body is the same)
    out = _compute_rehydrate_outputs()

    # Outputs 0..6 are classes/status; 7..13 are 7 thresh values; 14..20 are disabled
    tau_idx = 7 + 4
    assert abs(out[tau_idx] - 88.0) < 1e-9, (
        f"expected 88.0, got {out[tau_idx]} - rehydrate did not surface custom value"
    )
    assert out[14] is False  # editable -> inputs enabled


def test_rehydrate_outputs_frozen_shows_preset_even_with_custom_draft():
    """When frozen but a custom draft exists, rehydrate shows preset (UI hides draft)."""
    from app.routing_config import _compute_rehydrate_outputs
    from app.routing_state import routing_state as global_routing_state
    from config.routing_thresholds import RoutingThresholds

    global_routing_state.current_preset = "sram_7nm_wl"
    global_routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    global_routing_state.set_frozen_mode(True)
    # Inject a draft directly (simulating user previously edited)
    global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
        global_routing_state.get_thresholds().to_dict()
    )
    global_routing_state.custom_thresholds.max_tau_ps = 88.0

    # _is_frozen = True (we set it before injecting the draft)
    global_routing_state._is_frozen = True

    out = _compute_rehydrate_outputs()
    tau_idx = 7 + 4
    preset_tau = RoutingThresholds.for_preset("sram_7nm_wl").max_tau_ps
    assert abs(out[tau_idx] - preset_tau) < 1e-9
    assert out[14] is True  # frozen -> inputs disabled
    # The draft is preserved in state
    assert global_routing_state.custom_thresholds.max_tau_ps == 88.0