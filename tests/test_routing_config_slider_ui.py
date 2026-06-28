"""Tests for slider row constraint detection and compact logic annotation.

Compact 2-column redesign:
- Text badges for low/high were merged into the RangeSlider's always-visible
  tooltip, so the only threshold input is the slider.
- The logic-row annotation is now compact (one-liner inline math notation),
  rendered as `.logic-compact` inside each `.metric-cell`.
- Row-level class targets moved from `.row-{name}` to `.cell-{name}`.
"""
from app.routing_config import _compute_constraint_status


def test_constraint_status_valid_normal_range():
    """A normal, non-narrow range is 'valid'."""
    assert _compute_constraint_status(0.1, 0.2, 0.0, 1.0) == "valid"


def test_constraint_status_invalid_low_greater_than_high():
    """Low > High is logically impossible \u2192 'invalid'."""
    assert _compute_constraint_status(0.5, 0.2, 0.0, 1.0) == "invalid"


def test_constraint_status_warning_zero_width():
    """Low == High (zero width) \u2192 'warning' (no value can be compliant)."""
    assert _compute_constraint_status(0.5, 0.5, 0.0, 1.0) == "warning"


def test_constraint_status_warning_narrow_range():
    """Range narrower than 5% of full domain \u2192 'warning'."""
    # Full domain 0..1, 5% = 0.05; width 0.04 < 0.05 \u2192 warning
    assert _compute_constraint_status(0.5, 0.54, 0.0, 1.0) == "warning"


def test_constraint_status_valid_at_5_percent_boundary():
    """Exactly 5% width \u2192 still 'valid' (boundary inclusive)."""
    # Width 0.05 of full 0..1 \u2192 valid
    assert _compute_constraint_status(0.5, 0.55, 0.0, 1.0) == "valid"


def test_constraint_status_none_inputs_default_valid():
    """None values (initial render before user interaction) \u2192 'valid'."""
    assert _compute_constraint_status(None, None, 0.0, 1.0) == "valid"
    assert _compute_constraint_status(None, 0.5, 0.0, 1.0) == "valid"
    assert _compute_constraint_status(0.5, None, 0.0, 1.0) == "valid"


# -- Compact logic content (used by metric cell's logic-compact row) --

def test_logic_compact_content_valid_uses_math_notation():
    """Valid status shows compact `low \u2264 X \u2264 high` inline notation."""
    from app.routing_config import _build_logic_compact_content
    children = _build_logic_compact_content(0.10, 0.15, "{:.2f}", "valid")
    s = str(children)
    assert "\u5408\u89c4" in s
    assert "0.10" in s
    assert "0.15" in s
    assert "\u2264" in s  # \u2264
    assert "0.05" in s  # width = high - low


def test_logic_compact_content_invalid_shows_low_greater_than_high():
    """Invalid status surfaces Low > High annotation."""
    from app.routing_config import _build_logic_compact_content
    children = _build_logic_compact_content(0.50, 0.20, "{:.2f}", "invalid")
    s = str(children)
    assert "Low" in s
    assert "0.50" in s
    assert "High" in s
    assert "0.20" in s
    assert "\u4e0d\u5408\u6cd5" in s


def test_logic_compact_content_warning_zero_width():
    """Warning (low==high) shows zero-width message."""
    from app.routing_config import _build_logic_compact_content
    children = _build_logic_compact_content(0.50, 0.50, "{:.2f}", "warning")
    s = str(children)
    assert "\u533a\u95f4\u5bbd\u5ea6\u4e3a 0" in s


def test_logic_compact_content_warning_narrow_range():
    """Warning (narrow width) shows the narrow-range message."""
    from app.routing_config import _build_logic_compact_content
    children = _build_logic_compact_content(0.5, 0.54, "{:.2f}", "warning")
    s = str(children)
    assert "\u533a\u95f4\u8fc7\u7a84" in s
    assert "0.04" in s


def test_logic_compact_content_returns_list_of_components():
    """Returns list[Component] (or compatible iterable) for Dash children."""
    from app.routing_config import _build_logic_compact_content
    children = _build_logic_compact_content(0.10, 0.15, "{:.2f}", "valid")
    # Must be iterable, non-empty, and contain at least one html component
    assert len(list(children)) >= 1


# -- Backward-compatibility alias --

def test_logic_row_content_alias_uses_compact_format():
    """`_build_logic_row_content` is now a thin alias for the compact version."""
    from app.routing_config import (
        _build_logic_row_content, _build_logic_compact_content,
    )
    a = _build_logic_row_content(0.10, 0.15, "{:.2f}", "valid")
    b = _build_logic_compact_content(0.10, 0.15, "{:.2f}", "valid")
    assert str(a) == str(b)


# -- Row grouping for 2-column layout --

def test_range_row_groups_pair_all_seven_fields():
    """RANGE_ROW_GROUPS must partition all 7 RANGE_FIELDS into rows of 1 or 2."""
    from app.routing_config import RANGE_FIELDS, RANGE_ROW_GROUPS
    paired = [n for pair in RANGE_ROW_GROUPS for n in pair if n is not None]
    expected = [f["name"] for f in RANGE_FIELDS]
    assert sorted(paired) == sorted(expected)
    # 3 rows of 2 + 1 single row = 4 rows total
    assert len(RANGE_ROW_GROUPS) == 4
    # Last row is single-cell (similarity)
    assert RANGE_ROW_GROUPS[-1][1] is None


