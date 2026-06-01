#!/usr/bin/env python3
"""
Unit tests for Routing Check Engine module
路由检查引擎模块的单元测试

包含10个测试用例：
- TC01: 纯水平走线
- TC02: 纯垂直走线
- TC03: 均衡混合走线
- TC04: 空路由
- TC05: Tau超限
- TC06: 最长线段识别
- TC07: 多层分组统计
- TC08: 边界条件
- TC09: 配置参数覆盖
- TC10: 严格模式验证
"""

import unittest
import sys
import os
import importlib.util

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)


def _load_module_directly(module_name, file_path):
    """直接加载模块而不通过__init__"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 预先加载依赖模块，避免core/__init__.py导入问题
_review_engine_path = os.path.join(_project_root, 'review_engine.py')
_routing_check_path = os.path.join(_project_root, 'core', 'routing_check.py')

# 确保review_engine先加载
if 'review_engine' not in sys.modules:
    _load_module_directly('review_engine', _review_engine_path)

if 'core.routing_check' not in sys.modules:
    _load_module_directly('core.routing_check', _routing_check_path)

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


class TestRoutingCheckEngine(unittest.TestCase):
    """路由检查引擎测试基类"""

    def setUp(self):
        """测试初始化"""
        self.engine = create_default_engine()
        self.tech_layers = {
            'met1': {
                'type': 'metal',
                'min_width': 0.032,
                'resistance_per_sq': 0.15,
                'capacitance_per_um': 0.20,
            },
            'met2': {
                'type': 'metal',
                'min_width': 0.032,
                'resistance_per_sq': 0.12,
                'capacitance_per_um': 0.16,
            },
            'met3': {
                'type': 'metal',
                'min_width': 0.048,
                'resistance_per_sq': 0.10,
                'capacitance_per_um': 0.14,
            },
        }


# ============================================================================
# 测试用例
# ============================================================================

class TC01_HorizontalRouting(unittest.TestCase):
    """TC01: 纯水平走线 (avg_x_ratio 应接近 1.0)"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_horizontal_routing_ratio(self):
        """测试纯水平走线的X方向占比"""
        # 创建水平矩形 - 宽度远大于高度
        poly = Polygon(
            points=[
                Point(0, 0),
                Point(100, 0),
                Point(100, 0.032),
                Point(0, 0.032),
            ],
            layer='met1',
            net_name='horizontal_net'
        )

        result = self.engine.check_routing('horizontal_net', [poly])

        # 纯水平走线，X方向占比应该接近1.0
        self.assertGreater(result.avg_x_ratio, 0.95,
            f"X ratio should be > 0.95 for horizontal wire, got {result.avg_x_ratio:.4f}")
        self.assertLess(result.avg_y_ratio, 0.05,
            f"Y ratio should be < 0.05 for horizontal wire, got {result.avg_y_ratio:.4f}")

    def test_multiple_horizontal_wires(self):
        """测试多条水平走线"""
        polys = [
            Polygon(
                points=[Point(0, i*0.1), Point(50, i*0.1),
                        Point(50, i*0.1 + 0.032), Point(0, i*0.1 + 0.032)],
                layer='met1',
                net_name='h_net'
            )
            for i in range(3)
        ]

        result = self.engine.check_routing('h_net', polys)

        # 多条水平走线应该都是X方向为主
        self.assertGreater(result.avg_x_ratio, 0.9)
        print(f"[TC01] Multiple horizontal wires - X ratio: {result.avg_x_ratio:.4f}")


