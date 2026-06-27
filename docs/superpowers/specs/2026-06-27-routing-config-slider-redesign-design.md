# 2026-06-27 Routing Config Range Slider UI Redesign — Design Spec

## 0. 背景与目标

`app/routing_config.py` 中的 Range Slider UI 当前实现存在以下问题：

1. **视觉简陋** — 仅一个 `form-label` + `dcc.RangeSlider` + 两个独立 `dcc.Input`，无视觉分隔、无层次，与项目主体的 metric-card / accent 风格脱节。
2. **比例失衡** — Slider 撑满整行但数值输入被挤压到下方窄条，拖拽手柄与数值展示区视觉权重不对等。
3. **逻辑不清** — "什么算合规、当前设置了什么、约束被违反了" 全部依赖用户对照阅读数值，没有任何显式语义提示。
4. **缺乏模式适配** — 当前样式硬编码 dark 配色，light 模式下颜色与背景对比不足。
5. **DCC RangeSlider 默认 marks 稀薄** — 只有 min/mid/max 三个刻度，无法感知"低值区"或"高值区"的边界含义。

**本 spec 目标**：

- 单列卡片堆叠：每 metric 独立一行，使用 **Accent Strip** 风格（左侧 3px accent 边条 + 浅渐变背景 + 柔和阴影）
- **数值徽章替代数字输入框**：拖拽 Slider 手柄即可设置；点击徽章原地切换为 `dcc.Input` 精确编辑（Enter/blur 确认，Esc 取消）
- Slider ↔ Badge 双向实时同步
- **合规区间数学表达**：每行底部以 `合规: low ≤ X ≤ high ⟷ 区间宽度 w` 显示当前语义
- Slider 填充区用渐变色高亮当前合规区间
- 约束违反时：左侧 accent 边转 fail/warning 色 · 徽章边框转状态色 · 底部逻辑行 ⚠ 提示
- 完全基于项目现有 `eda-theme.css` CSS 变量，自动适配 dark / light 模式
- 仅依赖 Dash 库，无任何额外前端依赖，离线可运行

参考 mockup：`docs/mockups/slider-option-b-bimodal.html`

## 1. 范围

| 范围项 | 包含 |
|---|---|
| UI 组件 | `app/routing_config.py` 的 `_build_range_input_group` 重写 |
| CSS | `assets/eda-theme.css` 新增 `.slider-row`、`.range-slider-badge`、`.range-slider-track` 等样式块 |
| 回调 | 现有 slider↔input 同步回调（14 个）改写为 slider↔badge 同步；新增 badge 编辑态切换逻辑 |
| 测试 | 现有 slider/input 渲染与同步测试更新；新增 badge 编辑态测试 |
| 文档 | 无（视觉调整） |
| 不动 | `config/routing_thresholds.py` 的 `Range` 数据模型；`preset_loader.py`；`routing_state.py`；其他 tab；preset YAML 文件 |

## 2. 视觉规范

### 2.1 单行 Slider Row 结构

```
┌──────────────────────────────────────────────────────────────────┐
│▌ Horizontal Ratio — 横向走线占比        bounds [0.00, 1.00]      │  ← row-header
│▌                                                                │
│▌  ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●      │  ← slider
│▌  0.00                  0.50                  1.00              │  ← tick-row
│▌                                                                │
│▌  ┌──────────────────────┐   ┌──────────────────────┐           │  ← badges
│▌  │ LOW      0.10        │   │ HIGH      0.15       │           │
│▌  └──────────────────────┘   └──────────────────────┘           │
│▌                                                                │
│▌  合规: 0.10 ≤ X ≤ 0.15  ⟷  区间宽度 0.05                       │  ← logic row
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 关键 CSS 变量（复用 eda-theme.css 已有的 token）

| 用途 | CSS 变量 | dark | light |
|---|---|---|---|
| 卡片底色 | `--bg-secondary` | `#16213e` | `#ffffff` |
| 卡片描边 | `--border-primary` | `#2d4a6f` | `#cbd5e1` |
| 强调主色（左侧条、handle 边框） | `--accent-primary` | `#3b82f6` | `#2563eb` |
| 强调副色（slider 填充右端、徽章 key） | `--accent-secondary` | `#06b6d4` | `#0891b2` |
| 数值文字 | `--text-primary` | `#e2e8f0` | `#1e293b` |
| 数值副文字（key/单位） | `--text-muted` | `#64748b` | `#94a3b8` |
| 失败色 | `--status-fail` | `#ef4444` | `#ef4444` |
| 警告色 | `--status-warning` | `#f59e0b` | `#f59e0b` |
| 间距 | `--space-xs/sm/md/lg` | 4/8/12/16 px | 同 |
| 圆角 | `--radius-md/lg` | 4/6 px | 同 |
| 字体 | `--font-data` (JetBrains Mono) / `--font-body` (IBM Plex Sans) | — | — |

