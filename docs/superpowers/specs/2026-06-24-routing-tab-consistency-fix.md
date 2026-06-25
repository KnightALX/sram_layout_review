# Routing Tab Consistency & Thresholds Fix Design

**Date**: 2026-06-24  
**Based on**: Brainstorming session with user confirmations (RC: A + 准确; Thresholds: 准确; UI: 确认)

## Confirmed User Requirements

1. **RC Values**:
   - Layout View Properties accurate (符合诉求).
   - Routing Review shows different resistance, capacitance, tau_rc (mainly tau range differs; R/C roughly same).
   - Check units/logic inconsistency.
   - Fix: Ensure default path matches legacy Properties exactly.

2. **Routing Config Thresholds**:
   - Confirm presets accurate, refresh templates.
   - No red (invalid) values after import.
   - Fix "apply无效" after switching tabs back to Config.
   - Add explicit freeze (Locked) / editable mode:
     - Locked (default): inputs disabled, strictly follow preset. Switch preset = immediate effect.
     - Editable: modify on top of preset; must Apply to commit.
   - Ensure Apply results take effect in Routing Review (cards, table, gates, source).

3. **UI Style**:
   - Consistent style across all tabs (Layout View, Routing Config, Routing Review, Report Export).
   - Prohibit Chinese text.
   - Convert any Chinese buttons/labels to professional English.
   - Overall consistent styling (buttons, colors, spacing, error states).

## High-Level Architecture

- Two pipelines share `app_state.nets_data` but use separate states (`app_state` for legacy, `routing_state` for routing).
- **RC Path**: Routing Review must default to legacy path (tech_layers + calculate_net_rc + lumped via `ohm_ff_to_ps`) to match Properties. Only use `RCModelConfig` if user explicitly sets custom model (via `custom_rc_model`).
- **State**: `RoutingState` owns `is_frozen`, `get_thresholds()` (authoritative), `get_threshold_source()`.
- **Config**: Single callback (`_routing_config_ui`) handles preset/mode/thresh/apply + tab rehydrate. Explicit Locked/Editable toggle.
- **Review**: Always reads `routing_state.get_thresholds()` + shows source banner + value/threshold. Cards/table include Eff. C and C column.
- **UI**: 100% professional English; unified theme (buttons, cards, banners) across tabs. No Chinese.

## Design Sections (All Confirmed)

### Section 1: RC Consistency (User: A + 准确)
- In `_run_routing_review`: `rc_model_to_use = routing_state.custom_rc_model if routing_state.custom_rc_model else None`.
- In `compute_net_metrics_with_tau` (default/else): use `ohm_ff_to_ps` on totals from `calculate_net_rc` (matches legacy Properties).
- Add/ensure test: `test_rc_values_match_between_properties_and_routing_review` (same net via upload path; assert R/C/tau equality using engine.net_rc_data vs review metrics).
- Visual: `docs/visuals/rc_comparison.html`

**Rationale**: Eliminates model override or dominant-layer recompute for default case. Tau now identical for mono/multi-layer nets.

### Section 2: Routing Config Thresholds & Modes (User: 准确)
- **Presets**: All BUILTIN + YAML must pass `validate()` (h+v ≥ 1.0, values >0, sim in [0,100]). Call `validate()` on load/switch in `for_preset`/`load_preset_yaml`.
- **No red on valid**: Initial load, rehydrate, preset switch use direct `get_thresholds()` values (no tentative validate). Red + revert only on "Apply Thresholds" path.
- **Freeze/Editable** (new explicit mode):
  - Toggle buttons next to Preset dropdown: "Locked" (default) / "Editable".
  - **Locked**: All thresh inputs disabled; strictly follow preset. Switch preset = immediate load + state update.
  - **Editable**: Inputs enabled; modify on template; show "unsaved" badge; must click Apply to commit to `custom_thresholds` + set `is_frozen=False`.
  - On Editable + preset switch with unsaved: warn + prevent (simple status/revert).
- **Apply & Tab Persistence**:
  - Apply: commit (custom or preset), clear unsaved badge, update `last_status`, set mode.
  - Tab switch to Config: dedicated rehydrate outputs current values + disabled flags + mode button classes from state (21-tuple).
  - Review always uses `get_thresholds()` + source banner ("Active Threshold Source: Locked preset: xxx" or "Custom (based on xxx)").
- Visuals: `docs/visuals/current_config_ui_mock.html`, `docs/visuals/11-frozen-editable-modes.html`

**Rationale**: Directly solves "apply无效", red on valid, confusing presets. Mode makes UX clear and controllable.

### Section 3: UI Style & Consistency (User: 确认)
- **No Chinese**: Full audit of `layout.py`, `routing_config.py`, `routing_review.py`, `callbacks.py`. Convert all buttons/labels/status/banners/errors to professional English.
  - Buttons: "Locked", "Editable", "Apply Thresholds", "Generate Routing Report (PPTX)", "Dismiss".
  - Banners: "Active Threshold Source: Locked preset: sram_7nm_wl".
  - Errors/Status: "Error: ...", "Thresholds modified — click Apply to save.".
- **Consistent Styling**:
  - Same button classes/styles (btn-primary, btn-secondary, btn-sm) across tabs.
  - Uniform cards, inputs, error colors (theme vars), spacing, flex/grid.
  - Source banners + cards use "value / threshold" format consistently.
  - EDA/professional utilitarian look (no drift).
- Visuals: `docs/visuals/12-ui-english-consistency.html`, `docs/visuals/13-final-ui-mock.html`, `docs/visuals/14-all-sections-summary.html`

**Rationale**: Meets "UI风格保持一致，禁止出现中文" exactly. Professional and unified.

## Risks & Mitigations
- Tab rehydrate must output all 21 values correctly (test thoroughly).
- Mode state survives switches (enforce via `routing_state`).
- Backward compat: default to Locked.
- Audit for hidden Chinese (e.g., in dropdowns or dynamic text).
- No scope creep beyond 3 user points.

## Visual References
- `docs/visuals/rc_comparison.html`
- `docs/visuals/current_config_ui_mock.html`
- `docs/visuals/11-frozen-editable-modes.html`
- `docs/visuals/12-ui-english-consistency.html`
- `docs/visuals/13-final-ui-mock.html`
- `docs/visuals/14-all-sections-summary.html`

## Next Steps (post this spec)
- Spec self-review (done internally: no placeholders, consistent, scoped to user points).
- User reviews this doc.
- If approved: invoke writing-plans for detailed TDD implementation plan.
- Execute with subagent reviews.

All requirements addressed with minimal, focused changes following existing patterns (state helpers, single callback, `get_thresholds()`, theme).

---
*This spec captures the validated design from the full brainstorming session (user choices + multiple "准确"/"确认" approvals). Ready for your final review.*