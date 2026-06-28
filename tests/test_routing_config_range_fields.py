"""Tests for the compact 2-column range-field structure.

In the redesign:
- `_build_metric_cell(field)` produces a single metric cell (replaces the old
  `_build_range_input_group` per-field card).
- `_build_compact_range_row(left, right)` wraps one or two cells in a shared
  `.range-row` container.
- Badge text inputs (low/high) were removed; the slider's always-visible
  tooltip replaces them.
- Cell-level DOM ids are `cell-{name}`, `slider-{name}`, `logic-{name}`.
"""


def test_range_fields_has_seven_entries_with_required_keys():
    from app.routing_config import RANGE_FIELDS
    assert len(RANGE_FIELDS) == 7
    required = {"name", "label", "help", "unit", "slider_min", "slider_max", "step", "fmt"}
    for f in RANGE_FIELDS:
        assert required.issubset(f.keys()), f"missing keys in {f}"
    names = [f["name"] for f in RANGE_FIELDS]
    assert set(names) == {"h_ratio", "v_ratio", "r_ohm", "c_ff", "tau_ps",
                          "via_coverage", "similarity"}


def test_range_fields_have_help_and_unit():
    """Every range field carries Chinese help text and SI unit (may be '')."""
    from app.routing_config import RANGE_FIELDS
    for f in RANGE_FIELDS:
        assert isinstance(f["help"], str) and len(f["help"]) > 0, f"{f['name']} missing help"
        assert isinstance(f["unit"], str), f"{f['name']} unit must be str (possibly empty)"


def test_thresh_fields_removed():
    """THRESHOLD_FIELDS is replaced by RANGE_FIELDS."""
    from app import routing_config
    assert not hasattr(routing_config, "THRESHOLD_FIELDS")


def test_build_metric_cell_uses_slider_and_logic_ids():
    """Metric cell uses cell-{name}, slider-{name}, logic-{name} ids."""
    from app.routing_config import _build_metric_cell, RANGE_FIELDS
    for field in RANGE_FIELDS:
        name = field["name"]
        el = _build_metric_cell(field)
        s = str(el)
        assert f"id='cell-{name}'" in s, f"cell-{name} container missing"
        assert f"id='slider-{name}'" in s, f"slider-{name} missing"
        assert f"id='logic-{name}'" in s, f"logic-{name} missing"
        # No badge-input-* IDs (text badges were removed)
        assert f"id='badge-input-{name}-low'" not in s
        assert f"id='badge-input-{name}-high'" not in s
        # Legacy id='row-{name}' was renamed to id='cell-{name}'
        assert f"id='row-{name}'" not in s
        assert f"id='input-{name}-low'" not in s
        assert f"id='input-{name}-high'" not in s
        # RangeSlider is the only input mechanism
        assert "RangeSlider" in s


def test_build_metric_cell_contains_help_and_bounds_text():
    """Each cell renders help text and bounds text (e.g. '[0.00, 1.00]')."""
    from app.routing_config import _build_metric_cell, RANGE_FIELDS
    for field in RANGE_FIELDS:
        el = _build_metric_cell(field)
        s = str(el)
        assert field["help"] in s, f"help '{field['help']}' missing for {field['name']}"
        bounds_min = field["fmt"].format(field["slider_min"])
        bounds_max = field["fmt"].format(field["slider_max"])
        assert bounds_min in s, f"slider_min '{bounds_min}' not in bounds for {field['name']}"
        assert bounds_max in s, f"slider_max '{bounds_max}' not in bounds for {field['name']}"


def test_build_metric_cell_contains_tick_row_with_three_spans():
    """tick-row contains 3 spans: min, mid, max."""
    from app.routing_config import _build_metric_cell, RANGE_FIELDS
    field = RANGE_FIELDS[0]  # h_ratio
    el = _build_metric_cell(field)
    s = str(el)
    assert "tick-row" in s
    fmt = field["fmt"]
    assert fmt.format(field["slider_min"]) in s
    assert fmt.format(field["slider_max"]) in s
    mid = (field["slider_min"] + field["slider_max"]) / 2
    assert fmt.format(mid) in s


def test_build_metric_cell_contains_logic_compact_with_math_notation():
    """logic-compact contains the math notation 'low \u2264 X \u2264 high'."""
    from app.routing_config import _build_metric_cell, RANGE_FIELDS
    el = _build_metric_cell(RANGE_FIELDS[0])  # h_ratio
    s = str(el)
    assert "logic-compact" in s
    assert "\u5408\u89c4" in s  # 合规
    assert "\u2264" in s        # ≤ symbol


def test_build_metric_cell_uses_metric_cell_class():
    """Cell class starts with 'metric-cell' (and may include is-invalid / is-warning)."""
    from app.routing_config import _build_metric_cell, RANGE_FIELDS
    for field in RANGE_FIELDS:
        el = _build_metric_cell(field)
        cls = el.className
        assert cls.startswith("metric-cell"), \
            f"cell className must start with 'metric-cell'; got {cls!r}"


def test_build_metric_cell_has_always_visible_tooltip():
    """The RangeSlider in a metric cell always shows its tooltip (text badges removed)."""
    from app.routing_config import _build_metric_cell, RANGE_FIELDS
    for field in RANGE_FIELDS:
        el = _build_metric_cell(field)
        s = str(el)
        # Dash's repr stringifies dict props; verify the always_visible flag is set
        assert "'always_visible': True" in s, \
            f"RangeSlider in {field['name']} cell must have always_visible tooltip"


def test_range_row_groups_layout_three_double_one_single():
    """RANGE_ROW_GROUPS: 3 double rows + 1 single row = 4 total."""
    from app.routing_config import RANGE_ROW_GROUPS
    doubles = sum(1 for pair in RANGE_ROW_GROUPS if pair[1] is not None)
    singles = sum(1 for pair in RANGE_ROW_GROUPS if pair[1] is None)
    assert doubles == 3
    assert singles == 1
    assert len(RANGE_ROW_GROUPS) == 4


def test_compact_range_row_double_wraps_two_cells():
    """A 2-field row wraps two .metric-cell elements in .range-row.double."""
    from app.routing_config import (
        RANGE_FIELDS, _build_compact_range_row, _field_by_name,
    )
    left = _field_by_name(RANGE_FIELDS[0]["name"])
    right = _field_by_name(RANGE_FIELDS[1]["name"])
    row = _build_compact_range_row(left, right)
    assert row.className == "range-row double"
    assert len(list(row.children)) == 2
    for child in row.children:
        assert child.className.startswith("metric-cell")


def test_compact_range_row_single_wraps_one_cell():
    """A single-field row wraps one .metric-cell in .range-row.single."""
    from app.routing_config import (
        _build_compact_range_row, _field_by_name,
    )
    left = _field_by_name("similarity")
    row = _build_compact_range_row(left, None)
    assert row.className == "range-row single"
    assert len(list(row.children)) == 1
    assert row.children[0].className.startswith("metric-cell")


def test_field_by_name_returns_correct_field():
    """Helper returns the field descriptor dict for a known name."""
    from app.routing_config import _field_by_name
    h = _field_by_name("h_ratio")
    assert h["name"] == "h_ratio"
    assert h["slider_min"] == 0.0
    assert h["slider_max"] == 1.0


def test_field_by_name_raises_for_unknown():
    """Unknown name raises KeyError."""
    import pytest
    from app.routing_config import _field_by_name
    with pytest.raises(KeyError):
        _field_by_name("not_a_real_field")