"""Tests for slider row constraint detection and logic-row annotation."""
from app.routing_config import _compute_constraint_status


def test_constraint_status_valid_normal_range():
    """A normal, non-narrow range is 'valid'."""
    assert _compute_constraint_status(0.1, 0.2, 0.0, 1.0) == "valid"


def test_constraint_status_invalid_low_greater_than_high():
    """Low > High is logically impossible → 'invalid'."""
    assert _compute_constraint_status(0.5, 0.2, 0.0, 1.0) == "invalid"


def test_constraint_status_warning_zero_width():
    """Low == High (zero width) → 'warning' (no value can be compliant)."""
    assert _compute_constraint_status(0.5, 0.5, 0.0, 1.0) == "warning"


def test_constraint_status_warning_narrow_range():
    """Range narrower than 5% of full domain → 'warning'."""
    # Full domain 0..1, 5% = 0.05; width 0.04 < 0.05 → warning
    assert _compute_constraint_status(0.5, 0.54, 0.0, 1.0) == "warning"


def test_constraint_status_valid_at_5_percent_boundary():
    """Exactly 5% width → still 'valid' (boundary inclusive)."""
    # Width 0.05 of full 0..1 → valid
    assert _compute_constraint_status(0.5, 0.55, 0.0, 1.0) == "valid"


def test_constraint_status_none_inputs_default_valid():
    """None values (initial render before user interaction) → 'valid'."""
    assert _compute_constraint_status(None, None, 0.0, 1.0) == "valid"
    assert _compute_constraint_status(None, 0.5, 0.0, 1.0) == "valid"
    assert _compute_constraint_status(0.5, None, 0.0, 1.0) == "valid"
