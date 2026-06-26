"""Unit tests for the new Range dataclass."""
import sys
sys.path.insert(0, '.')

import pytest
from config.routing_thresholds import Range


def test_range_contains_inclusive_bounds():
    rng = Range(0.0, 1.0)
    assert rng.contains(0.0) is True
    assert rng.contains(1.0) is True
    assert rng.contains(0.5) is True


def test_range_contains_outside():
    rng = Range(0.0, 1.0)
    assert rng.contains(-0.1) is False
    assert rng.contains(1.1) is False


def test_range_single_point_allowed():
    """low == high means a single-point range (e.g. [1.0, 1.0])."""
    rng = Range(1.0, 1.0)
    assert rng.contains(1.0) is True
    assert rng.contains(0.99) is False
    assert rng.contains(1.01) is False


def test_range_rejects_low_gt_high():
    with pytest.raises(ValueError, match="low.*high"):
        Range(2.0, 1.0)


def test_violation_direction():
    rng = Range(0.0, 1.0)
    assert rng.violation_direction(-0.1) == "low"
    assert rng.violation_direction(1.1) == "high"
    assert rng.violation_direction(0.5) is None
    # boundary: at low or high, no violation
    assert rng.violation_direction(0.0) is None
    assert rng.violation_direction(1.0) is None


def test_range_is_frozen():
    """Range is immutable; attribute assignment raises FrozenInstanceError."""
    rng = Range(0.0, 1.0)
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        rng.low = 5.0