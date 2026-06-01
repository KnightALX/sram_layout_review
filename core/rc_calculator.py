#!/usr/bin/env python3
"""
RC Calculator - 精确的电阻电容计算
"""

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from review_engine import Point, Polygon, WireSegment, Via, NetRCData


def _extract_layer_number(layer_name: str) -> int:
    """Extract layer number from layer name using robust regex.

    Handles patterns like:
    - 'met1', 'met2', 'metal1', 'metal2' -> 1, 2
    - 'via0', 'via1', 'via2' -> 0, 1, 2
    - 'm1', 'm2' -> 1, 2
    - 'poly', 'active' (no number) -> 0 as default

    Returns:
        Layer number as integer, defaults to 0 if no number found
    """
    if not layer_name:
        return 0

    layer_lower = layer_name.lower()

    patterns = [
        r'met(\d+)$', r'metal(\d+)$', r'via(\d+)$', r'^(\d+)$',
    ]

    for pattern in patterns:
        match = re.search(pattern, layer_lower)
        if match:
            return int(match.group(1))

    digits_match = re.search(r'(\d+)', layer_lower)
    if digits_match:
        return int(digits_match.group(1))

    return 0


def parse_polygons_to_wires(
    polygons: List[Polygon],
    net_name: str,
    tech_layers: Dict
) -> List[WireSegment]:
    """将多边形解析为走线段 - 用于RC计算。

    Args:
        polygons: 多边形列表
        net_name: net名称
        tech_layers: 工艺层配置字典

    Returns:
        WireSegment列表，用于RC计算
    """
    segments: List[WireSegment] = []

    layer_aliases = {
        'metal1': 'met1', 'm1': 'met1',
        'metal2': 'met2', 'm2': 'met2',
        'metal3': 'met3', 'm3': 'met3',
        'metal4': 'met4', 'm4': 'met4',
        'metal5': 'met5', 'm5': 'met5',
        'metal6': 'met6', 'm6': 'met6',
        'metal7': 'met7', 'm7': 'met7',
    }

    for poly in polygons:
        layer_name = poly.layer.lower()
        resolved_layer = layer_aliases.get(layer_name, layer_name)

        layer_info = tech_layers.get(resolved_layer, {})
        if not layer_info:
            layer_info = tech_layers.get(poly.layer, {})

        layer_type = layer_info.get('type', '')

        if layer_type != 'metal':
            is_likely_metal = (
                resolved_layer.startswith('met') or
                resolved_layer.startswith('m') and resolved_layer[1:].isdigit() or
                layer_name in layer_aliases
            )
            if not is_likely_metal:
                continue

            layer_info = {
                'type': 'metal',
                'min_width': 0.032,
                'resistance_per_sq': 0.15,
                'capacitance_per_um': 0.20,
            }

        points = poly.points
        if len(points) < 2:
            continue

        if poly.is_rectangular and len(points) >= 4:
            bbox = poly.bbox
            if poly.width > poly.height:
                y_center = (bbox[1] + bbox[3]) / 2
                segment = WireSegment(
                    start=Point(bbox[0], y_center),
                    end=Point(bbox[2], y_center),
                    layer=poly.layer,
                    width=poly.height,
                    net_name=net_name
                )
            else:
                x_center = (bbox[0] + bbox[2]) / 2
                segment = WireSegment(
                    start=Point(x_center, bbox[1]),
                    end=Point(x_center, bbox[3]),
                    layer=poly.layer,
                    width=poly.width,
                    net_name=net_name
                )
            segments.append(segment)
        else:
            for i in range(len(points) - 1):
                seg_length = points[i].distance_to(points[i+1])
                if seg_length > 0.01:
                    width = poly.area / poly.perimeter * 2 if poly.perimeter > 0 else 0.032
                    segment = WireSegment(
                        start=points[i],
                        end=points[i+1],
                        layer=poly.layer,
                        width=max(width, layer_info.get('min_width', 0.032)),
                        net_name=net_name
                    )
                    segments.append(segment)

    return segments


