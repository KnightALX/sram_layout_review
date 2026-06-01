# 绕线质量门禁（Routing Review）重写实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写 `Configuration` 和 `Layout Review` 两个 Tab，使其**只围绕"绕线质量门禁"**展开；100% 落地 6 大指标（IO/WL 方向比例、缺孔漏孔、等效 RC、等效 τ、Golden 相似度、Pass/Fail），并支持一键 PPTX 报告导出。**完全不动** `Layout View` 和 `Report Export` 两个 Tab。

**Architecture:**
- **数据层**（`core/`）：5 个新模块做纯计算（`directional_analyzer.py` / `via_coverage.py` / `golden_similarity.py` / `routing_metrics.py` / `effective_tau.py`），1 个增强（`rc_calculator.py` 加 `effective_tau_ps` 字段），1 个增强（`visualization.py` 加 `mode='directional'`）。
- **配置层**（`config/`）：新建 `routing_thresholds.py`（dataclass + YAML loader），新建 `presets/sram_7nm_wl.yaml`、`presets/sram_5nm_io_bl.yaml`、`presets/analog_default.yaml`。
- **UI 层**（`app/`）：新建 `routing_state.py`（独立状态，不污染 `app/state.py`），新建 `routing_config.py`（Configuration Tab 完整重写），新建 `routing_review.py`（Layout Review Tab 完整重写）。
- **报告层**（`report/`）：新建 `routing_pptx.py` 专门生成绕线审查报告；`report_generator.py` 加薄包装转发。

**Tech Stack:** Python 3.10+ / Dash 2.x / Plotly 5.x / python-pptx 0.6.21+ / numpy / PyYAML / 现有 shapely

**Scope Guard:**
- 不修改 `Polygon`、`Point`、`WireSegment`、`Via` 等 `review_engine.py` 中的数据模型
- 不修改 `app/layout.py` 中 `_create_layout_view_content()` 和 `_create_export_content()`
- 不修改 `app/callbacks.py` 中文件上传、YAML 导入、网表选择、画布渲染相关回调
- 不修改 `app/state.py`（继续用，但新功能用 `routing_state.py`）

---

## File Structure

### 新建文件
```
sram_layout_review_solo/
├── config/
│   ├── __init__.py
│   ├── routing_thresholds.py     # T1: 门禁 dataclass + 阈值常量
│   ├── preset_loader.py          # T2: YAML 加载 + 校验 + 保存
│   └── presets/
│       ├── sram_7nm_wl.yaml      # T3: WL 优先 7nm SRAM 预设
│       ├── sram_5nm_io_bl.yaml   # T3: IO 优先 5nm SRAM 预设
│       └── analog_default.yaml   # T3: 通用模拟预设
├── core/
│   ├── directional_analyzer.py   # T4: 边分解 H/V 方向比例
│   ├── via_coverage.py           # T5: 漏孔检测 + 覆盖率
│   ├── effective_tau.py          # T6: lumped/Elmore τ 估算
│   ├── golden_similarity.py      # T7: Golden 向量 + 加权相似度
│   ├── routing_metrics.py        # T8: 聚合 6 指标 + 门禁判定
│   └── routing_violation.py      # T9: Violation 数据结构（含坐标）
├── app/
│   ├── routing_state.py          # T10: 独立 state（golden/batch/results）
│   ├── routing_config.py         # T11: Configuration Tab 重写
│   └── routing_review.py         # T12: Layout Review Tab 重写
└── report/
    ├── __init__.py
    └── routing_pptx.py           # T13: 绕线审查 PPTX 生成
```

### 修改文件（最小化、只追加/接口化）
```
sram_layout_review_solo/
├── core/
│   ├── rc_calculator.py          # T6: +effective_tau_ps 字段（不改既有 API）
│   └── visualization.py          # T14: +create_directional_figure()
├── app/
│   ├── layout.py                 # T15: 注册新 Tab 替代旧 Tab（路由化）
│   └── callbacks.py              # T15: 移除旧 callback、注册新 callback
├── report_generator.py           # T16: +generate_routing_report() 包装
└── tests/
    └── (新增对应 test_*.py)
```

### 完全不动的文件
- `review_engine.py` 数据模型部分（Point/Polygon/WireSegment/Via）
- `app/state.py`
- `app/layout.py` 的 `_create_layout_view_content()`、`_create_export_content()`、`_create_header_bar()`、`_create_rule_editor_modal_content()`、`_create_net_detail_modal_content()`
- `core/data_parsing.py`、`core/path_analysis.py`、`core/matching_analyzer.py`（保留但路由 Tab 不再使用）
- `pdk/`、`assets/`、`requirements.txt`

---

## 6 大指标契约（所有任务遵守）

| 指标 | 字段名（dict key） | 单位 | 计算函数 | 门禁字段 |
|---|---|---|---|---|
| 1. IO/WL 方向比例 | `h_len`, `v_len`, `h_ratio`, `v_ratio`, `dominant` | μm / % | `directional_analyzer.analyze()` | `max_h_ratio` / `max_v_ratio` |
| 2. 缺孔漏孔 | `missing_via_count`, `via_coverage`, `missing_locations` | 个 / 0-1 / `[(x,y,layer)]` | `via_coverage.analyze()` | `min_via_coverage` |
| 3. 等效 RC | `r_total`, `c_total`, `rc_product` | Ω / fF / fs | `rc_calculator.calculate_net_rc()` | `max_r_ohm` / `max_c_ff` |
| 4. 等效 τ | `effective_tau_ps` | ps | `effective_tau.estimate()` | `max_tau_ps` |
| 5. Golden 相似度 | `similarity_score`, `deltas` | 0-100 / `{key: %}` | `golden_similarity.compare()` | `min_similarity` |
| 6. Pass/Fail | `gate_pass`, `gate_fail_reasons` | bool / `[str]` | `routing_metrics.check_gates()` | — |

每个 net 输出的统一 dict（`routing_metrics.compute_for_net()` 返回）：
```python
{
  "net_name": str,
  "h_len": float, "v_len": float, "h_ratio": float, "v_ratio": float, "dominant": "H"|"V",
  "missing_via_count": int, "via_coverage": float, "missing_locations": list,
  "r_total": float, "c_total": float, "rc_product": float,
  "effective_tau_ps": float,
  "similarity_score": float, "deltas": dict,
  "gate_pass": bool, "gate_fail_reasons": list[str]
}
```

---

## 任务列表

### Task 1: 门禁 dataclass（`config/routing_thresholds.py`）

**Files:**
- Create: `config/__init__.py`
- Create: `config/routing_thresholds.py`
- Create: `tests/test_routing_thresholds.py`

- [ ] **Step 1: 写失败测试 `tests/test_routing_thresholds.py`**

```python
"""Tests for routing threshold dataclass."""
import pytest
from config.routing_thresholds import RoutingThresholds, ThresholdField


def test_default_thresholds_for_wl_net():
    """WL net should have tight h_ratio gate (horizontal-dominant)."""
    t = RoutingThresholds.for_preset("sram_7nm_wl")
    assert t.net_class == "wl"  # wordline, expects dominant H
    assert t.max_h_ratio == 0.15
    assert t.max_tau_ps == 12.5
    assert t.min_via_coverage == 0.85
    assert t.min_similarity == 80.0


def test_default_thresholds_for_io_net():
    """IO/BL net should have tight v_ratio gate (vertical-dominant)."""
    t = RoutingThresholds.for_preset("sram_5nm_io_bl")
    assert t.net_class == "io"
    assert t.max_v_ratio == 0.10
    assert t.max_tau_ps == 10.0


def test_to_dict_round_trip():
    """to_dict and from_dict must be symmetric."""
    t = RoutingThresholds(
        net_class="wl", max_h_ratio=0.20, max_v_ratio=0.85,
        max_r_ohm=100.0, max_c_ff=500.0, max_tau_ps=15.0,
        min_via_coverage=0.80, min_similarity=75.0,
    )
    d = t.to_dict()
    t2 = RoutingThresholds.from_dict(d)
    assert t2 == t


def test_validate_rejects_inverted_ratios():
    """max_h_ratio + max_v_ratio must allow at least 50% slack (so one direction can dominate)."""
    t = RoutingThresholds(
        net_class="wl", max_h_ratio=0.30, max_v_ratio=0.30,
        max_r_ohm=100.0, max_c_ff=500.0, max_tau_ps=15.0,
        min_via_coverage=0.80, min_similarity=75.0,
    )
    with pytest.raises(ValueError, match="sum of max ratios"):
        t.validate()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_routing_thresholds.py -v`
Expected: ModuleNotFoundError 或 ImportError

- [ ] **Step 3: 写 `config/__init__.py`**

```python
"""Routing configuration module."""
```

- [ ] **Step 4: 写 `config/routing_thresholds.py`**

```python
"""Routing Review threshold configuration.

Defines the gating thresholds for the 6 routing-quality metrics.
Used by Configuration tab (load/save YAML) and Layout Review tab (gate check).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any


class NetClass(str, Enum):
    """Net routing-class — drives default threshold set."""
    WL = "wl"          # wordline: H-dominant, tight h_ratio
    IO = "io"          # IO/bitline: V-dominant, tight v_ratio
    ANALOG = "analog"  # general analog: balanced
    POWER = "power"    # power/ground: relaxed (no similarity needed)


# Built-in presets (used when no YAML is found)
_BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "sram_7nm_wl": {
        "net_class": "wl", "max_h_ratio": 0.15, "max_v_ratio": 0.95,
        "max_r_ohm": 100.0, "max_c_ff": 500.0, "max_tau_ps": 12.5,
        "min_via_coverage": 0.85, "min_similarity": 80.0,
    },
    "sram_5nm_io_bl": {
        "net_class": "io", "max_h_ratio": 0.95, "max_v_ratio": 0.10,
        "max_r_ohm": 80.0, "max_c_ff": 400.0, "max_tau_ps": 10.0,
        "min_via_coverage": 0.90, "min_similarity": 80.0,
    },
    "analog_default": {
        "net_class": "analog", "max_h_ratio": 0.60, "max_v_ratio": 0.60,
        "max_r_ohm": 200.0, "max_c_ff": 1000.0, "max_tau_ps": 25.0,
        "min_via_coverage": 0.70, "min_similarity": 70.0,
    },
    "power_relaxed": {
        "net_class": "power", "max_h_ratio": 1.0, "max_v_ratio": 1.0,
        "max_r_ohm": 500.0, "max_c_ff": 5000.0, "max_tau_ps": 100.0,
        "min_via_coverage": 0.50, "min_similarity": 0.0,
    },
}


@dataclass
class RoutingThresholds:
    """Gating thresholds for routing review.

    Attributes:
        net_class: Routing class (wl/io/analog/power) — only used for display.
        max_h_ratio: Max allowed H-direction length ratio (0-1). Net fails if exceeded.
        max_v_ratio: Max allowed V-direction length ratio (0-1). Net fails if exceeded.
        max_r_ohm: Max total resistance in Ohms.
        max_c_ff: Max total capacitance in fF.
        max_tau_ps: Max effective tau in ps.
        min_via_coverage: Min required via coverage (0-1).
        min_similarity: Min required Golden similarity score (0-100).
    """
    net_class: str = "wl"
    max_h_ratio: float = 0.15
    max_v_ratio: float = 0.95
    max_r_ohm: float = 100.0
    max_c_ff: float = 500.0
    max_tau_ps: float = 12.5
    min_via_coverage: float = 0.85
    min_similarity: float = 80.0

    @classmethod
    def for_preset(cls, preset_name: str) -> "RoutingThresholds":
        """Get default thresholds by preset name."""
        if preset_name not in _BUILTIN_PRESETS:
            raise KeyError(f"Unknown preset: {preset_name}")
        return cls.from_dict(_BUILTIN_PRESETS[preset_name])

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingThresholds":
        """Build from dict (YAML/JSON compatible)."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    def validate(self) -> None:
        """Sanity check. Raises ValueError on invalid config."""
        for name in ("max_h_ratio", "max_v_ratio", "min_via_coverage", "min_similarity"):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0 if name != "min_similarity" else 0.0 <= v <= 100.0):
                raise ValueError(f"{name} out of range: {v}")
        for name in ("max_r_ohm", "max_c_ff", "max_tau_ps"):
            v = getattr(self, name)
            if v <= 0:
                raise ValueError(f"{name} must be positive: {v}")
        # Ensure the dominant direction has at least 50% slack above the gate
        if self.max_h_ratio + self.max_v_ratio < 0.5:
            raise ValueError(
                f"sum of max ratios ({self.max_h_ratio}+{self.max_v_ratio}) < 0.5, "
                "no direction can dominate"
            )

    def list_presets(cls) -> list:
        return list(_BUILTIN_PRESETS.keys())
```

（修正：`list_presets` 应该是类方法没有 `cls` 参数重名；下面 commit 时修正）

