"""Smoke tests for legacy Full Review engine path."""
import sys

sys.path.insert(0, '.')

from config_system import get_sram_7nm_config
from core.data_parsing import import_shape_from_file
from review_engine import ProfessionalLayoutReviewEngine


def test_run_full_review_sets_summary():
    result = import_shape_from_file("tests/shapes_test_normal.txt", custom_net_name="NORMAL")
    assert result is not None
    net_id = result["net_id"]
    polygons = result["polygons"]
    config = get_sram_7nm_config()
    engine = ProfessionalLayoutReviewEngine(config)
    engine.add_net_polygons(net_id, polygons)
    engine.calculate_net_rc(net_id)
    summary = engine.run_full_review()
    assert summary.total_nets >= 1
    assert summary.total_violations >= 0


def test_review_completed_flag_pattern():
    from app.state import AppState
    s = AppState()
    assert s.review_completed is False
    s.review_completed = True
    assert s.review_completed is True
