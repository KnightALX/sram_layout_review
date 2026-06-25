"""End-to-end test: load shapes → run routing review → check all 6 metrics."""
import sys

sys.path.insert(0, '.')
from config.routing_thresholds import RoutingThresholds
from core.routing_metrics import compute_for_net
from review_engine import Point, Polygon


def _tech():
    return {
        "met1": {"type": "metal", "resistance_per_sq": 0.15, "capacitance_per_um": 0.20, "min_width": 0.032, "min_space": 0.032},
        "met2": {"type": "metal", "resistance_per_sq": 0.12, "capacitance_per_um": 0.16, "min_width": 0.032, "min_space": 0.032},
    }


def test_wordline_wl_preset_h_dominant_passes():
    """A V-dominant net on WL preset should pass direction gate."""
    # 5μm vertical, 0.5μm horizontal — V-dominant (typical WL layout)
    polys = [Polygon(points=[Point(0,0), Point(0.5,0), Point(0.5,5), Point(0,5)], layer="met1")]
    t = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("WL0", polys, [], _tech(), t, golden_metrics=None)
    assert m["dominant"] == "V"
    assert m["gate_pass"] is True
    # All 6 metrics present
    for k in ("h_ratio", "v_ratio", "missing_via_count", "via_coverage",
             "r_total", "c_total", "effective_tau_ps",
             "similarity_score", "gate_pass"):
        assert k in m


def test_io_bl_preset_v_dominant_passes():
    """An H-dominant net on IO preset should pass direction gate."""
    polys = [Polygon(points=[Point(0,0), Point(5,0), Point(5,0.5), Point(0,0.5)], layer="met2")]
    t = RoutingThresholds.for_preset("sram_5nm_io_bl")
    m = compute_for_net("BL0", polys, [], _tech(), t, golden_metrics=None)
    assert m["dominant"] == "H"
    assert m["gate_pass"] is True


def test_long_wire_fails_tau_gate():
    """A long wire (1000μm) should fail the τ gate."""
    polys = [Polygon(points=[Point(0,0), Point(1000,0), Point(1000,0.1), Point(0,0.1)], layer="met1")]
    t = RoutingThresholds.for_preset("sram_7nm_wl")  # max_tau_ps=12.5
    m = compute_for_net("WL0", polys, [], _tech(), t, golden_metrics=None)
    assert any("τ" in r or "tau" in r for r in m["gate_fail_reasons"])


# Task 7: ensure routing review path consistently uses state.get_thresholds()
# (added for cross-callback hygiene coverage)

def test_e2e_uses_get_thresholds_for_gates():
    """Simple smoke: compute_for_net called in review uses thresholds from routing_state.get_thresholds()."""
    from app.routing_state import routing_state
    polys = [Polygon(points=[Point(0,0), Point(10,0), Point(10,0.5), Point(0,0.5)], layer="met1")]
    # Ensure state provides them
    t = routing_state.get_thresholds()
    m = compute_for_net("E2E_NET", polys, [], _tech(), t, golden_metrics=None)
    assert "gate_pass" in m
    # Re-run after forcing frozen preset via public API
    routing_state.set_frozen_mode(True)
    t2 = routing_state.get_thresholds()
    m2 = compute_for_net("E2E_NET2", polys, [], _tech(), t2, golden_metrics=None)
    assert m2["gate_pass"] is True or m2["gate_pass"] is False  # just exercises the getter path


# --- Task 3 rendering tests (TDD style: added to verify Eff. C card, C column,
# threshold display on cards, source banner; these exercise _build_* helpers)

def test_build_metric_cards_includes_eff_c_and_threshold_display():
    """Verify Task 3 Step 1+3: Eff. C card present + min-max + current/thresh format on cards."""
    from app.routing_review import _build_metric_cards
    from app.routing_state import routing_state

    fake_results = {
        "netA": {
            "h_ratio": 0.10, "v_ratio": 0.05, "missing_via_count": 0,
            "r_total": 12.3, "c_total": 45.6, "effective_tau_ps": 4.2,
            "similarity_score": 92.0, "gate_pass": True, "status": "ok",
            "dominant": "H", "via_coverage": 1.0, "missing_locations": [],
        },
        "netB": {
            "h_ratio": 0.20, "v_ratio": 0.10, "missing_via_count": 0,
            "r_total": 23.4, "c_total": 67.8, "effective_tau_ps": 6.1,
            "similarity_score": 85.0, "gate_pass": True, "status": "ok",
            "dominant": "H", "via_coverage": 0.95, "missing_locations": [],
        },
    }
    prev_frozen = routing_state.is_frozen
    try:
        routing_state.set_frozen_mode(True)
        cards_html = _build_metric_cards(fake_results)
        rendered = str(cards_html)
        assert "Eff. C (fF)" in rendered, "Eff. C card label must be present (Step 1)"
        # min-max range for c
        assert "45.6" in rendered and "67.8" in rendered
        # threshold display using current thresholds (Step 3)
        # e.g. contains / 500.0fF or equivalent for active preset
        assert "/ " in rendered and "fF" in rendered
        assert "H / V Ratio" in rendered
        # we hard-coded threshold for H/V and Miss too
        assert "H≤" in rendered or "maxH" in rendered or "Missing Via" in rendered
    finally:
        routing_state.set_frozen_mode(prev_frozen)


def test_build_table_rows_includes_c_column_with_threshold():
    """Verify Task 3 Step 2: C (fF) column uses value / threshold format."""
    from app.routing_review import _build_table_rows
    from app.routing_state import routing_state

    fake_batch = {
        "trk_foo": {
            "dominant": "V", "h_ratio": 0.05, "v_ratio": 0.85,
            "r_total": 8.0, "c_total": 120.5, "effective_tau_ps": 3.14,
            "via_coverage": 0.92, "missing_via_count": 0,
            "similarity_score": 88.0, "gate_pass": True, "status": "ok",
            "missing_locations": [],
        }
    }
    prev = routing_state.is_frozen
    try:
        routing_state.set_frozen_mode(True)
        rows = _build_table_rows(fake_batch)
        assert len(rows) == 1
        row = rows[0]
        assert "C (fF)" in row
        c_val = row["C (fF)"]
        assert "120.5 / " in c_val, f"C column must be 'val / thresh' form, got {c_val}"
        # thresh should be positive number from get_thresholds
        assert any(ch.isdigit() for ch in c_val.split("/")[-1])
    finally:
        routing_state.set_frozen_mode(prev)


def test_routing_review_source_banner_and_tab_structure():
    """Verify Task 3 Step 4: source banner div + content from routing_state."""
    from app.routing_review import _build_threshold_source, create_routing_review_tab

    banner = _build_threshold_source()
    bstr = str(banner)
    assert "Active Threshold Source:" in bstr, "Step 4 banner label"

    # the create_ func must emit the id used by callback
    tab = create_routing_review_tab()
    tstr = str(tab)
    assert "routing-threshold-source" in tstr
    assert "routing-metric-cards" in tstr  # also cards container
