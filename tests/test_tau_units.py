"""Regression: τ must be in ps and consistent across Legacy + Routing + RC model."""
import sys

sys.path.insert(0, ".")

import pytest

from app.rc_model import RCModelConfig
from config.routing_thresholds import RoutingThresholds
from config_system import get_sram_7nm_config
from core.effective_tau import OHM_FF_TO_PS, ohm_ff_to_ps
from core.rc_calculator import compute_net_metrics_with_tau
from core.routing_metrics import compute_for_net
from review_engine import Point, Polygon, ProfessionalLayoutReviewEngine


def _long_wire_polygons():
    return [Polygon(
        points=[Point(0, 0), Point(1000, 0), Point(1000, 0.1), Point(0, 0.1)],
        layer="met1",
    )]


def test_legacy_and_routing_tau_agree_without_rc_model():
    """Legacy tau_rc and routing effective_tau_ps use the same Ω·fF→ps convention."""
    cfg = get_sram_7nm_config()
    tech = cfg.tech_config.layers
    polys = _long_wire_polygons()
    net = "WL0"

    engine = ProfessionalLayoutReviewEngine(cfg)
    engine.add_net_polygons(net, polys)
    rc = engine.calculate_net_rc(net)

    thresh = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net(net, polys, [], tech, thresh, rc_model=None)

    expected = ohm_ff_to_ps(rc.total_resistance, rc.total_capacitance, method="lumped")
    assert rc.tau_rc == pytest.approx(expected, rel=1e-6)
    assert m["effective_tau_ps"] == pytest.approx(expected, rel=1e-6)


def test_rc_model_tau_tracks_displayed_rc_totals():
    """When RCModelConfig is active, τ must follow the displayed r_total/c_total."""
    cfg = get_sram_7nm_config()
    tech = cfg.tech_config.layers
    polys = _long_wire_polygons()
    model = RCModelConfig(temperature_c=125.0)

    m = compute_net_metrics_with_tau("WL0", polys, [], tech, rc_model=model)
    expected = ohm_ff_to_ps(
        m["r_total"], m["c_total"], method=model.model_type, n_segments=20,
    )
    assert m["effective_tau_ps"] == pytest.approx(expected, rel=1e-6)


def test_rc_model_temperature_increases_tau():
    """Higher sheet-R tempco should increase τ when RC model is used."""
    tech = get_sram_7nm_config().tech_config.layers
    polys = _long_wire_polygons()
    cold = compute_net_metrics_with_tau("WL0", polys, [], tech, rc_model=RCModelConfig(temperature_c=25.0))
    hot = compute_net_metrics_with_tau("WL0", polys, [], tech, rc_model=RCModelConfig(temperature_c=150.0))
    assert hot["effective_tau_ps"] > cold["effective_tau_ps"]


def test_ohm_ff_conversion_constant():
    assert OHM_FF_TO_PS == pytest.approx(1e-3)
    # 1000 Ω × 500 fF = 500000 fs → 500 ps
    assert ohm_ff_to_ps(1000.0, 500.0) == pytest.approx(500.0)
