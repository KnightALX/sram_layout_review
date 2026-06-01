#!/usr/bin/env python3
"""
EM Rules - 电迁移规则
包含电迁移风险、电源网络宽度、通孔电流容量等
"""

from typing import List, Dict
from rules.base_rule import BaseRule, ConstraintType, Severity, RuleParameter
from rules.registry import register_rule


@register_rule("em")
class ElectromigrationRule(BaseRule):
    """电迁移风险检查"""
    
    RULE_ID = "EM001"
    NAME = "Electromigration Risk"
    DESCRIPTION = "检查电迁移风险（基于电流密度估算）"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["VDD.*", "VSS.*", ".*PWR.*"]
    
    PARAMETERS = [
        RuleParameter(
            name="em_safety_factor",
            param_type="number",
            default=0.8,
            min_value=0.5,
            max_value=1.0,
            description="EM安全系数"
        ),
        RuleParameter(
            name="estimated_current",
            param_type="number",
            default=None,
            unit="mA",
            description="估算电流（未指定时自动估算）"
        )
    ]
    
    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []
        
        segments = getattr(net_data, 'wire_segments', [])
        if not segments:
            return violations
        
        # 估算电流
        current = self.get_parameter('estimated_current')
        if current is None:
            # 自动估算
            if 'VDD' in net_name.upper() or 'VSS' in net_name.upper():
                current = 50.0  # 电源网络
            elif 'PWR' in net_name.upper():
                current = 30.0
            else:
                current = 10.0
        
        for segment in segments:
            layer_info = getattr(net_data, 'tech', {}).get(segment.layer, {})
            if not layer_info:
                continue
            
            j_max = layer_info.get('current_density', 10.0)  # mA/μm
            width = segment.width
            
            if width > 0:
                current_density = current / width
                safety_factor = self.get_parameter('em_safety_factor', 0.8)
                
                if current_density > j_max * safety_factor:
                    violations.append({
                        'rule_id': self.rule_id,
                        'rule_name': self.name,
                        'net_name': net_name,
                        'severity': self.severity,
                        'type': 'EM',
                        'message': f"EM risk on {segment.layer}: J={current_density:.2f}mA/μm (max {j_max * safety_factor:.2f})",
                        'location': segment.start,
                        'wire_segments': [segment],
                        'suggestion': "增加走线宽度、使用多条并联走线或更高层金属",
                        'reference': "Electromigration Design Rules - Section 5.3"
                    })
        
        return violations


@register_rule("em")
class PowerWidthRule(BaseRule):
    """电源网络宽度检查"""
    
    RULE_ID = "EM002"
    NAME = "Power Net Width Check"
    DESCRIPTION = "检查电源网络走线宽度是否足够"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["VDD.*", "VSS.*", ".*PWR.*"]
    
    PARAMETERS = [
        RuleParameter(
            name="min_power_width",
            param_type="number",
            default=0.5,
            unit="μm",
            description="电源网络最小宽度"
        ),
        RuleParameter(
            name="min_length",
            param_type="number",
            default=10,
            unit="μm",
            description="最小检查长度"
        )
    ]
    
    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []
        
        segments = getattr(net_data, 'wire_segments', [])
        
        min_width = self.get_parameter('min_power_width', 0.5)
        min_length = self.get_parameter('min_length', 10)
        
        for segment in segments:
            if segment.width < min_width and segment.length > min_length:
                violations.append({
                    'rule_id': self.rule_id,
                    'rule_name': self.name,
                    'net_name': net_name,
                    'severity': self.severity,
                    'type': 'EM',
                    'message': f"Power net narrow segment: {segment.width:.3f}μm on {segment.layer}",
                    'location': segment.start,
                    'wire_segments': [segment],
                    'suggestion': "电源网络建议使用更宽的金属走线或strap",
                    'reference': "Power Distribution Network Guidelines"
                })
        
        return violations


@register_rule("em")
class ViaCurrentRule(BaseRule):
    """通孔电流容量检查"""
    
    RULE_ID = "EM003"
    NAME = "Via Current Capacity"
    DESCRIPTION = "检查通孔电流承载能力是否足够"
    CONSTRAINT_TYPE = ConstraintType.SOFT
    SEVERITY = Severity.WARNING
    TARGET_NETS = ["VDD.*", "VSS.*", ".*PWR.*"]
    
    PARAMETERS = [
        RuleParameter(
            name="min_via_array_size",
            param_type="number",
            default=2,
            description="最小通孔阵列大小（如2表示2x2）"
        )
    ]
    
    def check(self, net_name: str, net_data, polygons: List) -> List[Dict]:
        """执行检查"""
        violations = []
        
        via_count = getattr(net_data, 'via_count', 0)
        min_size = self.get_parameter('min_via_array_size', 2)
        
        # 简化：检查通孔数量
        if via_count > 0 and via_count < min_size * min_size:
            violations.append({
                'rule_id': self.rule_id,
                'rule_name': self.name,
                'net_name': net_name,
                'severity': self.severity,
                'type': 'EM',
                'message': f"Via count ({via_count}) below minimum ({min_size*min_size}) for power net",
                'suggestion': "在大电流路径使用更大的通孔阵列（如3x3或4x4）",
                'reference': "Via Current Density Rules"
            })
        
        return violations


__all__ = ['ElectromigrationRule', 'PowerWidthRule', 'ViaCurrentRule']
