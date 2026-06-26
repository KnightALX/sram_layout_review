"""Tests for routing metrics aggregator."""
import sys

sys.path.insert(0, '.')
import pytest

from config.routing_thresholds import RoutingThresholds
from config_system import get_sram_7nm_config
from core.effective_tau import ohm_ff_to_ps
from core.routing_metrics import check_gates, compute_for_net, split_metal_via_polygons
from review_engine import Point, Polygon, ProfessionalLayoutReviewEngine


def _rect(x1, y1, x2, y2, layer):
    return Polygon(points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)], layer=layer)


def _via(x, y, size=0.024, layer="via1"):
    s = size / 2
    return Polygon(
        points=[Point(x-s, y-s), Point(x+s, y-s), Point(x+s, y+s), Point(x-s, y+s)],
        layer=layer,
    )


def _tech_layers():
    return {
        "met1": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_space": 0.032},
        "met2": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.12,
                 "capacitance_per_um": 0.16, "min_space": 0.032},
        "via1": {"type": "via", "min_size": 0.024, "resistance": 1.0, "min_space": 0.024},
    }


def test_compute_for_net_returns_all_six_metrics():
    """Output must have all 6 metric families."""
    polys = [_rect(0, 0, 10, 1, "met1"), _rect(5, 0, 6, 10, "met2")]
    vias = [_via(5.5, 5)]
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("WL0", polys, vias, _tech_layers(), thresholds, golden_metrics=None)
    for key in ("h_len", "v_len", "h_ratio", "v_ratio", "dominant",
                "missing_via_count", "via_coverage", "missing_locations",
                "r_total", "c_total", "rc_product", "effective_tau_ps",
                "similarity_score", "deltas", "gate_pass", "gate_fail_reasons"):
        assert key in m, f"Missing key: {key}"


def test_wl_net_with_violation_fails_gate():
    """A 'horizontal-only' net should fail WL preset (expect V-dominant)."""
    polys = [_rect(0, 0, 10, 1, "met2")]  # only H
    m = compute_for_net("WL0", polys, [], _tech_layers(),
                        RoutingThresholds.for_preset("sram_7nm_wl"), golden_metrics=None)
    assert m["gate_pass"] is False
    assert any("h_ratio" in r or "v_ratio" in r for r in m["gate_fail_reasons"])


def test_golden_match_yields_100_similarity():
    """If golden_metrics == own metrics, similarity should be 100."""
    polys = [_rect(0, 0, 5, 1, "met1"), _rect(3, 0, 4, 5, "met2")]
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    m1 = compute_for_net("WL0", polys, [], _tech_layers(), thresholds, golden_metrics=None)
    m2 = compute_for_net("WL0", polys, [], _tech_layers(), thresholds,
                         golden_metrics={k: m1[k] for k in (
                             "h_ratio", "v_ratio", "total_len", "via_count",
                             "r_total", "c_total", "effective_tau_ps", "bbox_aspect"
                         )})
    assert m2["similarity_score"] == pytest.approx(100.0, abs=1.0)


def test_check_gates_returns_fail_reasons():
    metrics = {
        "h_ratio": 0.50, "v_ratio": 0.50,
        "r_total": 50.0, "c_total": 200.0, "effective_tau_ps": 30.0,
        "via_coverage": 0.50, "missing_via_count": 3,
        "similarity_score": 50.0,
    }
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    pass_, reasons = check_gates(metrics, thresholds)
    assert pass_ is False
    assert len(reasons) >= 4  # h_ratio, tau_ps, via_coverage, similarity all fail


def test_soft_gates_bypassed_with_high_golden_similarity():
    """H-only net WITH a horizontal golden should pass the WL preset's
    h_ratio gate via bypass (soft fail is forgiven when net matches golden)."""
    polys = [_rect(0, 0, 10, 1, "met2")]  # only H
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    # First, derive an H-only "golden" by computing a similar net's metrics
    m_golden = compute_for_net(
        "WL_GOLDEN", polys, [], _tech_layers(), thresholds, golden_metrics=None
    )
    golden_features = {k: m_golden[k] for k in (
        "h_ratio", "v_ratio", "total_len", "via_count",
        "r_total", "c_total", "effective_tau_ps", "bbox_aspect"
    )}
    # Now run the same net, but pass the golden in: similarity = ~100, soft bypass triggers
    m = compute_for_net(
        "WL0", polys, [], _tech_layers(), thresholds, golden_metrics=golden_features
    )
    assert m["similarity_score"] >= thresholds.min_similarity
    assert m["gate_pass"] is True
    assert m["gate_fail_reasons"] == []


