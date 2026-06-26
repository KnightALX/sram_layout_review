"""Tests for preset YAML loader."""
import pytest

from config.preset_loader import list_yaml_presets, load_preset_yaml, save_preset_yaml
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
    assert t.h_ratio.high == 0.15
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
    # missing h_ratio and other required Range fields
    bad.write_text("net_class: wl\nr_ohm: {low: 0.0, high: 100.0}\n")
    with pytest.raises(ValueError, match="Missing required fields"):
        load_preset_yaml(str(bad))


def test_load_preset_yaml_with_nested_low_high(tmp_path):
    """YAML with nested {low, high} dicts loads into RoutingThresholds with Range fields."""
    import yaml
    from config.preset_loader import load_preset_yaml, load_preset_from_file

    yaml_path = tmp_path / "test_range.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "net_class": "wl",
        "h_ratio":    {"low": 0.0, "high": 0.20},
        "v_ratio":    {"low": 0.0, "high": 1.0},
        "r_ohm":      {"low": 0.0, "high": 80.0},
        "c_ff":       {"low": 0.0, "high": 500.0},
        "tau_ps":     {"low": 0.0, "high": 12.5},
        "via_coverage": {"low": 0.85, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    }))
    # Pass the full path to load_preset_yaml (it accepts either name or path)
    t = load_preset_yaml(str(yaml_path))
    assert t.h_ratio.high == 0.20
    assert t.r_ohm.high == 80.0
    t.validate()

    # Also test load_preset_from_file directly
    t2 = load_preset_from_file(str(yaml_path))
    assert t2.h_ratio.low == 0.0
    assert t2.similarity.high == 100.0


def test_load_all_yaml_presets_use_new_format():
    """All YAML presets load via from_dict with the new low/high format and pass validate()."""
    from config.preset_loader import list_yaml_presets, load_preset_yaml
    from pathlib import Path
    from config.routing_thresholds import RoutingThresholds
    yaml_dir = Path(__file__).parent.parent / "config" / "presets"
    names = list_yaml_presets(presets_dir=yaml_dir) if False else list_yaml_presets()
    assert len(names) >= 3
    for name in names:
        t = load_preset_yaml(name)
        assert isinstance(t, RoutingThresholds)
        t.validate()  # must not raise
