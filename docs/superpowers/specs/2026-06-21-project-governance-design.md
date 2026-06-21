# SRAM Layout Review — Project Governance Design Spec

**Date:** 2026-06-21  
**Status:** Approved  
**Scope:** Comprehensive governance (functional fixes + architecture + engineering quality)  
**Strategy:** Path 1 — incremental risk ordering (Phase 0 → 5)  
**Legacy decision:** **A — Fix and keep** both pipelines; wire `rules/` plugin in Phase 3

---

## Background

Deep audit (2026-06-21) identified:

- **P0 functional breaks:** Report Export gate, Full Review button, legacy via path, dual `review_completed`
- **Architecture debt:** dual routing engines, inverted `core/` deps, three Violation types, `rules/` plugin unused
- **Engineering gaps:** no pyproject, fragmented tests, ~1,000 LOC dead code, Dash anti-patterns

Prior cleanup (2026-06-20) fixed RC Prediction tab removal and routing via wiring. This spec addresses remaining systemic issues.

---

## Goals

1. Both pipelines (**Legacy Full Review + Routing Review**) work end-to-end from the UI.
2. `rules/` plugin system is the single rule execution path for legacy review.
3. Dead code and orphan UI removed; `suppress_callback_exceptions` eliminated.
4. `core/` is UI-free with shared models in `core/models.py`.
5. Test/lint/CI baseline established; 0 failing tests in main suite.

## Non-Goals

- Rewriting the Dash UI framework or migrating off Dash.
- Full PDK calibration against silicon (keep FreePDK45-style defaults).
- Routing-only mode (Legacy is retained per decision A).

---

## Target Architecture (End State)

```
                    ┌──────────────────────────────────────┐
                    │  core/data_parsing.parse_shape_txt   │
                    │  core/data_parsing.process_yaml_*    │
                    └──────────────────┬───────────────────┘
                                       ▼
                    ┌──────────────────────────────────────┐
                    │  NetRecord (dataclass)               │
                    │  shapes, polygons, filename, vias    │
                    └──────────┬─────────────┬─────────────┘
                               │             │
         LEGACY PIPELINE       │             │   ROUTING PIPELINE
                               ▼             ▼
              ProfessionalLayoutReviewEngine   routing_service
              rules/ RuleRegistry.check()      routing_metrics.compute_for_net
              report_generator (PPTX/PDF)      report/routing_pptx.py
                               │             │
                               └──────┬──────┘
                                      ▼
                         core/visualization (pure functions)
                         app/* (Dash callbacks only)
```

**Shared contracts:**
- `core/models.py` — `Point`, `Polygon`, `Via`, `WireSegment`, `NetRCData`, `Violation`
- `pdk/7nm.yaml` — single process parameter source (loaded by TechConfig + RCModelConfig)
- `app_state.nets_data: Dict[str, NetRecord]`
- `routing_state` — routing-only; `review_completed` flags documented per pipeline

---

## Phase Plan

### Phase 0: Baseline (1–2 days)

| Task | Deliverable |
|------|-------------|
| Add `pyproject.toml` with `[tool.pytest.ini_options] pythonpath = ["."]` | Reproducible test entry |
| Add `requirements-dev.txt` (`pytest`, `ruff`) | Dev deps separated |
| Add `tests/conftest.py` | Remove per-file `sys.path.insert` over time |
| Record baseline | `132 pass / 3 fail` documented |

**Exit criteria:** `pytest tests/ -q --ignore=tests/test_rc_prediction.py` reproducible.

---

### Phase 1: P0 Functional Fixes (3–5 days)

#### 1.1 Full Review button
- Add callback for `btn-run-review-panel` → `app_state.engine.run_full_review()`
- Set `app_state.review_completed = True` on success
- Update right-panel violations/RC summary from engine results

#### 1.2 Report Export gate
- `generate_report` callback accepts review if **either**:
  - `app_state.review_completed` (legacy), **or**
  - `routing_state.review_completed` with routing PPTX path documented separately
- Legacy export continues to use `report_generator.generate_reports(engine)`

#### 1.3 Legacy via population
- On shape upload / engine rebuild: `split_metal_via_polygons(polygons)` → populate `engine.vias[net_name]` via `_polygon_to_via`
- Pass vias into `calculate_net_rc` for each net

#### 1.4 Routing PPTX button state
- Callback `Output("btn-gen-routing-pptx", "disabled")` driven by `routing_state.review_completed`

#### 1.5 Fix pre-existing test failures
- `test_polygon_distance`: overlapping/touching rects return distance 0
- `test_rc_calculator::test_via_creation`: fix assertion (`<= 20` or cap logic)

**Exit criteria:**
- Full Review → Report Export generates PPTX/PDF
- Routing Review → PPTX download works
- `pytest tests/ -q --ignore=tests/test_rc_prediction.py` → **0 failed**

---

### Phase 2: Dead Code & Dash Cleanup (3–4 days)

#### 2.1 Remove RC Prediction dead modules
- Delete: `app/rc_prediction.py`, `app/rc_visualization.py`
- Keep: `app/rc_model.py`, `app/rc_persistence.py` (optional: merge persistence into rc_model)
- Delete or rewrite: `tests/test_rc_prediction.py`

#### 2.2 Deprecate `core/routing_check.py`
- Migrate unique tests to `routing_metrics` equivalents
- Delete `run_routing_check_tests.py`, `tests/test_routing_check.py`, `core/routing_check.py`
- Remove from `core/__init__.py` exports

#### 2.3 Remove orphan UI from `layout.py`
- Rule editor modal, net detail modal, bottom panel tabs (or wire minimally if kept)
- Unused `dcc.Store` components
- Orphan buttons: document removal of `btn-generate-report-panel` if redundant with Export tab

