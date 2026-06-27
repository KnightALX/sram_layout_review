"""Tests for slider<->badge-input bidirectional sync.

These exercise the pure functions _sync_slider_to_badges and
_sync_badges_to_slider directly (without a Dash server)."""
from app.routing_config import _sync_slider_to_badges, _sync_badges_to_slider


def test_slider_to_badges():
    assert _sync_slider_to_badges([0.05, 0.20]) == (0.05, 0.20)


def test_badges_to_slider_valid():
    assert _sync_badges_to_slider(0.05, 0.20) == [0.05, 0.20]


def test_badges_to_slider_low_gt_high_returns_none():
    """low > high is invalid; the sync returns None (caller raises PreventUpdate)."""
    from dash.exceptions import PreventUpdate
    try:
        result = _sync_badges_to_slider(0.20, 0.05)
        assert result is None
    except PreventUpdate:
        pass


def test_badges_to_slider_none_returns_none():
    from dash.exceptions import PreventUpdate
    try:
        result = _sync_badges_to_slider(None, 0.20)
        assert result is None
    except PreventUpdate:
        pass