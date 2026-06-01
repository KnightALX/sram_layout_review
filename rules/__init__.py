#!/usr/bin/env python3
"""
Rules Package - 规则插件系统
提供灵活的规则扩展机制
"""

# 导入基础类
from rules.base_rule import (
    BaseRule,
    ConstraintType,
    Severity,
    RuleParameter
)

# 导入注册中心
from rules.registry import (
    RuleRegistry,
    register_rule,
    auto_load_rules,
    create_rule,
    list_rules
)


# 初始化函数
def initialize_rules() -> RuleRegistry:
    """初始化规则系统"""
    return RuleRegistry.get_instance()


# 自动初始化：导入子包中的规则
def _auto_import_rules():
    """从子目录自动导入规则"""
    import rules.drc
    import rules.si
    import rules.em
    import rules.sram
    import rules.qty


_auto_import_rules()


__all__ = [
    'BaseRule', 'ConstraintType', 'Severity', 'RuleParameter',
    'RuleRegistry', 'register_rule', 'auto_load_rules', 'create_rule', 'list_rules',
    'initialize_rules',
]
