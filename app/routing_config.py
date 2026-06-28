"""Routing-focused Configuration tab.

Replaces `_create_config_content()` from `app/layout.py`.
Exposes ONLY routing thresholds + preset selector + golden/batch regex — no
rule editor, no per-rule enable/disable.

Reads available nets from `app.state.app_state.nets_data` (populated by the
Layout View tab's upload callbacks). Surfacing this connection in the UI is
critical — without it, the user has no way to know what nets exist or whether
their regex matches anything.

Task 7 hygiene: threshold *reads* are centralized. All code in this file
(and routing_review) obtains active thresholds exclusively via
routing_state.get_thresholds() and reads mode via the is_frozen attribute
(True == Locked per the UI buttons).
(get_thresholds is the single source of truth for values; internal writes to
the backing fields are only for preset load / set_custom paths.)
"""
from __future__ import annotations

import re
from typing import List, Optional

from dash import dcc, html

from app.routing_review import _run_routing_review
from app.routing_state import routing_state
from app.state import app_state
from config.preset_loader import list_yaml_presets
from config.routing_thresholds import RoutingThresholds


# For test access to the complex preset/thresh handling logic (without requiring
# a full Dash app or inner-callback extraction). Not part of public API surface.
def _handle_routing_preset_or_thresh(
    preset: Optional[str],
    range_pairs,
    trigger: Optional[str],
) -> tuple:
    """Testable core logic for preset/apply handling.

    Args:
        preset: preset name (used when trigger=='routing-preset')
        range_pairs: list of 7 `[low, high]` pairs (slider values)
        trigger: action identifier

    Returns the 14-element output tuple (mode buttons + status + 7 sliders).
    """
    is_frozen = routing_state.is_frozen
    thresholds = routing_state.get_thresholds()
    f_cls, e_cls = _mode_button_classes(is_frozen)
    slider_vals = [[getattr(thresholds, fld["name"]).low,
                    getattr(thresholds, fld["name"]).high] for fld in RANGE_FIELDS]

    if trigger == "routing-preset" and preset:
        if preset == routing_state.current_preset:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        if not is_frozen:
            curr_p = routing_state.current_preset
            warn = ("Edit Mode: Preset switch Blocked (unsaved changes). "
                    "Please click Apply or switch to Locked first.")
            f_ed, e_ed = _mode_button_classes(False)
            return tuple([f_ed, e_ed, f"Loaded: {curr_p}", warn,
                          html.Span("\u25cf unsaved changes",
                                    style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
                          "", curr_p]
                         + slider_vals)
        try:
            t = RoutingThresholds.for_preset(preset)
            routing_state.current_preset = preset
            routing_state.thresholds = t
            routing_state.set_frozen_mode(True)
            status = f"Loaded preset: {preset}"
            new_slider = [[getattr(t, fld["name"]).low,
                           getattr(t, fld["name"]).high] for fld in RANGE_FIELDS]
            f_f, e_f = _mode_button_classes(True)
            return tuple([f_f, e_f, status, "", html.Span("", style={"display": "none"}), "", preset]
                         + new_slider)
        except Exception as e:
            return tuple([f_cls, e_cls, f"Error: {e}", "", html.Span("", style={"display": "none"}), "", routing_state.current_preset]
                         + slider_vals)

    return _render_state(list(range_pairs))

# REMOVED: THRESHOLD_FIELDS replaced by RANGE_FIELDS below (Task 14-20 will
# migrate the remaining references in this module).
# THRESHOLD_FIELDS = [
#     ("max_h_ratio", "Max H Ratio (WL gate)", "0.0", "1.0", "0.01"),
#     ("max_v_ratio", "Max V Ratio (IO gate)", "0.0", "1.0", "0.01"),
#     ("max_r_ohm", "Max Total R (Ω)", "0", "10000", "0.1"),
#     ("max_c_ff", "Max Total C (fF)", "0", "100000", "1"),
#     ("max_tau_ps", "Max Effective τ (ps)", "0", "1000", "0.1"),
#     ("min_via_coverage", "Min Via Coverage", "0.0", "1.0", "0.01"),
#     ("min_similarity", "Min Golden Similarity", "0", "100", "1"),
# ]
# Task 6 Step 3: mins for R/C/tau loosened to "0" (from "0.1"/"0.01") so that
# browser-native :invalid styling (red) is not triggered for near-zero or
# intermediate positive values during live typing. Real >0 enforcement still
# happens in RoutingThresholds.validate() on Apply only.

# 7 metric range fields, each with a RangeSlider (low, high handles) plus
# two dcc.Input fields for precise text input. The fmt field controls
# how values are displayed in the inputs.
RANGE_FIELDS = [
    {"name": "h_ratio",      "label": "Horizontal Ratio",
     "help": "\u6a2a\u5411\u8d70\u7ebf\u5360\u6bd4", "unit": "",
     "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01, "fmt": "{:.2f}"},
    {"name": "v_ratio",      "label": "Vertical Ratio",
     "help": "\u7eb5\u5411\u8d70\u7ebf\u5360\u6bd4", "unit": "",
     "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01, "fmt": "{:.2f}"},
    {"name": "r_ohm",        "label": "Resistance",
     "help": "\u8d70\u7ebf\u7535\u963b",     "unit": "\u03a9",
     "slider_min": 0.0,    "slider_max": 10000.0, "step": 50,   "fmt": "{:g}"},
    {"name": "c_ff",         "label": "Capacitance",
     "help": "\u8d70\u7ebf\u7535\u5bb9",     "unit": "fF",
     "slider_min": 0,      "slider_max": 100000,  "step": 100,  "fmt": "{:g}"},
    {"name": "tau_ps",       "label": "Delay (Tau)",
     "help": "\u4fe1\u53f7\u5ef6\u8fdf",     "unit": "ps",
     "slider_min": 0,      "slider_max": 1000,    "step": 5,    "fmt": "{:g}"},
    {"name": "via_coverage", "label": "Via Coverage",
     "help": "\u901a\u5b54\u8986\u76d6\u7387",   "unit": "",
     "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01, "fmt": "{:.2f}"},
    {"name": "similarity",   "label": "Similarity",
     "help": "\u8d70\u7ebf\u76f8\u4f3c\u5ea6",   "unit": "",
     "slider_min": 0.0,    "slider_max": 100.0,   "step": 1,    "fmt": "{:0f}"},
] # noqa: E501


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


def _build_logic_row_content(low, high, fmt, status):
    """Backward-compatible alias for `_build_logic_compact_content`.

    Older tests (and any external imports) still reference this name. The
    implementation has moved to the more compact `_build_logic_compact_content`.
    """
    return _build_logic_compact_content(low, high, fmt, status)


# Row grouping for compact 2-column layout. Each tuple holds the field names
# to share a row (right entry may be None for single-cell rows).
# Order matches RANGE_FIELDS above.
RANGE_ROW_GROUPS = [
    ("h_ratio", "v_ratio"),
    ("r_ohm", "c_ff"),
    ("tau_ps", "via_coverage"),
    ("similarity", None),
]


def _field_by_name(name):
    """Look up the field descriptor dict for a given threshold name."""
    for fld in RANGE_FIELDS:
        if fld["name"] == name:
            return fld
    raise KeyError(f"Unknown range field: {name}")


def _build_metric_cell(field):
    """Build a single metric cell \u2014 name + help + bounds + RangeSlider + tick + logic.

    The RangeSlider is the ONLY input control. Its built-in tooltip
    (`always_visible=True`) replaces the previous low/high text badges,
    showing the current low/high values directly on the bar so users can
    read and drag-set them in one place.

    IDs:
      slider-{name}     dcc.RangeSlider (tooltip={"always_visible": True})
      logic-{name}      html.Div (logic-compact annotation; className updated)
      cell-{name}       outer html.Div (className updated: is-invalid / is-warning)
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

    cell_class = "metric-cell"
    if initial_status != "valid":
        cell_class += f" is-{initial_status}"

    return html.Div([
        # \u2500\u2500 Metric header (name + help + bounds) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        html.Div([
            html.Span([
                html.Span(label, className="metric-name"),
                html.Span(f" \u2014 {help_text}", className="metric-help") if help_text else None,
            ]),
            html.Span([
                "bounds ",
                html.B(bounds_text),
                f" {unit}".rstrip(),
            ], className="metric-bounds"),
        ], className="metric-header"),

        # \u2500\u2500 RangeSlider (tooltip merged \u2014 shows low/high on the bar) \u2500\u2500\u2500\u2500\u2500
        dcc.RangeSlider(
            id=f"slider-{name}",
            min=s_min, max=s_max, step=step,
            value=[initial_low, initial_high],
            marks=None,
            tooltip={"placement": "bottom", "always_visible": True},
            allowCross=False,
            className="range-slider",
            persistence=False,
        ),

        # \u2500\u2500 Custom tick-row (min, mid, max) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        html.Div([
            html.Span(fmt.format(s_min)),
            html.Span(fmt.format((s_min + s_max) / 2), className="mid"),
            html.Span(fmt.format(s_max)),
        ], className="tick-row"),

        # \u2500\u2500 Logic-compact row (math notation) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        html.Div(
            id=f"logic-{name}",
            className="logic-compact"
                     + (f" is-{initial_status}" if initial_status != "valid" else ""),
            children=_build_logic_compact_content(initial_low, initial_high, fmt, initial_status),
        ),
    ], id=f"cell-{name}",
       className=cell_class,
       **{"data-field": name})


def _build_compact_range_row(left_field, right_field=None):
    """Build a 1- or 2-cell row. Two cells share one outer .range-row.double border.

    The outer .range-row container provides a shared border so two cells feel
    like one logical group. The grid auto-layout (CSS) handles the column split.
    """
    if right_field is None:
        return html.Div(
            [_build_metric_cell(left_field)],
            className="range-row single",
        )
    return html.Div(
        [_build_metric_cell(left_field), _build_metric_cell(right_field)],
        className="range-row double",
    )


def _build_logic_compact_content(low, high, fmt, status):
    """Build the logic-compact annotation as a list of Dash components.

    Compact text \u2014 uses inline `\u2264 X \u2264` instead of a wide multi-line notation.
    Status determines color via class on the container.
    """
    from dash import html
    if status == "invalid":
        return [
            html.Span("\u26a0 Low ("),
            html.Code(fmt.format(low)),
            html.Span(") > High ("),
            html.Code(fmt.format(high)),
            html.Span("\uff09\uff0c\u533a\u95f4\u4e0d\u5408\u6cd5"),
        ]
    if status == "warning":
        if low == high:
            return [
                html.Span("\u26a0 \u533a\u95f4\u5bbd\u5ea6\u4e3a 0"),
            ]
        return [
            html.Span("\u26a0 \u533a\u95f4\u8fc7\u7a84 ("),
            html.Code(fmt.format(high - low)),
            html.Span("\uff09"),
        ]
    # valid
    return [
        html.Span("\u5408\u89c4 "),
        html.Code(f"{fmt.format(low)} \u2264 X \u2264 {fmt.format(high)}"),
        html.Span(" \u27fa "),
        html.Code(fmt.format(high - low)),
    ]


def _sync_slider_to_tooltip(value):
    """Slider -> Tooltip: passed-through (kept for API symmetry / tests).

    Dash renders the always-visible tooltip automatically from the slider's
    value, so no explicit projection is required. This stub exists only so
    tests/test_routing_config_sync.py can import a single function name.
    """
    return value


def _mode_button_classes(frozen: bool) -> tuple[str, str]:
    """Pure helper: return (locked_button_class, editable_button_class).

    frozen=True means Locked (primary style on Locked button).
    Used by layout builder and all callbacks that touch mode buttons.
    Reduces duplication of the ternary class logic.
    """
    if frozen:
        return "btn btn-primary btn-sm", "btn btn-secondary btn-sm"
    return "btn btn-secondary btn-sm", "btn btn-primary btn-sm"


def _disabled_list(frozen: bool, n_fields: int) -> list[bool]:
    """Pure helper: return disabled flags for threshold inputs.

    frozen=True (Locked) -> all disabled; frozen=False (Editable) -> all enabled.
    """
    return [frozen] * n_fields


def _validate_apply(range_pairs):
    """Validate 7 `[low, high]` slider pairs for Apply.

    Args:
        range_pairs: list of 7 `[low, high]` lists, one per RANGE_FIELDS
            entry. In the compact 2-column redesign, each RangeSlider exposes
            its value as a `[low, high]` list — there are no separate
            "low input" / "high input" anymore.

    Returns:
        (valid_thresholds, None) on success
        (None, error_message) on failure
    """
    n = len(RANGE_FIELDS)
    if len(range_pairs) != n:
        return None, f"Expected {n} slider pairs, got {len(range_pairs)}"

    current = routing_state.get_thresholds()
    tentative_dict = current.to_dict()

    try:
        for i, field in enumerate(RANGE_FIELDS):
            name = field["name"]
            pair = range_pairs[i]
            if pair is None or len(pair) != 2:
                continue
            low, high = pair[0], pair[1]
            if low is None or high is None:
                continue
            low_f, high_f = float(low), float(high)
            tentative_dict[name] = {"low": low_f, "high": high_f}
    except (TypeError, ValueError) as e:
        return None, f"Invalid number: {e}"

    try:
        tentative = RoutingThresholds.from_dict(tentative_dict)
        tentative.validate()
    except Exception as e:
        return None, str(e)
    return tentative, None


def _apply_thresholds(range_pairs):
    """Apply the user's 7 `[low, high]` slider pairs to `routing_state`.

    Updates `routing_state.custom_thresholds` and switches to Editable mode
    on success; sets `routing_state.last_error` on validation failure.
    """
    valid, err = _validate_apply(range_pairs)
    if valid is None:
        routing_state.last_error = err
    else:
        routing_state.set_custom(valid)
        routing_state.last_error = None
    routing_state.last_status = ""


def _render_state(range_pairs):
    """Project routing_state to UI outputs (14-element tuple).

    Args:
        range_pairs: list of 7 `[low, high]` lists (slider values from the
            browser). Used only for the unsaved-changes diff vs. state.

    Output tuple order:
      [0]   mode-frozen className
      [1]   mode-editable className
      [2]   routing-preset-status children
      [3]   routing-config-status children
      [4]   thresh-unsaved-badge children
      [5]   thresh-apply-status children
      [6]   routing-preset value
      [7..13]  7 slider-{name} values (each [low, high])

    Note: low/high text badges were removed in the compact 2-column redesign.
    The slider's always-visible tooltip is the single source for displayed values.
    """
    thresholds = routing_state.get_thresholds()
    is_frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(is_frozen)
    n = len(RANGE_FIELDS)
    slider_vals = [[getattr(thresholds, fld["name"]).low,
                    getattr(thresholds, fld["name"]).high] for fld in RANGE_FIELDS]

    def _vals_differ(a, b):
        try:
            return abs(float(a) - float(b)) > 1e-9
        except Exception:
            return a != b

    has_unsaved = False
    if not is_frozen and len(range_pairs) == n:
        for i, fld in enumerate(RANGE_FIELDS):
            cur_low = slider_vals[i][0]
            cur_high = slider_vals[i][1]
            pair = range_pairs[i]
            if pair is None or len(pair) != 2:
                continue
            inp_low = pair[0]
            inp_high = pair[1]
            if _vals_differ(inp_low, cur_low) or _vals_differ(inp_high, cur_high):
                has_unsaved = True
                break

    source = routing_state.get_threshold_source()
    preset_status = html.Span(source, style={"color": "#888", "fontSize": "11px"})

    if routing_state.last_error:
        err = routing_state.last_error
        if err and ("Blocked" in err or "Preset switch" in err or "Edit Mode" in err):
            config_status = html.Span(err, style={"fontSize": "11px", "color": "#E67E22"})
        else:
            config_status = html.Span(f"Error: {err}", style={"fontSize": "11px", "color": "#C0392B"})
    elif routing_state.last_status:
        config_status = html.Span(routing_state.last_status, style={"fontSize": "11px", "color": "#2C7A2C"})
    else:
        config_status = ""

    if has_unsaved:
        unsaved_badge = html.Span("Unsaved Changes", style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"})
        apply_status = html.Span("Thresholds modified - click Apply to save.", style={"fontSize": "11px", "color": "#E67E22"})
    else:
        unsaved_badge = html.Span("", style={"display": "none"})
        apply_status = ""

    return tuple([
        f_cls, e_cls,
        preset_status, config_status, unsaved_badge, apply_status,
        routing_state.current_preset,
    ] + slider_vals)


def _dispatch_action(trigger_id, trigger_value, range_pairs):
    """Handle non-typing triggers (preset, mode, apply, tabs).

    Args:
        trigger_id: e.g. "btn-apply-thresholds.n_clicks"
        trigger_value: value the trigger fired with
        range_pairs: list of 7 `[low, high]` pairs from the sliders
            (used by Apply). Each item is itself a 2-element list.
    """
    if trigger_id is None:
        return
    if trigger_id == "routing-preset.value":
        new_preset = trigger_value
        if routing_state.is_frozen:
            routing_state.current_preset = new_preset
            routing_state.thresholds = RoutingThresholds.for_preset(new_preset)
            routing_state.custom_thresholds = None
            routing_state.last_error = None
            routing_state.last_status = ""
        else:
            if new_preset and new_preset != routing_state.current_preset:
                routing_state.last_error = ("Edit Mode: Preset switch Blocked (unsaved changes). "
                                            "Please click Apply or switch to Locked first.")
                routing_state.last_status = ""
        return
    if trigger_id == "mode-frozen.n_clicks":
        routing_state.set_frozen_mode(True)
        routing_state.last_error = None
        routing_state.last_status = ""
        return
    if trigger_id == "mode-editable.n_clicks":
        routing_state.set_frozen_mode(False)
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        routing_state.last_error = None
        routing_state.last_status = ""
        return
    if trigger_id == "btn-apply-thresholds.n_clicks":
        _apply_thresholds(range_pairs)
        return
    if trigger_id == "tabs.value":
        return


def _compute_rehydrate_outputs():
    """Return the full 14-tuple to re-populate Routing Config controls from state.
    Used by the tab-switch rehydration callback. Order matches the output list
    used by preset/mode/apply callbacks:
      [mode-frozen, mode-editable, preset-status, config-status,
       unsaved-badge, apply-status, preset-value]
      + 7 slider-{name} values.
    Clears transient badges on re-entry for clean re-hydration while restoring
    authoritative values + mode from routing_state.
    """
    thresholds = routing_state.get_thresholds()
    is_frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(is_frozen)
    slider_vals = [[getattr(thresholds, fld["name"]).low,
                    getattr(thresholds, fld["name"]).high] for fld in RANGE_FIELDS]
    return tuple([
        f_cls, e_cls,
        f"Loaded: {routing_state.current_preset}",
        "",
        html.Span("", style={"display": "none"}),
        "",
        routing_state.current_preset,
    ] + slider_vals)


def get_threshold_input_ids() -> List[str]:
    """Return the slider IDs for all threshold fields (used in callbacks).

    In the compact 2-column redesign, the only threshold input control is the
    RangeSlider. The old low/high text badges were merged into the slider via
    its always-visible tooltip, so there are no separate dcc.Input IDs anymore.
    """
    return [f"slider-{fld['name']}" for fld in RANGE_FIELDS]


def _preset_options():
    # YAML presets + code-only built-in presets (e.g. power_relaxed, which has
    # no YAML file). `_BUILTIN_PRESETS` is a known private symbol of
    # config.routing_thresholds; we use it locally rather than add a new
    # public list_builtin_presets() API.
    yaml_names = set(list_yaml_presets())
    from config.routing_thresholds import _BUILTIN_PRESETS
    code_only = sorted(set(_BUILTIN_PRESETS.keys()) - yaml_names)
    options = [{"label": n, "value": n} for n in sorted(yaml_names)]
    options.extend({"label": f"{n} (built-in)", "value": n} for n in code_only)
    return options


def _resolve_regex(pattern: str) -> tuple[Optional[re.Pattern], List[str], Optional[str]]:
    """Resolve a regex against `app_state.nets_data`.

    Returns:
        (compiled_regex | None, matched_net_names, error_message | None)
    """
    if not pattern:
        return None, [], None
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return None, [], f"Invalid regex: {e}"
    matches = [n for n in app_state.nets_data if rx.search(n)]
    return rx, matches, None


def _loaded_nets_status() -> html.Div:
    """Show how many nets the Layout View has loaded — and the first 5 names."""
    nets = sorted(app_state.nets_data.keys())
    if not nets:
        return html.Div([
            html.Span("⚠ ", style={"color": "#E67E22", "fontWeight": "600"}),
            html.Span("No nets loaded. ", style={"color": "#E67E22"}),
            html.Span("Go to the ", style={"color": "#888"}),
            html.B("Layout View"),
            html.Span(" tab and upload shape files or a YAML batch config.",
                      style={"color": "#888"}),
        ], className="text-muted", style={"fontSize": "11px", "marginTop": "6px"})

    preview = ", ".join(nets[:5]) + (f" … (+{len(nets) - 5} more)" if len(nets) > 5 else "")
    return html.Div([
        html.Span("✓ ", style={"color": "#27AE60", "fontWeight": "600"}),
        html.Span(f"{len(nets)} net(s) loaded from Layout View: ",
                  style={"color": "#27AE60", "fontWeight": "600"}),
        html.Span(preview, style={"color": "#888", "fontSize": "10px"}),
    ], className="text-muted", style={"fontSize": "11px", "marginTop": "6px"})


def _regex_match_preview(pattern: str, label: str) -> html.Div:
    """Inline 'matches N nets' / error message under a regex input."""
    if not pattern:
        return html.Div("Enter a regex to see matching nets.",
                         className="text-muted",
                         style={"fontSize": "10px", "marginTop": "4px"})
    _, matches, err = _resolve_regex(pattern)
    if err:
        return html.Div(err, style={"fontSize": "10px", "color": "#C0392B",
                                    "marginTop": "4px"})
    if not matches:
        return html.Div(
            f"⚠ matches 0 of {len(app_state.nets_data)} loaded nets",
            style={"fontSize": "10px", "color": "#E67E22", "marginTop": "4px"}
        )
    # Golden regex must match exactly one net (we use the first match); warn
    # the user if their pattern is too loose.
    if label == "Golden" and len(matches) > 1:
        return html.Div(
            f"⚠ Golden regex matches {len(matches)} nets — only the first "
            f"({matches[0]!r}) will be used. Use ^name$ for exact match.",
            style={"fontSize": "10px", "color": "#E67E22", "marginTop": "4px"}
        )
    preview = ", ".join(matches[:3]) + (f" … (+{len(matches) - 3})" if len(matches) > 3 else "")
    return html.Div(
        f"✓ {label}: matches {len(matches)} net(s) — {preview}",
        style={"fontSize": "10px", "color": "#27AE60", "marginTop": "4px"}
    )


def _run_and_status() -> str:
    """Run the routing review and return a human-readable status string.

    Side effect: stores the result on `routing_state.last_status` (success)
    or `routing_state.last_error` (failure) so the next render of
    routing-config-status children — by the single _routing_config_ui
    callback — picks up the message.

    Caller is responsible for guarding against an empty `app_state.nets_data`
    (the button click callbacks do that up-front and `raise PreventUpdate`).
    """
    try:
        _run_routing_review()
        msg = (
            f"Reviewed {len(routing_state.batch_results)} nets, "
            f"golden={routing_state.golden_net_name or '(none)'}"
        )
        routing_state.last_status = msg
        routing_state.last_error = None
        return msg
    except Exception as e:
        routing_state.last_error = str(e)
        routing_state.last_status = ""
        return f"Error: {e}"


def create_routing_config_tab():
    """Build the routing Configuration tab content (Dash components only)."""
    preset = routing_state.current_preset
    # Centralized reads (Task 7 Step 1)
    thresholds = routing_state.get_thresholds()
    thr = thresholds
    is_frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(is_frozen)

    nets = sorted(app_state.nets_data.keys())
    first_net = nets[0] if nets else ""

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
                # Explicit Locked/Editable toggle (Task 4)
                html.Div([
                    html.Button(
                        "Locked",
                        id="mode-frozen",
                        className=f_cls,
                        style={"marginRight": "4px"},
                    ),
                    html.Button(
                        "Editable",
                        id="mode-editable",
                        className=e_cls,
                    ),
                ], style={"display": "flex", "gap": "4px", "marginTop": "8px"}),
                html.Div(id="routing-preset-status",
                         className="text-muted", style={"fontSize": "11px", "marginTop": "6px"}),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Threshold sliders
        html.Div([
            html.Div([
                html.Span("Routing Thresholds", style={"flex": "1"}),
                html.Span(id="thresh-unsaved-badge",
                          style={"fontSize": "10px", "color": "#E67E22",
                                 "fontWeight": "600", "display": "none"}),
            ], className="card-header"),
            html.Div([
                # Range slider groups (compact 2-column layout)
                html.Div([
                    html.Div("\u9608\u503c\u533a\u95f4 (Closed Interval)",
                             className="section-header"),
                    html.Div("\u62d6\u62fd\u624b\u67c4\u8c03\u6574 \u00b7 \u4e24\u4e2a\u6307\u6807\u4e00\u884c\u663e\u793a \u00b7 \u503c\u5728 slider \u4e0a\u53f3\u4fa7 tooltip",
                             className="section-subheader"),
                    html.Div([
                        # 2-cell rows first, then the lone trailing single-cell row
                        _build_compact_range_row(
                            _field_by_name(left),
                            _field_by_name(right) if right else None,
                        )
                        for left, right in RANGE_ROW_GROUPS
                    ], id="routing-config-ranges", className="ranges-container"),
                ], className="config-section"),
                # Apply button + status
                html.Div([
                    html.Button("✓ Apply Thresholds", id="btn-apply-thresholds",
                                className="btn btn-primary",
                                style={"marginTop": "12px", "width": "100%",
                                       "minHeight": "32px", "fontWeight": "600"}),
                    html.Div(id="thresh-apply-status",
                             style={"fontSize": "11px", "marginTop": "6px"}),
                ]),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Golden / Batch regex
        html.Div([
            html.Div("Net Selection (Regex)", className="card-header"),
            html.Div([
                # Loaded-nets status — bridges the gap with the Layout View tab
                html.Div(id="loaded-nets-status", children=_loaded_nets_status()),

                # Golden regex
                html.Div([
                    html.Label("Golden Net Regex", className="form-label"),
                    dcc.Input(id="golden-regex", type="text",
                              value=routing_state.golden_regex,
                              placeholder="e.g. ^WL_0$ or ^WL.*$",
                              className="input-field"),
                    html.Div(id="golden-regex-preview", children=_regex_match_preview(
                        routing_state.golden_regex, "Golden"
                    )),
                ], className="form-group", style={"marginBottom": "12px"}),

                # Batch regex
                html.Div([
                    html.Label("Batch Net Regex", className="form-label"),
                    dcc.Input(id="batch-regex", type="text",
                              value=routing_state.batch_regex,
                              placeholder="e.g. ^WL_.*$ or ^BL.*$",
                              className="input-field"),
                    html.Div(id="batch-regex-preview", children=_regex_match_preview(
                        routing_state.batch_regex, "Batch"
                    )),
                ], className="form-group", style={"marginBottom": "12px"}),

                # Quick-fill buttons — eliminate the empty-regex dead-end.
                # We deliberately do NOT set `disabled=` here: Dash does not
                # re-render the layout when state changes, so a captured-at-
                # construction `disabled=not first_net` would be frozen forever.
                # The callbacks themselves handle the no-nets case.
                html.Div([
                    html.Button(
                        "Use first net as golden",
                        id="btn-fill-golden",
                        className="btn btn-secondary btn-sm",
                        style={"flex": "1", "marginRight": "6px"},
                        title=(f"Set golden to {first_net!r}" if first_net
                               else "No nets loaded — upload on Layout View first"),
                    ),
                    html.Button(
                        "Use all loaded nets (batch)",
                        id="btn-fill-batch",
                        className="btn btn-secondary btn-sm",
                        style={"flex": "1"},
                        title=("Set batch to match all loaded nets" if nets
                               else "No nets loaded — upload on Layout View first"),
                    ),
                ], className="btn-group", style={"display": "flex",
                                                  "marginBottom": "12px"}),

                html.Button("Run Routing Review", id="btn-run-routing-review",
                            className="btn btn-primary btn-block",
                            title=("Run on currently-matched batch nets" if nets
                                   else "Load nets on Layout View first")),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Status
        html.Div(id="routing-config-status"),
    ], style={"padding": "16px"})


def register_routing_config_callbacks(app):
    """Register all callbacks for the routing Configuration tab."""
    from dash import Input, Output, State, no_update
    from dash import ctx as dash_ctx


    # --- 1. Regex preview / loaded-nets status (cheap, no thresh updates).
    #         Note: routing-config-status is owned exclusively by the single
    #         _routing_config_ui callback (and the secondary fill/sync callbacks
    #         that use allow_duplicate=True). Adding a 4th primary writer would
    #         trigger Dash's "Output N is already in use" error at app start. ---
    @app.callback(
        [Output("golden-regex-preview", "children"),
         Output("batch-regex-preview", "children"),
         Output("loaded-nets-status", "children")],
        [Input("golden-regex", "value"),
         Input("batch-regex", "value"),
         Input("tabs", "value"),
         Input("nets-meta-store", "data")],
    )
    def _refresh_previews(golden_re, batch_re, tab, _nets_meta):
        # Task 5 Step 1: tab listener in preview callback.
        # Only run when this tab is visible.
        if tab != "tab-routing-config":
            return no_update, no_update, no_update
        return (
            _regex_match_preview(golden_re or "", "Golden"),
            _regex_match_preview(batch_re or "", "Batch"),
            _loaded_nets_status(),
        )

    # --- 1b. Tab switch + preset + thresh + mode + apply handling are now
    #         unified in a single _routing_config_ui callback further down
    #         (Task 5: eliminates 4 overlapping callbacks with allow_duplicate=True).

    # --- 2. Quick-fill buttons (each does everything: set regex + run review +
    #         navigate to the Routing Review tab). One click, one result. ---
    @app.callback(
        [Output("golden-regex", "value", allow_duplicate=True),
         Output("tabs", "value", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)],
        Input("btn-fill-golden", "n_clicks"),
        prevent_initial_call=True,
    )
    def _fill_golden(_n):
        nets = sorted(app_state.nets_data.keys())
        if not nets:
            raise dash_ctx.PreventUpdate
        # Anchor the regex on the first loaded net for predictability
        first = re.escape(nets[0])
        routing_state.golden_regex = f"^{first}$"
        status = _run_and_status()
        return routing_state.golden_regex, "tab-routing-review", status

    @app.callback(
        [Output("batch-regex", "value", allow_duplicate=True),
         Output("tabs", "value", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)],
        Input("btn-fill-batch", "n_clicks"),
        prevent_initial_call=True,
    )
    def _fill_batch(_n):
        if not app_state.nets_data:
            raise dash_ctx.PreventUpdate
        # Use case-insensitive prefix common to the first net so it's a useful
        # starting point. Fall back to ".*" if we can't derive anything.
        first = sorted(app_state.nets_data.keys())[0]
        # Strip a trailing _<digits> from the first net to find a class prefix
        m = re.match(r"^(.+?)(?:_\d+)?$", first)
        prefix = re.escape(m.group(1)) if m else re.escape(first)
        routing_state.batch_regex = f"^{prefix}.*$"
        status = _run_and_status()
        return routing_state.batch_regex, "tab-routing-review", status

    # --- "Run Routing Review" button handling moved to app/routing_review.py
    #     (single callback owns both: run + tab navigation + result rendering). ---

    # --- 4. Mirror regex inputs into routing_state so _run_routing_review()
    #         sees the latest values (the quick-fill buttons above also set
    #         these directly, so this is just for manually-typed edits). ---
    @app.callback(
        Output("routing-config-status", "children", allow_duplicate=True),
        [Input("golden-regex", "value"),
         Input("batch-regex", "value")],
        prevent_initial_call=True,
    )
    def _sync_regex_state(golden_re, batch_re):
        routing_state.golden_regex = golden_re or ""
        routing_state.batch_regex = batch_re or ""
        # Don't touch routing-config-status here — the quick-fill and
        # run-review callbacks own it. no_update avoids a race that would
        # otherwise blank the run status on quick-fill clicks.
        return no_update

    # (Preset switch + thresh input handling moved to _routing_config_ui.)

    # (Apply Thresholds button handling moved to _routing_config_ui.)

    # --- 6. Unified single callback for the entire Routing Config tab.
    #         Compact 2-column redesign: 14 Outputs total (mode/status + 7 sliders).
    #         Replaces the 4 overlapping callbacks (_rehydrate_on_tab,
    #         update_routing_config, _apply_thresholds, _switch_mode) which all
    #         wrote to the same 21 Outputs and required `allow_duplicate=True`.
    #         This single callback owns ALL 14 Outputs and uses ctx.triggered
    #         to dispatch state mutations via _dispatch_action + render via
    #         _render_state. NO allow_duplicate=True anywhere. ---
    n = len(RANGE_FIELDS)
    slider_outputs = [Output(f"slider-{f['name']}", "value") for f in RANGE_FIELDS]
    slider_inputs = [Input(f"slider-{f['name']}", "value") for f in RANGE_FIELDS]
    slider_states = [State(f"slider-{f['name']}", "value") for f in RANGE_FIELDS]

    @app.callback(
        [Output("mode-frozen", "className"),
         Output("mode-editable", "className"),
         Output("routing-preset-status", "children"),
         Output("routing-config-status", "children"),
         Output("thresh-unsaved-badge", "children"),
         Output("thresh-apply-status", "children"),
         Output("routing-preset", "value")]
        + slider_outputs,
        [Input("routing-preset", "value"),
         Input("mode-frozen", "n_clicks"),
         Input("mode-editable", "n_clicks"),
         Input("btn-apply-thresholds", "n_clicks"),
         Input("tabs", "value")]
        + slider_inputs,
        slider_states,
        prevent_initial_call=False,
    )
    def _routing_config_ui(
        preset_value, _f_clicks, _e_clicks, _apply_clicks, tab,
        *input_args,
    ):
        """Single state-driven callback for the entire Routing Config tab.

        - Reads `ctx.triggered` to identify the action
        - Mutates `routing_state` (via _dispatch_action)
        - Projects state to 14 UI outputs (via _render_state)

        NO allow_duplicate=True anywhere. This is the ONLY callback that
        writes to these 14 Outputs.

        IMPORTANT — slider-drag isolation:
        When the trigger is one of the 7 RangeSliders, we MUST NOT write
        back to any slider output. `_render_state()` reads its slider values
        from `routing_state.thresholds` (which still holds the pre-Apply
        state), so writing them out would snap the dragged handle back to
        its pre-drag value. Using `no_update` for slider outputs preserves
        the user's in-flight drag while still updating mode buttons and
        the "Unsaved Changes" badge (via the existing diff-vs-state logic
        in `_render_state()`).

        IMPORTANT — slider value format:
        Each RangeSlider exposes its `value` as a `[low, high]` list, NOT
        two separate scalar inputs (the compact 2-column redesign removed
        the legacy low/high text badges). We therefore project `*input_args`
        into a list of 7 `[low, high]` pairs and pass that to all helpers.
        """
        from dash import callback_context as _ctx
        from dash.exceptions import PreventUpdate as _PreventUpdate
        from dash import no_update as _no_update

        n = len(RANGE_FIELDS)
        # `*input_args` holds:
        #   - the n slider Inputs (each [low, high] pair), then
        #   - the n slider States (each [low, high] pair)
        # For our purposes the two are the same value (Inputs shadow States),
        # so we only need to extract the first n items. Each item is itself
        # a `[low, high]` list — DO NOT flatten it.
        if len(input_args) < n:
            range_pairs = [None] * n
        else:
            range_pairs = list(input_args[:n])

        if not _ctx.triggered:
            return _render_state(range_pairs)

        trigger_id = _ctx.triggered[0]["prop_id"]
        trigger_value = _ctx.triggered[0]["value"]

        if trigger_id == "tabs.value":
            if trigger_value != "tab-routing-config":
                raise _PreventUpdate
            return _compute_rehydrate_outputs()

        # Slider drags: preserve the user's drag. Do NOT write back to any
        # slider output (that would reset the dragged value). The mode
        # buttons + unsaved badge still update via _render_state().
        if trigger_id and trigger_id.startswith("slider-") and trigger_id.endswith(".value"):
            rendered = list(_render_state(range_pairs))
            # Slider outputs occupy indices 7..13 (7 mode/status + 7 slider pairs).
            for i in range(n):
                rendered[7 + i] = _no_update
            return tuple(rendered)

        _dispatch_action(trigger_id, trigger_value, range_pairs)
        return _render_state(range_pairs)

    # --- 7. Logic-compact + cell className updates per field.
    #         Slider value drives the math-notation annotation and the
    #         is-invalid / is-warning class on the metric cell container
    #         and the logic-compact row.
    #         Pure helpers _compute_constraint_status and _build_logic_compact_content
    #         keep this callback thin and fully testable.
    for field in RANGE_FIELDS:
        _name = field["name"]
        _slider_id = f"slider-{_name}"
        _logic_id = f"logic-{_name}"
        _cell_id = f"cell-{_name}"
        _s_min = field["slider_min"]
        _s_max = field["slider_max"]
        _fmt = field["fmt"]

        @app.callback(
            [Output(_logic_id, "children"),
             Output(_logic_id, "className"),
             Output(_cell_id, "className")],
            Input(_slider_id, "value"),
            prevent_initial_call=False,
        )
        def _update_logic_and_cell(_value, _name=_name, _s_min=_s_min,
                                   _s_max=_s_max, _fmt=_fmt):
            from dash.exceptions import PreventUpdate
            if _value is None or len(_value) != 2:
                raise PreventUpdate
            low, high = _value[0], _value[1]
            status = _compute_constraint_status(low, high, _s_min, _s_max)
            logic_class = "logic-compact" if status == "valid" else f"logic-compact is-{status}"
            cell_class = "metric-cell" if status == "valid" else f"metric-cell is-{status}"
            return (
                _build_logic_compact_content(low, high, _fmt, status),
                logic_class,
                cell_class,
            )
