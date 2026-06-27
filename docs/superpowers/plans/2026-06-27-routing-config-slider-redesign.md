# Routing Config Range Slider UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Routing Config Range Slider UI to use Accent Strip visual style with click-to-edit value badges, math-notation logic annotations, and constraint-violation indicators, fully consistent with the project's `eda-theme.css` design system (dark + light).

**Architecture:**
- Rewrite `_build_range_input_group` in `app/routing_config.py` to produce a richer row structure (header + slider + tick-row + 2 badges + logic-row).
- Replace legacy `input-{name}-{low/high}` IDs with `badge-input-{name}-{low/high}` (transparent dcc.Input overlays rendered inside each badge).
- Add a pure helper `_compute_constraint_status(low, high, s_min, s_max)` that returns `valid` / `warning` / `invalid` based on logical checks.
- Add a pure helper `_build_logic_row_content(low, high, fmt, status)` that returns Dash children for the math notation `合规: low ≤ X ≤ high ⟷ 区间宽度 w`.
- Add a new callback per field that listens to the slider value and projects to the logic row + row className.
- Append ~200 lines of new CSS to `assets/eda-theme.css` (slider-row, range-slider-badge, tick-row, logic, section-header, rc-slider overrides).
- All colors via existing CSS variables; no hardcoded values; light mode automatically adapts via `.theme-light` overrides.

**Tech Stack:** Python 3.13, Dash 2.x, Plotly, `dcc.RangeSlider`, `dcc.Input`, custom CSS via `assets/eda-theme.css`. No new dependencies.

**Reference:** Design spec at `docs/superpowers/specs/2026-06-27-routing-config-slider-redesign-design.md`. Visual reference at `docs/mockups/slider-option-b-bimodal.html`.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `app/routing_config.py` | Modify | `RANGE_FIELDS` (add `help`, `unit`); rewrite `_build_range_input_group`; add `_compute_constraint_status`, `_build_logic_row_content` helpers; rename sync helpers (`_sync_slider_to_badges`, `_sync_badges_to_slider`); update callback registrations to use `badge-input-` IDs; add new logic-row callback; wrap ranges area with section header |
| `assets/eda-theme.css` | Modify (append) | `.slider-row`, `.range-slider-badge`, `.badge-input-overlay`, `.tick-row`, `.logic`, `.config-section`, `.section-header`, `.section-subheader`, `.ranges-container`, `.rc-slider-*` overrides |
| `tests/test_routing_config_range_fields.py` | Modify | Update assertion for new IDs (`badge-input-` replaces `input-`) |
| `tests/test_routing_config_layout.py` | Modify | Add `test_create_routing_config_tab_uses_section_header`; update `test_create_routing_config_tab_uses_range_sliders` ID assertions |
| `tests/test_routing_config_sync.py` | Modify | Update helper imports (renamed) |
| `tests/test_routing_config_slider_ui.py` | Create | New tests for `_compute_constraint_status`, `_build_logic_row_content`, new structure assertions, logic callback |

---

## Task 1: Extend `RANGE_FIELDS` with `help` and `unit` fields

**Files:**
- Modify: `app/routing_config.py:109-117`
- Modify: `tests/test_routing_config_range_fields.py`

- [ ] **Step 1: Update test to require new fields**

Replace `tests/test_routing_config_range_fields.py` line 3-9 with:

```python
def test_range_fields_has_seven_entries_with_required_keys():
    from app.routing_config import RANGE_FIELDS
    assert len(RANGE_FIELDS) == 7
    required = {"name", "label", "help", "unit", "slider_min", "slider_max", "step", "fmt"}
    for f in RANGE_FIELDS:
        assert required.issubset(f.keys()), f"missing keys in {f}"
    names = [f["name"] for f in RANGE_FIELDS]
    assert set(names) == {"h_ratio", "v_ratio", "r_ohm", "c_ff", "tau_ps",
                          "via_coverage", "similarity"}
```

Add new test at the end of the file:

```python
def test_range_fields_have_help_and_unit():
    """Every range field carries Chinese help text and SI unit (may be '')."""
    from app.routing_config import RANGE_FIELDS
    for f in RANGE_FIELDS:
        assert isinstance(f["help"], str) and len(f["help"]) > 0, f"{f['name']} missing help"
        assert isinstance(f["unit"], str), f"{f['name']} unit must be str (possibly empty)"
```

- [ ] **Step 2: Run tests to verify failure**

Run:
```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py -v
```

Expected: `test_range_fields_has_seven_entries_with_required_keys` and `test_range_fields_have_help_and_unit` FAIL with `KeyError: 'help'` / `KeyError: 'unit'`.

- [ ] **Step 3: Extend `RANGE_FIELDS` in `app/routing_config.py`**

Replace lines 109-117 of `app/routing_config.py` with:

```python
RANGE_FIELDS = [
    {"name": "h_ratio",      "label": "Horizontal Ratio",
     "help": "横向走线占比", "unit": "",
     "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01, "fmt": "{:.2f}"},
    {"name": "v_ratio",      "label": "Vertical Ratio",
     "help": "纵向走线占比", "unit": "",
     "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01, "fmt": "{:.2f}"},
    {"name": "r_ohm",        "label": "Resistance",
     "help": "走线电阻",     "unit": "\u03a9",
     "slider_min": 0.0,    "slider_max": 10000.0, "step": 50,   "fmt": "{:g}"},
    {"name": "c_ff",         "label": "Capacitance",
     "help": "走线电容",     "unit": "fF",
     "slider_min": 0,      "slider_max": 100000,  "step": 100,  "fmt": "{:g}"},
    {"name": "tau_ps",       "label": "Delay (Tau)",
     "help": "信号延迟",     "unit": "ps",
     "slider_min": 0,      "slider_max": 1000,    "step": 5,    "fmt": "{:g}"},
    {"name": "via_coverage", "label": "Via Coverage",
     "help": "通孔覆盖率",   "unit": "",
     "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01, "fmt": "{:.2f}"},
    {"name": "similarity",   "label": "Similarity",
     "help": "走线相似度",   "unit": "",
     "slider_min": 0.0,    "slider_max": 100.0,   "step": 1,    "fmt": "{:0f}"},
] # noqa: E501
```

- [ ] **Step 4: Run tests to verify pass**

Run:
```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_range_fields.py
git commit -m "feat(routing-config): add help and unit fields to RANGE_FIELDS"
```