#### 2.4 Remove `suppress_callback_exceptions`
- Fix all callback/component mismatches exposed
- Verify app starts cleanly

#### 2.5 Replace 1s `dcc.Interval` polling
- Chain: `upload-data` / `upload-yaml` → update `dcc.Store(id='nets-meta-store')`
- `routing_config` / `routing_review` read Store instead of interval tick

**Exit criteria:** No import of deleted modules; no interval-based refresh; app starts without suppressed exceptions.

---

### Phase 3: Architecture Unification (5–7 days)

#### 3.1 `core/models.py`
- Move `Point`, `Polygon`, `Via`, `WireSegment`, `NetRCData` from `review_engine.py`
- `review_engine.py` imports from `core.models`
- Update all `core/*` to import from `core.models` (not `review_engine`)

#### 3.2 `NetRecord` dataclass
```python
@dataclass
class NetRecord:
    shapes: Dict[str, List]
    polygons: List[Polygon]
    filename: str
    vias: List[Via] = field(default_factory=list)
```
- Single YAML import via `core/data_parsing.process_yaml_batch_import`
- Remove duplicate YAML logic from `callbacks.py`

#### 3.3 Unified `Violation`
- Single `core/models.Violation` (or `core/violation.py`)
- `routing_violation.RoutingViolation` becomes alias or removed
- `check_gates` + `_compute_violations_for_net` → one `build_violations(metrics, thresholds, has_golden)`

#### 3.4 Tau units — ps everywhere
- Audit all `effective_tau`, `max_tau`; remove ns conversions
- Document: 1 Ω·fF = 1 ps

#### 3.5 `app/routing_service.py`
- Extract: `_resolve_regex`, `_run_routing_review`, shared orchestration
- `routing_config` imports service, not `routing_review._private`

#### 3.6 Wire `rules/` plugin (Decision A)
- Replace `review_engine._execute_check_rule` hardcoded dispatch with:
  ```python
  rule_impl = create_rule(rule.rule_id)  # from rules.registry
  if rule_impl:
      violations.extend(rule_impl.check(net_name, net_data, polygons))
  ```
- Map `config_system.CheckRule` IDs to `rules/` RULE_IDs (or unify rule definition)
- Fix `BaseRule.from_dict` → use module-level `create_rule()`
- Add `tests/test_rules_registry.py` + per-category smoke tests

#### 3.7 Decouple visualization
- `create_net_visualization(polygons, shapes, visible_layers, zoom)` — no `app_state` read
- Callbacks pass state explicitly

#### 3.8 Deduplicate matching
- `review_engine.analyze_matching` delegates to `core/matching_analyzer.analyze_pair_matching`

**Exit criteria:**
- `grep "from app\." core/` → empty
- `rules/` tests pass; at least DRC001 executed via registry in integration test
- `review_engine.py` < 900 lines

---

### Phase 4: Module Split & Config Unification (4–5 days)

#### 4.1 Split `theme.py`
- Move `EDA_CSS` → `assets/eda-theme.css`
- `theme.py` < 100 lines (tokens + loader)

#### 4.2 Split `report_generator.py`
- `report/pptx_legacy.py`, `report/pdf_legacy.py`
- Shim `report_generator.generate_reports` for backward compat

#### 4.3 Split `review_engine.py` further
- `core/geometry.py` — distance, overlap, bbox
- `core/em_analysis.py` — EM/IR helpers

#### 4.4 Unified PDK YAML
- `pdk/sram_7nm.yaml` — metal/via tables
- `TechConfig`, `RCModelConfig` load from same file

#### 4.5 `core/layer_style.py`
- Single layer→color map for viz + report

**Exit criteria:** No Python module > 600 LOC (except generated/CSS).

---

### Phase 5: Engineering Quality & CI (3–4 days)

#### 5.1 `ruff` configuration in `pyproject.toml`
#### 5.2 Consolidate test entry: `pytest tests/` only; deprecate `run_tests.py` runners
#### 5.3 Coverage: `pytest-cov` on `core/routing_*`, `rules/`, `data_parsing`
#### 5.4 GitHub Actions workflow
#### 5.5 Update README, CLAUDE.md with final architecture diagram

**Exit criteria:** CI green; `ruff check .` clean; routing core coverage ≥ 80%.

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Phase 3 import churn breaks app | Phase 0 baseline tests; small PRs per submodule |
| rules/ IDs don't match CheckRule IDs | Mapping table in `config_system` or migrate to registry-only |
| Removing suppress_callback_exceptions surfaces many errors | Phase 2.3 removes orphans first |
| Dual pipeline confusion persists | Document in CLAUDE.md which tab uses which pipeline |

---

## Acceptance Criteria (Program Level)

- [ ] Legacy: Upload → Full Review → Export PPTX/PDF works
- [ ] Routing: Upload → Config → Review → PPTX works
- [ ] `rules/` plugin executes at least DRC, SI, EM rules in full review
- [ ] 0 test failures in main suite (excluding optional rc tests if removed)
- [ ] No `suppress_callback_exceptions`
- [ ] No `routing_check.py`, no `rc_prediction.py`
- [ ] `core/` has zero imports from `app/`
- [ ] CI passes on push

---

## Estimated Timeline

| Phase | Duration |
|-------|----------|
| 0 | 1–2 days |
| 1 | 3–5 days |
| 2 | 3–4 days |
| 3 | 5–7 days |
| 4 | 4–5 days |
| 5 | 3–4 days |
| **Total** | **~4–6 weeks** |

---

## References

- Audit session: 2026-06-21 brainstorming
- Prior cleanup: `docs/superpowers/specs/2026-06-20-sram-layout-cleanup-design.md`
- Routing rewrite: `docs/superpowers/plans/2026-06-01-routing-review-rewrite.md`