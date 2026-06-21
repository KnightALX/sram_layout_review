#!/usr/bin/env python3
"""
QTY Rules - Layout Quality Rules
包含复杂多边形、通孔链、覆盖率等检查
"""

import math
from typing import Dict, List

from rules.base_rule import BaseRule, ConstraintType, RuleParameter, Severity
from rules.registry import register_rule


@register_rule("qty")
class ExcessiveViaChainRule(BaseRule):
    """过长通孔链检查"""

    RULE_ID = "QTY001"
    NAME = "Excessive Via Chain"
    DESCRIPTION = "检查过长的通孔链（增加电阻）"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = [".*"]

    PARAMETERS = [
        RuleParameter(name="max_via_chain_length", param_type="number", default=4, description="最大通孔链长度"),
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        violations = []
        via_count = getattr(net_data, 'via_count', 0)
        max_chain = self.get_parameter('max_via_chain_length', 4)

        if via_count > max_chain:
            violations.append({
                'rule_id': self.rule_id,
                'rule_name': self.name,
                'net_name': net_name,
                'severity': self.severity,
                'type': 'QTY',
                'message': f"Excessive via chain: {via_count} vias (max {max_chain})",
                'suggestion': "避免长通孔链，考虑使用更高层金属跳过中间层",
                'reference': "Via Chain Guidelines - Best Practices"
            })
        return violations


@register_rule("qty")
class ViaCoverageRule(BaseRule):
    """通孔覆盖率检查"""

    RULE_ID = "QTY002"
    NAME = "Insufficient Via Coverage"
    DESCRIPTION = "检查大面积金属的通孔覆盖率"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["VDD.*", "VSS.*"]

    PARAMETERS = [
        RuleParameter(name="min_coverage", param_type="number", default=0.02, description="最小覆盖率"),
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        violations = []
        via_count = getattr(net_data, 'via_count', 0)
        total_area = getattr(net_data, 'total_area', 0)

        if total_area > 10 and via_count < 2:
            self.get_parameter('min_coverage', 0.02)
            violations.append({
                'rule_id': self.rule_id,
                'rule_name': self.name,
                'net_name': net_name,
                'severity': self.severity,
                'type': 'QTY',
                'message': f"Low via coverage for large metal area: {total_area:.1f}μm² with only {via_count} vias",
                'suggestion': "在大面积金属区域增加通孔阵列，提高覆盖率",
                'reference': "Via Density Guidelines"
            })
        return violations


@register_rule("qty")
class ComplexShapeRule(BaseRule):
    """复杂多边形检查"""

    RULE_ID = "QTY003"
    NAME = "Complex Polygon Shape"
    DESCRIPTION = "检查过于复杂的多边形（可能增加光刻风险）"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.INFO
    TARGET_NETS = [".*"]

    PARAMETERS = [
        RuleParameter(name="max_vertices", param_type="number", default=20, description="最大顶点数"),
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        violations = []
        max_verts = self.get_parameter('max_vertices', 20)

        for poly in polygons:
            if len(poly.points) > max_verts:
                violations.append({
                    'rule_id': self.rule_id,
                    'rule_name': self.name,
                    'net_name': net_name,
                    'severity': self.severity,
                    'type': 'QTY',
                    'message': f"Complex polygon with {len(poly.points)} vertices (max {max_verts})",
                    'location': poly.center,
                    'polygons': [poly],
                    'suggestion': "简化走线形状，减少不必要的转角和jog",
                    'reference': "Layout Quality Guidelines"
                })
        return violations


@register_rule("qty")
class Corner90Rule(BaseRule):
    """90度转角检查"""

    RULE_ID = "QTY005"
    NAME = "90-Degree Corner"
    DESCRIPTION = "检查90度转角（电流集中点）"
    CONSTRAINT_TYPE = ConstraintType.INFO
    SEVERITY = Severity.INFO
    TARGET_NETS = ["VDD.*", "VSS.*", ".*PWR.*"]

    PARAMETERS = [
        RuleParameter(name="alert_on_corners", param_type="boolean", default=True, description="是否警告90度转角"),
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        violations = []
        if not self.get_parameter('alert_on_corners', True):
            return violations

        for poly in polygons:
            pts = poly.points
            for i in range(len(pts)):
                p1 = pts[i]
                p2 = pts[(i + 1) % len(pts)]
                p3 = pts[(i + 2) % len(pts)]

                dx1 = p1.x - p2.x
                dy1 = p1.y - p2.y
                dx2 = p3.x - p2.x
                dy2 = p3.y - p2.y

                dot = dx1 * dx2 + dy1 * dy2
                len1 = (dx1 * dx1 + dy1 * dy1) ** 0.5
                len2 = (dx2 * dx2 + dy2 * dy2) ** 0.5

                if len1 > 0 and len2 > 0:
                    cos_angle = dot / (len1 * len2)
                    cos_angle = max(-1.0, min(1.0, cos_angle))
                    angle = abs(math.degrees(math.acos(cos_angle)))

                    if abs(angle - 90) < 5:
                        violations.append({
                            'rule_id': self.rule_id,
                            'rule_name': self.name,
                            'net_name': net_name,
                            'severity': self.severity,
                            'type': 'QTY',
                            'message': f"90-degree corner detected on {poly.layer}",
                            'location': p2,
                            'polygons': [poly],
                            'suggestion': "关键走线建议使用圆角或45度转角",
                            'reference': "Current Density Optimization"
                        })
        return violations


@register_rule("qty")
class MultiLayerRouteRule(BaseRule):
    """多层走线检查"""

    RULE_ID = "QTY006"
    NAME = "Multi-Layer Routing"
    DESCRIPTION = "检查跨越多层的复杂走线"
    CONSTRAINT_TYPE = ConstraintType.INFO
    SEVERITY = Severity.INFO
    TARGET_NETS = [".*"]

    PARAMETERS = [
        RuleParameter(name="max_layers", param_type="number", default=3, description="最大层数"),
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        violations = []
        layers = set()
        for poly in polygons:
            if hasattr(poly, 'layer'):
                layers.add(poly.layer)

        max_layers = self.get_parameter('max_layers', 3)
        if len(layers) > max_layers:
            violations.append({
                'rule_id': self.rule_id,
                'rule_name': self.name,
                'net_name': net_name,
                'severity': self.severity,
                'type': 'QTY',
                'message': f"Multi-layer routing: {len(layers)} layers ({', '.join(sorted(layers))})",
                'suggestion': "简化层转换，减少通孔数量",
                'reference': "Routing Efficiency Guidelines"
            })
        return violations


__all__ = ['ExcessiveViaChainRule', 'ViaCoverageRule', 'ComplexShapeRule', 'Corner90Rule', 'MultiLayerRouteRule']
