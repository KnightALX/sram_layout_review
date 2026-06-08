"""Smoke tests for the RC Prediction tab (app/rc_*.py)."""
import pytest

from app.rc_model import RCModelConfig, ModelType
from app.rc_visualization import safe_render_stack_3d_figure
from app.routing_state import routing_state


# --- RCModelConfig ---------------------------------------------------------

def test_default_config_validates():
    cfg = RCModelConfig()
    cfg.validate()  # must not raise


def test_predict_wire_resistance_scales_with_length():
    cfg = RCModelConfig(temperature_c=25.0)  # no tempco correction
    r1 = cfg.predict_wire_resistance("met1", 50.0)
    r2 = cfg.predict_wire_resistance("met1", 100.0)
    assert r2 == pytest.approx(2.0 * r1, rel=1e-9)


def test_predict_wire_resistance_tempco():
    cfg25 = RCModelConfig(temperature_c=25.0)
    cfg85 = RCModelConfig(temperature_c=85.0)
    r25 = cfg25.predict_wire_resistance("met1", 100.0)
    r85 = cfg85.predict_wire_resistance("met1", 100.0)
    # tempco 0.004 × ΔT(60) = 24 % increase
    assert r85 == pytest.approx(r25 * 1.24, rel=1e-6)


def test_predict_wire_capacitance_positive():
    cfg = RCModelConfig()
    for layer in cfg.metal_layers():
        c = cfg.predict_wire_capacitance(layer, 100.0)
        assert c > 0, f"{layer} C should be positive, got {c}"


def test_predict_via_resistance_tempco():
    cfg25 = RCModelConfig(temperature_c=25.0)
    cfg85 = RCModelConfig(temperature_c=85.0)
    r25 = cfg25.predict_via_resistance("via1")
    r85 = cfg85.predict_via_resistance("via1")
    assert r85 > r25  # positive tempco
    assert r85 == pytest.approx(r25 * (1.0 + 0.003 * 60.0), rel=1e-6)


def test_validate_rejects_bad_model_type():
    cfg = RCModelConfig(model_type="not_a_model")
    with pytest.raises(ValueError, match="model_type"):
        cfg.validate()


def test_validate_rejects_bad_epsilon():
    cfg = RCModelConfig(dielectric_constant=99.0)
    with pytest.raises(ValueError, match="dielectric_constant"):
        cfg.validate()


def test_roundtrip_to_from_dict():
    cfg = RCModelConfig(temperature_c=100.0, model_type="t_model",
                        dielectric_constant=2.5)
    cfg.validate()
    d = cfg.to_dict()
    cfg2 = RCModelConfig.from_dict(d)
    assert cfg == cfg2


def test_effective_model_segments():
    cfg = RCModelConfig(model_type=ModelType.LUMPED_PI.value)
    assert cfg.effective_model_segments(1000.0) == 1
    cfg = RCModelConfig(model_type=ModelType.DISTRIBUTED_5.value,
                        length_per_segment_um=50.0)
    assert cfg.effective_model_segments(250.0) == 5


# --- routing_state integration --------------------------------------------

def test_routing_state_has_rc_model():
    assert hasattr(routing_state, "rc_model")
    assert hasattr(routing_state, "custom_rc_model")
    assert hasattr(routing_state, "get_rc_model")
    m = routing_state.get_rc_model()
    assert isinstance(m, RCModelConfig)


# --- 3D rendering ---------------------------------------------------------

def test_safe_render_returns_figure():
    fig = safe_render_stack_3d_figure(RCModelConfig())
    assert "data" in fig
    assert "layout" in fig
    # The render path should embed a base64 image
    images = fig["layout"].get("images", [])
    assert images, "Expected at least one embedded image in the figure"
    src = images[0]["source"]
    assert src.startswith("data:image/png;base64,")
    assert len(src) > 100  # non-trivial payload


# --- Tab factory ----------------------------------------------------------

def test_create_rc_prediction_tab_runs():
    from app.rc_prediction import create_rc_prediction_tab
    tab = create_rc_prediction_tab()
    assert tab is not None
