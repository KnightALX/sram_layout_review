# 2026-06-26 Routing Thresholds Range Redesign — Design Spec

## 0. 背景与目标

用户在实测 `routing review` 与 `routing config` 两个 tab 时，发现三个具体问题：

1. **Per-Net Results 表格无法一眼看出问题单元格** — 当某行 Pass 显示 ✗ 时，所有数值单元格都正常显示，用户需要逐个对照 threshold 才能定位到超出范围的指标。
2. **Active Threshold Source banner 有暗绿色背景 (`rgba(5, 46, 22, 0.8)`)** — 视觉上像 success/active 状态指示色，但实际上与阈值来源的语义不符（无状态含义），用户希望去掉。
3. **Routing Thresholds 仅支持单边界（max 或 min）** — 实际工程中，指标可能同时有上限与下限要求（如 via coverage 既不能低于 85% 也不能超过 100%），单值语义不足以表达"区间正确"。

**本 spec 目标**：
- 引入 `Range` 数据类型，将 7 个指标统一为 `[low, high]` 区间
- per-net 表格中，超出区间的 cell 浅红背景 + `∉` 符号双重提示
- metric card 与 per-net 表格统一使用 `∈ [low, high]` 表达
- 去掉 Active Threshold Source banner 的暗绿色背景
- 一次性重构，preset YAML 与所有调用方同步迁移

## 1. 范围

| 范围项 | 包含 |
|---|---|
| 数据模型 | 新增 `Range` dataclass；`RoutingThresholds` 7 个字段改为 `Range` 类型 |
| Preset 迁移 | 3 个 YAML preset 重写；`_BUILTIN_PRESETS` 4 个内置项重写 |
| 逻辑层 | `check_gates`、`RoutingViolation` 改用 `Range.contains()`；新增 `direction`、`range_low`、`range_high`、`measured` 字段 |
| 应用层 | `app/routing_state.py`、`app/routing_review.py`、`app/routing_config.py` 全部同步 |
| UI 控件 | `dcc.RangeSlider` + 双 `dcc.Input`（low/high）双向同步；新增 slider↔input 同步回调 |
| 视觉 | 浅红 cell 背景（`rgba(239, 68, 68, 0.15)`）；动态 `∈`/`∉` 符号；去掉 banner 暗绿色 |
| 测试 | 全部 30+ 文件中引用旧字段名的同步更新；新增 Range 单元测试 |
| 报告层 | `core/report_visualization.py`、`report/routing_pptx.py` 同步新格式 |
| 文档 | `CLAUDE.md`、`README.md` 字段名说明更新 |
| 不动 | `routing_state.py` 公开 API（`get_thresholds`、`is_frozen`、`get_threshold_source`、`set_frozen_mode`、`set_custom`）；其他 tab |

## 2. 架构

### 2.1 数据模型

#### 2.1.1 Range dataclass

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Range:
    """A closed interval [low, high]. Value passes iff low <= value <= high.

    Attributes:
        low: Lower bound (inclusive).
        high: Upper bound (inclusive).

    Raises:
        ValueError: When constructed with low > high.
    """
    low: float
    high: float

    def __post_init__(self):
        # Note: low == high is allowed (single-point range, e.g. via_coverage
        # can be [1.0, 1.0] meaning "must be exactly 100% covered"). Only
        # strict inversion (low > high) is rejected.
        if self.low > self.high:
            raise ValueError(f"Range low ({self.low}) > high ({self.high})")

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high

    def violation_direction(self, value: float) -> Optional[str]:
        """Return 'low' if value < low, 'high' if value > high, None if in range."""
        if value < self.low:
            return "low"
        if value > self.high:
            return "high"
        return None
