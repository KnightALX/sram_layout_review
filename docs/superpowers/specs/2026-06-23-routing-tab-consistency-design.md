# Routing Tab Consistency Design

**Date**: 2026-06-23  
**Status**: Draft for review  
**Topic**: Fix inconsistencies between Layout View, Routing Config, and Routing Review tabs (RC values, thresholds apply/persistence, missing C display, state/callback sync)

## Decisions Confirmed (User A/A/A)

1. **RC Calculation Consistency**
   - Routing Review must produce identical resistance, capacitance, and tau values as Layout View Properties for the same nets.
   - Default path: Use the traditional tech_layers + calculate_net_rc + lumped path (same as legacy engine).
   - RCModelConfig override is **only** used when user explicitly sets a custom model (future-proofing). By default, pass `rc_model=None`.

2. **Routing Config Thresholds UX**
   - Introduce explicit "冻结 / 可编辑" (Frozen / Editable) mode toggle next to Preset selector.
   - **Frozen (default)**: Inputs disabled, values strictly from the selected preset template. Switching preset applies immediately.
   - **Editable**: Inputs enabled. Modifications create unsaved changes. Must click "Apply Thresholds" to commit to `custom_thresholds`.
   - Apply persists correctly. Switching tabs back to Config must re-hydrate inputs from current state.
   - Presets templates must always be valid (pass `validate()`). Red/invalid styling only appears for actual manual invalid inputs.
   - Switching preset while editable prompts for confirmation if unsaved changes exist.

3. **Routing Review Completeness**
   - Every threshold configurable in Routing Config must be visible and verifiable in Routing Review.
   - Add Eff. C (fF) summary card with min-max range.
   - Add "C (fF)" column to the per-net results table.
   - For every metric, display both current value and the active threshold (e.g., "45.2 / 100").
   - Prominent source banner: "当前阈值来源: sram_7nm_wl（冻结）" or "基于 sram_7nm_wl 的自定义".
   - Pass/Fail, cards, and violations must always use `routing_state.get_thresholds()` (latest applied values).
   - Apply in Config must take effect on subsequent review runs without requiring extra steps.

## Architecture

Two pipelines share input data (`app_state.nets_data`) but maintain separate states:
- `app.state.AppState` for legacy Layout View / Properties.
- `app.routing_state.RoutingState` for Config + Review.

**Key flows after fix**:
- Upload → populates shared nets_data + rebuilds legacy engine.
- Config: Preset/mode + thresholds → stored in RoutingState (thresholds or custom_thresholds, plus explicit frozen flag).
- Review: Always calls `get_thresholds()`, computes metrics with consistent RC path, renders cards/table with value + threshold + source.
- Tab switches trigger lightweight sync callbacks to re-hydrate UI from state (prevents "apply无效" symptom).

## Major Changes

### 1. RC Path Unification (core + app)
- `core/routing_metrics.py`: `compute_for_net` and calls to `compute_net_metrics_with_tau` default `rc_model=None` unless `routing_state.custom_rc_model` is explicitly set.
- `app/routing_review.py`: `_run_routing_review` passes rc_model only when custom is active.
- `core/rc_calculator.py` and `effective_tau.py` remain unchanged (they already support both paths).
- Result: R/C/τ numbers in Properties and Review cards/table become identical for the same net.

### 2. RoutingState Enhancement
- Add explicit `is_frozen: bool = True`.
- `get_thresholds()` remains the single source of truth (returns custom or preset).
- Add `get_active_preset_name()` or similar for UI source banner.
- Reset logic updated to preserve/clear frozen state appropriately.

### 3. Routing Config Tab (app/routing_config.py)
- New toggle UI next to Preset dropdown (Frozen / Editable).
- Update `create_routing_config_tab()` to render current mode and disabled state of threshold inputs.
- Stronger callbacks:
  - On tab activation ("tabs" == "tab-routing-config"): force-output current values + mode from state to all `thresh-*` inputs.
  - Preset change respects mode:
    - Frozen: load preset immediately, set custom=None, is_frozen=True.
    - Editable: prompt if unsaved.
  - Apply button: always creates/updates `custom_thresholds`, sets is_frozen=False if was editing.
  - Manual input changes only affect UI + unsaved badge while in editable; validation shows red **only** on real failures.
- Remove or guard the aggressive tentative-validate revert logic that caused defaults to appear invalid.
- Ensure all built-in + YAML presets pass `validate()` (h+v >= 1.0, positive values).

### 4. Routing Review Tab (app/routing_review.py)
- Add "Eff. C (fF)" card in `_build_metric_cards`.
- Extend table columns and `_build_table_rows` with C value (current / threshold format).
- Add threshold comparison text to all metric cards (current / threshold).
- Add/reuse source banner component at top of the tab, populated from routing_state.
- `_run_routing_review` and violation computation continue to use `get_thresholds()`.
- Empty-state and picker logic unchanged.

### 5. Cross-Tab State & Callback Hygiene
- Ensure `routing_state` is the only place that owns current thresholds and mode.
- Add/strengthen tab-switch listeners in both routing_config and routing_review callbacks to refresh from state.
- Quick-fill buttons (golden/batch) and Run Review already navigate correctly; keep behavior.
- After Apply success in Config, optionally provide a small status that new values will be used on next review run.

### 6. Preset & Validation Cleanup
- `config/routing_thresholds.py` and preset YAMLs: verify or adjust defaults so all are valid out of the box.
- `config/preset_loader.py`: no functional change, but used for frozen loads.
- Fix any initial render timing that caused red text on valid defaults.

## Non-Goals / Out of Scope
- Changing legacy Layout View Properties panel itself (it is already trusted).
- Full RC Prediction tab revival (custom model remains available via state for future use).
- Changing how batch/golden regex or visualization works.
- Adding new metrics beyond the existing 7 thresholds.

## Trade-offs Considered
- **Explicit Frozen/Editable vs Implicit**: User chose explicit (A). More UI elements but removes ambiguity and "apply无效" surprises.
- **Show every threshold in Review vs minimal**: User chose strong visibility (A). Slightly busier UI but directly satisfies "Config sets it → Review must let me check it".
- **Immediate re-compute vs run-required**: After Apply, next Run uses latest values. Full auto-recompute on every tab switch was avoided to keep performance predictable.

## Implementation Order (High Level)
1. RC path default change + RoutingState mode field.
2. Routing Config UI + callbacks (freeze/edit, tab hydration, Apply fix).
3. Routing Review cards/table/source banner.
4. Cross-callback sync + validation hardening.
5. Preset validation + test updates.
6. Manual verification with real nets.

## Risks & Mitigations
- Risk: Existing tests assume old RC numbers → update or add golden tests that assert Properties == Review numbers.
- Risk: UI state drift on tab switches → centralize all reads through `get_thresholds()` and add tab-activation refresh callbacks.
- Backward compat: Old sessions with no explicit mode default to frozen (current preset behavior).

## Visual References (in repo)
- `docs/visuals/01-rc-calculation-divergence.html`
- `docs/visuals/04-preset-freeze-edit-flow.html`
- `docs/visuals/05-routing-review-display-options.html`
- `docs/visuals/08-routing-config-design.html`
- `docs/visuals/09-routing-review-enhanced.html`
- `docs/visuals/10-full-changes-summary.html`

## Next Steps
- Review and approve this spec.
- Break into implementation plan (via writing-plans).
- Implement with tests.

---
*This document captures the validated design based on user choices during brainstorming.*