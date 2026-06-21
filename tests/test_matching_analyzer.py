#!/usr/bin/env python3
"""
Unit tests for Matching Analyzer module
测试匹配分析功能
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.matching_analyzer import analyze_pair_matching
from review_engine import NetRCData, Point, Polygon


class TestMatchingAnalysis(unittest.TestCase):
    """测试匹配分析"""

    def setUp(self):
        self.design_rules = {
            'max_rc_variation': 0.1,
            'matching_tolerance': 0.05,
        }

    def test_identical_nets(self):
        """测试完全相同的net"""
        rc1 = NetRCData(
            net_name='BL_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=50.0,
            via_count=4,
            layer_usage={'met1': 2, 'met2': 2}
        )
        rc2 = NetRCData(
            net_name='BLB_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=50.0,
            via_count=4,
            layer_usage={'met1': 2, 'met2': 2}
        )

        poly1 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )
        poly2 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )

        result = analyze_pair_matching(
            'BL_0', 'BLB_0', rc1, rc2, [poly1], [poly2], self.design_rules
        )

        # 完全相同的net应该得到高分
        self.assertGreaterEqual(result.match_score, 95)
        self.assertAlmostEqual(result.length_ratio, 1.0, places=2)
        self.assertAlmostEqual(result.resistance_ratio, 1.0, places=2)

    def test_length_mismatch(self):
        """测试长度不匹配"""
        rc1 = NetRCData(
            net_name='BL_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=50.0,
            via_count=4,
            layer_usage={'met1': 2}
        )
        rc2 = NetRCData(
            net_name='BLB_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=60.0,  # 20%差异
            via_count=4,
            layer_usage={'met1': 2}
        )

        poly1 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )
        poly2 = Polygon(
            points=[Point(0, 0), Point(60, 0), Point(60, 0.04), Point(0, 0.04)],
            layer='met1'
        )

        result = analyze_pair_matching(
            'BL_0', 'BLB_0', rc1, rc2, [poly1], [poly2], self.design_rules
        )

        # 长度不匹配应该产生issues
        self.assertGreater(len(result.issues), 0)
        self.assertIn('Length mismatch', result.issues[0])

    def test_resistance_mismatch(self):
        """测试电阻不匹配"""
        rc1 = NetRCData(
            net_name='BL_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=50.0,
            via_count=4,
            layer_usage={'met1': 2}
        )
        rc2 = NetRCData(
            net_name='BLB_0',
            total_resistance=15.0,  # 50%差异
            total_capacitance=100.0,
            total_length=50.0,
            via_count=4,
            layer_usage={'met1': 2}
        )

        poly1 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )
        poly2 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )

        result = analyze_pair_matching(
            'BL_0', 'BLB_0', rc1, rc2, [poly1], [poly2], self.design_rules
        )

        self.assertGreater(len(result.issues), 0)
        self.assertTrue(any('Resistance mismatch' in i for i in result.issues))

    def test_via_count_mismatch(self):
        """测试通孔数量不匹配"""
        rc1 = NetRCData(
            net_name='BL_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=50.0,
            via_count=4,
            layer_usage={'met1': 2}
        )
        rc2 = NetRCData(
            net_name='BLB_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=50.0,
            via_count=8,  # 差异4个
            layer_usage={'met1': 4}
        )

        poly1 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )
        poly2 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )

        result = analyze_pair_matching(
            'BL_0', 'BLB_0', rc1, rc2, [poly1], [poly2], self.design_rules
        )

        self.assertGreater(result.via_count_diff, 0)

    def test_score_bounds(self):
        """测试分数边界"""
        rc1 = NetRCData(
            net_name='BL_0',
            total_resistance=10.0,
            total_capacitance=100.0,
            total_length=50.0,
            via_count=4,
            layer_usage={'met1': 2}
        )
        rc2 = NetRCData(
            net_name='BLB_0',
            total_resistance=100.0,  # 巨大差异
            total_capacitance=1000.0,
            total_length=500.0,
            via_count=0,
            layer_usage={'met1': 0, 'met2': 0}
        )

        poly1 = Polygon(
            points=[Point(0, 0), Point(50, 0), Point(50, 0.04), Point(0, 0.04)],
            layer='met1'
        )
        poly2 = Polygon(
            points=[Point(0, 0), Point(500, 0), Point(500, 0.04), Point(0, 0.04)],
            layer='met2'
        )

        result = analyze_pair_matching(
            'BL_0', 'BLB_0', rc1, rc2, [poly1], [poly2], self.design_rules
        )

        # 分数应该在0-100之间
        self.assertGreaterEqual(result.match_score, 0)
        self.assertLessEqual(result.match_score, 100)


if __name__ == '__main__':
    unittest.main()