```

#### 2.1.2 RoutingThresholds 重构

```python
@dataclass
class RoutingThresholds:
    """Gating thresholds for routing review.

    Each metric is a [low, high] interval. A value passes iff
    low <= value <= high. The aggregate pass/fail for a net is
    computed in core.routing_metrics.check_gates.
    """
    net_class: str = "wl"
    h_ratio: Range = field(default_factory=lambda: Range(0.0, 0.15))
    v_ratio: Range = field(default_factory=lambda: Range(0.0, 1.0))
    r_ohm: Range = field(default_factory=lambda: Range(0.0, 100.0))
    c_ff: Range = field(default_factory=lambda: Range(0.0, 500.0))
    tau_ps: Range = field(default_factory=lambda: Range(0.0, 12.5))
    via_coverage: Range = field(default_factory=lambda: Range(0.85, 1.0))
    similarity: Range = field(default_factory=lambda: Range(80.0, 100.0))

    def validate(self) -> None:
        """Sanity check. Raises ValueError on invalid config.

        - Each Range: low <= high (already enforced in __post_init__)
        - h_ratio.high + v_ratio.high >= 1.0 (so at least one direction can dominate)
        - r_ohm.high, c_ff.high, tau_ps.high must be > 0
        """
        # Range fields self-validate in __post_init__; just check the h+v rule.
        if self.h_ratio.high + self.v_ratio.high < 1.0 - 1e-9:
            raise ValueError(
                f"h_ratio.high ({self.h_ratio.high}) + v_ratio.high "
                f"({self.v_ratio.high}) must sum to >= 1.0"
            )
        for name in ("r_ohm", "c_ff", "tau_ps"):
            v = getattr(self, name).high
            if v <= 0:
                raise ValueError(f"{name}.high must be positive: {v}")
```

#### 2.1.3 Preset YAML 新格式

```yaml
# 7nm FinFET SRAM — Wordline-dominant preset
# Use for: WL signal nets (expect H-dominant routing)
net_class: wl
h_ratio:    {low: 0.0, high: 0.15}    # H length ≤ 15%
v_ratio:    {low: 0.0, high: 1.0}     # V length allowed up to 100%
r_ohm:      {low: 0.0, high: 100.0}
c_ff:       {low: 0.0, high: 500.0}
tau_ps:     {low: 0.0, high: 12.5}
via_coverage: {low: 0.85, high: 1.0}
similarity: {low: 80.0, high: 100.0}
```

#### 2.1.4 _BUILTIN_PRESETS 同步重写

```python
_BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "sram_7nm_wl": {
        "net_class": "wl",
        "h_ratio":    {"low": 0.0, "high": 0.15},
        "v_ratio":    {"low": 0.0, "high": 1.0},
        "r_ohm":      {"low": 0.0, "high": 100.0},
        "c_ff":       {"low": 0.0, "high": 500.0},
        "tau_ps":     {"low": 0.0, "high": 12.5},
        "via_coverage": {"low": 0.85, "high": 1.0},
        "similarity": {"low": 80.0, "high": 100.0},
    },
    # ... 其他 3 个内置项同理
}
```

### 2.2 逻辑层

#### 2.2.1 check_gates 改用 Range

**Threshold field → Metrics dict key 映射表**：

| Threshold field | metrics dict key | 类型 |
|---|---|---|
| `h_ratio` | `metrics["h_ratio"]` | float 0-1 |
| `v_ratio` | `metrics["v_ratio"]` | float 0-1 |
| `r_ohm` | `metrics["r_total"]` | float Ω（保留原 metrics key 名） |
| `c_ff` | `metrics["c_total"]` | float fF（保留原 metrics key 名） |
| `tau_ps` | `metrics["effective_tau_ps"]` | float ps（保留原 metrics key 名） |
| `via_coverage` | `metrics["via_coverage"]` | float 0-1 |
| `similarity` | `metrics["similarity_score"]` | float 0-100 |

> 注意：metrics dict 沿用 `r_total` / `c_total` / `effective_tau_ps` 的 key 命名以避免改动
> `core/routing_metrics.py` 内部太多的 metric 名称映射。仅 threshold 字段名变更为 `r_ohm` / `c_ff` /
> `tau_ps`。`_THRESHOLD_TO_METRIC_KEY` 常量在 `check_gates` 内部用于解耦。

```python
# Mapping from threshold field name to metrics dict key
_THRESHOLD_TO_METRIC_KEY = {
    "h_ratio": "h_ratio",
    "v_ratio": "v_ratio",
    "r_ohm": "r_total",
    "c_ff": "c_total",
    "tau_ps": "effective_tau_ps",
    "via_coverage": "via_coverage",
    "similarity": "similarity_score",
}

