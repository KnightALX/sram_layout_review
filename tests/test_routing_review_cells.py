def test_format_cell_in_range():
    from app.routing_review import _format_cell
    from config.routing_thresholds import Range
    s = _format_cell(0.10, Range(0.0, 0.15))
    assert "0.1" in s
    assert "\u2208" in s    # ∈
    assert "\u2209" not in s # ∉
    assert "[0.0, 0.15]" in s


def test_format_cell_out_of_range():
    from app.routing_review import _format_cell
    from config.routing_thresholds import Range
    s = _format_cell(0.22, Range(0.0, 0.15))
    assert "0.2" in s
    assert "\u2209" in s    # ∉
    assert "\u2208" not in s # ∈
    assert "[0.0, 0.15]" in s


def test_build_cell_violation_map_marks_out_of_range():
    from app.routing_review import _build_cell_violation_map
    from config.routing_thresholds import Range, RoutingThresholds

    thresholds = RoutingThresholds(
        h_ratio=Range(0.0, 0.15),
        r_ohm=Range(0.0, 100.0),
    )
    batch_results = {
        "WL_0": {
            "status": "ok",
            "h_ratio": 0.10, "v_ratio": 0.90,
            "r_total": 50.0, "c_total": 200.0, "effective_tau_ps": 8.0,
            "via_coverage": 0.95, "similarity_score": 95.0,
        },
        "WL_1": {
            "status": "ok",
            "h_ratio": 0.22, "v_ratio": 0.78,            # h out of range
            "r_total": 150.0, "c_total": 200.0, "effective_tau_ps": 8.0,  # r out of range
            "via_coverage": 0.95, "similarity_score": 95.0,
        },
    }
    m = _build_cell_violation_map(batch_results, thresholds)
    assert "WL_0" not in m
    assert m["WL_1"] == {"H %", "R (\u03a9)"}


def test_build_cell_violation_map_skips_no_data():
    from app.routing_review import _build_cell_violation_map
    from config.routing_thresholds import Range, RoutingThresholds

    thresholds = RoutingThresholds(h_ratio=Range(0.0, 0.15))
    batch_results = {
        "WL_x": {"status": "no_data"},
    }
    m = _build_cell_violation_map(batch_results, thresholds)
    assert m == {}