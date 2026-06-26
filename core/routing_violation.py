"""Structured routing violations with location info for visualization."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ViolationKind(str, Enum):
    H_RATIO = "h_ratio"
    V_RATIO = "v_ratio"
    R_TOTAL = "r_total"
    C_TOTAL = "c_total"
    TAU_PS = "tau_ps"
    VIA_COVERAGE = "via_coverage"
    MISSING_VIA = "missing_via"
    SIMILARITY = "similarity"


@dataclass
class RoutingViolation:
    """A single routing-quality violation with location for highlighting."""
    kind: ViolationKind
    net_name: str
    severity: str = "critical"  # "critical" or "warning"
    message: str = ""
    # Location (for visualization)
    x: Optional[float] = None
    y: Optional[float] = None
    polygon_index: Optional[int] = None
    # Direction of the violation relative to the range
    direction: Optional[str] = None          # "low" / "high"
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    # The actual measured value (used for per-cell coloring)
    measured: Optional[float] = None
    # Measured vs limit
    h_ratio: Optional[float] = None
    v_ratio: Optional[float] = None
    r_total: Optional[float] = None
    c_total: Optional[float] = None
    tau_ps: Optional[float] = None
    via_coverage: Optional[float] = None
    missing_via_count: Optional[int] = None
    similarity_score: Optional[float] = None
    limit: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingViolation":
        d = dict(d)
        d["kind"] = ViolationKind(d["kind"])
        return cls(**d)

    # ---------- Factory helpers ----------
    @classmethod
    def h_ratio(cls, net_name, value, rng):  # noqa: F811
        direction = rng.violation_direction(value)
        return cls(
            kind=ViolationKind.H_RATIO, net_name=net_name,
            measured=value, direction=direction,
            range_low=rng.low, range_high=rng.high,
            h_ratio=value,
            message=f"h_ratio {value:.2%} {direction} [{rng.low:.2%}, {rng.high:.2%}]",
        )

    @classmethod
    def v_ratio(cls, net_name, value, rng):  # noqa: F811
        direction = rng.violation_direction(value)
        return cls(
            kind=ViolationKind.V_RATIO, net_name=net_name,
            measured=value, direction=direction,
            range_low=rng.low, range_high=rng.high,
            v_ratio=value,
            message=f"v_ratio {value:.2%} {direction} [{rng.low:.2%}, {rng.high:.2%}]",
        )

    @classmethod
    def r_ohm(cls, net_name, value, rng):  # noqa: F811
        direction = rng.violation_direction(value)
        return cls(
            kind=ViolationKind.R_TOTAL, net_name=net_name,
            measured=value, direction=direction,
            range_low=rng.low, range_high=rng.high,
            r_total=value,
            message=f"R {value:.2f}\u03a9 {direction} [{rng.low:.2f}, {rng.high:.2f}]",
        )

    @classmethod
    def c_ff(cls, net_name, value, rng):  # noqa: F811
        direction = rng.violation_direction(value)
        return cls(
            kind=ViolationKind.C_TOTAL, net_name=net_name,
            measured=value, direction=direction,
            range_low=rng.low, range_high=rng.high,
            c_total=value,
            message=f"C {value:.2f}fF {direction} [{rng.low:.2f}, {rng.high:.2f}]",
        )

    @classmethod
    def tau_ps(cls, net_name, value, rng):  # noqa: F811
        direction = rng.violation_direction(value)
        return cls(
            kind=ViolationKind.TAU_PS, net_name=net_name,
            measured=value, direction=direction,
            range_low=rng.low, range_high=rng.high,
            tau_ps=value,
            message=f"\u03c4 {value:.2f}ps {direction} [{rng.low:.2f}, {rng.high:.2f}]",
        )

    @classmethod
    def via_coverage(cls, net_name, value, rng):  # noqa: F811
        direction = rng.violation_direction(value)
        return cls(
            kind=ViolationKind.VIA_COVERAGE, net_name=net_name,
            measured=value, direction=direction,
            range_low=rng.low, range_high=rng.high,
            via_coverage=value,
            message=f"via_coverage {value:.2%} {direction} [{rng.low:.2%}, {rng.high:.2%}]",
        )

    @classmethod
    def missing_via(cls, net_name, x, y, layer):
        return cls(
            kind=ViolationKind.MISSING_VIA, net_name=net_name,
            x=x, y=y, message=f"missing via near ({x:.3f}, {y:.3f}) on {layer}",
        )

    @classmethod
    def similarity(cls, net_name, value, rng):
        direction = rng.violation_direction(value)
        return cls(
            kind=ViolationKind.SIMILARITY, net_name=net_name,
            measured=value, direction=direction,
            range_low=rng.low, range_high=rng.high,
            similarity_score=value,
            message=f"similarity {value:.1f} {direction} [{rng.low:.1f}, {rng.high:.1f}]",
        )
