#!/usr/bin/env python3
"""
Professional Layout Review Engine
专业级版图Review引擎

核心功能：
1. 精确的RC提取和计算
2. 点到点(P2P)电阻分析
3. EM/IR详细分析
4. SRAM特定检查
5. 匹配度量化分析
6. 违规分级和统计
"""

import os
import re
import math
import json
import warnings
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set, Callable
from collections import defaultdict
from enum import Enum
import heapq

import numpy as np

warnings.filterwarnings('ignore')

from rules.base_rule import ConstraintType, Severity
from config_system import (
    LayoutReviewConfig, CheckRule,
    TechConfig, get_sram_7nm_config
)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Point:
    """2D点"""
    x: float
    y: float
    
    def __add__(self, other: 'Point') -> 'Point':
        return Point(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other: 'Point') -> 'Point':
        return Point(self.x - other.x, self.y - other.y)
    
    def distance_to(self, other: 'Point') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass  
class Polygon:
    """多边形"""
    points: List[Point]
    layer: str
    net_name: str = ""
    shape_id: int = 0
    
    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """边界框 (xmin, ymin, xmax, ymax)"""
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))
    
    @property
    def center(self) -> Point:
        """几何中心"""
        bbox = self.bbox
        return Point((bbox[0] + bbox[2])/2, (bbox[1] + bbox[3])/2)
    
    @property
    def width(self) -> float:
        bbox = self.bbox
        return bbox[2] - bbox[0]
    
    @property
    def height(self) -> float:
        bbox = self.bbox
        return bbox[3] - bbox[1]
    
    @property
    def area(self) -> float:
        """面积 (Shoelace公式)"""
        n = len(self.points)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.points[i].x * self.points[j].y
            area -= self.points[j].x * self.points[i].y
        return abs(area) / 2.0
    
    @property
    def perimeter(self) -> float:
        """周长"""
        n = len(self.points)
        if n < 2:
            return 0.0
        perim = 0.0
        for i in range(n):
            j = (i + 1) % n
            perim += self.points[i].distance_to(self.points[j])
        return perim
    
    @property
    def edge_lengths(self) -> List[float]:
        """各边长度"""
        n = len(self.points)
        lengths = []
        for i in range(n):
            j = (i + 1) % n
            lengths.append(self.points[i].distance_to(self.points[j]))
        return lengths
    
    @property
    def main_axis(self) -> str:
        """主方向 (horizontal/vertical)"""
        if self.width > self.height:
            return 'horizontal'
        return 'vertical'

    @property
    def is_rectangular(self) -> bool:
        """检查多边形是否为矩形。

        使用以下判定条件：
        1. 有4个不同的顶点（忽略重复的首尾点）
        2. 所有内角接近90度（容差10度）
        3. 对边长度相等（容差5%）
        """
        pts = self._get_unique_points()

        # 需要至少4个点才能构成矩形
        if len(pts) < 4:
            return False

        # 如果点数不是4，可能是不规则多边形
        if len(pts) > 4:
            # 尝试凸包算法简化，但当前实现只接受4点矩形
            return False

        # 检查所有角度是否为90度
        # 角度容差10度：考虑到工艺偏差、光刻误差和版图数据精度
        # 这个容差足够宽松以容纳正常误差，但足够严格以检测真正的问题
        angle_tolerance = 10.0  # 度
        # 长度容差5%：考虑到测量精度和对边应该相等的预期
        length_tolerance = 0.05  # 5%

        for i in range(4):
            p1 = pts[i]
            p2 = pts[(i + 1) % 4]
            p3 = pts[(i + 2) % 4]

            # 计算角度
            v1 = (p1.x - p2.x, p1.y - p2.y)
            v2 = (p3.x - p2.x, p3.y - p2.y)

            angle = self._angle_between_vectors(v1, v2)
            if abs(angle - 90.0) > angle_tolerance:
                return False

        # 检查对边长度是否相等
        sides = [
            self._distance(pts[0], pts[1]),
            self._distance(pts[1], pts[2]),
            self._distance(pts[2], pts[3]),
            self._distance(pts[3], pts[0])
        ]

        # 对边1 (0-1, 2-3) 应该相等
        if sides[0] > 0 and sides[2] > 0:
            if abs(sides[0] - sides[2]) / max(sides[0], sides[2]) > length_tolerance:
                return False
        else:
            return False

        # 对边2 (1-2, 3-0) 应该相等
        if sides[1] > 0 and sides[3] > 0:
            if abs(sides[1] - sides[3]) / max(sides[1], sides[3]) > length_tolerance:
                return False
        else:
            return False

        return True

    def _get_unique_points(self) -> List[Point]:
        """获取去重后的顶点列表（处理首尾重复的闭合多边形）"""
        pts = self.points
        if len(pts) >= 4:
            # 检查首尾是否相同，如果是则去掉最后一个
            if (abs(pts[0].x - pts[-1].x) < 1e-9 and
                abs(pts[0].y - pts[-1].y) < 1e-9):
                pts = pts[:-1]
        return pts

    @staticmethod
    def _distance(p1: Point, p2: Point) -> float:
        """计算两点之间的距离"""
        return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)

    @staticmethod
    def _angle_between_vectors(v1: Tuple[float, float], v2: Tuple[float, float]) -> float:
        """计算两个向量之间的夹角（度）"""
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        mag1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
        mag2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)

        if mag1 < 1e-9 or mag2 < 1e-9:
            return 0.0

        cos_angle = dot / (mag1 * mag2)
        # 处理浮点误差导致的cos值略微超出[-1, 1]范围
        cos_angle = max(-1.0, min(1.0, cos_angle))

        return math.degrees(math.acos(cos_angle))

    def intersects(self, other: 'Polygon') -> bool:
        """检查是否与另一个多边形相交"""
        b1 = self.bbox
        b2 = other.bbox
        return not (b1[2] < b2[0] or b1[0] > b2[2] or 
                   b1[3] < b2[1] or b1[1] > b2[3])
    
    def overlap_area(self, other: 'Polygon') -> float:
        """计算与另一个多边形的重叠面积 (简化版)"""
        if not self.intersects(other):
            return 0.0
        
        # 简化计算：使用bbox交集作为近似
        b1 = self.bbox
        b2 = other.bbox
        
        x_overlap = max(0, min(b1[2], b2[2]) - max(b1[0], b2[0]))
        y_overlap = max(0, min(b1[3], b2[3]) - max(b1[1], b2[1]))
        
        return x_overlap * y_overlap


@dataclass
class Via:
    """通孔"""
    position: Point
    layer: str  # via layer name
    upper_metal: str
    lower_metal: str
    size: float = 0.028  # μm
    net_name: str = ""

    # 典型Via接触电阻 (Ω/via)，基于ITRS和实际工艺数据
    # 实际电阻取决于：via尺寸、层间材料、接触面积
    TYPICAL_CONTACT_RESISTIVITY: float = 15.0  # Ω·μm² (接触电阻率)

    @property
    def resistance(self) -> float:
        """计算Via电阻 - 基于接触面积模型。

        Via电阻 = 接触电阻率 / 接触面积
        这比固定查表更精确，因为考虑了尺寸变化。

        对于叠层via（如via0连接M1-M2），总电阻约为各层via电阻之和。
        """
        # 接触面积 = size² (假设方形via)
        contact_area = self.size * self.size

        if contact_area > 0:
            # R = ρ / A (Ω·μm² / μm² = Ω)
            r_contact = self.TYPICAL_CONTACT_RESISTIVITY / contact_area
            # 限制在合理范围内 [0.1Ω, 20Ω]
            return max(0.1, min(20.0, r_contact))

        # 回退：基于layer的经验值
        layer_resistances = {
            'via0': 5.0, 'via1': 4.0, 'via2': 3.0,
            'via3': 2.5, 'via4': 2.0, 'via5': 1.5
        }
        return layer_resistances.get(self.layer, 3.0)


