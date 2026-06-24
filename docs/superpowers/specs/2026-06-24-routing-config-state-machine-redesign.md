# 2026-06-24 Routing Config State Machine Redesign — Design Spec

## 0. 背景与目标

在 2026-06-24 完成 `routing-config-review-fix` 改造（`f53c952` 等 10 个 commit）后，用户实测发现：

1. **点击 Editable 后 routing thresholds 依然无法编辑** — UI 上 input 仍呈 disabled 状态
2. **点击 Apply Thresholds 后值仍呈红色** — 即便值有效（h+v=1.15 ≥ 1.0、c_ff=500.0 ∈ [0.1, 100000]、tau=12.5 ∈ [0.01, 1000]）

**根因**：`app/routing_config.py` 当前 4 个 callback（`_rehydrate_on_tab` / `_handle_routing_preset_or_thresh` / `_apply_thresholds` / `_switch_mode`）**共享同一组 21 个 Output** 并全部使用 `allow_duplicate=True`。Dash 在多个 callback 写同一组 Output 时，**最后一个执行的 callback 胜出**，行为不可预测：
- 用户点 Editable → `_switch_mode` 跑出 `disabled=[False]*7`，但 `_handle_routing_preset_or_thresh` 也可能因为 thresh values re-emit 触发 → 覆盖回 `disabled=[True]*7`
- 用户点 Apply → `_apply_thresholds` 跑出 success 状态，但 `_handle_routing_preset_or_thresh` 又被 7 thresh values 触发 → 覆盖 success 状态

**本 spec 目标**：
- 把 4 个重叠 callback 合并为 **1 个 state-driven callback**，彻底消除 `allow_duplicate=True`
- 状态机集中到一个文件，**routing_state 是唯一真源**
- Apply / Editable / Preset / Tab 切换 / 键盘敲击 五类操作，**全部可预测**且**有单测覆盖**

## 1. 范围

| 范围项 | 包含 |
|---|---|
| 单 callback 状态机 | 重写 `register_routing_config_callbacks`：合并 4 个 callback 为 1 个；保留 layout / helpers / state API |
| 测试重写 | `tests/test_routing_config_layout.py` 大幅重写：移除 4-callback 互操作测试，加状态机单元测试 |
| 测试保留 | `tests/test_apply_persistence.py` / `test_tab_rehydrate.py` / `test_summarize_net.py` / `test_rc_consistency.py` 等不动 |
| 不动 | `routing_state.py` API；layout 函数；preset YAML；i18n 字符串；其它 tab |

## 2. 架构

### 2.1 状态机边界

```
            ┌──────────────────────────────────────────────┐
            │  routing_state（routing_state.py）            │
            │  - current_preset: str                       │
            │  - thresholds: RoutingThresholds              │
            │  - custom_thresholds: RoutingThresholds|None │
            │  - is_frozen: bool                            │
            │  - set_frozen_mode(frozen)  # 不清 custom    │
            │  - set_custom(t)             # 切到 editable  │
            │  - get_thresholds() →  preset|custom         │
            │  - get_threshold_source() → 三态英文          │
            └────────────────▲─────────────────────────────┘
                             │
                             │ (mutate)
                             │
   User Input               │
   ─────────                │
   routing-preset.value   ───┤
   mode-frozen.n_clicks   ───┤
   mode-editable.n_clicks ───┤
   btn-apply.n_clicks     ───┤  ┌────────────────────────────────────────┐
   thresh-*.value         ───┤  │  ONE callback: _routing_config_ui()  │
   tabs.value             ───┘  │  Inputs: 上述 6 类                    │
                                │  State: 7 thresh values                │
                                │                                        │
                                │  1. ctx.triggered → identify action    │
                                │  2. mutate routing_state               │
                                │  3. _render_state() → 21 Outputs       │
                                └────────────────────────────────────────┘
                                                 │
                                                 ▼
                                          21 个 UI 属性
                                          （无 allow_duplicate）
```

### 2.2 Output 列表（与之前完全一致）

```python
OUTPUTS = [
    Output("mode-frozen", "className"),
    Output("mode-editable", "className"),
    Output("routing-preset-status", "children"),
    Output("routing-config-status", "children"),
    Output("thresh-unsaved-badge", "children"),
    Output("thresh-apply-status", "children"),
    Output("routing-preset", "value"),
] + [Output(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS]
+  [Output(f"thresh-{name}", "disabled") for name, *_ in THRESHOLD_FIELDS]
```

**不变量**：整个项目只有**这一处**写这 21 个 Output。0 个 `allow_duplicate`。

### 2.3 内部 helper 拆分

为避免单 callback 过大，拆成 3 个 pure helper + 1 个 dispatcher：

