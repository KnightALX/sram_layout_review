# Professional Layout Review Tool

**专业级 SRAM / 模拟电路版图 Review 工具**

RC 提取 · EM/IR 分析 · 信号匹配 · 6-metric 路由质量评估 · PPTX/PDF 报告生成

---

## 功能特性

### 通用 (两套 pipeline 共享)

| 模块 | 功能 | 状态 |
|------|------|------|
| 版图可视化 | 多 net 同时显示，支持缩放、平移、定向着色 | ✅ |
| Shape 导入 | 单文件 / YAML 批量导入（绝对路径、`~`、自定义 net 名） | ✅ |
| RC 分析 | 精确电阻电容计算 + 时序 (τ / t_pd，单位 ps) | ✅ |
| 通孔检测 | 相邻金属层缺失通孔 + 通孔覆盖率 | ✅ |
| PPTX 报告 | 封面 / Summary / Matching / Net Details / 建议 | ✅ |

### 路由质量 Review (`Routing Review` tab)

| 指标 | 说明 |
|------|------|
| **H / V Ratio** | 水平 / 垂直长度占比 (directional_analyzer) |
| **Missing Via** | 缺失通孔数 + 位置 (via_coverage) |
| **Eff. R (Ω)** | 总有效电阻 (rc_calculator) |
| **Eff. τ (ps)** | RC 时间常数，1 Ω·fF = 1 ps (effective_tau) |
| **Similarity** | 与 golden net 的 8 维特征相似度 (golden_similarity) |
| **Pass / Fail** | 三类 gate 综合：HARD / SOFT / SIMILARITY |

### 全量 Review (`Layout View` → `Run Full Review` 右侧面板)

| 模块 | 功能 | 状态 |
|------|------|------|
| DRC 检查 | Width / Space / Via 规则 | ✅ |
| SI 检查 | 长走线 / 高阻 / 高容 | ✅ |
| EM/IR 分析 | 电迁移 + IR Drop 风险 | ✅ |
| 信号匹配 | BL/BLB、WL 等差分对量化 | ✅ |
| 规则插件 | DRC / SI / EM / SRAM / QTY 五大类 | ✅ |

---

## 系统架构

本项目同时维护**两套分析 pipeline**——老的全量 review 提供 DRC/SI/EM/matching 深度检查，新的 routing review 提供 6 指标快速 gate。

```
                ┌─────────────────────────────┐
                │      Layout View tab        │  ← shape 导入 (单文件/YAML)
                │      app/callbacks.py       │
                │      app/state.py           │
                └─────────────┬───────────────┘
                              │ nets_data
                  ┌───────────┴───────────┐
                  ▼                       ▼
        ┌──────────────────────┐  ┌──────────────────────────┐
        │   LEGACY PIPELINE    │  │   ROUTING REVIEW PIPELINE│
        │                      │  │                          │
        │ review_engine        │  │ Routing Config tab       │
        │   · RC + EM          │  │   · preset YAML          │
        │   · matching         │  │   · thresholds (7)       │
        │   · P2P              │  │   · golden/batch regex   │
        │ rules/{drc,si,       │  │                          │
        │       em,sram,qty}   │  │ core/routing_metrics     │
        │   · @register_rule   │  │   · directional          │
        │                      │  │   · via_coverage         │
        │ report_generator     │  │   · rc + tau             │
        │   · PPTX + PDF       │  │   · golden_similarity    │
        │                      │  │   · check_gates          │
        │  Layout Review tab   │  │                          │
        │  (right panel)       │  │ report/routing_pptx      │
        └──────────────────────┘  │                          │
                                  │  Routing Review tab      │
                                  │  (cards + table)         │
                                  └──────────────────────────┘
```

两套 pipeline 共享输入解析（`core.data_parsing`）和可视化（`core.visualization`），但有**独立的状态对象和独立的 callback 注册**——`app_state`（`app.state`）承载 layout view 状态，`routing_state`（`app.routing_state`）承载 routing review 状态。

---

## 目录结构