@dataclass
class WireSegment:
    """走线段 - 用于RC计算"""
    start: Point
    end: Point
    layer: str
    width: float
    net_name: str = ""
    
    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)
    
    @property
    def direction(self) -> str:
        dx = abs(self.end.x - self.start.x)
        dy = abs(self.end.y - self.start.y)
        return 'horizontal' if dx > dy else 'vertical'
    
    def resistance(self, r_per_sq: float) -> float:
        """计算电阻"""
        if self.width > 0:
            squares = self.length / self.width
            return r_per_sq * squares
        return float('inf')
    
    def capacitance(self, c_per_um: float, fringe_c: float = 0.1) -> float:
        """计算电容 (包含边缘电容)。

        电容由两部分组成：
        1. 面积电容 (area_c): C = c_per_um × length
           这是走线与下层ground plane之间的电容

        2. 边缘电容 (fringe_c): C_fringe = fringe_c × 2 × (L + W)
           这是由于电力线在走线边缘发散而产生的额外电容
           fringe_c单位是fF/μm，代表单位长度的边缘电容

        总电容 = area_c + fringe

        Args:
            c_per_um: 单位长度电容 (fF/μm)
            fringe_c: 单位边缘长度电容 (fF/μm)，默认0.1fF/μm是典型值

        Returns:
            总电容 (fF)
        """
        area_c = c_per_um * self.length
        fringe = fringe_c * 2 * (self.length + self.width)
        return area_c + fringe


@dataclass
class NetRCData:
    """Net的RC数据"""
    net_name: str
    total_resistance: float = 0.0       # Ω
    total_capacitance: float = 0.0      # fF
    ground_capacitance: float = 0.0     # fF (对地)
    coupling_capacitance: float = 0.0   # fF (耦合)
    wire_segments: List[WireSegment] = field(default_factory=list)
    vias: List[Via] = field(default_factory=list)
    layer_resistances: Dict[str, float] = field(default_factory=dict)
    layer_capacitances: Dict[str, float] = field(default_factory=dict)

    # 详细统计
    total_length: float = 0.0           # μm
    total_area: float = 0.0             # μm²
    via_count: int = 0
    layer_usage: Dict[str, int] = field(default_factory=dict)

    # 时序分析 (单位: ps)
    # 注意: R (Ω) × C (fF) 物理上等于 1 ps (1 Ω·fF = 10⁻¹⁵ s = 1 ps)
    # 过去使用 1e-9 换算系数,导致结果小 6 个数量级,显示为 0.000
    tau_rc: float = 0.0                 # RC时间常数 (ps) - tau = R * C
    trise: float = 0.0                  # 信号上升时间 (ps)
    tfall: float = 0.0                  # 信号下降时间 (ps)
    tpd_50: float = 0.0                # 传播延迟 50% (ps)

    # 驱动/负载信息
    r_driver: float = 0.0                # Ω - 前级驱动等效电阻
    c_load: float = 0.0                 # fF - 后级负载电容


@dataclass
class P2PResult:
    """点到点电阻分析结果"""
    net_name: str
    source_point: Point
    target_point: Point
    resistance: float                   # Ω
    path_length: float                  # μm
    path_layers: List[str] = field(default_factory=list)
    via_count: int = 0
    bottleneck_layer: Optional[str] = None
    bottleneck_resistance: float = 0.0


@dataclass
class EMResult:
    """EM分析结果"""
    net_name: str
    layer: str
    segment: WireSegment
    max_current: float                  # mA
    current_density: float              # mA/μm
    safety_factor: float                # 安全系数
    em_violation: bool = False
    violation_ratio: float = 0.0


@dataclass
class MatchingAnalysis:
    """匹配分析结果"""
    net1: str
    net2: str
    match_score: float                  # 0-100
    
    # 详细对比
    length_ratio: float                 # L1/L2
    resistance_ratio: float             # R1/R2
    capacitance_ratio: float            # C1/C2
    via_count_diff: int
    
    # 形状匹配
    bbox_similarity: float              # 0-1
    centroid_distance: float            # μm
    routing_pattern_similarity: float   # 0-1
    
    # 问题列表和详细对比 (有默认值的放最后)
    layer_usage_diff: Dict[str, int] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class Violation:
    """违规项"""
    rule_id: str
    rule_name: str
    type: str
    severity: Severity
    net_name: str
    message: str
    location: Optional[Point] = None
    polygons: List[Polygon] = field(default_factory=list)
    wire_segments: List[WireSegment] = field(default_factory=list)
    suggestion: str = ""
    reference: str = ""
    related_data: Dict = field(default_factory=dict)


@dataclass
class ReviewSummary:
    """Review汇总"""
    total_nets: int = 0
    total_violations: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # RC统计
    total_resistance_range: Tuple[float, float] = (0, 0)
    total_capacitance_range: Tuple[float, float] = (0, 0)
    avg_resistance: float = 0
    avg_capacitance: float = 0
    
    # 匹配分析
    matching_pairs_analyzed: int = 0
    poor_matching_count: int = 0
    
    # 层使用统计
    layer_usage: Dict[str, int] = field(default_factory=dict)
    
    # 违规分类
    violations_by_type: Dict[str, int] = field(default_factory=dict)
    violations_by_net: Dict[str, int] = field(default_factory=dict)
    
    # 检查规则统计
    rules_triggered: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# 专业版图Review引擎
# ============================================================================

