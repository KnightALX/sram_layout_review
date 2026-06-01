#!/usr/bin/env python3
"""
Matching Analyzer - SRAM信号匹配分析
用于BL/BLB、WL等差分对的匹配度量化分析
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

from review_engine import Point, Polygon, MatchingAnalysis, NetRCData


def analyze_pair_matching(
    net1: str,
    net2: str,
    rc1: NetRCData,
    rc2: NetRCData,
    polygons1: List[Polygon],
    polygons2: List[Polygon],
    design_rules: Dict
) -> MatchingAnalysis:
    """分析两个net的匹配度。

    Args:
        net1: 第一个net名称
        net2: 第二个net名称
        rc1: 第一个net的RC数据
        rc2: 第二个net的RC数据
        polygons1: 第一个net的多边形
        polygons2: 第二个net的多边形
        design_rules: 设计规则

    Returns:
        MatchingAnalysis匹配分析结果
    """
    length1 = rc1.total_length
    length2 = rc2.total_length
    length_ratio = length1 / length2 if length2 > 0 else 1.0

    r1 = rc1.total_resistance
    r2 = rc2.total_resistance
    resistance_ratio = r1 / r2 if r2 > 0 else 1.0

    c1 = rc1.total_capacitance
    c2 = rc2.total_capacitance
    capacitance_ratio = c1 / c2 if c2 > 0 else 1.0

    via_diff = abs(rc1.via_count - rc2.via_count)

    all_layers = set(rc1.layer_usage.keys()) | set(rc2.layer_usage.keys())
    layer_diff = {}
    for layer in all_layers:
        cnt1 = rc1.layer_usage.get(layer, 0)
        cnt2 = rc2.layer_usage.get(layer, 0)
        if cnt1 != cnt2:
            layer_diff[layer] = cnt2 - cnt1

    score = 100.0
    issues: List[str] = []
    suggestions: List[str] = []

    max_length_diff = max(length1, length2)
    if max_length_diff > 0:
        length_deviation = abs(length1 - length2) / max_length_diff
        if length_deviation > 0.05:
            penalty = length_deviation * 30
            score -= penalty
            issues.append(f"Length mismatch: {abs(length1-length2):.1f}μm ({length_deviation*100:.1f}%)")
            suggestions.append("Balance wire lengths between matched nets")

    r_tolerance = design_rules.get('max_rc_variation', 0.1)
    if abs(resistance_ratio - 1.0) > r_tolerance:
        score -= 20
        issues.append(f"Resistance mismatch: R1/R2 = {resistance_ratio:.2f}")
        suggestions.append("Ensure consistent resistance for matched signals")

    if abs(capacitance_ratio - 1.0) > r_tolerance:
        score -= 15
        issues.append(f"Capacitance mismatch: C1/C2 = {capacitance_ratio:.2f}")
        suggestions.append("Balance capacitive loading")

    if via_diff > 1:
        score -= via_diff * 5
        issues.append(f"Via count difference: {via_diff}")
        suggestions.append("Match via count for symmetry")

    if layer_diff:
        score -= len(layer_diff) * 3
        issues.append(f"Layer usage differs: {list(layer_diff.keys())}")
        suggestions.append("Use consistent layer assignments")

    score = max(0, min(100, score))

    bbox_sim = 0.5
    if polygons1 and polygons2:
        bbox1 = _get_overall_bbox(polygons1)
        bbox2 = _get_overall_bbox(polygons2)
        bbox_sim = _calculate_bbox_similarity(bbox1, bbox2)

    centroid_dist = 0.0
    if polygons1 and polygons2:
        c1 = _calculate_centroid(polygons1)
        c2 = _calculate_centroid(polygons2)
        centroid_dist = c1.distance_to(c2)

    return MatchingAnalysis(
        net1=net1,
        net2=net2,
        match_score=score,
        length_ratio=length_ratio,
        resistance_ratio=resistance_ratio,
        capacitance_ratio=capacitance_ratio,
        via_count_diff=via_diff,
        layer_usage_diff=layer_diff,
        bbox_similarity=bbox_sim,
        centroid_distance=centroid_dist,
        routing_pattern_similarity=0.8 if score > 70 else 0.5,
        issues=issues,
        suggestions=suggestions
    )


def _get_overall_bbox(polygons: List[Polygon]) -> Tuple[float, float, float, float]:
    """获取多边形集合的整体bbox"""
    if not polygons:
        return (0, 0, 0, 0)
    xmins, ymins, xmaxs, ymaxs = zip(*[p.bbox for p in polygons])
    return (min(xmins), min(ymins), max(xmaxs), max(ymaxs))


def _calculate_centroid(polygons: List[Polygon]) -> Point:
    """计算多边形集合的质心"""
    if not polygons:
        return Point(0, 0)
    total_area = sum(p.area for p in polygons)
    if total_area == 0:
        centers = [p.center for p in polygons]
        return Point(
            sum(c.x for c in centers) / len(centers),
            sum(c.y for c in centers) / len(centers)
        )
    cx = sum(p.center.x * p.area for p in polygons) / total_area
    cy = sum(p.center.y * p.area for p in polygons) / total_area
    return Point(cx, cy)


def _calculate_bbox_similarity(
    bbox1: Tuple[float, float, float, float],
    bbox2: Tuple[float, float, float, float]
) -> float:
    """计算两个bbox的相似度"""
    w1 = bbox1[2] - bbox1[0]
    h1 = bbox1[3] - bbox1[1]
    w2 = bbox2[2] - bbox2[0]
    h2 = bbox2[3] - bbox2[1]

    if w1 + h1 == 0 or w2 + h2 == 0:
        return 0.5

    size_sim = 1.0 - abs((w1+h1) - (w2+h2)) / max(w1+h1, w2+h2)

    ar1 = w1 / h1 if h1 > 0 else 1
    ar2 = w2 / h2 if h2 > 0 else 1
    ar_sim = 1.0 - abs(ar1 - ar2) / max(ar1, ar2, 1)

    return (size_sim + ar_sim) / 2