def check_gates(metrics, thresholds, has_golden=False):
    """每项指标独立判断是否落在 [low, high] 区间内。"""
    hard_reasons: List[str] = []
    soft_reasons: List[str] = []

    # HARD: r_ohm / c_ff / tau_ps
    for thresh_key, display_name in [("r_ohm", "R"), ("c_ff", "C"), ("tau_ps", "τ")]:
        rng = getattr(thresholds, thresh_key)
        measured = metrics[_THRESHOLD_TO_METRIC_KEY[thresh_key]]
        if not rng.contains(measured):
            d = rng.violation_direction(measured)
            hard_reasons.append(
                f"{display_name} {measured:.2f} {d} of [{rng.low}, {rng.high}]"
            )

    # SOFT: h_ratio / v_ratio / via_coverage (golden bypass)
    for thresh_key in ("h_ratio", "v_ratio", "via_coverage"):
        rng = getattr(thresholds, thresh_key)
        measured = metrics[_THRESHOLD_TO_METRIC_KEY[thresh_key]]
        if not rng.contains(measured):
            d = rng.violation_direction(measured)
            soft_reasons.append(
                f"{thresh_key} {measured} {d} of [{rng.low}, {rng.high}]"
            )

    # Similarity
    sim_rng = thresholds.similarity
    sim_measured = metrics[_THRESHOLD_TO_METRIC_KEY["similarity"]]
    if not sim_rng.contains(sim_measured):
        d = sim_rng.violation_direction(sim_measured)
        hard_reasons.append(
            f"similarity {sim_measured} {d} of "
            f"[{sim_rng.low}, {sim_rng.high}]"
        )

    # missing_via 计数检查保留（不在 Range 范围内）
    ...
```

#### 2.2.2 RoutingViolation 字段扩展

```python
@dataclass
class RoutingViolation:
    kind: ViolationKind
    net_name: str
    severity: str = "critical"
    message: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
    polygon_index: Optional[int] = None
    # Direction of the violation relative to the range
    direction: Optional[str] = None          # "low" / "high"
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    # The actual measured value (used for per-cell coloring)
    measured: Optional[float] = None
    # Legacy limit field kept for backward serialization
    limit: Optional[float] = None

    @classmethod
    def h_ratio(cls, net_name, h_ratio, rng: Range):
        return cls(
            kind=ViolationKind.H_RATIO, net_name=net_name,
            measured=h_ratio, range_low=rng.low, range_high=rng.high,
            direction=rng.violation_direction(h_ratio),
            message=f"h_ratio {h_ratio:.2%} {rng.violation_direction(h_ratio)} "
                    f"[{rng.low:.2%}, {rng.high:.2%}]",
        )
    # ... 其他工厂方法同理
```

### 2.3 应用层

#### 2.3.1 Active Threshold Source Banner 去绿色

修改 `app/routing_review.py::_build_threshold_source`：

```python
# 修改前
html.Span(src, style={
    "background": "rgba(5, 46, 22, 0.8)",  # 暗绿色
    "padding": "2px 6px",
    "borderRadius": "3px",
    "fontSize": "10px",
}),

# 修改后
html.Span(src, style={"fontSize": "11px"}),  # 无背景，仅文字
```

#### 2.3.2 Per-Net Cell 浅红染色

新增辅助函数 `_build_cell_violation_map`，根据 measurement 与 range 比较，生成 `{net_name: {column_id, ...}}` 映射：

```python
FIELD_TO_COLUMN = {
    "h_ratio": "H %", "v_ratio": "V %", "r_ohm": "R (Ω)",
    "c_ff": "C (fF)", "tau_ps": "τ (ps)",
    "via_coverage": "Via Cov", "similarity": "Sim",
}

def _build_cell_violation_map(batch_results, thresholds):
    cell_map: Dict[str, Set[str]] = {}
    for name, m in batch_results.items():
        if m.get("status") == "no_data":
            continue
        bad_cells = set()
        for field, col in FIELD_TO_COLUMN.items():
            rng = getattr(thresholds, field)
            measured = _extract_metric(m, field)
            if measured is not None and not rng.contains(measured):
                bad_cells.add(col)
        if bad_cells:
            cell_map[name] = bad_cells
    return cell_map
```

在 `_compute_table_styles` 中追加浅红背景规则：

```python
{"if": {"column_id": col, "filter_query": f'{{Net}} = "{net_name}"'},
 "backgroundColor": "rgba(239, 68, 68, 0.15)"}  # 不改文字、不加粗
```

#### 2.3.3 Per-Net Cell 动态 ∈ / ∉ 符号

在 `_build_table_rows` 中：

```python
def _format_cell(value, rng: Range, fmt="{:.1f}"):
    symbol = "∈" if rng.contains(value) else "∉"
    return f"{fmt.format(value)} {symbol} [{fmt.format(rng.low)}, {fmt.format(rng.high)}]"
