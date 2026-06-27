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
    range_values,
    trigger: Optional[str],
) -> tuple:
    """Testable core logic for preset/apply handling.

    `range_values` is a 14-tuple of (low_0, high_0, ..., low_6, high_6).
    Returns the 41-element output tuple.
    """
    n = len(RANGE_FIELDS)
    is_frozen = routing_state.is_frozen
    thresholds = routing_state.get_thresholds()
    f_cls, e_cls = _mode_button_classes(is_frozen)
    dis_list = [is_frozen] * (2 * n)
    slider_vals = [[getattr(thresholds, fld["name"]).low,
                    getattr(thresholds, fld["name"]).high] for fld in RANGE_FIELDS]
    low_vals = [getattr(thresholds, fld["name"]).low for fld in RANGE_FIELDS]
    high_vals = [getattr(thresholds, fld["name"]).high for fld in RANGE_FIELDS]

    if trigger == "routing-preset" and preset:
        if preset == routing_state.current_preset:
            from dash.exceptions import PreventUpdate
            raise PreventUpdate
        if not is_frozen:
            curr_p = routing_state.current_preset
            warn = ("Edit Mode: Preset switch Blocked (unsaved changes). "
                    "Please click Apply or switch to Locked first.")
            dis_ed = [False] * (2 * n)
            f_ed, e_ed = _mode_button_classes(False)
            return tuple([f_ed, e_ed, f"Loaded: {curr_p}", warn,
                          html.Span("\u25cf unsaved changes",
                                    style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
                          "", curr_p]
                         + slider_vals + low_vals + high_vals + dis_ed)
        try:
            t = RoutingThresholds.for_preset(preset)
            routing_state.current_preset = preset
            routing_state.thresholds = t
            routing_state.set_frozen_mode(True)
            status = f"Loaded preset: {preset}"
            new_slider = [[getattr(t, fld["name"]).low,
                           getattr(t, fld["name"]).high] for fld in RANGE_FIELDS]
            new_low = [getattr(t, fld["name"]).low for fld in RANGE_FIELDS]
            new_high = [getattr(t, fld["name"]).high for fld in RANGE_FIELDS]
            dis_f = [True] * (2 * n)
            f_f, e_f = _mode_button_classes(True)
            return tuple([f_f, e_f, status, "", html.Span("", style={"display": "none"}), "", preset]
                         + new_slider + new_low + new_high + dis_f)
        except Exception as e:
            return tuple([f_cls, e_cls, f"Error: {e}", "", html.Span("", style={"display": "none"}), "", routing_state.current_preset]
                         + slider_vals + low_vals + high_vals + dis_list)

    return _render_state(list(range_values))

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
    """Placeholder for Task 5 — return minimal valid content."""
    from dash import html
    if status != "valid":
        return [html.Span("placeholder")]
    return [
        html.Span("\u5408\u89c4: "),
        html.Code(f"{fmt.format(low)} \u2264 X \u2264 {fmt.format(high)}"),
        html.Span(" \u27fa ", className="ic"),
        html.Span("\u533a\u95f4\u5bbd\u5ea6 "),
        html.Code(fmt.format(high - low)),
    ]


def _build_range_input_group(field):
    """Build a single range-setting row with Accent Strip visual style.

    Structure (each row is its own bordered card with left accent strip):
      row-header       \u2014 label + help + bounds info
      dcc.RangeSlider  \u2014 two handles, accent-gradient fill, no Dash internal marks
      tick-row         \u2014 3 spans (min, mid, max)
      badges           \u2014 two badges (Low / High), each with transparent dcc.Input overlay
      logic-row        \u2014 math notation \u5408\u89c4: low \u2264 X \u2264 high \u27fa \u533a\u95f4\u5bbd\u5ea6 w

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
        # \u2500\u2500 Row header \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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

        # \u2500\u2500 RangeSlider (no Dash marks; we render custom ticks below) \u2500\u2500
        dcc.RangeSlider(
            id=f"slider-{name}",
            min=s_min, max=s_max, step=step,
            value=[initial_low, initial_high],
            marks=None,
            tooltip={"placement": "bottom", "always_visible": False},
            allowCross=False,
            className="range-slider",
        ),

        # \u2500\u2500 Custom tick-row (3 labels: min, mid, max) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        html.Div([
            html.Span(fmt.format(s_min)),
            html.Span(fmt.format((s_min + s_max) / 2), className="mid"),
            html.Span(fmt.format(s_max)),
        ], className="tick-row"),

        # \u2500\u2500 Badges row (Low / High, each with overlay dcc.Input) \u2500\u2500\u2500\u2500\u2500
        html.Div([
            _build_badge(name, "low", "Low", initial_low, unit, s_min, s_max, step),
            _build_badge(name, "high", "High", initial_high, unit, s_min, s_max, step),
        ], className="badges"),

        # \u2500\u2500 Logic row (math notation) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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


def _sync_slider_to_input(value):
    """Slider -> Inputs: simply unpack the [low, high] list."""
    return value[0], value[1]


def _sync_input_to_slider(low, high):
    """Inputs -> Slider. Returns [low, high] or None to signal PreventUpdate."""
    from dash.exceptions import PreventUpdate
    if low is None or high is None:
        raise PreventUpdate
    if low > high:
        raise PreventUpdate
    return [low, high]


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


def _validate_apply(range_values):
    """Validate 14 (low, high) values for Apply.

    Returns:
        (valid_thresholds, None) on success
        (None, error_message) on failure
    """
    n = len(RANGE_FIELDS)
    if len(range_values) != 2 * n:
        return None, f"Expected {2 * n} values, got {len(range_values)}"

    current = routing_state.get_thresholds()
    tentative_dict = current.to_dict()

    try:
        for i, field in enumerate(RANGE_FIELDS):
            name = field["name"]
            low = range_values[2 * i]
            high = range_values[2 * i + 1]
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


def _apply_thresholds(range_values):
    valid, err = _validate_apply(range_values)
    if valid is None:
        routing_state.last_error = err
    else:
        routing_state.set_custom(valid)
        routing_state.last_error = None
    routing_state.last_status = ""


def _render_state(range_input_values):
    """Project routing_state to UI outputs (41-element tuple).

    Output tuple order:
      [0]   mode-frozen className
      [1]   mode-editable className
      [2]   routing-preset-status children
      [3]   routing-config-status children
      [4]   thresh-unsaved-badge children
      [5]   thresh-apply-status children
      [6]   routing-preset value
      [7..13]  7 slider-{name} values (each [low, high])
      [14..20] 7 input-{name}-low values
      [21..27] 7 input-{name}-high values
      [28..34] 7 input-{name}-low disabled
      [35..41] 7 input-{name}-high disabled
    """
    thresholds = routing_state.get_thresholds()
    is_frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(is_frozen)
    n = len(RANGE_FIELDS)
    slider_vals = [[getattr(thresholds, fld["name"]).low,
                    getattr(thresholds, fld["name"]).high] for fld in RANGE_FIELDS]
    low_vals = [getattr(thresholds, fld["name"]).low for fld in RANGE_FIELDS]
    high_vals = [getattr(thresholds, fld["name"]).high for fld in RANGE_FIELDS]
    dis_list = [is_frozen] * (2 * n)

    def _vals_differ(a, b):
        try:
            return abs(float(a) - float(b)) > 1e-9
        except Exception:
            return a != b

    has_unsaved = False
    if not is_frozen and len(range_input_values) == 2 * n:
        for i, fld in enumerate(RANGE_FIELDS):
            if _vals_differ(range_input_values[2 * i], low_vals[i]):
                has_unsaved = True
                break
            if _vals_differ(range_input_values[2 * i + 1], high_vals[i]):
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
    ] + slider_vals + low_vals + high_vals + dis_list)


def _dispatch_action(trigger_id, trigger_value, range_values):
    """Handle non-typing triggers (preset, mode, apply, tabs)."""
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
        _apply_thresholds(tuple(range_values))
        return
    if trigger_id and trigger_id.startswith("input-") and trigger_id.endswith(".value"):
        return
    if trigger_id == "tabs.value":
        return


def _compute_rehydrate_outputs():
    """Return the full 41-tuple to re-populate Routing Config controls from state.

    Used by the tab-switch rehydration callback. Order matches the large
    output list used by preset/mode/apply callbacks:
      [mode-frozen, mode-editable, preset-status, config-status,
       unsaved-badge, apply-status, preset-value]
      + 7 slider-{name} values + 7 input-{name}-low values
      + 7 input-{name}-high values + 14 disabled flags.
    Clears transient badges on re-entry for clean re-hydration while restoring
    authoritative values + mode + disabled from routing_state.
    """
    thresholds = routing_state.get_thresholds()
    is_frozen = routing_state.is_frozen
    f_cls, e_cls = _mode_button_classes(is_frozen)
    n = len(RANGE_FIELDS)
    slider_vals = [[getattr(thresholds, fld["name"]).low,
                    getattr(thresholds, fld["name"]).high] for fld in RANGE_FIELDS]
    low_vals = [getattr(thresholds, fld["name"]).low for fld in RANGE_FIELDS]
    high_vals = [getattr(thresholds, fld["name"]).high for fld in RANGE_FIELDS]
    dis_list = [is_frozen] * (2 * n)
    return tuple([
        f_cls, e_cls,
        f"Loaded: {routing_state.current_preset}",
        "",
        html.Span("", style={"display": "none"}),
        "",
        routing_state.current_preset,
    ] + slider_vals + low_vals + high_vals + dis_list)


def get_threshold_input_ids() -> List[str]:
    """Return the dcc.Input IDs for all threshold fields (used in callbacks)."""
    return [f"input-{fld['name']}-low" for fld in RANGE_FIELDS] + [f"input-{fld['name']}-high" for fld in RANGE_FIELDS]


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
                # Range slider groups (replaces legacy thresh-{name} inputs)
                html.Div([
                    _build_range_input_group(field)
                    for field in RANGE_FIELDS
                ], style={"display": "flex", "flexDirection": "column", "gap": "8px"}),
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
    #         Replaces the 4 overlapping callbacks (_rehydrate_on_tab,
    #         update_routing_config, _apply_thresholds, _switch_mode) which all
    #         wrote to the same 21 Outputs and required `allow_duplicate=True`.
    #         This single callback owns ALL 41 Outputs and uses ctx.triggered
    #         to dispatch state mutations via _dispatch_action + render via
    #         _render_state. NO allow_duplicate=True anywhere. ---
    n = len(RANGE_FIELDS)
    low_outputs = [Output(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
    high_outputs = [Output(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS]
    low_dis = [Output(f"input-{f['name']}-low", "disabled") for f in RANGE_FIELDS]
    high_dis = [Output(f"input-{f['name']}-high", "disabled") for f in RANGE_FIELDS]

    @app.callback(
        [Output("mode-frozen", "className"),
         Output("mode-editable", "className"),
         Output("routing-preset-status", "children"),
         Output("routing-config-status", "children"),
         Output("thresh-unsaved-badge", "children"),
         Output("thresh-apply-status", "children"),
         Output("routing-preset", "value")]
        + [Output(f"slider-{f['name']}", "value") for f in RANGE_FIELDS]
        + low_outputs + high_outputs + low_dis + high_dis,
        [Input("routing-preset", "value"),
         Input("mode-frozen", "n_clicks"),
         Input("mode-editable", "n_clicks"),
         Input("btn-apply-thresholds", "n_clicks"),
         Input("tabs", "value")]
        + [Input(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
        + [Input(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS],
        [State(f"input-{f['name']}-low", "value") for f in RANGE_FIELDS]
        + [State(f"input-{f['name']}-high", "value") for f in RANGE_FIELDS],
        prevent_initial_call=False,
    )
    def _routing_config_ui(
        preset_value, _f_clicks, _e_clicks, _apply_clicks, tab,
        *input_args,
    ):
        """Single state-driven callback for the entire Routing Config tab.

        - Reads `ctx.triggered` to identify the action
        - Mutates `routing_state` (via _dispatch_action)
        - Projects state to 41 UI outputs (via _render_state)

        NO allow_duplicate=True anywhere. This is the ONLY callback that
        writes to these 41 Outputs.
        """
        from dash import callback_context as _ctx
        from dash.exceptions import PreventUpdate as _PreventUpdate
        from dash import no_update as _no_update

        n = len(RANGE_FIELDS)
        # Last 2*n args are the 14 State input values: [low_0..low_6, high_0..high_6]
        range_state = list(input_args[-2 * n:])

        if not _ctx.triggered:
            return _render_state(range_state)

        trigger_id = _ctx.triggered[0]["prop_id"]
        trigger_value = _ctx.triggered[0]["value"]

        if trigger_id == "tabs.value":
            if trigger_value != "tab-routing-config":
                raise _PreventUpdate
            return _compute_rehydrate_outputs()

        _dispatch_action(trigger_id, trigger_value, tuple(range_state))
        rendered = _render_state(range_state)

        if trigger_id and trigger_id.startswith("input-") and trigger_id.endswith(".value"):
            outs = list(rendered)
            for i in range(n):
                outs[14 + i] = _no_update
                outs[21 + i] = _no_update
            return tuple(outs)
        return rendered

    # --- 7. Slider <-> Inputs bidirectional sync (range fields).
    #         For each RANGE_FIELDS entry, two pure-function callbacks:
    #           (a) slider-{name}.value        -> input-{name}-low/high.value
    #           (b) input-{name}-low/high.value -> slider-{name}.value
    #         Pure logic is in _sync_slider_to_input / _sync_input_to_slider
    #         and exercised directly by tests/test_routing_config_sync.py.
    #         prevent_initial_call=True so the sync only fires on real user
    #         interaction (avoids feedback loops on initial render).
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