def test_hard_gates_never_bypassed():
    """Even with high similarity (golden set), a net with missing vias or
    excessive R must still fail — HARD gates are never bypassed."""
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    # High similarity, but R exceeds max_r_ohm (HARD fail)
    metrics = {
        "h_ratio": 0.10, "v_ratio": 0.90,
        "r_total": 500.0,  # >> 100.0 max_r_ohm
        "c_total": 100.0, "effective_tau_ps": 5.0,
        "via_coverage": 0.95, "missing_via_count": 0,
        "similarity_score": 95.0,
    }
    pass_, reasons = check_gates(metrics, thresholds, has_golden=True)
    assert pass_ is False
    assert any("R" in r and "max" in r for r in reasons)
    # missing_via > 0 also must always fail
    metrics["r_total"] = 50.0
    metrics["missing_via_count"] = 2
    pass_, reasons = check_gates(metrics, thresholds, has_golden=True)
    assert pass_ is False
    assert any("missing_via" in r for r in reasons)


def test_soft_gates_enforced_without_golden():
    """H-only net WITHOUT golden should still fail soft gates (backward compat)."""
    metrics = {
        "h_ratio": 1.0,  # >> 0.15 max_h_ratio (soft fail)
        "v_ratio": 0.0,
        "r_total": 10.0, "c_total": 50.0, "effective_tau_ps": 1.0,
        "via_coverage": 0.90, "missing_via_count": 0,
        "similarity_score": 100.0,  # sim OK, no golden → defaults to 100
    }
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    pass_, reasons = check_gates(metrics, thresholds, has_golden=False)
    assert pass_ is False
    assert any("h_ratio" in r for r in reasons)


# --- Consistency test helper (Task 2) ---
# Ensures the default rc_model=None path in compute_for_net yields the same
# R/C/τ as the legacy engine path used by Layout View Properties panel.

def _simple_long_m1():
    """A simple long horizontal wire on met1 (no vias)."""
    return [Polygon(
        points=[Point(0, 0), Point(200, 0), Point(200, 0.05), Point(0, 0.05)],
        layer="met1",
    )]


def _multi_layer_m1_m2():
    """Multi-layer net (met1 + met2, no vias) to cover tau unification on mixed layers."""
    return [
        Polygon(
            points=[Point(0, 0), Point(100, 0), Point(100, 0.05), Point(0, 0.05)],
            layer="met1",
        ),
        Polygon(
            points=[Point(100, 0), Point(100, 50), Point(100.05, 50), Point(100.05, 0)],
            layer="met2",
        ),
    ]


def test_compute_for_net_default_path_matches_legacy_rc():
    """When rc_model is not passed (defaults to None), compute_for_net must
    produce R/C/τ identical to legacy engine.calculate_net_rc + lumped tau.
    This is the required default for Routing Review == Properties consistency.

    Covers both mono-layer (original) and multi-layer nets (via-containing
    is also supported when set_net_vias is used on engine; here we use
    multi-metal to enforce the tau identity fix).
    """
    cfg = get_sram_7nm_config()
    tech = cfg.tech_config.layers
    thresh = RoutingThresholds.for_preset("sram_7nm_wl")

    for label, polys in [
        ("mono-met1", _simple_long_m1()),
        ("multi-met1+met2", _multi_layer_m1_m2()),
    ]:
        net = f"test_net_{label}"

        # Legacy path (as used by Properties panel)
        engine = ProfessionalLayoutReviewEngine(cfg)
        engine.add_net_polygons(net, polys)
        rc_legacy = engine.calculate_net_rc(net)

        # Routing path with default (no rc_model arg → None inside)
        m = compute_for_net(net, polys, [], tech, thresh)

        # R and C must match exactly (same calculate_net_rc)
        assert m["r_total"] == pytest.approx(rc_legacy.total_resistance, rel=1e-12, abs=1e-12), f"R mismatch on {label}"
        assert m["c_total"] == pytest.approx(rc_legacy.total_capacitance, rel=1e-12, abs=1e-12), f"C mismatch on {label}"

        # Tau must match the lumped calculation used by legacy timing
        expected_tau = ohm_ff_to_ps(rc_legacy.total_resistance, rc_legacy.total_capacitance, method="lumped")
        assert m["effective_tau_ps"] == pytest.approx(expected_tau, rel=1e-9), f"tau mismatch on {label}"
        assert m["effective_tau_ps"] == pytest.approx(rc_legacy.tau_rc, rel=1e-9), f"tau_rc mismatch on {label}"

    # Self-review note: test now enforces identity for multi-layer (previously only mono
    # long-met1 was covered). Default path now derives τ from totals via ohm_ff_to_ps
    # exactly as legacy does, closing the last unification gap for Properties vs Routing Review.


def test_split_metal_via_polygons_separates_layers():
    """Mixed polygon list splits into metals and vias."""
    metals_in = [_rect(0, 0, 10, 1, "met1"), _rect(5, 0, 6, 10, "met2")]
    vias_in = [_via(5.5, 5, layer="via1")]
    all_polys = metals_in + vias_in
    metals, vias = split_metal_via_polygons(all_polys)
    assert len(metals) == 2
    assert len(vias) == 1
    assert metals[0].layer == "met1"
    assert vias[0].layer == "via1"