class TC02_VerticalRouting(unittest.TestCase):
    """TC02: 纯垂直走线 (avg_y_ratio 应接近 1.0)"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_vertical_routing_ratio(self):
        """测试纯垂直走线的Y方向占比"""
        # 创建垂直矩形 - 高度远大于宽度
        poly = Polygon(
            points=[
                Point(0, 0),
                Point(0.032, 0),
                Point(0.032, 100),
                Point(0, 100),
            ],
            layer='met2',
            net_name='vertical_net'
        )

        result = self.engine.check_routing('vertical_net', [poly])

        # 纯垂直走线，Y方向占比应该接近1.0
        self.assertGreater(result.avg_y_ratio, 0.95,
            f"Y ratio should be > 0.95 for vertical wire, got {result.avg_y_ratio:.4f}")
        self.assertLess(result.avg_x_ratio, 0.05,
            f"X ratio should be < 0.05 for vertical wire, got {result.avg_x_ratio:.4f}")

    def test_multiple_vertical_wires(self):
        """测试多条垂直走线"""
        polys = [
            Polygon(
                points=[Point(i*0.1, 0), Point(i*0.1 + 0.032, 0),
                        Point(i*0.1 + 0.032, 50), Point(i*0.1, 50)],
                layer='met2',
                net_name='v_net'
            )
            for i in range(3)
        ]

        result = self.engine.check_routing('v_net', polys)

        # 多条垂直走线应该都是Y方向为主
        self.assertGreater(result.avg_y_ratio, 0.9)
        print(f"[TC02] Multiple vertical wires - Y ratio: {result.avg_y_ratio:.4f}")


class TC03_BalancedRouting(unittest.TestCase):
    """TC03: 均衡混合走线 (avg_x_ratio 和 avg_y_ratio 应接近 0.5)"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_balanced_routing_ratio(self):
        """测试均衡混合走线的方向占比"""
        # 创建L形走线 - 水平和垂直各一半
        polys = [
            # 水平段
            Polygon(
                points=[Point(0, 0), Point(50, 0),
                        Point(50, 0.032), Point(0, 0.032)],
                layer='met1',
                net_name='balanced_net'
            ),
            # 垂直段
            Polygon(
                points=[Point(50, 0), Point(50.032, 0),
                        Point(50.032, 50), Point(50, 50)],
                layer='met2',
                net_name='balanced_net'
            ),
        ]

        result = self.engine.check_routing('balanced_net', polys)

        # 均衡混合走线，X和Y方向占比应该都接近0.5
        # 允许±20%的容差
        self.assertAlmostEqual(result.avg_x_ratio, 0.5, delta=0.2,
            msg=f"X ratio should be ~0.5 for balanced routing, got {result.avg_x_ratio:.4f}")
        self.assertAlmostEqual(result.avg_y_ratio, 0.5, delta=0.2,
            msg=f"Y ratio should be ~0.5 for balanced routing, got {result.avg_y_ratio:.4f}")

        # X + Y 应该约等于1
        total_ratio = result.avg_x_ratio + result.avg_y_ratio
        self.assertAlmostEqual(total_ratio, 1.0, delta=0.01,
            msg=f"Total ratio should be ~1.0, got {total_ratio:.4f}")

    def test_near_balanced_routing(self):
        """测试接近均衡的走线 (40% X, 60% Y)"""
        polys = [
            # 水平段 (较短)
            Polygon(
                points=[Point(0, 0), Point(40, 0),
                        Point(40, 0.032), Point(0, 0.032)],
                layer='met1',
                net_name='near_balanced'
            ),
            # 垂直段 (较长)
            Polygon(
                points=[Point(40, 0), Point(40.032, 0),
                        Point(40.032, 60), Point(40, 60)],
                layer='met2',
                net_name='near_balanced'
            ),
        ]

        result = self.engine.check_routing('near_balanced', polys)

        # X应该接近40%，Y接近60% (考虑矩形多边形的边长计算方式)
        self.assertGreater(result.avg_x_ratio, 0.35,
            msg=f"X ratio should be > 0.35, got {result.avg_x_ratio:.4f}")
        self.assertGreater(result.avg_y_ratio, 0.35,
            msg=f"Y ratio should be > 0.35, got {result.avg_y_ratio:.4f}")
        # 总和应该约等于1
        total = result.avg_x_ratio + result.avg_y_ratio
        self.assertAlmostEqual(total, 1.0, delta=0.05)
        print(f"[TC03] Near balanced - X: {result.avg_x_ratio:.2%}, Y: {result.avg_y_ratio:.2%}")