class ProfessionalLayoutReviewEngine:
    """专业级版图Review引擎"""
    
    def __init__(self, config: LayoutReviewConfig = None):
        self.config = config or get_sram_7nm_config()
        self.tech = self.config.tech_config
        
        # 数据存储
        self.nets: Dict[str, List[Polygon]] = {}
        self.net_rc_data: Dict[str, NetRCData] = {}
        self.vias: Dict[str, List[Via]] = {}
        
        # 结果存储
        self.violations: List[Violation] = []
        self.p2p_results: Dict[str, List[P2PResult]] = {}
        self.matching_results: List[MatchingAnalysis] = []
        self.em_results: List[EMResult] = []
        
        # 构建图结构用于P2P分析
        self.net_graphs: Dict[str, Dict] = {}
    
    def add_net_polygons(self, net_name: str, polygons: List[Polygon]):
        """添加net的多边形"""
        for poly in polygons:
            poly.net_name = net_name
        self.nets[net_name] = polygons
    
    def parse_polygons_to_wires(self, net_name: str) -> List[WireSegment]:
        """将多边形解析为走线段 - 用于RC计算。

        Args:
            net_name: net名称

        Returns:
            WireSegment列表，用于RC计算
        """
        polygons = self.nets.get(net_name, [])
        segments = []

        # 层类型别名映射：处理常见的命名差异
        # 例如 'metal1' -> 'met1', 'm1' -> 'met1'
        layer_aliases = {
            'metal1': 'met1', 'm1': 'met1',
            'metal2': 'met2', 'm2': 'met2',
            'metal3': 'met3', 'm3': 'met3',
            'metal4': 'met4', 'm4': 'met4',
            'metal5': 'met5', 'm5': 'met5',
            'metal6': 'met6', 'm6': 'met6',
            'metal7': 'met7', 'm7': 'met7',
        }

        for poly in polygons:
            layer_name = poly.layer.lower()
            resolved_layer = layer_aliases.get(layer_name, layer_name)

            # 获取层信息（尝试别名后的层名）
            layer_info = self.tech.layers.get(resolved_layer, {})

            # 如果仍然没有，尝试原始层名
            if not layer_info:
                layer_info = self.tech.layers.get(poly.layer, {})

            # 确定层的实际类型
            layer_type = layer_info.get('type', '')

            # 只处理metal层，但也要处理未定义的metal-like层
            # 对于未定义的层，假设它是metal（提供合理的默认值）
            if layer_type != 'metal':
                # 检查是否是未定义的metal层（通过别名或常见命名模式）
                is_likely_metal = (
                    resolved_layer.startswith('met') or
                    resolved_layer.startswith('m') and resolved_layer[1:].isdigit() or
                    layer_name in layer_aliases
                )

                if not is_likely_metal:
                    # 对于via、poly、active等非金属层，不提取为wire segment
                    continue

                # 对于未定义的metal-like层，使用默认参数
                layer_info = {
                    'type': 'metal',
                    'min_width': 0.032,
                    'resistance_per_sq': 0.15,
                    'capacitance_per_um': 0.20,
                }

            # 从多边形提取走线中心线
            points = poly.points
            if len(points) < 2:
                continue

            # 简化：对于矩形，提取中心线
            if poly.is_rectangular and len(points) >= 4:
                bbox = poly.bbox
                if poly.width > poly.height:
                    # 水平走线
                    y_center = (bbox[1] + bbox[3]) / 2
                    segment = WireSegment(
                        start=Point(bbox[0], y_center),
                        end=Point(bbox[2], y_center),
                        layer=poly.layer,
                        width=poly.height,
                        net_name=net_name
                    )
                else:
                    # 垂直走线
                    x_center = (bbox[0] + bbox[2]) / 2
                    segment = WireSegment(
                        start=Point(x_center, bbox[1]),
                        end=Point(x_center, bbox[3]),
                        layer=poly.layer,
                        width=poly.width,
                        net_name=net_name
                    )
                segments.append(segment)
            else:
                # 复杂多边形：提取边
                for i in range(len(points) - 1):
                    seg_length = points[i].distance_to(points[i+1])
                    if seg_length > 0.01:  # 忽略太短的边
                        # 估算宽度
                        width = poly.area / poly.perimeter * 2 if poly.perimeter > 0 else 0.032
                        segment = WireSegment(
                            start=points[i],
                            end=points[i+1],
                            layer=poly.layer,
                            width=max(width, layer_info.get('min_width', 0.032)),
                            net_name=net_name
                        )
                        segments.append(segment)

        return segments
    
    def calculate_net_rc(self, net_name: str) -> NetRCData:
        """计算net的RC参数。

        Args:
            net_name: net名称

        Returns:
            NetRCData包含RC计算结果
        """
        rc_data = NetRCData(net_name=net_name)
        polygons = self.nets.get(net_name, [])

        if not polygons:
            return rc_data

        # 解析为走线段
        wire_segments = self.parse_polygons_to_wires(net_name)
        rc_data.wire_segments = wire_segments

        # 层类型别名映射（与parse_polygons_to_wires保持一致）
        layer_aliases = {
            'metal1': 'met1', 'm1': 'met1',
            'metal2': 'met2', 'm2': 'met2',
            'metal3': 'met3', 'm3': 'met3',
            'metal4': 'met4', 'm4': 'met4',
            'metal5': 'met5', 'm5': 'met5',
            'metal6': 'met6', 'm6': 'met6',
            'metal7': 'met7', 'm7': 'met7',
        }

        # 计算每层的RC
        for segment in wire_segments:
            # 尝试解析层名（支持别名）
            layer_name = segment.layer.lower()
            resolved_layer = layer_aliases.get(layer_name, layer_name)

            # 获取层信息
            layer_info = self.tech.layers.get(resolved_layer, {})

            # 如果仍然没有，尝试原始层名
            if not layer_info:
                layer_info = self.tech.layers.get(segment.layer, {})

            # 如果仍然没有，使用默认参数
            if not layer_info:
                layer_info = {
                    'resistance_per_sq': 0.15,  # 默认值
                    'capacitance_per_um': 0.20,
                    'min_width': 0.032,
                }

            r_per_sq = layer_info.get('resistance_per_sq', 0.15)
            c_per_um = layer_info.get('capacitance_per_um', 0.20)
            
            # 电阻
            r = segment.resistance(r_per_sq)
            rc_data.total_resistance += r

            # 电容计算
            # 总电容 = 对地电容 + 耦合电容
            # 简化模型：假设70%是对地电容，30%是相邻走线耦合电容
            # 实际比例取决于走线密度、层间距、介电常数等
            # 这是FinFET工艺下的典型近似值（ITRS路线图数据）
            c = segment.capacitance(c_per_um)
            rc_data.total_capacitance += c
            rc_data.ground_capacitance += c * 0.7  # 70%对地 (典型值)
            rc_data.coupling_capacitance += c * 0.3  # 30%耦合 (典型值)

            # 层统计
            if segment.layer not in rc_data.layer_resistances:
                rc_data.layer_resistances[segment.layer] = 0
                rc_data.layer_capacitances[segment.layer] = 0
                rc_data.layer_usage[segment.layer] = 0
            
            rc_data.layer_resistances[segment.layer] += r
            rc_data.layer_capacitances[segment.layer] += c
            rc_data.layer_usage[segment.layer] += 1
            
            rc_data.total_length += segment.length
        
        # 添加通孔电阻
        for via in self.vias.get(net_name, []):
            rc_data.total_resistance += via.resistance
            rc_data.via_count += 1

        # 总面积
        rc_data.total_area = sum(p.area for p in polygons)

        # ============================================
        # 时序分析计算
        # ============================================
        self._calculate_timing_metrics(rc_data, polygons)

        self.net_rc_data[net_name] = rc_data
        return rc_data

    def _calculate_timing_metrics(self, rc_data: NetRCData, polygons: List[Polygon]):
        """计算时序指标：tau_rc, trise, tfall, tpd

        模型：
        - tau_rc = R * C (RC时间常数)
        - tpd_50% = 0.69 * (R_driver + 0.5 * R_wire) * (C_wire + C_load)
        - trise/tfall ≈ 2.2 * tau_rc (10%-90%上升/下降时间)

        如果存在poly/gate层作为后级负载，或S/D层作为前级驱动，
        会根据层类型估算R_driver和C_load。

        **单位说明**：R 单位是 Ω, C 单位是 fF。
        物理上 1 Ω·fF = 10⁻¹⁵ s = **1 ps**。
        因此 tau/tpd 字段直接以 ps 为单位,不需要再乘换算系数。
        (历史版本曾用 * 1e-9 把结果当作 ns,导致小 6 个数量级,显示为 0.000)

        Args:
            rc_data: NetRCData对象（会被直接修改）
            polygons: 该net的所有多边形
        """
        # 单位: R=Ω, C=fF, 结果=ps
        R_ohm = rc_data.total_resistance
        C_ff = rc_data.total_capacitance

        # 1. RC时间常数 tau_rc = R * C (单位: ps)
        rc_data.tau_rc = R_ohm * C_ff  # 1 Ω·fF = 1 ps

        # 2. 估算 R_driver 和 C_load
        # 如果存在 poly/gate 层，它们作为后级输入贡献 C_load
        # 如果存在 S/D/Source/Drain 层，它们作为前级输出贡献 R_driver

        c_load = 0.0   # fF
        r_driver = 0.0  # Ω

        for poly in polygons:
            layer_lower = poly.layer.lower()
            area = poly.area

            # Poly/Gate 层作为负载电容
            if 'poly' in layer_lower or 'gate' in layer_lower:
                # 典型栅极电容密度 (fF/μm²)
                c_gate_per_area = 0.10  # fF/μm² (10fF/100nm² 典型值)
                c_load += area * c_gate_per_area

            # S/D 层作为驱动
            if any(x in layer_lower for x in ['sd', 'source', 'drain', 'n_sd', 'p_sd']):
                # 典型S/D接触电阻 (Ω)
                r_contact_per_area = 5.0  # Ω/μm² (简化模型)
                r_driver += area * r_contact_per_area

        # 如果没有检测到显著的C_load，使用总电容的50%作为估算
        if c_load < C_ff * 0.1:
            c_load = C_ff * 0.5

        # 如果没有检测到显著的R_driver，使用线电阻的30%作为估算
        if r_driver < R_ohm * 0.1:
            r_driver = R_ohm * 0.3

        rc_data.c_load = c_load
        rc_data.r_driver = r_driver

        # 3. 传播延迟 tpd_50% (单位: ps)
        # tpd_50% ≈ 0.69 * (R_driver + 0.5 * R_wire) * (C_wire + C_load)
        C_total = C_ff + c_load  # fF
        R_total = r_driver + 0.5 * R_ohm  # Ω
        rc_data.tpd_50 = 0.69 * R_total * C_total  # 1 Ω·fF = 1 ps

        # 4. 上升/下降时间
        # trise/tfall ≈ 2.2 * tau_rc (对于 10%-90%)
        # 对于 0%-100% 上升时间，约 2.2 * tau_rc
        rc_data.trise = 2.2 * rc_data.tau_rc
        rc_data.tfall = 2.2 * rc_data.tau_rc
    
    def calculate_p2p_resistance(self, net_name: str,
                                  source: Point, target: Point) -> Optional[P2PResult]:
        """
        计算点到点电阻 - 使用Dijkstra图算法

        构建连通性图并使用Dijkstra算法找到最高电阻路径。
        这对于S/D到Gate的电阻分析很重要，可以识别EM风险最高的关键路径。

        Args:
            net_name: net名称
            source: 起点（通常是S/D接触点）
            target: 终点（通常是Gate poly）

        Returns:
            P2PResult包含完整路径信息和电阻值
        """
        rc_data = self.net_rc_data.get(net_name)
        if not rc_data:
            rc_data = self.calculate_net_rc(net_name)

        segments = rc_data.wire_segments
        if not segments:
            return None

        # 构建连通性图
        # 节点: (x, y)坐标
        # 边: (weight=电阻, segment=WireSegment)
        graph: Dict[Tuple[float, float], List[Tuple[float, Tuple[float, float], WireSegment]]] = defaultdict(list)

        def add_edge(p1: Point, p2: Point, seg: WireSegment, layer_info: Dict):
            """添加边到图中，包含电阻作为权重"""
            p1_key = (round(p1.x, 6), round(p1.y, 6))
            p2_key = (round(p2.x, 6), round(p2.y, 6))

            r_per_sq = layer_info.get('resistance_per_sq', 0.1)
            resistance = seg.resistance(r_per_sq)

            # 双向边
            graph[p1_key].append((resistance, p2_key, seg))
            graph[p2_key].append((resistance, p1_key, seg))

        # 添加所有线段到图中
        for seg in segments:
            layer_info = self.tech.layers.get(seg.layer, {})
            if layer_info:
                add_edge(seg.start, seg.end, seg, layer_info)

        # 添加via连接（via连接相同位置的上下层）
        for via in self.vias.get(net_name, []):
            via_key = (round(via.position.x, 6), round(via.position.y, 6))
            # Via电阻作为连接权重
            via_r = via.resistance
            # 在via位置添加自环（实际上via连接两层）
            graph[via_key].append((via_r, via_key, None))  # 自环

        if not graph:
            return None

        # 找到最近的节点到source和target
        source_key = self._find_closest_node(graph, source)
        target_key = self._find_closest_node(graph, target)

        if not source_key or not target_key:
            return None

        # 使用Dijkstra算法找到最高电阻路径
        # 通过将电阻取负来找到最大路径
        path, total_r, path_segments = self._dijkstra_max_path(graph, source_key, target_key)

        # 统计路径信息
        path_layers: Set[str] = set()
        via_count = 0
        for seg in path_segments:
            if seg:
                path_layers.add(seg.layer)
            via_count += 1  # 估算via数量

        # 找出瓶颈层（电阻最大的层）
        layer_resistances: Dict[str, float] = defaultdict(float)
        for seg in path_segments:
            if seg:
                layer_info = self.tech.layers.get(seg.layer, {})
                r_per_sq = layer_info.get('resistance_per_sq', 0.1)
                layer_resistances[seg.layer] += seg.resistance(r_per_sq)

        bottleneck_layer = max(layer_resistances, key=layer_resistances.get) if layer_resistances else None
        bottleneck_r = layer_resistances.get(bottleneck_layer, 0) if bottleneck_layer else 0

        # 计算路径总长度
        path_length = sum(seg.length for seg in path_segments if seg)

        result = P2PResult(
            net_name=net_name,
            source_point=source,
            target_point=target,
            resistance=total_r,
            path_length=path_length,
            path_layers=list(path_layers),
            via_count=via_count,
            bottleneck_layer=bottleneck_layer,
            bottleneck_resistance=bottleneck_r
        )

        if net_name not in self.p2p_results:
            self.p2p_results[net_name] = []
        self.p2p_results[net_name].append(result)

        return result

    def _find_closest_node(self, graph: Dict, point: Point) -> Optional[Tuple[float, float]]:
        """找到图中距离给定点的最近节点"""
        min_dist = float('inf')
        closest = None

        for node in graph.keys():
            dist = math.sqrt((node[0] - point.x) ** 2 + (node[1] - point.y) ** 2)
            if dist < min_dist:
                min_dist = dist
                closest = node

        return closest

    def _dijkstra_max_path(self, graph: Dict,
                           source: Tuple[float, float],
                           target: Tuple[float, float]) -> Tuple[List[Tuple[float, float]], float, List[Optional[WireSegment]]]:
        """
        使用修改的Dijkstra算法找到最高电阻路径。

        通过将边权重取负，可以直接使用最小优先级队列找到最大路径。

        Returns:
            (path_nodes, total_resistance, path_segments)
        """
        # 初始化: 使用负电阻表示我们想找最大路径
        dist: Dict[Tuple[float, float], float] = {source: 0.0}
        prev: Dict[Tuple[float, float], Optional[Tuple[float, float]]] = {source: None}
        prev_seg: Dict[Tuple[float, float], Optional[WireSegment]] = {source: None}

        # 优先队列: (-distance, node)
        pq = [(0.0, source)]
        visited: Set[Tuple[float, float]] = set()

        while pq:
            current_dist, u = heapq.heappop(pq)

            if u in visited:
                continue
            visited.add(u)

            # 到达目标
            if u == target:
                break

            # 遍历邻居（使用负距离，因为heapq是最小堆）
            for edge_weight, v, seg in graph.get(u, []):
                # 对于最大路径，我们使用负权重
                weight = -edge_weight
                new_dist = dist[u] + weight

                if v not in dist or new_dist > dist[v]:
                    dist[v] = new_dist
                    prev[v] = u
                    prev_seg[v] = seg
                    heapq.heappush(pq, (new_dist, v))

        # 重建路径
        if target not in prev:
            return [], 0.0, []

        path = []
        segments = []
        node = target
        while node is not None:
            path.append(node)
            segments.append(prev_seg.get(node))
            node = prev[node]

        path.reverse()
        segments.reverse()

        # 计算总电阻（取绝对值因为我们用了负权重）
        total_r = abs(dist.get(target, 0.0))

        return path, total_r, segments

    def analyze_p2p_for_sd_to_gate(self, net_name: str,
                                     sd_points: List[Point],
                                     gate_points: List[Point]) -> List[P2PResult]:
        """
        分析S/D点到Gate的最长电阻路径。

        用于SRAM单元的S/D到Gate电阻分析，
        识别EM和IR Drop风险最高的关键路径。

        Args:
            net_name: net名称
            sd_points: S/D接触点列表
            gate_points: Gate位置列表

        Returns:
            按电阻降序排列的P2P结果列表
        """
        results = []

        for sd in sd_points:
            for gate in gate_points:
                result = self.calculate_p2p_resistance(net_name, sd, gate)
                if result:
                    results.append(result)

        # 按电阻降序排列（最危险的路径在前）
        results.sort(key=lambda x: x.resistance, reverse=True)

        return results
    
    def analyze_em(self, net_name: str, estimated_current: float = None) -> List[EMResult]:
        """分析电迁移风险"""
        results = []
        rc_data = self.net_rc_data.get(net_name)
        if not rc_data:
            rc_data = self.calculate_net_rc(net_name)
        
        # 估算电流
        if estimated_current is None:
            # 基于net名称估算
            if any(kw in net_name.upper() for kw in ['VDD', 'VCC', 'PWR']):
                estimated_current = 50.0  # mA - 电源
            elif any(kw in net_name.upper() for kw in ['BL', 'BLB']):
                estimated_current = 5.0   # mA - 位线
            elif 'WL' in net_name.upper():
                estimated_current = 2.0   # mA - 字线
            else:
                estimated_current = 1.0   # mA - 信号
        
        for segment in rc_data.wire_segments:
            layer_info = self.tech.layers.get(segment.layer, {})
            if not layer_info:
                continue
            
            j_max = layer_info.get('current_density', 10.0)  # mA/μm
            width = segment.width
            
            if width > 0:
                current_density = estimated_current / width
                safety_factor = j_max / current_density if current_density > 0 else float('inf')
                
                em_violation = current_density > j_max * self.tech.design_rules.get('em_safety_factor', 0.8)
                
                result = EMResult(
                    net_name=net_name,
                    layer=segment.layer,
                    segment=segment,
                    max_current=estimated_current,
                    current_density=current_density,
                    safety_factor=safety_factor,
                    em_violation=em_violation,
                    violation_ratio=current_density / j_max if j_max > 0 else 0
                )
                results.append(result)
                self.em_results.append(result)
        
        return results
    
    def analyze_matching(self, net1: str, net2: str) -> MatchingAnalysis:
        """分析两个net的匹配度"""
        rc1 = self.net_rc_data.get(net1) or self.calculate_net_rc(net1)
        rc2 = self.net_rc_data.get(net2) or self.calculate_net_rc(net2)
        
        polygons1 = self.nets.get(net1, [])
        polygons2 = self.nets.get(net2, [])
        
        # 长度比
        length1 = rc1.total_length
        length2 = rc2.total_length
        length_ratio = length1 / length2 if length2 > 0 else 1.0
        
        # 电阻比
        r1 = rc1.total_resistance
        r2 = rc2.total_resistance
        resistance_ratio = r1 / r2 if r2 > 0 else 1.0
        
        # 电容比
        c1 = rc1.total_capacitance
        c2 = rc2.total_capacitance
        capacitance_ratio = c1 / c2 if c2 > 0 else 1.0
        
        # 通孔数差异
        via_diff = abs(rc1.via_count - rc2.via_count)
        
        # 层使用差异
        all_layers = set(rc1.layer_usage.keys()) | set(rc2.layer_usage.keys())
        layer_diff = {}
        for layer in all_layers:
            cnt1 = rc1.layer_usage.get(layer, 0)
            cnt2 = rc2.layer_usage.get(layer, 0)
            if cnt1 != cnt2:
                layer_diff[layer] = cnt2 - cnt1
        
        # 计算匹配分数
        score = 100.0
        issues = []
        suggestions = []
        
        # 长度匹配检查
        max_length_diff = max(length1, length2)
        if max_length_diff > 0:
            length_deviation = abs(length1 - length2) / max_length_diff
            if length_deviation > 0.05:  # 5%容差
                penalty = length_deviation * 30
                score -= penalty
                issues.append(f"Length mismatch: {abs(length1-length2):.1f}μm ({length_deviation*100:.1f}%)")
                suggestions.append("Balance wire lengths between matched nets")
        
        # 电阻匹配检查
        r_tolerance = self.tech.design_rules.get('max_rc_variation', 0.1)
        if abs(resistance_ratio - 1.0) > r_tolerance:
            score -= 20
            issues.append(f"Resistance mismatch: R1/R2 = {resistance_ratio:.2f}")
            suggestions.append("Ensure consistent resistance for matched signals")
        
        # 电容匹配检查
        if abs(capacitance_ratio - 1.0) > r_tolerance:
            score -= 15
            issues.append(f"Capacitance mismatch: C1/C2 = {capacitance_ratio:.2f}")
            suggestions.append("Balance capacitive loading")
        
        # 通孔数检查
        if via_diff > 1:
            score -= via_diff * 5
            issues.append(f"Via count difference: {via_diff}")
            suggestions.append("Match via count for symmetry")
        
        # 层使用检查
        if layer_diff:
            score -= len(layer_diff) * 3
            issues.append(f"Layer usage differs: {list(layer_diff.keys())}")
            suggestions.append("Use consistent layer assignments")
        
        score = max(0, min(100, score))
        
        # BBox相似度
        if polygons1 and polygons2:
            bbox1 = self._get_overall_bbox(polygons1)
            bbox2 = self._get_overall_bbox(polygons2)
            bbox_sim = self._calculate_bbox_similarity(bbox1, bbox2)
        else:
            bbox_sim = 0.5
        
        # 质心距离
        if polygons1 and polygons2:
            c1 = self._calculate_centroid(polygons1)
            c2 = self._calculate_centroid(polygons2)
            centroid_dist = c1.distance_to(c2)
        else:
            centroid_dist = 0
        
        analysis = MatchingAnalysis(
            net1=net1,
            net2=net2,
            match_score=score,
            length_ratio=length_ratio,
            resistance_ratio=resistance_ratio,
            capacitance_ratio=capacitance_ratio,
            via_count_diff=via_diff,
            layer_usage_diff=layer_diff,
            bbox_similarity=bbox_sim,
            centroid_distance=centroid_dist,
            routing_pattern_similarity=0.8 if score > 70 else 0.5,
            issues=issues,
            suggestions=suggestions
        )
        
        self.matching_results.append(analysis)
        return analysis
    
    def _get_overall_bbox(self, polygons: List[Polygon]) -> Tuple[float, float, float, float]:
        """获取多边形集合的整体bbox"""
        if not polygons:
            return (0, 0, 0, 0)
        xmins, ymins, xmaxs, ymaxs = zip(*[p.bbox for p in polygons])
        return (min(xmins), min(ymins), max(xmaxs), max(ymaxs))
    
    def _calculate_centroid(self, polygons: List[Polygon]) -> Point:
        """计算多边形集合的质心"""
        if not polygons:
            return Point(0, 0)
        total_area = sum(p.area for p in polygons)
        if total_area == 0:
            centers = [p.center for p in polygons]
            return Point(
                sum(c.x for c in centers) / len(centers),
                sum(c.y for c in centers) / len(centers)
            )
        cx = sum(p.center.x * p.area for p in polygons) / total_area
        cy = sum(p.center.y * p.area for p in polygons) / total_area
        return Point(cx, cy)

    def _min_polygon_distance(self, poly1: Polygon, poly2: Polygon) -> float:
        """计算两个多边形之间的最小距离。

        使用bbox近似 + 精确边距离计算的混合方法：
        1. 先用bbox快速排除不相近的多边形
        2. 对可能接近的多边形计算精确的边-边距离

        Args:
            poly1: 第一个多边形
            poly2: 第二个多边形

        Returns:
            两个多边形之间的最小距离 (μm)
        """
        b1 = poly1.bbox
        b2 = poly2.bbox

        # 快速检查：基于bbox完全分离的情况
        # 如果bbox不相交（分离），计算它们之间的最小距离
        if b1[2] < b2[0] or b2[2] < b1[0] or b1[3] < b2[1] or b2[3] < b1[1]:
            # bbox在X方向分离
            if b1[2] < b2[0] or b2[2] < b1[0]:
                gap_x = max(b1[0] - b2[2], b2[0] - b1[2], 0)
            else:
                gap_x = 0

            # bbox在Y方向分离
            if b1[3] < b2[1] or b2[3] < b1[1]:
                gap_y = max(b1[1] - b2[3], b2[1] - b1[3], 0)
            else:
                gap_y = 0

            if gap_x > 0 and gap_y > 0:
                return math.sqrt(gap_x * gap_x + gap_y * gap_y)
            elif gap_x > 0:
                return gap_x
            elif gap_y > 0:
                return gap_y
            else:
                return 0.0

        # bbox相交或重叠：计算精确的边-边最小距离
        min_dist = float('inf')

        def segment_to_segment_dist(p1: Point, p2: Point, p3: Point, p4: Point) -> float:
            """计算两条线段之间的最小距离"""
            # 使用变量消除算法求两条线段之间的最短距离
            d1 = self._point_to_segment_distance(p1, p2, p3)
            d2 = self._point_to_segment_distance(p1, p2, p4)
            d3 = self._point_to_segment_distance(p3, p4, p1)
            d4 = self._point_to_segment_distance(p3, p4, p2)
            return min(d1, d2, d3, d4)

        # 检查所有边对之间的距离
        pts1 = poly1.points
        pts2 = poly2.points

        for i in range(len(pts1)):
            p1 = pts1[i]
            p2 = pts1[(i + 1) % len(pts1)]

            for j in range(len(pts2)):
                p3 = pts2[j]
                p4 = pts2[(j + 1) % len(pts2)]

                dist = segment_to_segment_dist(p1, p2, p3, p4)
                min_dist = min(min_dist, dist)

        return min_dist if min_dist < float('inf') else 0.0

    def _point_to_segment_distance(self, seg_start: Point, seg_end: Point, point: Point) -> float:
        """计算点到线段的最小距离。

        Args:
            seg_start: 线段起点
            seg_end: 线段终点
            point: 待测点

        Returns:
            点到线段的最小距离
        """
        # 向量 seg_start -> seg_end
        dx = seg_end.x - seg_start.x
        dy = seg_end.y - seg_start.y

        # 向量 seg_start -> point
        px = point.x - seg_start.x
        py = point.y - seg_start.y

        seg_len_sq = dx * dx + dy * dy

        if seg_len_sq < 1e-10:
            # 线段退化为点
            return math.sqrt(px * px + py * py)

        # 投影比例 t (在线段上的位置)
        t = max(0, min(1, (px * dx + py * dy) / seg_len_sq))

        # 最近点在线段上的位置
        nearest_x = seg_start.x + t * dx
        nearest_y = seg_start.y + t * dy

        # 计算距离
        dist_x = point.x - nearest_x
        dist_y = point.y - nearest_y

        return math.sqrt(dist_x * dist_x + dist_y * dist_y)

    def _calculate_bbox_similarity(self, bbox1: Tuple, bbox2: Tuple) -> float:
        """计算两个bbox的相似度"""
        w1 = bbox1[2] - bbox1[0]
        h1 = bbox1[3] - bbox1[1]
        w2 = bbox2[2] - bbox2[0]
        h2 = bbox2[3] - bbox2[1]
        
        if w1 + h1 == 0 or w2 + h2 == 0:
            return 0.5
        
        # 尺寸相似度
        size_sim = 1.0 - abs((w1+h1) - (w2+h2)) / max(w1+h1, w2+h2)
        
        # 长宽比相似度
        ar1 = w1 / h1 if h1 > 0 else 1
        ar2 = w2 / h2 if h2 > 0 else 1
        ar_sim = 1.0 - abs(ar1 - ar2) / max(ar1, ar2, 1)
        
        return (size_sim + ar_sim) / 2
    
    def run_full_review(self) -> ReviewSummary:
        """运行完整Review"""
        print("=" * 60)
        print("Professional Layout Review Engine")
        print("=" * 60)
        
        self.violations = []
        self.matching_results = []
        self.em_results = []
        
        # 1. 计算所有net的RC
        print("\n[Phase 1] Calculating RC for all nets...")
        for net_name in self.nets:
            self.calculate_net_rc(net_name)
        print(f"  [OK] Processed {len(self.nets)} nets")
        
        # 2. 运行检查规则
        print("\n[Phase 2] Running check rules...")
        self._run_all_checks()
        
        # 3. 分析匹配对
        print("\n[Phase 3] Analyzing matching pairs...")
        self._analyze_all_matching_pairs()
        
        # 4. EM分析
        print("\n[Phase 4] Running EM analysis...")
        self._run_em_analysis()
        
        # 5. 生成汇总
        print("\n[Phase 5] Generating summary...")
        summary = self._generate_summary()
        
        print("\n" + "=" * 60)
        print("Review Complete!")
        print("=" * 60)
        self._print_summary(summary)
        
        return summary
    
    def _run_all_checks(self):
        """运行所有启用的检查规则"""
        enabled_rules = self.config.get_enabled_rules()
        
        for net_name in self.nets:
            applicable_rules = self.config.get_rules_for_net(net_name)
            
            for rule in applicable_rules:
                self._execute_check_rule(net_name, rule)
    
    def _execute_check_rule(self, net_name: str, rule: CheckRule):
        """执行单个检查规则"""
        rc_data = self.net_rc_data.get(net_name)
        polygons = self.nets.get(net_name, [])
        
        # DRC001: Minimum Width
        if rule.rule_id == "DRC001":
            for poly in polygons:
                layer_info = self.tech.layers.get(poly.layer, {})
                min_width = layer_info.get('min_width', 0.032)
                actual_width = min(poly.width, poly.height)
                if actual_width < min_width * 0.95:
                    self._add_violation(rule, net_name, 
                        f"Width violation on {poly.layer}: {actual_width:.4f}μm < {min_width}μm",
                        poly.center, [poly])
        
        # SI001: Long Wire
        elif rule.rule_id == "SI001":
            max_lengths = rule.parameters
            for segment in rc_data.wire_segments:
                # Extract trailing number from layer name using regex
                # Handles: 'met1', 'met2', 'metal1', 'm1', 'via0', 'via1', etc.
                layer_num = _extract_layer_number(segment.layer)

                if layer_num <= 2:
                    max_len = max_lengths.get('max_length_met12', 100)
                elif layer_num <= 4:
                    max_len = max_lengths.get('max_length_met34', 200)
                else:
                    max_len = max_lengths.get('max_length_met56', 300)
                
                if segment.length > max_len:
                    self._add_violation(rule, net_name,
                        f"Long wire on {segment.layer}: {segment.length:.1f}μm (max {max_len}μm)",
                        segment.start, wire_segments=[segment])
        
        # SI002: High Resistance
        elif rule.rule_id == "SI002":
            max_r = rule.parameters.get('max_resistance', 100)
            if rc_data.total_resistance > max_r:
                self._add_violation(rule, net_name,
                    f"High resistance: {rc_data.total_resistance:.1f}Ω (max {max_r}Ω)",
                    related_data={'resistance': rc_data.total_resistance})
        
        # SI003: High Capacitance
        elif rule.rule_id == "SI003":
            max_c = rule.parameters.get('max_capacitance', 500)
            if rc_data.total_capacitance > max_c:
                self._add_violation(rule, net_name,
                    f"High capacitance: {rc_data.total_capacitance:.1f}fF (max {max_c}fF)",
                    related_data={'capacitance': rc_data.total_capacitance})
        
        # EM002: Power Net Width
        elif rule.rule_id == "EM002":
            min_width = rule.parameters.get('min_power_width', 0.5)
            for segment in rc_data.wire_segments:
                if segment.width < min_width and segment.length > 10:
                    self._add_violation(rule, net_name,
                        f"Power net narrow segment: {segment.width:.3f}μm on {segment.layer}",
                        segment.start, wire_segments=[segment])
        
        # QTY004: Narrow Long Wire
        elif rule.rule_id == "QTY004":
            params = rule.parameters
            length_thresh = params.get('length_threshold', 100)
            width_thresh = params.get('width_threshold', 0.05)
            ar_thresh = params.get('aspect_ratio_threshold', 100)

            for segment in rc_data.wire_segments:
                if segment.length > length_thresh and segment.width < width_thresh:
                    ar = segment.length / segment.width if segment.width > 0 else 0
                    if ar > ar_thresh:
                        self._add_violation(rule, net_name,
                            f"Narrow long wire: {segment.length:.1f}μm x {segment.width:.3f}μm (AR={ar:.0f})",
                            segment.start, wire_segments=[segment])

        # DRC002: Minimum Space Violation
        # 检查同层多边形之间的间距是否满足最小间距要求
        elif rule.rule_id == "DRC002":
            layer_polys = defaultdict(list)
            for poly in polygons:
                layer_polys[poly.layer].append(poly)

            for layer, polys_on_layer in layer_polys.items():
                if len(polys_on_layer) < 2:
                    continue
                layer_info = self.tech.layers.get(layer, {})
                min_space = layer_info.get('min_space', 0.032)

                # 检查所有多边形对之间的间距
                for i in range(len(polys_on_layer)):
                    for j in range(i + 1, len(polys_on_layer)):
                        min_dist = self._min_polygon_distance(polys_on_layer[i], polys_on_layer[j])
                        if min_dist < min_space:
                            center = polys_on_layer[i].center
                            self._add_violation(rule, net_name,
                                f"Space violation on {layer}: {min_dist:.4f}μm < {min_space}μm",
                                center, polygons=[polys_on_layer[i], polys_on_layer[j]])

        # DRC003: Missing Via Detection
        # 检查相邻金属层重叠区域是否存在通孔
        elif rule.rule_id == "DRC003":
            overlap_threshold = rule.parameters.get('overlap_threshold', 0.1)

            # 按层分组polygons
            layer_polygons: Dict[str, List[Polygon]] = defaultdict(list)
            for poly in polygons:
                layer_polygons[poly.layer].append(poly)

            # 定义相邻层对（基于工艺顺序）
            adjacent_layer_pairs = [
                ('met1', 'met2'), ('met2', 'met3'), ('met3', 'met4'),
                ('met4', 'met5'), ('met5', 'met6'), ('met6', 'met7'),
            ]

            # 获取该net的via位置列表
            net_vias = self.vias.get(net_name, [])
            via_positions = set()
            for via in net_vias:
                via_positions.add((round(via.position.x, 4), round(via.position.y, 4)))

            # 检查每对相邻层
            for layer1, layer2 in adjacent_layer_pairs:
                polys1 = layer_polygons.get(layer1, [])
                polys2 = layer_polygons.get(layer2, [])

                if not polys1 or not polys2:
                    continue

                # 查找重叠区域
                for poly1 in polys1:
                    for poly2 in polys2:
                        if poly1.intersects(poly2):
                            overlap = poly1.overlap_area(poly2)
                            if overlap >= overlap_threshold:
                                # 检查重叠区域是否有via
                                # 通过检查via位置是否在重叠区域来验证
                                has_via = False
                                center1 = poly1.center
                                center2 = poly2.center

                                # 检查两个层的via
                                for via in net_vias:
                                    # 检查via是否在重叠区域附近
                                    via_key = (round(via.position.x, 4), round(via.position.y, 4))
                                    # 简单检查：via位置是否在两个polygon的中心连线附近
                                    if abs(via.position.x - center1.x) < abs(center1.x - center2.x) * 0.5 and \
                                       abs(via.position.y - center1.y) < abs(center1.y - center2.y) * 0.5:
                                        has_via = True
                                        break

                                if not has_via and overlap > overlap_threshold:
                                    self._add_violation(rule, net_name,
                                        f"Missing via between {layer1} and {layer2}: overlap area {overlap:.3f}μm²",
                                        poly1.center, polygons=[poly1, poly2],
                                        related_data={'overlap_area': overlap, 'layers': [layer1, layer2]})

            # 额外检查：高电阻via
            for via in net_vias:
                if via.resistance > 10.0:
                    self._add_violation(rule, net_name,
                        f"High via resistance detected: {via.resistance:.1f}Ω on {via.layer}",
                        via.position, related_data={'via_resistance': via.resistance})

        # EM003: Via Current Capacity
        # 检查通孔阵列尺寸是否满足电流承载需求
        elif rule.rule_id == "EM003":
            min_via_array_size = rule.parameters.get('min_via_array_size', 2)

            # 估算通过该net的电流（基于net类型）
            if any(kw in net_name.upper() for kw in ['VDD', 'VSS', 'PWR']):
                estimated_current = 50.0  # mA for power nets
            elif any(kw in net_name.upper() for kw in ['BL', 'BLB']):
                estimated_current = 5.0
            else:
                estimated_current = 1.0

            # 检查via电流容量
            for via in self.vias.get(net_name, []):
                layer_info = self.tech.layers.get(via.layer, {})
                via_current_capacity = layer_info.get('current_capacity', 50.0)

                if estimated_current > via_current_capacity:
                    self._add_violation(rule, net_name,
                        f"Via current capacity insufficient: {estimated_current:.1f}mA > {via_current_capacity:.1f}mA on {via.layer}",
                        via.position, related_data={'current': estimated_current, 'capacity': via_current_capacity})

    def _add_violation(self, rule: CheckRule, net_name: str, message: str,
                       location: Point = None, polygons: List[Polygon] = None,
                       wire_segments: List[WireSegment] = None, related_data: Dict = None):
        """添加违规项"""
        violation = Violation(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            type=rule.rule_id.split('_')[0] if '_' in rule.rule_id else 'GENERAL',
            severity=rule.severity,
            net_name=net_name,
            message=message,
            location=location,
            polygons=polygons or [],
            wire_segments=wire_segments or [],
            suggestion=rule.suggestion,
            reference=rule.reference,
            related_data=related_data or {}
        )
        self.violations.append(violation)
    
    def _analyze_all_matching_pairs(self):
        """分析所有匹配对"""
        net_names = list(self.nets.keys())
        
        # 位线对
        bl_nets = sorted([n for n in net_names if 'BL' in n.upper() and 'BLB' not in n.upper()])
        for bl in bl_nets:
            # 找对应的BLB
            blb_candidates = [n for n in net_names if 'BLB' in n.upper()]
            # 简单的命名匹配
            for blb in blb_candidates:
                if bl.replace('BL', '').replace('bl', '') == blb.replace('BLB', '').replace('blb', ''):
                    self.analyze_matching(bl, blb)
                    break
        
        # 字线
        wl_nets = sorted([n for n in net_names if re.search(r'WL\d+', n, re.I)])
        for i in range(len(wl_nets) - 1):
            self.analyze_matching(wl_nets[i], wl_nets[i+1])
    
    def _run_em_analysis(self):
        """对所有电源net运行EM分析"""
        for net_name in self.nets:
            if any(kw in net_name.upper() for kw in ['VDD', 'VSS', 'PWR']):
                self.analyze_em(net_name)
    
    def _generate_summary(self) -> ReviewSummary:
        """生成Review汇总"""
        summary = ReviewSummary()
        summary.total_nets = len(self.nets)
        summary.total_violations = len(self.violations)
        summary.critical_count = len([v for v in self.violations if v.severity == Severity.CRITICAL])
        summary.warning_count = len([v for v in self.violations if v.severity == Severity.WARNING])
        summary.info_count = len([v for v in self.violations if v.severity == Severity.INFO])
        
        # RC统计
        resistances = [rc.total_resistance for rc in self.net_rc_data.values()]
        capacitances = [rc.total_capacitance for rc in self.net_rc_data.values()]
        
        if resistances:
            summary.total_resistance_range = (min(resistances), max(resistances))
            summary.avg_resistance = sum(resistances) / len(resistances)
        
        if capacitances:
            summary.total_capacitance_range = (min(capacitances), max(capacitances))
            summary.avg_capacitance = sum(capacitances) / len(capacitances)
        
        # 匹配分析
        summary.matching_pairs_analyzed = len(self.matching_results)
        summary.poor_matching_count = len([m for m in self.matching_results if m.match_score < 70])
        
        # 层使用统计
        for rc in self.net_rc_data.values():
            for layer, count in rc.layer_usage.items():
                if layer not in summary.layer_usage:
                    summary.layer_usage[layer] = 0
                summary.layer_usage[layer] += count
        
        # 违规分类
        for v in self.violations:
            if v.type not in summary.violations_by_type:
                summary.violations_by_type[v.type] = 0
            summary.violations_by_type[v.type] += 1
            
            if v.net_name not in summary.violations_by_net:
                summary.violations_by_net[v.net_name] = 0
            summary.violations_by_net[v.net_name] += 1
            
            if v.rule_id not in summary.rules_triggered:
                summary.rules_triggered[v.rule_id] = 0
            summary.rules_triggered[v.rule_id] += 1
        
        return summary
    
    def _print_summary(self, summary: ReviewSummary):
        """打印汇总"""
        print(f"\nTotal Nets: {summary.total_nets}")
        print(f"Violations: {summary.total_violations}")
        print(f"  Critical: {summary.critical_count}")
        print(f"  Warning:  {summary.warning_count}")
        print(f"  Info:     {summary.info_count}")
        print(f"\nRC Summary:")
        print(f"  Resistance range: {summary.total_resistance_range[0]:.1f} - {summary.total_resistance_range[1]:.1f} Ω")
        print(f"  Average R: {summary.avg_resistance:.1f} Ω")
        print(f"  Capacitance range: {summary.total_capacitance_range[0]:.1f} - {summary.total_capacitance_range[1]:.1f} fF")
        print(f"  Average C: {summary.avg_capacitance:.1f} fF")
        print(f"\nMatching Analysis:")
        print(f"  Pairs analyzed: {summary.matching_pairs_analyzed}")
        print(f"  Poor matching: {summary.poor_matching_count}")
    
    def get_net_info_table(self) -> List[Dict]:
        """获取Net信息表格数据"""
        table_data = []

        for net_name, rc_data in self.net_rc_data.items():
            row = {
                'Net Name': net_name,
                'Total R (Ω)': round(rc_data.total_resistance, 2),
                'Total C (fF)': round(rc_data.total_capacitance, 2),
                'Length (μm)': round(rc_data.total_length, 1),
                'Area (μm²)': round(rc_data.total_area, 2),
                'Via Count': rc_data.via_count,
                'Layer Count': len(rc_data.layer_usage),
                'Layers Used': ', '.join(rc_data.layer_usage.keys()),
                # 时序分析 (单位: ps; 1 Ω·fF = 1 ps)
                'tau_rc (ps)': round(rc_data.tau_rc, 4),
                'tpd_50% (ps)': round(rc_data.tpd_50, 4),
                'trise (ps)': round(rc_data.trise, 4),
                'tfall (ps)': round(rc_data.tfall, 4),
            }

            # 添加每层细节
            for layer, r in rc_data.layer_resistances.items():
                row[f'{layer}_R'] = round(r, 2)
            for layer, c in rc_data.layer_capacitances.items():
                row[f'{layer}_C'] = round(c, 2)

            # 添加违规计数
            violation_count = len([v for v in self.violations if v.net_name == net_name])
            row['Violations'] = violation_count

            table_data.append(row)

        return table_data


