"""Tests for schema-aware preset loading (fallback + validation)."""
import sys
sys.path.insert(0, '.')

import pytest
import yaml
import tempfile
import os

from config.preset_loader import (
    PresetValidationError,
    load_preset_from_file,
    list_presets,
)
from config.routing_thresholds import RoutingThresholds


def test_load_known_preset_no_error():
    """Built-in presets must load without error."""
    presets = list_presets()
    assert "sram_7nm_wl" in presets
    t = load_preset_from_file(f"config/presets/{presets[0]}.yaml")
    assert t.h_ratio.high > 0


def test_missing_field_falls_back_to_default():
    """YAML missing a Range field -> that field takes RoutingThresholds default."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"h_ratio": {"low": 0.0, "high": 0.42}}, f)
        path = f.name
    try:
        t = load_preset_from_file(path)
        assert t.h_ratio.high == 0.42
        # similarity should fall back to RoutingThresholds default Range
        assert t.similarity.low == 80.0
    finally:
        os.unlink(path)


def test_unknown_field_is_ignored_or_filled_by_default():
    """YAML with an unknown field is currently silently ignored by
    _normalize_keys (only known keys are mapped). Verify that the loader
    still produces a valid RoutingThresholds from such YAML — this
    documents the actual permissive behavior of the schema-aware loader.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        # An unknown field ("max_h_ratios" with extra 's') is silently ignored;
        # the missing canonical fields fall back to RoutingThresholds defaults.
        yaml.dump({"net_class": "wl",
                   "h_ratio": {"low": 0.0, "high": 0.15},
                   "v_ratio": {"low": 0.0, "high": 1.0},
                   "r_ohm": {"low": 0.0, "high": 100.0},
                   "c_ff": {"low": 0.0, "high": 500.0},
                   "tau_ps": {"low": 0.0, "high": 12.5},
                   "via_coverage": {"low": 0.85, "high": 1.0},
                   "similarity": {"low": 80.0, "high": 100.0},
                   "max_h_ratios": 0.42}, f)
        path = f.name
    try:
        t = load_preset_from_file(path)
        # Known fields preserved
        assert t.h_ratio.high == 0.15
        # Unknown field ignored; defaults applied where needed
        assert isinstance(t, RoutingThresholds)
    finally:
        os.unlink(path)


def test_invalid_h_plus_v_raises():
    """h_ratio.high + v_ratio.high < 1.0 should raise."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"net_class": "wl",
                   "h_ratio": {"low": 0.0, "high": 0.3},
                   "v_ratio": {"low": 0.0, "high": 0.3},
                   "r_ohm": {"low": 0.0, "high": 100.0},
                   "c_ff": {"low": 0.0, "high": 500.0},
                   "tau_ps": {"low": 0.0, "high": 12.5},
                   "via_coverage": {"low": 0.85, "high": 1.0},
                   "similarity": {"low": 80.0, "high": 100.0}}, f)
        path = f.name
    try:
        with pytest.raises((PresetValidationError, ValueError)):
            load_preset_from_file(path)
    finally:
        os.unlink(path)


def test_via_coverage_range_field():
    """via_coverage now uses Range (low/high) like other fields."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"net_class": "wl",
                   "h_ratio": {"low": 0.0, "high": 0.6},
                   "v_ratio": {"low": 0.0, "high": 0.6},
                   "r_ohm": {"low": 0.0, "high": 100.0},
                   "c_ff": {"low": 0.0, "high": 500.0},
                   "tau_ps": {"low": 0.0, "high": 12.5},
                   "via_coverage": {"low": 0.85, "high": 1.0},
                   "similarity": {"low": 80.0, "high": 100.0}}, f)
        path = f.name
    try:
        t = load_preset_from_file(path)
        assert t.via_coverage.low == 0.85
        assert t.via_coverage.high == 1.0
    finally:
        os.unlink(path)