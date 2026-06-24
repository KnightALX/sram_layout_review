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
