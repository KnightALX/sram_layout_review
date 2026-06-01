#!/usr/bin/env python3
"""
DRC Rules - 设计规则检查
包含最小宽度、最小间距、通孔缺失等检查
"""

from typing import List, Dict
from rules.base_rule import BaseRule, ConstraintType, Severity, RuleParameter
from rules.registry import register_rule


@register_rule("drc")
class MinWidthRule(BaseRule):
    """最小宽度检查"""

    RULE_ID = "DRC001"
    NAME = "Minimum Width Violation"
    DESCRIPTION = "检查走线宽度是否满足工艺最小宽度要求"
    CONSTRAINT_TYPE = ConstraintType.HARD
    SEVERITY = Severity.CRITICAL
    TARGET_NETS = [".*"]

    PARAMETERS = [
        RuleParameter(
            name="safety_factor",
            param_type="number",
            default=0.95,
            min_value=0.5,
            max_value=1.0,
            description="安全系数"
        )
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []

        tech = getattr(net_data, 'tech', {})

        for polygon in polygons:
            layer = polygon.layer
            layer_info = tech.get(layer, {})
            min_width = layer_info.get('min_width', 0.032)

            actual_width = min(polygon.width, polygon.height)
            safety_factor = self.get_parameter('safety_factor', 0.95)

            if actual_width < min_width * safety_factor:
                violations.append({
                    'rule_id': self.rule_id,
                    'rule_name': self.name,
                    'net_name': net_name,
                    'severity': self.severity,
                    'type': 'DRC',
                    'message': f"Width violation on {layer}: {actual_width:.4f}μm < {min_width * safety_factor:.4f}μm",
                    'location': polygon.center,
                    'polygons': [polygon],
                    'suggestion': "增加走线宽度至工艺最小值以上，或使用更高层金属",
                    'reference': "Design Rule Manual (DRM) - Metal Width Rules"
                })

        return violations


@register_rule("drc")
class MinSpaceRule(BaseRule):
    """最小间距检查"""

    RULE_ID = "DRC002"
    NAME = "Minimum Space Violation"
    DESCRIPTION = "检查走线间距是否满足工艺最小间距要求"
    CONSTRAINT_TYPE = ConstraintType.HARD
    SEVERITY = Severity.CRITICAL
    TARGET_NETS = [".*"]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查

        注意：此检查需要成对比较polygons，当前为简化实现。
        完整实现需要使用polygon intersection算法。
        """
        violations = []

        # 简化实现：对于矩形polygon，检查bbox间距
        for i, poly1 in enumerate(polygons):
            if not hasattr(poly1, 'bbox'):
                continue

            bbox1 = poly1.bbox

            for poly2 in polygons[i+1:]:
                if not hasattr(poly2, 'bbox'):
                    continue

                bbox2 = poly2.bbox

                # 检查是否相邻（简化：仅检查bbox）
                # 如果有重叠则违反间距规则
                x_overlap = max(0, min(bbox1[2], bbox2[2]) - max(bbox1[0], bbox2[0]))
                y_overlap = max(0, min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1]))

                if x_overlap > 0 and y_overlap > 0:
                    violations.append({
                        'rule_id': self.rule_id,
                        'rule_name': self.name,
                        'net_name': net_name,
                        'severity': self.severity,
                        'type': 'DRC',
                        'message': f"Space violation between layers on same net",
                        'location': poly1.center,
                        'polygons': [poly1, poly2],
                        'suggestion': "增加走线间距至工艺最小值以上",
                        'reference': "Design Rule Manual (DRM) - Metal Space Rules"
                    })

        return violations


@register_rule("drc")
class MissingViaRule(BaseRule):
    """通孔缺失检测"""

    RULE_ID = "DRC003"
    NAME = "Missing Via Detection"
    DESCRIPTION = "检查相邻金属层重叠区域是否存在通孔连接"
    CONSTRAINT_TYPE = ConstraintType.HARD
    SEVERITY = Severity.CRITICAL
    TARGET_NETS = [".*"]

    PARAMETERS = [
        RuleParameter(
            name="overlap_threshold",
            param_type="number",
            default=0.1,
            unit="μm²",
            description="最小重叠面积阈值"
        )
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查

        检查相邻层之间的重叠区域是否有via连接。
        这是简化实现，完整实现需要：
        1. 识别哪些层是相邻的（met1-met2, met2-met3等）
        2. 检查重叠区域
        3. 验证via存在
        """
        violations = []

        via_count = getattr(net_data, 'via_count', 0)
        if via_count == 0:
            # 没有via，如果有多层polygon，可能存在缺失via问题
            layers = set()
            for poly in polygons:
                if hasattr(poly, 'layer'):
                    layers.add(poly.layer)

            if len(layers) > 1:
                violations.append({
                    'rule_id': self.rule_id,
                    'rule_name': self.name,
                    'net_name': net_name,
                    'severity': self.severity,
                    'type': 'DRC',
                    'message': f"Multiple layers ({len(layers)}) with no via connections detected",
                    'suggestion': "在金属层重叠区域添加通孔阵列",
                    'reference': "Via Connection Rules - DRM Section 4.2"
                })

        return violations


__all__ = ['MinWidthRule', 'MinSpaceRule', 'MissingViaRule']
