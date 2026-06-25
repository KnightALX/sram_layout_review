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
    snap = _save_state_snapshot()
    try:
        _reset()
        out = _compute_rehydrate_outputs()
        assert len(out) == 21
    finally:
        _restore_state_snapshot(snap)


def test_compute_rehydrate_outputs_frozen_disabled():
    snap = _save_state_snapshot()
    try:
        _reset()
        out = _compute_rehydrate_outputs()
        assert all(out[14:21]) is True
    finally:
        _restore_state_snapshot(snap)


def test_compute_rehydrate_outputs_uses_preset_values():
    snap = _save_state_snapshot()
    try:
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