```python
def _dispatch_action(trigger_id, thresh_values) -> None:
    """根据 ctx.triggered 决定 mutate 哪个 state 字段。pure side effect on routing_state。"""

def _render_state(thresh_input_values) -> tuple[...]:
    """把 routing_state 投影到 21 个 UI 属性。pure function。"""

def _validate_apply(thresh_values) -> tuple[RoutingThresholds | None, str | None]:
    """验证 7 个 thresh 值，返回 (valid_thresholds | None, error_msg | None)。"""
```

callback 本身只做：`dispatch + render`，约 40 行。

## 3. 数据流（每类用户操作）

### 3.1 Preset 切换（`routing-preset.value` 变化）

```python
if trigger == "routing-preset.value":
    new_preset = preset_value
    if routing_state.is_frozen:
        # 直接 load preset，丢弃 custom（spec §3.2.1 frozen 分支）
        routing_state.current_preset = new_preset
        routing_state.thresholds = RoutingThresholds.for_preset(new_preset)
        routing_state.custom_thresholds = None
    else:
        # editable 模式阻止 preset 切换（spec §3.2.1 editable 分支）
        # 不 mutate state，_render_state 会通过 preset_value == state.current_preset 的回弹
        # 把 dropdown 拉回 state 当前 preset
        pass
```

UX 表现：
- frozen 模式：dropdown 改变 → 立即重渲染 7 thresh inputs 为新 preset 值 + cleared unsaved badge
- editable 模式：dropdown 改变 → routing-preset-status 显示 "Edit Mode: Preset switch Blocked. Click Apply or switch to Locked first."（红色），dropdown 自动回弹到 state.current_preset

### 3.2 模式切换（`mode-frozen.n_clicks` / `mode-editable.n_clicks`）

```python
elif trigger == "mode-frozen.n_clicks":
    routing_state.set_frozen_mode(True)
    # custom_thresholds 保留不丢（草稿区约定）

elif trigger == "mode-editable.n_clicks":
    routing_state.set_frozen_mode(False)
    if routing_state.custom_thresholds is None:
        routing_state.custom_thresholds = RoutingThresholds.from_dict(
            routing_state.get_thresholds().to_dict()
        )
```

UX 表现：
- 点 Locked：disabled=[True]*7，inputs 显示 state.thresholds（preset）值
- 点 Editable：disabled=[False]*7，inputs 显示 custom_thresholds（草稿）值，若无草稿则显示 preset 值

### 3.3 Apply（`btn-apply-thresholds.n_clicks`）

```python
elif trigger == "btn-apply-thresholds.n_clicks":
    valid, err = _validate_apply(thresh_values)
    if valid is None:
        # 失败：返回 error 状态，state 不变
        # 仍需 render_state 来 emit 一致的 values + disabled
        apply_status = html.Span(f"✗ Apply Failed: {err}", style={"color": "#C0392B"})
    else:
        # 成功：写入 state
        routing_state.set_custom(valid)
        apply_status = html.Span("✓ Thresholds applied.", style={"color": "#27AE60"})
    # 注：set_custom 内部会 set_frozen_mode(False) + 写 custom_thresholds
```

UX 表现：
- 合法值：apply-status 绿色 ✓；routing-config-status 显示 source；unsaved badge 隐藏
- 非法值：apply-status 红色 ✗ + 错误信息；routing-config-status 同样红字；state 不变

### 3.4 键盘敲击（`thresh-*.value` 变化）

```python
elif trigger.startswith("thresh-") and trigger.endswith(".value"):
    # 不 mutate state
    # _render_state 会基于 thresh_input_values 与 state.get_thresholds() 对比：
    #   - 有差异 → 显示 unsaved badge
    #   - 无差异 → 隐藏 unsaved badge
    pass
```

UX 表现：
- 用户敲值 → unsaved badge（橙色 ● Unsaved Changes）显示 + apply-status 橙色 "Thresholds modified — click Apply to save."
- 用户敲回原值 → unsaved badge 消失

### 3.5 切回 tab（`tabs.value == "tab-routing-config"`）

```python
elif trigger == "tabs.value":
    if active_tab == "tab-routing-config":
        # 完整 rehydrate：清 transient badges，反映 state
        pass
    else:
        raise PreventUpdate
```

UX 表现：切回 routing-config tab → UI 重新反映 state 真值。

### 3.6 初始渲染

`prevent_initial_call=False`：app 启动时 callback 跑一次，把 state 推到 UI。

## 4. _render_state 输出规则

```python
def _render_state(thresh_input_values: list) -> tuple[...]:
    """Project routing_state → 21 UI properties.

    thresh_input_values: 当前 7 个 input 的实际值（用于判断 unsaved 状态）
    """
    thr = routing_state.get_thresholds()
    vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
    frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(frozen)
    dis_list = _disabled_list(frozen, len(THRESHOLD_FIELDS))

    # detect unsaved changes
    has_unsaved = thresh_input_values != vals

    # preset-status banner
    source = routing_state.get_threshold_source()
    preset_status = html.Span(source, style={"color": "#888"})

    # config-status
    config_status = ""  # 默认无内容

    # unsaved badge
    if has_unsaved:
        unsaved_badge = html.Span("● Unsaved Changes",
                                  style={"fontSize": "10px", "color": "#E67E22",
                                         "fontWeight": "600"})
    else:
        unsaved_badge = html.Span("", style={"display": "none"})

    # apply-status
    if has_unsaved:
        apply_status = html.Span("Thresholds modified — click Apply to save.",
                                 style={"fontSize": "11px", "color": "#E67E22"})
    else:
        apply_status = ""

    return (f_cls, e_cls, preset_status, config_status, unsaved_badge,
            apply_status, routing_state.current_preset, *vals, *dis_list)
```

