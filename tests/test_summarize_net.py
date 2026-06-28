"""Tests for the single RC source-of-truth wrapper."""
import sys
sys.path.insert(0, '.')

import pytest

from core.rc_summary import summarize_net
from review_engine import Point, Polygon
from config.routing_thresholds import RoutingThresholds


def _tech():
    return {
        "met1": {"type": "metal", "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_width": 0.032, "min_space": 0.032},
        "met2": {"type": "metal", "resistance_per_sq": 0.12,
                 "capacitance_per_um": 0.16, "min_width": 0.032, "min_space": 0.032},
        "via1": {"type": "via"},
    }


def test_summarize_returns_required_fields():
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = RoutingThresholds.for_preset("sram_7nm_wl")
    out = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    for key in ("net_name", "r_total_ohm", "c_total_ff", "tau_elmore_ps",
                "tau_naive_ps", "h_ratio", "v_ratio", "missing_via_count",
                "via_coverage", "similarity_score", "dominant", "status"):
        assert key in out, f"missing key: {key}"


def test_summarize_horizontal_net_dominant_h():
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    thr = RoutingThresholds.for_preset("sram_7nm_wl")
    out = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    assert out["dominant"] == "H"
    assert out["h_ratio"] > out["v_ratio"]


def test_summarize_vertical_net_dominant_v():
    polys = [Polygon(points=[Point(0, 0), Point(0.5, 0), Point(0.5, 5), Point(0, 5)],
                     layer="met1")]
    thr = RoutingThresholds.for_preset("sram_7nm_wl")
    out = summarize_net("N1", polys, [], _tech(), thr, golden_metrics=None)
    assert out["dominant"] == "V"


def test_summarize_empty_polys_no_data():
    out = summarize_net("EMPTY", [], [], _tech(),
                        RoutingThresholds.for_preset("sram_7nm_wl"),
                        golden_metrics=None)
    assert out["status"] == "no_data"


def test_summarize_units_ohm_ff_ps():
    """R in ohm, C in fF, tau in ps - sanity check on a 10um met1 wire.

    The Routing Review path uses the lumped τ method (factor 1.0), so
    `tau_elmore_ps` (legacy field name; effectively lumped) is numerically
    equal to `tau_naive_ps` (= R × C × 1e-3). The two fields exist so the
    UI can show the same number under both legacy "tau_rc"/"tau_naive"
    column names without order-of-magnitude mismatch.
    """
    polys = [Polygon(points=[Point(0, 0), Point(10, 0), Point(10, 0.5), Point(0, 0.5)],
                     layer="met1")]
    out = summarize_net("N1", polys, [], _tech(),
                        RoutingThresholds.for_preset("sram_7nm_wl"),
                        golden_metrics=None)
    # 10um wire, 0.5um wide met1, R_per_sq=0.15 ohm/sq
    # L/W = 10/0.5 = 20 squares, R = 0.15 * 20 = 3.0 ohm
    assert 2.5 < out["r_total_ohm"] < 3.5
    # C = 0.20 fF/um * 10um (area) + fringe_c=0.1*2*(L+W)
    #   = 2.0 + 0.1*2*(10+0.5) = 2.0 + 2.1 = 4.1 fF
    # (WireSegment.capacitance includes both area and fringe terms)
    assert 3.5 < out["c_total_ff"] < 4.5
    # tau_naive_ps = R(Ω) × C(fF) × 1e-3 (Ω·fF→ps conversion).
    # 3.0 Ω × 4.1 fF = 12.3 fs → 0.0123 ps.
    assert 0.010 < out["tau_naive_ps"] < 0.014
    # tau_elmore_ps uses the same Ω·fF→ps conversion under the default
    # "lumped" method (factor = 1.0, see core/effective_tau.py), so it
    # equals tau_naive_ps within numerical tolerance.
    assert out["tau_elmore_ps"] == pytest.approx(out["tau_naive_ps"], rel=1e-9)
    # And both tau values must equal R × C × 1e-3 directly, proving the
    # order-of-magnitude fix (was historically left in fs by mistake).
    expected_ps = out["r_total_ohm"] * out["c_total_ff"] * 1e-3
    assert out["tau_naive_ps"] == pytest.approx(expected_ps, rel=1e-9)