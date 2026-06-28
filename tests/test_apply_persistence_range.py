"""Tests for Apply + persistence with the 7-pair RangeSlider value structure.

After the compact 2-column redesign, each RangeSlider exposes its value as a
`[low, high]` list. There are no separate legacy "low input" / "high input"
text badges anymore. So _validate_apply now receives 7 `[low, high]` pairs
(not 14 flat numbers).
"""
import pytest

from app.routing_config import _validate_apply
from config.routing_thresholds import RoutingThresholds


def test_validate_apply_with_range_values():
    from app.routing_config import _validate_apply
    # 7 [low, high] pairs for h_ratio, v_ratio, r_ohm, c_ff, tau_ps, via_coverage, similarity
    pairs = [
        [0.0, 0.15],
        [0.0, 1.0],
        [0.0, 100.0],
        [0.0, 500.0],
        [0.0, 12.5],
        [0.85, 1.0],
        [80.0, 100.0],
    ]
    result, err = _validate_apply(pairs)
    assert err is None
    assert result is not None
    assert result.h_ratio.high == 0.15
    assert result.h_ratio.low == 0.0


def test_validate_apply_low_gt_high_rejected():
    from app.routing_config import _validate_apply
    # h_ratio.low=0.20 > h_ratio.high=0.10 -> invalid
    pairs = [
        [0.20, 0.10],
        [0.0, 1.0],
        [0.0, 100.0],
        [0.0, 500.0],
        [0.0, 12.5],
        [0.85, 1.0],
        [80.0, 100.0],
    ]
    result, err = _validate_apply(pairs)
    assert result is None
    assert err is not None