---

## Task 2: Write failing tests for new `_build_range_input_group` structure

**Files:**
- Modify: `tests/test_routing_config_range_fields.py`

- [ ] **Step 1: Add new structural tests**

Append to `tests/test_routing_config_range_fields.py`:

```python
def test_build_range_input_group_has_new_structure_ids():
    """New row structure: row-{name}, slider-{name}, badge-input-{name}-{low|high}, logic-{name}."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    for field in RANGE_FIELDS:
        name = field["name"]
        el = _build_range_input_group(field)
        s = str(el)
        assert f"id='row-{name}'" in s, f"row-{name} container missing"
        assert f"id='slider-{name}'" in s, f"slider-{name} missing"
        assert f"id='badge-input-{name}-low'" in s, f"badge-input-{name}-low missing"
        assert f"id='badge-input-{name}-high'" in s, f"badge-input-{name}-high missing"
        assert f"id='logic-{name}'" in s, f"logic-{name} missing"
        # Legacy input-{name}-* IDs must NOT appear
        assert f"id='input-{name}-low'" not in s, f"legacy input-{name}-low still present"
        assert f"id='input-{name}-high'" not in s, f"legacy input-{name}-high still present"


def test_build_range_input_group_contains_help_and_bounds_text():
    """Each row renders help text (in row-header) and bounds text (e.g. '[0.00, 1.00]')."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    for field in RANGE_FIELDS:
        el = _build_range_input_group(field)
        s = str(el)
        # help text appears in row-header
        assert field["help"] in s, f"help '{field['help']}' missing for {field['name']}"
        # bounds text contains the formatted slider_min and slider_max
        bounds_min = field["fmt"].format(field["slider_min"])
        bounds_max = field["fmt"].format(field["slider_max"])
        assert bounds_min in s, f"slider_min '{bounds_min}' not in bounds for {field['name']}"
        assert bounds_max in s, f"slider_max '{bounds_max}' not in bounds for {field['name']}"


def test_build_range_input_group_contains_tick_row_with_three_spans():
    """tick-row contains 3 spans: min, mid, max."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    field = RANGE_FIELDS[0]  # h_ratio
    el = _build_range_input_group(field)
    s = str(el)
    # tick-row class must be present
    assert "tick-row" in s
    # min and max values formatted are visible
    fmt = field["fmt"]
    assert fmt.format(field["slider_min"]) in s
    assert fmt.format(field["slider_max"]) in s
    # mid value
    mid = (field["slider_min"] + field["slider_max"]) / 2
    assert fmt.format(mid) in s


def test_build_range_input_group_contains_logic_row_with_math_notation():
    """logic-row contains the math notation '合规: low ≤ X ≤ high'."""
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    el = _build_range_input_group(RANGE_FIELDS[0])  # h_ratio
    s = str(el)
    assert "logic" in s
    assert "合规" in s
    assert "\u2264" in s  # ≤ symbol
    assert "\u27fa" in s  # ⟷ arrow
```

- [ ] **Step 2: Run tests to verify failure (legacy implementation in place)**

Run:
```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py -v
```

Expected: The 4 new tests FAIL (legacy structure has no `row-`, `badge-input-`, `logic-` IDs).

- [ ] **Step 3: Verify only the 4 new tests fail; pre-existing tests should still pass**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py -v 2>&1 | Select-String "PASSED|FAILED"
```

Expected: `test_range_fields_has_seven_entries_with_required_keys`, `test_thresh_fields_removed`, `test_range_fields_have_help_and_unit` PASS; `test_build_range_input_group_uses_slider_and_inputs` PASS (still works with legacy impl); the 4 new tests FAIL.

- [ ] **Step 4: Commit the failing tests**

```bash
git add tests/test_routing_config_range_fields.py
git commit -m "test(routing-config): add failing tests for new slider row structure"
```

---

## Task 3: Rewrite `_build_range_input_group` with Accent Strip structure

**Files:**
- Modify: `app/routing_config.py:120-148`

- [ ] **Step 1: Replace `_build_range_input_group`**

Replace lines 120-148 of `app/routing_config.py` (the entire `_build_range_input_group` function) with:

```python
def _build_range_input_group(field):
    """Build a single range-setting row with Accent Strip visual style.

    Structure (each row is its own bordered card with left accent strip):
      row-header       — label + help + bounds info
      dcc.RangeSlider  — two handles, accent-gradient fill, no Dash internal marks
      tick-row         — 3 spans (min, mid, max)
      badges           — two badges (Low / High), each with transparent dcc.Input overlay
      logic-row        — math notation 合规: low ≤ X ≤ high ⟷ 区间宽度 w

    IDs:
      slider-{name}            dcc.RangeSlider
      badge-input-{name}-low   dcc.Input (transparent overlay, debounce=True)
      badge-input-{name}-high  dcc.Input (transparent overlay, debounce=True)
      logic-{name}             html.Div (logic annotation, gets className updates)
      row-{name}               outer html.Div (gets className updates: is-invalid / is-warning)
    """
    from dash import dcc, html
    name = field["name"]
    label = field["label"]
    help_text = field.get("help", "")
    unit = field.get("unit", "")
    fmt = field["fmt"]
    rng = getattr(routing_state.get_thresholds(), name)
    s_min = field["slider_min"]
    s_max = field["slider_max"]
    step = field["step"]
    bounds_text = f"[{fmt.format(s_min)}, {fmt.format(s_max)}]"

    initial_low, initial_high = rng.low, rng.high
    initial_status = _compute_constraint_status(initial_low, initial_high, s_min, s_max)

    return html.Div([
        # ── Row header ──────────────────────────────────────────────
        html.Div([
            html.Span([
                html.Span(label, className="name"),
                html.Span(f" \u2014 {help_text}", className="help") if help_text else None,
            ]),
            html.Span([
                "bounds ",
                html.B(bounds_text),
                f" {unit}".rstrip(),
            ], className="bounds"),
        ], className="row-header"),

        # ── RangeSlider (no Dash marks; we render custom ticks below) ──
        dcc.RangeSlider(
            id=f"slider-{name}",
            min=s_min, max=s_max, step=step,
            value=[initial_low, initial_high],
            marks=None,
            tooltip={"placement": "bottom", "always_visible": False},
            allowCross=False,
            className="range-slider",
        ),

        # ── Custom tick-row (3 labels: min, mid, max) ────────────────
        html.Div([
            html.Span(fmt.format(s_min)),
            html.Span(fmt.format((s_min + s_max) / 2), className="mid"),
            html.Span(fmt.format(s_max)),
        ], className="tick-row"),

        # ── Badges row (Low / High, each with overlay dcc.Input) ─────
        html.Div([
            _build_badge(name, "low", "Low", initial_low, unit, s_min, s_max, step),
            _build_badge(name, "high", "High", initial_high, unit, s_min, s_max, step),
        ], className="badges"),

        # ── Logic row (math notation) ────────────────────────────────
        html.Div(
            id=f"logic-{name}",
            className="logic" + (f" is-{initial_status}" if initial_status != "valid" else ""),
            children=_build_logic_row_content(initial_low, initial_high, fmt, initial_status),
        ),
    ], id=f"row-{name}",
       className="slider-row" + (f" is-{initial_status}" if initial_status != "valid" else ""),
       **{"data-field": name})