```
sram_layout_review_solo/
├── layout_review_app.py        # Dash 入口，注册两套 callback
├── review_engine.py            # 核心全量 review 引擎 (legacy pipeline)
├── report_generator.py         # PPTX/PDF 报告 (legacy)
├── config_system.py            # Tech config + 19 默认规则
├── start.sh                    # 启动脚本 (./start.sh [port])
├── requirements.txt
├── example_batch_import.yaml   # YAML 批量导入示例
│
├── core/                       # 共享分析模块 (无 Dash 依赖)
│   ├── rc_calculator.py        # 电阻电容 + tau 计算
│   ├── effective_tau.py        # τ = R·C (1 Ω·fF = 1 ps)
│   ├── directional_analyzer.py # H/V 长度 + dominant
│   ├── via_coverage.py         # 缺失通孔检测 + 覆盖率
│   ├── golden_similarity.py    # 8 维特征相似度
│   ├── routing_metrics.py      # ★ 6 指标聚合器 + check_gates
│   ├── routing_violation.py    # 结构化违例
│   ├── routing_check.py        # 独立 RoutingCheckEngine (可选)
│   ├── matching_analyzer.py    # BL/BLB、WL 差分对 (legacy)
│   ├── data_parsing.py         # shape 文件 / YAML 解析
│   ├── visualization.py        # 版图可视化
│   ├── path_analysis.py        # 路径分析 (legacy)
│   └── report_visualization.py # 报告图表 (legacy)
│
├── config/                     # 路由阈值 + 预设加载
│   ├── routing_thresholds.py   # RoutingThresholds dataclass
│   ├── preset_loader.py        # YAML 加载/保存
│   └── presets/                # 用户可编辑的 YAML 预设
│       ├── sram_7nm_wl.yaml
│       ├── sram_5nm_io_bl.yaml
│       └── analog_default.yaml
│
├── report/
│   └── routing_pptx.py         # ★ 路由 review 专用 PPTX 输出
│
├── app/                        # Web UI 组件
│   ├── layout.py               # 4-tab 布局 (Layout View / Routing Config / Routing Review / Report Export)
│   ├── callbacks.py            # 旧版 callback (legacy)
│   ├── state.py                # AppState 单例
│   ├── routing_state.py        # ★ RoutingState 单例
│   ├── routing_config.py       # ★ Routing Config tab + callback
│   ├── routing_review.py       # ★ Routing Review tab + callback
│   └── theme.py                # CSS 主题 (EDA 专业风格)
│
├── rules/                      # 规则插件系统 (legacy pipeline)
│   ├── base_rule.py            # BaseRule / ConstraintType / Severity
│   ├── registry.py             # RuleRegistry + @register_rule
│   ├── drc/                    # DRC 规则
│   ├── si/                     # 信号完整性规则
│   ├── em/                     # EM 规则
│   ├── sram/                   # SRAM 特定规则
│   └── qty/                    # 版图质量规则
│
├── tests/                      # pytest 测试套件 (16 文件, 109+ 通过)
│   ├── test_routing_metrics.py # 8 个：6 指标 + check_gates (含新 gate 逻辑)
│   ├── test_routing_e2e.py     # 3 个：端到端 routing review
│   ├── test_routing_pptx.py    # 1 个：PPTX 输出
│   ├── test_routing_config_layout.py # 2 个：config tab 布局
│   ├── test_routing_thresholds.py    # 4 个
│   ├── test_routing_violation.py     # 4 个
│   ├── test_directional_analyzer.py  # 6 个
│   ├── test_effective_tau.py         # 5 个
│   ├── test_golden_similarity.py     # 6 个
│   ├── test_via_coverage.py          # 4 个
│   ├── test_preset_loader.py         # 4 个
│   ├── test_visualization_directional.py # 4 个
│   └── ... (3 个 unittest 风格)
│
├── assets/                     # 本地 Bootstrap + Font Awesome CSS
│   ├── bootstrap.min.css
│   ├── bootstrap.bundle.min.js
│   └── font-awesome.min.css
│
└── pdk/                        # PDK 文件 (display.drf, tsmcN7.layermap, techfile)
```

---

## 快速开始

### 1. 安装依赖

```bash
cd sram_layout_review_solo
pip install -r requirements.txt
```

### 2. 启动应用

```bash
./start.sh                   # 默认 8050 端口
./start.sh 8080              # 指定端口
# 或
python3 layout_review_app.py 8050
```

> **Windows 用户**：`./start.sh` 需要 Git Bash 或 WSL；或者直接用 `python layout_review_app.py 8050`（注意是 `python` 而非 `python3`）。

### 3. 访问界面

打开浏览器 → **http://localhost:8050**

---

## 四 Tab 工作流

| Tab | 用途 | 关键操作 |
|-----|------|----------|
| **Layout View** | Shape 导入 + 旧版 review | 上传 .txt / YAML，选 net，右面板 Run Full Review |
| **Routing Config** | 路由 review 配置 | 选 preset，调 7 项 threshold，设 golden/batch regex |
| **Routing Review** | 路由 review 结果 | 6 指标卡 + 排序表 + 定向可视化 + PPTX 下载 |
| **Report Export** | 旧版报告导出 | 设置标题/输出目录，生成 PPTX / PDF |

### 完整 Routing Review 流程（推荐起点）

