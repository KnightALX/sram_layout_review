#!/usr/bin/env python3
"""
Layout Review Configuration System
版图Review配置管理系统

支持：
1. 自定义检查项配置（支持正则匹配目标net）
2. 导入/导出配置
3. 软约束/硬约束分离
4. 工艺参数定制
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Set, Any
from pathlib import Path

from rules.base_rule import ConstraintType, Severity


@dataclass
class CheckRule:
    """检查规则"""
    rule_id: str                    # 规则ID
    name: str                       # 规则名称
    description: str                # 规则描述
    constraint_type: ConstraintType # 约束类型
    severity: Severity              # 严重程度
    target_nets: List[str]          # 目标net（支持正则）
    enabled: bool = True            # 是否启用
    parameters: Dict = field(default_factory=dict)  # 规则参数
    suggestion: str = ""            # 改进建议
    reference: str = ""             # 参考文档/规范
    
    def matches_net(self, net_name: str) -> bool:
        """检查net名称是否匹配规则"""
        if not self.target_nets:
            return True  # 空列表表示匹配所有
        for pattern in self.target_nets:
            try:
                if re.search(pattern, net_name, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False


@dataclass
class TechConfig:
    """工艺配置"""
    name: str
    node: str                       # 工艺节点 (e.g., "7nm", "5nm")
    voltage: float                  # 工作电压 (V)
    temperature: float              # 工作温度 (°C)
    layers: Dict = field(default_factory=dict)      # 层定义
    design_rules: Dict = field(default_factory=dict) # 设计规则
    
    @classmethod
    def get_default_7nm(cls) -> 'TechConfig':
        """获取默认7nm配置"""
        return cls(
            name="Generic_7nm_SRAM",
            node="7nm",
            voltage=0.75,
            temperature=85.0,
            layers={
                # Metal layers - 7nm FinFET typical values
                'met1': {
                    'type': 'metal',
                    'direction': 'vertical',
                    'min_width': 0.032,           # μm
                    'min_space': 0.032,           # μm
                    'pitch': 0.064,               # μm
                    'thickness': 0.060,           # μm
                    'resistance_per_sq': 0.15,    # Ω/□
                    'capacitance_per_um': 0.20,   # fF/μm (total C)
                    'current_density': 10.0,      # mA/μm (EM limit)
                    'color': '#1f77b4',
                    'order': 10
                },
                'met2': {
                    'type': 'metal',
                    'direction': 'horizontal',
                    'min_width': 0.032,
                    'min_space': 0.032,
                    'pitch': 0.064,
                    'thickness': 0.060,
                    'resistance_per_sq': 0.12,
                    'capacitance_per_um': 0.16,
                    'current_density': 12.0,
                    'color': '#ff7f0e',
                    'order': 20
                },
                'met3': {
                    'type': 'metal',
                    'direction': 'vertical',
                    'min_width': 0.032,
                    'min_space': 0.032,
                    'pitch': 0.064,
                    'thickness': 0.060,
                    'resistance_per_sq': 0.10,
                    'capacitance_per_um': 0.14,
                    'current_density': 14.0,
                    'color': '#2ca02c',
                    'order': 30
                },
                'met4': {
                    'type': 'metal',
                    'direction': 'horizontal',
                    'min_width': 0.042,
                    'min_space': 0.042,
                    'pitch': 0.084,
                    'thickness': 0.080,
                    'resistance_per_sq': 0.08,
                    'capacitance_per_um': 0.12,
                    'current_density': 18.0,
                    'color': '#d62728',
                    'order': 40
                },
                'met5': {
                    'type': 'metal',
                    'direction': 'vertical',
                    'min_width': 0.056,
                    'min_space': 0.056,
                    'pitch': 0.112,
                    'thickness': 0.110,
                    'resistance_per_sq': 0.06,
                    'capacitance_per_um': 0.10,
                    'current_density': 25.0,
                    'color': '#9467bd',
                    'order': 50
                },
                'met6': {
                    'type': 'metal',
                    'direction': 'horizontal',
                    'min_width': 0.074,
                    'min_space': 0.074,
                    'pitch': 0.148,
                    'thickness': 0.140,
                    'resistance_per_sq': 0.04,
                    'capacitance_per_um': 0.08,
                    'current_density': 35.0,
                    'color': '#8c564b',
                    'order': 60
                },
                'met7': {
                    'type': 'metal',
                    'direction': 'vertical',
                    'min_width': 0.100,
                    'min_space': 0.100,
                    'pitch': 0.200,
                    'thickness': 0.200,
                    'resistance_per_sq': 0.025,
                    'capacitance_per_um': 0.06,
                    'current_density': 50.0,
                    'color': '#e377c2',
                    'order': 70
                },
                # Via layers
                'via0': {
                    'type': 'via',
                    'min_size': 0.024,
                    'min_space': 0.024,
                    'resistance': 1.0,            # Ω per via
                    'current_capacity': 50.0,     # mA per via
                    'color': '#7f7f7f',
                    'order': 15
                },
                'via1': {
                    'type': 'via',
                    'min_size': 0.028,
                    'min_space': 0.028,
                    'resistance': 0.8,
                    'current_capacity': 60.0,
                    'color': '#bcbd22',
                    'order': 25
                },
                'via2': {
                    'type': 'via',
                    'min_size': 0.028,
                    'min_space': 0.028,
                    'resistance': 0.6,
                    'current_capacity': 70.0,
                    'color': '#17becf',
                    'order': 35
                },
                'via3': {
                    'type': 'via',
                    'min_size': 0.036,
                    'min_space': 0.036,
                    'resistance': 0.5,
                    'current_capacity': 80.0,
                    'color': '#393b79',
                    'order': 45
                },
                'via4': {
                    'type': 'via',
                    'min_size': 0.048,
                    'min_space': 0.048,
                    'resistance': 0.4,
                    'current_capacity': 100.0,
                    'color': '#637939',
                    'order': 55
                },
                'via5': {
                    'type': 'via',
                    'min_size': 0.064,
                    'min_space': 0.064,
                    'resistance': 0.3,
                    'current_capacity': 120.0,
                    'color': '#8c6d31',
                    'order': 65
                },
                # Poly/Active
                'poly': {
                    'type': 'poly',
                    'direction': 'horizontal',
                    'min_width': 0.020,
                    'min_space': 0.030,
                    'resistance_per_sq': 10.0,
                    'capacitance_per_um': 0.50,
                    'color': '#843c39',
                    'order': 5
                },
                'active': {
                    'type': 'active',
                    'min_width': 0.020,
                    'min_space': 0.020,
                    'resistance_per_sq': 5.0,
                    'color': '#7b4173',
                    'order': 3
                }
            },
            design_rules={
                'max_metal_length': 500,          # μm - 单段金属最大长度
                'max_via_chain': 4,                # 最大连续通孔链长度
                'min_via_coverage': 0.02,          # 最小通孔覆盖率 (2%)
                'max_aspect_ratio': 200,           # 最大长宽比
                'matching_tolerance': 0.05,        # 匹配容差 (5%)
                'max_rc_variation': 0.10,          # RC变异容差 (10%)
                'em_safety_factor': 0.8,           # EM安全系数
            }
        )


@dataclass
class LayoutReviewConfig:
    """版图Review完整配置"""
    name: str = "SRAM_Layout_Review"
    description: str = "SRAM版图Review检查配置"
    version: str = "1.0.0"
    tech_config: TechConfig = field(default_factory=TechConfig.get_default_7nm)
    check_rules: List[CheckRule] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化默认规则"""
        if not self.check_rules:
            self.check_rules = self._get_default_rules()
    
    def _get_default_rules(self) -> List[CheckRule]:
        """获取默认检查规则 - 基于业界最佳实践"""
        return [
            # ============================================
            # 硬约束 - 必须遵守
            # ============================================
            CheckRule(
                rule_id="DRC001",
                name="Minimum Width Violation",
                description="检查走线宽度是否满足工艺最小宽度要求",
                constraint_type=ConstraintType.HARD,
                severity=Severity.CRITICAL,
                target_nets=[".*"],  # 所有net
                parameters={"check_all_layers": True},
                suggestion="增加走线宽度至工艺最小值以上，或使用更高层金属",
                reference="Design Rule Manual (DRM) - Metal Width Rules"
            ),
            CheckRule(
                rule_id="DRC002",
                name="Minimum Space Violation",
                description="检查走线间距是否满足工艺最小间距要求",
                constraint_type=ConstraintType.HARD,
                severity=Severity.CRITICAL,
                target_nets=[".*"],
                parameters={"check_all_layers": True},
                suggestion="增加走线间距至工艺最小值以上",
                reference="Design Rule Manual (DRM) - Metal Space Rules"
            ),
            CheckRule(
                rule_id="DRC003",
                name="Missing Via Detection",
                description="检查相邻金属层重叠区域是否存在通孔连接",
                constraint_type=ConstraintType.HARD,
                severity=Severity.CRITICAL,
                target_nets=[".*"],
                parameters={"overlap_threshold": 0.1},  # μm²
                suggestion="在金属层重叠区域添加通孔阵列",
                reference="Via Connection Rules - DRM Section 4.2"
            ),
            
            # ============================================
            # 软约束 - 信号完整性相关
            # ============================================
            CheckRule(
                rule_id="SI001",
                name="Long Wire RC Analysis",
                description="检查过长走线的RC延迟和串扰风险",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["BL.*", "BLB.*", "WL.*", ".*DATA.*", ".*CLK.*"],
                parameters={
                    "max_length_met12": 100,    # μm
                    "max_length_met34": 200,
                    "max_length_met56": 300,
                },
                suggestion="考虑使用buffer插入、wider metal或更高层金属",
                reference="Signal Integrity Guidelines - Section 3.1"
            ),
            CheckRule(
                rule_id="SI002",
                name="High Resistance Path",
                description="检查高电阻路径（可能导致IR drop和延迟）",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["VDD.*", "VSS.*", ".*PWR.*", "BL.*", "WL.*"],
                parameters={"max_resistance": 100},  # Ω
                suggestion="增加走线宽度、使用并联路径或更高层金属",
                reference="Power Delivery Network Guidelines"
            ),
            CheckRule(
                rule_id="SI003",
                name="High Capacitance Net",
                description="检查高电容网络（可能增加延迟和功耗）",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=[".*CLK.*", ".*DATA.*", "BL.*", "WL.*"],
                parameters={"max_capacitance": 500},  # fF
                suggestion="缩短走线长度、减少重叠面积、使用低电容层",
                reference="Capacitance Optimization Guide"
            ),
            
            # ============================================
            # 软约束 - EM/IR相关
            # ============================================
            CheckRule(
                rule_id="EM001",
                name="Electromigration Risk",
                description="检查电迁移风险（基于电流密度估算）",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["VDD.*", "VSS.*", ".*PWR.*"],
                parameters={
                    "em_safety_factor": 0.8,
                    "min_width_alert": 0.5  # μm for power nets
                },
                suggestion="增加走线宽度、使用多条并联走线或更高层金属",
                reference="Electromigration Design Rules - Section 5.3"
            ),
            CheckRule(
                rule_id="EM002",
                name="Power Net Width Check",
                description="检查电源网络走线宽度是否足够",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["VDD.*", "VSS.*", ".*PWR.*"],
                parameters={"min_power_width": 0.5},  # μm
                suggestion="电源网络建议使用更宽的金属走线或strap",
                reference="Power Distribution Network Guidelines"
            ),
            CheckRule(
                rule_id="EM003",
                name="Via Current Capacity",
                description="检查通孔电流承载能力是否足够",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["VDD.*", "VSS.*", ".*PWR.*"],
                parameters={"min_via_array_size": 2},  # 2x2 minimum
                suggestion="在大电流路径使用更大的通孔阵列（如3x3或4x4）",
                reference="Via Current Density Rules"
            ),
            
            # ============================================
            # 软约束 - SRAM特定
            # ============================================
            CheckRule(
                rule_id="SRAM001",
                name="Bitline Matching Check",
                description="检查位线对(BL/BLB)的匹配度",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["BL.*", "BLB.*"],
                parameters={
                    "max_length_diff": 5,      # μm
                    "max_via_diff": 1,
                    "max_rc_diff": 0.05        # 5%
                },
                suggestion="保持BL/BLB走线长度、层分布和通孔数量对称",
                reference="SRAM Layout Matching Guidelines - Section 2.1"
            ),
            CheckRule(
                rule_id="SRAM002",
                name="Wordline Matching Check",
                description="检查相邻字线的匹配度",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["WL.*"],
                parameters={
                    "max_length_diff": 10,     # μm
                    "max_resistance_diff": 0.10  # 10%
                },
                suggestion="确保相邻字线具有一致的RC特性",
                reference="SRAM Wordline Design Guide"
            ),
            CheckRule(
                rule_id="SRAM003",
                name="Control Signal Matching",
                description="检查控制信号（如PC,SE,WE等）的匹配",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.INFO,
                target_nets=["PC.*", "SE.*", "WE.*", "RWL.*", "WWL.*"],
                parameters={"max_skew": 50},  # ps
                suggestion="控制信号走线应尽量匹配，减少skew",
                reference="SRAM Control Signal Routing Guidelines"
            ),
            
            # ============================================
            # 软约束 - 版图质量
            # ============================================
            CheckRule(
                rule_id="QTY001",
                name="Excessive Via Chain",
                description="检查过长的通孔链（增加电阻）",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=[".*"],
                parameters={"max_via_chain_length": 4},
                suggestion="避免长通孔链，考虑使用更高层金属跳过中间层",
                reference="Via Chain Guidelines - Best Practices"
            ),
            CheckRule(
                rule_id="QTY002",
                name="Insufficient Via Coverage",
                description="检查大面积金属的通孔覆盖率",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=["VDD.*", "VSS.*"],
                parameters={"min_coverage": 0.02},  # 2%
                suggestion="在大面积金属区域增加通孔阵列，提高覆盖率",
                reference="Via Density Guidelines"
            ),
            CheckRule(
                rule_id="QTY003",
                name="Complex Polygon Shape",
                description="检查过于复杂的多边形（可能增加光刻风险）",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.INFO,
                target_nets=[".*"],
                parameters={"max_vertices": 20},
                suggestion="简化走线形状，减少不必要的转角和jog",
                reference="Layout Quality Guidelines"
            ),
            CheckRule(
                rule_id="QTY004",
                name="Narrow Long Wire",
                description="检查长而窄的走线（EM和电阻风险）",
                constraint_type=ConstraintType.SOFT,
                severity=Severity.WARNING,
                target_nets=[".*"],
                parameters={
                    "length_threshold": 100,   # μm
                    "width_threshold": 0.05,   # μm
                    "aspect_ratio_threshold": 100
                },
                suggestion="长走线应使用更宽的金属或更高层",
                reference="Routing Quality Guidelines"
            ),
            CheckRule(
                rule_id="QTY005",
                name="90-Degree Corner",
                description="检查90度转角（电流集中点）",
                constraint_type=ConstraintType.INFO,
                severity=Severity.INFO,
                target_nets=["VDD.*", "VSS.*", ".*PWR.*"],
                parameters={"alert_on_corners": True},
                suggestion="关键走线建议使用圆角或45度转角",
                reference="Current Density Optimization"
            ),
            CheckRule(
                rule_id="QTY006",
                name="Multi-Layer Routing",
                description="检查跨越多层的复杂走线",
                constraint_type=ConstraintType.INFO,
                severity=Severity.INFO,
                target_nets=[".*"],
                parameters={"max_layers": 3},
                suggestion="简化层转换，减少通孔数量",
                reference="Routing Efficiency Guidelines"
            ),
            
            # ============================================
            # 信息提示
            # ============================================
            CheckRule(
                rule_id="INF001",
                name="Net Statistics",
                description="显示net的基本统计信息",
                constraint_type=ConstraintType.INFO,
                severity=Severity.INFO,
                target_nets=[".*"],
                parameters={"show_all": True},
                suggestion="",
                reference=""
            ),
        ]
    
    def get_enabled_rules(self) -> List[CheckRule]:
        """获取启用的规则"""
        return [r for r in self.check_rules if r.enabled]
    
    def get_rules_for_net(self, net_name: str) -> List[CheckRule]:
        """获取适用于指定net的规则"""
        return [r for r in self.get_enabled_rules() if r.matches_net(net_name)]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tech_config": {
                "name": self.tech_config.name,
                "node": self.tech_config.node,
                "voltage": self.tech_config.voltage,
                "temperature": self.tech_config.temperature,
                "layers": self.tech_config.layers,
                "design_rules": self.tech_config.design_rules
            },
            "check_rules": [
                {
                    "rule_id": r.rule_id,
                    "name": r.name,
                    "description": r.description,
                    "constraint_type": r.constraint_type.value,
                    "severity": r.severity.value,
                    "target_nets": r.target_nets,
                    "enabled": r.enabled,
                    "parameters": r.parameters,
                    "suggestion": r.suggestion,
                    "reference": r.reference
                }
                for r in self.check_rules
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LayoutReviewConfig':
        """从字典创建配置"""
        tech_data = data.get("tech_config", {})
        tech_config = TechConfig(
            name=tech_data.get("name", "Generic"),
            node=tech_data.get("node", "7nm"),
            voltage=tech_data.get("voltage", 0.75),
            temperature=tech_data.get("temperature", 85.0),
            layers=tech_data.get("layers", {}),
            design_rules=tech_data.get("design_rules", {})
        )
        
        check_rules = []
        for rule_data in data.get("check_rules", []):
            check_rules.append(CheckRule(
                rule_id=rule_data["rule_id"],
                name=rule_data["name"],
                description=rule_data["description"],
                constraint_type=ConstraintType(rule_data["constraint_type"]),
                severity=Severity(rule_data["severity"]),
                target_nets=rule_data["target_nets"],
                enabled=rule_data.get("enabled", True),
                parameters=rule_data.get("parameters", {}),
                suggestion=rule_data.get("suggestion", ""),
                reference=rule_data.get("reference", "")
            ))
        
        return cls(
            name=data.get("name", "SRAM_Layout_Review"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            tech_config=tech_config,
            check_rules=check_rules
        )
    
    def save_to_file(self, filepath: str):
        """保存配置到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'LayoutReviewConfig':
        """从文件加载配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    # ============================================
    # 在线编辑支持
    # ============================================
    
    def add_rule(self, rule: 'CheckRule') -> bool:
        """添加新规则
        
        Args:
            rule: 要添加的规则
            
        Returns:
            是否添加成功（rule_id已存在返回False）
        """
        # 检查rule_id是否已存在
        for existing in self.check_rules:
            if existing.rule_id == rule.rule_id:
                return False
        
        self.check_rules.append(rule)
        return True
    
    def update_rule(self, rule_id: str, **kwargs) -> bool:
        """更新规则
        
        Args:
            rule_id: 规则ID
            **kwargs: 要更新的字段
            
        Returns:
            是否更新成功
        """
        for rule in self.check_rules:
            if rule.rule_id == rule_id:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                return True
        return False
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            是否删除成功
        """
        for i, rule in enumerate(self.check_rules):
            if rule.rule_id == rule_id:
                self.check_rules.pop(i)
                return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional['CheckRule']:
        """获取指定规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            规则对象，不存在返回None
        """
        for rule in self.check_rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def toggle_rule(self, rule_id: str) -> Optional[bool]:
        """切换规则启用状态
        
        Args:
            rule_id: 规则ID
            
        Returns:
            新的启用状态，不存在返回None
        """
        rule = self.get_rule(rule_id)
        if rule:
            rule.enabled = not rule.enabled
            return rule.enabled
        return None
    
    def validate_rule(self, rule_data: Dict) -> List[str]:
        """校验规则数据
        
        Args:
            rule_data: 规则数据字典
            
        Returns:
            错误列表，空表示校验通过
        """
        errors = []
        
        # 必填字段
        required = ['rule_id', 'name', 'description', 'constraint_type', 'severity', 'target_nets']
        for field in required:
            if field not in rule_data or not rule_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # rule_id格式检查
        if 'rule_id' in rule_data:
            if not re.match(r'^[A-Z]{2,4}\d{3}$', rule_data['rule_id']):
                errors.append("rule_id must match format: 2-4 uppercase letters + 3 digits (e.g., DRC001)")
        
        # constraint_type有效性
        if 'constraint_type' in rule_data:
            try:
                ConstraintType(rule_data['constraint_type'])
            except ValueError:
                errors.append(f"Invalid constraint_type: {rule_data['constraint_type']}")
        
        # severity有效性
        if 'severity' in rule_data:
            try:
                Severity(rule_data['severity'])
            except ValueError:
                errors.append(f"Invalid severity: {rule_data['severity']}")
        
        # target_nets格式
        if 'target_nets' in rule_data:
            if not isinstance(rule_data['target_nets'], list):
                errors.append("target_nets must be a list")
            else:
                for pattern in rule_data['target_nets']:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        errors.append(f"Invalid regex pattern '{pattern}': {e}")
        
        # parameters格式
        if 'parameters' in rule_data:
            if not isinstance(rule_data['parameters'], dict):
                errors.append("parameters must be a dictionary")
        
        return errors
    
    def duplicate_rule(self, rule_id: str, new_rule_id: str) -> Optional['CheckRule']:
        """复制规则
        
        Args:
            rule_id: 源规则ID
            new_rule_id: 新规则ID
            
        Returns:
            新创建的规则，失败返回None
        """
        source = self.get_rule(rule_id)
        if not source:
            return None
        
        # 检查新ID是否已存在
        if self.get_rule(new_rule_id):
            return None
        
        # 创建副本
        new_rule = CheckRule(
            rule_id=new_rule_id,
            name=source.name + " (Copy)",
            description=source.description,
            constraint_type=source.constraint_type,
            severity=source.severity,
            target_nets=source.target_nets.copy(),
            enabled=False,
            parameters=source.parameters.copy(),
            suggestion=source.suggestion,
            reference=source.reference
        )
        
        self.check_rules.append(new_rule)
        return new_rule
    
    def import_rules(self, rules_data: List[Dict], mode: str = 'merge') -> Dict:
        """批量导入规则
        
        Args:
            rules_data: 规则数据列表
            mode: 'merge' 合并, 'replace' 替换
            
        Returns:
            导入结果统计
        """
        result = {'success': 0, 'skipped': 0, 'errors': []}
        
        if mode == 'replace':
            self.check_rules = []
        
        for rule_data in rules_data:
            errors = self.validate_rule(rule_data)
            if errors:
                result['errors'].append({'rule_id': rule_data.get('rule_id', 'unknown'), 'errors': errors})
                result['skipped'] += 1
                continue
            
            rule_id = rule_data['rule_id']
            if self.get_rule(rule_id):
                result['skipped'] += 1
                continue
            
            try:
                rule = CheckRule(
                    rule_id=rule_data['rule_id'],
                    name=rule_data['name'],
                    description=rule_data['description'],
                    constraint_type=ConstraintType(rule_data['constraint_type']),
                    severity=Severity(rule_data['severity']),
                    target_nets=rule_data['target_nets'],
                    enabled=rule_data.get('enabled', True),
                    parameters=rule_data.get('parameters', {}),
                    suggestion=rule_data.get('suggestion', ''),
                    reference=rule_data.get('reference', '')
                )
                self.check_rules.append(rule)
                result['success'] += 1
            except Exception as e:
                result['errors'].append({'rule_id': rule_id, 'errors': [str(e)]})
                result['skipped'] += 1
        
        return result
    
    def export_rules(self, rule_ids: List[str] = None) -> List[Dict]:
        """导出规则
        
        Args:
            rule_ids: 要导出的规则ID列表，None表示全部
            
        Returns:
            规则数据列表
        """
        rules = self.check_rules
        
        if rule_ids:
            rules = [r for r in rule_ids if r in [x.rule_id for x in self.check_rules]]
        
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "constraint_type": r.constraint_type.value,
                "severity": r.severity.value,
                "target_nets": r.target_nets,
                "enabled": r.enabled,
                "parameters": r.parameters,
                "suggestion": r.suggestion,
                "reference": r.reference
            }
            for r in rules
        ]


# ============================================
# 预设配置
# ============================================

def get_sram_7nm_config() -> LayoutReviewConfig:
    """获取7nm SRAM配置"""
    return LayoutReviewConfig(
        name="SRAM_7nm_Review",
        description="7nm SRAM版图Review检查配置",
        version="1.0.0",
        tech_config=TechConfig.get_default_7nm()
    )


def get_sram_5nm_config() -> LayoutReviewConfig:
    """获取5nm SRAM配置"""
    config = LayoutReviewConfig(
        name="SRAM_5nm_Review",
        description="5nm SRAM版图Review检查配置",
        version="1.0.0"
    )
    # 修改工艺参数为5nm
    config.tech_config.node = "5nm"
    config.tech_config.voltage = 0.65
    
    # 更新5nm层参数
    for layer_name, layer in config.tech_config.layers.items():
        if layer.get('type') == 'metal':
            layer['min_width'] *= 0.7
            layer['min_space'] *= 0.7
            layer['resistance_per_sq'] *= 1.2
            layer['current_density'] *= 0.9
    
    return config


def get_analog_config() -> LayoutReviewConfig:
    """获取模拟电路配置"""
    config = LayoutReviewConfig(
        name="Analog_Layout_Review",
        description="模拟电路版图Review检查配置",
        version="1.0.0"
    )
    
    # 添加模拟电路特定的严格规则
    analog_rules = [
        CheckRule(
            rule_id="ANA001",
            name="Symmetry Check",
            description="检查差分对和镜像电路的对称性",
            constraint_type=ConstraintType.HARD,
            severity=Severity.CRITICAL,
            target_nets=[".*IN.*", ".*OUT.*", ".*P.*", ".*N.*"],
            parameters={"symmetry_tolerance": 0.01},
            suggestion="差分对必须严格对称，包括走线长度和层分布",
            reference="Analog Layout Matching Rules"
        ),
        CheckRule(
            rule_id="ANA002",
            name="Dummy Metal Check",
            description="检查dummy metal的填充密度",
            constraint_type=ConstraintType.SOFT,
            severity=Severity.WARNING,
            target_nets=[".*"],
            parameters={"min_density": 0.3, "max_density": 0.7},
            suggestion="保持均匀的金属密度，避免CMP凹陷",
            reference="CMP Dummy Fill Guidelines"
        ),
    ]
    
    config.check_rules.extend(analog_rules)
    return config


def get_default_config_path() -> str:
    """获取默认配置保存路径（跨平台）"""
    # 使用用户家目录的.config子目录
    config_dir = Path.home() / ".config" / "layout_review"
    config_dir.mkdir(parents=True, exist_ok=True)
    return str(config_dir / "default_sram_7nm.json")


if __name__ == '__main__':
    # 测试配置系统
    print("Layout Review Configuration System")
    print("=" * 50)

    config = get_sram_7nm_config()
    print(f"\nConfig: {config.name}")
    print(f"Tech: {config.tech_config.name} ({config.tech_config.node})")
    print(f"Rules: {len(config.check_rules)} total")

    enabled = config.get_enabled_rules()
    print(f"Enabled: {len(enabled)} rules")

    # 测试net匹配
    test_nets = ["BL_0", "BLB_0", "WL_1", "VDD", "VSS", "CLK"]
    for net in test_nets:
        rules = config.get_rules_for_net(net)
        print(f"\n{net}: {len(rules)} rules apply")

    # 测试在线编辑
    print("\n--- Testing Online Editing ---")

    # 添加新规则
    new_rule = CheckRule(
        rule_id="TEST001",
        name="Test Rule",
        description="A test rule for online editing",
        constraint_type=ConstraintType.SOFT,
        severity=Severity.INFO,
        target_nets=[".*TEST.*"],
        suggestion="This is a test"
    )
    result = config.add_rule(new_rule)
    print(f"Add rule: {'success' if result else 'failed'}")

    # 更新规则
    result = config.update_rule("TEST001", name="Updated Test Rule")
    print(f"Update rule: {'success' if result else 'failed'}")

    # 导出配置到跨平台路径
    config_path = get_default_config_path()
    config.save_to_file(config_path)
    print(f"\n✓ Configuration saved to: {config_path}")
