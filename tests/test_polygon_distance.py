#!/usr/bin/env python3
"""
Unit tests for Polygon distance calculation
测试多边形距离计算
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_system import get_sram_7nm_config
from review_engine import Point, Polygon, ProfessionalLayoutReviewEngine


class TestPolygonDistance(unittest.TestCase):
    """测试多边形距离计算"""

    def setUp(self):
        self.engine = ProfessionalLayoutReviewEngine(get_sram_7nm_config())

    def test_separated_polygons_x(self):
        """测试X方向分离的多边形"""
        # poly1: x=0到x=5, y=0到y=1
        poly1 = Polygon(
            points=[Point(0, 0), Point(5, 0), Point(5, 1), Point(0, 1)],
            layer='met1'
        )
        # poly2: x=10到x=15, y=0到y=1 (与poly1在X方向分离)
        poly2 = Polygon(
            points=[Point(10, 0), Point(15, 0), Point(15, 1), Point(10, 1)],
            layer='met1'
        )

        dist = self.engine._min_polygon_distance(poly1, poly2)

        # 距离应该是5 (10 - 5 = 5)
        self.assertAlmostEqual(dist, 5.0, places=2)

    def test_separated_polygons_y(self):
        """测试Y方向分离的多边形"""
        # poly1: x=0到x=5, y=0到y=5
        poly1 = Polygon(
            points=[Point(0, 0), Point(5, 0), Point(5, 5), Point(0, 5)],
            layer='met1'
        )
        # poly2: x=0到x=5, y=10到y=15 (与poly1在Y方向分离)
        poly2 = Polygon(
            points=[Point(0, 10), Point(5, 10), Point(5, 15), Point(0, 15)],
            layer='met1'
        )

        dist = self.engine._min_polygon_distance(poly1, poly2)

        # 距离应该是5 (10 - 5 = 5)
        self.assertAlmostEqual(dist, 5.0, places=2)

    def test_separated_polygons_diagonal(self):
        """测试对角线分离的多边形"""
        # poly1: 左下角
        poly1 = Polygon(
            points=[Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)],
            layer='met1'
        )
        # poly2: 右上角，对角分离
        poly2 = Polygon(
            points=[Point(10, 10), Point(11, 10), Point(11, 11), Point(10, 11)],
            layer='met1'
        )

        dist = self.engine._min_polygon_distance(poly1, poly2)

        # 距离应该是 sqrt(9^2 + 9^2) = 12.73
        expected = math.sqrt(9 ** 2 + 9 ** 2)
        self.assertAlmostEqual(dist, expected, places=1)

    def test_overlapping_polygons(self):
        """测试重叠的多边形"""
        poly1 = Polygon(
            points=[Point(0, 0), Point(5, 0), Point(5, 5), Point(0, 5)],
            layer='met1'
        )
        poly2 = Polygon(
            points=[Point(2, 2), Point(7, 2), Point(7, 7), Point(2, 7)],
            layer='met1'
        )

        dist = self.engine._min_polygon_distance(poly1, poly2)

        # 重叠时距离应该是0
        self.assertEqual(dist, 0.0)

    def test_touching_polygons(self):
        """测试刚好接触的多边形"""
        poly1 = Polygon(
            points=[Point(0, 0), Point(5, 0), Point(5, 5), Point(0, 5)],
            layer='met1'
        )
        # poly2的左边与poly1的右边接触
        poly2 = Polygon(
            points=[Point(5, 0), Point(10, 0), Point(10, 5), Point(5, 5)],
            layer='met1'
        )

        dist = self.engine._min_polygon_distance(poly1, poly2)

        # 接触时距离应该是0
        self.assertEqual(dist, 0.0)

    def test_identical_polygons(self):
        """测试相同的多边形"""
        poly1 = Polygon(
            points=[Point(0, 0), Point(5, 0), Point(5, 5), Point(0, 5)],
            layer='met1'
        )
        poly2 = Polygon(
            points=[Point(0, 0), Point(5, 0), Point(5, 5), Point(0, 5)],
            layer='met1'
        )

        dist = self.engine._min_polygon_distance(poly1, poly2)

        # 相同多边形距离为0
        self.assertEqual(dist, 0.0)


class TestPolygonProperties(unittest.TestCase):
    """测试多边形属性计算"""

    def test_bbox(self):
        """测试边界框计算"""
        poly = Polygon(
            points=[Point(1, 2), Point(5, 2), Point(5, 7), Point(1, 7)],
            layer='met1'
        )

        bbox = poly.bbox
        self.assertEqual(bbox[0], 1)  # xmin
        self.assertEqual(bbox[1], 2)  # ymin
        self.assertEqual(bbox[2], 5)  # xmax
        self.assertEqual(bbox[3], 7)  # ymax

    def test_center(self):
        """测试中心点计算"""
        poly = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)],
            layer='met1'
        )

        center = poly.center
        self.assertAlmostEqual(center.x, 5.0, places=2)
        self.assertAlmostEqual(center.y, 5.0, places=2)

    def test_width_height(self):
        """测试宽度和高度"""
        poly = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(10, 5), Point(0, 5)],
            layer='met1'
        )

        self.assertAlmostEqual(poly.width, 10.0, places=2)
        self.assertAlmostEqual(poly.height, 5.0, places=2)

    def test_area(self):
        """测试面积计算（使用Shoelace公式）"""
        # 1x1正方形
        poly = Polygon(
            points=[Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)],
            layer='met1'
        )

        self.assertAlmostEqual(poly.area, 1.0, places=2)

    def test_is_rectangular(self):
        """测试矩形判定"""
        # 矩形
        rect = Polygon(
            points=[Point(0, 0), Point(10, 0), Point(10, 5), Point(0, 5)],
            layer='met1'
        )
        self.assertTrue(rect.is_rectangular)

        # L形不是矩形
        l_shape = Polygon(
            points=[Point(0, 0), Point(5, 0), Point(5, 5), Point(2, 5), Point(2, 10), Point(0, 10)],
            layer='met1'
        )
        self.assertFalse(l_shape.is_rectangular)


if __name__ == '__main__':
    unittest.main()
