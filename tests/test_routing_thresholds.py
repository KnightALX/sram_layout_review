"""Tests for routing threshold dataclass."""
import pytest

from config.preset_loader import list_yaml_presets, load_preset_yaml
from config.routing_thresholds import _BUILTIN_PRESETS, RoutingThresholds


def test_default_thresholds_for_wl_net():
    """WL net should have tight h_ratio gate (horizontal-dominant)."""
    t = RoutingThresholds.for_preset("sram_7nm_wl")
    assert t.net_class == "wl"  # wordline, expects dominant H
    assert t.max_h_ratio == 0.15
    assert t.max_tau_ps == 12.5
    assert t.min_via_coverage == 0.85
    assert t.min_similarity == 80.0


def test_default_thresholds_for_io_net():
    """IO/BL net should have tight v_ratio gate (vertical-dominant)."""
    t = RoutingThresholds.for_preset("sram_5nm_io_bl")
    assert t.net_class == "io"
    assert t.max_v_ratio == 0.10
    assert t.max_tau_ps == 10.0


def test_to_dict_round_trip():
    """to_dict and from_dict must be symmetric."""
    t = RoutingThresholds(
        net_class="wl", max_h_ratio=0.20, max_v_ratio=0.85,
        max_r_ohm=100.0, max_c_ff=500.0, max_tau_ps=15.0,
        min_via_coverage=0.80, min_similarity=75.0,
    )
    d = t.to_dict()
    t2 = RoutingThresholds.from_dict(d)
    assert t2 == t


def test_validate_rejects_inverted_ratios():
    """max_h_ratio + max_v_ratio must allow at least 50% slack (so one direction can dominate)."""
    t = RoutingThresholds(
        net_class="wl", max_h_ratio=0.30, max_v_ratio=0.30,
        max_r_ohm=100.0, max_c_ff=500.0, max_tau_ps=15.0,
        min_via_coverage=0.80, min_similarity=75.0,
    )
    with pytest.raises(ValueError, match="sum of max ratios"):
        t.validate()


def test_all_builtin_and_yaml_presets_pass_validate():
    """All _BUILTIN_PRESETS (via for_preset which now validates on load) and
    YAML presets must pass .validate(). This guards against 'default values red'
    caused by templates that fail range or h+v>=1 rules.
    """
    # Built-ins are validated inside for_preset (Task 6)
    for name in _BUILTIN_PRESETS:
        t = RoutingThresholds.for_preset(name)
        # Explicit re-validate to be sure (idempotent)
        t.validate()

    # YAMLs are validated at load time; double-check round trip values
    for name in list_yaml_presets():
        t = load_preset_yaml(name)
        t.validate()
        # Cross-check against builtin equivalent when present
        if name in _BUILTIN_PRESETS:
            t2 = RoutingThresholds.for_preset(name)
            assert abs(t.max_h_ratio - t2.max_h_ratio) < 1e-12
            assert abs(t.max_v_ratio - t2.max_v_ratio) < 1e-12
