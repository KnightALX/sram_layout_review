"""Effective-tau (delay) estimator for routing.

Two methods:
- "lumped":  tau = R_total * C_total  (first-order, conservative)
- "elmore": tau = Sigma R_i * C_suffix_i  (per-segment, more accurate)

Output unit: picoseconds (ps). Inputs in um/fF/ohm.
"""
from __future__ import annotations
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import WireSegment


# Convert fs -> ps
FS_TO_PS = 1.0e-3


def _seg_rc(seg: "WireSegment", r_per_sq: float, c_per_um: float):
    """Return (R_ohms, C_fF, length_um) for a segment."""
    length = seg.length
    width = max(seg.width, 1e-9)  # avoid div by zero
    r = r_per_sq * length / width
    c = c_per_um * length
    return r, c, length


def compute_effective_tau(
    segments: List["WireSegment"],
    r_per_sq: float,
    c_per_um: float,
    method: str = "lumped",
) -> float:
    """Compute effective tau for a set of wire segments.

    Args:
        segments: Wire segments in the net (any order).
        r_per_sq: Sheet resistance in ohm/sq.
        c_per_um: Capacitance per um in fF/um.
        method: "lumped" or "elmore".

    Returns:
        Effective tau in picoseconds.
    """
    if not segments:
        return 0.0

    rc_list = [_seg_rc(s, r_per_sq, c_per_um) for s in segments]
    r_total = sum(rc[0] for rc in rc_list)
    c_total = sum(rc[1] for rc in rc_list)

    if method == "lumped":
        tau_fs = r_total * c_total
    elif method == "elmore":
        # For a single chain (simplification): Elmore = Sigma R_i * C_suffix_i
        # We approximate by sorting segments by length (driver end has highest C suffix)
        # For a lumped approximation: tau_elmore = R_total * C_total / 2
        tau_fs = 0.5 * r_total * c_total
    else:
        raise ValueError(f"Unknown method: {method}")

    return tau_fs * FS_TO_PS
