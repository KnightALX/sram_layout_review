"""Tests for routing PPTX report."""
import os
import sys
import tempfile

sys.path.insert(0, '.')
from app.routing_state import RoutingState
from report.routing_pptx import generate_routing_pptx


def _make_state():
    s = RoutingState()
    s.current_preset = "sram_7nm_wl"
    s.golden_net_name = "WL0"
    s.golden_metrics = {"h_ratio": 0.1, "v_ratio": 0.9, "total_len": 10,
                        "via_count": 2, "r_total": 10, "c_total": 2,
                        "effective_tau_ps": 5, "bbox_aspect": 1.0}
    s.batch_net_names = ["WL0", "WL1"]
    s.batch_results = {
        "WL0": {"net_name": "WL0", "h_len": 1, "v_len": 9, "h_ratio": 0.1, "v_ratio": 0.9,
                "dominant": "V", "missing_via_count": 0, "via_coverage": 1.0,
                "missing_locations": [], "r_total": 10, "c_total": 2, "rc_product": 20,
                "effective_tau_ps": 5, "total_length": 10, "via_count": 2,
                "similarity_score": 100, "deltas": {}, "gate_pass": True,
                "gate_fail_reasons": [], "violations": [], "bbox_aspect": 1.0,
                "per_polygon_dir": []},
        "WL1": {"net_name": "WL1", "h_len": 5, "v_len": 5, "h_ratio": 0.5, "v_ratio": 0.5,
                "dominant": "H", "missing_via_count": 1, "via_coverage": 0.6,
                "missing_locations": [{"x": 1, "y": 2, "layer_a": "met1", "layer_b": "met2", "overlap_area": 1}],
                "r_total": 200, "c_total": 50, "rc_product": 10000,
                "effective_tau_ps": 20, "total_length": 10, "via_count": 1,
                "similarity_score": 50, "deltas": {"total_len": 0}, "gate_pass": False,
                "gate_fail_reasons": ["h_ratio over"], "violations": [],
                "bbox_aspect": 1.0, "per_polygon_dir": []},
    }
    return s


class FakeAppState:
    nets_data = {"WL0": {"polygons": []}, "WL1": {"polygons": []}}


def test_generate_routing_pptx_creates_file():
    s = _make_state()
    app_s = FakeAppState()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "report.pptx")
        generate_routing_pptx(s, app_s, out)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 1000