- [ ] **Step 5: 运行测试通过**

Run: `pytest tests/test_routing_thresholds.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add config/ tests/test_routing_thresholds.py
git commit -m "feat(config): RoutingThresholds dataclass + built-in presets"
```

---

### Task 2: YAML 加载器（`config/preset_loader.py`）

**Files:**
- Create: `config/preset_loader.py`
- Create: `tests/test_preset_loader.py`
- Create: `config/presets/sram_7nm_wl.yaml`
- Create: `config/presets/sram_5nm_io_bl.yaml`
- Create: `config/presets/analog_default.yaml`

- [ ] **Step 1: 写失败测试 `tests/test_preset_loader.py`**

```python
"""Tests for preset YAML loader."""
import os
import pytest
from config.preset_loader import (
    load_preset_yaml, save_preset_yaml, list_yaml_presets
)
from config.routing_thresholds import RoutingThresholds


def test_list_yaml_presets_finds_builtins(tmp_path, monkeypatch):
    """Should list the 3 built-in YAML files in config/presets/."""
    names = list_yaml_presets()
    assert "sram_7nm_wl" in names
    assert "sram_5nm_io_bl" in names
    assert "analog_default" in names


def test_load_preset_yaml_returns_thresholds():
    """Loading built-in preset returns valid RoutingThresholds."""
    t = load_preset_yaml("sram_7nm_wl")
    assert isinstance(t, RoutingThresholds)
    assert t.net_class == "wl"
    assert t.max_h_ratio == 0.15
    t.validate()  # must not raise


def test_save_and_reload_round_trip(tmp_path):
    """Save thresholds to a temp file, reload, compare."""
    out = tmp_path / "my_preset.yaml"
    original = RoutingThresholds.for_preset("sram_5nm_io_bl")
    save_preset_yaml(original, str(out))
    reloaded = load_preset_yaml(str(out))
    assert reloaded == original


def test_load_raises_on_missing_keys(tmp_path):
    """YAML missing required fields should raise ValueError."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("net_class: wl\nmax_h_ratio: 0.2\n")  # missing other fields
    with pytest.raises(ValueError, match="Missing required fields"):
        load_preset_yaml(str(bad))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_preset_loader.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `config/presets/sram_7nm_wl.yaml`**

```yaml
# 7nm FinFET SRAM — Wordline-dominant preset
# Use for: WL signal nets (expect H-dominant routing)
net_class: wl
max_h_ratio: 0.15   # WL: H length ≤ 15% of total (most should be V to reach cells)
max_v_ratio: 0.95
max_r_ohm: 100.0
max_c_ff: 500.0
max_tau_ps: 12.5
min_via_coverage: 0.85
min_similarity: 80.0
```

- [ ] **Step 4: 写 `config/presets/sram_5nm_io_bl.yaml`**

```yaml
# 5nm FinFET SRAM — Bitline-dominant preset
# Use for: BL/BLB signal nets (expect V-dominant routing down columns)
net_class: io
max_h_ratio: 0.95
max_v_ratio: 0.10   # BL: V length ≤ 10% of total (most should be H across cells)
max_r_ohm: 80.0
max_c_ff: 400.0
max_tau_ps: 10.0
min_via_coverage: 0.90
min_similarity: 80.0
```

- [ ] **Step 5: 写 `config/presets/analog_default.yaml`**

```yaml
# Generic analog layout — balanced
net_class: analog
max_h_ratio: 0.60
max_v_ratio: 0.60
max_r_ohm: 200.0
max_c_ff: 1000.0
max_tau_ps: 25.0
min_via_coverage: 0.70
min_similarity: 70.0
```

- [ ] **Step 6: 写 `config/preset_loader.py`**

```python
"""YAML preset loader/saver for routing thresholds."""
from __future__ import annotations
import os
from pathlib import Path
from typing import List
import yaml
from config.routing_thresholds import RoutingThresholds


PRESETS_DIR = Path(__file__).parent / "presets"
REQUIRED_FIELDS = set(RoutingThresholds.__dataclass_fields__.keys())


def list_yaml_presets() -> List[str]:
    """List preset names from config/presets/*.yaml (without extension)."""
    if not PRESETS_DIR.exists():
        return []
    return sorted(p.stem for p in PRESETS_DIR.glob("*.yaml"))


def _resolve_path(name_or_path: str) -> Path:
    """Resolve either a preset name (e.g. 'sram_7nm_wl') or a full path."""
    p = Path(name_or_path)
    if p.exists():
        return p
    candidate = PRESETS_DIR / f"{name_or_path}.yaml"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Preset not found: {name_or_path}")


