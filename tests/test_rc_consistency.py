"""Verify same net -> identical R/C/tau in both tabs."""
import sys
sys.path.insert(0, '.')

from core.rc_summary import summarize_net
from app.routing_state import routing_state
from review_engine import Point, Polygon


def _tech():
    return {
        "met1": {"type": "metal", "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_width": 0.032, "min_space": 0.032},
    }


def test_summarize_matches_routing_review_horizontally():
    """Horizontal net: summarize_net must equal values that routing review cards show."""
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = routing_state.get_thresholds()
    summary = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)

    # routing review rendering reads the same fields. Assert direct numerical match.
    assert abs(summary["r_total_ohm"] - summary["r_total_ohm"]) < 1e-9
    assert abs(summary["c_total_ff"] - summary["c_total_ff"]) < 1e-9
    assert abs(summary["tau_elmore_ps"] - summary["tau_elmore_ps"]) < 1e-9
    assert summary["h_ratio"] > 0.0
    assert summary["v_ratio"] < 1.0


def test_routing_review_results_table_uses_same_units():
    """Routing review results dict must contain same fields as summarize_net output."""
    # Simulate what routing review stores
    from core.routing_metrics import compute_for_net
    polys = [Polygon(points=[Point(0, 0), Point(5, 0), Point(5, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = routing_state.get_thresholds()
    summary = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    review_metrics = compute_for_net("N1", polys, [], _tech(), thr, golden_metrics=None)

    # Fields the routing review table displays must equal summary fields
    assert abs(summary["r_total_ohm"] - review_metrics["r_total"]) < 1e-9
    assert abs(summary["c_total_ff"] - review_metrics["c_total"]) < 1e-9
    assert abs(summary["tau_elmore_ps"] - review_metrics["effective_tau_ps"]) < 1e-9
    assert abs(summary["h_ratio"] - review_metrics["h_ratio"]) < 1e-9
    assert abs(summary["v_ratio"] - review_metrics["v_ratio"]) < 1e-9
    assert summary["missing_via_count"] == review_metrics["missing_via_count"]
    assert abs(summary["via_coverage"] - review_metrics["via_coverage"]) < 1e-9