def _build_badge(field_name, bound, key_label, value, unit, s_min, s_max, step):
    """Build a single badge: key label + transparent dcc.Input overlay + unit span.

    The dcc.Input is always rendered (never hidden) and styled as a transparent
    overlay. Clicking the badge focuses the input; user types directly; debounce
    triggers the sync callback on Enter / blur.
    """
    from dash import dcc, html
    return html.Div([
        html.Span(key_label, className="key"),
        html.Span([
            dcc.Input(
                id=f"badge-input-{field_name}-{bound}",
                type="number",
                value=value,
                min=s_min, max=s_max,
                step=step,
                debounce=True,
                className="badge-input-overlay",
            ),
            html.Span(unit, className="unit") if unit else None,
        ], className="value-area"),
    ], className="range-slider-badge",
       **{"data-field": field_name, "data-bound": bound})
```

- [ ] **Step 2: Run new structural tests**

Run:
```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py -v
```

Expected: The 4 new structural tests PASS. Existing `test_build_range_input_group_uses_slider_and_inputs` will FAIL because it asserts on legacy `input-h_ratio-low`/`input-h_ratio-high` IDs.

- [ ] **Step 3: Update legacy structural test (do NOT skip — must keep coverage)**

In `tests/test_routing_config_range_fields.py`, replace `test_build_range_input_group_uses_slider_and_inputs` with:

```python
def test_build_range_input_group_uses_slider_and_badge_inputs():
    from app.routing_config import _build_range_input_group, RANGE_FIELDS
    el = _build_range_input_group(RANGE_FIELDS[0])  # h_ratio
    s = str(el)
    # str() on Dash components gives Python repr; ids are single-quoted.
    assert "id='slider-h_ratio'" in s
    assert "id='badge-input-h_ratio-low'" in s
    assert "id='badge-input-h_ratio-high'" in s
    # RangeSlider is a component of the rendered element
    assert "RangeSlider" in s
```

- [ ] **Step 4: Run full range_fields test file**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_range_fields.py
git commit -m "feat(routing-config): rewrite _build_range_input_group with accent strip + badges"
```

---

## Task 4: Add `_compute_constraint_status` pure helper (TDD)

**Files:**
- Create: `tests/test_routing_config_slider_ui.py`
- Modify: `app/routing_config.py` (append after `_build_range_input_group`)

- [ ] **Step 1: Write failing tests**

Create `tests/test_routing_config_slider_ui.py` with:

```python
"""Tests for slider row constraint detection and logic-row annotation."""
from app.routing_config import _compute_constraint_status


def test_constraint_status_valid_normal_range():
    """A normal, non-narrow range is 'valid'."""
    assert _compute_constraint_status(0.1, 0.2, 0.0, 1.0) == "valid"


def test_constraint_status_invalid_low_greater_than_high():
    """Low > High is logically impossible → 'invalid'."""
    assert _compute_constraint_status(0.5, 0.2, 0.0, 1.0) == "invalid"


def test_constraint_status_warning_zero_width():
    """Low == High (zero width) → 'warning' (no value can be compliant)."""
    assert _compute_constraint_status(0.5, 0.5, 0.0, 1.0) == "warning"


def test_constraint_status_warning_narrow_range():
    """Range narrower than 5% of full domain → 'warning'."""
    # Full domain 0..1, 5% = 0.05; width 0.04 < 0.05 → warning
    assert _compute_constraint_status(0.5, 0.54, 0.0, 1.0) == "warning"


def test_constraint_status_valid_at_5_percent_boundary():
    """Exactly 5% width → still 'valid' (boundary inclusive)."""
    # Width 0.05 of full 0..1 → valid
    assert _compute_constraint_status(0.5, 0.55, 0.0, 1.0) == "valid"


def test_constraint_status_none_inputs_default_valid():
    """None values (initial render before user interaction) → 'valid'."""
    assert _compute_constraint_status(None, None, 0.0, 1.0) == "valid"
    assert _compute_constraint_status(None, 0.5, 0.0, 1.0) == "valid"
    assert _compute_constraint_status(0.5, None, 0.0, 1.0) == "valid"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_slider_ui.py -v
```

Expected: 6 tests FAIL with `ImportError: cannot import name '_compute_constraint_status'`.

- [ ] **Step 3: Implement `_compute_constraint_status`**

Add to `app/routing_config.py` immediately after `_build_badge`:

```python
def _compute_constraint_status(low, high, s_min, s_max):
    """Return one of: 'valid', 'invalid', 'warning'.

    Logic:
    - None input(s)        → 'valid'   (initial render before any user input)
    - low > high           → 'invalid' (logical impossibility)
    - low == high          → 'warning' (zero-width interval)
    - width < 5% of domain → 'warning' (narrow range may reject all values)
    - otherwise            → 'valid'
    """
    if low is None or high is None:
        return "valid"
    if low > high:
        return "invalid"
    if low == high:
        return "warning"
    full_range = s_max - s_min
    if full_range > 0 and (high - low) < 0.05 * full_range:
        return "warning"
    return "valid"
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_slider_ui.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_slider_ui.py
git commit -m "feat(routing-config): add _compute_constraint_status pure helper"
```

---

## Task 5: Add `_build_logic_row_content` pure helper (TDD)

**Files:**
- Modify: `tests/test_routing_config_slider_ui.py`
- Modify: `app/routing_config.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_routing_config_slider_ui.py`:

