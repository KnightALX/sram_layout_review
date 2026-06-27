# 2026-06-27 Routing Config Range Slider Compact 2-Column Redesign — Design Spec

## 0. 背景与目标

上一轮 (`2026-06-27-routing-config-slider-redesign`) 已将 Slider UI 改造为单列 Accent Strip 风格 + 数值徽章 + 数学区间提示。但用户反馈：

1. **单列布局占用垂直空间过大**：7 个 metric × 单列堆叠 = 长滚动
2. **数值徽章冗余**：低/高文字输入与 slider bar 表达的是同一信息，但徽章占用了额外空间，分散了用户注意力
3. **「Low/High 文字设定」应与 slider bar 合并**：去掉独立的数字输入，slider 本身就是设置交互

**本 spec 目标**：

- **2 列行布局**：每个 row 容纳 2 个 metric（语义配对），节省约 50% 垂直空间
- **去掉 Low/High 数字输入徽章**：slider 是唯一的设置交互；精确数值通过 hover tooltip 显示
- **共享外层边框**：row 内 2 个 metric 通过细分隔线分割，视觉上是一个 row 但语义上是 2 个独立 metric
- **紧凑数学区间**：每个 metric 底部一行 `low ≤ X ≤ high ⟷ w=width`
- **约束违反可视化**：low > high → metric cell 背景泛红 + 滑轨变红 + 逻辑行 ⚠
- **完全复用上一轮 CSS 变量 / dark-light 模式适配**
- **仅依赖 Dash 库 · 离线运行**

参考 mockup：`docs/mockups/slider-2col-compact.html`

## 1. 范围

| 范围项 | 包含 |
|---|---|
| UI 组件 | `_build_range_input_group` → `_build_metric_cell` + `_build_compact_range_row` |
| 移除 | `badge-input-{name}-{low|high}` ID · `_build_badge` 辅助 · `_sync_slider_to_badges` / `_sync_badges_to_slider` 同步回调 |
| CSS | 新增 `.range-row` / `.metric-cell` / `.logic-compact` / `.metric-cell.is-invalid` / `.is-warning` 块 |
| 数据模型 | 不动（`Range` / `RoutingThresholds` / presets） |
| 配对规则 | `RANGE_ROW_GROUPS` 新增，定义语义配对 |
| 不动 | `config/routing_thresholds.py` · preset YAML · review tab · banner · state machine |

## 2. 视觉规范

### 2.1 Row 结构（一行 = 2 个 metric）

