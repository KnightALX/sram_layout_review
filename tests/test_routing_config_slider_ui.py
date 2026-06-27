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


def test_logic_row_content_valid_uses_math_notation():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.10, 0.15, "{:.2f}", "valid")
    s = str(children)
    assert "\u5408\u89c4" in s
    assert "0.10" in s
    assert "0.15" in s
    assert "\u2264" in s  # ≤
    assert "\u533a\u95f4\u5bbd\u5ea6" in s
    assert "0.05" in s  # width = high - low


def test_logic_row_content_invalid_shows_low_greater_than_high():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.50, 0.20, "{:.2f}", "invalid")
    s = str(children)
    assert "Low" in s
    assert "0.50" in s
    assert "High" in s
    assert "0.20" in s
    assert "\u4e0d\u5408\u6cd5" in s or "\u91cd\u65b0\u8bbe\u7f6e" in s


def test_logic_row_content_warning_zero_width():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.50, 0.50, "{:.2f}", "warning")
    s = str(children)
    assert "\u533a\u95f4\u5bbd\u5ea6\u4e3a 0" in s
    assert "\u8bf7\u8c03\u6574" in s


def test_logic_row_content_warning_narrow_range():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.5, 0.54, "{:.2f}", "warning")
    s = str(children)
    assert "\u533a\u95f4\u8fc7\u7a84" in s
    assert "0.04" in s
    assert "\u5efa\u8bae\u6269\u5927\u533a\u95f4" in s


def test_logic_row_content_returns_list_of_components():
    """Returns list[Component] (or compatible iterable) for Dash children."""
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.10, 0.15, "{:.2f}", "valid")
    # Must be iterable, non-empty, and contain at least one html component
    assert len(list(children)) >= 1
