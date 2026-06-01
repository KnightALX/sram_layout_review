#!/usr/bin/env python3
"""
Unit tests for RC Calculator module
测试RC计算功能
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from review_engine import Point, Polygon, WireSegment, Via
from core.rc_calculator import (
    parse_polygons_to_wires,
    calculate_net_rc,
    _extract_layer_number,
)


class TestExtractLayerNumber(unittest.TestCase):
    """测试层号提取函数"""

    def test_met_layers(self):
        self.assertEqual(_extract_layer_number('met1'), 1)
        self.assertEqual(_extract_layer_number('met2'), 2)
        self.assertEqual(_extract_layer_number('met7'), 7)

    def test_metal_layers(self):
        self.assertEqual(_extract_layer_number('metal1'), 1)
        self.assertEqual(_extract_layer_number('metal3'), 3)

    def test_via_layers(self):
        self.assertEqual(_extract_layer_number('via0'), 0)
        self.assertEqual(_extract_layer_number('via1'), 1)

    def test_m_layers(self):
        self.assertEqual(_extract_layer_number('m1'), 1)
        self.assertEqual(_extract_layer_number('m2'), 2)

    def test_no_number(self):
        self.assertEqual(_extract_layer_number('poly'), 0)
        self.assertEqual(_extract_layer_number('active'), 0)

    def test_empty(self):
        self.assertEqual(_extract_layer_number(''), 0)
        self.assertEqual(_extract_layer_number(None), 0)


class TestParsePolygonsToWires(unittest.TestCase):
    """测试多边形解析为走线段"""

    def setUp(self):
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
        }

    def test_horizontal_rectangle(self):
        """测试水平矩形"""
        poly = Polygon(
            points=[
                Point(0, 0),
                Point(10, 0),
                Point(10, 0.04),
                Point(0, 0.04),
            ],
            layer='met1',
            net_name='test_net'
        )

        segments = parse_polygons_to_wires(
            [poly], 'test_net', self.tech_layers
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].width, 0.04)
        self.assertAlmostEqual(segments[0].length, 10.0, places=2)

    def test_vertical_rectangle(self):
        """测试垂直矩形"""
        poly = Polygon(
            points=[
                Point(0, 0),
                Point(0.04, 0),
                Point(0.04, 10),
                Point(0, 10),
            ],
            layer='met1',
            net_name='test_net'
        )

        segments = parse_polygons_to_wires(
            [poly], 'test_net', self.tech_layers
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].width, 0.04)

    def test_multiple_polygons(self):
        """测试多个多边形"""
        poly1 = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(10, 0.04), Point(0, 0.04)],
            layer='met1', net_name='test_net'
        )
        poly2 = Polygon(
            points=[Point(0, 1), Point(5, 1), Point(5, 1.04), Point(0, 1.04)],
            layer='met2', net_name='test_net'
        )

        segments = parse_polygons_to_wires(
            [poly1, poly2], 'test_net', self.tech_layers
        )

        self.assertEqual(len(segments), 2)

    def test_layer_aliases(self):
        """测试层名别名"""
        poly1 = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(10, 0.04), Point(0, 0.04)],
            layer='metal1', net_name='test_net'
        )
        poly2 = Polygon(
            points=[Point(0, 1), Point(5, 1), Point(5, 1.04), Point(0, 1.04)],
            layer='m2', net_name='test_net'
        )

        segments = parse_polygons_to_wires(
            [poly1, poly2], 'test_net', self.tech_layers
        )

        self.assertEqual(len(segments), 2)


class TestCalculateNetRC(unittest.TestCase):
    """测试RC计算"""

    def setUp(self):
        self.tech_layers = {
            'met1': {
                'type': 'metal',
                'min_width': 0.032,
                'resistance_per_sq': 0.15,
                'capacitance_per_um': 0.20,
            },
        }

    def test_single_segment(self):
        """测试单段走线"""
        poly = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(10, 0.04), Point(0, 0.04)],
            layer='met1',
            net_name='test_net'
        )

        rc_data = calculate_net_rc(
            'test_net', [poly], [], self.tech_layers
        )

        self.assertGreater(rc_data.total_resistance, 0)
        self.assertGreater(rc_data.total_capacitance, 0)
        self.assertGreater(rc_data.total_length, 0)
        self.assertIn('met1', rc_data.layer_usage)

    def test_empty_polygons(self):
        """测试空多边形列表"""
        rc_data = calculate_net_rc(
            'test_net', [], [], self.tech_layers
        )

        self.assertEqual(rc_data.total_resistance, 0)
        self.assertEqual(rc_data.total_capacitance, 0)

    def test_capacitance_split(self):
        """测试电容分配（70%对地 + 30%耦合）"""
        poly = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(10, 0.04), Point(0, 0.04)],
            layer='met1',
            net_name='test_net'
        )

        rc_data = calculate_net_rc(
            'test_net', [poly], [], self.tech_layers
        )

        total = rc_data.total_capacitance
        ground = rc_data.ground_capacitance
        coupling = rc_data.coupling_capacitance

        self.assertAlmostEqual(ground / total, 0.7, places=1)
        self.assertAlmostEqual(coupling / total, 0.3, places=1)


class TestViaResistance(unittest.TestCase):
    """测试通孔电阻计算"""

    def test_via_creation(self):
        """测试创建Via对象"""
        via = Via(
            position=Point(1.0, 2.0),
            layer='via1',
            upper_metal='met2',
            lower_metal='met1',
            size=0.028,
            net_name='test_net'
        )

        self.assertGreater(via.resistance, 0)
        self.assertLess(via.resistance, 20)


if __name__ == '__main__':
    unittest.main()