# ============================================================================
# 便捷函数
# ============================================================================

import re


def _extract_layer_number(layer_name: str) -> int:
    """Extract layer number from layer name using robust regex.

    Handles patterns like:
    - 'met1', 'met2', 'metal1', 'metal2' -> 1, 2
    - 'via0', 'via1', 'via2' -> 0, 1, 2
    - 'm1', 'm2' -> 1, 2
    - 'poly', 'active' (no number) -> 0 as default

    Args:
        layer_name: Layer name string

    Returns:
        Layer number as integer, defaults to 0 if no number found
    """
    if not layer_name:
        return 0

    layer_lower = layer_name.lower()

    # Pattern to find trailing digits: met1, metal1, via1, m1, etc.
    # Matches: optional prefix (met/metal/via/m) followed by digits at end
    patterns = [
        r'met(\d+)$',      # met1, met2
        r'metal(\d+)$',   # metal1, metal2
        r'via(\d+)$',     # via0, via1
        r'^(\d+)$',       # just a number
    ]

    for pattern in patterns:
        match = re.search(pattern, layer_lower)
        if match:
            return int(match.group(1))

    # Fallback: try to find ANY digits in the string
    digits_match = re.search(r'(\d+)', layer_lower)
    if digits_match:
        return int(digits_match.group(1))

    return 0  # Default for layers without numbers (poly, active, etc.)


def create_engine(config: LayoutReviewConfig = None) -> ProfessionalLayoutReviewEngine:
    """创建Review引擎"""
    return ProfessionalLayoutReviewEngine(config)


if __name__ == '__main__':
    print("Professional Layout Review Engine")
    print("=" * 60)
    
    # 创建引擎
    engine = create_engine()
    
    # 打印配置信息
    print(f"\nTech: {engine.tech.name} ({engine.tech.node})")
    print(f"Rules: {len(engine.config.check_rules)} configured")
    print(f"Enabled: {len(engine.config.get_enabled_rules())} enabled")
    
    print("\n[OK] Engine initialized successfully!")