## 5. 行为约束（与之前 spec 一致 + 强化）

| 场景 | 行为 |
|---|---|
| frozen → Editable → Locked → Editable | custom_thresholds 保留；第二次 Editable 时 inputs 显示草稿值 |
| frozen → Apply | state.thresholds 写入新值；切到 editable（custom_thresholds = applied） |
| editable → Preset 改变 | 阻止 + 红字提示；dropdown 自动回弹 |
| editable → Apply 合法值 | state.custom_thresholds 写入 + 清 unsaved badge |
| editable → Apply 非法值 | 错误信息，state 不变，unsaved badge 保留 |
| editable → 键盘敲合法值 | unsaved badge 显示 |
| editable → 键盘敲回原值 | unsaved badge 消失 |
| 任意时刻切走 tab 再回来 | 完整 rehydrate，UI = state |
| 初始渲染 | callback 跑一次，UI = state |

## 6. 测试

### 6.1 重写 `tests/test_routing_config_layout.py`

旧测试基于 4-callback 互操作，需重写为状态机单测：

| Test | 覆盖 |
|---|---|
| `test_initial_render_shows_frozen_with_preset` | app 启动后 UI = frozen + preset + 7 inputs disabled |
| `test_click_editable_enables_inputs` | mode-editable.n_clicks 触发后 disabled=[False]*7 |
| `test_click_editable_copies_preset_to_custom` | 编辑态首次切换时 custom_thresholds = state.thresholds |
| `test_click_frozen_preserves_custom` | editable→frozen→editable 时 custom 草稿保留 |
| `test_apply_valid_writes_state_and_clears_badge` | Apply 合法值 → state.custom_thresholds 更新 + unsaved badge 隐藏 |
| `test_apply_invalid_shows_error_and_keeps_state` | Apply 非法值（h+v<1）→ state 不变 + 红字错误 |
| `test_keypress_shows_unsaved_badge` | thresh-* 改动 → unsaved badge 显示 |
| `test_keypress_revert_clears_unsaved_badge` | 改回原值 → badge 消失 |
| `test_preset_change_in_frozen_loads_new_preset` | frozen 模式改 preset → 7 inputs 显示新值 + custom 清空 |
| `test_preset_change_in_editable_blocked` | editable 模式改 preset → routing_preset_status 红字 + dropdown 回弹 |
| `test_tab_switch_rehydrates_state` | 切走再切回 → UI = state |

### 6.2 保留测试

- `tests/test_apply_persistence.py`：Apply success/fail 持久化
- `tests/test_tab_rehydrate.py`：tab 切回 rehydrate
- `tests/test_preset_loader_schema.py`：preset loader
- `tests/test_summarize_net.py`、`test_rc_consistency.py`：RC 一致性

### 6.3 移除/废弃

旧的 `_handle_routing_preset_or_thresh` / `_switch_mode` 等 4-callback 互操作测试如果存在则删除。

## 7. 风险与回退

| 风险 | 缓解 |
|---|---|
| 单 callback 200 行 | 拆成 3 个 pure helper，callback 只做 dispatch+render |
| 现有 27 个 routing tests 失败 | 重写测试（spec §6.1） |
| 行为漂移 | 每个旧行为都有 spec §5 表行对应测试 |
| `routing_state` API 不变 | 仅重写 UI 投影层，回退 = revert 单个 commit |

## 8. 验收

1. `pytest tests/` 全绿（含新重写的 routing_config_layout 测试 + 既有 162 个测试）
2. 启动 dash app，手动走 5 步流程：
   - 打开 Routing Config tab → 7 inputs 全部 disabled
   - 点 Editable → inputs 立即可编辑（disabled=False）
   - 改 max_h_ratio → unsaved badge 出现
   - 点 Apply → state 写入 + badge 消失
   - 切到 Layout View 再切回 → inputs 显示 Apply 后的值，仍可编辑
3. Editable 模式改 preset dropdown → 红字阻止 + dropdown 回弹
4. Locked 模式改 preset dropdown → 立即切到新 preset
5. Apply 非法值（如 h=0.1, v=0.1）→ 红字错误，state 不变

## 9. 不做（Out of Scope）

- `routing_state` API 修改
- preset YAML / loader 改动
- layout 函数改动
- i18n（spec §4 锁定术语已稳定）
- 其它 tab（routing_review / layout_view / overview）