### 2.3 新增 CSS 块（追加到 `assets/eda-theme.css` 末尾）

```css
/* ============================================================
   Range Slider Row (Routing Config)
   ============================================================ */
.slider-row {
    background: linear-gradient(90deg,
        rgba(59, 130, 246, 0.10) 0%,
        rgba(6, 182, 212, 0.02) 100%);
    border: 1px solid var(--border-primary);
    border-left: 3px solid var(--accent-primary);
    border-radius: var(--radius-md);
    padding: var(--space-md);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18);
    margin-bottom: var(--space-md);
    transition: border-left-color 0.2s ease, box-shadow 0.2s ease;
}
.slider-row:hover { border-left-color: var(--accent-secondary); }
.slider-row.is-invalid { border-left-color: var(--status-fail); }
.slider-row.is-warning { border-left-color: var(--status-warning); }
.slider-row:last-child { margin-bottom: 0; }

.slider-row .row-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: var(--space-sm);
}
.slider-row .row-header .name {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
}
.slider-row .row-header .help {
    font-weight: 400;
    color: var(--text-muted);
    font-size: 11px;
    margin-left: var(--space-sm);
}
.slider-row .row-header .bounds {
    font-family: var(--font-data);
    font-size: 10px;
    color: var(--text-muted);
}
.slider-row .row-header .bounds b {
    color: var(--accent-secondary);
    font-weight: 500;
}

.slider-row .tick-row {
    position: relative;
    height: 12px;
    font-family: var(--font-data);
    font-size: 9px;
    color: var(--text-muted);
    margin-top: 2px;
}
.slider-row .tick-row span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.slider-row .tick-row span:first-child { left: 0; transform: none; }
.slider-row .tick-row span:last-child  { right: 0; left: auto; transform: none; }
.slider-row .tick-row span.mid         { left: 50%; }

.slider-row .badges { display: flex; gap: var(--space-sm); margin-top: var(--space-sm); }
.range-slider-badge {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    font-family: var(--font-data);
    font-size: 12px;
    cursor: text;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.range-slider-badge:hover {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.range-slider-badge .key {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent-secondary);
    font-weight: 600;
}
.range-slider-badge .val {
    color: var(--text-primary);
    font-weight: 500;
}
.range-slider-badge .unit {
    color: var(--text-muted);
    font-size: 10px;
    margin-left: 2px;
}
.range-slider-badge.is-editing {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.20);
    background: var(--bg-tertiary);
}
.range-slider-badge.is-invalid {
    border-color: var(--status-fail);
    box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.15);
}
.range-slider-badge.is-invalid .key { color: var(--status-fail); }
.range-slider-badge.is-warning {
    border-color: var(--status-warning);
}
.range-slider-badge.is-warning .key { color: var(--status-warning); }

.slider-row .logic {
    margin-top: var(--space-sm);
    font-family: var(--font-data);
    font-size: 10px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: var(--space-xs);
}
.slider-row .logic .ic { color: var(--accent-secondary); font-weight: 500; }
.slider-row .logic code {
    background: var(--bg-tertiary);
    color: var(--accent-secondary);
    padding: 1px 6px;
    border-radius: var(--radius-sm);
}
.slider-row .logic.is-invalid { color: var(--status-fail); }
.slider-row .logic.is-invalid code { background: rgba(239, 68, 68, 0.12); color: var(--status-fail); }
.slider-row .logic.is-warning { color: var(--status-warning); }
.slider-row .logic.is-warning code { background: rgba(245, 158, 11, 0.12); color: var(--status-warning); }

/* Light mode 调整 */
.theme-light .slider-row {
    background: linear-gradient(90deg,
        rgba(37, 99, 235, 0.07) 0%,
        rgba(8, 145, 178, 0.015) 100%);
    box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15), 0 1px 2px rgba(15, 23, 42, 0.06);
}
.theme-light .range-slider-badge:hover { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18); }
.theme-light .range-slider-badge.is-editing { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.22); }
.theme-light .range-slider-badge.is-invalid { box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.18); }

/* Dash RangeSlider 内部元素覆盖（仅样式，不改功能） */
.rc-slider { margin: 6px 0 !important; }
.rc-slider-rail { background: var(--bg-elevated) !important; height: 6px !important; }
.rc-slider-track { background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary)) !important; height: 6px !important; }
.rc-slider-handle {
    width: 18px !important; height: 18px !important;
    background: var(--bg-secondary) !important;
    border: 2px solid var(--accent-primary) !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5) !important;
    margin-top: -7px !important;
}
.rc-slider-handle::after {
    content: ''; position: absolute; top: 50%; left: 50%;
    width: 4px; height: 4px;
    background: var(--accent-primary); border-radius: 50%;
    transform: translate(-50%, -50%);
}
.theme-light .rc-slider-handle { box-shadow: 0 1px 3px rgba(15, 23, 42, 0.20) !important; }
.rc-slider-mark-text { color: var(--text-muted) !important; font-size: 9px !important; font-family: var(--font-data) !important; }
```

