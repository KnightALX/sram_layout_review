#!/usr/bin/env python3
"""
Base Rule Interface - 规则插件基类
定义规则接口，所有规则需继承此类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ConstraintType(Enum):
    """约束类型"""
    HARD = "hard"      # 硬约束 - 必须遵守
    SOFT = "soft"      # 软约束 - 建议遵守
    INFO = "info"      # 信息提示


class Severity(Enum):
    """严重程度"""
    CRITICAL = "critical"   # 严重 - 必须修复
    WARNING = "warning"     # 警告 - 建议修复
    INFO = "info"           # 信息 - 仅供参考


@dataclass
class RuleParameter:
    """规则参数定义"""
    name: str
    param_type: str  # "string", "number", "boolean", "array", "object"
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    unit: str = ""  # 如 "μm", "Ω", "fF"


class BaseRule(ABC):
    """规则基类 - 所有规则需继承此类"""
    
    # 规则元数据（子类必须定义）
    RULE_ID: str = ""
    NAME: str = ""
    DESCRIPTION: str = ""
    CONSTRAINT_TYPE: ConstraintType = ConstraintType.SOFT
    SEVERITY: Severity = Severity.WARNING
    TARGET_NETS: List[str] = field(default_factory=lambda: [".*"])  # 默认匹配所有
    
    # 参数定义（子类可重写）
    PARAMETERS: List[RuleParameter] = []
    
    def __init__(self, parameters: Dict = None):
        """
        初始化规则
        
        Args:
            parameters: 规则参数字典，会覆盖默认值
        """
        self._parameters = parameters or {}
        self._init_defaults()
    
    def _init_defaults(self):
        """用默认值初始化未设置的参数"""
        for param_def in self.PARAMETERS:
            if param_def.name not in self._parameters:
                self._parameters[param_def.name] = param_def.default
    
    @property
    def rule_id(self) -> str:
        return self.RULE_ID
    
    @property
    def name(self) -> str:
        return self.NAME
    
    @property
    def description(self) -> str:
        return self.DESCRIPTION
    
    @property
    def constraint_type(self) -> ConstraintType:
        return self.CONSTRAINT_TYPE
    
    @property
    def severity(self) -> Severity:
        return self.SEVERITY
    
    @property
    def target_nets(self) -> List[str]:
        return self.TARGET_NETS
    
    @property
    def parameters(self) -> Dict:
        return self._parameters
    
    def get_parameter(self, name: str, default=None):
        """获取参数值"""
        return self._parameters.get(name, default)
    
    def set_parameter(self, name: str, value: Any):
        """设置参数值"""
        self._parameters[name] = value
    
    def matches_net(self, net_name: str) -> bool:
        """检查net是否匹配此规则"""
        import re
        if not self.TARGET_NETS:
            return True
        for pattern in self.TARGET_NETS:
            try:
                if re.search(pattern, net_name, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False
    
    @abstractmethod
    def check(self, net_name: str, net_data: Any, polygons: List[Any]) -> List[Dict]:
        """
        执行检查
        
        Args:
            net_name: net名称
            net_data: net的RC数据 (NetRCData)
            polygons: net的多边形列表
            
        Returns:
            违规列表，每项需包含:
            {
                'rule_id': str,
                'rule_name': str,
                'net_name': str,
                'severity': Severity,
                'message': str,
                'location': Optional[Point],
                'suggestion': str,
                'reference': str
            }
        """
        pass
    
    def get_parameters_schema(self) -> Dict:
        """返回参数JSON Schema，用于UI生成配置表单"""
        schema = {
            "type": "object",
            "properties": {}
        }
        
        for param in self.PARAMETERS:
            prop = {
                "type": param.param_type,
                "description": param.description,
            }
            
            if param.default is not None:
                prop["default"] = param.default
            
            if param.param_type == "number":
                if param.min_value is not None:
                    prop["minimum"] = param.min_value
                if param.max_value is not None:
                    prop["maximum"] = param.max_value
                if param.unit:
                    prop["unit"] = param.unit
            
            if param.unit:
                prop["unit"] = param.unit
            
            schema["properties"][param.name] = prop
        
        return schema
    
    def to_dict(self) -> Dict:
        """导出为字典（用于配置保存）"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "constraint_type": self.constraint_type.value,
            "severity": self.severity.value,
            "target_nets": self.TARGET_NETS,
            "parameters": self._parameters
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BaseRule':
        """从字典创建（用于配置加载）"""
        rule_id = data.get("rule_id", cls.RULE_ID)
        # 查找对应的规则类并实例化
        from rules.registry import RuleRegistry
        registry = RuleRegistry.get_instance()
        rule = registry.create_rule(rule_id)
        if rule:
            rule._parameters = data.get("parameters", {})
            return rule
        return cls(data.get("parameters", {}))
    
    def validate(self) -> List[str]:
        """验证参数是否合法，返回错误列表"""
        errors = []
        
        for param_def in self.PARAMETERS:
            value = self._parameters.get(param_def.name)
            
            if param_def.param_type == "number":
                if value is not None:
                    if param_def.min_value is not None and value < param_def.min_value:
                        errors.append(f"{param_def.name} must be >= {param_def.min_value}")
                    if param_def.max_value is not None and value > param_def.max_value:
                        errors.append(f"{param_def.name} must be <= {param_def.max_value}")
            
            # TODO: 其他类型验证
        
        return errors


# 导出
__all__ = ['BaseRule', 'ConstraintType', 'Severity', 'RuleParameter']
