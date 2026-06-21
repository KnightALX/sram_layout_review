"""Tests for the new RC Prediction Tab features:
- effective_tau model variations (lumped_pi / t_model / distributed_5)
- compute_net_metrics_with_tau end-to-end with rc_model
- rc_persistence (PDK import / export / history)
"""
import json

import pytest

from app.rc_model import ModelType, RCModelConfig
from app.rc_persistence import (
    HistoryStack,
    merge_pdk_into,
    parse_pdk_text,
    to_yaml,
)
from app.rc_persistence import (
    history as rc_history,
)
from app.routing_state import routing_state
from core.effective_tau import compute_effective_tau

# --- effective_tau model variations ----------------------------------------

class _Seg:
    def __init__(self, length=100.0, width=0.05, layer="met1"):
        self.length = length
        self.width = width
        self.layer = layer


def test_lumped_pi_tau():
    """lumped_pi = R * C (worst case)."""
    tau = compute_effective_tau([_Seg()], r_per_sq=0.15, c_per_um=0.20,
                                method="lumped_pi")
    # R = 0.15 * 100 / 0.05 = 300 Ω
    # C = 0.20*100 + 0.1*2*(100.05) = 40.01 fF
    # tau = 300 * 40.01 * 1e-3 = 12.003 ps
    assert tau == pytest.approx(12.003, rel=1e-4)


def test_t_model_tau_is_half_lumped():
    """t_model = R * C / 2 (symmetric driver)."""
    lumped = compute_effective_tau([_Seg()], 0.15, 0.20, method="lumped_pi")
    t = compute_effective_tau([_Seg()], 0.15, 0.20, method="t_model")
    assert t == pytest.approx(lumped / 2.0, rel=1e-9)


def test_distributed_5_tau_lte_lumped():
    """Distributed N=5 model: factor = (N²-1)/(6·N²) = 24/150 = 0.16 < 0.5."""
    lumped = compute_effective_tau([_Seg()], 0.15, 0.20, method="lumped_pi")
    d5 = compute_effective_tau([_Seg()], 0.15, 0.20, method="distributed_5", n_segments=5)
    assert d5 < lumped
    assert d5 == pytest.approx(lumped * 24.0 / 150.0, rel=1e-9)


def test_distributed_ladder_known_factor():
    """Verify the explicit ladder factor formula."""
    n = 10
    expected_factor = (n * n - 1) / (6.0 * n * n)  # 99/600 = 0.165
    lumped = compute_effective_tau([_Seg()], 0.15, 0.20, method="lumped_pi")
    d = compute_effective_tau([_Seg()], 0.15, 0.20,
                              method="distributed_5", n_segments=n)
    assert d == pytest.approx(lumped * expected_factor, rel=1e-9)


def test_invalid_method_raises():
    with pytest.raises(ValueError, match="Unknown tau method"):
        compute_effective_tau([_Seg()], 0.15, 0.20, method="definitely_not_a_model")


def test_empty_segments_returns_zero():
    assert compute_effective_tau([], 0.15, 0.20) == 0.0


# --- PDK import / export ---------------------------------------------------

def test_parse_pdk_yaml():
    text = """
tech_node: 5nm
temperature_c: 100
metal_r_sheet:
  met1: 0.10
  met2: 0.08
"""
    d = parse_pdk_text(text, "pdk_5nm.yaml")
    assert d["tech_node"] == "5nm"
    assert d["temperature_c"] == 100
    assert d["metal_r_sheet"]["met1"] == 0.10


def test_parse_pdk_json():
    text = json.dumps({"tech_node": "3nm", "dielectric_constant": 2.5})
    d = parse_pdk_text(text, "pdk.json")
    assert d["tech_node"] == "3nm"
    assert d["dielectric_constant"] == 2.5


def test_parse_pdk_invalid_text():
    with pytest.raises(ValueError, match="Could not parse"):
        parse_pdk_text("not :: valid : yaml : at : all", "x.txt")


def test_parse_pdk_top_level_not_dict():
    with pytest.raises(ValueError, match="mapping"):
        parse_pdk_text("- a\n- b\n", "x.yaml")


def test_parse_pdk_empty():
    with pytest.raises(ValueError, match="Empty"):
        parse_pdk_text("", "x.yaml")


def test_merge_pdk_overlays_scalars():
    base = RCModelConfig()
    new = merge_pdk_into(base, {"tech_node": "5nm", "temperature_c": 100.0})
    assert new.tech_node == "5nm"
    assert new.temperature_c == 100.0
    # Unchanged fields stay
    assert new.dielectric_constant == base.dielectric_constant


def test_merge_pdk_overlays_per_layer():
    base = RCModelConfig()
    pdk = {"metal_r_sheet": {"met1": 0.05}}  # override only met1
    new = merge_pdk_into(base, pdk)
    assert new.metal_r_sheet["met1"] == 0.05
    # Other layers preserved
    assert new.metal_r_sheet["met2"] == base.metal_r_sheet["met2"]


def test_merge_pdk_adds_new_layer():
    base = RCModelConfig()
    pdk = {"metal_r_sheet": {"met8": 0.03}}
    new = merge_pdk_into(base, pdk)
    assert "met8" in new.metal_r_sheet
    assert new.metal_r_sheet["met8"] == 0.03
    # All other met1-met7 still there
    assert "met1" in new.metal_r_sheet


def test_to_yaml_roundtrip():
    cfg = RCModelConfig(tech_node="5nm", temperature_c=100.0,
                        model_type=ModelType.T_MODEL.value)
    cfg.validate()
    text = to_yaml(cfg)
    parsed = parse_pdk_text(text, "export.yaml")
    assert parsed["tech_node"] == "5nm"
    assert parsed["temperature_c"] == 100.0
    assert parsed["model_type"] == "t_model"


# --- History stack ---------------------------------------------------------

def test_history_push_pop():
    h = HistoryStack(maxlen=3)
    a = RCModelConfig(tech_node="A")
    a.validate()
    b = RCModelConfig(tech_node="B")
    b.validate()
    c = RCModelConfig(tech_node="C")
    c.validate()
    h.push(a)
    h.push(b)
    h.push(c)
    assert h.pop().tech_node == "C"
    assert h.pop().tech_node == "B"
    assert h.pop().tech_node == "A"
    assert h.pop() is None


def test_history_maxlen():
    h = HistoryStack(maxlen=2)
    for i in range(5):
        cfg = RCModelConfig(tech_node=f"n{i}")
        h.push(cfg)
    assert len(h) == 2


def test_module_level_history_singleton():
    rc_history().push(RCModelConfig(tech_node="singleton_test"))
    popped = rc_history().pop()
    assert popped is not None
    assert popped.tech_node == "singleton_test"


# --- End-to-end: routing_state.get_rc_model flows into compute_for_net ------

def test_routing_state_active_model_is_custom():
    """When custom_rc_model is set, get_rc_model returns it."""
    custom = RCModelConfig(tech_node="3nm", temperature_c=125.0)
    custom.validate()
    routing_state.custom_rc_model = custom
    try:
        m = routing_state.get_rc_model()
        assert m.tech_node == "3nm"
        assert m.temperature_c == 125.0
    finally:
        routing_state.custom_rc_model = None
