"""Aggregate the 6 routing metrics for a single net and check gates."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    from app.rc_model import RCModelConfig
    from config.routing_thresholds import RoutingThresholds
    from review_engine import Polygon, Via

from core.directional_analyzer import analyze_net_directional
from core.golden_similarity import compare_to_golden
from core.rc_calculator import compute_net_metrics_with_tau
from core.via_coverage import analyze_via_coverage
from core.visualization import is_via_layer


# Mapping from RoutingThresholds field name to the metrics dict key.
# threshold field names use r_ohm / c_ff / tau_ps (range-based),
# while metrics dict keys retain the original r_total / c_total /
# effective_tau_ps names (no need to rename inside the metrics module).
_THRESHOLD_TO_METRIC_KEY = {
    "h_ratio": "h_ratio",
    "v_ratio": "v_ratio",
    "r_ohm": "r_total",
    "c_ff": "c_total",
    "tau_ps": "effective_tau_ps",
    "via_coverage": "via_coverage",
    "similarity": "similarity_score",
}


def split_metal_via_polygons(polygons: List["Polygon"]) -> Tuple[List["Polygon"], List["Polygon"]]:
    """Split a mixed polygon list into metal shapes and via shapes.

    Shape files store all layers in one list. Routing review must pass
    metals and vias separately to analyze_via_coverage().
    """
    metals: List["Polygon"] = []
    vias: List["Polygon"] = []
    for poly in polygons:
        if is_via_layer(poly.layer):
            vias.append(poly)
        else:
            metals.append(poly)
    return metals, vias


def _bbox_aspect(polygons: List["Polygon"]) -> float:
    """Overall bbox aspect ratio (max(w,h)/min(w,h)), 1.0 if empty."""
    if not polygons:
        return 1.0
    xs = [p.bbox[0] for p in polygons] + [p.bbox[2] for p in polygons]
    ys = [p.bbox[1] for p in polygons] + [p.bbox[3] for p in polygons]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if min(w, h) <= 0:
        return 1.0
    return max(w, h) / min(w, h)


def _polygon_to_via(poly, tech_layers: Dict) -> "Via":
    """Convert a Polygon (used as a via) into a real Via object.

    Looks at the polygon's layer name (e.g. "via1") to determine the connecting
    metals. The `resistance` is a computed property on Via (based on size),
    so we don't need to (and can't) set it as an instance attribute.
    """
    from review_engine import Point, Via
    pts = poly.points
    cx = sum(p.x for p in pts) / len(pts)
    cy = sum(p.y for p in pts) / len(pts)
    layer_lower = poly.layer.lower()
    m = re.search(r"\d+", layer_lower)
    idx = int(m.group()) if m else 0
    upper = f"met{idx + 1}"
    lower = f"met{idx}"
    size = max(p.x for p in pts) - min(p.x for p in pts)
    return Via(
        position=Point(cx, cy),
        layer=poly.layer,
        upper_metal=upper,
        lower_metal=lower,
        size=size,
        net_name=poly.net_name or "",
    )


def coerce_vias(vias_in, tech_layers: Dict) -> list:
    """Accept a list of Via or Polygon; return a list of Via."""
    from review_engine import Via
    out = []
    for v in vias_in:
        if isinstance(v, Via):
            out.append(v)
        else:
            out.append(_polygon_to_via(v, tech_layers))
    return out


def check_gates(metrics: Dict[str, Any], thresholds: "RoutingThresholds",
                has_golden: bool = False) -> Tuple[List[str], List[str]]:
    """Each metric is checked against its [low, high] range.

    Returns:
        (hard_reasons, soft_reasons):
            - hard: r_ohm / c_ff / tau_ps / similarity / missing_via violations
            - soft: h_ratio / v_ratio / via_coverage violations
              (caller may bypass soft if has_golden=True and similarity passes)
    """
    hard_reasons: List[str] = []
    soft_reasons: List[str] = []

    # HARD: r_ohm / c_ff / tau_ps
    for thresh_key, display in [("r_ohm", "R"), ("c_ff", "C"), ("tau_ps", "\u03c4")]:
        rng = getattr(thresholds, thresh_key)
        measured = metrics[_THRESHOLD_TO_METRIC_KEY[thresh_key]]
        if not rng.contains(measured):
            d = rng.violation_direction(measured)
            hard_reasons.append(
                f"{display} {measured:.2f} {d} of [{rng.low}, {rng.high}]"
            )

    # SOFT: h_ratio / v_ratio / via_coverage
    for thresh_key in ("h_ratio", "v_ratio", "via_coverage"):
        rng = getattr(thresholds, thresh_key)
        measured = metrics[_THRESHOLD_TO_METRIC_KEY[thresh_key]]
        if not rng.contains(measured):
            d = rng.violation_direction(measured)
            soft_reasons.append(
                f"{thresh_key} {measured} {d} of [{rng.low}, {rng.high}]"
            )

    # Similarity (HARD)
    sim_rng = thresholds.similarity
    sim_measured = metrics[_THRESHOLD_TO_METRIC_KEY["similarity"]]
    if not sim_rng.contains(sim_measured):
        d = sim_rng.violation_direction(sim_measured)
        hard_reasons.append(
            f"similarity {sim_measured} {d} of "
            f"[{sim_rng.low}, {sim_rng.high}]"
        )

    # missing_via count check (preserved from old logic, always hard)
    miss = metrics.get("missing_via_count", 0)
    if miss and miss > 0:
        hard_reasons.append(f"missing_via {miss} > 0")

    return hard_reasons, soft_reasons


def _empty_result(net_name: str, reason: str) -> Dict[str, Any]:
    """Build a complete result dict for a net that has no polygons.

    Returned with `status="no_data"` and `gate_pass=False` so that the UI
    can distinguish "explicitly failed analysis" from "silently passed all
    gates because every value is zero". Every numeric field is populated
    so downstream code that doesn't check `status` still gets stable types.
    """
    return {
        "net_name": net_name,
        "status": "no_data",
        "h_len": 0.0,
        "v_len": 0.0,
        "h_ratio": 0.0,
        "v_ratio": 0.0,
        "dominant": "none",
        "missing_via_count": 0,
        "via_coverage": 0.0,
        "missing_locations": [],
        "r_total": 0.0,
        "c_total": 0.0,
        "rc_product": 0.0,
        "effective_tau_ps": 0.0,
        "total_length": 0.0,
        "total_len": 0.0,
        "via_count": 0,
        "similarity_score": 0.0,
        "deltas": {},
        "bbox_aspect": 1.0,
        "gate_pass": False,
        "gate_fail_reasons": [reason],
        "per_polygon_dir": [],
    }


def compute_for_net(
    net_name: str,
    polygons: List["Polygon"],
    vias: List,
    tech_layers: Dict,
    thresholds: "RoutingThresholds",
    golden_metrics: Dict[str, Any] = None,
    rc_model: "RCModelConfig | None" = None,
) -> Dict[str, Any]:
    """Compute the unified 6-metric dict for one net.

    Accepts vias as either Via objects or Polygons (Polygons are auto-converted).

    Args:
        net_name: Net name.
        polygons: All polygons of the net.
        vias: Via objects OR Polygons used as vias.
        tech_layers: Tech config dict.
        thresholds: RoutingThresholds for gate check.
        golden_metrics: Dict with 8 FEATURE_NAMES keys, or None.
        rc_model: Optional RCModelConfig.  When provided (and non-None),
            R/C/tau are computed using the user's process / EDA parameters
            (from the RC Prediction Tab / custom model).  When None (the
            default), the legacy `tech_layers` + calculate_net_rc + totals-based
            lumped τ is used — unifies default RC path so R/C/τ match
            Layout View Properties panel (see Task 2).

    Returns:
        Dict matching the 6-metric contract (with both `total_length` and
        `total_len` keys). Includes `status` field:
        - "ok": normal analysis result
        - "no_data": net had no polygons; `gate_pass=False` to avoid silent
          false positives (see _empty_result above)
    """
    # Guard: empty net must NOT silently pass all gates. A net that failed
    # to parse / has no shapes is a real problem the user needs to see, not
    # a "0Ω, 0fF, 100% similarity" virtual pass.
    if not polygons:
        return _empty_result(net_name, "empty net: no polygons to analyze")

    # Convert any polygon-vias to Via objects (for the rc_calculator)
    vias_for_rc = coerce_vias(vias or [], tech_layers)

    # 1. Directional
    dr = analyze_net_directional(polygons)
    # 2. Via coverage (analyze_via_coverage accepts polygons)
    vc = analyze_via_coverage(polygons, vias, min_via_per_overlap=1)
    # 3-4. RC + tau:
    # - Default (rc_model=None): use legacy tech_layers + calculate_net_rc + ohm_ff_to_ps
    #   (R/C/τ now identical to Layout View Properties panel / review_engine path
    #    for mono- and multi-layer nets).
    # - Only when an explicit RCModelConfig is passed: use custom model for R/C/τ.
    rc = compute_net_metrics_with_tau(
        net_name, polygons, vias_for_rc, tech_layers,
        rc_model=rc_model,
    )
    # 5. Similarity (only if golden given)
    aspect = _bbox_aspect(polygons)
    own_features = {
        "h_ratio": dr.h_ratio,
        "v_ratio": dr.v_ratio,
        "total_len": rc["total_length"],
        "via_count": rc["via_count"],
        "r_total": rc["r_total"],
        "c_total": rc["c_total"],
        "effective_tau_ps": rc["effective_tau_ps"],
        "bbox_aspect": aspect,
    }
    if golden_metrics:
        sim_score, deltas = compare_to_golden(golden_metrics, own_features)
    else:
        sim_score, deltas = 100.0, {k: 0.0 for k in own_features}
    # 6. Gate check
    metrics_for_gate = {
        **own_features,
        "missing_via_count": vc.missing_via_count,
        "via_coverage": vc.via_coverage,
        "similarity_score": sim_score,
    }
    gate_pass, fail_reasons = check_gates(
        metrics_for_gate, thresholds, has_golden=bool(golden_metrics)
    )

    return {
        "net_name": net_name,
        "status": "ok",
        "h_len": dr.h_len,
        "v_len": dr.v_len,
        "h_ratio": dr.h_ratio,
        "v_ratio": dr.v_ratio,
        "dominant": dr.dominant,
        "missing_via_count": vc.missing_via_count,
        "via_coverage": vc.via_coverage,
        "missing_locations": vc.missing_locations,
        "r_total": rc["r_total"],
        "c_total": rc["c_total"],
        "rc_product": rc["rc_product"],
        "effective_tau_ps": rc["effective_tau_ps"],
        "total_length": rc["total_length"],
        "total_len": rc["total_length"],   # alias for FEATURE_NAMES compatibility
        "via_count": rc["via_count"],
        "similarity_score": sim_score,
        "deltas": deltas,
        "bbox_aspect": aspect,
        "gate_pass": gate_pass,
        "gate_fail_reasons": fail_reasons,
        "per_polygon_dir": dr.per_polygon,  # for visualization
    }