1. **Layout View** → 上传 shape 文件或 YAML 批量配置 → net 选择器显示已加载 net
2. **Routing Config** →
   - 选 preset（默认 `sram_7nm_wl`）
   - 调整 7 项 threshold（max_h_ratio / max_v_ratio / max_r_ohm / max_c_ff / max_tau_ps / min_via_coverage / min_similarity）
   - 点 **Use first net as golden** 一键填 golden regex
   - 点 **Use all loaded nets (batch)** 一键填 batch regex
   - 点 **Run Routing Review**（或上一步两个按钮任一会自动 run）
3. **Routing Review** → 自动跳转到本 tab：
   - 6 张卡片显示 batch 内 min–max 数据范围 + pass/fail 计数
   - 每 net 一行的可排序表，Pass 列绿色 ✓ / 红色 ✗ 圆角 pill
   - 定向可视化（H 红 / V 蓝）+ missing via 标红
4. 点 **Generate Routing Report (PPTX)** 下载 `routing_report.pptx`

---

## 路由 Review 详解

### 6 指标定义

| 指标 | 计算 | 阈值 (sram_7nm_wl) |
|------|------|--------------------|
| H Ratio | 水平长度 / 总长 | ≤ 0.15 |
| V Ratio | 垂直长度 / 总长 | ≤ 1.00 |
| R Total | Σ 金属层电阻 (Ω) | ≤ 100 |
| C Total | Σ 寄生电容 (fF) | ≤ 500 |
| τ (ps) | R × C（1 Ω·fF = 1 ps） | ≤ 12.5 |
| Via Cov | 已布通孔 / 应有通孔 | ≥ 0.85 |
| Similarity | 与 golden 8 维特征相似度 | ≥ 80 |

### Gate 逻辑：HARD / SOFT / SIMILARITY 三类

`check_gates()` 在 `core/routing_metrics.py` 中实现，按违例性质分三类：

| 类别 | 包含 | 是否可被 golden 相似度绕过 |
|------|------|---------------------------|
| **HARD** | missing_via, R, C, τ | ❌ 永远不可 |
| **SOFT** | h_ratio, v_ratio, via_coverage | ✅ 当 `has_golden=True` 且 `similarity ≥ min_similarity` |
| **SIMILARITY** | similarity_score | ❌ 永远不可 |

**Pass 规则**：

```
PASS = NOT (HARD_fail OR SIMILARITY_fail) AND
       NOT (SOFT_fail AND NOT (has_golden AND similarity ≥ min_similarity))
```

举例：horizontal-only golden + horizontal-only batch net → 软 h_ratio 违例被相似度绕过 → PASS；但 R 超过 100Ω → HARD 违例 → 仍然 FAIL。

### Routing 预设

`config/presets/` 下 3 个 YAML 预设，可在线编辑或本地修改：

| Preset | 用途 | max_h | max_v | min_sim |
|--------|------|-------|-------|---------|
| `sram_7nm_wl` | 7nm 字线（V-dominant 走线） | 0.15 | 1.00 | 80 |
| `sram_5nm_io_bl` | 5nm IO/位线（H-dominant） | 1.00 | 0.10 | 80 |
| `analog_default` | 通用模拟（均衡） | 0.60 | 0.60 | 70 |
| `power_relaxed` | 电源/地（最宽松） | 1.00 | 1.00 | 0 |

> `power_relaxed` 是 `RoutingThresholds` 内置的代码预设，YAML 文件未提供（设计上鼓励手动覆盖）。

---

## Shape 导入格式

### 单文件 (.txt)

每行一段矩形：

```
layer  x1  y1  x2  y2  net_name
M1     0   0   10  1   WL0
M2     5   0   6   10  WL0
```

### YAML 批量导入 (`example_batch_import.yaml`)

```yaml
import_mode: "batch"

options:
  auto_prefix: ""         # 给所有 net 名称加前缀
  clear_existing: false    # 是否清空已有数据

shapes:
  - /abs/path/to/shapes_20000_net1.txt
  - /abs/path/~/shapes_20001_net2.txt
  - file: "/abs/path/shapes_20002.txt"
    net_name: "CUSTOM_NET"  # 自定义 net 名（覆盖文件内）
```

支持：绝对路径、`~`、相对路径、自定义 net 名、批量前缀、清空选项。

---

## 工艺参数 (7nm FinFET SRAM 默认)

| 层 | 最小宽度 | 方块电阻 | 电容/μm | 电流密度 |
|----|---------|---------|---------|---------|
| M1 | 0.032 μm | 0.15 Ω/□ | 0.20 fF | 10 mA/μm |
| M2 | 0.032 μm | 0.12 Ω/□ | 0.16 fF | 12 mA/μm |
| M3 | 0.032 μm | 0.10 Ω/□ | 0.14 fF | 14 mA/μm |
| M4 | 0.042 μm | 0.08 Ω/□ | 0.12 fF | 18 mA/μm |
| M5 | 0.056 μm | 0.06 Ω/□ | 0.10 fF | 25 mA/μm |
| M6 | 0.074 μm | 0.04 Ω/□ | 0.08 fF | 35 mA/μm |