```

例：
- `H %: 12.5 ∈ [0.0, 0.15]`
- `H %: 22.0 ∉ [0.0, 0.15]`

#### 2.3.4 Metric Card 显示更新

所有 6 个 metric card 统一使用 `∈ [low, high]` 格式：

| Card | 显示 |
|---|---|
| H / V Ratio | `0.0–15.0% ∈ [0.0, 0.15] / [0.0, 1.0]` |
| Missing Via | `0–2 ∈ [0, 0]` |
| Eff. R (Ω) | `80.5–120.3Ω ∈ [0.0, 100.0]` |
| Eff. C (fF) | `320.5–650.0fF ∈ [0.0, 500.0]` |
| Eff. τ (ps) | `8.2–15.0ps ∈ [0.0, 12.5]` |
| Similarity | `75–95 ∈ [80.0, 100.0]` |

`Pass / Fail` 卡片维持原样（红/绿边框）。

#### 2.3.5 Routing Config — Range Slider + Text Inputs

`THRESHOLD_FIELDS` 扩展为 `RANGE_FIELDS`：

```python
RANGE_FIELDS = [
    {
        "name": "h_ratio", "label": "H Ratio",
        "slider_min": 0.0, "slider_max": 1.0, "step": 0.01,
    },
    {
        "name": "v_ratio", "label": "V Ratio",
        "slider_min": 0.0, "slider_max": 1.0, "step": 0.01,
    },
    {
        "name": "r_ohm", "label": "R (Ω)",
        "slider_min": 0.0, "slider_max": 10000.0, "step": 0.1,
    },
    {
        "name": "c_ff", "label": "C (fF)",
        "slider_min": 0.0, "slider_max": 100000.0, "step": 1,
    },
    {
        "name": "tau_ps", "label": "τ (ps)",
        "slider_min": 0.0, "slider_max": 1000.0, "step": 0.1,
    },
    {
        "name": "via_coverage", "label": "Via Coverage",
        "slider_min": 0.0, "slider_max": 1.0, "step": 0.01,
    },
    {
        "name": "similarity", "label": "Similarity",
        "slider_min": 0.0, "slider_max": 100.0, "step": 1,
    },
]
```

每行 UI 布局：

```python
def _build_range_input_group(field):
    name, label = field["name"], field["label"]
    rng = getattr(routing_state.get_thresholds(), name)
    # marks: 显示 low/high 端点 + 中点（4 个标度），刻度间距均匀便于视觉对位
    s_min, s_max, step = field["slider_min"], field["slider_max"], field["step"]
    marks = {
        s_min: f"{s_min:g}",
        (s_min + s_max) / 2: f"{(s_min + s_max) / 2:g}",
        s_max: f"{s_max:g}",
    }
    return html.Div([
        html.Label(label, className="form-label"),
        dcc.RangeSlider(
            id=f"slider-{name}",
            min=s_min, max=s_max, step=step,
            value=[rng.low, rng.high], marks=marks,
            tooltip={"placement": "bottom", "always_visible": False},
        ),
        html.Div([
            html.Span("Low: "),
            dcc.Input(id=f"input-{name}-low", type="number",
                      value=rng.low, min=s_min, max=s_max, step=step),
            html.Span("High: ", style={"marginLeft": "12px"}),
            dcc.Input(id=f"input-{name}-high", type="number",
                      value=rng.high, min=s_min, max=s_max, step=step),
        ], style={"display": "flex", "alignItems": "center",
                  "marginTop": "4px"}),
    ], className="form-group", style={"marginBottom": "12px"})
```

#### 2.3.6 双向同步回调

```python
# Slider → Inputs
@app.callback(
    [Output(f"input-{name}-low", "value"),
     Output(f"input-{name}-high", "value")],
    Input(f"slider-{name}", "value"),
)
def _slider_to_input(value, field_name):
    return value[0], value[1]

# Inputs → Slider（防回环：仅当两边都有值才更新）
@app.callback(
    Output(f"slider-{name}", "value"),
    [Input(f"input-{name}-low", "value", allow_duplicate=True),
     Input(f"input-{name}-high", "value", allow_duplicate=True)],
    prevent_initial_call=True,
)
def _input_to_slider(low, high, field_name):
    if low is None or high is None:
        raise PreventUpdate
    if low > high:
        raise PreventUpdate  # 不允许 low > high，UI 不回环
    return [low, high]