```python
def test_logic_row_content_valid_uses_math_notation():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.10, 0.15, "{:.2f}", "valid")
    s = str(children)
    assert "合规" in s
    assert "0.10" in s
    assert "0.15" in s
    assert "\u2264" in s  # ≤
    assert "区间宽度" in s
    assert "0.05" in s  # width = high - low


def test_logic_row_content_invalid_shows_low_greater_than_high():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.50, 0.20, "{:.2f}", "invalid")
    s = str(children)
    assert "Low" in s
    assert "0.50" in s
    assert "High" in s
    assert "0.20" in s
    assert "不合法" in s or "重新设置" in s


def test_logic_row_content_warning_zero_width():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.50, 0.50, "{:.2f}", "warning")
    s = str(children)
    assert "区间宽度为 0" in s
    assert "请调整" in s


def test_logic_row_content_warning_narrow_range():
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.5, 0.54, "{:.2f}", "warning")
    s = str(children)
    assert "区间过窄" in s
    assert "0.04" in s
    assert "建议扩大区间" in s


def test_logic_row_content_returns_list_of_components():
    """Returns list[Component] (or compatible iterable) for Dash children."""
    from app.routing_config import _build_logic_row_content
    children = _build_logic_row_content(0.10, 0.15, "{:.2f}", "valid")
    # Must be iterable, non-empty, and contain at least one html component
    assert len(list(children)) >= 1
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_slider_ui.py -v -k "logic_row"
```

Expected: 5 logic_row tests FAIL with `ImportError: cannot import name '_build_logic_row_content'`.

- [ ] **Step 3: Implement `_build_logic_row_content`**

Add to `app/routing_config.py` immediately after `_compute_constraint_status`:

```python
def _build_logic_row_content(low, high, fmt, status):
    """Build the logic-row annotation as a list of Dash components.

    status: 'valid' | 'warning' | 'invalid'

    Returns:
        list of Dash components suitable for `children=` of an html.Div.

    Layout per status:
    - 'valid':    合规: {low} ≤ X ≤ {high}  ⟷  区间宽度 {width}
    - 'invalid':  ⚠ Low ({low}) > High ({high})，区间不合法  ·  请重新设置
    - 'warning' (low == high): ⚠ 区间宽度为 0，无任何值合规  ·  请调整 Low < High
    - 'warning' (narrow):      ⚠ 区间过窄 ({width})，可能误杀合规走线  ·  建议扩大区间
    """
    from dash import html
    if status == "invalid":
        return [
            html.Span("\u26a0 Low ("),
            html.Code(fmt.format(low)),
            html.Span(") > High ("),
            html.Code(fmt.format(high)),
            html.Span("\uff09\uff0c\u533a\u95f4\u4e0d\u5408\u6cd5  \u00b7  \u8bf7\u91cd\u65b0\u8bbe\u7f6e"),
        ]
    if status == "warning":
        if low == high:
            return [
                html.Span("\u26a0 \u533a\u95f4\u5bbd\u5ea6\u4e3a 0\uff0c\u65e0\u4efb\u4f55\u503c\u5408\u89c4  \u00b7  \u8bf7\u8c03\u6574 Low < High"),
            ]
        return [
            html.Span("\u26a0 \u533a\u95f4\u8fc7\u7a84 ("),
            html.Code(fmt.format(high - low)),
            html.Span("\uff09\uff0c\u53ef\u80fd\u8bef\u6740\u5408\u89c4\u8d70\u7ebf  \u00b7  \u5efa\u8bae\u6269\u5927\u533a\u95f4"),
        ]
    # valid
    return [
        html.Span("\u5408\u89c4: "),
        html.Code(f"{fmt.format(low)} \u2264 X \u2264 {fmt.format(high)}"),
        html.Span(" \u27fa ", className="ic"),
        html.Span("\u533a\u95f4\u5bbd\u5ea6 "),
        html.Code(fmt.format(high - low)),
    ]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_slider_ui.py -v -k "logic_row"
```

Expected: 5 logic_row tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_slider_ui.py
git commit -m "feat(routing-config): add _build_logic_row_content pure helper"
```

---

## Task 6: Wire up logic-row callback for each range field

**Files:**
- Modify: `app/routing_config.py` (in `register_routing_config_callbacks`, after the existing slider↔input sync loop)
- Modify: `tests/test_routing_config_slider_ui.py`

- [ ] **Step 1: Write test for logic-row callback registration**

Append to `tests/test_routing_config_slider_ui.py`:

```python
def test_logic_row_callback_registered_for_each_field():
    """A logic-row callback must be registered for each of the 7 range fields,
    listening to slider-{name} and writing to logic-{name} + row-{name}."""
    import dash
    from app.layout import create_layout
    from app.routing_config import (
        RANGE_FIELDS, register_routing_config_callbacks,
    )

    app = dash.Dash(__name__)
    app.layout = create_layout()
    register_routing_config_callbacks(app)

    # For each field, the callback map should reference its slider as Input
    # and its logic / row as Output.
    for field in RANGE_FIELDS:
        name = field["name"]
        slider_id = f"slider-{name}"
        logic_id = f"logic-{name}"
        row_id = f"row-{name}"
        # Search callback_map for a callback whose outputs include logic-{name}
        found = False
        for _cb_id, cb in app.callback_map.items():
            outputs = cb.get("output", "")
            if isinstance(outputs, str) and outputs.startswith(logic_id):
                found = True
                # Verify slider is among the inputs
                inputs = cb.get("inputs", [])
                input_ids = [i.get("id") if isinstance(i, dict) else str(i) for i in inputs]
                assert slider_id in str(input_ids), \
                    f"logic callback for {name} must listen to {slider_id}; got {input_ids}"
                break
        assert found, f"No callback registered with output {logic_id}"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_slider_ui.py::test_logic_row_callback_registered_for_each_field -v
```

Expected: FAIL with `AssertionError: No callback registered with output logic-h_ratio`.

- [ ] **Step 3: Implement the logic-row callback**

Find the section in `register_routing_config_callbacks` that contains the comment `# --- 7. Slider <-> Inputs bidirectional sync`. Immediately AFTER the closing of that loop (after `def _inputs_to_slider(_low, _high, _name=_name):`), add:

```python
    # --- 8. Logic-row + row className updates per field.
    #         Slider value drives the math-notation annotation and the
    #         is-invalid / is-warning class on the row container and logic row.
    #         Pure helpers _compute_constraint_status and _build_logic_row_content
    #         keep this callback thin and fully testable.
    for field in RANGE_FIELDS:
        _name = field["name"]
        _slider_id = f"slider-{_name}"
        _logic_id = f"logic-{_name}"
        _row_id = f"row-{_name}"
        _s_min = field["slider_min"]
        _s_max = field["slider_max"]
        _fmt = field["fmt"]

        @app.callback(
            [Output(_logic_id, "children"),
             Output(_logic_id, "className"),
             Output(_row_id, "className")],
            Input(_slider_id, "value"),
            prevent_initial_call=False,
        )
        def _update_logic_and_row(_value, _name=_name, _s_min=_s_min,
                                  _s_max=_s_max, _fmt=_fmt):
            from dash.exceptions import PreventUpdate
            if _value is None or len(_value) != 2:
                raise PreventUpdate
            low, high = _value[0], _value[1]
            status = _compute_constraint_status(low, high, _s_min, _s_max)
            logic_class = "logic" if status == "valid" else f"logic is-{status}"
            row_class = "slider-row" if status == "valid" else f"slider-row is-{status}"
            return (
                _build_logic_row_content(low, high, _fmt, status),
                logic_class,
                row_class,
            )
```

- [ ] **Step 4: Run test to verify pass**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_slider_ui.py::test_logic_row_callback_registered_for_each_field -v
```

Expected: PASS.

- [ ] **Step 5: Run full routing_config test suite**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py tests/test_routing_config_slider_ui.py tests/test_routing_config_sync.py tests/test_routing_config_layout.py -v
```

Expected: All tests PASS. If `test_register_callbacks_has_no_duplicate_primary_outputs` fails due to callback-output conflicts, see Troubleshooting in the plan appendix.

- [ ] **Step 6: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_slider_ui.py
git commit -m "feat(routing-config): add logic-row callback for each range field"
```

---

## Task 7: Rename sync helpers and migrate callback IDs from `input-{name}-{low|high}` to `badge-input-{name}-{low|high}`

**Files:**
- Modify: `app/routing_config.py` (rename helpers, update callback registrations, update `_routing_config_ui` callback Inputs/States)
- Modify: `tests/test_routing_config_sync.py`

- [ ] **Step 1: Update sync tests for renamed helpers**

Replace `tests/test_routing_config_sync.py` (entire file) with:

```python
"""Tests for slider<->badge-input bidirectional sync.

These exercise the pure functions _sync_slider_to_badges and
_sync_badges_to_slider directly (without a Dash server)."""
from app.routing_config import _sync_slider_to_badges, _sync_badges_to_slider


def test_slider_to_badges():
    assert _sync_slider_to_badges([0.05, 0.20]) == (0.05, 0.20)


def test_badges_to_slider_valid():
    assert _sync_badges_to_slider(0.05, 0.20) == [0.05, 0.20]


def test_badges_to_slider_low_gt_high_returns_none():
    """low > high is invalid; the sync returns None (caller raises PreventUpdate)."""
    from dash.exceptions import PreventUpdate
    try:
        result = _sync_badges_to_slider(0.20, 0.05)
        assert result is None
    except PreventUpdate:
        pass


def test_badges_to_slider_none_returns_none():
    from dash.exceptions import PreventUpdate
    try:
        result = _sync_badges_to_slider(None, 0.20)
        assert result is None
    except PreventUpdate:
        pass
```

- [ ] **Step 2: Run sync tests to verify failure (old helpers don't exist)**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_sync.py -v
```

Expected: 4 tests FAIL with `ImportError: cannot import name '_sync_slider_to_badges'`.

- [ ] **Step 3: Rename sync helpers and update callback registrations**

In `app/routing_config.py`:

(a) Rename the two helpers (around line 151):

```python
def _sync_slider_to_badges(value):
    """Slider -> Badge inputs: unpack the [low, high] list."""
    return value[0], value[1]


def _sync_badges_to_slider(low, high):
    """Badge inputs -> Slider. Returns [low, high] or None to signal PreventUpdate."""
    from dash.exceptions import PreventUpdate
    if low is None or high is None:
        raise PreventUpdate
    if low > high:
        raise PreventUpdate
    return [low, high]
```

(b) Find the section in `register_routing_config_callbacks` (around line 805) containing the comment `# --- 7. Slider <-> Inputs bidirectional sync`. Replace the variable names and helper calls:

Find this block:
```python
    for field in RANGE_FIELDS:
        _name = field["name"]
        _slider_id = f"slider-{_name}"
        _low_id = f"input-{_name}-low"
        _high_id = f"input-{_name}-high"

        # (a) Slider -> Inputs
        @app.callback(
            [Output(_low_id, "value", allow_duplicate=True),
             Output(_high_id, "value", allow_duplicate=True)],
            Input(_slider_id, "value"),
            prevent_initial_call=True,
        )
        def _slider_to_inputs(_value, _name=_name):
            return _sync_slider_to_input(_value)

        # (b) Inputs -> Slider (with low>high / None guard via PreventUpdate)
        @app.callback(
            Output(_slider_id, "value", allow_duplicate=True),
            [Input(_low_id, "value"),
             Input(_high_id, "value")],
            prevent_initial_call=True,
        )
        def _inputs_to_slider(_low, _high, _name=_name):
            return _sync_input_to_slider(_low, _high)
```

Replace with:

```python
    for field in RANGE_FIELDS:
        _name = field["name"]
        _slider_id = f"slider-{_name}"
        _low_id = f"badge-input-{_name}-low"
        _high_id = f"badge-input-{_name}-high"

        # (a) Slider -> Badge inputs
        @app.callback(
            [Output(_low_id, "value", allow_duplicate=True),
             Output(_high_id, "value", allow_duplicate=True)],
            Input(_slider_id, "value"),
            prevent_initial_call=True,
        )
        def _slider_to_badges(_value, _name=_name):
            return _sync_slider_to_badges(_value)

        # (b) Badge inputs -> Slider (with low>high / None guard via PreventUpdate)
        @app.callback(
            Output(_slider_id, "value", allow_duplicate=True),
            [Input(_low_id, "value"),
             Input(_high_id, "value")],
            prevent_initial_call=True,
        )
        def _badges_to_slider(_low, _high, _name=_name):
            return _sync_badges_to_slider(_low, _high)
```