### 2.4 dark/light 模式验证

- dark 模式：accent 蓝渐变在深色卡片上对比强；徽章底色 `--bg-primary`（更深的 `#1a1a2e`）与卡片底色 `--bg-secondary`（`#16213e`）形成微对比，徽章自然浮起
- light 模式：accent 蓝渐变在白卡上仍然清晰；徽章底色 `--bg-primary`（浅灰 `#f8fafc`）与卡片底色 `--bg-secondary`（白 `#ffffff`）形成微对比，符合"层级而非装饰"的扁平化美学

## 3. 组件结构

### 3.1 `_build_range_input_group(field)` 新实现

```python
def _build_range_input_group(field):
    """
    Build a single range-setting row: header + RangeSlider + tick-row +
    badges (Low/High) + logic annotation.
    """
    from dash import dcc, html
    name, label = field["name"], field["label"]
    help_text = field.get("help", "")
    unit = field.get("unit", "")
    fmt = field["fmt"]
    rng = getattr(routing_state.get_thresholds(), name)
    s_min, s_max, step = field["slider_min"], field["slider_max"], field["step"]

    bounds_text = f"[{fmt.format(s_min)}, {fmt.format(s_max)}]"

    return html.Div([
        # Row header: name + help + bounds info
        html.Div([
            html.Span([
                html.Span(label, className="name"),
                html.Span(f" — {help_text}", className="help") if help_text else None,
            ]),
            html.Span([
                "bounds ",
                html.B(bounds_text),
                f" {unit}".rstrip(),
            ], className="bounds"),
        ], className="row-header"),

        # RangeSlider (no marks — we render ticks below for control)
        dcc.RangeSlider(
            id=f"slider-{name}",
            min=s_min, max=s_max, step=step,
            value=[rng.low, rng.high],
            marks=None,                          # 自定义 ticks 由我们渲染
            tooltip={"placement": "bottom", "always_visible": False},
            allowCross=False,
            className="range-slider",
        ),

        # Custom tick row (3 labels: min, mid, max)
        html.Div([
            html.Span(fmt.format(s_min)),
            html.Span(fmt.format((s_min + s_max) / 2), className="mid"),
            html.Span(fmt.format(s_max)),
        ], className="tick-row"),

        # Badges (Low / High) — clickable to enter edit mode
        html.Div([
            html.Div([
                html.Span("Low", className="key"),
                html.Span([
                    html.Span(fmt.format(rng.low), className="val",
                             id=f"badge-{name}-low-text"),
                    html.Span(unit, className="unit") if unit else None,
                ]),
            ], id=f"badge-{name}-low", className="range-slider-badge",
               **{"data-field": name, "data-bound": "low"}),

            html.Div([
                html.Span("High", className="key"),
                html.Span([
                    html.Span(fmt.format(rng.high), className="val",
                             id=f"badge-{name}-high-text"),
                    html.Span(unit, className="unit") if unit else None,
                ]),
            ], id=f"badge-{name}-high", className="range-slider-badge",
               **{"data-field": name, "data-bound": "high"}),
        ], className="badges"),

        # Hidden inputs (only visible when badge is in edit mode)
        dcc.Input(id=f"badge-input-{name}-low", type="number",
                  value=rng.low, min=s_min, max=s_max, step=step,
                  className="range-slider-badge-input",
                  style={"display": "none"}),
        dcc.Input(id=f"badge-input-{name}-high", type="number",
                  value=rng.high, min=s_min, max=s_max, step=step,
                  className="range-slider-badge-input",
                  style={"display": "none"}),

        # Logic annotation row
        html.Div([
            html.Span("合规: "),
            html.Code(f"{fmt.format(rng.low)} ≤ X ≤ {fmt.format(rng.high)}"),
            html.Span(" ⟷ ", className="ic"),
            html.Span("区间宽度 "),
            html.Code(fmt.format(rng.high - rng.low)),
        ], id=f"logic-{name}", className="logic"),
    ], id=f"row-{name}", className="slider-row",
       **{"data-field": name})
```

