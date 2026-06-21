"""Tests for via coverage analyzer."""
import sys

sys.path.insert(0, '.')
import pytest

from core.via_coverage import analyze_via_coverage
from review_engine import Point, Polygon


def _rect(x1, y1, x2, y2, layer):
    return Polygon(points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)], layer=layer)


def _via(x, y, size=0.024, layer="via1"):
    """Helper: build a via-like polygon."""
    s = size / 2
    return Polygon(
        points=[Point(x-s, y-s), Point(x+s, y-s), Point(x+s, y+s), Point(x-s, y+s)],
        layer=layer,
    )


def test_full_coverage_no_missing():
    """Overlap fully covered by vias → coverage=1.0, missing=0."""
    met1 = _rect(0, 0, 2, 2, "met1")
    met2 = _rect(0, 0, 2, 2, "met2")
    vias = [_via(0.5, 0.5), _via(1.5, 1.5), _via(1.5, 0.5), _via(0.5, 1.5)]
    r = analyze_via_coverage([met1, met2], vias, min_via_per_overlap=1)
    assert r.missing_via_count == 0
    assert r.via_coverage == pytest.approx(1.0, rel=1e-2)


def test_partial_coverage_detects_missing():
    """Only 1 via in a 2x2 overlap → coverage low, missing=1."""
    met1 = _rect(0, 0, 2, 2, "met1")
    met2 = _rect(0, 0, 2, 2, "met2")
    vias = [_via(0.5, 0.5)]  # only 1 via in large overlap
    r = analyze_via_coverage([met1, met2], vias, min_via_per_overlap=4, min_size=0.024)
    # Overlap area = 4.0, via area = 0.024^2 = 0.000576
    # coverage = 0.000576 / 4 = 0.000144 (very low)
    # But more importantly, only 1 via where 4 expected → missing
    assert r.missing_via_count >= 1
    assert r.via_coverage < 0.5
    assert len(r.missing_locations) >= 1


def test_no_overlap_means_no_vias_needed():
    """If metal layers don't overlap, no via is required."""
    met1 = _rect(0, 0, 1, 1, "met1")
    met2 = _rect(5, 5, 6, 6, "met2")  # far apart
    r = analyze_via_coverage([met1, met2], [], min_via_per_overlap=1)
    assert r.missing_via_count == 0
    assert r.via_coverage == 1.0  # trivially "covered" — no requirement


def test_no_polygons_returns_full_coverage():
    r = analyze_via_coverage([], [], min_via_per_overlap=1)
    assert r.missing_via_count == 0
    assert r.via_coverage == 1.0