Also update the comment header above the loop from `# --- 7. Slider <-> Inputs bidirectional sync` to `# --- 7. Slider <-> Badge inputs bidirectional sync`, and update the line `#         input-{name}-low/high.value -> slider-{name}.value` to `#         badge-input-{name}-low/high.value -> slider-{name}.value`.

(c) Find the `_routing_config_ui` callback (around line 743) and update its Inputs/States that reference `input-{name}-{low|high}` to `badge-input-{name}-{low|high}`. Find this block:

```python
        + [Input(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
        + [Input(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS],
        [State(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
        + [State(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS],
```

Replace with:

```python
        + [Input(f"badge-input-{f['name']}-low", "value") for f in RANGE_FIELDS]
        + [Input(f"badge-input-{f['name']}-high", "value") for f in RANGE_FIELDS],
        [State(f"badge-input-{f['name']}-low", "value") for f in RANGE_FIELDS]
        + [State(f"badge-input-{f['name']}-high", "value") for f in RANGE_FIELDS],
```

Also find the `if trigger_id and trigger_id.startswith("input-") and trigger_id.endswith(".value"):` check (around line 789) and update to:

```python
        if trigger_id and trigger_id.startswith("badge-input-") and trigger_id.endswith(".value"):
```

Also update the inline comments referring to "inputs" near `_routing_config_ui` (e.g. `# Last 2*n args are the 14 State input values: [low_0..low_6, high_0..high_6]` → `# Last 2*n args are the 14 State badge-input values: [low_0..low_6, high_0..high_6]`).

- [ ] **Step 4: Run sync tests to verify pass**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_sync.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full routing_config test suite to catch any ID-rename regressions**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_range_fields.py tests/test_routing_config_slider_ui.py tests/test_routing_config_sync.py tests/test_routing_config_layout.py -v
```

Expected: All tests PASS.

If `test_compute_rehydrate_outputs_*` fail due to assertion on input values, see Troubleshooting #1.

- [ ] **Step 6: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_sync.py
git commit -m "refactor(routing-config): rename input- to badge-input- IDs and sync helpers"
```

---

## Task 8: Add section header above the range sliders container

**Files:**
- Modify: `app/routing_config.py` (around line 538, the slider groups container)
- Modify: `tests/test_routing_config_layout.py`

- [ ] **Step 1: Write test for section header**

Append to `tests/test_routing_config_layout.py`:

```python
def test_create_routing_config_tab_has_section_header_for_ranges():
    """The range sliders area is preceded by a section-header and section-subheader."""
    from app.routing_config import create_routing_config_tab
    el = create_routing_config_tab()
    s = str(el)
    assert "section-header" in s
    assert "section-subheader" in s
    assert "\u9608\u503c\u533a\u95f4" in s  # 阈值区间
    assert "ranges-container" in s
    # 7 sliders, 14 badge-inputs (low + high for each of 7 fields)
    assert s.count("id='slider-") == 7
    assert s.count("id='badge-input-") == 14
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_layout.py::test_create_routing_config_tab_has_section_header_for_ranges -v
```

Expected: FAIL with `AssertionError: 'section-header' not in ...`.

- [ ] **Step 3: Wrap ranges area with section header**

In `app/routing_config.py`, find the slider groups container at line 538:

```python
                # Range slider groups (replaces legacy thresh-{name} inputs)
                html.Div([
                    _build_range_input_group(field)
                    for field in RANGE_FIELDS
                ], style={"display": "flex", "flexDirection": "column", "gap": "8px"}),
```

Replace with:

```python
                # Range slider groups (replaces legacy thresh-{name} inputs)
                html.Div([
                    html.Div("\u9608\u503c\u533a\u95f4 (Closed Interval)",
                             className="section-header"),
                    html.Div("\u62d6\u62fd\u624b\u67c4\u7c97\u8c03 \u00b7 \u70b9\u51fb Low/High \u5fbd\u7ae0\u7cbe\u786e\u8f93\u5165",
                             className="section-subheader"),
                    html.Div([
                        _build_range_input_group(field)
                        for field in RANGE_FIELDS
                    ], id="routing-config-ranges", className="ranges-container"),
                ], className="config-section"),
```

- [ ] **Step 4: Run test to verify pass**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/test_routing_config_layout.py -v
```

Expected: All tests PASS (including the new one and existing `test_create_routing_config_tab_uses_range_sliders`).

- [ ] **Step 5: Update legacy test that asserts `id='input-'` count**

Find `test_create_routing_config_tab_uses_range_sliders` in `tests/test_routing_config_layout.py` (around line 326) and replace the body:

```python
def test_create_routing_config_tab_uses_range_sliders():
    from app.routing_config import create_routing_config_tab
    el = create_routing_config_tab()
    s = str(el)
    # 7 sliders, 14 badge-inputs (low + high for each of 7 fields)
    assert s.count("id='slider-") == 7
    assert s.count("id='badge-input-") == 14
```

- [ ] **Step 6: Commit**

```bash
git add app/routing_config.py tests/test_routing_config_layout.py
git commit -m "feat(routing-config): add section header above range sliders"
```

---

## Task 9: Add CSS for slider-row, range-slider-badge, badge-input-overlay, tick-row, logic, section-header

**Files:**
- Modify: `assets/eda-theme.css` (append at end)

This task has no failing-test gate — CSS is purely declarative. After applying the CSS, manually verify in browser.

- [ ] **Step 1: Append CSS block to `eda-theme.css`**

Open `assets/eda-theme.css`. Append the following at the very end of the file (after the last rule, ensuring a blank line separates the existing content):

```css

/* ============================================================
   Range Slider Row (Routing Config Tab)
   Accent Strip visual style · dark / light mode aware
   ============================================================ */

/* Slider row container — card with left accent border + subtle gradient */
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
.slider-row:last-child { margin-bottom: 0; }
.slider-row.is-invalid { border-left-color: var(--status-fail); }
.slider-row.is-warning { border-left-color: var(--status-warning); }

/* Row header: name + help + bounds info */
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

/* Custom tick row (3 spans) */
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

/* Badges container */
.slider-row .badges { display: flex; gap: var(--space-sm); margin-top: var(--space-sm); }

