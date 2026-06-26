"""Tests for routing violation dataclass."""
from core.routing_violation import RoutingViolation, ViolationKind


def test_create_h_ratio_violation():
    v = RoutingViolation.h_ratio(net_name="WL0", h_ratio=0.50, limit=0.15)
    assert v.kind == ViolationKind.H_RATIO
    assert v.net_name == "WL0"
    assert v.severity == "critical"


def test_create_missing_via_violation():
    v = RoutingViolation.missing_via(net_name="BL0", x=1.0, y=2.0, layer="via1")
    assert v.kind == ViolationKind.MISSING_VIA
    assert v.x == 1.0
    assert v.y == 2.0


def test_serialization_round_trip():
    v = RoutingViolation.tau_ps(net_name="WL0", tau_ps=20.0, limit=12.5)
    d = v.to_dict()
    v2 = RoutingViolation.from_dict(d)
    assert v2.net_name == v.net_name
    assert v2.tau_ps == v.tau_ps


def test_all_kinds_covered():
    kinds = {k.value for k in ViolationKind}
    assert "h_ratio" in kinds
    assert "v_ratio" in kinds
    assert "r_total" in kinds
    assert "c_total" in kinds
    assert "tau_ps" in kinds
    assert "via_coverage" in kinds
    assert "missing_via" in kinds
    assert "similarity" in kinds


def test_violation_has_direction_and_range():
    from config.routing_thresholds import Range
    from core.routing_violation import RoutingViolation, ViolationKind

    rng = Range(0.0, 0.15)
    v = RoutingViolation(
        kind=ViolationKind.H_RATIO, net_name="WL_0",
        measured=0.22, direction="high",
        range_low=rng.low, range_high=rng.high,
    )
    assert v.direction == "high"
    assert v.range_low == 0.0
    assert v.range_high == 0.15
    assert v.measured == 0.22


def test_violation_factory_uses_range():
    from config.routing_thresholds import Range
    from core.routing_violation import RoutingViolation

    rng = Range(0.0, 100.0)
    v = RoutingViolation.r_ohm("WL_0", 150.0, rng)
    assert v.direction == "high"
    assert v.measured == 150.0
    assert v.range_high == 100.0
