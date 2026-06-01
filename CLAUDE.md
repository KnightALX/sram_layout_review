# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Professional Layout Review Tool for SRAM/analog circuit layouts. Two analysis
pipelines run side-by-side:

1. **Full-pipeline review** (legacy, exercised in the right-panel "Run Full
   Review" path and `report_generator.py`): shape import → `review_engine`
   RC/EM/matching → rule plugins → PPTX/PDF.
2. **Routing review** (newer, the default Routing Config / Routing Review
   tabs): shape import → 6-metric aggregator in `core.routing_metrics` →
   threshold gating → `report/routing_pptx.py`.

Both pipelines share input parsing (`core.data_parsing`, `app.state`) and
visualization (`core.visualization`), but have **separate state objects and
separate callbacks**.

## Commands

```bash
# Install
pip install -r requirements.txt

# Run the Dash UI at http://localhost:8050
./start.sh                       # defaults to port 8050
./start.sh 8080                  # alternate port
python layout_review_app.py 8080

# Tests
python tests/run_tests.py            # functional tests + a few unittest modules
python tests/run_tests.py --unit     # only unittest-style tests in tests/
python tests/run_tests.py --all      # functional + unit
python -m pytest tests/              # recommended for the pytest-style modules
python -m pytest tests/test_routing_metrics.py::test_compute_for_net_returns_all_six_metrics   # one test
python run_routing_check_tests.py    # RoutingCheckEngine unit tests (uses exec-hack to bypass core/__init__.py)

# Lint/format: no project config — repo has no pyproject.toml, no pre-commit.
# Use whatever your environment provides (e.g. `python -m pyflakes .`).
```

There is no `conftest.py`, `pytest.ini`, or `pyproject.toml`. Newer tests
expect to be run from the repo root with `sys.path.insert(0, '.')`.

## High-Level Architecture

### Module map

| Path | Role |
|------|------|
| `layout_review_app.py` | Dash entry point. Builds the app, registers two callback groups (legacy + routing), serves the 4-tab UI. |
| `review_engine.py` | Legacy full-pipeline engine. Defines `Point`, `Polygon`, `Via`, `WireSegment`, `NetRCData`, `Violation`, `ReviewSummary`, `ProfessionalLayoutReviewEngine`. Also RC calculation, EM analysis, BL/BLB matching. |
| `config_system.py` | Legacy config dataclasses: `CheckRule`, `TechConfig`, `LayoutReviewConfig`, and preset factories `get_sram_7nm_config()`, `get_sram_5nm_config()`, `get_analog_config()`. |
| `report_generator.py` | Legacy PPTX/PDF report (uses legacy engine output). |
| `core/` | Shared analysis modules (no dependencies on Dash). |
| `core/routing_check.py` | Self-contained `RoutingCheckEngine` with its own `Violation`/`RoutingCheckResult` types (NOT used by the routing review tab — see `core/routing_metrics` below). |
| `core/routing_metrics.py` | The 6-metric aggregator actually used by the Routing Review tab. Calls `core.directional_analyzer`, `core.via_coverage`, `core.rc_calculator.compute_net_metrics_with_tau`, and `core.golden_similarity`. |
| `core/rc_calculator.py`, `directional_analyzer.py`, `via_coverage.py`, `golden_similarity.py`, `effective_tau.py`, `matching_analyzer.py`, `data_parsing.py`, `visualization.py`, `path_analysis.py`, `report_visualization.py` | Individual analyzers. |
| `config/routing_thresholds.py` | `RoutingThresholds` dataclass + 4 built-in presets (`sram_7nm_wl`, `sram_5nm_io_bl`, `analog_default`, `power_relaxed`). `validate()` enforces `max_h_ratio + max_v_ratio ≥ 1.0`. |
| `config/preset_loader.py` | YAML load/save for `RoutingThresholds`. Reads from `config/presets/*.yaml`. |
| `config/presets/*.yaml` | Three user-editable preset files (sram_5nm_io_bl, sram_7nm_wl, analog_default). |
| `app/state.py` | `AppState` singleton — nets_data, engine, config, zoom/view state. Used by the legacy callbacks and by `app/routing_state` (which reads `app_state.nets_data` for regex resolution). |
| `app/routing_state.py` | `RoutingState` singleton — preset, thresholds, golden_net_name, batch_results, review_completed. |
| `app/routing_config.py` | Routing Config tab UI + `register_routing_config_callbacks`. |
| `app/routing_review.py` | Routing Review tab UI + `_run_routing_review()` + `register_routing_review_callbacks`. The 6-metric cards, sortable table, and PPTX download button live here. |
| `app/layout.py`, `app/callbacks.py`, `app/theme.py` | Legacy tab layout and callbacks (Layout View, Report Export, right-panel Properties). |
| `report/routing_pptx.py` | PPTX output for the routing review tab. |
| `rules/base_rule.py` | `BaseRule`, `ConstraintType`, `Severity`, `RuleParameter`. `matches_net()` uses regex against `TARGET_NETS`. |
| `rules/registry.py` | `RuleRegistry` singleton + `@register_rule(category)` decorator. |
| `rules/{drc,si,em,sram,qty}/__init__.py` | **All rules for a category live in one file each** (see "Rule plugin quirk" below). |
| `tests/` | Mixed unittest + pytest. Fixture shape files are `shapes_test_*.txt` next to the test code. |
| `assets/` | Local Bootstrap + Font Awesome CSS (used because the app avoids CDN at runtime). |

### Data flow — routing review (the default path)

1. User uploads `.txt` shape files or a YAML batch config on the Layout View tab. `app/callbacks.py:update_net_selector` populates `app_state.nets_data` and creates a `ProfessionalLayoutReviewEngine`, calling `calculate_net_rc` for every net.
2. On Routing Config tab, user picks a YAML preset + threshold values + golden/batch regex. `register_routing_config_callbacks` mutates the global `routing_state` singleton.
3. On Routing Review tab, clicking **Run Routing Review** calls `_run_routing_review()` (`app/routing_review.py:255`). It resolves the regexes against `app_state.nets_data`, then for each net calls `core.routing_metrics.compute_for_net(...)` which returns a 6-metric dict.
4. The callback rebuilds the 6 metric cards (averages), the sortable per-net table, and the directional viz (`create_directional_figure`).
5. **Generate Routing Report (PPTX)** → `report/routing_pptx.generate_routing_pptx(state, app_state, out_path)`, downloaded via `dcc.send_file`.

### Data flow — full review (legacy)

`app_state.engine.run_full_review()` → for each net: RC + rule plugins + matching. Violations feed `app/callbacks.py` right-panel summary and `report_generator.py`.

### Rule plugin quirk

All rules for a category are **stacked in `rules/{category}/__init__.py`** — there is no per-rule file. `RuleRegistry` discovers them via the `_auto_import_rules()` call in `rules/__init__.py` (which imports each subpackage), and `@register_rule("drc")` decorates the classes. Adding a new rule means editing the category's `__init__.py`, not creating a new file. Each rule reads from `net_data` via `getattr(net_data, "wire_segments", [])` / `getattr(net_data, "total_resistance", 0)` etc. — pair-wise checks (BL/BLB) are no-ops in the rule body and are handled at the engine level.

### Two state singletons

- `app.state.app_state` — global app state (nets_data, config, engine, zoom/view). Read by both pipelines.
- `app.routing_state.routing_state` — routing review state (preset, thresholds, golden/batch results). Mutated by routing callbacks, read by `report/routing_pptx.py`.

`app.callbacks` writes `app_state`; `app.routing_config` and `app.routing_review` write `routing_state`. Both are module-level instances — there is no DI. Tests instantiate `RoutingState()` directly when needed (see `tests/test_routing_pptx.py`).

### Adding a new routing metric or threshold field

1. Add the field to `RoutingThresholds` in `config/routing_thresholds.py` and to `_BUILTIN_PRESETS`.
2. Extend `check_gates` in `core/routing_metrics.py`.
3. Add a `THRESHOLD_FIELDS` entry in `app/routing_config.py` and the corresponding `dcc.Input(id=f"thresh-{name}")` will be wired up automatically.
4. Add a metric card entry to `METRIC_CARD_IDS` in `app/routing_review.py` (and the averaging block in `_build_metric_cards`).
5. Update each `config/presets/*.yaml`.

### Adding a new rule

Edit the relevant `rules/{drc,si,em,sram,qty}/__init__.py`, add a class with `RULE_ID`/`NAME`/`SEVERITY`/`TARGET_NETS` (regex) and `PARAMETERS`, decorate with `@register_rule("category")`, implement `check(self, net_name, net_data, polygons) -> list[dict]`. Rules are loaded at import time, so a process restart is needed.

## Notes / gotchas

- `core/__init__.py` re-exports many submodules. Some test files (`tests/test_routing_check.py`, `run_routing_check_tests.py`) avoid triggering that re-export chain by loading `review_engine` and `core.routing_check` directly via `importlib.util.spec_from_file_location`. If a new test fails with an import error from `core/__init__.py`, follow the same pattern.
- `app.routing_review._run_routing_review` always passes `vias=[]` to `compute_for_net` (with a comment about wiring up via support later) — current routing review does not see real via coverage; the placeholder `via_coverage` value comes from the polygon-overlap heuristic.
- `review_engine.calculate_net_rc` is invoked on upload even for nets the user never reviews; this is intentional so right-panel properties are populated immediately.
- `config_system.py` lives at the repo root (not under `config/`) — the `config/` package holds only the routing-threshold YAML loader. Don't move it.
