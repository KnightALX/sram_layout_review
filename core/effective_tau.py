"""Effective-tau (delay) estimator for routing.

Supported methods:
- "lumped":      tau = R_total * C_total                  (first-order, conservative)
- "elmore":     tau ≈ 0.5 * R_total * C_total            (Elmore for single chain)
- "lumped_pi":  alias of "lumped" (π-segment)            (used by RC Prediction Tab)
- "t_model":    tau = R_total * C_total / 2              (T-segment, symmetric driver)
- "distributed_5": 5-segment ladder — accurate for long wires
                 tau ≈ R * C * (N² - 1) / (6 * N²) where N is segment count

Unit convention (shared across Legacy + Routing pipelines):
  R in Ω, C in fF  →  numeric product equals femtoseconds
  τ(ps) = R × C × OHM_FF_TO_PS × model_factor
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from review_engine import WireSegment

# Ω·fF numeric product is femtoseconds; multiply by 1e-3 for picoseconds.
OHM_FF_TO_PS = 1.0e-3
FS_TO_PS = OHM_FF_TO_PS  # backward-compat alias

# Match WireSegment.capacitance() default fringe term (fF/µm).
DEFAULT_FRINGE_C = 0.1


def tau_model_factor(method: str, n_segments: int = 5) -> float:
    """Return the dimensionless delay-line factor for a tau model."""
    method_norm = (method or "lumped").lower()
    if method_norm in ("lumped", "lumped_pi"):
        return 1.0
    if method_norm in ("elmore", "t_model"):
        return 0.5
    if method_norm == "distributed_5":
        n = max(int(n_segments), 2)
        return (n * n - 1) / (6.0 * n * n)
    raise ValueError(
        f"Unknown tau method: {method!r}. "
        "Expected one of: lumped, lumped_pi, elmore, t_model, distributed_5"
    )


def ohm_ff_to_ps(
    r_ohm: float,
    c_ff: float,
    method: str = "lumped",
    n_segments: int = 5,
) -> float:
    """Convert total R (Ω) and C (fF) to effective τ in picoseconds."""
    if r_ohm <= 0 or c_ff <= 0:
        return 0.0
    factor = tau_model_factor(method, n_segments)
    return r_ohm * c_ff * factor * OHM_FF_TO_PS


def _segment_capacitance_ff(
    length_um: float,
    width_um: float,
    c_per_um: float,
    fringe_c: float = DEFAULT_FRINGE_C,
) -> float:
    """Total wire C (fF) — area + fringe, matching WireSegment.capacitance()."""
    area_c = c_per_um * length_um
    fringe = fringe_c * 2.0 * (length_um + width_um)
    return area_c + fringe


def _seg_rc(
    seg: "WireSegment",
    r_per_sq: float,
    c_per_um: float,
    fringe_c: float = DEFAULT_FRINGE_C,
):
    """Return (R_ohms, C_fF) for a segment using the same C model as calculate_net_rc."""
    length = seg.length
    width = max(seg.width, 1e-9)
    r = r_per_sq * length / width
    if hasattr(seg, "capacitance"):
        c = seg.capacitance(c_per_um, fringe_c)
    else:
        c = _segment_capacitance_ff(length, width, c_per_um, fringe_c)
    return r, c


def compute_effective_tau(
    segments: List["WireSegment"],
    r_per_sq: float,
    c_per_um: float,
    method: str = "lumped",
    n_segments: int = 5,
    fringe_c: float = DEFAULT_FRINGE_C,
) -> float:
    """Compute effective tau from wire segments (sums per-segment R/C first)."""
    if not segments:
        return 0.0

    r_total = 0.0
    c_total = 0.0
    for seg in segments:
        r, c = _seg_rc(seg, r_per_sq, c_per_um, fringe_c)
        r_total += r
        c_total += c

    return ohm_ff_to_ps(r_total, c_total, method, n_segments)
