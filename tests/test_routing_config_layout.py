"""Tests for routing config tab layout generation."""
from app.routing_config import create_routing_config_tab, get_threshold_input_ids


def test_create_routing_config_tab_returns_div():
    layout = create_routing_config_tab()
    assert layout is not None


def test_threshold_input_ids_contains_all_thresholds():
    ids = get_threshold_input_ids()
    for name in ("max_h_ratio", "max_v_ratio", "max_r_ohm", "max_c_ff",
                 "max_tau_ps", "min_via_coverage", "min_similarity"):
        assert f"thresh-{name}" in ids, f"Missing input: {name}"
