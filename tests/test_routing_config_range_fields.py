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


def test_build_range_input_group_uses_slider_and_inputs():
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    el = _build_range_input_group(RANGE_FIELDS[0])  # h_ratio
    s = str(el)
    # str() on Dash components gives Python repr; ids are single-quoted.
    assert "id='slider-h_ratio'" in s
    assert "id='input-h_ratio-low'" in s
    assert "id='input-h_ratio-high'" in s
    # RangeSlider is a component of the rendered element
    assert "RangeSlider" in s


def test_build_range_input_group_has_new_structure_ids():
    """New row structure: row-{name}, slider-{name}, badge-input-{name}-{low|high}, logic-{name}."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    for field in RANGE_FIELDS:
        name = field["name"]
        el = _build_range_input_group(field)
        s = str(el)
        assert f"id='row-{name}'" in s, f"row-{name} container missing"
        assert f"id='slider-{name}'" in s, f"slider-{name} missing"
        assert f"id='badge-input-{name}-low'" in s, f"badge-input-{name}-low missing"
        assert f"id='badge-input-{name}-high'" in s, f"badge-input-{name}-high missing"
        assert f"id='logic-{name}'" in s, f"logic-{name} missing"
        # Legacy input-{name}-* IDs must NOT appear
        assert f"id='input-{name}-low'" not in s, f"legacy input-{name}-low still present"
        assert f"id='input-{name}-high'" not in s, f"legacy input-{name}-high still present"


def test_build_range_input_group_contains_help_and_bounds_text():
    """Each row renders help text (in row-header) and bounds text (e.g. '[0.00, 1.00]')."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    for field in RANGE_FIELDS:
        el = _build_range_input_group(field)
        s = str(el)
        # help text appears in row-header
        assert field["help"] in s, f"help '{field['help']}' missing for {field['name']}"
        # bounds text contains the formatted slider_min and slider_max
        bounds_min = field["fmt"].format(field["slider_min"])
        bounds_max = field["fmt"].format(field["slider_max"])
        assert bounds_min in s, f"slider_min '{bounds_min}' not in bounds for {field['name']}"
        assert bounds_max in s, f"slider_max '{bounds_max}' not in bounds for {field['name']}"


def test_build_range_input_group_contains_tick_row_with_three_spans():
    """tick-row contains 3 spans: min, mid, max."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    field = RANGE_FIELDS[0]  # h_ratio
    el = _build_range_input_group(field)
    s = str(el)
    # tick-row class must be present
    assert "tick-row" in s
    # min and max values formatted are visible
    fmt = field["fmt"]
    assert fmt.format(field["slider_min"]) in s
    assert fmt.format(field["slider_max"]) in s
    # mid value
    mid = (field["slider_min"] + field["slider_max"]) / 2
    assert fmt.format(mid) in s


def test_build_range_input_group_contains_logic_row_with_math_notation():
    """logic-row contains the math notation '合规: low ≤ X ≤ high'."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    el = _build_range_input_group(RANGE_FIELDS[0])  # h_ratio
    s = str(el)
    assert "logic" in s
    assert "\u5408\u89c4" in s  # 合规
    assert "\u2264" in s  # ≤ symbol
    assert "\u27fa" in s  # ⟷ arrow