### 3.2 `RANGE_FIELDS` 扩展

每个 field 增加 `help`（中文副标题）与 `unit`（单位）字段：

```python
RANGE_FIELDS = [
    {
        "name": "h_ratio",      "label": "Horizontal Ratio",
        "help": "横向走线占比",  "unit": "",
        "slider_min": 0.0, "slider_max": 1.0, "step": 0.01,
        "fmt": "{:.2f}",
    },
    {
        "name": "v_ratio",      "label": "Vertical Ratio",
        "help": "纵向走线占比",  "unit": "",
        "slider_min": 0.0, "slider_max": 1.0, "step": 0.01,
        "fmt": "{:.2f}",
    },
    {
        "name": "r_ohm",        "label": "Resistance",
        "help": "走线电阻",      "unit": "Ω",
        "slider_min": 0, "slider_max": 10000, "step": 50,
        "fmt": "{:g}",
    },
    {
        "name": "c_ff",         "label": "Capacitance",
        "help": "走线电容",      "unit": "fF",
        "slider_min": 0, "slider_max": 100000, "step": 100,
        "fmt": "{:g}",
    },
    {
        "name": "tau_ps",       "label": "Delay (Tau)",
        "help": "信号延迟",      "unit": "ps",
        "slider_min": 0, "slider_max": 1000, "step": 5,
        "fmt": "{:g}",
    },
    {
        "name": "via_coverage", "label": "Via Coverage",
        "help": "通孔覆盖率",    "unit": "",
        "slider_min": 0.0, "slider_max": 1.0, "step": 0.01,
        "fmt": "{:.2f}",
    },
    {
        "name": "similarity",   "label": "Similarity",
        "help": "走线相似度",    "unit": "",
        "slider_min": 0.0, "slider_max": 1.0, "step": 0.01,
        "fmt": "{:.2f}",
    },
]
```

### 3.3 外层容器调整

将原来单纯的 `flex column` 容器调整为带顶部说明的 panel 结构：

```python
# Routing Config Tab — Range Slider 区域
html.Div([
    html.Div("阈值区间 (Closed Interval)", className="section-header"),
    html.Div("拖拽手柄粗调 · 点击 Low/High 徽章精确输入", className="section-subheader"),
    html.Div([
        _build_range_input_group(field) for field in RANGE_FIELDS
    ], id="routing-config-ranges", className="ranges-container"),
], className="config-section")
```

新增 CSS：
```css
.config-section { margin-bottom: var(--space-xl); }
.config-section .section-header {
    font-size: 11px; text-transform: uppercase;
    letter-spacing: 0.08em; color: var(--text-secondary);
    font-weight: 600; margin-bottom: var(--space-xs);
}
.config-section .section-subheader {
    font-size: 11px; color: var(--text-muted);
    margin-bottom: var(--space-lg); font-style: italic;
}
.ranges-container { display: flex; flex-direction: column; gap: 0; }
```

## 4. 交互模型

### 4.1 Slider ↔ Badge 双向同步

**已存在的回调**（在第一期 redesign 中实现）：`_sync_slider_to_input` / `_sync_input_to_slider`

**改造方案**：
- 保留 14 个 slider↔input 同步回调（结构不变，仅 ID 前缀与目标 element 变化）
- `_sync_slider_to_<field>_low/high`：更新对应 badge 的 `children` 而非 input 的 `value`
- `_sync_input_to_slider_<field>`：input 更新 → slider 更新（保持不变）
- 新增 `_update_badge_text_<field>`：badge 文本 + 徽章 + logic row 内容同步刷新

