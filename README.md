# Professional Layout Review Tool

**专业级 SRAM/模拟电路版图Review工具**

用于 RC 提取、EM/IR 分析、信号匹配检查和自动化报告生成。

---

## 功能特性

| 模块 | 功能 | 状态 |
|------|------|------|
| 版图可视化 | 多 net 同时显示，支持缩放、平移 | ✅ |
| RC 分析 | 精确电阻电容计算，含 Net Cap 和 P2P Res | ✅ |
| 走线检查 | 长度、宽度、间距、复杂性检查 | ✅ |
| 漏孔检测 | 自动检测缺失通孔和通孔覆盖率 | ✅ |
| EM/IR 分析 | 电迁移和 IR Drop 风险评估 | ✅ |
| 信号匹配 | BL/BLB、WL 等差分对匹配度量化分析 | ✅ |
| YAML 批量导入 | 配置文件批量导入多个 shape 文件 | ✅ |
| 配置系统 | 自定义检查规则，支持正则匹配目标 net | ✅ |
| 报告导出 | PPTX 和 PDF 双格式专业报告 | ✅ |

### 支持的工艺节点

- **7nm FinFET SRAM** — 默认配置
- **5nm FinFET SRAM** — 可切换配置
- **通用模拟电路** — 可切换配置

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Layout Review Tool                  │
├─────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Dash UI     │  │ Config System│  │  Report   │ │
│  │  (Web UI)    │  │  (Rules)     │  │ Generator │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│         │                │               │          │
│         └────────────────┼───────────────┘          │
│                          ▼                          │
│              ┌─────────────────────┐                 │
│              │   Review Engine    │                 │
│              │  · RC Calculator   │                 │
│              │  · EM Analyzer     │                 │
│              │  · Matching Engine │                 │
│              │  · P2P Resistance  │                 │
│              └─────────────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### 目录结构

```
sram_layout_review/
├── layout_review_app.py    # 主应用入口（Dash Web UI）
├── review_engine.py        # 核心分析引擎
├── config_system.py        # 配置系统和技术参数
├── report_generator.py     # PPTX/PDF 报告生成
├── requirements.txt        # Python 依赖
│
├── core/                   # 核心分析模块
│   ├── rc_calculator.py   # 电阻电容计算
│   ├── em_analyzer.py     # 电迁移分析
│   ├── matching_analyzer.py # 信号匹配分析
│   ├── p2p_analyzer.py    # 点到点电阻分析
│   ├── data_parsing.py    # 数据解析
│   ├── visualization.py   # 版图可视化
│   └── path_analysis.py   # 路径分析
│
├── rules/                  # 规则插件系统
│   ├── base_rule.py       # 规则基类
│   ├── registry.py        # 规则注册中心
│   ├── drc/               # 设计规则检查
│   ├── si/                # 信号完整性规则
│   ├── em/                # 电迁移规则
│   ├── sram/              # SRAM 特定规则
│   └── qty/               # 版图质量规则
│
├── app/                    # Web UI 组件
│   ├── layout.py          # 页面布局
│   ├── callbacks.py        # 交互回调
│   ├── state.py           # 应用状态
│   └── theme.py           # 主题样式
│
├── tests/                  # 测试套件
│   ├── run_tests.py       # 功能测试
│   ├── test_rc_calculator.py
│   ├── test_polygon_distance.py
│   └── test_matching_analyzer.py
│
└── example_batch_import.yaml  # YAML 批量导入示例
```

---

## 快速开始

### 1. 安装依赖

```bash
cd sram_layout_review
pip install -r requirements.txt
```

### 2. 启动应用

```bash
./start.sh
# 或手动启动
python layout_review_app.py
```

### 3. 访问界面

打开浏览器访问 **http://localhost:8050**

---

## 使用流程

### 第一步：导入版图数据

#### 方式一：单文件导入

1. 切换到 **Layout View** 标签
2. 点击 **Select Shape Files (.txt)** 选择文件
3. 从 Net 选择器选择要显示的 net

#### 方式二：YAML 批量导入（推荐）

适用于需要批量处理多个 shape 文件的场景：

```yaml
# example_batch_import.yaml
import_mode: "batch"

options:
  auto_prefix: ""        # 为 net 名称添加前缀
  clear_existing: false   # 是否清空已有数据

shapes:
  - /path/to/shapes_20000_net1.txt
  - /path/to/shapes_20001_net2.txt
  - file: "/path/to/shapes_20002.txt"
    net_name: "CUSTOM_NET"
```

支持特性：
- ✅ 绝对路径和相对路径
- ✅ `~` 表示用户主目录
- ✅ 自定义每个文件的 net 名称
- ✅ 批量添加前缀
- ✅ 清空已有数据选项

### 第二步：配置检查规则

1. 切换到 **Configuration** 标签
2. 选择预设配置：
   - **SRAM 7nm** — 适用于 7nm FinFET SRAM
   - **SRAM 5nm** — 适用于 5nm FinFET SRAM
   - **Analog** — 适用于通用模拟电路
3. 查看和编辑检查规则（支持正则表达式）

### 第三步：运行 Layout Review

1. 切换到 **Layout Review** 标签
2. 点击 **Run Full Review**
3. 查看 Summary 和 Violations 列表
4. 检查 Matching Analysis 结果

### 第四步：导出报告