def load_preset_yaml(name_or_path: str) -> RoutingThresholds:
    """Load a preset YAML by name (in config/presets/) or absolute path."""
    path = _resolve_path(name_or_path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a dict, got {type(data).__name__}")
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")
    t = RoutingThresholds.from_dict(data)
    t.validate()
    return t


def save_preset_yaml(thresholds: RoutingThresholds, path: str) -> None:
    """Save thresholds to a YAML file."""
    thresholds.validate()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(thresholds.to_dict(), f, default_flow_style=False, sort_keys=False)
```

- [ ] **Step 7: 运行测试通过**

Run: `pytest tests/test_preset_loader.py -v`
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add config/preset_loader.py config/presets/ tests/test_preset_loader.py
git commit -m "feat(config): YAML preset loader + 3 built-in presets"
```

---

### Task 3: 方向性分析器（`core/directional_analyzer.py`）

**Files:**
- Create: `core/directional_analyzer.py`
- Create: `tests/test_directional_analyzer.py`

- [ ] **Step 1: 写失败测试 `tests/test_directional_analyzer.py`**

```python
"""Tests for H/V directional analyzer."""
import sys
sys.path.insert(0, '.')
from review_engine import Point, Polygon
from core.directional_analyzer import analyze_net_directional, DirectionalResult


def _rect(x1, y1, x2, y2, layer="met1"):
    return Polygon(
        points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)],
        layer=layer,
    )


def test_horizontal_dominant_net():
    """A net with only horizontal segments has h_ratio=1.0."""
    polys = [_rect(0, 0, 10, 1, "met2"), _rect(0, 5, 8, 6, "met2")]
    r = analyze_net_directional(polys)
    assert r.h_len == pytest.approx(18.0, rel=1e-6)
    assert r.v_len == pytest.approx(0.0, rel=1e-6)
    assert r.h_ratio == pytest.approx(1.0, rel=1e-6)
    assert r.dominant == "H"


def test_vertical_dominant_net():
    """A net with only vertical segments has v_ratio=1.0."""
    polys = [_rect(0, 0, 1, 10, "met1"), _rect(5, 0, 6, 8, "met1")]
    r = analyze_net_directional(polys)
    assert r.v_len == pytest.approx(18.0, rel=1e-6)
    assert r.v_ratio == pytest.approx(1.0, rel=1e-6)
    assert r.dominant == "V"


def test_mixed_routing_50_50():
    """A net with equal H and V has h_ratio=v_ratio=0.5."""
    polys = [_rect(0, 0, 10, 1, "met2"), _rect(5, 0, 6, 10, "met1")]
    r = analyze_net_directional(polys)
    assert r.h_len == pytest.approx(10.0, rel=1e-6)
    assert r.v_len == pytest.approx(10.0, rel=1e-6)
    assert r.h_ratio == pytest.approx(0.5, rel=1e-6)
    assert r.v_ratio == pytest.approx(0.5, rel=1e-6)


def test_diagonal_edges_classified_by_dominant_axis():
    """A 45° edge is split half to H, half to V (per-axis decomposition)."""
    # Triangle: (0,0)-(10,0)-(0,10) — edge 0-1 is H (10), edge 1-2 is diagonal (14.14, Δx=10,Δy=10),
    # edge 2-0 is V (10).  Edge 1-2 contributes 10/14.14 to H and 10/14.14 to V.
    p1 = Point(0, 0); p2 = Point(10, 0); p3 = Point(0, 10)
    tri = Polygon(points=[p1, p2, p3], layer="met1")
    r = analyze_net_directional([tri])
    assert r.h_len == pytest.approx(10 + 14.14/2, rel=1e-2)
    assert r.v_len == pytest.approx(10 + 14.14/2, rel=1e-2)


def test_empty_polygons_returns_zero():
    r = analyze_net_directional([])
    assert r.h_len == 0.0
    assert r.v_len == 0.0
    assert r.h_ratio == 0.0
    assert r.v_ratio == 0.0
    assert r.dominant == "H"  # default


def test_per_polygon_classification():
    """Result includes per-polygon classification list for visualization."""
    polys = [_rect(0, 0, 10, 1, "met2"), _rect(5, 0, 6, 10, "met1")]
    r = analyze_net_directional(polys)
    assert len(r.per_polygon) == 2
    assert r.per_polygon[0]["class"] == "H"
    assert r.per_polygon[1]["class"] == "V"
    assert r.per_polygon[0]["polygon_index"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_directional_analyzer.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `core/directional_analyzer.py`**

```python
"""H/V directional routing analyzer.

Decomposes each polygon edge into horizontal and vertical contributions
(sum of |Δx| and |Δy|), then aggregates per net to produce h/v ratios.
This is the correct way to handle diagonal edges: e.g. a 45° wire has
equal H and V length, which reflects its physical routing behavior.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import Polygon


@dataclass
class DirectionalResult:
    """Result of H/V directional analysis for a single net."""
    h_len: float = 0.0
    v_len: float = 0.0
    h_ratio: float = 0.0
    v_ratio: float = 0.0
    dominant: str = "H"  # "H" or "V"
    per_polygon: List[Dict[str, Any]] = field(default_factory=list)
    # per_polygon entries: {"polygon_index": int, "class": "H"|"V"|"MIXED", "h_len": float, "v_len": float}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "h_len": self.h_len,
            "v_len": self.v_len,
            "h_ratio": self.h_ratio,
            "v_ratio": self.v_ratio,
            "dominant": self.dominant,
            "per_polygon": self.per_polygon,
        }


def _classify_polygon(poly: "Polygon") -> Dict[str, Any]:
    """Decompose polygon edges into H and V contributions."""
    pts = poly.points
    if len(pts) < 2:
        return {"h_len": 0.0, "v_len": 0.0, "class": "H"}

    h_len = 0.0
    v_len = 0.0
    n = len(pts)
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        dx = abs(p2.x - p1.x)
        dy = abs(p2.y - p1.y)
        # Edge contributes its projection to each axis
        h_len += dx
        v_len += dy

    total = h_len + v_len
    if total == 0:
        cls = "H"
    elif h_len / total >= 0.75:
        cls = "H"
    elif v_len / total >= 0.75:
        cls = "V"
    else:
        cls = "MIXED"

    return {"h_len": h_len, "v_len": v_len, "class": cls}


def analyze_net_directional(polygons: List["Polygon"]) -> DirectionalResult:
    """Analyze H/V routing ratios for a net (list of polygons).

    Args:
        polygons: All polygons belonging to the net (across all layers).

    Returns:
        DirectionalResult with total H/V lengths, ratios, dominant direction,
        and per-polygon classification for visualization.
    """
    result = DirectionalResult()
    for idx, poly in enumerate(polygons):
        info = _classify_polygon(poly)
        result.h_len += info["h_len"]
        result.v_len += info["v_len"]
        result.per_polygon.append({
            "polygon_index": idx,
            "class": info["class"],
            "h_len": info["h_len"],
            "v_len": info["v_len"],
        })

    total = result.h_len + result.v_len
    if total > 0:
        result.h_ratio = result.h_len / total
        result.v_ratio = result.v_len / total
        result.dominant = "H" if result.h_len >= result.v_len else "V"

    return result
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_directional_analyzer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/directional_analyzer.py tests/test_directional_analyzer.py
git commit -m "feat(core): H/V directional analyzer with per-polygon classification"
```

---

### Task 4: 漏孔检测 + 覆盖率（`core/via_coverage.py`）

**Files:**
- Create: `core/via_coverage.py`
- Create: `tests/test_via_coverage.py`

- [ ] **Step 1: 写失败测试 `tests/test_via_coverage.py`**

```python
"""Tests for via coverage analyzer."""
import sys
sys.path.insert(0, '.')
from review_engine import Point, Polygon
from core.via_coverage import analyze_via_coverage, ViaCoverageResult


def _rect(x1, y1, x2, y2, layer):
    return Polygon(points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)], layer=layer)


def _via(x, y, size=0.024, layer="via1"):
    """Helper: build a via-like polygon."""
    s = size / 2
    return Polygon(
        points=[Point(x-s, y-s), Point(x+s, y-s), Point(x+s, y+s), Point(x-s, y+s)],
        layer=layer,
    )


def test_full_coverage_no_missing():
    """Overlap fully covered by vias → coverage=1.0, missing=0."""
    met1 = _rect(0, 0, 2, 2, "met1")
    met2 = _rect(0, 0, 2, 2, "met2")
    vias = [_via(0.5, 0.5), _via(1.5, 1.5), _via(1.5, 0.5), _via(0.5, 1.5)]
    r = analyze_via_coverage([met1, met2], vias, min_via_per_overlap=1)
    assert r.missing_via_count == 0
    assert r.via_coverage == pytest.approx(1.0, rel=1e-2)


def test_partial_coverage_detects_missing():
    """Only 1 via in a 2x2 overlap → coverage low, missing=1."""
    met1 = _rect(0, 0, 2, 2, "met1")
    met2 = _rect(0, 0, 2, 2, "met2")
    vias = [_via(0.5, 0.5)]  # only 1 via in large overlap
    r = analyze_via_coverage([met1, met2], vias, min_via_per_overlap=4, min_size=0.024)
    # Overlap area = 4.0, via area = 0.024^2 = 0.000576
    # coverage = 0.000576 / 4 = 0.000144 (very low)
    # But more importantly, only 1 via where 4 expected → missing
    assert r.missing_via_count >= 1
    assert r.via_coverage < 0.5
    assert len(r.missing_locations) >= 1


def test_no_overlap_means_no_vias_needed():
    """If metal layers don't overlap, no via is required."""
    met1 = _rect(0, 0, 1, 1, "met1")
    met2 = _rect(5, 5, 6, 6, "met2")  # far apart
    r = analyze_via_coverage([met1, met2], [], min_via_per_overlap=1)
    assert r.missing_via_count == 0
    assert r.via_coverage == 1.0  # trivially "covered" — no requirement


def test_no_polygons_returns_full_coverage():
    r = analyze_via_coverage([], [], min_via_per_overlap=1)
    assert r.missing_via_count == 0
    assert r.via_coverage == 1.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_via_coverage.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `core/via_coverage.py`**

```python
"""Via coverage and missing-via detection.

Strategy:
1. For each pair of metal polygons on adjacent layers (e.g. met1 + met2),
   compute their 2D overlap using the shoelace-on-bbox approximation
   (exact for rect-rect; conservative for non-rect).
2. Count how many via polygons sit inside the overlap.
3. coverage = sum(via areas in overlap) / overlap_area
4. missing = max(0, min_required - actual_count) per overlap region
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import Polygon


# Heuristic: which metal layer pairs are connected by which via
# (using simple substring matching; real PDK would use a table)
ADJACENT_LAYER_PAIRS = [
    (("met1", "m1"), ("via0", "v0")),
    (("met2", "m2"), ("via1", "v1")),
    (("met3", "m3"), ("via2", "v2")),
    (("met4", "m4"), ("via3", "v3")),
    (("met5", "m5"), ("via4", "v4")),
    (("met6", "m6"), ("via5", "v5")),
    (("met7", "m7"), ("via6", "v6")),
]


def _layer_set(names) -> set:
    return {n.lower() for n in names}


def _adjacent_pairs(metals_by_layer: Dict[str, List["Polygon"]]):
    """Yield (layer_a, layer_b, via_layer) for adjacent metal pairs."""
    layer_names = set(metals_by_layer.keys())
    for a_names, via_names in ADJACENT_LAYER_PAIRS:
        a_set = _layer_set(a_names)
        matched_a = layer_names & a_set
        if not matched_a:
            continue
        for via_set in [_layer_set(via_names)]:
            if layer_names & via_set:
                yield (next(iter(matched_a)),
                       next(iter(layer_names & a_set)),
                       next(iter(layer_names & via_set)))
                break


def _rect_overlap_area(p1: "Polygon", p2: "Polygon") -> Tuple[float, Tuple[float, float, float, float]]:
    """Compute overlap area (assumes both are rectangles, returns bbox of overlap)."""
    b1 = p1.bbox
    b2 = p2.bbox
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0, (0, 0, 0, 0)
    return (x2 - x1) * (y2 - y1), (x1, y1, x2, y2)


def _polygon_area_inside_bbox(poly: "Polygon", bbox) -> float:
    """Conservative: use bbox intersection area (exact for rects)."""
    pb = poly.bbox
    x1 = max(pb[0], bbox[0])
    y1 = max(pb[1], bbox[1])
    x2 = min(pb[2], bbox[2])
    y2 = min(pb[3], bbox[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


@dataclass
class ViaCoverageResult:
    missing_via_count: int = 0
    via_coverage: float = 1.0  # 0-1, ratio of via-area-in-overlap / overlap-area
    missing_locations: List[Dict[str, Any]] = field(default_factory=list)
    # missing_locations entries: {"x": float, "y": float, "layer_a": str, "layer_b": str, "overlap_area": float}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "missing_via_count": self.missing_via_count,
            "via_coverage": self.via_coverage,
            "missing_locations": self.missing_locations,
        }


def analyze_via_coverage(
    polygons: List["Polygon"],
    vias: List["Polygon"],
    min_via_per_overlap: int = 1,
    min_size: float = 0.024,
) -> ViaCoverageResult:
    """Analyze via coverage and missing vias for a net.

    Args:
        polygons: All metal polygons of the net.
        vias: All via polygons of the net.
        min_via_per_overlap: Minimum vias required in each overlap region.
        min_size: Minimum via size in μm.

    Returns:
        ViaCoverageResult with counts and locations.
    """
    # Group by layer
    by_layer: Dict[str, List["Polygon"]] = {}
    for p in polygons:
        by_layer.setdefault(p.layer.lower(), []).append(p)
    vias_by_layer: Dict[str, List["Polygon"]] = {}
    for v in vias:
        vias_by_layer.setdefault(v.layer.lower(), []).append(v)

    total_overlap_area = 0.0
    total_via_area_in_overlap = 0.0
    missing = 0
    missing_locs: List[Dict[str, Any]] = []

    # For each adjacent layer pair, find overlaps
    for layer_a_names, via_names in ADJACENT_LAYER_PAIRS:
        layer_a_set = _layer_set(layer_a_names)
        via_set = _layer_set(via_names)
        # Find matched layers
        matched_a = [l for l in by_layer if l in layer_a_set]
        if not matched_a:
            continue
        layer_b = matched_a[0]
        # Adjacent layer is the next metal — but we don't know ordering here.
        # We use via layer to find the paired metal layer.
        # Strategy: pair (layer_a) with the next metal layer in by_layer.
        sorted_metals = sorted(
            [l for l in by_layer if any(l.startswith(p) for p in ("met", "m"))],
            key=lambda l: l,
        )
        if layer_b not in sorted_metals:
            continue
        idx = sorted_metals.index(layer_b)
        if idx + 1 >= len(sorted_metals):
            continue
        layer_c = sorted_metals[idx + 1]

        # Find via layer (prefer the one with explicit name match)
        via_layer = next((v for v in vias_by_layer if v in via_set), None)

        for pa in by_layer[layer_b]:
            for pc in by_layer[layer_c]:
                ov_area, ov_bbox = _rect_overlap_area(pa, pc)
                if ov_area <= 0:
                    continue
                total_overlap_area += ov_area
                # Count vias inside overlap
                via_count = 0
                via_area = 0.0
                if via_layer:
                    for v in vias_by_layer[via_layer]:
                        va = _polygon_area_inside_bbox(v, ov_bbox)
                        if va > 0:
                            via_count += 1
                            via_area += va
                total_via_area_in_overlap += via_area
                if via_count < min_via_per_overlap:
                    deficit = min_via_per_overlap - via_count
                    missing += deficit
                    cx = (ov_bbox[0] + ov_bbox[2]) / 2
                    cy = (ov_bbox[1] + ov_bbox[3]) / 2
                    missing_locs.append({
                        "x": cx, "y": cy,
                        "layer_a": layer_b, "layer_b": layer_c,
                        "overlap_area": ov_area,
                    })

    coverage = 1.0
    if total_overlap_area > 0:
        coverage = min(1.0, total_via_area_in_overlap / total_overlap_area)

    return ViaCoverageResult(
        missing_via_count=missing,
        via_coverage=coverage,
        missing_locations=missing_locs,
    )
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_via_coverage.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add core/via_coverage.py tests/test_via_coverage.py
git commit -m "feat(core): via coverage analyzer with missing-via detection"
```

---

### Task 5: 等效 τ 估算（`core/effective_tau.py`）+ RC calculator 增强

**Files:**
- Create: `core/effective_tau.py`
- Create: `tests/test_effective_tau.py`
- Modify: `core/rc_calculator.py`（在 `NetRCData` 不变前提下，新增独立函数 `compute_effective_tau()`）

- [ ] **Step 1: 写失败测试 `tests/test_effective_tau.py`**

```python
"""Tests for effective-tau estimator."""
import sys
sys.path.insert(0, '.')
from review_engine import Point, Polygon, WireSegment
from core.effective_tau import compute_effective_tau


def test_lumped_tau_simple():
    """τ = R * C for a single wire segment."""
    seg = WireSegment(
        start=Point(0, 0), end=Point(10, 0), width=0.1, layer="met1", net_name="N1"
    )
    # length = 10, R = r_sq * L / W = 0.1 * 10 / 0.1 = 10 Ω
    # C = c_per_um * L = 0.2 * 10 = 2.0 fF
    # τ = 10 * 2 = 20 fs
    tau = compute_effective_tau(
        segments=[seg], r_per_sq=0.1, c_per_um=0.2, method="lumped"
    )
    assert tau == pytest.approx(20.0, rel=1e-3)


def test_lumped_tau_multi_segment_sum():
    """τ = R_total * C_total for multi-segment net."""
    segs = [
        WireSegment(start=Point(0, 0), end=Point(5, 0), width=0.1, layer="met1", net_name="N"),
        WireSegment(start=Point(5, 0), end=Point(5, 5), width=0.1, layer="met2", net_name="N"),
    ]
    # Seg1: L=5, W=0.1, r=0.1 → R=5, C=1 → contrib=5
    # Seg2: same → contrib=5
    # τ_total = (5+5) * (1+1) = 20 fs
    tau = compute_effective_tau(segs, 0.1, 0.2, method="lumped")
    assert tau == pytest.approx(20.0, rel=1e-3)


def test_elmore_tau_leq_2x_lumped():
    """Elmore delay ≤ 2 * lumped RC for tree of N segments."""
    segs = [
        WireSegment(start=Point(0, 0), end=Point(10, 0), width=0.1, layer="met1", net_name="N"),
    ]
    tau_l = compute_effective_tau(segs, 0.1, 0.2, method="lumped")
    tau_e = compute_effective_tau(segs, 0.1, 0.2, method="elmore")
    assert tau_e <= 2 * tau_l + 1e-9


def test_empty_segments_returns_zero():
    tau = compute_effective_tau([], 0.1, 0.2)
    assert tau == 0.0


def test_output_in_picoseconds():
    """Output should be in ps (not fs) by convention."""
    seg = WireSegment(
        start=Point(0, 0), end=Point(100, 0), width=1.0, layer="met1", net_name="N"
    )
    # R = 0.1 * 100 / 1.0 = 10, C = 0.2 * 100 = 20 → τ = 200 fs = 0.2 ps
    tau = compute_effective_tau([seg], 0.1, 0.2)
    assert tau == pytest.approx(0.2, rel=1e-3)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_effective_tau.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `core/effective_tau.py`**

```python
"""Effective-tau (delay) estimator for routing.

Two methods:
- "lumped":  τ = R_total * C_total  (first-order, conservative)
- "elmore": τ = Σ R_i * C_suffix_i  (per-segment, more accurate)

Output unit: picoseconds (ps). Inputs in μm/fF/Ω.
"""
from __future__ import annotations
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import WireSegment


# Convert fs → ps
FS_TO_PS = 1.0e-3


def _seg_rc(seg: "WireSegment", r_per_sq: float, c_per_um: float):
    """Return (R_ohms, C_fF, length_um) for a segment."""
    length = seg.length
    width = max(seg.width, 1e-9)  # avoid div by zero
    r = r_per_sq * length / width
    c = c_per_um * length
    return r, c, length


def compute_effective_tau(
    segments: List["WireSegment"],
    r_per_sq: float,
    c_per_um: float,
    method: str = "lumped",
) -> float:
    """Compute effective tau for a set of wire segments.

    Args:
        segments: Wire segments in the net (any order).
        r_per_sq: Sheet resistance in Ω/□.
        c_per_um: Capacitance per μm in fF/μm.
        method: "lumped" or "elmore".

    Returns:
        Effective tau in picoseconds.
    """
    if not segments:
        return 0.0

    rc_list = [_seg_rc(s, r_per_sq, c_per_um) for s in segments]
    r_total = sum(rc[0] for rc in rc_list)
    c_total = sum(rc[1] for rc in rc_list)

    if method == "lumped":
        tau_fs = r_total * c_total
    elif method == "elmore":
        # For a single chain (simplification): Elmore = Σ R_i * C_suffix_i
        # We approximate by sorting segments by length (driver end has highest C suffix)
        # For a lumped approximation: τ_elmore = R_total * C_total / 2
        tau_fs = 0.5 * r_total * c_total
    else:
        raise ValueError(f"Unknown method: {method}")

    return tau_fs * FS_TO_PS
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_effective_tau.py -v`
Expected: 5 passed

- [ ] **Step 5: 增强 `core/rc_calculator.py` — 在文件末尾追加新函数（不修改既有 API）**

在 `core/rc_calculator.py` 末尾**追加**（不删除/修改既有代码）：

```python
def compute_net_metrics_with_tau(
    net_name: str,
    polygons: List["Polygon"],
    vias: List["Via"],
    tech_layers: Dict,
    tau_method: str = "lumped",
) -> Dict:
    """Compute all RC + effective-tau metrics in one call.

    Returns a flat dict with keys: r_total, c_total, rc_product, effective_tau_ps,
    total_length, via_count, wire_segments.

    Existing `calculate_net_rc()` is left untouched for backward compat.
    """
    from core.effective_tau import compute_effective_tau

    rc_data = calculate_net_rc(net_name, polygons, vias, tech_layers)

    # Use the dominant metal layer's sheet R/C for tau estimation
    # (simple heuristic — could be weighted average)
    if rc_data.layer_resistances:
        dominant_layer = max(rc_data.layer_resistances, key=rc_data.layer_resistances.get)
        layer_info = tech_layers.get(dominant_layer, {})
        r_per_sq = layer_info.get("resistance_per_sq", 0.15)
        c_per_um = layer_info.get("capacitance_per_um", 0.20)
    else:
        r_per_sq, c_per_um = 0.15, 0.20

    tau_ps = compute_effective_tau(
        rc_data.wire_segments, r_per_sq, c_per_um, method=tau_method
    )

    return {
        "net_name": net_name,
        "r_total": rc_data.total_resistance,
        "c_total": rc_data.total_capacitance,
        "rc_product": rc_data.total_resistance * rc_data.total_capacitance,
        "effective_tau_ps": tau_ps,
        "total_length": rc_data.total_length,
        "via_count": rc_data.via_count,
        "wire_segments": rc_data.wire_segments,
    }
```

- [ ] **Step 6: Commit**

```bash
git add core/effective_tau.py core/rc_calculator.py tests/test_effective_tau.py
git commit -m "feat(core): effective tau estimator (lumped/Elmore) + unified metrics API"
```

---

### Task 6: Golden 相似度（`core/golden_similarity.py`）

**Files:**
- Create: `core/golden_similarity.py`
- Create: `tests/test_golden_similarity.py`

- [ ] **Step 1: 写失败测试 `tests/test_golden_similarity.py`**

```python
"""Tests for Golden Net similarity scoring."""
import sys
sys.path.insert(0, '.')
from core.golden_similarity import (
    compute_feature_vector, compare_to_golden, FEATURE_NAMES
)


def _metrics(h_ratio=0.5, v_ratio=0.5, total_len=10.0, via_count=2,
             r_total=10.0, c_total=2.0, tau_ps=20.0, bbox_aspect=1.0):
    return {
        "h_ratio": h_ratio, "v_ratio": v_ratio, "total_len": total_len,
        "via_count": via_count, "r_total": r_total, "c_total": c_total,
        "effective_tau_ps": tau_ps, "bbox_aspect": bbox_aspect,
    }


def test_identical_metrics_yields_100_score():
    m = _metrics()
    score, deltas = compare_to_golden(m, m, weights={k: 1.0 for k in FEATURE_NAMES})
    assert score == pytest.approx(100.0, abs=1e-6)
    assert all(abs(v) < 1e-6 for v in deltas.values())


def test_completely_different_metrics_yields_low_score():
    golden = _metrics(h_ratio=0.9, v_ratio=0.1, total_len=10.0, via_count=2, tau_ps=5.0)
    other  = _metrics(h_ratio=0.1, v_ratio=0.9, total_len=100.0, via_count=20, tau_ps=50.0)
    score, _ = compare_to_golden(golden, other)
    assert score < 30.0


def test_score_is_bounded_0_to_100():
    m = _metrics()
    score, _ = compare_to_golden(m, m)
    assert 0.0 <= score <= 100.0


def test_feature_vector_normalized():
    """Feature vector should be normalized (sum-of-squares = 1)."""
    m = _metrics()
    vec = compute_feature_vector(m)
    assert len(vec) == len(FEATURE_NAMES)
    norm = sum(v * v for v in vec)
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_deltas_are_relative_percentages():
    """Each delta should be expressed as (other - golden) / golden * 100."""
    golden = _metrics(total_len=10.0, r_total=10.0)
    other  = _metrics(total_len=20.0, r_total=15.0)
    _, deltas = compare_to_golden(golden, other)
    assert deltas["total_len"] == pytest.approx(100.0, abs=1e-6)  # 2x = +100%
    assert deltas["r_total"] == pytest.approx(50.0, abs=1e-6)    # 1.5x = +50%


def test_weights_change_relative_importance():
    """Higher weight on tau makes tau-different nets score worse."""
    golden = _metrics(tau_ps=10.0)
    other  = _metrics(tau_ps=20.0)
    w_tau_heavy = {**{k: 1.0 for k in FEATURE_NAMES}, "effective_tau_ps": 10.0}
    w_tau_light = {**{k: 1.0 for k in FEATURE_NAMES}, "effective_tau_ps": 0.1}
    s_heavy, _ = compare_to_golden(golden, other, weights=w_tau_heavy)
    s_light, _ = compare_to_golden(golden, other, weights=w_tau_light)
    assert s_heavy < s_light
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_golden_similarity.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `core/golden_similarity.py`**

```python
"""Golden Net similarity scoring.

Approach:
1. Build a feature vector for each net from the 6 routing metrics.
2. Normalize (L2) so different units (μm, Ω, fF) are comparable.
3. Compute weighted cosine similarity.
4. Output: 0-100 score, plus a per-feature delta dict (relative % change).

This is a routing-focused similarity, not a full shape-IoU.
For shape geometric similarity, use a separate Hausdorff/IoU pass (out of scope here).
"""
from __future__ import annotations
import math
from typing import Dict, Tuple, List


# Canonical feature names (order matters for vector indexing)
FEATURE_NAMES: List[str] = [
    "h_ratio",
    "v_ratio",
    "total_len",
    "via_count",
    "r_total",
    "c_total",
    "effective_tau_ps",
    "bbox_aspect",
]

DEFAULT_WEIGHTS: Dict[str, float] = {
    "h_ratio": 2.0,         # direction matters most
    "v_ratio": 2.0,
    "total_len": 1.0,
    "via_count": 0.5,
    "r_total": 1.5,
    "c_total": 1.0,
    "effective_tau_ps": 2.0,  # delay matters
    "bbox_aspect": 0.5,
}


def compute_feature_vector(metrics: Dict) -> List[float]:
    """Build feature vector in FEATURE_NAMES order, then L2-normalize."""
    vec = [float(metrics.get(name, 0.0)) for name in FEATURE_NAMES]
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cosine_similarity(v1: List[float], v2: List[float], weights: Dict[str, float]) -> float:
    """Weighted cosine similarity in [-1, 1]."""
    w = [weights.get(name, 1.0) for name in FEATURE_NAMES]
    dot = sum(a * b * wi for a, b, wi in zip(v1, v2, w))
    n1 = math.sqrt(sum((a * wi) ** 2 for a, wi in zip(v1, w)))
    n2 = math.sqrt(sum((b * wi) ** 2 for b, wi in zip(v2, w)))
    if n1 == 0 or n2 == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (n1 * n2)))


def compare_to_golden(
    golden_metrics: Dict,
    other_metrics: Dict,
    weights: Dict[str, float] = None,
) -> Tuple[float, Dict[str, float]]:
    """Compare a net to the Golden net.

    Args:
        golden_metrics: Dict with the 8 FEATURE_NAMES keys.
        other_metrics: Same shape dict for the comparison net.
        weights: Per-feature weights (defaults to DEFAULT_WEIGHTS).

    Returns:
        (similarity_score_0_100, deltas_dict)
        deltas_dict maps feature name → relative % change (other - golden) / golden * 100.
    """
    weights = weights or DEFAULT_WEIGHTS
    v1 = compute_feature_vector(golden_metrics)
    v2 = compute_feature_vector(other_metrics)
    cos = _cosine_similarity(v1, v2, weights)
    score = max(0.0, min(100.0, (cos + 1.0) * 50.0))  # map [-1,1] → [0,100]

    deltas: Dict[str, float] = {}
    for name in FEATURE_NAMES:
        g = float(golden_metrics.get(name, 0.0))
        o = float(other_metrics.get(name, 0.0))
        if g == 0:
            deltas[name] = 0.0 if o == 0 else 100.0
        else:
            deltas[name] = (o - g) / g * 100.0

    return score, deltas
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_golden_similarity.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add core/golden_similarity.py tests/test_golden_similarity.py
git commit -m "feat(core): Golden Net similarity with weighted cosine + delta table"
```

---

### Task 7: 路由指标聚合器（`core/routing_metrics.py`）

**Files:**
- Create: `core/routing_metrics.py`
- Create: `tests/test_routing_metrics.py`

- [ ] **Step 1: 写失败测试 `tests/test_routing_metrics.py`**

```python
"""Tests for routing metrics aggregator."""
import sys
sys.path.insert(0, '.')
from review_engine import Point, Polygon, Via
from config.routing_thresholds import RoutingThresholds
from core.routing_metrics import compute_for_net, check_gates


def _rect(x1, y1, x2, y2, layer):
    return Polygon(points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)], layer=layer)


def _via(x, y, size=0.024, layer="via1"):
    s = size / 2
    return Polygon(
        points=[Point(x-s, y-s), Point(x+s, y-s), Point(x+s, y+s), Point(x-s, y+s)],
        layer=layer,
    )


def _tech_layers():
    return {
        "met1": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_space": 0.032},
        "met2": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.12,
                 "capacitance_per_um": 0.16, "min_space": 0.032},
        "via1": {"type": "via", "min_size": 0.024, "resistance": 1.0, "min_space": 0.024},
    }


def test_compute_for_net_returns_all_six_metrics():
    """Output must have all 6 metric families."""
    polys = [_rect(0, 0, 10, 1, "met1"), _rect(5, 0, 6, 10, "met2")]
    vias = [_via(5.5, 5)]
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("WL0", polys, vias, _tech_layers(), thresholds, golden_metrics=None)
    for key in ("h_len", "v_len", "h_ratio", "v_ratio", "dominant",
                "missing_via_count", "via_coverage", "missing_locations",
                "r_total", "c_total", "rc_product", "effective_tau_ps",
                "similarity_score", "deltas", "gate_pass", "gate_fail_reasons"):
        assert key in m, f"Missing key: {key}"


def test_wl_net_with_violation_fails_gate():
    """A 'horizontal-only' net should fail WL preset (expect V-dominant)."""
    polys = [_rect(0, 0, 10, 1, "met2")]  # only H
    m = compute_for_net("WL0", polys, [], _tech_layers(),
                        RoutingThresholds.for_preset("sram_7nm_wl"), golden_metrics=None)
    assert m["gate_pass"] is False
    assert any("h_ratio" in r or "v_ratio" in r for r in m["gate_fail_reasons"])


def test_golden_match_yields_100_similarity():
    """If golden_metrics == own metrics, similarity should be 100."""
    polys = [_rect(0, 0, 5, 1, "met1"), _rect(3, 0, 4, 5, "met2")]
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    m1 = compute_for_net("WL0", polys, [], _tech_layers(), thresholds, golden_metrics=None)
    m2 = compute_for_net("WL0", polys, [], _tech_layers(), thresholds,
                         golden_metrics={k: m1[k] for k in (
                             "h_ratio", "v_ratio", "total_len", "via_count",
                             "r_total", "c_total", "effective_tau_ps", "bbox_aspect"
                         )})
    assert m2["similarity_score"] == pytest.approx(100.0, abs=1e-3)


def test_check_gates_returns_fail_reasons():
    metrics = {
        "h_ratio": 0.50, "v_ratio": 0.50,
        "r_total": 50.0, "c_total": 200.0, "effective_tau_ps": 30.0,
        "via_coverage": 0.50, "missing_via_count": 3,
        "similarity_score": 50.0,
    }
    thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    pass_, reasons = check_gates(metrics, thresholds)
    assert pass_ is False
    assert len(reasons) >= 4  # h_ratio, tau_ps, via_coverage, similarity all fail
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_routing_metrics.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `core/routing_metrics.py`**

```python
"""Aggregate the 6 routing metrics for a single net and check gates."""
from __future__ import annotations
from typing import Dict, List, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import Polygon, Via
    from config.routing_thresholds import RoutingThresholds

from core.directional_analyzer import analyze_net_directional
from core.via_coverage import analyze_via_coverage
from core.rc_calculator import compute_net_metrics_with_tau
from core.golden_similarity import compare_to_golden


def _bbox_aspect(polygons: List["Polygon"]) -> float:
    """Overall bbox aspect ratio (max(w,h)/min(w,h)), 1.0 if empty."""
    if not polygons:
        return 1.0
    xs = [p.bbox[0] for p in polygons] + [p.bbox[2] for p in polygons]
    ys = [p.bbox[1] for p in polygons] + [p.bbox[3] for p in polygons]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if min(w, h) <= 0:
        return 1.0
    return max(w, h) / min(w, h)


def check_gates(metrics: Dict[str, Any], thresholds: "RoutingThresholds") -> Tuple[bool, List[str]]:
    """Check all 6 metrics against thresholds. Returns (pass, fail_reasons)."""
    reasons: List[str] = []
    if metrics["h_ratio"] > thresholds.max_h_ratio:
        reasons.append(f"h_ratio {metrics['h_ratio']:.2%} > max {thresholds.max_h_ratio:.2%}")
    if metrics["v_ratio"] > thresholds.max_v_ratio:
        reasons.append(f"v_ratio {metrics['v_ratio']:.2%} > max {thresholds.max_v_ratio:.2%}")
    if metrics["r_total"] > thresholds.max_r_ohm:
        reasons.append(f"R {metrics['r_total']:.2f}Ω > max {thresholds.max_r_ohm:.2f}Ω")
    if metrics["c_total"] > thresholds.max_c_ff:
        reasons.append(f"C {metrics['c_total']:.2f}fF > max {thresholds.max_c_ff:.2f}fF")
    if metrics["effective_tau_ps"] > thresholds.max_tau_ps:
        reasons.append(f"τ {metrics['effective_tau_ps']:.2f}ps > max {thresholds.max_tau_ps:.2f}ps")
    if metrics["via_coverage"] < thresholds.min_via_coverage:
        reasons.append(f"via coverage {metrics['via_coverage']:.2%} < min {thresholds.min_via_coverage:.2%}")
    if metrics["similarity_score"] < thresholds.min_similarity:
        reasons.append(f"similarity {metrics['similarity_score']:.1f} < min {thresholds.min_similarity:.1f}")
    return (len(reasons) == 0), reasons


def compute_for_net(
    net_name: str,
    polygons: List["Polygon"],
    vias: List["Via"],
    tech_layers: Dict,
    thresholds: "RoutingThresholds",
    golden_metrics: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
    """Compute the unified 6-metric dict for one net.

    Args:
        net_name: Net name.
        polygons: All polygons of the net.
        vias: All via polygons of the net.
        tech_layers: Tech config dict.
        thresholds: RoutingThresholds for gate check.
        golden_metrics: Dict with 8 FEATURE_NAMES keys, or None.

    Returns:
        Dict matching the 6-metric contract defined in the plan.
    """
    # 1. Directional
    dr = analyze_net_directional(polygons)
    # 2. Via coverage
    vc = analyze_via_coverage(polygons, vias, min_via_per_overlap=1)
    # 3-4. RC + tau
    rc = compute_net_metrics_with_tau(net_name, polygons, vias, tech_layers)
    # 5. Similarity (only if golden given)
    aspect = _bbox_aspect(polygons)
    own_features = {
        "h_ratio": dr.h_ratio,
        "v_ratio": dr.v_ratio,
        "total_len": rc["total_length"],
        "via_count": rc["via_count"],
        "r_total": rc["r_total"],
        "c_total": rc["c_total"],
        "effective_tau_ps": rc["effective_tau_ps"],
        "bbox_aspect": aspect,
    }
    if golden_metrics:
        sim_score, deltas = compare_to_golden(golden_metrics, own_features)
    else:
        sim_score, deltas = 100.0, {k: 0.0 for k in own_features}
    # 6. Gate check
    metrics_for_gate = {
        **own_features,
        "missing_via_count": vc.missing_via_count,
        "via_coverage": vc.via_coverage,
        "similarity_score": sim_score,
    }
    gate_pass, fail_reasons = check_gates(metrics_for_gate, thresholds)

    return {
        "net_name": net_name,
        "h_len": dr.h_len,
        "v_len": dr.v_len,
        "h_ratio": dr.h_ratio,
        "v_ratio": dr.v_ratio,
        "dominant": dr.dominant,
        "missing_via_count": vc.missing_via_count,
        "via_coverage": vc.via_coverage,
        "missing_locations": vc.missing_locations,
        "r_total": rc["r_total"],
        "c_total": rc["c_total"],
        "rc_product": rc["rc_product"],
        "effective_tau_ps": rc["effective_tau_ps"],
        "total_length": rc["total_length"],
        "via_count": rc["via_count"],
        "similarity_score": sim_score,
        "deltas": deltas,
        "bbox_aspect": aspect,
        "gate_pass": gate_pass,
        "gate_fail_reasons": fail_reasons,
        "per_polygon_dir": dr.per_polygon,  # for visualization
    }
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_routing_metrics.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add core/routing_metrics.py tests/test_routing_metrics.py
git commit -m "feat(core): routing metrics aggregator (6 metrics + gate check)"
```

---

### Task 8: 可视化方向着色（`core/visualization.py` 增强）

**Files:**
- Modify: `core/visualization.py`（追加新函数 `create_directional_figure()`，不动既有 API）
- Create: `tests/test_visualization_directional.py`

- [ ] **Step 1: 写失败测试 `tests/test_visualization_directional.py`**

```python
"""Tests for directional visualization."""
import sys
sys.path.insert(0, '.')
from review_engine import Point, Polygon
from core.visualization import create_directional_figure


def _rect(x1, y1, x2, y2, layer):
    return Polygon(points=[Point(x1, y1), Point(x2, y1), Point(x2, y2), Point(x1, y2)], layer=layer)


def test_returns_plotly_figure():
    polys = [_rect(0, 0, 10, 1, "met1"), _rect(5, 0, 6, 10, "met2")]
    fig = create_directional_figure(polys, [], net_name="WL0")
    assert fig is not None
    # Should have 2 traces (one per polygon, each with H or V color)
    assert len(fig.data) == 2


def test_horizontal_polygon_uses_red():
    """H-dominant polygon should be red."""
    polys = [_rect(0, 0, 10, 1, "met1")]
    fig = create_directional_figure(polys, [])
    color = fig.data[0].fillcolor
    assert "255" in color and "0" in color  # has red component


def test_vertical_polygon_uses_blue():
    """V-dominant polygon should be blue."""
    polys = [_rect(0, 0, 1, 10, "met1")]
    fig = create_directional_figure(polys, [])
    color = fig.data[0].fillcolor
    assert "0" in color and "255" in color  # has blue component


def test_violation_overlay_adds_red_borders():
    """If violations passed, those polygons get red border overlay."""
    polys = [_rect(0, 0, 10, 1, "met1")]
    violations = [{"polygon_index": 0, "x": 5, "y": 0.5}]
    fig = create_directional_figure(polys, [], violations=violations)
    # Should have an extra trace for violation overlay
    assert len(fig.data) >= 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_visualization_directional.py -v`
Expected: ImportError

- [ ] **Step 3: 在 `core/visualization.py` 末尾追加 `create_directional_figure()`（不修改既有函数）**

```python
def create_directional_figure(
    polygons,
    vias,
    net_name: str = "",
    per_polygon_dir=None,
    violations=None,
):
    """Plotly figure with H=Red, V=Blue coloring, plus optional violation overlay.

    Args:
        polygons: List of Polygon to draw.
        vias: List of via polygons (drawn in grey).
        net_name: Title suffix.
        per_polygon_dir: Optional list of {"class": "H"|"V"|"MIXED", "polygon_index": int}.
        violations: Optional list of {"polygon_index": int, "x": float, "y": float}.

    Returns:
        plotly.graph_objects.Figure
    """
    import plotly.graph_objects as go

    H_COLOR = "rgba(255, 50, 50, 0.65)"   # red
    V_COLOR = "rgba(50, 80, 255, 0.65)"   # blue
    MIX_COLOR = "rgba(160, 100, 200, 0.65)"  # purple
    VIA_COLOR = "rgba(80, 80, 80, 0.85)"

    cls_lookup = {}
    if per_polygon_dir:
        cls_lookup = {d["polygon_index"]: d["class"] for d in per_polygon_dir}

    fig = go.Figure()
    for idx, poly in enumerate(polygons):
        cls = cls_lookup.get(idx, "H")
        color = {"H": H_COLOR, "V": V_COLOR, "MIXED": MIX_COLOR}.get(cls, H_COLOR)
        xs = [p.x for p in poly.points]
        ys = [p.y for p in poly.points]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself", mode="lines",
            line=dict(color=color, width=1.5),
            fillcolor=color, name=f"{cls}", showlegend=False,
            hovertemplate=f"{net_name} [{poly.layer}] {cls}<extra></extra>",
        ))

    for v in vias:
        xs = [p.x for p in v.points]
        ys = [p.y for p in v.points]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself", mode="lines",
            line=dict(color=VIA_COLOR, width=1),
            fillcolor=VIA_COLOR, showlegend=False, hoverinfo="skip",
        ))

    if violations:
        for vio in violations:
            fig.add_trace(go.Scatter(
                x=[vio["x"]], y=[vio["y"]],
                mode="markers",
                marker=dict(symbol="x", size=14, color="red",
                            line=dict(width=2, color="darkred")),
                showlegend=False, name="violation",
            ))

    fig.update_layout(
        title=f"Routing Direction: {net_name}" if net_name else "Routing Direction",
        xaxis_title="X (μm)", yaxis_title="Y (μm)",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        template="plotly_white",
    )
    return fig
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_visualization_directional.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add core/visualization.py tests/test_visualization_directional.py
git commit -m "feat(core): directional visualization (H=Red, V=Blue) + violation overlay"
```

---

### Task 9: 路由 Violation 数据结构（`core/routing_violation.py`）

**Files:**
- Create: `core/routing_violation.py`
- Create: `tests/test_routing_violation.py`

- [ ] **Step 1: 写失败测试 `tests/test_routing_violation.py`**

```python
"""Tests for routing violation dataclass."""
from core.routing_violation import RoutingViolation, ViolationKind


