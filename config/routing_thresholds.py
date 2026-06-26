"""Routing Review threshold configuration.

Defines the gating thresholds for the 6 routing-quality metrics.
Used by Configuration tab (load/save YAML) and Layout Review tab (gate check).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class NetClass(str, Enum):
    """Net routing-class — drives default threshold set."""
    WL = "wl"          # wordline: H-dominant, tight h_ratio
    IO = "io"          # IO/bitline: V-dominant, tight v_ratio
    ANALOG = "analog"  # general analog: balanced
    POWER = "power"    # power/ground: relaxed (no similarity needed)


# Placeholder for future field-level validation descriptors.
# Imported by tests/test_routing_thresholds.py; reserved for future use.
class ThresholdField:
    """Threshold field descriptor (placeholder, reserved for future use)."""
    pass


@dataclass(frozen=True)
class Range:
    """A closed interval [low, high]. Value passes iff low <= value <= high.

    Attributes:
        low: Lower bound (inclusive).
        high: Upper bound (inclusive).

    Raises:
        ValueError: When constructed with low > high.

    Note: low == high is allowed (single-point range). Only strict
    inversion (low > high) is rejected.
    """
    low: float
    high: float

    def __post_init__(self):
        if self.low > self.high:
            raise ValueError(
                f"Range low ({self.low}) > high ({self.high})"
            )

    def contains(self, value: float) -> bool:
        """Return True if value is in [low, high]."""
        return self.low <= value <= self.high

    def violation_direction(self, value: float) -> Optional[str]:
        """Return 'low' if value < low, 'high' if value > high, None if in range."""
        if value < self.low:
            return "low"
        if value > self.high:
            return "high"
        return None


# Built-in presets (used when no YAML is found)
_BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "sram_7nm_wl": {
        "net_class": "wl",
        "h_ratio":    {"low": 0.0, "high": 0.15},
        "v_ratio":    {"low": 0.0, "high": 1.0},
        "r_ohm":      {"low": 0.0, "high": 100.0},
        "c_ff":       {"low": 0.0, "high": 500.0},
        "tau_ps":     {"low": 0.0, "high": 12.5},
        "via_coverage": {"low": 0.85, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    },
    "sram_5nm_io_bl": {
        "net_class": "io",
        "h_ratio":    {"low": 0.0, "high": 1.0},
        "v_ratio":    {"low": 0.0, "high": 0.10},
        "r_ohm":      {"low": 0.0, "high": 80.0},
        "c_ff":       {"low": 0.0, "high": 400.0},
        "tau_ps":     {"low": 0.0, "high": 10.0},
        "via_coverage": {"low": 0.90, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    },
    "analog_default": {
        "net_class": "analog",
        "h_ratio":    {"low": 0.0, "high": 0.60},
        "v_ratio":    {"low": 0.0, "high": 0.60},
        "r_ohm":      {"low": 0.0, "high": 200.0},
        "c_ff":       {"low": 0.0, "high": 1000.0},
        "tau_ps":     {"low": 0.0, "high": 25.0},
        "via_coverage": {"low": 0.70, "high": 1.0},
        "similarity": {"low": 70.0, "high": 100.0},
    },
    "power_relaxed": {
        "net_class": "power",
        "h_ratio":    {"low": 0.0, "high": 1.0},
        "v_ratio":    {"low": 0.0, "high": 1.0},
        "r_ohm":      {"low": 0.0, "high": 500.0},
        "c_ff":       {"low": 0.0, "high": 5000.0},
        "tau_ps":     {"low": 0.0, "high": 100.0},
        "via_coverage": {"low": 0.50, "high": 1.0},
        "similarity": {"low": 0.0, "high": 100.0},
    },
}


@dataclass
class RoutingThresholds:
    """Gating thresholds for routing review.

    Each metric is a [low, high] interval. A value passes iff
    low <= value <= high. The aggregate pass/fail for a net is
    computed in core.routing_metrics.check_gates.

    Attributes:
        net_class: Routing class (wl/io/analog/power) — only used for display.
        h_ratio: H-direction length ratio range.
        v_ratio: V-direction length ratio range.
        r_ohm: Total resistance range (Ohms).
        c_ff: Total capacitance range (fF).
        tau_ps: Effective tau range (ps).
        via_coverage: Via coverage ratio range.
        similarity: Golden similarity score range (0-100).
    """
    net_class: str = "wl"
    h_ratio: Range = field(default_factory=lambda: Range(0.0, 0.15))
    v_ratio: Range = field(default_factory=lambda: Range(0.0, 1.0))
    r_ohm: Range = field(default_factory=lambda: Range(0.0, 100.0))
    c_ff: Range = field(default_factory=lambda: Range(0.0, 500.0))
    tau_ps: Range = field(default_factory=lambda: Range(0.0, 12.5))
    via_coverage: Range = field(default_factory=lambda: Range(0.85, 1.0))
    similarity: Range = field(default_factory=lambda: Range(80.0, 100.0))

    @classmethod
    def for_preset(cls, preset_name: str) -> "RoutingThresholds":
        """Get default thresholds by preset name."""
        if preset_name not in _BUILTIN_PRESETS:
            raise KeyError(f"Unknown preset: {preset_name}")
        t = cls.from_dict(_BUILTIN_PRESETS[preset_name])
        t.validate()
        return t

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingThresholds":
        """Build from dict (YAML/JSON compatible).

        Accepts nested {low, high} dicts for Range fields.
        """
        kwargs: Dict[str, Any] = {}
        for k, v in d.items():
            if k not in cls.__dataclass_fields__:
                continue
            field_type = str(cls.__dataclass_fields__[k].type)
            if "Range" in field_type and isinstance(v, dict):
                kwargs[k] = Range(v["low"], v["high"])
            else:
                kwargs[k] = v
        return cls(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict (Range fields become {low, high} dicts via asdict)."""
        return asdict(self)

    def validate(self) -> None:
        """Sanity check. Raises ValueError on invalid config.

        - Each Range: low <= high (already enforced in __post_init__)
        - h_ratio.high + v_ratio.high >= 1.0
        - r_ohm.high, c_ff.high, tau_ps.high must be > 0
        """
        if self.h_ratio.high + self.v_ratio.high < 1.0 - 1e-9:
            raise ValueError(
                f"h_ratio.high ({self.h_ratio.high}) + v_ratio.high "
                f"({self.v_ratio.high}) must sum to >= 1.0"
            )
        for name in ("r_ohm", "c_ff", "tau_ps"):
            v = getattr(self, name).high
            if v <= 0:
                raise ValueError(f"{name}.high must be positive: {v}")

    @classmethod
    def list_presets(cls) -> List[str]:
        """List all built-in preset names."""
        return list(_BUILTIN_PRESETS.keys())


# Task 6 Step 1: run validate on load (import time) for every _BUILTIN_PRESET.
# Guarantees no preset can be loaded that would fail .validate() (range or h+v>=1).
# This eliminates false red/invalid indicators on UI load of defaults or yamls
# (yamls get validated via load_preset_yaml path).
# Uses for_preset() which does from_dict + validate().
for _pn in list(_BUILTIN_PRESETS.keys()):
    RoutingThresholds.for_preset(_pn)
