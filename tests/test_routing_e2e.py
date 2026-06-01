"""End-to-end test: load shapes → run routing review → check all 6 metrics."""
import os
import sys
sys.path.insert(0, '.')
from review_engine import Polygon, Point
from config.routing_thresholds import RoutingThresholds
from core.routing_metrics import compute_for_net


def _tech():
    return {
        "met1": {"type": "metal", "resistance_per_sq": 0.15, "capacitance_per_um": 0.20, "min_width": 0.032, "min_space": 0.032},
        "met2": {"type": "metal", "resistance_per_sq": 0.12, "capacitance_per_um": 0.16, "min_width": 0.032, "min_space": 0.032},
    }


def test_wordline_wl_preset_h_dominant_passes():
    """A V-dominant net on WL preset should pass direction gate."""
    # 5μm vertical, 0.5μm horizontal — V-dominant (typical WL layout)
    polys = [Polygon(points=[Point(0,0), Point(0.5,0), Point(0.5,5), Point(0,5)], layer="met1")]
    t = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("WL0", polys, [], _tech(), t, golden_metrics=None)
    assert m["dominant"] == "V"
    assert m["gate_pass"] is True
    # All 6 metrics present
    for k in ("h_ratio", "v_ratio", "missing_via_count", "via_coverage",
             "r_total", "c_total", "effective_tau_ps",
             "similarity_score", "gate_pass"):
        assert k in m


def test_io_bl_preset_v_dominant_passes():
    """An H-dominant net on IO preset should pass direction gate."""
    polys = [Polygon(points=[Point(0,0), Point(5,0), Point(5,0.5), Point(0,0.5)], layer="met2")]
    t = RoutingThresholds.for_preset("sram_5nm_io_bl")
    m = compute_for_net("BL0", polys, [], _tech(), t, golden_metrics=None)
    assert m["dominant"] == "H"
    assert m["gate_pass"] is True


def test_long_wire_fails_tau_gate():
    """A long wire (1000μm) should fail the τ gate."""
    polys = [Polygon(points=[Point(0,0), Point(1000,0), Point(1000,0.1), Point(0,0.1)], layer="met1")]
    t = RoutingThresholds.for_preset("sram_7nm_wl")  # max_tau_ps=12.5
    m = compute_for_net("WL0", polys, [], _tech(), t, golden_metrics=None)
    assert any("τ" in r or "tau" in r for r in m["gate_fail_reasons"])
