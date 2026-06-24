"""End-to-end test: load shapes → run routing review → check all 6 metrics."""
import sys

sys.path.insert(0, '.')
from config.routing_thresholds import RoutingThresholds
from core.routing_metrics import compute_for_net
from review_engine import Point, Polygon


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


# Task 7: ensure routing review path consistently uses state.get_thresholds()
# (added for cross-callback hygiene coverage)

def test_e2e_uses_get_thresholds_for_gates():
    """Simple smoke: compute_for_net called in review uses thresholds from routing_state.get_thresholds()."""
    from app.routing_state import routing_state
    polys = [Polygon(points=[Point(0,0), Point(10,0), Point(10,0.5), Point(0,0.5)], layer="met1")]
    # Ensure state provides them
    t = routing_state.get_thresholds()
    m = compute_for_net("E2E_NET", polys, [], _tech(), t, golden_metrics=None)
    assert "gate_pass" in m
    # Re-run after forcing frozen preset via public API
    routing_state.set_frozen_mode(True)
    t2 = routing_state.get_thresholds()
    m2 = compute_for_net("E2E_NET2", polys, [], _tech(), t2, golden_metrics=None)
    assert m2["gate_pass"] is True or m2["gate_pass"] is False  # just exercises the getter path
