"""Single source-of-truth wrapper for per-net RC/tau summary.

Wraps `core.routing_metrics.compute_for_net` and normalizes field names
plus units so that Layout View Properties and Routing Review cards/table
display identical numbers for the same net.

Units contract (UI consumers may rely on these):
  - r_total_ohm     : ohms
  - c_total_ff      : femtofarads
  - tau_elmore_ps   : picoseconds (Elmore delay, 0.5 * R * C)
  - tau_naive_ps    : picoseconds (R*C without Elmore, full lumped value)
  - h_ratio, v_ratio: 0..1
  - via_coverage    : 0..1
  - similarity_score: 0..100
  - missing_via_count: int

Relationship: tau_naive_ps ≈ 2 × tau_elmore_ps (Elmore halves the lumped
factor for a single RC chain). Both fields are in ps so they can be
displayed side-by-side at the same order of magnitude.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.effective_tau import OHM_FF_TO_PS
from core.routing_metrics import compute_for_net


def summarize_net(
    net_name: str,
    polygons: List,
    vias: List,
    tech: Dict[str, Dict[str, Any]],
    thresholds: "RoutingThresholds",
    golden_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute normalized per-net RC summary.

    Returns a dict with stable field names and units. When the net has
    no polygons, returns status='no_data' with zeroed numerics and
    gate_pass=False.
    """
    if not polygons:
        return {
            "net_name": net_name,
            "r_total_ohm": 0.0,
            "c_total_ff": 0.0,
            "tau_elmore_ps": 0.0,
            "tau_naive_ps": 0.0,
            "h_ratio": 0.0,
            "v_ratio": 0.0,
            "missing_via_count": 0,
            "via_coverage": 0.0,
            "similarity_score": 100.0,
            "dominant": "balanced",
            "status": "no_data",
        }

    m = compute_for_net(net_name, polygons, vias, tech, thresholds, golden_metrics)
    r_total = float(m.get("r_total", 0.0))
    c_total = float(m.get("c_total", 0.0))
    tau_elmore = float(m.get("effective_tau_ps", 0.0))

    return {
        "net_name": net_name,
        "r_total_ohm": r_total,
        "c_total_ff": c_total,
        "tau_elmore_ps": tau_elmore,
        # tau_naive = R*C without Elmore correction. Convert Ω·fF numeric
        # product to picoseconds via OHM_FF_TO_PS so the field name and the
        # actual unit agree (was historically left as fs by mistake).
        # Physically: tau_naive ≈ 2 × tau_elmore_ps (Elmore halves the lumped
        # factor for single-chain wires), so both stay in the same magnitude.
        "tau_naive_ps": r_total * c_total * OHM_FF_TO_PS,
        "h_ratio": float(m.get("h_ratio", 0.0)),
        "v_ratio": float(m.get("v_ratio", 0.0)),
        "missing_via_count": int(m.get("missing_via_count", 0)),
        "via_coverage": float(m.get("via_coverage", 0.0)),
        "similarity_score": float(m.get("similarity_score", 100.0)),
        "dominant": m.get("dominant", "balanced"),
        "status": "ok",
    }