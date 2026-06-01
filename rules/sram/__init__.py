#!/usr/bin/env python3
"""
SRAM Rules - SRAM特定规则
包含位线匹配、字线匹配、控制信号匹配等
"""

from typing import List, Dict
from rules.base_rule import BaseRule, ConstraintType, Severity, RuleParameter
from rules.registry import register_rule


@register_rule("sram")
class BitlineMatchingRule(BaseRule):
    """位线对匹配检查"""
    
    RULE_ID = "SRAM001"
    NAME = "Bitline Matching Check"
    DESCRIPTION = "检查位线对(BL/BLB)的匹配度"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["BL.*", "BLB.*"]
    
    PARAMETERS = [
        RuleParameter(
            name="max_length_diff",
            param_type="number",
            default=5,
            unit="μm",
            description="最大长度差异"
        ),
        RuleParameter(
            name="max_rc_diff",
            param_type="number",
            default=0.05,
            min_value=0,
            max_value=1.0,
            description="最大RC差异比例"
        )
    ]
    
    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []
        
        # 这个规则需要成对检查，在引擎层面处理更合适
        # 这里提供基础的单个net检查
        
        length = getattr(net_data, 'total_length', 0)
        
        # 如果是BL，检查对应的BLB
        if 'BL' in net_name.upper() and 'BLB' not in net_name.upper():
            # 需要在引擎中配对检查
            pass
        
        return violations


@register_rule("sram")
class WordlineMatchingRule(BaseRule):
    """字线匹配检查"""
    
    RULE_ID = "SRAM002"
    NAME = "Wordline Matching Check"
    DESCRIPTION = "检查相邻字线的匹配度"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["WL.*"]
    
    PARAMETERS = [
        RuleParameter(
            name="max_length_diff",
            param_type="number",
            default=10,
            unit="μm",
            description="最大长度差异"
        ),
        RuleParameter(
            name="max_resistance_diff",
            param_type="number",
            default=0.10,
            min_value=0,
            max_value=1.0,
            description="最大电阻差异比例"
        )
    ]
    
    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        # 字线匹配需要在引擎中成对分析
        return []


@register_rule("sram")
class ControlSignalMatchingRule(BaseRule):
    """控制信号匹配检查"""
    
    RULE_ID = "SRAM003"
    NAME = "Control Signal Matching"
    DESCRIPTION = "检查控制信号（如PC,SE,WE等）的匹配"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.INFO
    TARGET_NETS = ["PC.*", "SE.*", "WE.*", "RWL.*", "WWL.*"]
    
    PARAMETERS = [
        RuleParameter(
            name="max_skew",
            param_type="number",
            default=50,
            unit="ps",
            description="最大skew"
        )
    ]
    
    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        return []


@register_rule("sram")
class NarrowLongWireRule(BaseRule):
    """长而窄的走线检查"""
    
    RULE_ID = "SRAM004"
    NAME = "Narrow Long Wire"
    DESCRIPTION = "检查长而窄的走线（EM和电阻风险）"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = [".*"]
    
    PARAMETERS = [
        RuleParameter(
            name="length_threshold",
            param_type="number",
            default=100,
            unit="μm",
            description="长度阈值"
        ),
        RuleParameter(
            name="width_threshold",
            param_type="number",
            default=0.05,
            unit="μm",
            description="宽度阈值"
        ),
        RuleParameter(
            name="aspect_ratio_threshold",
            param_type="number",
            default=100,
            description="长宽比阈值"
        )
    ]
    
    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []
        
        segments = getattr(net_data, 'wire_segments', [])
        
        length_thresh = self.get_parameter('length_threshold', 100)
        width_thresh = self.get_parameter('width_threshold', 0.05)
        ar_thresh = self.get_parameter('aspect_ratio_threshold', 100)
        
        for segment in segments:
            if (segment.length > length_thresh and 
                segment.width < width_thresh):
                
                ar = segment.length / segment.width if segment.width > 0 else 0
                
                if ar > ar_thresh:
                    violations.append({
                        'rule_id': self.rule_id,
                        'rule_name': self.name,
                        'net_name': net_name,
                        'severity': self.severity,
                        'type': 'SRAM',
                        'message': f"Narrow long wire: {segment.length:.1f}μm x {segment.width:.3f}μm (AR={ar:.0f})",
                        'location': segment.start,
                        'wire_segments': [segment],
                        'suggestion': "长走线应使用更宽的金属或更高层",
                        'reference': "Routing Quality Guidelines"
                    })
        
        return violations


__all__ = ['BitlineMatchingRule', 'WordlineMatchingRule', 'ControlSignalMatchingRule', 'NarrowLongWireRule']
