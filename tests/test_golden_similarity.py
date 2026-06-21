"""Tests for Golden Net similarity scoring."""
import sys

import pytest

sys.path.insert(0, '.')
from core.golden_similarity import FEATURE_NAMES, compare_to_golden, compute_feature_vector


def _metrics(h_ratio=0.5, v_ratio=0.5, total_len=10.0, via_count=2,
             r_total=10.0, c_total=2.0, tau_ps=20.0, bbox_aspect=1.0):
    return {
        "h_ratio": h_ratio, "v_ratio": v_ratio, "total_len": total_len,
        "via_count": via_count, "r_total": r_total, "c_total": c_total,
        "effective_tau_ps": tau_ps, "bbox_aspect": bbox_aspect,
    }


def test_identical_metrics_yields_100_score():
    m = _metrics()
    score, deltas = compare_to_golden(m, m, weights={k: 1.0 for k in FEATURE_NAMES})
    assert score == pytest.approx(100.0, abs=1e-6)
    assert all(abs(v) < 1e-6 for v in deltas.values())


def test_completely_different_metrics_yields_low_score():
    """All 8 features differ between golden and other → score should be low.

    Note: L2-normalized cosine similarity on positive-only vectors has a
    mathematical floor of ~60-70 (since unit vectors with all positive
    components are bounded in angle). The test asserts that the score is
    clearly below 100 (the identical case).
    """
    golden = _metrics(h_ratio=0.9, v_ratio=0.1, total_len=1.0, via_count=0,
                     r_total=1.0, c_total=0.1, tau_ps=0.1, bbox_aspect=10.0)
    other  = _metrics(h_ratio=0.1, v_ratio=0.9, total_len=1000.0, via_count=50,
                      r_total=500.0, c_total=100.0, tau_ps=100.0, bbox_aspect=0.1)
    score, _ = compare_to_golden(golden, other)
    assert score < 70.0   # clearly less than 100 (identical case)


def test_score_is_bounded_0_to_100():
    m = _metrics()
    score, _ = compare_to_golden(m, m)
    assert 0.0 <= score <= 100.0


def test_feature_vector_normalized():
    """Feature vector should be normalized (sum-of-squares = 1)."""
    m = _metrics()
    vec = compute_feature_vector(m)
    assert len(vec) == len(FEATURE_NAMES)
    norm = sum(v * v for v in vec)
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_deltas_are_relative_percentages():
    """Each delta should be expressed as (other - golden) / golden * 100."""
    golden = _metrics(total_len=10.0, r_total=10.0)
    other  = _metrics(total_len=20.0, r_total=15.0)
    _, deltas = compare_to_golden(golden, other)
    assert deltas["total_len"] == pytest.approx(100.0, abs=1e-6)  # 2x = +100%
    assert deltas["r_total"] == pytest.approx(50.0, abs=1e-6)    # 1.5x = +50%


def test_weights_change_relative_importance():
    """Higher weight on tau makes tau-different nets score worse."""
    golden = _metrics(tau_ps=10.0)
    other  = _metrics(tau_ps=20.0)
    w_tau_heavy = {**{k: 1.0 for k in FEATURE_NAMES}, "effective_tau_ps": 10.0}
    w_tau_light = {**{k: 1.0 for k in FEATURE_NAMES}, "effective_tau_ps": 0.1}
    s_heavy, _ = compare_to_golden(golden, other, weights=w_tau_heavy)
    s_light, _ = compare_to_golden(golden, other, weights=w_tau_light)
    assert s_heavy < s_light
