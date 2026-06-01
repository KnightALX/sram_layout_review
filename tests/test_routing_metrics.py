"""Tests for routing metrics aggregator."""
import sys
sys.path.insert(0, '.')
import pytest
from review_engine import Point, Polygon, Via
from config.routing_thresholds import RoutingThresholds
from core.routing_metrics import compute_for_net, check_gates


def _rect(x1, y1, x2, y2, layer):
    return Polygon(points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)], layer=layer)


def _via(x, y, size=0.024, layer="via1"):
    s = size / 2
    return Polygon(
        points=[Point(x-s, y-s), Point(x+s, y-s), Point(x+s, y+s), Point(x-s, y+s)],
        layer=layer,
    )


def _tech_layers():
    return {
        "met1": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_space": 0.032},
        "met2": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.12,
                 "capacitance_per_um": 0.16, "min_space": 0.032},
        "via1": {"type": "via", "min_size": 0.024, "resistance": 1.0, "min_space": 0.024},
    }


def test_compute_for_net_returns_all_six_metrics():
    """Output must have all 6 metric families."""
    polys = [_rect(0, 0, 10, 1, "met1"), _rect(5, 0, 6, 10, "met2")]
    vias = [_via(5.5, 5)]
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("WL0", polys, vias, _tech_layers(), thresholds, golden_metrics=None)
    for key in ("h_len", "v_len", "h_ratio", "v_ratio", "dominant",
                "missing_via_count", "via_coverage", "missing_locations",
                "r_total", "c_total", "rc_product", "effective_tau_ps",
                "similarity_score", "deltas", "gate_pass", "gate_fail_reasons"):
        assert key in m, f"Missing key: {key}"


def test_wl_net_with_violation_fails_gate():
    """A 'horizontal-only' net should fail WL preset (expect V-dominant)."""
    polys = [_rect(0, 0, 10, 1, "met2")]  # only H
    m = compute_for_net("WL0", polys, [], _tech_layers(),
                        RoutingThresholds.for_preset("sram_7nm_wl"), golden_metrics=None)
    assert m["gate_pass"] is False
    assert any("h_ratio" in r or "v_ratio" in r for r in m["gate_fail_reasons"])


def test_golden_match_yields_100_similarity():
    """If golden_metrics == own metrics, similarity should be 100."""
    polys = [_rect(0, 0, 5, 1, "met1"), _rect(3, 0, 4, 5, "met2")]
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    m1 = compute_for_net("WL0", polys, [], _tech_layers(), thresholds, golden_metrics=None)
    m2 = compute_for_net("WL0", polys, [], _tech_layers(), thresholds,
                         golden_metrics={k: m1[k] for k in (
                             "h_ratio", "v_ratio", "total_len", "via_count",
                             "r_total", "c_total", "effective_tau_ps", "bbox_aspect"
                         )})
    assert m2["similarity_score"] == pytest.approx(100.0, abs=1.0)


def test_check_gates_returns_fail_reasons():
    metrics = {
        "h_ratio": 0.50, "v_ratio": 0.50,
        "r_total": 50.0, "c_total": 200.0, "effective_tau_ps": 30.0,
        "via_coverage": 0.50, "missing_via_count": 3,
        "similarity_score": 50.0,
    }
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    pass_, reasons = check_gates(metrics, thresholds)
    assert pass_ is False
    assert len(reasons) >= 4  # h_ratio, tau_ps, via_coverage, similarity all fail