---

## 扩展开发

### 添加路由指标或新阈值字段

1. 在 `config/routing_thresholds.py` 的 `RoutingThresholds` dataclass 添加字段，并写入 `_BUILTIN_PRESETS`
2. 在 `core/routing_metrics.py` 的 `check_gates` 中加入 gate 逻辑
3. 在 `app/routing_config.py` 的 `THRESHOLD_FIELDS` 中加 `(name, label, min, max, step)` 元组 — `dcc.Input` 会自动布线
4. 在 `app/routing_review.py` 的 `METRIC_CARD_IDS` 中加卡片定义，并在 `_build_metric_cards` 的 averaging 块加平均逻辑
5. 更新每个 `config/presets/*.yaml`

### 添加新规则 (legacy pipeline)

每个 category 的所有规则堆在 `rules/{category}/__init__.py` 里（**不是每规则一个文件**）。`RuleRegistry` 通过 `rules/__init__.py` 的 `_auto_import_rules()` 自动发现。

```python
# rules/drc/__init__.py
from rules.base_rule import BaseRule, ConstraintType, Severity
from rules.registry import register_rule

@register_rule("drc")
class MyNewRule(BaseRule):
    RULE_ID = "DRC999"
    NAME = "My Custom Rule"
    SEVERITY = Severity.CRITICAL
    TARGET_NETS = [".*"]   # regex

    def check(self, net_name, net_data, polygons):
        violations = []
        # 你的检查逻辑
        return violations
```

规则在 import 时被加载，所以新增规则后需要重启进程。

---

## 运行测试

```bash
# 全部测试 (推荐)
python -m pytest tests/ -q
# 109 通过，3 失败 (test_polygon_distance.py × 2, test_rc_calculator.py::test_via_creation — 与本项目无关的预存在失败)

# 单个测试
python -m pytest tests/test_routing_metrics.py::test_compute_for_net_returns_all_six_metrics -v

# 路由 check engine (绕过 core/__init__.py 重导出链)
python run_routing_check_tests.py

# 老式功能性测试 + unittest (仍可用)
python tests/run_tests.py --all
```

### 端到端测试 3 件套 (`tests/test_routing_e2e.py`)

- `test_wordline_wl_preset_h_dominant_passes` — WL preset (max_v=1.0) + V-dominant net (5μm 垂直) → 软 h_ratio 违例被相似度绕过 → pass
- `test_io_bl_preset_v_dominant_passes` — IO/BL preset (max_h=1.0) + H-dominant net (5μm 水平) → 同上
- `test_long_wire_fails_tau_gate` — 1000μm 长走线超过 τ 上限 → HARD 违例 → fail

---

## UI 主题

`app/theme.py` 提供 Cadence-Virtuoso 风格的 EDA 主题：

- `.card` / `.card-header` — 顶部细线强调 + 提升阴影
- `.metric-card` / `.metric-card.pass` / `.metric-card.fail` — 路由 review 指标卡
- `.eda-tabs .tab` / `.tab--selected` — 标签页样式
- `.dash-spreadsheet-container` — 表格分离边框 + hover 高亮
- `.badge-pass` / `.badge-fail` / `.panel-tab .count.{error,warning,info}` — 状态徽章
- 完整 `:focus-visible` / `:active` / `:disabled` 按钮态

UI 故意保持**极简**——per-net 结果表只对 Pass 列做绿色 ✓ / 红色 ✗ 圆角 pill，无数据条或行级 tint。

---

## 技术栈

- **Python 3.8+**
- **Dash 2.0+** — Web UI 框架
- **Plotly 5.0+** — 可视化图表
- **python-pptx 0.6.21+** — PPTX 报告生成
- **reportlab 3.6+** — PDF 报告生成（旧 pipeline）
- **PyYAML** — preset / batch import
- **numpy 1.21+** — 数值计算

---

## 项目状态

- **2026-06-01**: Routing review rewrite (Phase 1–5) 完成。6 指标聚合器 + HARD/SOFT/SIMILARITY gate 逻辑、YAML 预设、4 tab 布局、EDA 主题。
- **测试**: 112 收集，109 通过，3 预存在失败。
- **下次迭代**: Via 支持接入 `core.routing_metrics`（当前 `vias=[]` 占位），polygon-as-via 自动转换已写好。

---

## License

Internal Use Only

---

**Professional Layout Review Tool** — 为 SRAM 设计工程师打造的专业级版图审查工具