1. 切换到 **Report Export** 标签
2. 设置报告标题和输出目录
3. 选择导出格式（PPTX / PDF）
4. 点击 **Generate Reports**

---

## 检查规则

### 硬约束（Hard Constraints）

| 规则 ID | 名称 | 说明 |
|---------|------|------|
| DRC001 | Minimum Width | 走线宽度 ≥ 工艺最小宽度 |
| DRC002 | Minimum Space | 走线间距 ≥ 工艺最小间距 |
| DRC003 | Missing Via | 相邻金属层重叠区域必须存在通孔 |

### 软约束 — 信号完整性

| 规则 ID | 名称 | 阈值 |
|---------|------|------|
| SI001 | Long Wire RC | M1/M2 > 100μm, M3/M4 > 200μm |
| SI002 | High Resistance | > 100Ω |
| SI003 | High Capacitance | > 500fF |

### 软约束 — EM/IR

| 规则 ID | 名称 | 阈值 |
|---------|------|------|
| EM001 | Electromigration Risk | J > 0.8 × Jmax |
| EM002 | Power Net Width | < 0.5μm |
| EM003 | Via Current Capacity | < 2×2 array |

### SRAM 特定检查

| 规则 ID | 名称 | 阈值 |
|---------|------|------|
| SRAM001 | Bitline Matching | 长度差 < 5μm |
| SRAM002 | Wordline Matching | 长度差 < 10μm |
| SRAM003 | Control Signal Matching | Skew < 50ps |

### 版图质量

| 规则 ID | 名称 |
|---------|------|
| QTY001 | Excessive Via Chain |
| QTY002 | Via Coverage |
| QTY003 | Complex Polygon Shape |
| QTY004 | Narrow Long Wire |
| QTY005 | 90-Degree Corner |
| QTY006 | Multi-Layer Routing |

---

## 报告结构

### PPTX 报告

1. **封面页** — 标题、工艺信息、时间戳
2. **目录** — 报告内容导航
3. **Executive Summary** — 总体统计概览
4. **Net Statistics** — RC 数据表格
5. **Violation Overview** — 违规分类统计
6. **Critical Issues** — 严重问题详情
7. **Warning Issues** — 警告详情（最多 10 条）
8. **Matching Analysis** — 匹配分析汇总
9. **Matching Details** — 逐对匹配详情（最多 6 对）
10. **Net Details** — 逐Net详细分析页面
11. **Recommendations** — 改进建议
12. **结束页**

### PPTX 报告 — Net Details 页面结构

每个 net 单独一页，结构如下：

| 区域 | 内容 |
|------|------|
| **标题** | Net: XXXXX（net 名称） |
| **截图区** | 同一行放置三张截图：全貌（Fit）、密度最大区域、违例/潜在违例区域 |
| **描述区** | Layer/shapes 信息、RC 结果 |
| **结论区** | Critical / Warning / Info 数量 |

### PDF 报告

与 PPTX 相同结构，适合打印和邮件分享。

---

## 工艺参数（7nm FinFET）

| 层 | 最小宽度 | 方块电阻 | 电容/μm | 电流密度 |
|----|---------|---------|---------|---------|
| M1 | 0.032μm | 0.15Ω/□ | 0.20fF | 10mA/μm |
| M2 | 0.032μm | 0.12Ω/□ | 0.16fF | 12mA/μm |
| M3 | 0.032μm | 0.10Ω/□ | 0.14fF | 14mA/μm |
| M4 | 0.042μm | 0.08Ω/□ | 0.12fF | 18mA/μm |
| M5 | 0.056μm | 0.06Ω/□ | 0.10fF | 25mA/μm |
| M6 | 0.074μm | 0.04Ω/□ | 0.08fF | 35mA/μm |

---

## 扩展开发

### 添加自定义检查规则

1. 在 `rules/{category}/` 目录创建规则文件
2. 继承 `BaseRule` 并实现 `check()` 方法
3. 使用 `@register_rule("category")` 装饰器注册

```python
from rules.base_rule import BaseRule, ConstraintType, Severity, RuleParameter
from rules.registry import register_rule

@register_rule("drc")
class MyCustomRule(BaseRule):
    RULE_ID = "DRC999"
    NAME = "My Custom Rule"
    DESCRIPTION = "Description here"
    CONSTRAINT_TYPE = ConstraintType.HARD
    SEVERITY = Severity.CRITICAL
    TARGET_NETS = [".*"]

    def check(self, net_name: str, net_data, polygons: list) -> list:
        violations = []
        # 检查逻辑
        return violations
```

### 导出/导入配置

```python
from config_system import LayoutReviewConfig, get_sram_7nm_config

# 保存配置
config = get_sram_7nm_config()
config.save_to_file("my_config.json")

# 加载配置
config = LayoutReviewConfig.load_from_file("my_config.json")
```

---

## 运行测试

```bash
# 功能测试
python tests/run_tests.py

# 单元测试
python tests/run_tests.py --unit

# 所有测试
python tests/run_tests.py --all
```

---

## 技术栈

- **Python 3.8+**
- **Dash 2.0+** — Web UI 框架
- **Plotly 5.0+** — 可视化图表
- **python-pptx 0.6.21+** — PPTX 报告生成
- **reportlab 3.6+** — PDF 报告生成
- **numpy 1.21+** — 数值计算

---

## License

Internal Use Only

---

**Professional Layout Review Tool** — 为 SRAM 设计工程师打造的专业级版图审查工具