class TC04_EmptyRouting(unittest.TestCase):
    """TC04: 空路由 (无走线数据)"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_empty_polygons(self):
        """测试空多边形列表"""
        result = self.engine.check_routing('empty_net', [])

        # 空路由应该返回WARNING状态
        self.assertEqual(result.status, CheckStatus.WARNING)
        self.assertGreater(len(result.violations), 0)
        self.assertEqual(result.violation_count, 1)

        # 违规消息应该是关于空路由的
        violation = result.violations[0]
        self.assertIn("Empty routing", violation.message)

    def test_non_metal_layers(self):
        """测试只包含非金属层的polygons"""
        # Poly层不是金属层，不应该产生走线段
        poly = Polygon(
            points=[Point(0, 0), Point(100, 0),
                    Point(100, 0.1), Point(0, 0.1)],
            layer='poly',
            net_name='non_metal_net'
        )

        result = self.engine.check_routing('non_metal_net', [poly])

        # 非金属层应该被视为空路由
        self.assertEqual(result.status, CheckStatus.WARNING)
        self.assertGreater(result.violation_count, 0)

    def test_empty_result_attributes(self):
        """测试空路由结果的属性"""
        result = self.engine.check_routing('empty', [])

        # 验证默认属性值
        self.assertEqual(result.avg_x_ratio, 0.0)
        self.assertEqual(result.avg_y_ratio, 0.0)
        self.assertEqual(result.max_segment_length, 0.0)
        self.assertEqual(result.max_segment_layer, "")
        self.assertEqual(result.tau, 0.0)

        print(f"[TC04] Empty routing result: {result.get_violation_summary()}")


class TC05_TauThreshold(unittest.TestCase):
    """TC05: Tau超限 (tau > threshold -> FAIL)"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_tau_within_threshold(self):
        """测试Tau在阈值内的情况"""
        # 创建RC数据，tau = R * C * 1e-9
        # 设置较小的值，确保tau < threshold
        rc_data = NetRCData(
            net_name='low_tau_net',
            total_resistance=100.0,  # 100 Ω
            total_capacitance=5000.0  # 5000 fF
        )
        # tau = 100 * 5000 * 1e-9 = 0.0005 ns (非常小)

        poly = Polygon(
            points=[Point(0, 0), Point(10, 0),
                    Point(10, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='low_tau_net'
        )

        result = self.engine.check_routing('low_tau_net', [poly], rc_data)

        # tau非常小，应该通过
        self.assertLess(result.tau, self.engine.config.tau_threshold)

        # 使用自定义配置允许WARNING（因为默认配置可能因为X比率产生WARNING）
        # 这是正常的，因为水平走线本身不会FAIL
        self.assertIn(result.status, [CheckStatus.PASS, CheckStatus.WARNING])

    def test_tau_exceeds_threshold(self):
        """测试Tau超过阈值的情况"""
        # 创建高RC数据，使得tau > threshold (默认1ns)
        # tau = R * C * 1e-9 > 1
        # 例如: R=1000Ω, C=2000fF -> tau = 1000 * 2000 * 1e-9 = 0.002 ns
        # 需要更大的值: R=1000Ω, C=2000000fF -> tau = 1000 * 2000000 * 1e-9 = 2 ns
        rc_data = NetRCData(
            net_name='high_tau_net',
            total_resistance=1000.0,  # 1000 Ω
            total_capacitance=2000000.0  # 2000000 fF = 2μF
        )

        poly = Polygon(
            points=[Point(0, 0), Point(10, 0),
                    Point(10, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='high_tau_net'
        )

        result = self.engine.check_routing('high_tau_net', [poly], rc_data)

        # tau应该超过阈值
        self.assertGreater(result.tau, self.engine.config.tau_threshold)

        # 应该至少有一个Tau超限的违规
        tau_violations = [v for v in result.violations if v.type == ViolationType.TAU_THRESHOLD]
        self.assertGreater(len(tau_violations), 0,
            "Should have Tau threshold violation")

        # Tau超限应该是CRITICAL级别的FAIL
        self.assertEqual(result.status, CheckStatus.FAIL)

        print(f"[TC05] Tau exceeded: {result.tau:.4f}ns > {self.engine.config.tau_threshold:.4f}ns")

    def test_custom_tau_threshold(self):
        """测试自定义Tau阈值"""
        config = RoutingCheckConfig(tau_threshold=0.5)  # 0.5ns阈值
        engine = RoutingCheckEngine(config)

        # tau = R * C * 1e-9 = 500 * 2000000 * 1e-9 = 1 ns (大于0.5ns阈值)
        rc_data = NetRCData(
            net_name='custom_tau',
            total_resistance=500.0,
            total_capacitance=2000000.0
        )

        poly = Polygon(
            points=[Point(0, 0), Point(1, 0),
                    Point(1, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='custom_tau'
        )

        result = engine.check_routing('custom_tau', [poly], rc_data)

        # tau=1ns > threshold=0.5ns，应该FAIL
        self.assertGreater(result.tau, 0.5, "Tau should be > 0.5ns threshold")
        self.assertEqual(result.status, CheckStatus.FAIL)


class TC06_MaxSegmentLength(unittest.TestCase):
    """TC06: 最长线段识别"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_longest_segment_detection(self):
        """测试最长线段识别"""
        # 创建不同长度的线段
        polys = [
            # 短段 (10μm)
            Polygon(
                points=[Point(0, 0), Point(10, 0),
                        Point(10, 0.032), Point(0, 0.032)],
                layer='met1',
                net_name='length_test'
            ),
            # 长段 (100μm) - 应该是最长的
            Polygon(
                points=[Point(0, 10), Point(100, 10),
                        Point(100, 10.032), Point(0, 10.032)],
                layer='met2',
                net_name='length_test'
            ),
            # 中段 (50μm)
            Polygon(
                points=[Point(0, 20), Point(50, 20),
                        Point(50, 20.032), Point(0, 20.032)],
                layer='met1',
                net_name='length_test'
            ),
        ]

        result = self.engine.check_routing('length_test', polys)

        # 最长线段应该是100μm左右
        self.assertGreater(result.max_segment_length, 90.0)
        self.assertLess(result.max_segment_length, 110.0)

        # 最长线段应该在met2层
        self.assertEqual(result.max_segment_layer, 'met2')

        print(f"[TC06] Max segment length: {result.max_segment_length:.1f}μm on {result.max_segment_layer}")

    def test_max_segment_violation(self):
        """测试最长线段超限违规"""
        # 设置一个较小的max_segment_length阈值
        config = RoutingCheckConfig(max_segment_length=50.0)  # 50μm阈值
        engine = RoutingCheckEngine(config)

        # 创建一个超过阈值的线段
        poly = Polygon(
            points=[Point(0, 0), Point(100, 0),
                    Point(100, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='long_wire'
        )

        result = engine.check_routing('long_wire', [poly])

        # 应该检测到最长线段超限违规
        length_violations = [v for v in result.violations
                           if v.type == ViolationType.MAX_SEGMENT_LENGTH]
        self.assertGreater(len(length_violations), 0)

        # 应该有WARNING状态
        self.assertEqual(result.status, CheckStatus.WARNING)

        print(f"[TC06] Max segment violation: {result.violations[0].message}")

    def test_single_segment(self):
        """测试单线段的情况"""
        poly = Polygon(
            points=[Point(0, 0), Point(25, 0),
                    Point(25, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='single_seg'
        )

        result = self.engine.check_routing('single_seg', [poly])

        # 单线段，它本身就是最长的
        self.assertGreater(result.max_segment_length, 20.0)
        self.assertLess(result.max_segment_length, 30.0)
        self.assertEqual(result.max_segment_layer, 'met1')


class TC07_MultiLayerStats(unittest.TestCase):
    """TC07: 多层分组统计"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_multi_layer_routing(self):
        """测试多层走线统计"""
        polys = [
            # met1层 - 水平段
            Polygon(
                points=[Point(0, 0), Point(30, 0),
                        Point(30, 0.032), Point(0, 0.032)],
                layer='met1',
                net_name='multi_layer'
            ),
            # met2层 - 垂直段
            Polygon(
                points=[Point(30, 0), Point(30.032, 0),
                        Point(30.032, 30), Point(30, 30)],
                layer='met2',
                net_name='multi_layer'
            ),
            # met3层 - 水平段
            Polygon(
                points=[Point(30, 30), Point(60, 30),
                        Point(60, 30.048), Point(30, 30.048)],
                layer='met3',
                net_name='multi_layer'
            ),
        ]

        result = self.engine.check_routing('multi_layer', polys)

        # 验证多层走线
        self.assertGreater(result.max_segment_length, 0)
        self.assertIn(result.max_segment_layer, ['met1', 'met2', 'met3'])

        # 方向占比应该在合理范围内
        self.assertGreater(result.avg_x_ratio + result.avg_y_ratio, 0.9)

        print(f"[TC07] Multi-layer routing: {result.max_segment_layer}, "
              f"X={result.avg_x_ratio:.2%}, Y={result.avg_y_ratio:.2%}")

    def test_layer_assignment(self):
        """测试层信息正确分配"""
        polys = [
            Polygon(
                points=[Point(0, 0), Point(20, 0),
                        Point(20, 0.032), Point(0, 0.032)],
                layer='met1',
                net_name='layer_test'
            ),
            Polygon(
                points=[Point(20, 0), Point(20.032, 0),
                        Point(20.032, 20), Point(20, 20)],
                layer='met2',
                net_name='layer_test'
            ),
        ]

        result = self.engine.check_routing('layer_test', polys)

        # 最长线段应该在met2层（因为垂直线段可能更长）
        self.assertIn(result.max_segment_layer, ['met1', 'met2'])


class TC08_BoundaryConditions(unittest.TestCase):
    """TC08: 边界条件 (零长度线段)"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_zero_length_polygon(self):
        """测试零长度多边形（退化为点）"""
        # 退化为点的多边形
        poly = Polygon(
            points=[
                Point(0, 0),
                Point(0, 0),
                Point(0, 0.001),
                Point(0, 0.001),
            ],
            layer='met1',
            net_name='zero_length'
        )

        result = self.engine.check_routing('zero_length', [poly])

        # 应该处理这种边界情况而不崩溃
        self.assertIsNotNone(result)
        self.assertIn(result.status, [CheckStatus.PASS, CheckStatus.WARNING])

    def test_very_short_segment(self):
        """测试非常短的线段"""
        poly = Polygon(
            points=[Point(0, 0), Point(0.001, 0),
                    Point(0.001, 0.001), Point(0, 0.001)],
            layer='met1',
            net_name='very_short'
        )

        result = self.engine.check_routing('very_short', [poly])

        # 短线段应该被正确处理
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.avg_x_ratio, 0.0)
        self.assertLessEqual(result.avg_x_ratio, 1.0)

    def test_mixed_zero_and_valid_segments(self):
        """测试混合零长度和有效线段"""
        polys = [
            # 有效线段
            Polygon(
                points=[Point(0, 0), Point(50, 0),
                        Point(50, 0.032), Point(0, 0.032)],
                layer='met1',
                net_name='mixed'
            ),
            # 零长度/无效线段（太短）
            Polygon(
                points=[Point(0, 10), Point(0.001, 10),
                        Point(0.001, 10.001), Point(0, 10.001)],
                layer='met1',
                net_name='mixed'
            ),
        ]

        result = self.engine.check_routing('mixed', polys)

        # 有效线段应该被正确处理
        self.assertGreater(result.max_segment_length, 40.0)
        # 注意：由于短多边形仍被解析为线段，可能会产生WARNING
        self.assertIn(result.status, [CheckStatus.PASS, CheckStatus.WARNING])

        print(f"[TC08] Mixed segments: max={result.max_segment_length:.1f}μm")

    def test_extreme_aspect_ratio(self):
        """测试极端长宽比"""
        # 非常长的细线
        poly = Polygon(
            points=[Point(0, 0), Point(1000, 0),
                    Point(1000, 0.001), Point(0, 0.001)],
            layer='met1',
            net_name='extreme_ar'
        )

        result = self.engine.check_routing('extreme_ar', [poly])

        # 极端长宽比的线应该被正确分类为水平
        self.assertGreater(result.avg_x_ratio, 0.9)
        self.assertLess(result.avg_y_ratio, 0.1)


class TC09_ConfigOverride(unittest.TestCase):
    """TC09: 配置参数覆盖"""

    def test_custom_config(self):
        """测试自定义配置"""
        config = RoutingCheckConfig(
            fullchip_x=2000.0,
            fullchip_y=2000.0,
            tau_threshold=2.0,
            routing_ratio_x=0.7,
            routing_ratio_y=0.7,
            max_segment_length=300.0,
            strict_mode=False
        )

        engine = RoutingCheckEngine(config)

        self.assertEqual(engine.config.fullchip_x, 2000.0)
        self.assertEqual(engine.config.fullchip_y, 2000.0)
        self.assertEqual(engine.config.tau_threshold, 2.0)
        self.assertEqual(engine.config.routing_ratio_x, 0.7)
        self.assertEqual(engine.config.routing_ratio_y, 0.7)
        self.assertEqual(engine.config.max_segment_length, 300.0)
        self.assertEqual(engine.config.strict_mode, False)

    def test_ratio_threshold_override(self):
        """测试比率阈值覆盖"""
        # 默认阈值是0.8
        engine1 = create_default_engine()
        self.assertEqual(engine1.config.routing_ratio_x, 0.8)
        self.assertEqual(engine1.config.routing_ratio_y, 0.8)

        # 自定义阈值
        config = RoutingCheckConfig(routing_ratio_x=0.6, routing_ratio_y=0.9)
        engine2 = RoutingCheckEngine(config)
        self.assertEqual(engine2.config.routing_ratio_x, 0.6)
        self.assertEqual(engine2.config.routing_ratio_y, 0.9)

        # 测试阈值生效
        poly = Polygon(
            points=[Point(0, 0), Point(100, 0),
                    Point(100, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='ratio_test'
        )

        # X比例0.95 > 0.6，应该产生WARNING
        result = engine2.check_routing('ratio_test', [poly])
        ratio_violations = [v for v in result.violations
                           if v.type == ViolationType.ROUTING_RATIO_X]
        self.assertGreater(len(ratio_violations), 0)

        print(f"[TC09] Ratio threshold override - X violation detected")

    def test_config_validation(self):
        """测试配置参数验证"""
        # 超出范围的参数应该被钳制
        config = RoutingCheckConfig(
            routing_ratio_x=1.5,  # 超出范围
            routing_ratio_y=-0.5   # 超出范围
        )

        # 应该被钳制到有效范围 [0, 1]
        self.assertLessEqual(config.routing_ratio_x, 1.0)
        self.assertGreaterEqual(config.routing_ratio_x, 0.0)
        self.assertLessEqual(config.routing_ratio_y, 1.0)
        self.assertGreaterEqual(config.routing_ratio_y, 0.0)


class TC10_StrictMode(unittest.TestCase):
    """TC10: 严格模式验证"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_strict_mode_off(self):
        """测试严格模式关闭"""
        # 严格模式关闭，WARNING不导致FAIL
        config = RoutingCheckConfig(
            max_segment_length=50.0,
            strict_mode=False
        )
        engine = RoutingCheckEngine(config)

        poly = Polygon(
            points=[Point(0, 0), Point(100, 0),
                    Point(100, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='strict_off'
        )

        result = engine.check_routing('strict_off', [poly])

        # 应该有WARNING
        self.assertGreater(len(result.violations), 0)

        # 但状态应该是WARNING，不是FAIL
        self.assertEqual(result.status, CheckStatus.WARNING)

    def test_strict_mode_on(self):
        """测试严格模式开启"""
        # 严格模式开启，WARNING导致FAIL
        config = RoutingCheckConfig(
            max_segment_length=50.0,
            strict_mode=True
        )
        engine = RoutingCheckEngine(config)

        poly = Polygon(
            points=[Point(0, 0), Point(100, 0),
                    Point(100, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='strict_on'
        )

        result = engine.check_routing('strict_on', [poly])

        # 应该有违规
        self.assertGreater(len(result.violations), 0)

        # 在严格模式下，即使是WARNING也应该导致FAIL
        self.assertEqual(result.status, CheckStatus.FAIL)

        print(f"[TC10] Strict mode: violations={len(result.violations)}, status={result.status.value}")

    def test_critical_always_fail(self):
        """测试CRITICAL级别始终导致FAIL"""
        # 创建一个严格的配置：tau阈值很小，确保tau会超过
        config = RoutingCheckConfig(
            tau_threshold=0.0001,  # 非常小的阈值
            routing_ratio_x=1.0,   # 允许所有X方向走线
            routing_ratio_y=1.0,    # 允许所有Y方向走线
            max_segment_length=1000.0,  # 允许长线段
            strict_mode=False  # 严格模式关闭
        )
        engine = RoutingCheckEngine(config)

        # tau = 100 * 10000 * 1e-9 = 0.001 ns
        rc_data = NetRCData(
            net_name='critical_test',
            total_resistance=100.0,
            total_capacitance=10000.0
        )

        poly = Polygon(
            points=[Point(0, 0), Point(1, 0),
                    Point(1, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='critical_test'
        )

        result = engine.check_routing('critical_test', [poly], rc_data)

        # tau 0.001 > threshold 0.0001，应该超过阈值
        self.assertGreater(result.tau, config.tau_threshold)

        # CRITICAL级别即使在非严格模式也应该导致FAIL
        self.assertEqual(result.status, CheckStatus.FAIL)

        # 检查是否有CRITICAL级别的违规
        critical_violations = [v for v in result.violations if v.severity == "CRITICAL"]
        self.assertGreater(len(critical_violations), 0)

    def test_batch_check_summary(self):
        """测试批量检查汇总"""
        config = RoutingCheckConfig(strict_mode=True)
        engine = RoutingCheckEngine(config)

        nets_data = {
            'net1': ([
                Polygon(
                    points=[Point(0, 0), Point(100, 0),
                            Point(100, 0.032), Point(0, 0.032)],
                    layer='met1',
                    net_name='net1'
                )
            ], None),
            'net2': ([
                Polygon(
                    points=[Point(0, 0), Point(0.032, 0),
                            Point(0.032, 100), Point(0, 100)],
                    layer='met2',
                    net_name='net2'
                )
            ], None),
        }

        results = engine.batch_check(nets_data)
        summary = engine.get_summary(results)

        # 验证汇总信息
        self.assertEqual(summary['total_nets'], 2)
        self.assertIn('passed', summary)
        self.assertIn('failed', summary)
        self.assertIn('warnings', summary)
        self.assertIn('pass_rate', summary)

        print(f"[TC10] Batch summary: {summary}")


# ============================================================================
# 便捷函数测试
# ============================================================================

class TestConvenienceFunctions(unittest.TestCase):
    """便捷函数测试"""

    def test_create_default_engine(self):
        """测试创建默认引擎"""
        engine = create_default_engine()
        self.assertIsInstance(engine, RoutingCheckEngine)
        self.assertIsInstance(engine.config, RoutingCheckConfig)

    def test_check_net_routing(self):
        """测试便捷检查函数"""
        poly = Polygon(
            points=[Point(0, 0), Point(10, 0),
                    Point(10, 0.032), Point(0, 0.032)],
            layer='met1',
            net_name='convenience_test'
        )

        result = check_net_routing('convenience_test', [poly])

        self.assertIsInstance(result, RoutingCheckResult)
        self.assertEqual(result.net_name, 'convenience_test')
        self.assertGreater(result.avg_x_ratio, 0.5)


# ============================================================================
# 集成测试
# ============================================================================

class TestRoutingCheckIntegration(unittest.TestCase):
    """路由检查集成测试"""

    def setUp(self):
        self.engine = create_default_engine()

    def test_full_workflow(self):
        """测试完整工作流程"""
        # 1. 创建测试数据
        polys = [
            Polygon(
                points=[Point(0, 0), Point(50, 0),
                        Point(50, 0.032), Point(0, 0.032)],
                layer='met1',
                net_name='full_test'
            ),
            Polygon(
                points=[Point(50, 0), Point(50.032, 0),
                        Point(50.032, 30), Point(50, 30)],
                layer='met2',
                net_name='full_test'
            ),
            Polygon(
                points=[Point(50, 30), Point(80, 30),
                        Point(80, 30.032), Point(50, 30.032)],
                layer='met3',
                net_name='full_test'
            ),
        ]

        rc_data = NetRCData(
            net_name='full_test',
            total_resistance=50.0,
            total_capacitance=1000.0
        )

        # 2. 执行检查
        result = self.engine.check_routing('full_test', polys, rc_data)

        # 3. 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result.net_name, 'full_test')
        self.assertGreater(result.tau, 0)
        self.assertGreater(result.max_segment_length, 0)
        self.assertGreater(result.avg_x_ratio + result.avg_y_ratio, 0.9)

        # 4. 打印结果摘要
        print(f"\n[Integration] Full workflow test:")
        print(f"  Net: {result.net_name}")
        print(f"  X Ratio: {result.avg_x_ratio:.2%}")
        print(f"  Y Ratio: {result.avg_y_ratio:.2%}")
        print(f"  Max Segment: {result.max_segment_length:.1f}μm on {result.max_segment_layer}")
        print(f"  Tau: {result.tau:.6f}ns")
        print(f"  Status: {result.status.value}")
        print(f"  Violations: {result.violation_count}")


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("Routing Check Engine - Unit Tests")
    print("=" * 70)

    # 运行所有测试
    unittest.main(verbosity=2)