```

#### 2.3.7 Apply 流程

```python
def _apply_ranges(range_values: dict) -> tuple[Optional[RoutingThresholds], Optional[str]]:
    """将 7 对 (low, high) 值构造为 RoutingThresholds。"""
    current = routing_state.get_thresholds()
    tentative_dict = current.to_dict()
    for name in ("h_ratio", "v_ratio", "r_ohm", "c_ff", "tau_ps",
                 "via_coverage", "similarity"):
        low = range_values.get(f"{name}-low")
        high = range_values.get(f"{name}-high")
        if low is None or high is None:
            continue
        try:
            tentative_dict[name] = {"low": float(low), "high": float(high)}
        except (TypeError, ValueError) as e:
            return None, f"{name}: {e}"
    try:
        tentative = RoutingThresholds.from_dict(tentative_dict)
        tentative.validate()
    except Exception as e:
        return None, str(e)
    return tentative, None
```

### 2.4 状态层

`app/routing_state.py` 的 `RoutingState` 类公开 API 不变：

- `current_preset: str`
- `is_frozen: bool`
- `thresholds: RoutingThresholds`
- `custom_thresholds: Optional[RoutingThresholds]`
- `get_thresholds() -> RoutingThresholds`
- `get_threshold_source() -> str`
- `set_frozen_mode(frozen: bool)`
- `set_custom(thresholds: RoutingThresholds)`

仅 `__post_init__` 中的默认 `RoutingThresholds()` 构造由单值字段改为 `Range` 字段。`get_thresholds()` 行为不变。

## 3. 文件变更清单

### 3.1 核心数据模型

| 文件 | 修改 |
|---|---|
| `config/routing_thresholds.py` | 新增 `Range` dataclass；`RoutingThresholds` 7 字段改 `Range`；`validate()` 改用 `low <= high` 规则 |
| `config/preset_loader.py` | `_normalize_keys` 处理嵌套 `low/high`；移除旧别名 |
| `config/presets/sram_7nm_wl.yaml` | 重写 |
| `config/presets/sram_5nm_io_bl.yaml` | 重写 |
| `config/presets/analog_default.yaml` | 重写 |

### 3.2 逻辑层

| 文件 | 修改 |
|---|---|
| `core/routing_metrics.py` | `check_gates` 改用 `Range.contains()`；metric 字段名调整 |
| `core/routing_violation.py` | 新增 `direction`/`range_low`/`range_high`/`measured`；工厂方法签名改 `Range` |

### 3.3 应用层

| 文件 | 修改 |
|---|---|
| `app/routing_state.py` | 默认构造改 `Range` |
| `app/routing_review.py` | 去掉 banner 绿色；新增 `_build_cell_violation_map`；`_build_table_rows` 用 `_format_cell`；`_compute_table_styles` 增浅红规则；metric card 用 `∈` |
| `app/routing_config.py` | `THRESHOLD_FIELDS` 改 `RANGE_FIELDS`；UI 改 RangeSlider+Inputs；新增 slider↔input 同步回调；`_apply_ranges` 构造 `Range`；metric card 改 `∈` |

### 3.4 测试

| 文件 | 修改 |
|---|---|
| `tests/test_routing_thresholds.py` | 全部改 `Range` 引用 |
| `tests/test_routing_metrics.py` | 改用 `Range.contains()` |
| `tests/test_routing_violation.py` | 改用新字段 |
| `tests/test_routing_config_layout.py` | 改用 `RANGE_FIELDS` |
| `tests/test_routing_config_state_machine.py` | 改用 `Range` |
| `tests/test_preset_loader.py` | YAML 解析改测 `low/high` |
| `tests/test_preset_loader_schema.py` | 同上 |
| `tests/test_apply_persistence.py` | 改用 `Range` |
| `tests/test_routing_e2e.py` | 端到端 |
| `tests/test_routing_pptx.py` | 报告生成 |
| `tests/test_tab_rehydrate.py` | tab 重新加载 |

### 3.5 报告 / 可视化

| 文件 | 修改 |
|---|---|
| `core/report_visualization.py` | cell 同步 `∈`/`∉` |
| `report/routing_pptx.py` | 同步 `∈`/`∉` |

### 3.6 文档

| 文件 | 修改 |
|---|---|
| `CLAUDE.md` | 字段名说明更新 |
| `README.md` | threshold 字段说明更新 |

## 4. 测试策略

### 4.1 单元测试

- `Range.__post_init__` 拒绝 `low > high`
- `Range.contains` 闭区间正确性（边界值）
- `Range.violation_direction` 三态返回
- `RoutingThresholds.validate()` 接受合法组合、拒绝 h+v < 1.0
- 所有 3 个 YAML preset 加载通过 `validate()`
- 所有 4 个 `_BUILTIN_PRESETS` 加载通过 `validate()`

### 4.2 集成测试

- 加载新 preset → 渲染到 UI → 修改 Range → Apply → 验证 batch_results 反映新阈值
- 故意构造超出区间的 net，验证：
  - Pass 显示 ✗
  - 对应 cell 显示 `∉` + 浅红背景
  - 在范围内 cell 显示 `∈` + 无背景
- slider 拖动 → input 同步更新
- input 输入 → slider 同步更新
- Apply 提交 → 新 Range 生效 → re-run review
- low > high 时 Apply 失败 + 错误提示

### 4.3 视觉验证（手动）

- 启动 `layout_review_app.py`
- 上传示例 shape file（`shapes_test_wordline_WL0.txt` 等）
- Routing Config tab：拖动 slider、输入数值、Apply
- Routing Review tab：验证 `∉` 符号 + 浅红背景 + Active Threshold Source 无绿色

## 5. 验收标准

| 验收项 | 通过条件 |
|---|---|
| Active Threshold Source banner 无绿色 | 检查 HTML，`background-color` 字段不存在或为 `transparent` |
| Per-Net 表格 in-range cell | 显示 `∈ [low, high]`，无背景 |
| Per-Net 表格 out-of-range cell | 显示 `∉ [low, high]`，浅红背景 `rgba(239, 68, 68, 0.15)`，文字不变 |
| Metric Card 显示 | `<value> ∈ [<low>, <high>]` 格式 |
| Range Slider | 拖动任一端点，对应 Input 数值同步 |
| Input 数值 | 修改 low/high，Slider 位置同步（防回环） |
| Apply | 合法输入 → 状态更新；`low > high` → 错误提示 |
| 3 个 YAML preset | 加载后通过 `validate()` |
| 4 个 _BUILTIN_PRESETS | 加载后通过 `validate()` |
| 30+ 引用旧字段名的文件 | 无遗漏，全部使用 `Range` 字段 |

## 6. 实施顺序

1. **Phase 1**: 数据模型与 preset
   - 新增 `Range` dataclass
   - 重构 `RoutingThresholds`
   - 重写 `_BUILTIN_PRESETS`
   - 重写 3 个 YAML preset
   - 单元测试覆盖

2. **Phase 2**: 逻辑层
   - `check_gates` 改用 `Range.contains()`
   - `RoutingViolation` 字段扩展
   - 集成测试覆盖

3. **Phase 3**: 应用层（review + config）
   - `routing_state.py` 默认值更新
   - review tab: 去掉绿色背景、新增 cell 染色、`∈`/`∉` 符号、metric card 格式
   - config tab: RangeSlider + Inputs 组件、回调、Apply 流程
   - 端到端测试

4. **Phase 4**: 报告与文档
   - PPTX 报告同步
   - `CLAUDE.md`、`README.md` 更新

5. **Phase 5**: 手动视觉验证

## 7. 不在范围内

- 后续可考虑的 per-net-class 独立阈值（不同 net 自动用不同 preset）
- 范围编辑时的可视化分布（直方图 + 当前值标注）
- 阈值导入/导出 UI（当前仅支持 preset YAML 加载）
- Range 区间外的 metric 趋势预警（仅当下值超界时报警）

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 大量文件同步修改可能漏改 | 通过 `Grep "max_h_ratio\|max_v_ratio\|max_r_ohm\|max_c_ff\|max_tau_ps\|min_via_coverage\|min_similarity"` 全文搜索确认无遗漏 |
| YAML 解析对嵌套 dict 的支持 | `yaml.safe_load` 天然支持，单元测试覆盖新格式 |
| `Range` frozen 特性（不可变） | 防止运行时意外修改 threshold 边界 |
| 旧测试 fixture 引用旧字段名 | 同步更新所有测试 fixture |
| PPTX 报告生成对新字段的兼容 | `test_routing_pptx.py` 覆盖 |
| Custom mode 切换后 range 保留 | `_render_state` 中所有 input value 都从 `routing_state.get_thresholds()` 读出，状态层无感 |
| Slider/Input 同步回环 | input → slider 回调使用 `prevent_initial_call=True` + 拒绝 `low > high` |
| 旧 max_*/min_* 别名 | 一次性迁移，无向后兼容。所有引用方同步更新 |
