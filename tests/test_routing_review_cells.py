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


def test_compute_table_styles_includes_light_red_for_out_of_range():
    from app.routing_review import _compute_table_styles, _build_cell_violation_map
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
            "gate_pass": True,
        },
        "WL_1": {
            "status": "ok",
            "h_ratio": 0.22, "v_ratio": 0.78,
            "r_total": 150.0, "c_total": 200.0, "effective_tau_ps": 8.0,
            "via_coverage": 0.95, "similarity_score": 95.0,
            "gate_pass": False,
        },
    }
    cell_map = _build_cell_violation_map(batch_results, thresholds)
    styles = _compute_table_styles([], batch_results, cell_map, thresholds)
    # Look for a rule matching the H % column for WL_1 with the light-red background
    found_h = any(
        rule.get("if", {}).get("column_id") == "H %"
        and 'WL_1' in str(rule.get("if", {}).get("filter_query", ""))
        and rule.get("backgroundColor") == "rgba(239, 68, 68, 0.15)"
        for rule in styles
    )
    found_r = any(
        rule.get("if", {}).get("column_id") == "R (\u03a9)"
        and 'WL_1' in str(rule.get("if", {}).get("filter_query", ""))
        and rule.get("backgroundColor") == "rgba(239, 68, 68, 0.15)"
        for rule in styles
    )
    assert found_h, f"light-red rule for H %/WL_1 not found in {styles}"
    assert found_r, f"light-red rule for R (\u03a9)/WL_1 not found in {styles}"
    # Pass-column pill rules (\u2717 red, \u2713 green, \u26a0 amber) should still be present
    pass_rules = [r for r in styles if r.get("if", {}).get("column_id") == "Pass"]
    assert len(pass_rules) >= 3