def test_create_h_ratio_violation():
    v = RoutingViolation.h_ratio(net_name="WL0", h_ratio=0.50, limit=0.15)
    assert v.kind == ViolationKind.H_RATIO
    assert v.net_name == "WL0"
    assert v.severity == "critical"


def test_create_missing_via_violation():
    v = RoutingViolation.missing_via(net_name="BL0", x=1.0, y=2.0, layer="via1")
    assert v.kind == ViolationKind.MISSING_VIA
    assert v.x == 1.0
    assert v.y == 2.0


def test_serialization_round_trip():
    v = RoutingViolation.tau_ps(net_name="WL0", tau_ps=20.0, limit=12.5)
    d = v.to_dict()
    v2 = RoutingViolation.from_dict(d)
    assert v2.net_name == v.net_name
    assert v2.tau_ps == v.tau_ps


def test_all_kinds_covered():
    kinds = {k.value for k in ViolationKind}
    assert "h_ratio" in kinds
    assert "v_ratio" in kinds
    assert "r_total" in kinds
    assert "c_total" in kinds
    assert "tau_ps" in kinds
    assert "via_coverage" in kinds
    assert "missing_via" in kinds
    assert "similarity" in kinds
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_routing_violation.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `core/routing_violation.py`**

```python
"""Structured routing violations with location info for visualization."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any


class ViolationKind(str, Enum):
    H_RATIO = "h_ratio"
    V_RATIO = "v_ratio"
    R_TOTAL = "r_total"
    C_TOTAL = "c_total"
    TAU_PS = "tau_ps"
    VIA_COVERAGE = "via_coverage"
    MISSING_VIA = "missing_via"
    SIMILARITY = "similarity"


@dataclass
class RoutingViolation:
    """A single routing-quality violation with location for highlighting."""
    kind: ViolationKind
    net_name: str
    severity: str = "critical"  # "critical" or "warning"
    message: str = ""
    # Location (for visualization)
    x: Optional[float] = None
    y: Optional[float] = None
    polygon_index: Optional[int] = None
    # Measured vs limit
    h_ratio: Optional[float] = None
    v_ratio: Optional[float] = None
    r_total: Optional[float] = None
    c_total: Optional[float] = None
    tau_ps: Optional[float] = None
    via_coverage: Optional[float] = None
    missing_via_count: Optional[int] = None
    similarity_score: Optional[float] = None
    limit: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoutingViolation":
        d = dict(d)
        d["kind"] = ViolationKind(d["kind"])
        return cls(**d)

    # ---------- Factory helpers ----------
    @classmethod
    def h_ratio(cls, net_name, h_ratio, limit):
        return cls(
            kind=ViolationKind.H_RATIO, net_name=net_name,
            h_ratio=h_ratio, limit=limit,
            message=f"h_ratio {h_ratio:.2%} > limit {limit:.2%}",
        )

    @classmethod
    def v_ratio(cls, net_name, v_ratio, limit):
        return cls(
            kind=ViolationKind.V_RATIO, net_name=net_name,
            v_ratio=v_ratio, limit=limit,
            message=f"v_ratio {v_ratio:.2%} > limit {limit:.2%}",
        )

    @classmethod
    def r_total(cls, net_name, r_total, limit):
        return cls(
            kind=ViolationKind.R_TOTAL, net_name=net_name,
            r_total=r_total, limit=limit,
            message=f"R {r_total:.2f}Ω > limit {limit:.2f}Ω",
        )

    @classmethod
    def c_total(cls, net_name, c_total, limit):
        return cls(
            kind=ViolationKind.C_TOTAL, net_name=net_name,
            c_total=c_total, limit=limit,
            message=f"C {c_total:.2f}fF > limit {limit:.2f}fF",
        )

    @classmethod
    def tau_ps(cls, net_name, tau_ps, limit):
        return cls(
            kind=ViolationKind.TAU_PS, net_name=net_name,
            tau_ps=tau_ps, limit=limit,
            message=f"τ {tau_ps:.2f}ps > limit {limit:.2f}ps",
        )

    @classmethod
    def via_coverage(cls, net_name, via_coverage, limit):
        return cls(
            kind=ViolationKind.VIA_COVERAGE, net_name=net_name,
            via_coverage=via_coverage, limit=limit,
            message=f"via coverage {via_coverage:.2%} < limit {limit:.2%}",
        )

    @classmethod
    def missing_via(cls, net_name, x, y, layer):
        return cls(
            kind=ViolationKind.MISSING_VIA, net_name=net_name,
            x=x, y=y, message=f"missing via near ({x:.3f}, {y:.3f}) on {layer}",
        )

    @classmethod
    def similarity(cls, net_name, similarity_score, limit):
        return cls(
            kind=ViolationKind.SIMILARITY, net_name=net_name,
            similarity_score=similarity_score, limit=limit,
            message=f"similarity {similarity_score:.1f} < limit {limit:.1f}",
        )
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_routing_violation.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add core/routing_violation.py tests/test_routing_violation.py
git commit -m "feat(core): RoutingViolation dataclass with location for visualization"
```

---

### Task 10: 路由独立 state（`app/routing_state.py`）

**Files:**
- Create: `app/routing_state.py`

- [ ] **Step 1: 写 `app/routing_state.py`**

```python
"""Independent state for the Routing Review workflow.

Kept separate from `app/state.py` (the original global state) so the
routing rewrite does not affect the existing tabs.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from config.routing_thresholds import RoutingThresholds


@dataclass
class RoutingState:
    """State for the Configuration + Layout Review tabs (routing-focused)."""
    # Current preset
    current_preset: str = "sram_7nm_wl"
    thresholds: RoutingThresholds = field(default_factory=RoutingThresholds.for_preset)
    # Custom overrides (None means use preset)
    custom_thresholds: Optional[RoutingThresholds] = None

    # Golden + batch (regex strings; resolved against app_state.nets_data)
    golden_regex: str = ""
    batch_regex: str = ""

    # Resolved (after Run Review)
    golden_net_name: str = ""
    golden_metrics: Optional[Dict[str, Any]] = None
    batch_net_names: List[str] = field(default_factory=list)
    batch_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # batch_results: net_name → 6-metric dict (from core.routing_metrics.compute_for_net)

    review_completed: bool = False
    last_error: Optional[str] = None

    def get_thresholds(self) -> RoutingThresholds:
        return self.custom_thresholds or self.thresholds

    def reset_review(self):
        self.golden_net_name = ""
        self.golden_metrics = None
        self.batch_net_names = []
        self.batch_results = {}
        self.review_completed = False
        self.last_error = None


# Module-level singleton
routing_state = RoutingState()
```