```
┌─────────────────────────────────────────────────────────────────┐
│  Horizontal Ratio 横向走线占比    bounds [0.00, 1.00]          │  ← metric-cell 1 header
│  ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●    │  ← slider 1
│  0.00                  0.50                  1.00               │  ← tick-row 1
│  ┌─────────────────────┐ ┌─────────────────────┐                 │
│  │ 0.10 ≤ X ≤ 0.15 ⟷ w=0.05│ │ 0.30 ≤ X ≤ 0.80 ⟷ w=0.50│       │  ← logic-compact 1 & 2
│  └─────────────────────┘ └─────────────────────┘                 │
├─────────────────────────────────────────────────────────────────┤ ← 1px border-secondary divider
│  Vertical Ratio 纵向走线占比         bounds [0.00, 1.00]        │
│  ...                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 视觉规范

| 元素 | 规范 |
|---|---|
| **外层 row** | `border: 1px solid var(--border-primary)` · `border-radius: 6px` · `display: grid; grid-template-columns: 1fr 1fr` |
| **metric-cell** | `padding: 12px 14px` · `display: flex; flex-direction: column; gap: 6px` |
| **metric-cell + .metric-cell** | `border-left: 1px solid var(--border-secondary)`（细分隔线） |
| **metric-header** | `display: flex; justify-content: space-between` · name + help 在左，bounds 在右 |
| **metric-name** | `font-size: 12px; font-weight: 600; color: var(--text-primary)` |
| **metric-help** | `font-size: 10px; color: var(--text-muted); margin-left: 4px` |
| **metric-bounds** | `font-family: var(--font-data); font-size: 10px; color: var(--text-muted)` |
| **logic-compact** | `font-family: var(--font-data); font-size: 10px; color: var(--text-muted)` · 单行 `code + ic + code` |
| **logic-compact code** | `background: var(--bg-tertiary); color: var(--accent-secondary); padding: 1px 5px; border-radius: 3px` |
| **.metric-cell.is-invalid** | `background: rgba(239, 68, 68, 0.06)` + 滑轨渐变变红 + logic 行转 fail 色 |
| **.metric-cell.is-warning** | `background: rgba(245, 158, 11, 0.06)` + 滑轨 handle 边框转 warning 色 + logic 行转 warning 色 |

### 2.3 dark / light 模式

完全复用上一轮 CSS 变量；light 模式通过 `.theme-light .range-row` / `.theme-light .metric-cell + .metric-cell` 覆盖。

### 2.4 移除元素

- **badge-input-{name}-{low|high} dcc.Input**（上一轮加的透明叠加）—— 删除
- **range-slider-badge** 样式块 —— 删除（保留 CSS 但不挂载组件）
- **badge-input-overlay** 样式块 —— 删除

## 3. 组件结构

### 3.1 `RANGE_ROW_GROUPS` 数据结构

定义语义配对（取代旧的顺序配对）：

```python
# 几何 / 电气 / 时序 / 单 metric
RANGE_ROW_GROUPS = [
    {
        "id": "geometric",
        "label": "几何",  # 调试用，可选
        "fields": ["h_ratio", "v_ratio"],
    },
    {
        "id": "electrical",
        "label": "电气",
        "fields": ["r_ohm", "c_ff"],
    },
    {
        "id": "timing",
        "label": "时序",
        "fields": ["tau_ps", "via_coverage"],
    },
    {
        "id": "quality",
        "label": "质量",
        "fields": ["similarity"],  # 单 metric
    },
]
```

字段总数 7，分 4 行：3 行 × 2 metric + 1 行 × 1 metric。

### 3.2 `_build_compact_range_row(group)` — 构建单 row

```python
def _build_compact_range_row(group):
    """Build a single compact row containing 1 or 2 metric cells.
    
    Single-metric rows (1 field) render with grid-template-columns: 1fr
    so the metric takes the full row width.
    """
    fields = [_lookup_field(name) for name in group["fields"]]
    is_single = len(fields) == 1
    return html.Div([
        _build_metric_cell(f) for f in fields
    ], id=f"row-{group['id']}",
       className="range-row" + (" single" if is_single else ""),
       style={"gridTemplateColumns": "1fr"} if is_single else None)
```

### 3.3 `_build_metric_cell(field)` — 构建单个 metric cell

```python
def _build_metric_cell(field):
    """Build a single metric cell: header + slider + tick + compact logic."""
    from dash import dcc, html
    name = field["name"]
    label = field["label"]
    help_text = field.get("help", "")
    unit = field.get("unit", "")
    fmt = field["fmt"]
    rng = getattr(routing_state.get_thresholds(), name)
    s_min = field["slider_min"]
    s_max = field["slider_max"]
    step = field["step"]
    bounds_text = f"[{fmt.format(s_min)}, {fmt.format(s_max)}]"
    
    initial_status = _compute_constraint_status(rng.low, rng.high, s_min, s_max)
    
    return html.Div([
        # ── Header: name + help + bounds ──
        html.Div([
            html.Div([
                html.Span(label, className="metric-name"),
                html.Span(f" {help_text}", className="metric-help") if help_text else None,
            ]),
            html.Div([
                "bounds ",
                html.B(bounds_text),
                f" {unit}".rstrip(),
            ], className="metric-bounds"),
        ], className="metric-header"),
        
        # ── Slider (the ONLY input control) ──
        dcc.RangeSlider(
            id=f"slider-{name}",
            min=s_min, max=s_max, step=step,
            value=[rng.low, rng.high],
            marks=None,
            tooltip={"placement": "bottom", "always_visible": False},
            allowCross=False,
            className="range-slider",
        ),
        
        # ── Tick row (min, mid, max) ──
        html.Div([
            html.Span(fmt.format(s_min)),
            html.Span(fmt.format((s_min + s_max) / 2), className="mid"),
            html.Span(fmt.format(s_max)),
        ], className="tick-row"),
        
        # ── Compact logic row ──
        html.Div(
            id=f"logic-{name}",
            className="logic-compact" + (f" is-{initial_status}" if initial_status != "valid" else ""),
            children=_build_compact_logic_content(rng.low, rng.high, fmt, initial_status),
        ),
    ], id=f"cell-{name}",
       className="metric-cell" + (f" is-{initial_status}" if initial_status != "valid" else ""),
       **{"data-field": name})
