"""Tests for H/V directional analyzer."""
import sys

import pytest

sys.path.insert(0, '.')
from core.directional_analyzer import analyze_net_directional
from review_engine import Point, Polygon


def _rect(x1, y1, x2, y2, layer="met1"):
    return Polygon(
        points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)],
        layer=layer,
    )


def test_horizontal_dominant_net():
    """A net with only horizontal segments has h_ratio=1.0."""
    polys = [_rect(0, 0, 10, 1, "met2"), _rect(0, 5, 8, 6, "met2")]
    r = analyze_net_directional(polys)
    assert r.h_len == pytest.approx(18.0, rel=1e-6)
    assert r.v_len == pytest.approx(0.0, rel=1e-6)
    assert r.h_ratio == pytest.approx(1.0, rel=1e-6)
    assert r.dominant == "H"


def test_vertical_dominant_net():
    """A net with only vertical segments has v_ratio=1.0."""
    polys = [_rect(0, 0, 1, 10, "met1"), _rect(5, 0, 6, 8, "met1")]
    r = analyze_net_directional(polys)
    assert r.v_len == pytest.approx(18.0, rel=1e-6)
    assert r.v_ratio == pytest.approx(1.0, rel=1e-6)
    assert r.dominant == "V"


def test_mixed_routing_50_50():
    """A net with equal H and V has h_ratio=v_ratio=0.5."""
    polys = [_rect(0, 0, 10, 1, "met2"), _rect(5, 0, 6, 10, "met1")]
    r = analyze_net_directional(polys)
    assert r.h_len == pytest.approx(10.0, rel=1e-6)
    assert r.v_len == pytest.approx(10.0, rel=1e-6)
    assert r.h_ratio == pytest.approx(0.5, rel=1e-6)
    assert r.v_ratio == pytest.approx(0.5, rel=1e-6)


def test_diagonal_edges_classified_by_dominant_axis():
    """A 45° edge is split half to H, half to V (per-axis decomposition)."""
    # Triangle: (0,0)-(10,0)-(0,10) — edge 0-1 is H (10), edge 1-2 is diagonal (14.14, Δx=10,Δy=10),
    # edge 2-0 is V (10).  Edge 1-2 contributes 10/14.14 to H and 10/14.14 to V.
    p1 = Point(0, 0)
    p2 = Point(10, 0)
    p3 = Point(0, 10)
    tri = Polygon(points=[p1, p2, p3], layer="met1")
    r = analyze_net_directional([tri])
    assert r.h_len == pytest.approx(10 + 14.14/2, rel=1e-2)
    assert r.v_len == pytest.approx(10 + 14.14/2, rel=1e-2)


def test_empty_polygons_returns_zero():
    r = analyze_net_directional([])
    assert r.h_len == 0.0
    assert r.v_len == 0.0
    assert r.h_ratio == 0.0
    assert r.v_ratio == 0.0
    assert r.dominant == "H"  # default


def test_per_polygon_classification():
    """Result includes per-polygon classification list for visualization."""
    polys = [_rect(0, 0, 10, 1, "met2"), _rect(5, 0, 6, 10, "met1")]
    r = analyze_net_directional(polys)
    assert len(r.per_polygon) == 2
    assert r.per_polygon[0]["class"] == "H"
    assert r.per_polygon[1]["class"] == "V"
    assert r.per_polygon[0]["polygon_index"] == 0