/* Single badge — key + transparent dcc.Input overlay */
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
.range-slider-badge .value-area {
    display: inline-flex;
    align-items: baseline;
    gap: 2px;
}
.range-slider-badge .unit {
    color: var(--text-muted);
    font-size: 10px;
    margin-left: 2px;
}

/* Badge states: invalid / warning */
.slider-row.is-invalid .range-slider-badge {
    border-color: var(--status-fail);
    box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.12);
}
.slider-row.is-invalid .range-slider-badge .key { color: var(--status-fail); }
.slider-row.is-warning .range-slider-badge {
    border-color: var(--status-warning);
}
.slider-row.is-warning .range-slider-badge .key { color: var(--status-warning); }

/* Logic row */
.slider-row .logic {
    margin-top: var(--space-sm);
    font-family: var(--font-data);
    font-size: 10px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    flex-wrap: wrap;
}
.slider-row .logic .ic { color: var(--accent-secondary); font-weight: 500; }
.slider-row .logic code {
    background: var(--bg-tertiary);
    color: var(--accent-secondary);
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    font-family: var(--font-data);
}
.slider-row .logic.is-invalid { color: var(--status-fail); }
.slider-row .logic.is-invalid code { background: rgba(239, 68, 68, 0.12); color: var(--status-fail); }
.slider-row .logic.is-warning { color: var(--status-warning); }
.slider-row .logic.is-warning code { background: rgba(245, 158, 11, 0.12); color: var(--status-warning); }

/* Config section wrapper */
.config-section { margin-bottom: var(--space-xl); }
.config-section .section-header {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-secondary);
    font-weight: 600;
    margin-bottom: var(--space-xs);
}
.config-section .section-subheader {
    font-size: 11px;
    color: var(--text-muted);
    margin-bottom: var(--space-lg);
    font-style: italic;
}
.ranges-container { display: flex; flex-direction: column; gap: 0; }

/* Light mode adjustments */
.theme-light .slider-row {
    background: linear-gradient(90deg,
        rgba(37, 99, 235, 0.07) 0%,
        rgba(8, 145, 178, 0.015) 100%);
    box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15), 0 1px 2px rgba(15, 23, 42, 0.06);
}
.theme-light .range-slider-badge:hover { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18); }
.theme-light .slider-row.is-invalid .range-slider-badge { box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.18); }
```

- [ ] **Step 2: Visual verification (no test)**

Reference the mockup at `http://localhost:8765/slider-option-b-bimodal.html` for design intent. To see the actual app, start the dev server per project convention.

Navigate to Routing Config tab. Confirm:
- 7 slider rows render with left accent border
- Each row has header (name + help + bounds), slider, tick-row, 2 badges, logic-row
- Badges show Low/High labels + current value + unit
- Logic-row shows `合规: low ≤ X ≤ high ⟷ 区间宽度 w`

- [ ] **Step 3: Commit**

```bash
git add assets/eda-theme.css
git commit -m "feat(eda-theme): add accent-strip slider-row CSS for routing config"
```

---

## Task 10: Add CSS overrides for Dash RangeSlider internal classes (.rc-slider-*)

**Files:**
- Modify: `assets/eda-theme.css` (append at end)

- [ ] **Step 1: Append rc-slider overrides**

Append to the very end of `assets/eda-theme.css`:

```css

/* ============================================================
   Dash RangeSlider internal class overrides
   Apply Accent Strip visual treatment to the rc-slider-* DOM
   ============================================================ */
.range-slider { margin: 6px 0 !important; }

.rc-slider-rail {
    background: var(--bg-elevated) !important;
    height: 6px !important;
    border-radius: 3px !important;
    border: 1px solid var(--border-secondary) !important;
}

.rc-slider-track {
    background: linear-gradient(90deg,
        var(--accent-primary),
        var(--accent-secondary)) !important;
    height: 6px !important;
    border-radius: 3px !important;
    box-shadow: 0 0 8px rgba(59, 130, 246, 0.3) !important;
}

.rc-slider-handle {
    width: 18px !important;
    height: 18px !important;
    background: var(--bg-secondary) !important;
    border: 2px solid var(--accent-primary) !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5) !important;
    margin-top: -7px !important;
}
.rc-slider-handle::after {
    content: '' !important;
    position: absolute !important;
    top: 50% !important;
    left: 50% !important;
    width: 4px !important;
    height: 4px !important;
    background: var(--accent-primary) !important;
    border-radius: 50% !important;
    transform: translate(-50%, -50%) !important;
}
.rc-slider-handle:hover,
.rc-slider-handle:focus {
    border-color: var(--accent-secondary) !important;
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.20) !important;
}

.theme-light .rc-slider-handle { box-shadow: 0 1px 3px rgba(15, 23, 42, 0.20) !important; }
.theme-light .rc-slider-handle:hover,
.theme-light .rc-slider-handle:focus { box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.22) !important; }

.rc-slider-mark-text {
    color: var(--text-muted) !important;
    font-size: 9px !important;
    font-family: var(--font-data) !important;
}
.rc-slider-tooltip {
    background: var(--bg-tertiary) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-primary) !important;
    font-family: var(--font-data) !important;
    font-size: 11px !important;
}
.rc-slider-tooltip-inner { box-shadow: none !important; }

/* Number input native chrome stripped — modern browsers */
.badge-input-overlay {
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-family: var(--font-data);
    font-size: 12px;
    text-align: right;
    width: 64px;
    padding: 0;
    margin: 0;
    outline: none;
    -moz-appearance: textfield;
}
.badge-input-overlay::-webkit-outer-spin-button,
.badge-input-overlay::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
.range-slider-badge:focus-within {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.20);
    background: var(--bg-tertiary);
}
.badge-input-overlay:focus {
    color: var(--accent-primary);
    font-weight: 600;
}
.theme-light .range-slider-badge:focus-within { box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.22); }
```

- [ ] **Step 2: Visual verification (no test)**

Re-run the dev server (or reload page if already running). Confirm:
- Slider rail is `--bg-elevated` (subtle gray in dark, light gray in light)
- Slider track fill uses blue → cyan gradient
- Handles are 18px circles with accent border + 4px inner dot
- Tooltips (hover handle) show on dark `--bg-tertiary`
- Number input arrows are hidden; clicking the badge focuses the input
- Focus state on badge shows accent border + glow

- [ ] **Step 3: Commit**

```bash
git add assets/eda-theme.css
git commit -m "feat(eda-theme): add rc-slider overrides for accent-strip handles/track"
```