```

### 3.4 `_build_compact_logic_content` — 紧凑逻辑行

```python
def _build_compact_logic_content(low, high, fmt, status):
    """Compact single-line logic annotation.
    
    Format: <code>low ≤ X ≤ high</code> <span class="ic">⟷</span> <code>w=width</code>
    
    Or for invalid/warning states:
      invalid: <code>low ≤ X ≤ high</code> <span class="ic">⚠ 越界</span>
      warning (zero width): <code>low ≤ X ≤ high</code> <span class="ic">⚠ 宽度为 0</span>
      warning (narrow): <code>low ≤ X ≤ high</code> <span class="ic">⚠ 区间过窄</span>
    """
    from dash import html
    range_text = f"{fmt.format(low)} \u2264 X \u2264 {fmt.format(high)}"
    
    if status == "invalid":
        return [
            html.Code(range_text),
            html.Span("\u26a0 \u8d8a\u754c", className="ic"),  # ⚠ 越界
        ]
    if status == "warning":
        if low == high:
            return [
                html.Code(range_text),
                html.Span("\u26a0 \u5bbd\u5ea6\u4e3a 0", className="ic"),  # ⚠ 宽度为 0
            ]
        return [
            html.Code(range_text),
            html.Span("\u26a0 \u533a\u95f4\u8fc7\u7a84", className="ic"),  # ⚠ 区间过窄
        ]
    # valid
    return [
        html.Code(range_text),
        html.Span(" \u27fa ", className="ic"),  # ⟷
        html.Code(f"w={fmt.format(high - low)}"),
    ]
```

### 3.5 主函数 `create_routing_config_tab` 改动

```python
# 替换原 slider 区域
html.Div([
    html.Div("\u9608\u503c\u533a\u95f4 (Closed Interval)",
             className="section-header"),
    html.Div("\u62d6\u62fd\u624b\u67c4\u8c03\u8282\u533a\u95f4 \u00b7 \u60ac\u505c\u770b\u7cbe\u786e\u503c \u00b7 4 \u884c \u00d7 2 \u5217",
             className="section-subheader"),
    html.Div([
        _build_compact_range_row(group) for group in RANGE_ROW_GROUPS
    ], id="routing-config-ranges", className="ranges-container"),
], className="config-section"),
```

## 4. 交互模型

### 4.1 Slider 拖拽 → Logic Row + Cell ClassName 同步

每个 metric 注册一个 callback（保留上一轮的 `_update_logic_and_row`，但输出目标改为 `logic-{name}` 和 `cell-{name}`）：

```python
@app.callback(
    [Output(f"logic-{name}", "children"),
     Output(f"logic-{name}", "className"),
     Output(f"cell-{name}", "className")],
    Input(f"slider-{name}", "value"),
    prevent_initial_call=False,
)
def _update_metric_cell(_value, _name=name, _s_min=s_min, _s_max=s_max, _fmt=fmt):
    from dash.exceptions import PreventUpdate
    if _value is None or len(_value) != 2:
        raise PreventUpdate
    low, high = _value[0], _value[1]
    status = _compute_constraint_status(low, high, _s_min, _s_max)
    logic_class = "logic-compact" if status == "valid" else f"logic-compact is-{status}"
    cell_class = "metric-cell" if status == "valid" else f"metric-cell is-{status}"
    return (
        _build_compact_logic_content(low, high, _fmt, status),
        logic_class,
        cell_class,
    )
```

### 4.2 移除的回调

- `_sync_slider_to_badges` —— 删除（不再需要 badge-input 同步）
- `_sync_badges_to_slider` —— 删除（不再需要 badge-input 同步）

### 4.3 移除的 IDs

- `badge-input-{name}-low` / `badge-input-{name}-high` —— 删除（不再渲染）

### 4.4 保留的 IDs

- `slider-{name}` —— 保留（每 metric 一个 RangeSlider）
- `logic-{name}` —— 保留（每 metric 一个 logic 行）
- `cell-{name}` —— 新增（每 metric 一个 cell 容器）
- `row-{group_id}` —— 新增（每个 row 的共享边框容器）

### 4.5 Hover Tooltip

Dash `dcc.RangeSlider` 自带 `tooltip={"placement": "bottom", "always_visible": False}`，鼠标悬停手柄时显示当前值。这是唯一的精确值显示方式。

## 5. 数据流

```
[Preset YAML / Custom dict]
        │
        ▼