def test_split_metal_via_polygons_empty():
    metals, vias = split_metal_via_polygons([])
    assert metals == []
    assert vias == []


def test_split_metal_via_polygons_via0_layer():
    """via0 (poly contact) must be recognized as a via layer."""
    polys = [_rect(0, 0, 2, 2, "met1"), _via(1, 1, layer="via0")]
    metals, vias = split_metal_via_polygons(polys)
    assert len(metals) == 1
    assert len(vias) == 1
    assert vias[0].layer == "via0"


def test_compute_for_net_detects_missing_via_from_mixed_polygons():
    """Overlapping met1+met2 without via polygon → missing_via_count > 0."""
    met1 = _rect(0, 0, 2, 4, "met1")
    met2 = _rect(0, 0, 2, 4, "met2")
    mixed = [met1, met2]
    metals, vias = split_metal_via_polygons(mixed)
    assert len(vias) == 0
    t = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("MISSING_VIA", metals, vias, _tech_layers(), t, golden_metrics=None)
    assert m["missing_via_count"] > 0
    assert m["via_coverage"] < 1.0


def test_low_similarity_no_bypass():
    """Net similar in shape (h_ratio passes) but with low similarity to golden
    should still fail soft gates — bypass requires similarity >= min."""
    metrics = {
        "h_ratio": 0.50,  # > 0.15, soft fail
        "v_ratio": 0.50,
        "r_total": 10.0, "c_total": 50.0, "effective_tau_ps": 1.0,
        "via_coverage": 0.90, "missing_via_count": 0,
        "similarity_score": 60.0,  # < 80.0 min_similarity
    }
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    pass_, reasons = check_gates(metrics, thresholds, has_golden=True)
    assert pass_ is False
    # soft fail not bypassed, sim fail → reasons contain both
    assert any("h_ratio" in r for r in reasons)
    assert any("similarity" in r for r in reasons)


# --- Task 7: RC equality between Properties (legacy engine path) and Routing Review ---
# Uses the upload/_rebuild path + app_state to simulate what Properties panel sees.

def test_rc_values_match_between_properties_and_routing_review():
    """RC values (R, C, τ) from legacy Properties (via _rebuild_engine_from_nets + engine.net_rc_data)
    must match those from routing review default path (compute_for_net with rc_model=None).
    Uses get_thresholds() for the thresholds passed to routing path.
    """
    import sys
    # ensure path
    if '.' not in sys.path:
        sys.path.insert(0, '.')

    import pytest

    from app.callbacks import _rebuild_engine_from_nets
    from app.routing_state import routing_state
    from app.state import app_state
    from config.routing_thresholds import RoutingThresholds
    from core.data_parsing import import_shape_from_file
    from core.routing_metrics import compute_for_net, split_metal_via_polygons

    # Clean state
    app_state.clear_nets()
    routing_state.reset_review()
    # reset thresholds/mode to known
    routing_state.current_preset = "sram_7nm_wl"
    routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    routing_state.custom_thresholds = None
    routing_state.set_frozen_mode(True)

    # Load a net using same mechanism as upload (import_shape gives polygons + net_id)
    rec = import_shape_from_file("tests/shapes_test_normal.txt", custom_net_name="RC_MATCH_NET")
    assert rec is not None
    net_id = rec["net_id"]
    polygons = rec["polygons"]

    # Simulate what upload callback does
    app_state.nets_data[net_id] = {
        "net_id": net_id,
        "polygons": polygons,
        "source": rec.get("source", "_default"),
        "net_name": rec.get("net_name", "RC_MATCH_NET"),
    }

    # Upload path: rebuilds engine + calls calculate_net_rc for Properties
    _rebuild_engine_from_nets()
    assert app_state.engine is not None
    assert net_id in app_state.engine.net_rc_data
    rc_legacy = app_state.engine.net_rc_data[net_id]

    # Routing Review path: same net data -> compute_for_net (rc_model=None default)
    tech = app_state.config.tech_config.layers
    thresholds = routing_state.get_thresholds()  # authoritative via public helper (Task 7)
    metals, vias = split_metal_via_polygons(polygons)
    m = compute_for_net(net_id, metals, vias, tech, thresholds, golden_metrics=None, rc_model=None)

    # Assert R/C/τ match (as Properties would show vs Review cards/table)
    assert m["r_total"] == pytest.approx(rc_legacy.total_resistance, rel=1e-12, abs=1e-12)
    assert m["c_total"] == pytest.approx(rc_legacy.total_capacitance, rel=1e-12, abs=1e-12)
    assert m["effective_tau_ps"] == pytest.approx(rc_legacy.tau_rc, rel=1e-9, abs=1e-9)

    # cleanup
    app_state.clear_nets()
