"""Routing Review threshold configuration.

Defines the gating thresholds for the 6 routing-quality metrics.
Used by Configuration tab (load/save YAML) and Layout Review tab (gate check).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List


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


# Built-in presets (used when no YAML is found)
_BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "sram_7nm_wl": {
        "net_class": "wl", "max_h_ratio": 0.15, "max_v_ratio": 1.0,
        "max_r_ohm": 100.0, "max_c_ff": 500.0, "max_tau_ps": 12.5,
        "min_via_coverage": 0.85, "min_similarity": 80.0,
    },
    "sram_5nm_io_bl": {
        "net_class": "io", "max_h_ratio": 1.0, "max_v_ratio": 0.10,
        "max_r_ohm": 80.0, "max_c_ff": 400.0, "max_tau_ps": 10.0,
        "min_via_coverage": 0.90, "min_similarity": 80.0,
    },
    "analog_default": {
        "net_class": "analog", "max_h_ratio": 0.60, "max_v_ratio": 0.60,
        "max_r_ohm": 200.0, "max_c_ff": 1000.0, "max_tau_ps": 25.0,
        "min_via_coverage": 0.70, "min_similarity": 70.0,
    },
    "power_relaxed": {
        "net_class": "power", "max_h_ratio": 1.0, "max_v_ratio": 1.0,
        "max_r_ohm": 500.0, "max_c_ff": 5000.0, "max_tau_ps": 100.0,
        "min_via_coverage": 0.50, "min_similarity": 0.0,
    },
}


@dataclass
class RoutingThresholds:
    """Gating thresholds for routing review.

    Attributes:
        net_class: Routing class (wl/io/analog/power) — only used for display.
        max_h_ratio: Max allowed H-direction length ratio (0-1). Net fails if exceeded.
        max_v_ratio: Max allowed V-direction length ratio (0-1). Net fails if exceeded.
        max_r_ohm: Max total resistance in Ohms.
        max_c_ff: Max total capacitance in fF.
        max_tau_ps: Max effective tau in ps.
        min_via_coverage: Min required via coverage (0-1).
        min_similarity: Min required Golden similarity score (0-100).
    """
    net_class: str = "wl"
    max_h_ratio: float = 0.15
    max_v_ratio: float = 0.95
    max_r_ohm: float = 100.0
    max_c_ff: float = 500.0
    max_tau_ps: float = 12.5
    min_via_coverage: float = 0.85
    min_similarity: float = 80.0

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
        """Build from dict (YAML/JSON compatible)."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    def validate(self) -> None:
        """Sanity check. Raises ValueError on invalid config."""
        for name in ("max_h_ratio", "max_v_ratio", "min_via_coverage", "min_similarity"):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0 if name != "min_similarity" else 0.0 <= v <= 100.0):
                raise ValueError(f"{name} out of range: {v}")
        for name in ("max_r_ohm", "max_c_ff", "max_tau_ps"):
            v = getattr(self, name)
            if v <= 0:
                raise ValueError(f"{name} must be positive: {v}")
        # Ensure at least one direction is allowed to dominate (sum ≥ 1.0).
        # If sum < 1.0, no net can be 100% in any direction without failing one gate.
        if self.max_h_ratio + self.max_v_ratio < 1.0:
            raise ValueError(
                f"sum of max ratios ({self.max_h_ratio}+{self.max_v_ratio}) < 1.0, "
                "no direction can dominate"
            )

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
