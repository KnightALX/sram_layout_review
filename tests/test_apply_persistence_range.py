"""Tests for Apply + persistence with the new 14-value Range field structure.

These exercise _validate_apply with 14 input values (7 fields * (low, high))
instead of the legacy 7 single-value thresholds.
"""
import pytest

from app.routing_config import _validate_apply
from config.routing_thresholds import RoutingThresholds


def test_validate_apply_with_range_values():
    from app.routing_config import _validate_apply
    vals = (0.0, 0.15, 0.0, 1.0, 0.0, 100.0, 0.0, 500.0, 0.0, 12.5, 0.85, 1.0, 80.0, 100.0)
    result, err = _validate_apply(vals)
    assert err is None
    assert result is not None
    assert result.h_ratio.high == 0.15
    assert result.h_ratio.low == 0.0


def test_validate_apply_low_gt_high_rejected():
    from app.routing_config import _validate_apply
    vals = (0.20, 0.10, 0.0, 1.0, 0.0, 100.0, 0.0, 500.0, 0.0, 12.5, 0.85, 1.0, 80.0, 100.0)
    result, err = _validate_apply(vals)
    assert result is None
    assert err is not None
