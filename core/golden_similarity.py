"""Golden Net similarity scoring.

Approach:
1. Build a feature vector for each net from the 6 routing metrics.
2. Normalize (L2) so different units (μm, Ω, fF) are comparable.
3. Compute weighted cosine similarity.
4. Output: 0-100 score, plus a per-feature delta dict (relative % change).

This is a routing-focused similarity, not a full shape-IoU.
For shape geometric similarity, use a separate Hausdorff/IoU pass (out of scope here).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

# Canonical feature names (order matters for vector indexing)
FEATURE_NAMES: List[str] = [
    "h_ratio",
    "v_ratio",
    "total_len",
    "via_count",
    "r_total",
    "c_total",
    "effective_tau_ps",
    "bbox_aspect",
]

DEFAULT_WEIGHTS: Dict[str, float] = {
    "h_ratio": 2.0,         # direction matters most
    "v_ratio": 2.0,
    "total_len": 1.0,
    "via_count": 0.5,
    "r_total": 1.5,
    "c_total": 1.0,
    "effective_tau_ps": 2.0,  # delay matters
    "bbox_aspect": 0.5,
}


def compute_feature_vector(metrics: Dict) -> List[float]:
    """Build feature vector in FEATURE_NAMES order, then L2-normalize."""
    vec = [float(metrics.get(name, 0.0)) for name in FEATURE_NAMES]
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cosine_similarity(v1: List[float], v2: List[float], weights: Dict[str, float]) -> float:
    """Weighted cosine similarity in [-1, 1]."""
    w = [weights.get(name, 1.0) for name in FEATURE_NAMES]
    dot = sum(a * b * wi for a, b, wi in zip(v1, v2, w))
    n1 = math.sqrt(sum((a * wi) ** 2 for a, wi in zip(v1, w)))
    n2 = math.sqrt(sum((b * wi) ** 2 for b, wi in zip(v2, w)))
    if n1 == 0 or n2 == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (n1 * n2)))


def compare_to_golden(
    golden_metrics: Dict,
    other_metrics: Dict,
    weights: Dict[str, float] = None,
) -> Tuple[float, Dict[str, float]]:
    """Compare a net to the Golden net.

    Args:
        golden_metrics: Dict with the 8 FEATURE_NAMES keys.
        other_metrics: Same shape dict for the comparison net.
        weights: Per-feature weights (defaults to DEFAULT_WEIGHTS).

    Returns:
        (similarity_score_0_100, deltas_dict)
        deltas_dict maps feature name → relative % change (other - golden) / golden * 100.
    """
    weights = weights or DEFAULT_WEIGHTS
    v1 = compute_feature_vector(golden_metrics)
    v2 = compute_feature_vector(other_metrics)
    cos = _cosine_similarity(v1, v2, weights)
    score = max(0.0, min(100.0, (cos + 1.0) * 50.0))  # map [-1,1] → [0,100]

    deltas: Dict[str, float] = {}
    for name in FEATURE_NAMES:
        g = float(golden_metrics.get(name, 0.0))
        o = float(other_metrics.get(name, 0.0))
        if g == 0:
            deltas[name] = 0.0 if o == 0 else 100.0
        else:
            deltas[name] = (o - g) / g * 100.0

    return score, deltas
