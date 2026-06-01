#!/usr/bin/env python3
"""运行路由检查模块测试"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 避免导入core/__init__.py中的其他模块
# 直接测试核心模块
import importlib.util

def load_module_directly(module_name, file_path):
    """直接加载模块而不通过__init__"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# 加载review_engine
review_engine_path = os.path.join(os.path.dirname(__file__), 'review_engine.py')
review_engine = load_module_directly('review_engine', review_engine_path)

# 加载routing_check
routing_check_path = os.path.join(os.path.dirname(__file__), 'core', 'routing_check.py')
routing_check = load_module_directly('core.routing_check', routing_check_path)

# 现在运行测试
import unittest

# 使用简化的导入方式
exec(f'''
from review_engine import Point, Polygon, WireSegment, NetRCData
from core.routing_check import (
    RoutingCheckEngine,
    RoutingCheckConfig,
    RoutingCheckResult,
    Violation,
    ViolationType,
    CheckStatus,
    create_default_engine,
    check_net_routing,
)
''')

# 加载测试模块
test_path = os.path.join(os.path.dirname(__file__), 'tests', 'test_routing_check.py')
with open(test_path, 'r', encoding='utf-8') as f:
    test_content = f.read()

# 移除导入语句（我们已经导入了）
test_content = test_content.replace(
    'from review_engine import Point, Polygon, WireSegment, NetRCData',
    ''
).replace(
    'from core.routing_check import',
    ''
).replace(
    '    RoutingCheckEngine,',
    ''
).replace(
    '    RoutingCheckConfig,',
    ''
).replace(
    '    RoutingCheckResult,',
    ''
).replace(
    '    Violation,',
    ''
).replace(
    '    ViolationType,',
    ''
).replace(
    '    CheckStatus,',
    ''
).replace(
    '    create_default_engine,',
    ''
).replace(
    '    check_net_routing,',
    ''
)

# 执行测试代码
exec(test_content)

if __name__ == '__main__':
    print("=" * 70)
    print("Routing Check Engine - Unit Tests")
    print("=" * 70)
    unittest.main(verbosity=2)