---

## Task 11: Final verification — full test suite + dark/light visual regression

**Files:** None modified.

- [ ] **Step 1: Run the full test suite**

```bash
cd d:\workspace\project\sram_layout_review
python -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 100
```

Expected: All tests PASS. Pay particular attention to:
- `tests/test_routing_config_range_fields.py` — 7 tests
- `tests/test_routing_config_slider_ui.py` — 12 tests (6 constraint + 5 logic + 1 callback)
- `tests/test_routing_config_sync.py` — 4 tests
- `tests/test_routing_config_layout.py` — all tests including new `test_create_routing_config_tab_has_section_header_for_ranges`
- `tests/test_routing_config_state_machine.py` — regression: state machine unaffected
- `tests/test_routing_review_cells.py` — regression: review tab cell formatting unaffected
- `tests/test_routing_review_banner.py` — regression: Active Threshold Source banner unchanged

If any tests fail, see Troubleshooting below.

- [ ] **Step 2: Manual visual regression — dark mode**

Start the app per project convention. Navigate to Routing Config tab. Verify:
- 7 slider rows render with visible left accent border (blue gradient)
- Each row has clear visual hierarchy: header → slider → ticks → 2 badges → logic-row
- Slider track uses blue → cyan gradient for current range
- Handles are 18px circles, draggable
- Clicking Low/High badge focuses a transparent number input (try typing a value, press Enter)
- Logic-row shows `合规: low ≤ X ≤ high ⟷ 区间宽度 w`
- Try dragging low > high → row left-border turns red, badges turn red, logic shows ⚠ warning

- [ ] **Step 3: Manual visual regression — light mode**

Toggle theme to light mode (use the existing theme toggle button in the app header). Verify:
- All colors adapt: accent still visible against white background
- Slider row has subtle blue gradient (not too saturated)
- Logic-row code badges are readable
- Number input badge bg is light gray (not stark white)
- Hover state on badges still shows accent border

- [ ] **Step 4: Final commit (if any cleanup needed)**

If Steps 1-3 surfaced issues, fix them and commit:
```bash
git add -A
git commit -m "fix(routing-config): cleanup from final visual regression"
```

If clean, no commit needed.

---

## Troubleshooting

### 1. `test_compute_rehydrate_outputs_*` fails with `out[14] != expected value`

`_compute_rehydrate_outputs` projects slider values + low/high values to its 42-tuple. The values at indices 14..20 are `low` values, 21..27 are `high` values. If a test asserts on `out[14]`, it expects the **low value** of the first range field. The position is unaffected by ID rename; only the **source** changed. If the source switched from `input-h_ratio-low` to `badge-input-h_ratio-low`, verify the `_routing_config_ui` callback's Inputs/States are updated to use the new IDs (Task 7 Step 3c). If the test still fails, the value at `out[14]` should still equal `routing_state.get_thresholds().h_ratio.low`.

### 2. Dash callback registration: `Output ... is already in use`

This means two callbacks try to write to the same Output without `allow_duplicate=True`. Common cause:
- After Task 7, the `_slider_to_inputs` callback and `_slider_to_badges` callback are both registered. Verify only the renamed version remains. Search the file for `_slider_to_` and ensure only one definition remains.

### 3. Slider not visually updating when dragging

Verify the callback chain:
- Slider `value` change → `_slider_to_badges` callback fires → updates `badge-input-{name}-{low|high}` `value`
- Slider `value` change → `_update_logic_and_row` callback fires → updates `logic-{name}` `children` + `row-{name}` `className`

If the slider value doesn't update on drag, check that `allowCross=False` is set on the RangeSlider (prevents handles from crossing).

### 4. Number input overlay not focusing when badge clicked

The dcc.Input is positioned via the layout (not absolutely). Ensure:
- `.range-slider-badge` has `cursor: text` (set in CSS)
- `.badge-input-overlay` has `background: transparent; border: none` (set in CSS)
- The Input is a child of `.value-area` which is a child of `.range-slider-badge`

If clicking still doesn't focus, inspect the DOM to ensure the Input is the rightmost interactive element in the badge.

### 5. Light mode accent border too saturated

Reduce the `linear-gradient` opacity in `.theme-light .slider-row` from `rgba(37, 99, 235, 0.07)` to `rgba(37, 99, 235, 0.04)` if too vivid. Tweak as needed for visual balance.

---

## Self-Review Notes

**Spec coverage check:**

| Spec section | Plan task |
|---|---|
| 2.1 Row structure | Tasks 2, 3 |
| 2.2 CSS variables reuse | Tasks 9, 10 (no new variables needed; reuse existing) |
| 2.3 New CSS blocks | Tasks 9, 10 |
| 2.4 dark/light verification | Tasks 11 step 2-3 |
| 3.1 `_build_range_input_group` new implementation | Task 3 |
| 3.2 `RANGE_FIELDS` extension | Task 1 |
| 3.3 Outer container section header | Task 8 |
| 4.1 Slider ↔ Badge sync | Task 7 |
| 4.2 Badge edit mode (transparent overlay) | Task 10 (CSS) |
| 4.3 Constraint violation detection | Tasks 4, 6 |
| 4.4 Logic row text rules | Task 5 |
| 4.5 Unit display | Task 1 (RANGE_FIELDS), Task 3 (badge builder) |
| 5 Data flow | All tasks |
| 6.1 Unit tests | Tasks 1, 4, 5 |
| 6.2 Callback tests | Task 6 |
| 6.3 Visual regression | Task 11 |
| 6.4 Existing tests preserved | Tasks 3 step 3, 7, 8 step 5 |
| 7 Acceptance criteria | Task 11 final verification |

**Placeholder scan:** No "TBD", "TODO", "implement later", or "fill in details" found in any task code block.

**Type consistency:**
- `Range.low: float`, `Range.high: float` (unchanged from existing spec)
- `_compute_constraint_status(low, high, s_min, s_max) -> str` (returns one of `"valid"`, `"warning"`, `"invalid"`)
- `_build_logic_row_content(low, high, fmt, status) -> list[Component]` (returns Dash children list)
- IDs: `slider-{name}`, `badge-input-{name}-low`, `badge-input-{name}-high`, `logic-{name}`, `row-{name}` (consistent across all tasks)

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-27-routing-config-slider-redesign.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints