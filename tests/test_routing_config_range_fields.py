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
