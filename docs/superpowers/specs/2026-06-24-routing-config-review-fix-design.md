# 2026-06-24 Routing Config & Review 端到端一致性修复 — Design Spec

## 0. 背景与目标

在 2026-06-23 完成 `routing-tab-consistency` 改造后，仍存在以下用户可观察的问题：

1. **RC/τ 在两 tab 不一致**：Layout View 右侧 Properties 面板使用 `review_engine.calculate_net_rc()` 的朴素 `R·C` 算 τ；Routing Review 卡片/表格使用 `core/routing_metrics.compute_for_net()` 的 Elmore delay。同一根 net 在两处看到的 R/C/τ 数值与单位含义不同。
2. **Routing Config 持久化失败**：
   - Apply Thresholds 之后状态写入 `routing_state.custom_thresholds`，但 `dcc.Tabs` 切回 tab 时不会自动 fire callback，UI 不会重新读取 state，显示旧值。
   - Preset YAML 字段名/类型与 `RoutingThresholds` dataclass 不严格一致，导致导入后"非法"红字出现。
3. **UI 中英文混杂**：路由相关模块与 review_engine docstring 残留中文，与整体英文风格不符。

**本 spec 目标**：
- 单一 RC 算源（Elmore τ），Layout View 与 Routing Review 字段一致；
- Routing Config 的 Apply / Locked-Editable / Preset 三类操作对 state 的修改在 UI 上**必然可见**（包括切 tab 回来后）；
- 全 UI 英文化，术语统一。

## 1. 范围

| 范围项 | 包含 |
|---|---|
| 单一 RC 来源 | 新增 `core/rc_summary.py`；改 `app/callbacks.py` 中 properties panel callback；Layout View 新增 Elmore τ 字段 |
| Routing Config 持久化 | 修复 Apply 回调；新增 tab-switch rehydrate 回调；preset loader 改 schema-aware fallback；3 个 YAML 字段对齐 |
| UI i18n | `app/routing_config.py` / `app/routing_review.py` / `app/callbacks.py` / `app/layout.py` / `app/state.py` / `review_engine.py` 全部中→英 |
| 不动 | DRC 引擎、SRAM 特定规则、报告生成、review_engine 的 DRC/SRAM 规则（仅解耦 RC 计算路径） |

## 2. 架构

### 2.1 RC 计算新边界

```
            ┌───────────────────────────┐
            │  core/routing_metrics.py  │  现有 π-model + Elmore
            │  compute_for_net(...)     │  （不修改，仅复用）
            └────────────▲──────────────┘
                         │
            ┌────────────┴──────────────┐
            │  core/rc_summary.py        │  新文件：薄包装层
            │  summarize_net(...)        │  统一字段名 + 单位元信息
            └────────────▲──────────────┘
                         │
        ┌────────────────┼─────────────────┐
        │                                  │
┌───────┴────────┐                ┌────────┴────────┐
│ Layout View    │                │ Routing Review  │
│ Properties     │                │ Cards / Table   │
│ (右侧面板)     │                │                  │
└────────────────┘                └─────────────────┘
```

**关键不变量**：
- 所有读 R/C/τ 的代码路径都通过 `summarize_net()`，禁止直接调 `engine.calculate_net_rc()` 用于 properties 显示。
- `summarize_net()` 返回字段固定为：
  ```python
  {
    "net_name": str,
    "r_total_ohm": float,        # 总电阻（Ω），π-model 累加，含 via
    "c_total_ff": float,         # 总电容（fF），π-model 累加，含 via
    "tau_elmore_ps": float,      # Elmore delay（ps）
    "tau_naive_ps": float,       # 朴素 R·C（ps），保留以便对照
    "h_ratio": float,            # 0..1
    "v_ratio": float,            # 0..1
    "missing_via_count": int,
    "via_coverage": float,       # 0..1
    "similarity_score": float,   # 0..100，未跑 golden 时为 100
    "dominant": "H" | "V" | "balanced",
    "status": "ok" | "no_data",
  }
  ```

### 2.2 Routing Config state 改造

```
User Input (UI)              State (权威)              UI Render
─────────────────         ────────────────         ──────────────
[thresh-max_h_ratio] ──┐
[thresh-max_v_ratio]  │ │
[thresh-max_r_ohm]    │ │
[thresh-max_c_ff]     │ ├──► _handle_inputs()      ──► 局部 dirty badge
[thresh-max_tau_ps]   │ │     (callback)              + red Invalid 标记
[thresh-min_via_cov]  │ │                            （不写 state）
[thresh-min_sim]      │ │
                      │ │
[apply-thresholds]────┘ │
                        ▼
                 routing_state.set_custom()      ──► rehydrate (Output 列表)
                 routing_state.set_frozen_mode(False)
                        ▲
                        │
[routing-preset]─────────┘  preset change
                              │
                              ▼
                       routing_state.load_preset() ──► rehydrate

[mode-frozen]   ──► routing_state.set_frozen_mode(True)  ──► rehydrate
[mode-editable] ──► routing_state.set_frozen_mode(False) ──► rehydrate

[tabs] (value change) ──► _rehydrate_on_tab() ──► rehydrate（仅 value == 'tab-routing-config' 时触发）
```

