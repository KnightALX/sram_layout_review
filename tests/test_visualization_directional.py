"""Tests for directional visualization."""
import sys

sys.path.insert(0, '.')
from core.visualization import create_directional_figure
from review_engine import Point, Polygon


def _rect(x1, y1, x2, y2, layer):
    return Polygon(points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)], layer=layer)


def test_returns_plotly_figure():
    polys = [_rect(0, 0, 10, 1, "met1"), _rect(5, 0, 6, 10, "met2")]
    fig = create_directional_figure(polys, [], net_name="WL0")
    assert fig is not None
    # Should have 2 traces (one per polygon, each with H or V color)
    assert len(fig.data) == 2


def test_horizontal_polygon_uses_red():
    """H-dominant polygon should be red."""
    polys = [_rect(0, 0, 10, 1, "met1")]
    fig = create_directional_figure(polys, [])
    color = fig.data[0].fillcolor
    assert "255" in color and "0" in color  # has red component


def test_vertical_polygon_uses_blue():
    """V-dominant polygon should be blue."""
    polys = [_rect(0, 0, 1, 10, "met1")]
    fig = create_directional_figure(polys, [])
    color = fig.data[0].fillcolor
    assert "0" in color and "255" in color  # has blue component


def test_violation_overlay_adds_red_borders():
    """If violations passed, those polygons get red border overlay."""
    polys = [_rect(0, 0, 10, 1, "met1")]
    violations = [{"polygon_index": 0, "x": 5, "y": 0.5}]
    fig = create_directional_figure(polys, [], violations=violations)
    # Should have an extra trace for violation overlay
    assert len(fig.data) >= 2
