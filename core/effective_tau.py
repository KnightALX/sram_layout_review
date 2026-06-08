"""Effective-tau (delay) estimator for routing.

Supported methods:
- "lumped":      tau = R_total * C_total                  (first-order, conservative)
- "elmore":     tau ≈ 0.5 * R_total * C_total            (Elmore for single chain)
- "lumped_pi":  alias of "lumped" (π-segment)            (used by RC Prediction Tab)
- "t_model":    tau = R_total * C_total / 2              (T-segment, symmetric driver)
- "distributed_5": 5-segment ladder — accurate for long wires
                 tau ≈ R * C * (N² - 1) / (6 * N²) where N is segment count

Output unit: picoseconds (ps). Inputs in um/fF/ohm.
"""
from __future__ import annotations
import math
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
    n_segments: int = 5,
) -> float:
    """Compute effective tau for a set of wire segments.

    Args:
        segments: Wire segments in the net (any order).
        r_per_sq: Sheet resistance in ohm/sq.
        c_per_um: Capacitance per um in fF/um.
        method: One of "lumped", "elmore", "lumped_pi", "t_model",
                "distributed_5". Unknown methods raise ValueError.
        n_segments: Segment count for the distributed_5 model (must be >= 2).

    Returns:
        Effective tau in picoseconds.
    """
    if not segments:
        return 0.0

    rc_list = [_seg_rc(s, r_per_sq, c_per_um) for s in segments]
    r_total = sum(rc[0] for rc in rc_list)
    c_total = sum(rc[1] for rc in rc_list)

    method_norm = (method or "lumped").lower()
    if method_norm in ("lumped", "lumped_pi"):
        # Standard π-model: tau = R * C (worst-case; driver at one end)
        tau_fs = r_total * c_total
    elif method_norm in ("elmore", "t_model"):
        # T-model / Elmore: tau = R * C / 2 (driver at the center)
        tau_fs = 0.5 * r_total * c_total
    elif method_norm == "distributed_5":
        # Distributed RC ladder with N segments: tau = R * C * (N² - 1) / (6 * N²)
        # As N → ∞: tau → R * C / 6 (asymptotic limit)
        n = max(int(n_segments), 2)
        factor = (n * n - 1) / (6.0 * n * n)
        tau_fs = r_total * c_total * factor
    else:
        raise ValueError(
            f"Unknown tau method: {method!r}. "
            "Expected one of: lumped, lumped_pi, elmore, t_model, distributed_5"
        )

    return tau_fs * FS_TO_PS