**关键不变量**：
- `routing_state` 是**唯一权威**，UI 永远从 state 推。
- 任何对 state 的修改（set_frozen_mode / set_custom / load_preset）必须经由 rehydrate 写到 UI。
- `dcc.Tabs` 切回 `tab-routing-config` 时显式触发 rehydrate（`Input('tabs', 'value')`）。
- 7 个 thresh inputs 的 `value` 与 `disabled` 都进入 rehydrate 的 Output 列表，确保切 tab 不丢值。

### 2.3 Preset Loader 改造

`config/preset_loader.py` 改造为 schema-aware：
1. 用 `dataclasses.fields(RoutingThresholds)` 生成 schema。
2. 对 YAML 中未出现的字段，从 `RoutingThresholds` 默认值 fallback。
3. 字段名拼写错误 / 类型不匹配时抛 `PresetValidationError`（继承 `ValueError`），UI 显示红字提示。
4. 校验：`__post_init__` 已有的 h+v≥1.0、tau>0、r>0、c>0、coverage∈[0,1]、similarity∈[0,100] 保留。

YAML 字段对齐（仅做 sanity 改写，不改语义值）：
- `via_coverage` → `min_via_coverage`
- `similarity` → `min_similarity`
- `h_ratio` / `v_ratio` / `r_total` / `c_total` / `tau` / `sim` 旧简称保留为 alias，loader 内部映射到完整名。

## 3. 数据流

### 3.1 Layout View 选 net → Properties 面板

1. 用户点击 canvas 上某个 net。
2. Callback `update_properties_panel(n_clicks, net_id, ...)` 触发。
3. Callback 调 `summarize_net(net_id, polygons, vias, tech, routing_state.get_thresholds())`。
4. 渲染字段：Net Name, Polygons, Vias, R (Ω), C (fF), τ Elmore (ps), τ Naive (ps), H/V Ratio, Missing Vias, Via Coverage, Similarity。
5. **新增** "τ Elmore" 与 Routing Review 完全一致；"τ Naive" 单独列以便与历史数值对照。

### 3.2 Routing Config tab 操作

#### 3.2.1 Preset 加载
```
[routing-preset value="sram_5nm_io_bl"]
  └─► callback: load_preset(preset_name)
        ├─► if editable: raise PreventUpdate（不允许在 editable 改 preset）
        ├─► routing_state.load_preset(preset_name)  # 内部验证 + 写 state
        └─► rehydrate → UI 更新
```

#### 3.2.2 阈值编辑（不点 Apply）
```
[thresh-* n_blur/change] → 7 个 values
  └─► callback: _handle_thresh_change(*values, which)
        ├─► 与 current state 对比
        ├─► 若无变化：清 unsaved badge + 红字
        └─► 若有变化：显示 unsaved badge，但**不写 state**
```

#### 3.2.3 Apply
```
[apply-thresholds n_clicks] + State(thresh-*, values)
  └─► callback: _apply_thresholds(*values)
        ├─► RoutingThresholds.from_dict(...) 触发 __post_init__ 校验
        ├─► 若 invalid：返回红字 Invalid，不写 state
        └─► 若 valid：
              ├─► routing_state.set_custom(thresholds)
              ├─► routing_state.set_frozen_mode(False)
              └─► rehydrate
```

#### 3.2.4 模式切换
```
[mode-frozen n_clicks]   → routing_state.set_frozen_mode(True)  → rehydrate
[mode-editable n_clicks] → routing_state.set_frozen_mode(False) → rehydrate
```

#### 3.2.5 Tab 切回
```
[tabs value="tab-routing-config"]
  └─► callback: _rehydrate_on_tab
        └─► _compute_rehydrate_outputs()  # 同步 7 个 value + 7 个 disabled + 模式 class + preset value
```

### 3.3 Routing Review 跑 review

1. 用户切到 Routing Review tab，点 Run Review。
2. Callback 走 `routing_state.get_thresholds()`（Apply 后的 custom），不再读 preset YAML。
3. 卡片 / 表格显示的 R/C/τ 与 Layout View Properties 面板同源（`summarize_net`）。

## 4. UI i18n 术语表

锁定术语，全项目统一：

