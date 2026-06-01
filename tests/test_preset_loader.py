"""Tests for preset YAML loader."""
import os
import pytest
from config.preset_loader import (
    load_preset_yaml, save_preset_yaml, list_yaml_presets
)
from config.routing_thresholds import RoutingThresholds


def test_list_yaml_presets_finds_builtins(tmp_path, monkeypatch):
    """Should list the 3 built-in YAML files in config/presets/."""
    names = list_yaml_presets()
    assert "sram_7nm_wl" in names
    assert "sram_5nm_io_bl" in names
    assert "analog_default" in names


def test_load_preset_yaml_returns_thresholds():
    """Loading built-in preset returns valid RoutingThresholds."""
    t = load_preset_yaml("sram_7nm_wl")
    assert isinstance(t, RoutingThresholds)
    assert t.net_class == "wl"
    assert t.max_h_ratio == 0.15
    t.validate()  # must not raise


def test_save_and_reload_round_trip(tmp_path):
    """Save thresholds to a temp file, reload, compare."""
    out = tmp_path / "my_preset.yaml"
    original = RoutingThresholds.for_preset("sram_5nm_io_bl")
    save_preset_yaml(original, str(out))
    reloaded = load_preset_yaml(str(out))
    assert reloaded == original


def test_load_raises_on_missing_keys(tmp_path):
    """YAML missing required fields should raise ValueError."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("net_class: wl\nmax_h_ratio: 0.2\n")  # missing other fields
    with pytest.raises(ValueError, match="Missing required fields"):
        load_preset_yaml(str(bad))