def calculate_net_rc(
    net_name: str,
    polygons: List[Polygon],
    vias: List[Via],
    tech_layers: Dict
) -> NetRCData:
    """计算net的RC参数。

    Args:
        net_name: net名称
        polygons: 多边形列表
        vias: 通孔列表
        tech_layers: 工艺层配置

    Returns:
        NetRCData包含RC计算结果
    """
    rc_data = NetRCData(net_name=net_name)

    if not polygons:
        return rc_data

    layer_aliases = {
        'metal1': 'met1', 'm1': 'met1',
        'metal2': 'met2', 'm2': 'met2',
        'metal3': 'met3', 'm3': 'met3',
        'metal4': 'met4', 'm4': 'met4',
        'metal5': 'met5', 'm5': 'met5',
        'metal6': 'met6', 'm6': 'met6',
        'metal7': 'met7', 'm7': 'met7',
    }

    wire_segments = parse_polygons_to_wires(polygons, net_name, tech_layers)
    rc_data.wire_segments = wire_segments

    for segment in wire_segments:
        layer_name = segment.layer.lower()
        resolved_layer = layer_aliases.get(layer_name, layer_name)

        layer_info = tech_layers.get(resolved_layer, {})
        if not layer_info:
            layer_info = tech_layers.get(segment.layer, {})

        if not layer_info:
            layer_info = {
                'resistance_per_sq': 0.15,
                'capacitance_per_um': 0.20,
                'min_width': 0.032,
            }

        r_per_sq = layer_info.get('resistance_per_sq', 0.15)
        c_per_um = layer_info.get('capacitance_per_um', 0.20)

        r = segment.resistance(r_per_sq)
        rc_data.total_resistance += r

        c = segment.capacitance(c_per_um)
        rc_data.total_capacitance += c
        rc_data.ground_capacitance += c * 0.7
        rc_data.coupling_capacitance += c * 0.3

        if segment.layer not in rc_data.layer_resistances:
            rc_data.layer_resistances[segment.layer] = 0.0
            rc_data.layer_capacitances[segment.layer] = 0.0
            rc_data.layer_usage[segment.layer] = 0

        rc_data.layer_resistances[segment.layer] += r
        rc_data.layer_capacitances[segment.layer] += c
        rc_data.layer_usage[segment.layer] += 1
        rc_data.total_length += segment.length

    for via in vias:
        rc_data.total_resistance += via.resistance
        rc_data.via_count += 1

    rc_data.total_area = sum(p.area for p in polygons)

    return rc_data


def compute_net_metrics_with_tau(
    net_name: str,
    polygons: List["Polygon"],
    vias: List["Via"],
    tech_layers: Dict,
    tau_method: str = "lumped",
) -> Dict:
    """Compute all RC + effective-tau metrics in one call.

    Returns a flat dict with keys: r_total, c_total, rc_product, effective_tau_ps,
    total_length, via_count, wire_segments.

    Existing `calculate_net_rc()` is left untouched for backward compat.
    """
    from core.effective_tau import compute_effective_tau

    rc_data = calculate_net_rc(net_name, polygons, vias, tech_layers)

    # Use the dominant metal layer's sheet R/C for tau estimation
    # (simple heuristic - could be weighted average)
    if rc_data.layer_resistances:
        dominant_layer = max(rc_data.layer_resistances, key=rc_data.layer_resistances.get)
        layer_info = tech_layers.get(dominant_layer, {})
        r_per_sq = layer_info.get("resistance_per_sq", 0.15)
        c_per_um = layer_info.get("capacitance_per_um", 0.20)
    else:
        r_per_sq, c_per_um = 0.15, 0.20

    tau_ps = compute_effective_tau(
        rc_data.wire_segments, r_per_sq, c_per_um, method=tau_method
    )

    return {
        "net_name": net_name,
        "r_total": rc_data.total_resistance,
        "c_total": rc_data.total_capacitance,
        "rc_product": rc_data.total_resistance * rc_data.total_capacitance,
        "effective_tau_ps": tau_ps,
        "total_length": rc_data.total_length,
        "via_count": rc_data.via_count,
        "wire_segments": rc_data.wire_segments,
    }