[RoutingThresholds: 7 × Range]   ◄─── 数据模型不变
        │
        ▼
[RANGE_ROW_GROUPS: 4 × group]    ◄─── 新增语义配对
        │
        ▼
[_build_compact_range_row(group)]
        │
        ├──► _build_metric_cell(field) × 1 or 2
        │       ├──► dcc.RangeSlider (id=slider-{name})
        │       ├──► tick-row (min, mid, max spans)
        │       ├──► logic-{name} (id=logic-{name})
        │       └──► cell-{name} (id=cell-{name})
        │
        └──► row-{group_id} (shared border container)

[用户拖拽 Slider]
        │
        ▼
[callback _update_metric_cell]   ◄─── 7 个 metric 各一个
        │
        ├──► 更新 logic-{name} 的 children
        ├──► 更新 logic-{name} 的 className
        └──► 更新 cell-{name} 的 className (合规/警告/失败)
```

## 6. 测试策略

### 6.1 单元测试

更新现有 `tests/test_routing_config_range_fields.py`：

- 移除 `test_build_range_input_group_uses_slider_and_badge_inputs`（badge-input 已删除）
- 添加 `test_range_row_groups_defines_four_groups_with_seven_fields`：
  - 4 个 group
  - 总 fields 数 = 7
  - 每个 field 在 RANGE_FIELDS 中存在
- 添加 `test_build_metric_cell_has_new_structure_ids`：
  - cell-{name} id 存在
  - slider-{name} id 存在
  - logic-{name} id 存在
  - badge-input-{name}-low/high id 不存在（移除确认）
- 添加 `test_build_compact_range_row_contains_correct_number_of_cells`：
  - 单 metric group → 1 个 cell
  - 双 metric group → 2 个 cell
  - row-{group_id} id 存在

### 6.2 Logic 内容测试

更新现有 `_build_logic_row_content` → 改为 `_build_compact_logic_content`：

- `test_compact_logic_content_valid_format` — 验证 `low ≤ X ≤ high ⟷ w=width` 三段结构
- `test_compact_logic_content_invalid_shows_越界`
- `test_compact_logic_content_warning_zero_width`
- `test_compact_logic_content_warning_narrow_range`

### 6.3 Callback 测试

更新 `tests/test_routing_config_slider_ui.py`：

- `test_logic_row_callback_registered_for_each_field` 更新断言：
  - Output 是 `logic-{name}.children`
  - Output 是 `cell-{name}.className`（不是 `row-{name}.className`）
- 删除 `test_slider_to_badges` / `test_badges_to_slider_*`（helpers 已移除）

### 6.4 Layout 测试

更新 `tests/test_routing_config_layout.py`：

- `test_create_routing_config_tab_uses_range_sliders` 更新断言：
  - 7 个 `id='slider-`
  - 0 个 `id='badge-input-`
  - 4 个 `id='row-`
  - 7 个 `id='cell-`
- 添加 `test_create_routing_config_tab_uses_2col_layout`：
  - `id='routing-config-ranges'` 存在
  - `range-row` class 出现 4 次

### 6.5 Sync 测试

`tests/test_routing_config_sync.py` 应被删除（helpers 已移除）或保持为空文件。

### 6.6 视觉回归

- 启动 dev server → dark 模式查看 4 行 × 2 列布局
- 切换 light 模式确认颜色适配
- 测试约束违反场景（拖拽让 low > high）

## 7. 验收标准

- [ ] 4 行 × 2 列布局（最后一行单 metric）
- [ ] 每行共享外层边框，内部 1px 分隔线
- [ ] 每个 metric cell 包含：header (name+help+bounds) + slider + tick-row + 紧凑逻辑行
- [ ] **无 badge-input dcc.Input 元素**（移除确认）
- [ ] 拖拽 slider 是唯一的设置交互
- [ ] hover slider handle 显示 tooltip（精确值）
- [ ] 紧凑逻辑行：`0.10 ≤ X ≤ 0.15 ⟷ w=0.05`
- [ ] 约束违反：metric cell 背景泛红 + 滑轨渐变变红 + logic 行 ⚠
- [ ] 区间过窄：metric cell 背景泛黄 + handle 边框变黄
- [ ] dark / light 模式自动适配
- [ ] 仅依赖 Dash 库 · 离线运行
- [ ] 所有现有相关测试通过
- [ ] 新增测试覆盖 RANGE_ROW_GROUPS / cell IDs / 紧凑 logic / callback 路径