### 4.2 Badge 编辑态切换

通过 clientside callback（推荐，避免服务端 round-trip 延迟）：

```javascript
// clientside callback: 点击 badge → 显示对应 input，隐藏 badge val
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    routing_config: {
        enterBadgeEdit: function(n_clicks_low, n_clicks_high, ...) {
            // 显示 #badge-input-{field}-low，隐藏 #badge-{field}-low
            // 触发自动 focus
            return [/* low input style */, /* high input style */,
                    /* low badge style */, /* high badge style */];
        }
    }
});
```

**简化方案（首选）**：使用 Dash pattern-matching callback + dcc.Input 的 `debounce=True`，badge 仅作为展示组件，点击触发 input 显示，input 失焦或 Enter 后写回。

**最终实现**：

1. 每个 row 包含 1 个 `RangeSlider` + 2 个 badge（div）+ 2 个隐藏 `dcc.Input`
2. **新增**两个 `html.Button` "edit-low" / "edit-high"（覆盖在 badge 区域，点击触发切换）
3. callback：`edit-low` n_clicks → 显示 input-low，隐藏 badge-low-text
4. callback：input-low `value` 变化（debounce）→ 写回 slider value，更新 badge text，隐藏 input
5. callback：`blur` 事件由 dcc.Input 的 `n_submit` + `n_blur` 处理

**为简化**：badge 上挂一个透明的 `dcc.Input`（仅 type=number），点击 badge 等同于点击 input。提交（Enter/blur）后更新 slider 与 badge text。

实际选型：**在 badge 内部嵌套一个透明 dcc.Input**（始终渲染，但视觉上叠加在 `.val` 上）。点击 badge → input 获得焦点 → 直接键入。Enter/blur → 提交（debounce）。

```python
html.Div([  # badge
    html.Span("Low", className="key"),
    dcc.Input(
        id=f"badge-input-{name}-low",
        type="number", value=rng.low, min=s_min, max=s_max, step=step,
        debounce=True,             # Enter/blur 才提交
        className="badge-input-overlay",  # 透明叠加在 .val 上
    ),
], className="range-slider-badge")
```

```css
.badge-input-overlay {
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-family: var(--font-data);
    font-size: 12px;
    text-align: right;
    width: 60px;
    padding: 0;
    outline: none;
}
.badge-input-overlay:focus {
    color: var(--accent-primary);
    font-weight: 600;
}
.range-slider-badge:has(.badge-input-overlay:focus) {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.20);
    background: var(--bg-tertiary);
}
```

> 注：`:has()` 选择器兼容性：Chrome 105+, Safari 15.4+, Firefox 121+。Dash 内置浏览器为现代浏览器，使用 chromium-based webview，无兼容性问题。

### 4.3 约束违反检测

在 slider 的 value callback 中检查：

- `value[0] > value[1]` → `is-invalid`（low > high，逻辑不可能）
- `value[0] == value[1]` → `is-warning`（单点区间，无宽度，几乎所有值都不合规）
- `value[1] - value[0] < (max - min) * 0.05` → `is-warning`（区间过窄）

callback 输出同步更新：
- `row-{name}` 的 `className`（追加 `is-invalid` / `is-warning`）
- `badge-{name}-low/high` 的 `className`（追加 `is-invalid` / `is-warning`）
- `logic-{name}` 的 `children` 与 `className`（显示警告文本或保持合规区间）

### 4.4 底部 Logic Row 文案规则

| 状态 | 文案 |
|---|---|
| 合规 | `合规: {low} ≤ X ≤ {high}  ⟷  区间宽度 {width}` |
| 警告（区间过窄） | `⚠ 区间过窄 ({width})，可能误杀合规走线  ·  建议扩大区间` |
| 警告（low == high） | `⚠ 区间宽度为 0，无任何值合规  ·  请调整 Low < High` |
| 失败（low > high） | `⚠ Low ({low}) > High ({high})，区间不合法  ·  请重新设置` |

### 4.5 Unit 显示

仅当 `field["unit"]` 非空时显示，例如：
- Resistance: `Low 500 Ω`
- Capacitance: `Low 60000 fF`
- Horizontal Ratio: `Low 0.10`（无单位）

## 5. 数据流

