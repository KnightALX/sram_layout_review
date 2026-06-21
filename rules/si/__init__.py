#!/usr/bin/env python3
"""
SI Rules - 信号完整性规则
包含长走线、高电阻、高电容等检查
"""

from typing import Dict, List

from rules.base_rule import BaseRule, ConstraintType, RuleParameter, Severity
from rules.registry import register_rule


@register_rule("si")
class LongWireRule(BaseRule):
    """长走线RC分析"""

    RULE_ID = "SI001"
    NAME = "Long Wire RC Analysis"
    DESCRIPTION = "检查过长走线的RC延迟和串扰风险"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["BL.*", "BLB.*", "WL.*", ".*DATA.*", ".*CLK.*"]

    PARAMETERS = [
        RuleParameter(
            name="max_length_met12",
            param_type="number",
            default=100,
            unit="μm",
            description="Met1/2最大长度"
        ),
        RuleParameter(
            name="max_length_met34",
            param_type="number",
            default=200,
            unit="μm",
            description="Met3/4最大长度"
        ),
        RuleParameter(
            name="max_length_met56",
            param_type="number",
            default=300,
            unit="μm",
            description="Met5/6最大长度"
        )
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []

        # 获取走线段（从net_data）
        segments = getattr(net_data, 'wire_segments', [])

        if not segments:
            return violations

        for segment in segments:
            layer = segment.layer
            length = segment.length

            # 确定该层的最大长度
            if layer in ['m0', 'm1', 'm2']:
                max_len = self.get_parameter('max_length_met12', 100)
            elif layer in ['m3', 'm4']:
                max_len = self.get_parameter('max_length_met34', 200)
            else:
                max_len = self.get_parameter('max_length_met56', 300)

            if length > max_len:
                violations.append({
                    'rule_id': self.rule_id,
                    'rule_name': self.name,
                    'net_name': net_name,
                    'severity': self.severity,
                    'type': 'SI',
                    'message': f"Long wire on {layer}: {length:.1f}μm (max {max_len}μm)",
                    'location': segment.start,
                    'wire_segments': [segment],
                    'suggestion': "考虑使用buffer插入、wider metal或更高层金属",
                    'reference': "Signal Integrity Guidelines - Section 3.1"
                })

        return violations


@register_rule("si")
class HighResistanceRule(BaseRule):
    """高电阻路径检查"""

    RULE_ID = "SI002"
    NAME = "High Resistance Path"
    DESCRIPTION = "检查高电阻路径（可能导致IR drop和延迟）"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["VDD.*", "VSS.*", ".*PWR.*", "BL.*", "WL.*"]

    PARAMETERS = [
        RuleParameter(
            name="max_resistance",
            param_type="number",
            default=100,
            unit="Ω",
            description="最大电阻阈值"
        )
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []

        total_r = getattr(net_data, 'total_resistance', 0)
        max_r = self.get_parameter('max_resistance', 100)

        if total_r > max_r:
            violations.append({
                'rule_id': self.rule_id,
                'rule_name': self.name,
                'net_name': net_name,
                'severity': self.severity,
                'type': 'SI',
                'message': f"High resistance: {total_r:.1f}Ω (max {max_r}Ω)",
                'suggestion': "增加走线宽度、使用并联路径或更高层金属",
                'reference': "Power Delivery Network Guidelines"
            })

        return violations


@register_rule("si")
class HighCapacitanceRule(BaseRule):
    """高电容网络检查"""

    RULE_ID = "SI003"
    NAME = "High Capacitance Net"
    DESCRIPTION = "检查高电容网络（可能增加延迟和功耗）"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = [".*CLK.*", ".*DATA.*", "BL.*", "WL.*"]

    PARAMETERS = [
        RuleParameter(
            name="max_capacitance",
            param_type="number",
            default=500,
            unit="fF",
            description="最大电容阈值"
        )
    ]

    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []

        total_c = getattr(net_data, 'total_capacitance', 0)
        max_c = self.get_parameter('max_capacitance', 500)

        if total_c > max_c:
            violations.append({
                'rule_id': self.rule_id,
                'rule_name': self.name,
                'net_name': net_name,
                'severity': self.severity,
                'type': 'SI',
                'message': f"High capacitance: {total_c:.1f}fF (max {max_c}fF)",
                'suggestion': "缩短走线长度、减少重叠面积、使用低电容层",
                'reference': "Capacitance Optimization Guide"
            })

        return violations


__all__ = ['LongWireRule', 'HighResistanceRule', 'HighCapacitanceRule']
