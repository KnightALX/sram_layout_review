"""Structured routing violations with location info for visualization."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any


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
    def h_ratio(cls, net_name, h_ratio, limit):
        return cls(
            kind=ViolationKind.H_RATIO, net_name=net_name,
            h_ratio=h_ratio, limit=limit,
            message=f"h_ratio {h_ratio:.2%} > limit {limit:.2%}",
        )

    @classmethod
    def v_ratio(cls, net_name, v_ratio, limit):
        return cls(
            kind=ViolationKind.V_RATIO, net_name=net_name,
            v_ratio=v_ratio, limit=limit,
            message=f"v_ratio {v_ratio:.2%} > limit {limit:.2%}",
        )

    @classmethod
    def r_total(cls, net_name, r_total, limit):
        return cls(
            kind=ViolationKind.R_TOTAL, net_name=net_name,
            r_total=r_total, limit=limit,
            message=f"R {r_total:.2f}Ω > limit {limit:.2f}Ω",
        )

    @classmethod
    def c_total(cls, net_name, c_total, limit):
        return cls(
            kind=ViolationKind.C_TOTAL, net_name=net_name,
            c_total=c_total, limit=limit,
            message=f"C {c_total:.2f}fF > limit {limit:.2f}fF",
        )

    @classmethod
    def tau_ps(cls, net_name, tau_ps, limit):
        return cls(
            kind=ViolationKind.TAU_PS, net_name=net_name,
            tau_ps=tau_ps, limit=limit,
            message=f"τ {tau_ps:.2f}ps > limit {limit:.2f}ps",
        )

    @classmethod
    def via_coverage(cls, net_name, via_coverage, limit):
        return cls(
            kind=ViolationKind.VIA_COVERAGE, net_name=net_name,
            via_coverage=via_coverage, limit=limit,
            message=f"via coverage {via_coverage:.2%} < limit {limit:.2%}",
        )

    @classmethod
    def missing_via(cls, net_name, x, y, layer):
        return cls(
            kind=ViolationKind.MISSING_VIA, net_name=net_name,
            x=x, y=y, message=f"missing via near ({x:.3f}, {y:.3f}) on {layer}",
        )

    @classmethod
    def similarity(cls, net_name, similarity_score, limit):
        return cls(
            kind=ViolationKind.SIMILARITY, net_name=net_name,
            similarity_score=similarity_score, limit=limit,
            message=f"similarity {similarity_score:.1f} < limit {limit:.1f}",
        )
