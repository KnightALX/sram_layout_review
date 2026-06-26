def test_range_fields_has_seven_entries_with_required_keys():
    from app.routing_config import RANGE_FIELDS
    assert len(RANGE_FIELDS) == 7
    required = {"name", "label", "slider_min", "slider_max", "step", "fmt"}
    for f in RANGE_FIELDS:
        assert required.issubset(f.keys()), f"missing keys in {f}"
    names = [f["name"] for f in RANGE_FIELDS]
    assert set(names) == {"h_ratio", "v_ratio", "r_ohm", "c_ff", "tau_ps",
                          "via_coverage", "similarity"}


def test_thresh_fields_removed():
    """THRESHOLD_FIELDS is replaced by RANGE_FIELDS."""
    from app import routing_config
    assert not hasattr(routing_config, "THRESHOLD_FIELDS")


def test_build_range_input_group_uses_slider_and_inputs():
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    el = _build_range_input_group(RANGE_FIELDS[0])  # h_ratio
    s = str(el)
    assert 'id="slider-h_ratio"' in s
    assert 'id="input-h_ratio-low"' in s
    assert 'id="input-h_ratio-high"' in s
    # dcc.RangeSlider renders as a div with class 'rc-slider'
    assert "rc-slider" in s
