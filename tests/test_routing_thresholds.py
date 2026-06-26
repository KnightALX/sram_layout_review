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

    # TDD for Task 6 Step 1: also validate raw dicts (simulates what "run validate on load" will enforce for builtins at import time)
    # If any builtin dict would fail validate, this (and on-load guard) catches it.
    for name, d in _BUILTIN_PRESETS.items():
        t = RoutingThresholds.from_dict(d)
        t.validate()


# ---------------------------------------------------------------------------
# Tests for the new range-based RoutingThresholds.
# ---------------------------------------------------------------------------
"""Tests for the new range-based RoutingThresholds."""
import sys
sys.path.insert(0, '.')

import pytest
from config.routing_thresholds import Range, RoutingThresholds


def test_thresholds_default_uses_range():
    """Default thresholds have Range fields with sensible low/high."""
    t = RoutingThresholds()
    assert isinstance(t.h_ratio, Range)
    assert t.h_ratio.low == 0.0
    assert t.h_ratio.high == 0.15
    assert isinstance(t.r_ohm, Range)
    assert t.r_ohm.high == 100.0


def test_thresholds_validate_ok():
    t = RoutingThresholds(
        h_ratio=Range(0.0, 0.15),
        v_ratio=Range(0.0, 1.0),
        r_ohm=Range(0.0, 100.0),
        c_ff=Range(0.0, 500.0),
        tau_ps=Range(0.0, 12.5),
        via_coverage=Range(0.85, 1.0),
        similarity=Range(80.0, 100.0),
    )
    t.validate()  # should not raise


def test_thresholds_validate_h_plus_v_too_small():
    t = RoutingThresholds(
        h_ratio=Range(0.0, 0.3),
        v_ratio=Range(0.0, 0.3),  # 0.3 + 0.3 = 0.6 < 1.0
    )
    with pytest.raises(ValueError, match="h_ratio.*v_ratio|sum|1.0"):
        t.validate()


def test_thresholds_validate_zero_r_high():
    t = RoutingThresholds(r_ohm=Range(0.0, 0.0))
    with pytest.raises(ValueError, match="r_ohm.*positive"):
        t.validate()


def test_thresholds_from_dict_nested():
    d = {
        "net_class": "wl",
        "h_ratio": {"low": 0.0, "high": 0.2},
        "v_ratio": {"low": 0.0, "high": 1.0},
        "r_ohm": {"low": 0.0, "high": 50.0},
        "c_ff": {"low": 0.0, "high": 500.0},
        "tau_ps": {"low": 0.0, "high": 12.5},
        "via_coverage": {"low": 0.85, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    }
    t = RoutingThresholds.from_dict(d)
    assert t.h_ratio == Range(0.0, 0.2)
    assert t.r_ohm.high == 50.0


def test_thresholds_to_dict_roundtrip():
    t = RoutingThresholds()
    d = t.to_dict()
    assert isinstance(d["h_ratio"], dict)
    assert d["h_ratio"]["low"] == 0.0
    assert d["h_ratio"]["high"] == 0.15
    t2 = RoutingThresholds.from_dict(d)
    assert t2.h_ratio == t.h_ratio
    assert t2.r_ohm == t.r_ohm