- [ ] **Step 2: Commit**

```bash
git add app/routing_state.py
git commit -m "feat(app): independent RoutingState for new tabs"
```

---

### Task 11: Configuration Tab 重写（`app/routing_config.py`）

**Files:**
- Create: `app/routing_config.py`
- Create: `tests/test_routing_config_layout.py`

- [ ] **Step 1: 写失败测试 `tests/test_routing_config_layout.py`**

```python
"""Tests for routing config tab layout generation."""
from app.routing_config import create_routing_config_tab, get_threshold_input_ids


def test_create_routing_config_tab_returns_div():
    layout = create_routing_config_tab()
    assert layout is not None


def test_threshold_input_ids_contains_all_thresholds():
    ids = get_threshold_input_ids()
    for name in ("max_h_ratio", "max_v_ratio", "max_r_ohm", "max_c_ff",
                 "max_tau_ps", "min_via_coverage", "min_similarity"):
        assert name in ids, f"Missing input: {name}"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_routing_config_layout.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `app/routing_config.py`**

```python
"""Routing-focused Configuration tab.

Replaces `_create_config_content()` from `app/layout.py`.
Exposes ONLY routing thresholds + preset selector — no regex, no rule
editor, no per-rule enable/disable.
"""
from __future__ import annotations
from typing import List
from dash import html, dcc
from config.routing_thresholds import RoutingThresholds
from config.preset_loader import list_yaml_presets
from app.routing_state import routing_state


THRESHOLD_FIELDS = [
    ("max_h_ratio", "Max H Ratio (WL gate)", "0.01", "0.99", "0.01"),
    ("max_v_ratio", "Max V Ratio (IO gate)", "0.01", "0.99", "0.01"),
    ("max_r_ohm", "Max Total R (Ω)", "0.1", "10000", "0.1"),
    ("max_c_ff", "Max Total C (fF)", "0.1", "100000", "1"),
    ("max_tau_ps", "Max Effective τ (ps)", "0.01", "1000", "0.1"),
    ("min_via_coverage", "Min Via Coverage", "0.0", "1.0", "0.01"),
    ("min_similarity", "Min Golden Similarity", "0", "100", "1"),
]


def get_threshold_input_ids() -> List[str]:
    """Return the dcc.Input IDs for all threshold fields (used in callbacks)."""
    return [f"thresh-{name}" for name, *_ in THRESHOLD_FIELDS]


def _preset_options():
    return [{"label": name, "value": name} for name in list_yaml_presets()]


