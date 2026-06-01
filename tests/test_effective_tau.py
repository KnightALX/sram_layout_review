"""Tests for effective-tau estimator."""
import sys
sys.path.insert(0, '.')
import pytest
from review_engine import Point, Polygon, WireSegment
from core.effective_tau import compute_effective_tau


def test_lumped_tau_simple():
    """tau = R * C for a single wire segment."""
    seg = WireSegment(
        start=Point(0, 0), end=Point(10, 0), width=0.1, layer="met1", net_name="N1"
    )
    # length = 10, R = r_sq * L / W = 0.1 * 10 / 0.1 = 10 ohm
    # C = c_per_um * L = 0.2 * 10 = 2.0 fF
    # tau = 10 * 2 = 20 fs = 0.02 ps
    tau = compute_effective_tau(
        segments=[seg], r_per_sq=0.1, c_per_um=0.2, method="lumped"
    )
    assert tau == pytest.approx(0.02, rel=1e-3)


def test_lumped_tau_multi_segment_sum():
    """tau = R_total * C_total for multi-segment net."""
    segs = [
        WireSegment(start=Point(0, 0), end=Point(5, 0), width=0.1, layer="met1", net_name="N"),
        WireSegment(start=Point(5, 0), end=Point(5, 5), width=0.1, layer="met2", net_name="N"),
    ]
    # Seg1: L=5, W=0.1, r=0.1 -> R=5, C=1 -> contrib=5
    # Seg2: same -> contrib=5
    # tau_total = (5+5) * (1+1) = 20 fs = 0.02 ps
    tau = compute_effective_tau(segs, 0.1, 0.2, method="lumped")
    assert tau == pytest.approx(0.02, rel=1e-3)


def test_elmore_tau_leq_2x_lumped():
    """Elmore delay <= 2 * lumped RC for tree of N segments."""
    segs = [
        WireSegment(start=Point(0, 0), end=Point(10, 0), width=0.1, layer="met1", net_name="N"),
    ]
    tau_l = compute_effective_tau(segs, 0.1, 0.2, method="lumped")
    tau_e = compute_effective_tau(segs, 0.1, 0.2, method="elmore")
    assert tau_e <= 2 * tau_l + 1e-9


def test_empty_segments_returns_zero():
    tau = compute_effective_tau([], 0.1, 0.2)
    assert tau == 0.0


def test_output_in_picoseconds():
    """Output should be in ps (not fs) by convention."""
    seg = WireSegment(
        start=Point(0, 0), end=Point(100, 0), width=1.0, layer="met1", net_name="N"
    )
    # R = 0.1 * 100 / 1.0 = 10, C = 0.2 * 100 = 20 -> tau = 200 fs = 0.2 ps
    tau = compute_effective_tau([seg], 0.1, 0.2)
    assert tau == pytest.approx(0.2, rel=1e-3)
