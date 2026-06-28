"""Tests for the slider<->tooltip sync shim.

In the compact 2-column redesign, the slider's always-visible tooltip replaces
the badge text inputs. There is no longer a two-way sync — the tooltip just
reads the slider's current `[low, high]` value directly. The shim is kept so
this module has a single named function to import (used elsewhere historically).
"""
from app.routing_config import _sync_slider_to_tooltip


def test_slider_to_tooltip_passes_through():
    """The shim returns the [low, high] list unchanged; Dash renders the tooltip."""
    assert _sync_slider_to_tooltip([0.05, 0.20]) == [0.05, 0.20]


def test_slider_to_tooltip_handles_int_values():
    """Integer-valued [low, high] is passed through unchanged."""
    assert _sync_slider_to_tooltip([0, 100]) == [0, 100]