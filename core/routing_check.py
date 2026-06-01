#!/usr/bin/env python3
"""
Routing Check Engine - 路由检查引擎

检查芯片走线的路由特性是否符合设计规范，包括：
1. 方向路由占比计算 (X/Y方向)
2. 最长线段识别
3. RC时间常数(Tau)计算
4. 违规判定

★ Insight ─────────────────────────────────────
路由方向分析对于高速信号线至关重要：
- 水平/垂直走线比例失衡会导致信号延迟不匹配
- 过长线段会产生EM/IR Drop问题
- Tau超限会直接影响时序收敛
`─────────────────────────────────────────────────`
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum

from review_engine import Point, Polygon, WireSegment, Via, NetRCData


# ============================================================================
# 枚举定义
# ============================================================================

class CheckStatus(Enum):
    """检查状态枚举"""
    PASS = "PASS"      # 通过
    FAIL = "FAIL"      # 失败
    WARNING = "WARNING"  # 警告


class ViolationType(Enum):
    """违规类型枚举"""
    ROUTING_RATIO_X = "ROUTING_RATIO_X"      # X方向路由占比超限
    ROUTING_RATIO_Y = "ROUTING_RATIO_Y"      # Y方向路由占比超限
    MAX_SEGMENT_LENGTH = "MAX_SEGMENT_LENGTH"  # 最长线段超限
    TAU_THRESHOLD = "TAU_THRESHOLD"          # Tau超限


# ============================================================================
# 配置数据类
# ============================================================================

@dataclass
class RoutingCheckConfig:
    """路由检查配置类

    Attributes:
        fullchip_x: 全芯片X方向尺寸 (μm)
        fullchip_y: 全芯片Y方向尺寸 (μm)
        tau_threshold: Tau阈值 (ns)
        routing_ratio_x: X方向路由占比阈值 (0-1)
        routing_ratio_y: Y方向路由占比阈值 (0-1)
        max_segment_length: 最大线段长度阈值 (μm)
        strict_mode: 严格模式 (在严格模式下，WARNING也会被视为FAIL)
    """
    fullchip_x: float = 1000.0       # 默认1000μm (1mm)
    fullchip_y: float = 1000.0       # 默认1000μm (1mm)
    tau_threshold: float = 1.0       # 默认1ns阈值
    routing_ratio_x: float = 0.8     # 默认80%阈值
    routing_ratio_y: float = 0.8    # 默认80%阈值
    max_segment_length: float = 500.0  # 默认500μm阈值
    strict_mode: bool = False        # 默认非严格模式

    def __post_init__(self):
        """参数验证"""
        # 确保阈值在有效范围内
        self.routing_ratio_x = max(0.0, min(1.0, self.routing_ratio_x))
        self.routing_ratio_y = max(0.0, min(1.0, self.routing_ratio_y))


# ============================================================================
# 结果数据类
# ============================================================================

@dataclass
class Violation:
    """违规项

    Attributes:
        type: 违规类型
        message: 违规消息
        severity: 严重程度 (CRITICAL/WARNING/INFO)
        value: 实际值
        threshold: 阈值
    """
    type: ViolationType
    message: str
    severity: str = "WARNING"
    value: float = 0.0
    threshold: float = 0.0


@dataclass
class RoutingCheckResult:
    """路由检查结果数据类

    Attributes:
        net_name: 网络名称
        avg_x_ratio: X方向平均路由占比 (0-1)
        avg_y_ratio: Y方向平均路由占比 (0-1)
        max_segment_length: 最长线段长度 (μm)
        max_segment_layer: 最长线段所在层
        total_resistance: 总电阻 (Ω)
        total_capacitance: 总电容 (fF)
        tau: RC时间常数 (ns) = R × C × 1e-9
        status: PASS/FAIL/WARNING
        violations: 违规列表
    """
    net_name: str
    avg_x_ratio: float = 0.0
    avg_y_ratio: float = 0.0
    max_segment_length: float = 0.0
    max_segment_layer: str = ""
    total_resistance: float = 0.0
    total_capacitance: float = 0.0
    tau: float = 0.0
    status: CheckStatus = CheckStatus.PASS
    violations: List[Violation] = field(default_factory=list)

    @property
    def is_pass(self) -> bool:
        """检查是否通过"""
        return self.status == CheckStatus.PASS

    @property
    def is_fail(self) -> bool:
        """检查是否失败"""
        return self.status == CheckStatus.FAIL

    @property
    def violation_count(self) -> int:
        """违规数量"""
        return len(self.violations)

    def get_violation_summary(self) -> str:
        """获取违规摘要"""
        if not self.violations:
            return "No violations"
        lines = [f"{len(self.violations)} violation(s) found:"]
        for v in self.violations:
            lines.append(f"  - [{v.type.value}] {v.message}")
        return "\n".join(lines)


# ============================================================================
# 路由检查引擎
# ============================================================================

class RoutingCheckEngine:
    """路由检查引擎

    提供路由特性检查功能，包括方向分析、长度分析和RC时序分析。
    """

    def __init__(self, config: Optional[RoutingCheckConfig] = None):
        """初始化路由检查引擎

        Args:
            config: 路由检查配置，如果为None则使用默认配置
        """
        self.config = config or RoutingCheckConfig()

    def check_routing(
        self,
        net_name: str,
        polygons: List[Polygon],
        rc_data: Optional[NetRCData] = None,
        wire_segments: Optional[List[WireSegment]] = None
    ) -> RoutingCheckResult:
        """执行路由检查

        Args:
            net_name: 网络名称
            polygons: 多边形列表
            rc_data: RC数据（可选）
            wire_segments: 走线段列表（可选）

        Returns:
            RoutingCheckResult 检查结果
        """
        result = RoutingCheckResult(net_name=net_name)

        # 如果没有提供wire_segments，从polygons解析
        if wire_segments is None:
            wire_segments = self._parse_polygons_to_segments(polygons, net_name)

        if not wire_segments:
            # 空路由
            result.status = CheckStatus.WARNING
            result.violations.append(Violation(
                type=ViolationType.MAX_SEGMENT_LENGTH,
                message="Empty routing - no wire segments found",
                severity="WARNING",
                value=0.0,
                threshold=0.0
            ))
            return result

        # 1. 计算方向路由占比
        x_total, y_total = self._calculate_routing_ratios(wire_segments)

        if x_total + y_total > 0:
            result.avg_x_ratio = x_total / (x_total + y_total)
            result.avg_y_ratio = y_total / (x_total + y_total)
        else:
            result.avg_x_ratio = 0.0
            result.avg_y_ratio = 0.0

        # 2. 识别最长线段
        result.max_segment_length, result.max_segment_layer = self._find_longest_segment(wire_segments)

        # 3. 获取RC数据
        if rc_data:
            result.total_resistance = rc_data.total_resistance
            result.total_capacitance = rc_data.total_capacitance
            result.tau = self._calculate_tau(rc_data.total_resistance, rc_data.total_capacitance)
        else:
            # 估算RC
            result.total_resistance = sum(seg.resistance(0.15) for seg in wire_segments)
            result.total_capacitance = sum(seg.capacitance(0.20) for seg in wire_segments)
            result.tau = self._calculate_tau(result.total_resistance, result.total_capacitance)

        # 4. 违规判定
        violations = self._check_violations(result)
        result.violations = violations

        # 5. 确定最终状态
        result.status = self._determine_status(violations)

        return result

    def _parse_polygons_to_segments(
        self,
        polygons: List[Polygon],
        net_name: str
    ) -> List[WireSegment]:
        """将多边形解析为走线段

        Args:
            polygons: 多边形列表
            net_name: 网络名称

        Returns:
            WireSegment列表
        """
        segments = []

        for poly in polygons:
            # 检查是否是metal层
            layer_name = poly.layer.lower()
            is_metal = (
                layer_name.startswith('met') or
                layer_name.startswith('m') and layer_name[1:].isdigit() or
                'metal' in layer_name
            )

            if not is_metal:
                continue

            points = poly.points
            if len(points) < 2:
                continue

            # 估算宽度
            width = poly.area / poly.perimeter * 2 if poly.perimeter > 0 else 0.032
            width = max(width, 0.032)

            # 提取边线段
            for i in range(len(points) - 1):
                seg_length = points[i].distance_to(points[i + 1])
                if seg_length > 0.01:  # 忽略太短的边
                    segment = WireSegment(
                        start=points[i],
                        end=points[i + 1],
                        layer=poly.layer,
                        width=width,
                        net_name=net_name
                    )
                    segments.append(segment)

        return segments

    def _calculate_routing_ratios(
        self,
        segments: List[WireSegment]
    ) -> Tuple[float, float]:
        """计算方向路由占比

        算法说明：
        - 对于每个线段，计算其Δx和Δy
        - 根据主方向将线段长度分配到X_total或Y_total
        - avg_x_ratio = X_total / (X_total + Y_total)
        - avg_y_ratio = Y_total / (X_total + Y_total)

        Args:
            segments: 走线段列表

        Returns:
            (X_total, Y_total) 元组
        """
        x_total = 0.0
        y_total = 0.0

        for seg in segments:
            dx = abs(seg.end.x - seg.start.x)
            dy = abs(seg.end.y - seg.start.y)
            length = seg.length

            if length < 1e-10:
                continue

            # 根据主方向分配
            if dx >= dy:
                # 主要在X方向
                x_total += length
            else:
                # 主要在Y方向
                y_total += length

        return (x_total, y_total)

    def _find_longest_segment(
        self,
        segments: List[WireSegment]
    ) -> Tuple[float, str]:
        """识别最长线段

        Args:
            segments: 走线段列表

        Returns:
            (最大长度, 所在层) 元组
        """
        if not segments:
            return 0.0, ""

        max_length = 0.0
        max_layer = ""

        for seg in segments:
            if seg.length > max_length:
                max_length = seg.length
                max_layer = seg.layer

        return max_length, max_layer

    def _calculate_tau(self, resistance: float, capacitance: float) -> float:
        """计算RC时间常数

        Tau计算公式：
        τ = R × C × 1e-9 (ns)
        从 Ω*fF 转换为 ns

        Args:
            resistance: 电阻 (Ω)
            capacitance: 电容 (fF)

        Returns:
            Tau值 (ns)
        """
        return resistance * capacitance * 1e-9

    def _check_violations(self, result: RoutingCheckResult) -> List[Violation]:
        """检查违规项

        违规判定规则：
        - avg_x_ratio > routing_ratio_x → FAIL
        - avg_y_ratio > routing_ratio_y → FAIL
        - max_segment_length > max_segment_threshold → WARNING
        - tau > tau_threshold → FAIL

        Args:
            result: 路由检查结果

        Returns:
            违规列表
        """
        violations = []

        # X方向路由占比超限
        if result.avg_x_ratio > self.config.routing_ratio_x:
            violations.append(Violation(
                type=ViolationType.ROUTING_RATIO_X,
                message=f"X-direction routing ratio {result.avg_x_ratio:.2%} exceeds threshold {self.config.routing_ratio_x:.2%}",
                severity="WARNING",
                value=result.avg_x_ratio,
                threshold=self.config.routing_ratio_x
            ))

        # Y方向路由占比超限
        if result.avg_y_ratio > self.config.routing_ratio_y:
            violations.append(Violation(
                type=ViolationType.ROUTING_RATIO_Y,
                message=f"Y-direction routing ratio {result.avg_y_ratio:.2%} exceeds threshold {self.config.routing_ratio_y:.2%}",
                severity="WARNING",
                value=result.avg_y_ratio,
                threshold=self.config.routing_ratio_y
            ))

        # 最长线段超限
        if result.max_segment_length > self.config.max_segment_length:
            violations.append(Violation(
                type=ViolationType.MAX_SEGMENT_LENGTH,
                message=f"Max segment length {result.max_segment_length:.1f}μm exceeds threshold {self.config.max_segment_length:.1f}μm",
                severity="WARNING",
                value=result.max_segment_length,
                threshold=self.config.max_segment_length
            ))

        # Tau超限
        if result.tau > self.config.tau_threshold:
            violations.append(Violation(
                type=ViolationType.TAU_THRESHOLD,
                message=f"Tau {result.tau:.4f}ns exceeds threshold {self.config.tau_threshold:.4f}ns",
                severity="CRITICAL",
                value=result.tau,
                threshold=self.config.tau_threshold
            ))

        return violations

    def _determine_status(self, violations: List[Violation]) -> CheckStatus:
        """根据违规列表确定检查状态

        Args:
            violations: 违规列表

        Returns:
            CheckStatus 检查状态
        """
        if not violations:
            return CheckStatus.PASS

        # 检查是否有CRITICAL违规
        has_critical = any(v.severity == "CRITICAL" for v in violations)
        if has_critical:
            return CheckStatus.FAIL

        # 检查是否有WARNING违规
        has_warning = any(v.severity == "WARNING" for v in violations)
        if has_warning:
            if self.config.strict_mode:
                return CheckStatus.FAIL
            return CheckStatus.WARNING

        return CheckStatus.PASS

    def batch_check(
        self,
        nets_data: Dict[str, Tuple[List[Polygon], Optional[NetRCData]]]
    ) -> Dict[str, RoutingCheckResult]:
        """批量检查多个网络

        Args:
            nets_data: 网络数据字典 {net_name: (polygons, rc_data)}

        Returns:
            检查结果字典
        """
        results = {}

        for net_name, (polygons, rc_data) in nets_data.items():
            result = self.check_routing(net_name, polygons, rc_data)
            results[net_name] = result

        return results

    def get_summary(self, results: Dict[str, RoutingCheckResult]) -> Dict:
        """获取批量检查的汇总信息

        Args:
            results: 检查结果字典

        Returns:
            汇总信息字典
        """
        total = len(results)
        passed = sum(1 for r in results.values() if r.is_pass)
        failed = sum(1 for r in results.values() if r.is_fail)
        warnings = sum(1 for r in results.values() if r.status == CheckStatus.WARNING)

        # Tau统计
        tau_values = [r.tau for r in results.values() if r.tau > 0]
        tau_avg = sum(tau_values) / len(tau_values) if tau_values else 0.0
        tau_max = max(tau_values) if tau_values else 0.0

        # 最长线段统计
        max_lengths = [r.max_segment_length for r in results.values() if r.max_segment_length > 0]
        max_len_avg = sum(max_lengths) / len(max_lengths) if max_lengths else 0.0
        max_len_max = max(max_lengths) if max_lengths else 0.0

        return {
            'total_nets': total,
            'passed': passed,
            'failed': failed,
            'warnings': warnings,
            'pass_rate': passed / total if total > 0 else 0.0,
            'tau_avg': tau_avg,
            'tau_max': tau_max,
            'max_segment_length_avg': max_len_avg,
            'max_segment_length_max': max_len_max,
        }


# ============================================================================
# 便捷函数
# ============================================================================

def create_default_engine() -> RoutingCheckEngine:
    """创建使用默认配置的路由检查引擎"""
    return RoutingCheckEngine(RoutingCheckConfig())


def check_net_routing(
    net_name: str,
    polygons: List[Polygon],
    rc_data: Optional[NetRCData] = None,
    config: Optional[RoutingCheckConfig] = None
) -> RoutingCheckResult:
    """便捷函数：检查单个网络的路由

    Args:
        net_name: 网络名称
        polygons: 多边形列表
        rc_data: RC数据（可选）
        config: 配置（可选）

    Returns:
        RoutingCheckResult 检查结果
    """
    engine = RoutingCheckEngine(config)
    return engine.check_routing(net_name, polygons, rc_data)


if __name__ == '__main__':
    # 测试代码
    print("Routing Check Engine")
    print("=" * 60)

    # 创建引擎
    engine = create_default_engine()
    print(f"Config: {engine.config}")

    # 创建测试数据
    from review_engine import Point, Polygon

    # 水平走线
    poly_h = Polygon(
        points=[
            Point(0, 0),
            Point(10, 0),
            Point(10, 0.04),
            Point(0, 0.04),
        ],
        layer='met1',
        net_name='TEST_H'
    )

    # 垂直走线
    poly_v = Polygon(
        points=[
            Point(0, 0),
            Point(0.04, 0),
            Point(0.04, 10),
            Point(0, 10),
        ],
        layer='met2',
        net_name='TEST_V'
    )

    # 测试水平走线
    result_h = engine.check_routing('TEST_H', [poly_h])
    print(f"\nHorizontal Test: avg_x_ratio={result_h.avg_x_ratio:.2%}")

    # 测试垂直走线
    result_v = engine.check_routing('TEST_V', [poly_v])
    print(f"Vertical Test: avg_y_ratio={result_v.avg_y_ratio:.2%}")

    print("\n[OK] Routing Check Engine initialized!")