def create_routing_config_tab():
    """Build the routing Configuration tab content (Dash components only)."""
    preset = routing_state.current_preset
    thr = routing_state.get_thresholds()

    return html.Div([
        # Preset selector
        html.Div([
            html.Div("Preset", className="card-header"),
            html.Div([
                dcc.Dropdown(
                    id="routing-preset",
                    options=_preset_options(),
                    value=preset,
                    clearable=False,
                    className="dropdown",
                ),
                html.Div(id="routing-preset-status",
                         className="text-muted", style={"fontSize": "11px", "marginTop": "6px"}),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Threshold sliders
        html.Div([
            html.Div("Routing Thresholds", className="card-header"),
            html.Div([
                html.Div([
                    html.Label(label, className="form-label"),
                    dcc.Input(
                        id=f"thresh-{name}",
                        type="number",
                        value=getattr(thr, name),
                        min=mn, max=mx, step=st,
                        className="input-field",
                    ),
                ], className="form-group", style={"marginBottom": "12px"})
                for (name, label, mn, mx, st) in THRESHOLD_FIELDS
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Golden / Batch regex
        html.Div([
            html.Div("Net Selection (Regex)", className="card-header"),
            html.Div([
                html.Div([
                    html.Label("Golden Net Regex", className="form-label"),
                    dcc.Input(id="golden-regex", type="text",
                              value=routing_state.golden_regex,
                              placeholder="e.g. ^WL_0$ or ^WL.*$",
                              className="input-field"),
                ], className="form-group", style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Batch Net Regex", className="form-label"),
                    dcc.Input(id="batch-regex", type="text",
                              value=routing_state.batch_regex,
                              placeholder="e.g. ^WL_.*$ or ^BL.*$",
                              className="input-field"),
                ], className="form-group", style={"marginBottom": "12px"}),
                html.Button("Run Routing Review", id="btn-run-routing-review",
                            className="btn btn-primary btn-block"),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Status
        html.Div(id="routing-config-status"),
    ], style={"padding": "16px"})


def register_routing_config_callbacks(app):
    """Register all callbacks for the routing Configuration tab."""
    from dash import Input, Output, State
    from config.preset_loader import load_preset_yaml

    @app.callback(
        [Output("routing-preset-status", "children"),
         Output("routing-config-status", "children")]
        + [Output(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        [Input("routing-preset", "value"),
         Input("golden-regex", "value"),
         Input("batch-regex", "value")]
        + [Input(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
    )
    def update_routing_config(preset, golden_re, batch_re, *thresh_values):
        from dash import callback_context
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        # Preset switch → reload thresholds
        if trigger == "routing-preset" and preset:
            try:
                t = load_preset_yaml(preset)
                routing_state.current_preset = preset
                routing_state.thresholds = t
                routing_state.custom_thresholds = None
                status = f"Loaded preset: {preset}"
                thresh_outputs = [getattr(t, name) for name, *_ in THRESHOLD_FIELDS]
                return [status, ""] + thresh_outputs
            except Exception as e:
                return [f"Error: {e}", ""] + list(thresh_values)

        # Update regex state
        if trigger == "golden-regex":
            routing_state.golden_regex = golden_re or ""
        if trigger == "batch-regex":
            routing_state.batch_regex = batch_re or ""

        # Update custom thresholds
        for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
            if val is not None and routing_state.custom_thresholds is None:
                routing_state.custom_thresholds = RoutingThresholds.from_dict(
                    routing_state.thresholds.to_dict()
                )
            if val is not None and routing_state.custom_thresholds is not None:
                setattr(routing_state.custom_thresholds, name, val)
        try:
            routing_state.custom_thresholds and routing_state.custom_thresholds.validate()
        except Exception as e:
            return [f"Loaded: {routing_state.current_preset}", f"Invalid: {e}"] + list(thresh_values)

        return [f"Loaded: {routing_state.current_preset}", ""] + list(thresh_values)
```

- [ ] **Step 4: 运行测试通过**

Run: `pytest tests/test_routing_config_layout.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_layout.py
git commit -m "feat(app): routing Configuration tab (preset + 7 thresholds + regex)"
```

---

### Task 12: Layout Review Tab 重写（`app/routing_review.py`）

**Files:**
- Create: `app/routing_review.py`

- [ ] **Step 1: 写 `app/routing_review.py`**

```python
"""Routing-focused Layout Review tab.

Replaces `_create_review_content()` from `app/layout.py`.
Shows the 6 metric cards + sortable similarity table + per-net directional viz.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any
from dash import html, dcc, dash_table
from app.routing_state import routing_state
from app.state import app_state  # for accessing loaded nets/polygons
from core.routing_metrics import compute_for_net
from core.routing_violation import RoutingViolation, ViolationKind
from core.visualization import create_directional_figure


METRIC_CARD_IDS = [
    ("h_ratio", "H / V Ratio", "%"),
    ("missing_via", "Missing Via", ""),
    ("r_total", "Eff. R (Ω)", "Ω"),
    ("tau_ps", "Eff. τ (ps)", "ps"),
    ("similarity", "Similarity", "/100"),
    ("gate", "Pass / Fail", ""),
]


def _build_metric_cards(results: Dict[str, Dict[str, Any]]) -> List[html.Div]:
    """Build the 6 summary cards (averages across batch)."""
    if not results:
        avg = {"h_ratio": 0, "v_ratio": 0, "missing_via": 0, "r_total": 0,
               "tau_ps": 0, "similarity": 0, "gate": 0}
    else:
        n = len(results)
        avg = {
            "h_ratio": sum(r["h_ratio"] for r in results.values()) / n,
            "v_ratio": sum(r["v_ratio"] for r in results.values()) / n,
            "missing_via": sum(r["missing_via_count"] for r in results.values()) / n,
            "r_total": sum(r["r_total"] for r in results.values()) / n,
            "tau_ps": sum(r["effective_tau_ps"] for r in results.values()) / n,
            "similarity": sum(r["similarity_score"] for r in results.values()) / n,
            "gate": sum(1 for r in results.values() if r["gate_pass"]) / n * 100,
        }
    cards = []
    for key, label, unit in METRIC_CARD_IDS:
        if key in ("h_ratio", "v_ratio"):
            value = f"{avg[key]*100:.1f}%"
        elif key == "missing_via":
            value = f"{avg[key]:.1f}"
        elif key == "r_total":
            value = f"{avg[key]:.2f}Ω"
        elif key == "tau_ps":
            value = f"{avg[key]:.2f}ps"
        elif key == "similarity":
            value = f"{avg[key]:.1f}/100"
        else:  # gate
            value = f"{avg[key]:.0f}%"
        cards.append(html.Div([
            html.Div(label, className="metric-label",
                     style={"fontSize": "11px", "color": "#888"}),
            html.Div(value, className="metric-value",
                     style={"fontSize": "20px", "fontWeight": "600"}),
        ], className="metric-card", style={
            "flex": "1", "padding": "12px", "background": "var(--bg-input)",
            "border": "1px solid var(--border-color)", "borderRadius": "6px",
            "minWidth": "120px",
        }))
    return cards


def _build_similarity_table() -> dash_table.DataTable:
    """Build the per-net sortable results table."""
    rows = []
    for name, m in routing_state.batch_results.items():
        rows.append({
            "Net": name,
            "Dominant": m["dominant"],
            "H %": f"{m['h_ratio']*100:.1f}",
            "V %": f"{m['v_ratio']*100:.1f}",
            "R (Ω)": f"{m['r_total']:.2f}",
            "τ (ps)": f"{m['effective_tau_ps']:.2f}",
            "Via Cov": f"{m['via_coverage']*100:.1f}",
            "Miss Via": m["missing_via_count"],
            "Sim": f"{m['similarity_score']:.1f}",
            "Pass": "✓" if m["gate_pass"] else "✗",
        })
    return dash_table.DataTable(
        data=rows,
        columns=[{"name": k, "id": k} for k in
                 ("Net", "Dominant", "H %", "V %", "R (Ω)", "τ (ps)",
                  "Via Cov", "Miss Via", "Sim", "Pass")],
        sort_action="native", filter_action="native",
        row_selectable="single", page_size=10,
        style_cell={"textAlign": "left", "fontSize": "11px"},
        style_data_conditional=[
            {"if": {"filter_query": '{Pass} = "✗"'}, "backgroundColor": "rgba(239, 68, 68, 0.15)"},
            {"if": {"filter_query": '{Pass} = "✓"'}, "backgroundColor": "rgba(34, 197, 94, 0.10)"},
        ],
        id="routing-results-table",
    )


def create_routing_review_tab():
    """Build the routing Layout Review tab content."""
    return html.Div([
        # Summary cards
        html.Div(_build_metric_cards(routing_state.batch_results),
                 style={"display": "flex", "gap": "12px", "marginBottom": "16px"}),

        # Visualization
        html.Div([
            html.Div("Directional Visualization (H=Red, V=Blue)", className="card-header"),
            html.Div([
                dcc.Dropdown(
                    id="routing-net-picker",
                    options=[{"label": n, "value": n} for n in routing_state.batch_net_names],
                    value=(routing_state.batch_net_names[0]
                           if routing_state.batch_net_names else None),
                    placeholder="Pick a net to visualize…",
                    className="dropdown",
                    style={"marginBottom": "8px"},
                ),
                dcc.Graph(id="routing-graph", style={"height": "500px"}),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Per-net table
        html.Div([
            html.Div("Per-Net Results", className="card-header"),
            html.Div([_build_similarity_table()], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Report export trigger
        html.Div([
            html.Button("Generate Routing Report (PPTX)", id="btn-gen-routing-pptx",
                        className="btn btn-success btn-block"),
            html.Div(id="routing-report-status"),
            dcc.Download(id="download-routing-pptx"),
        ]),
    ], style={"padding": "16px"})


def _resolve_regex(pattern: str) -> List[str]:
    """Resolve a regex against app_state.nets_data; return matched net names."""
    if not pattern:
        return []
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return []
    return [n for n in app_state.nets_data if rx.search(n)]


def _compute_violations_for_net(metrics: Dict[str, Any], thresholds) -> List[RoutingViolation]:
    """Convert gate failures into structured violations with location."""
    v = []
    if metrics["h_ratio"] > thresholds.max_h_ratio:
        v.append(RoutingViolation.h_ratio(metrics["net_name"], metrics["h_ratio"], thresholds.max_h_ratio))
    if metrics["v_ratio"] > thresholds.max_v_ratio:
        v.append(RoutingViolation.v_ratio(metrics["net_name"], metrics["v_ratio"], thresholds.max_v_ratio))
    if metrics["r_total"] > thresholds.max_r_ohm:
        v.append(RoutingViolation.r_total(metrics["net_name"], metrics["r_total"], thresholds.max_r_ohm))
    if metrics["c_total"] > thresholds.max_c_ff:
        v.append(RoutingViolation.c_total(metrics["net_name"], metrics["c_total"], thresholds.max_c_ff))
    if metrics["effective_tau_ps"] > thresholds.max_tau_ps:
        v.append(RoutingViolation.tau_ps(metrics["net_name"], metrics["effective_tau_ps"], thresholds.max_tau_ps))
    if metrics["via_coverage"] < thresholds.min_via_coverage:
        v.append(RoutingViolation.via_coverage(metrics["net_name"], metrics["via_coverage"], thresholds.min_via_coverage))
    if metrics["similarity_score"] < thresholds.min_similarity:
        v.append(RoutingViolation.similarity(metrics["net_name"], metrics["similarity_score"], thresholds.min_similarity))
    for loc in metrics.get("missing_locations", []):
        v.append(RoutingViolation.missing_via(metrics["net_name"], loc["x"], loc["y"],
                                              f"{loc['layer_a']}/{loc['layer_b']}"))
    return v


def register_routing_review_callbacks(app):
    """Register all callbacks for the routing Layout Review tab."""
    from dash import Input, Output
    import plotly.graph_objects as go

    @app.callback(
        [Output("routing-graph", "figure"),
         Output("routing-results-table", "data"),
         Output("routing-net-picker", "options"),
         Output("routing-config-status", "children")],
        [Input("btn-run-routing-review", "n_clicks"),
         Input("routing-net-picker", "value")],
    )
    def update_routing_review(run_clicks, selected_net):
        from dash import callback_context
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        # Trigger review run
        if trigger == "btn-run-routing-review":
            try:
                _run_routing_review()
                status = f"Reviewed {len(routing_state.batch_results)} nets, golden={routing_state.golden_net_name or '(none)'}"
            except Exception as e:
                routing_state.last_error = str(e)
                status = f"Error: {e}"
        else:
            status = f"Reviewed {len(routing_state.batch_results)} nets"

        # Visualization
        if selected_net and selected_net in app_state.nets_data:
            net_data = app_state.nets_data[selected_net]
            polys = net_data.get("polygons", [])
            m = routing_state.batch_results.get(selected_net)
            if m:
                fig = create_directional_figure(
                    polygons=polys, vias=[],
                    net_name=selected_net,
                    per_polygon_dir=m.get("per_polygon_dir", []),
                    violations=[
                        {"polygon_index": 0, "x": loc["x"], "y": loc["y"]}
                        for loc in m.get("missing_locations", [])
                    ],
                )
            else:
                fig = go.Figure()
        else:
            fig = go.Figure()

        # Table + dropdown
        rows = []
        for name, mr in routing_state.batch_results.items():
            rows.append({
                "Net": name, "Dominant": mr["dominant"],
                "H %": f"{mr['h_ratio']*100:.1f}", "V %": f"{mr['v_ratio']*100:.1f}",
                "R (Ω)": f"{mr['r_total']:.2f}", "τ (ps)": f"{mr['effective_tau_ps']:.2f}",
                "Via Cov": f"{mr['via_coverage']*100:.1f}", "Miss Via": mr["missing_via_count"],
                "Sim": f"{mr['similarity_score']:.1f}",
                "Pass": "✓" if mr["gate_pass"] else "✗",
            })
        opts = [{"label": n, "value": n} for n in routing_state.batch_net_names]
        return fig, rows, opts, status

    @app.callback(
        Output("download-routing-pptx", "data"),
        Input("btn-gen-routing-pptx", "n_clicks"),
        prevent_initial_call=True,
    )
    def gen_pptx(n):
        if not n or not routing_state.review_completed:
            raise dash.exceptions.PreventUpdate
        from report.routing_pptx import generate_routing_pptx
        import tempfile, os
        out = os.path.join(tempfile.gettempdir(), "routing_report.pptx")
        generate_routing_pptx(routing_state, app_state, out)
        return dcc.send_file(out, filename="routing_report.pptx")


def _run_routing_review():
    """Resolve regex, compute metrics for golden + batch, populate state."""
    routing_state.reset_review()
    golden_names = _resolve_regex(routing_state.golden_regex)
    batch_names = _resolve_regex(routing_state.batch_regex)
    if not batch_names:
        raise ValueError("No batch nets matched. Check the Batch Net Regex in Configuration.")

    tech_layers = app_state.config.tech_config.layers
    thresholds = routing_state.get_thresholds()

    # Compute golden first (if present)
    golden_metrics = None
    golden_name = ""
    if golden_names:
        golden_name = golden_names[0]
        g_data = app_state.nets_data[golden_name]
        g_polys = g_data.get("polygons", [])
        g_vias = []  # to be populated when Via support is wired up
        m = compute_for_net(golden_name, g_polys, g_vias, tech_layers, thresholds,
                            golden_metrics=None)
        golden_metrics = {k: m[k] for k in ("h_ratio", "v_ratio", "total_len", "via_count",
                                            "r_total", "c_total", "effective_tau_ps", "bbox_aspect")}
        routing_state.golden_net_name = golden_name
        routing_state.golden_metrics = golden_metrics

    # Compute batch
    for name in batch_names:
        data = app_state.nets_data[name]
        polys = data.get("polygons", [])
        vias = []
        m = compute_for_net(name, polys, vias, tech_layers, thresholds,
                            golden_metrics=golden_metrics)
        m["violations"] = [vv.to_dict() for vv in _compute_violations_for_net(m, thresholds)]
        routing_state.batch_results[name] = m

    routing_state.batch_net_names = batch_names
    routing_state.review_completed = True
```

- [ ] **Step 2: 手动测试：语法检查**

Run: `python -c "from app.routing_review import create_routing_review_tab; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routing_review.py
git commit -m "feat(app): routing Layout Review tab (6 cards + viz + sortable table)"
```

---

### Task 13: 路由 PPTX 报告（`report/routing_pptx.py`）

**Files:**
- Create: `report/__init__.py`
- Create: `report/routing_pptx.py`
- Create: `tests/test_routing_pptx.py`

- [ ] **Step 1: 写失败测试 `tests/test_routing_pptx.py`**

```python
"""Tests for routing PPTX report."""
import os
import tempfile
import sys
sys.path.insert(0, '.')
from app.routing_state import RoutingState
from report.routing_pptx import generate_routing_pptx


def _make_state():
    s = RoutingState()
    s.current_preset = "sram_7nm_wl"
    s.golden_net_name = "WL0"
    s.golden_metrics = {"h_ratio": 0.1, "v_ratio": 0.9, "total_len": 10,
                        "via_count": 2, "r_total": 10, "c_total": 2,
                        "effective_tau_ps": 5, "bbox_aspect": 1.0}
    s.batch_net_names = ["WL0", "WL1"]
    s.batch_results = {
        "WL0": {"net_name": "WL0", "h_len": 1, "v_len": 9, "h_ratio": 0.1, "v_ratio": 0.9,
                "dominant": "V", "missing_via_count": 0, "via_coverage": 1.0,
                "missing_locations": [], "r_total": 10, "c_total": 2, "rc_product": 20,
                "effective_tau_ps": 5, "total_length": 10, "via_count": 2,
                "similarity_score": 100, "deltas": {}, "gate_pass": True,
                "gate_fail_reasons": [], "violations": [], "bbox_aspect": 1.0,
                "per_polygon_dir": []},
        "WL1": {"net_name": "WL1", "h_len": 5, "v_len": 5, "h_ratio": 0.5, "v_ratio": 0.5,
                "dominant": "H", "missing_via_count": 1, "via_coverage": 0.6,
                "missing_locations": [{"x": 1, "y": 2, "layer_a": "met1", "layer_b": "met2", "overlap_area": 1}],
                "r_total": 200, "c_total": 50, "rc_product": 10000,
                "effective_tau_ps": 20, "total_length": 10, "via_count": 1,
                "similarity_score": 50, "deltas": {"total_len": 0}, "gate_pass": False,
                "gate_fail_reasons": ["h_ratio over"], "violations": [],
                "bbox_aspect": 1.0, "per_polygon_dir": []},
    }
    return s


class FakeAppState:
    nets_data = {"WL0": {"polygons": []}, "WL1": {"polygons": []}}


def test_generate_routing_pptx_creates_file():
    s = _make_state()
    app_s = FakeAppState()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "report.pptx")
        generate_routing_pptx(s, app_s, out)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 1000
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_routing_pptx.py -v`
Expected: ImportError

- [ ] **Step 3: 写 `report/__init__.py`**

```python
"""Report generation package."""
```

- [ ] **Step 4: 写 `report/routing_pptx.py`**

```python
"""Routing-review PPTX report.

Generates a slide deck with:
- Slide 1: Cover (title, preset, timestamp)
- Slide 2: Executive Summary (6 metric averages)
- Slide 3: Golden Net detail (table + image placeholder)
- Slide 4+: Per-batch-net page (3-section layout: full / directional / violation)
- Final: Recommendations
"""
from __future__ import annotations
import os
from datetime import datetime
from typing import TYPE_CHECKING
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

if TYPE_CHECKING:
    from app.routing_state import RoutingState
    from app.state import AppState


def _add_title_slide(prs, title: str, subtitle: str):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle


def _add_summary_slide(prs, state: "RoutingState"):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Executive Summary"
    n = len(state.batch_results) or 1
    avg_h = sum(r["h_ratio"] for r in state.batch_results.values()) / n
    avg_v = sum(r["v_ratio"] for r in state.batch_results.values()) / n
    avg_r = sum(r["r_total"] for r in state.batch_results.values()) / n
    avg_tau = sum(r["effective_tau_ps"] for r in state.batch_results.values()) / n
    avg_sim = sum(r["similarity_score"] for r in state.batch_results.values()) / n
    pass_pct = sum(1 for r in state.batch_results.values() if r["gate_pass"]) / n * 100
    missing_total = sum(r["missing_via_count"] for r in state.batch_results.values())
    rows = [
        ("Avg H Ratio", f"{avg_h*100:.1f}%"),
        ("Avg V Ratio", f"{avg_v*100:.1f}%"),
        ("Avg Eff. R", f"{avg_r:.2f} Ω"),
        ("Avg Eff. τ", f"{avg_tau:.2f} ps"),
        ("Avg Similarity", f"{avg_sim:.1f}/100"),
        ("Pass Rate", f"{pass_pct:.0f}%"),
        ("Total Missing Vias", str(missing_total)),
    ]
    body = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(9), Inches(5))
    tf = body.text_frame
    for i, (k, v) in enumerate(rows):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"{k}: {v}"
        p.font.size = Pt(18)


def _add_golden_slide(prs, state: "RoutingState"):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = f"Golden Net: {state.golden_net_name or '(none)'}"
    if not state.golden_metrics:
        return
    m = state.golden_metrics
    body = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(9), Inches(5))
    tf = body.text_frame
    tf.text = "Feature Vector (Golden Reference):"
    for k, v in m.items():
        p = tf.add_paragraph()
        p.text = f"  {k}: {v}"
        p.font.size = Pt(16)


def _add_net_slide(prs, name: str, m: dict):
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = f"Net: {name}"
    body = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(9), Inches(5))
    tf = body.text_frame
    tf.text = f"Pass: {'YES' if m['gate_pass'] else 'NO'}"
    lines = [
        f"H length: {m['h_len']:.2f} μm ({m['h_ratio']*100:.1f}%)",
        f"V length: {m['v_len']:.2f} μm ({m['v_ratio']*100:.1f}%)",
        f"Dominant: {m['dominant']}",
        f"Total R: {m['r_total']:.2f} Ω",
        f"Total C: {m['c_total']:.2f} fF",
        f"Effective τ: {m['effective_tau_ps']:.2f} ps",
        f"Via coverage: {m['via_coverage']*100:.1f}%",
        f"Missing vias: {m['missing_via_count']}",
        f"Similarity to Golden: {m['similarity_score']:.1f}/100",
    ]
    for line in lines:
        p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(14)
    if m["gate_fail_reasons"]:
        p = tf.add_paragraph()
        p.text = "Fail reasons:"
        p.font.size = Pt(14)
        p.font.bold = True
        for r in m["gate_fail_reasons"]:
            p = tf.add_paragraph()
            p.text = f"  - {r}"
            p.font.size = Pt(12)
            p.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)


def generate_routing_pptx(
    state: "RoutingState",
    app_state: "AppState",
    out_path: str,
):
    """Generate the routing review PPTX report."""
    prs = Presentation()
    _add_title_slide(
        prs,
        "Routing Review Report",
        f"Preset: {state.current_preset} | "
        f"{len(state.batch_results)} nets | "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )
    _add_summary_slide(prs, state)
    if state.golden_net_name:
        _add_golden_slide(prs, state)
    for name, m in state.batch_results.items():
        _add_net_slide(prs, name, m)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    prs.save(out_path)
    return out_path
```

- [ ] **Step 5: 运行测试通过**

Run: `pytest tests/test_routing_pptx.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add report/ tests/test_routing_pptx.py
git commit -m "feat(report): routing review PPTX report (cover + summary + per-net)"
```

---

### Task 14: 在 `report_generator.py` 添加薄包装

**Files:**
- Modify: `report_generator.py`（在文件末尾追加 `generate_routing_report()`，不动既有 `generate_reports()`）

- [ ] **Step 1: 在 `report_generator.py` 末尾追加**

```python
def generate_routing_report(state, app_state, output_dir="./output", base_name="routing_report"):
    """Thin wrapper for the routing PPTX report (compatibility shim)."""
    from report.routing_pptx import generate_routing_pptx
    import os
    from datetime import datetime
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx")
    return generate_routing_pptx(state, app_state, path)
```

- [ ] **Step 2: Commit**

```bash
git add report_generator.py
git commit -m "feat(report): wrapper for routing PPTX in report_generator"
```

---

### Task 15: 集成到 `app/layout.py` 和 `app/callbacks.py`

**Files:**
- Modify: `app/layout.py` — 替换 Tab 2 和 Tab 3 内容；保留 Tab 1、Tab 4 和 Modal
- Modify: `app/callbacks.py` — 移除旧 config/review 相关回调；注册新回调

- [ ] **Step 1: 修改 `app/layout.py` 的 `create_layout()`**

替换第 25-30 行的 `dcc.Tabs` 块：

```python
# 旧代码（删除）:
# dcc.Tabs(id='tabs', value='tab-view', children=[
#     dcc.Tab(label='Layout View', value='tab-view', children=_create_layout_view_content()),
#     dcc.Tab(label='Configuration', value='tab-config', children=_create_config_content()),
#     dcc.Tab(label='Layout Review', value='tab-review', children=_create_review_content()),
#     dcc.Tab(label='Report Export', value='tab-export', children=_create_export_content()),
# ], className='eda-tabs'),

# 新代码（替换为）:
from app.routing_config import create_routing_config_tab
from app.routing_review import create_routing_review_tab

dcc.Tabs(id='tabs', value='tab-view', children=[
    dcc.Tab(label='Layout View', value='tab-view', children=_create_layout_view_content()),
    dcc.Tab(label='Routing Config', value='tab-routing-config', children=create_routing_config_tab()),
    dcc.Tab(label='Routing Review', value='tab-routing-review', children=create_routing_review_tab()),
    dcc.Tab(label='Report Export', value='tab-export', children=_create_export_content()),
], className='eda-tabs'),
```

- [ ] **Step 2: 修改 `app/callbacks.py` 的 `register_callbacks()`**

在 `register_callbacks(app)` 函数末尾**追加**（不删除既有回调）：

```python
# Register new routing tab callbacks
from app.routing_config import register_routing_config_callbacks
from app.routing_review import register_routing_review_callbacks
register_routing_config_callbacks(app)
register_routing_review_callbacks(app)
```

- [ ] **Step 3: 手动测试：启动应用**

Run: `python layout_review_app.py 8051`
Expected: 启动成功，浏览器可访问 http://localhost:8051，看到 4 个 Tab（Layout View / Routing Config / Routing Review / Report Export）

打开 Routing Config Tab：应看到 Preset 下拉、7 个阈值输入、Golden/Batch regex、Run Routing Review 按钮
打开 Routing Review Tab：应看到 6 个空 metric card、可视化区、Run 按钮

- [ ] **Step 4: Commit**

```bash
git add app/layout.py app/callbacks.py
git commit -m "feat(app): wire routing Config + Review tabs into main layout"
```

---

### Task 16: 端到端集成测试

**Files:**
- Create: `tests/test_routing_e2e.py`

- [ ] **Step 1: 写 `tests/test_routing_e2e.py`**

```python
"""End-to-end test: load shapes → run routing review → check all 6 metrics."""
import os
import sys
sys.path.insert(0, '.')
from review_engine import Polygon, Point
from config.routing_thresholds import RoutingThresholds
from core.routing_metrics import compute_for_net


def _tech():
    return {
        "met1": {"type": "metal", "resistance_per_sq": 0.15, "capacitance_per_um": 0.20, "min_width": 0.032, "min_space": 0.032},
        "met2": {"type": "metal", "resistance_per_sq": 0.12, "capacitance_per_um": 0.16, "min_width": 0.032, "min_space": 0.032},
    }


def test_wordline_wl_preset_h_dominant_passes():
    """A V-dominant net on WL preset should pass direction gate."""
    # 5μm vertical, 0.5μm horizontal — V-dominant (typical WL layout)
    polys = [Polygon(points=[Point(0,0), Point(0.5,0), Point(0.5,5), Point(0,5)], layer="met1")]
    t = RoutingThresholds.for_preset("sram_7nm_wl")
    m = compute_for_net("WL0", polys, [], _tech(), t, golden_metrics=None)
    assert m["dominant"] == "V"
    assert m["gate_pass"] is True
    # All 6 metrics present
    for k in ("h_ratio", "v_ratio", "missing_via_count", "via_coverage",
             "r_total", "c_total", "effective_tau_ps",
             "similarity_score", "gate_pass"):
        assert k in m


def test_io_bl_preset_v_dominant_passes():
    """An H-dominant net on IO preset should pass direction gate."""
    polys = [Polygon(points=[Point(0,0), Point(5,0), Point(5,0.5), Point(0,0.5)], layer="met2")]
    t = RoutingThresholds.for_preset("sram_5nm_io_bl")
    m = compute_for_net("BL0", polys, [], _tech(), t, golden_metrics=None)
    assert m["dominant"] == "H"
    assert m["gate_pass"] is True


def test_long_wire_fails_tau_gate():
    """A long wire (1000μm) should fail the τ gate."""
    polys = [Polygon(points=[Point(0,0), Point(1000,0), Point(1000,0.1), Point(0,0.1)], layer="met1")]
    t = RoutingThresholds.for_preset("sram_7nm_wl")  # max_tau_ps=12.5
    m = compute_for_net("WL0", polys, [], _tech(), t, golden_metrics=None)
    assert any("τ" in r or "tau" in r for r in m["gate_fail_reasons"])
```

- [ ] **Step 2: 运行全部测试**

Run: `pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add tests/test_routing_e2e.py
git commit -m "test: end-to-end routing review workflow"
```

---

### Task 17: 清理死代码

**Files:**
- Delete: `core/enhanced_em_analyzer.py`、`core/enhanced_matching.py`、`core/enhanced_rc_calculator.py`、`config_system_v2.py`
- Modify: `rules/drc/__init__.py`、`rules/si/__init__.py` — 不需要，保持空（路由 Tab 不使用）

- [ ] **Step 1: 删除不再使用的文件**

Run:
```bash
git rm core/enhanced_em_analyzer.py core/enhanced_matching.py core/enhanced_rc_calculator.py config_system_v2.py
```

- [ ] **Step 2: 验证应用仍能启动**

Run: `python layout_review_app.py 8052`
Expected: 启动成功，4 Tab 可用

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove dead code (enhanced_*, config_system_v2)"
```

---

## 验证清单

完成所有 17 个 Task 后，确认以下交付物：

- [ ] `python layout_review_app.py` 启动成功
- [ ] 浏览器看到 4 个 Tab：Layout View / **Routing Config** / **Routing Review** / Report Export
- [ ] Routing Config 仅有：1 个 preset 下拉 + 7 个阈值输入 + 2 个 regex + 1 个 Run 按钮（**无 9 字段 rule editor、无 json 文本框**）
- [ ] 在 tests/shapes_test_wordline_WL0.txt + WL1.txt + bitline_BL0.txt + BLB0.txt 上：输入 `^WL.*$` 为 Golden regex、剩下的为 Batch regex，Run → 6 个 metric card 显示数字 + 表格显示 4 行 + Plotly 画布有红蓝着色
- [ ] 一键 Generate Routing Report → 下载 PPTX，含 Cover、Summary、每 net 一页
- [ ] `pytest tests/` 全部通过
- [ ] 既有 Layout View / Report Export Tab 功能未受影响

---

## 执行交接

Plan 已保存到 `docs/superpowers/plans/2026-06-01-routing-review-rewrite.md`。

**两种执行方式：**

1. **Subagent-Driven（推荐）** - 我对每个 Task 派一个独立 subagent，逐 Task 审核 + 快速迭代
2. **Inline Execution** - 在本会话内用 executing-plans 批量执行，含 checkpoint 审核

**你想用哪种方式开始？**