| 中文 | 英文 |
|---|---|
| 冻结 | Locked |
| 可编辑 | Editable |
| 编辑模式 | Edit Mode |
| 已阻止 | Blocked |
| 未保存 | Unsaved Changes |
| 已应用 | Applied |
| 应用 | Apply |
| 加载预设中 | Loading Preset… |
| 已加载预设 | Preset Loaded |
| 重新载入 | Reload |
| 恢复默认 | Restore Defaults |
| 校验失败 | Validation Failed |
| 高亮 | Highlight |
| 当前阈值来源 | Active Threshold Source |
| 请先在 Layout View 中运行 Full Review | Run Full Review from the Layout View tab first |
| 阈值 | Threshold |
| 预设 | Preset |
| 通过/失败 | Pass / Fail |
| 严重 | Critical |
| 加载中 | Loading… |
| 错误 | Error |
| 成功 | Success |
| 警告 | Warning |
| 有效 | Valid |
| 无效 | Invalid |
| 无变化 | No Changes |
| 已保存 | Saved |
| 默认 | Default |
| 自定义 | Custom |
| 单元 | Cell |
| 备注 | Note |
| 说明 | Description |
| 帮助 | Help |
| 详情 | Details |
| 摘要 | Summary |
| 报告 | Report |
| 导出 | Export |
| 导入 | Import |
| 取消 | Cancel |
| 确认 | Confirm |
| 关闭 | Close |
| 是 | Yes |
| 否 | No |
| 全部 | All |
| 部分 | Partial |
| 无 | None |
| 提示 | Hint |
| 示例 | Example |
| 数据 | Data |
| 状态 | Status |
| 操作 | Action |
| 设置 | Settings |
| 配置 | Configuration |
| 参数 | Parameter |
| 选项 | Options |
| 结果 | Result |
| 完成 | Completed |
| 失败 | Failed |
| 通过 | Pass |
| 重新 | Retry |
| 跳过 | Skip |

**作用域**：
- 替换所有 `app/*.py`、`review_engine.py`、`core/data_parsing.py` 等可见字符串
- docstring 中的中文保留（开发文档），但首行保留英文 summary

## 5. 错误处理

| 场景 | UI 表现 | state 影响 |
|---|---|---|
| Preset YAML 缺字段 | schema-aware fallback 静默补全；不显示红字 | 不变 |
| Preset YAML 字段名错 | `PresetValidationError` → UI 红字 "Invalid Preset: <field>" | 不变 |
| Preset YAML 校验失败（h+v<1 等） | UI 红字 "Invalid: <reason>" | 不变 |
| Apply 时输入非法 | UI 红字 "Validation Failed: <field>" | 不变 |
| Apply 时输入合法 | UI 绿字 "Applied" | custom_thresholds 写入 |
| 切 tab 回来 | UI 重新从 state 推 | 不变 |
| Locked 模式试图编辑 | inputs `disabled=True` | custom_thresholds **保留**（不丢草稿） |
| Editable 模式试图切 preset | 阻止 + 提示 "Preset change blocked in Edit Mode" | 不变 |
| Routing Review 用旧 custom | review 路径走 `routing_state.get_thresholds()`，永远最新 | 走 fresh read |

## 6. 测试

### 6.1 新增

| 文件 | 覆盖 |
|---|---|
| `tests/test_rc_consistency.py` | 同一 net 在 Layout View 与 Routing Review 看到 R/C/τ 数值一致（容差 1e-9） |
| `tests/test_summarize_net.py` | `summarize_net()` 字段完整性、单位正确性 |
| `tests/test_preset_loader_schema.py` | schema fallback、字段名错误抛错、h+v 校验 |
| `tests/test_apply_persistence.py` | Apply 后切 tab 回来值保留；Apply 失败不动 state；Locked → Editable 切换 rehydrate |
| `tests/test_tab_rehydrate.py` | tab 切到 routing-config 触发 rehydrate（mock callback_context） |

### 6.2 更新

| 文件 | 改动 |
|---|---|
| `tests/test_routing_config_layout.py` | 把"已阻止 preset 切换" 等中文字符串断言改为英文；新增 Apply success / Apply fail 两条 |
| `tests/test_routing_e2e.py` | 不变（已使用英文 `routing-preset` 等 id） |

### 6.3 保留

`tests/test_full_review_callback.py`、`tests/test_tau_units.py` 不动。

## 7. 风险与回退

| 风险 | 缓解 |
|---|---|
| Layout View 改用 Elmore τ 后历史数值差异显著 | Properties 面板同时显示 τ Elmore 与 τ Naive，迁移期可对照 |
| Apply 回调重写破坏现有 test_routing_config_layout | 先跑测试；契约（Output 索引、disabled list 长度）保持 |
| 大量中→英替换误伤字符串字面量 | 一次性脚本 + 人工 review；测试字符串同步改 |
| preset schema 改写后 YAML 错位 | schema-aware fallback + 显式错误信息；3 个 YAML 同步校正 |

回退策略：每个 commit 自包含、可独立 revert；最终一次性 squash。

## 8. 验收

1. `pytest tests/` 全绿。
2. 启动 dash app，同一根 net 在 Layout View Properties 与 Routing Review 看到的 R/C/τ Elmore 完全一致。
3. Routing Config tab：
   - 切换 preset → 立即反映在 7 个 input 上（disabled 取决于 mode）。
   - 在 Editable 改 preset dropdown → 被阻止并提示。
   - Apply 有效值 → 切到别的 tab 再切回来 → 值保留。
   - Apply 无效值 → 红字提示，state 不动。
4. 路由相关模块无中文字符串（grep 验证）。
5. Preset YAML 故意删一个字段 → loader 自动 fallback 不报错。

## 9. 不做（Out of Scope）

- 整体页面改版、theme 调整；
- review_engine.py 内部 DRC 逻辑重写；
- 新增 routing 指标（如 EM/IR）；
- 国际化框架（i18next 等）引入；本 spec 仅做静态字符串替换。