```
[Preset YAML / Custom dict]
        │
        ▼
[RoutingThresholds: 7 × Range]   ◄─── 数据模型不变
        │
        ▼
[_build_range_input_group(field)]
        │
        ├──► dcc.RangeSlider (id=slider-{name})
        ├──► dcc.Input (id=badge-input-{name}-low)   ← 透明叠加
        ├──► dcc.Input (id=badge-input-{name}-high)  ← 透明叠加
        ├──► html.Span (id=badge-{name}-low-text)    ← 视觉显示
        ├──► html.Span (id=badge-{name}-high-text)
        └──► html.Div (id=logic-{name})              ← 合规区间提示

[用户拖拽 Slider]
        │
        ▼
[callback _sync_slider_{name}]
        │
        ├──► 更新 badge-{name}-low-text/high-text 的 children
        ├──► 更新 badge-input-{name}-low/high 的 value
        ├──► 更新 logic-{name} 的 children
        └──► 更新 row-{name} 的 className (合规/警告/失败)

[用户键入 badge input (Enter/blur)]
        │
        ▼
[callback _sync_input_{name}]
        │
        ├──► 更新 slider-{name} 的 value
        └──► (后续同 slider 触发的下游更新)
```

## 6. 测试策略

### 6.1 单元测试（`tests/test_routing_config.py`）

保留/更新现有测试，新增：

- `test_build_range_input_group_contains_header_bounds_help` — header 包含 label + help + bounds
- `test_build_range_input_group_contains_tick_row` — tick-row 包含 min/mid/max 三个 span
- `test_build_range_input_group_contains_two_badges` — 包含 low/high 两个 badge
- `test_build_range_input_group_contains_two_badge_inputs` — 包含两个透明叠加 input
- `test_build_range_input_group_contains_logic_row` — logic-row 包含合规区间与宽度
- `test_build_range_input_group_unit_display` — unit 字段正确显示
- `test_build_range_input_group_no_unit_omits_unit_span` — 无 unit 字段时不显示 unit span
- `test_routing_config_layout_has_section_header` — 顶层容器包含 section header

### 6.2 回调测试（`tests/test_routing_config_callbacks.py`）

- `test_sync_slider_to_badges_updates_text_and_logic` — 拖拽 slider → badge text + logic row 同步
- `test_sync_input_to_slider_updates_slider_value` — input debounce 提交 → slider 跟随
- `test_invalid_range_marks_row_as_invalid` — low > high → row className 含 `is-invalid`
- `test_zero_width_range_marks_row_as_warning` — low == high → row className 含 `is-warning`
- `test_narrow_range_marks_row_as_warning` — width < 5% 全域 → warning
- `test_valid_range_keeps_row_clean` — 合规时 row className 不含 invalid/warning

### 6.3 视觉回归（手动）

- 启动 dev server → dark 模式查看 7 个 metric row → light 模式查看
- 拖拽每个 slider 验证 badge 实时更新
- 在 badge 上键入数值验证 slider 跟随
- 测试约束违反场景（low > high、窄区间、单点）
- 与 mockup `slider-option-b-bimodal.html` 对比确认无明显差异

### 6.4 现有测试保留

- 所有 slider/value 同步测试需更新断言 ID（`slider-{name}` 不变，但 badge 与 logic ID 是新的）
- 所有 ID/结构断言需更新以匹配新的 HTML 结构

## 7. 验收标准

- [ ] 单列卡片堆叠 · 每行 metric 包含 header + slider + tick-row + 2 个 badge + logic row
- [ ] 左侧 3px accent 边条 · accent-strip 视觉风格 · 与 mockup 一致
- [ ] dark / light 模式自动适配 · 无任何硬编码颜色
- [ ] 拖拽 Slider → badge 数值 + logic 行实时同步
- [ ] 点击 badge → 直接键入数字 · Enter/blur 提交 · slider 跟随
- [ ] Slider 填充区显示当前合规区间（accent 渐变）
- [ ] 约束违反检测：low > high → invalid；区间过窄 → warning
- [ ] 底部 logic row 显示 `合规: low ≤ X ≤ high ⟷ 区间宽度 w`
- [ ] 单位正确显示（Ω / fF / ps）
- [ ] 所有现有测试通过
- [ ] 新增测试 ≥ 8 个，覆盖新结构与约束检测
- [ ] 仅依赖 Dash 库 · 离线可运行 · 无外部前端资源
- [ ] 全部代码、文档使用项目统一语言风格（docstring 英文、UI 文案中文）