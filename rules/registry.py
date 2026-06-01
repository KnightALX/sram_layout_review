#!/usr/bin/env python3
"""
Rule Registry - 规则注册中心
负责规则的注册、发现、加载和管理
"""

import os
import importlib
import inspect
from typing import Dict, List, Type, Optional, Any
from pathlib import Path


class RuleRegistry:
    """规则注册中心 - 单例"""
    
    _instance = None
    
    def __init__(self):
        self._rules: Dict[str, Type] = {}  # rule_id -> rule_class
        self._categories: Dict[str, List[str]] = {}  # category -> [rule_ids]
    
    @classmethod
    def get_instance(cls) -> 'RuleRegistry':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """重置实例（用于测试）"""
        cls._instance = None
    
    def register(self, rule_class: Type, category: str = "custom") -> None:
        """
        注册规则类
        
        Args:
            rule_class: 继承自BaseRule的类
            category: 规则分类 (drc/si/em/sram/custom)
        """
        if not hasattr(rule_class, 'RULE_ID'):
            raise ValueError(f"{rule_class.__name__} must define RULE_ID")
        
        rule_id = rule_class.RULE_ID
        self._rules[rule_id] = rule_class
        
        # 添加到分类
        if category not in self._categories:
            self._categories[category] = []
        if rule_id not in self._categories[category]:
            self._categories[category].append(rule_id)
    
    def unregister(self, rule_id: str) -> bool:
        """注销规则"""
        if rule_id in self._rules:
            # 从所有分类中移除
            for category in self._categories:
                if rule_id in self._categories[category]:
                    self._categories[category].remove(rule_id)
            del self._rules[rule_id]
            return True
        return False
    
    def get(self, rule_id: str, parameters: Dict = None) -> Optional[Any]:
        """
        获取规则实例
        
        Args:
            rule_id: 规则ID
            parameters: 规则参数
            
        Returns:
            规则实例，如果不存在返回None
        """
        if rule_id not in self._rules:
            return None
        return self._rules[rule_id](parameters)
    
    def get_class(self, rule_id: str) -> Optional[Type]:
        """获取规则类"""
        return self._rules.get(rule_id)
    
    def list_all(self) -> List[str]:
        """列出所有已注册规则ID"""
        return list(self._rules.keys())
    
    def list_by_category(self, category: str) -> List[str]:
        """列出指定分类的规则"""
        return self._categories.get(category, [])
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._categories.keys())
    
    def get_rule_info(self, rule_id: str) -> Optional[Dict]:
        """获取规则信息"""
        rule_class = self._rules.get(rule_id)
        if not rule_class:
            return None
        
        # 创建实例获取默认参数
        instance = rule_class()
        
        return {
            "rule_id": rule_id,
            "name": instance.name,
            "description": instance.description,
            "constraint_type": instance.constraint_type.value,
            "severity": instance.severity.value,
            "target_nets": instance.target_nets,
            "parameters": instance.PARAMETERS,
            "parameters_schema": instance.get_parameters_schema(),
            "categories": [cat for cat, ids in self._categories.items() if rule_id in ids]
        }
    
    def get_all_rules_info(self) -> List[Dict]:
        """获取所有规则信息"""
        return [
            self.get_rule_info(rid)
            for rid in self.list_all()
        ]


# 装饰器：注册规则
def register_rule(category: str = "custom"):
    """
    装饰器：自动注册规则类
    
    Usage:
        @register_rule("drc")
        class MyRule(BaseRule):
            RULE_ID = "DRC001"
            ...
    """
    def decorator(rule_class: Type):
        registry = RuleRegistry.get_instance()
        registry.register(rule_class, category)
        return rule_class
    return decorator


# 自动加载规则
def auto_load_rules(rules_dir: str = None):
    """
    自动发现并加载规则
    
    Args:
        rules_dir: 规则目录路径，默认从当前目录查找
    """
    if rules_dir is None:
        # 默认从 rules 包目录加载
        current_dir = Path(__file__).parent
        rules_dir = current_dir / "rules"
    
    rules_dir = Path(rules_dir)
    registry = RuleRegistry.get_instance()
    
    # 定义分类映射
    category_map = {
        "drc": "drc",
        "si": "si",
        "em": "em", 
        "sram": "sram"
    }
    
    # 扫描子目录
    for subdir in rules_dir.iterdir():
        if not subdir.is_dir():
            continue
        
        if subdir.name.startswith('_'):
            continue
        
        category = category_map.get(subdir.name, "custom")
        
        # 扫描目录下的Python文件
        for py_file in subdir.glob("*.py"):
            if py_file.name.startswith('_'):
                continue
            
            try:
                # 动态导入模块
                module_name = f"rules.{subdir.name}.{py_file.stem}"
                
                # 添加父目录到path
                import sys
                if str(rules_dir.parent) not in sys.path:
                    sys.path.insert(0, str(rules_dir.parent))
                
                module = importlib.import_module(module_name)
                
                # 查找模块中继承自BaseRule的类
                from rules.base_rule import BaseRule
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BaseRule) and 
                        obj is not BaseRule and
                        hasattr(obj, 'RULE_ID')):
                        # 自动注册
                        obj.__category__ = category
                        registry.register(obj, category)
                        
            except Exception as e:
                print(f"Warning: Failed to load rules from {py_file}: {e}")
    
    return registry


# 便捷函数：创建规则实例
def create_rule(rule_id: str, parameters: Dict = None) -> Optional[Any]:
    """创建规则实例"""
    return RuleRegistry.get_instance().get(rule_id, parameters)


# 便捷函数：列出所有规则
def list_rules() -> List[str]:
    """列出所有已注册规则"""
    return RuleRegistry.get_instance().list_all()


__all__ = ['RuleRegistry', 'register_rule', 'auto_load_rules', 'create_rule', 'list_rules']
