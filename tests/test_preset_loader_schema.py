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


def test_load_known_preset_no_error():
    """Built-in presets must load without error."""
    presets = list_presets()
    assert "sram_7nm_wl" in presets
    t = load_preset_from_file(f"config/presets/{presets[0]}.yaml")
    assert t.max_h_ratio > 0


def test_missing_field_falls_back_to_default():
    """YAML missing a field -> that field takes RoutingThresholds default."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratio": 0.42}, f)
        path = f.name
    try:
        t = load_preset_from_file(path)
        assert t.max_h_ratio == 0.42
        # min_similarity should fall back to RoutingThresholds default (70.0)
        assert t.min_similarity == 70.0
    finally:
        os.unlink(path)


def test_unknown_field_raises_preset_validation_error():
    """YAML with a typo'd field name should raise PresetValidationError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratios": 0.42, "min_sim": 80.0}, f)  # wrong names
        path = f.name
    try:
        with pytest.raises(PresetValidationError):
            load_preset_from_file(path)
    finally:
        os.unlink(path)


def test_invalid_h_plus_v_raises():
    """h_ratio + v_ratio < 1.0 should raise."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratio": 0.3, "max_v_ratio": 0.3}, f)
        path = f.name
    try:
        with pytest.raises(PresetValidationError):
            load_preset_from_file(path)
    finally:
        os.unlink(path)


def test_alias_via_coverage_maps_to_min_via_coverage():
    """Old YAML key 'via_coverage' should still work (alias)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"max_h_ratio": 0.6, "max_v_ratio": 0.6,
                   "via_coverage": 0.85}, f)
        path = f.name
    try:
        t = load_preset_from_file(path)
        assert t.min_via_coverage == 0.85
    finally:
        os.unlink(path)