def test_metric_cell_uses_always_visible_tooltip():
    """The metric cell's RangeSlider must always show low/high on the bar."""
    from app.routing_config import _build_metric_cell
    from app.routing_state import routing_state
    cell = _build_metric_cell(_first_field())
    # Find the slider component inside the cell's children tree
    tooltip = _find_tooltip(cell)
    assert tooltip is not None, "Slider must declare a tooltip dict"
    assert tooltip.get("always_visible") is True, \
        "Tooltip must always be visible (merges text badges into the bar)"
    assert tooltip.get("placement") == "bottom"


def test_metric_cell_no_badge_input_id():
    """The compact metric cell must NOT contain any badge-input dcc.Input
    (text badges were removed; slider tooltip replaces them)."""
    from app.routing_config import _build_metric_cell
    cell = _build_metric_cell(_first_field())
    flat_str = str(cell)
    assert "badge-input-" not in flat_str, \
        "metric-cell must not contain badge-input- dcc.Input components"
    assert "range-slider-badge" not in flat_str, \
        "metric-cell must not contain badge DOM class"


def test_compact_range_row_double_has_two_cells():
    """A 2-field row must produce a .range-row.double with 2 metric cells."""
    from app.routing_config import (
        RANGE_FIELDS, _build_compact_range_row, _field_by_name,
    )
    left = _field_by_name(RANGE_FIELDS[0]["name"])
    right = _field_by_name(RANGE_FIELDS[1]["name"])
    row = _build_compact_range_row(left, right)
    assert row.className == "range-row double"
    # Two children (cells)
    assert len(list(row.children)) == 2
    # Both children are metric-cell elements
    cell_strs = [str(c) for c in row.children]
    assert all("metric-cell" in s for s in cell_strs)


def test_compact_range_row_single_has_one_cell():
    """A single-field row must produce a .range-row.single with 1 cell."""
    from app.routing_config import (
        _build_compact_range_row, _field_by_name,
    )
    left = _field_by_name("similarity")
    row = _build_compact_range_row(left, None)
    assert row.className == "range-row single"
    assert len(list(row.children)) == 1


# -- Callback registration: cell-{name} replaces row-{name} --

def test_logic_cell_callback_registered_for_each_field():
    """A logic-compact callback must be registered for each of the 7 range
    fields, listening to slider-{name} and writing to logic-{name} +
    cell-{name}.className."""
    import dash
    from app.layout import create_layout
    from app.routing_config import (
        RANGE_FIELDS, register_routing_config_callbacks,
    )

    app = dash.Dash(__name__)
    app.layout = create_layout()
    register_routing_config_callbacks(app)

    def _output_str(o):
        # Dash's Output object str() looks like: <Output `a.children`>
        # Pull the id portion out.
        s = str(o)
        if "`" in s:
            return s.split("`", 2)[1]
        return s

    # For each field, the callback map should reference its slider as Input
    # and its logic / cell as Output.
    for field in RANGE_FIELDS:
        name = field["name"]
        slider_id = f"slider-{name}"
        logic_id = f"logic-{name}"
        cell_id = f"cell-{name}"
        # Search callback_map for a callback whose outputs include logic-{name}
        found = False
        for _cb_id, cb in app.callback_map.items():
            outputs = cb.get("output", "")
            # Dash stores output as a single Output object (str repr) or
            # a list of Output objects when there are multiple outputs.
            output_list = outputs if isinstance(outputs, list) else [outputs]
            output_strs = [_output_str(o) for o in output_list]
            if any(s == logic_id or s.startswith(logic_id + ".")
                   for s in output_strs):
                found = True
                # Verify slider is among the inputs
                inputs = cb.get("inputs", [])
                input_ids = [i.get("id") if isinstance(i, dict) else str(i) for i in inputs]
                assert slider_id in input_ids, \
                    f"logic callback for {name} must listen to {slider_id}; got {input_ids}"
                # Verify cell-{name}.className is also an output
                assert any(s == f"{cell_id}.className" for s in output_strs), \
                    f"logic callback for {name} must write to {cell_id}.className; got {output_strs}"
                break
        assert found, f"No callback registered with output {logic_id}"


# -- Helpers --

def _first_field():
    from app.routing_config import RANGE_FIELDS
    return RANGE_FIELDS[0]


def _find_tooltip(component):
    """Recursively walk a Dash component tree to find a `tooltip=` kwarg."""
    # dcc.RangeSlider stores tooltip as a dict property on the component itself.
    if hasattr(component, "tooltip") and isinstance(component.tooltip, dict):
        return component.tooltip
    children = getattr(component, "children", None)
    if children is None:
        return None
    if isinstance(children, (list, tuple)):
        for c in children:
            t = _find_tooltip(c)
            if t is not None:
                return t
    else:
        return _find_tooltip(children)
    return None