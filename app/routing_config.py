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
    thresh_values: tuple,
    trigger: Optional[str],
) -> tuple:
    """Testable core logic extracted from the large update callback.

    Returns the tuple of output values in the same order as the callback
    (so tests can assert on classes, statuses, values, disabled).
    Side effects on routing_state are performed for preset/apply-like paths
    (mirrors production). Callers in tests should reset state.
    """
    n_fields = len(THRESHOLD_FIELDS)
    # Centralized reads (Task 7 Step 1)
    is_frozen = routing_state.is_frozen
    frozen = is_frozen  # Locked when True (matches button)
    thresholds = routing_state.get_thresholds()
    dis_list = _disabled_list(frozen, n_fields)
    f_cls, e_cls = _mode_button_classes(frozen)

    # Preset switch path
    if trigger == "routing-preset" and preset:
        if preset == routing_state.current_preset:
            # no-op guard (see improved revert logic)
            # For direct test call, we simulate by returning a sentinel.
            # Real cb raises PreventUpdate; here we raise for consistency in mocks.
            from dash.exceptions import PreventUpdate
            raise PreventUpdate

        if not frozen:
            curr_p = routing_state.current_preset
            curr_thr = thresholds  # from centralized get_thresholds() above
            curr_vals = [getattr(curr_thr, name) for name, *_ in THRESHOLD_FIELDS]
            warn = "Edit Mode: Preset switch Blocked (unsaved changes). Please click Apply or switch to Locked first."
            dis_ed = _disabled_list(False, n_fields)
            f_ed, e_ed = _mode_button_classes(False)
            return tuple([
                f_ed, e_ed,
                f"Loaded: {curr_p}",
                warn,
                html.Span("● unsaved changes", style={
                    "fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
                "",
                curr_p,
            ] + curr_vals + dis_ed)

        # Locked (frozen) load
        try:
            from config.routing_thresholds import _BUILTIN_PRESETS
            if preset in _BUILTIN_PRESETS and preset not in list_yaml_presets():
                t = RoutingThresholds.for_preset(preset)
            else:
                from config.preset_loader import load_preset_yaml as _load  # local alias
                t = _load(preset)
            routing_state.current_preset = preset
            # Base preset load (Locked/frozen path): direct set to the backing preset field.
            # Value reads always go through get_thresholds() which is authoritative on is_frozen.
            routing_state.thresholds = t
            routing_state.set_frozen_mode(True)  # ensures is_frozen (Locked); custom draft preserved by set_frozen_mode but ignored by get while Locked
            status = f"Loaded preset: {preset}"
            thresh_outputs = [getattr(t, name) for name, *_ in THRESHOLD_FIELDS]
            dis_f = _disabled_list(True, n_fields)
            f_f, e_f = _mode_button_classes(True)
            return tuple([f_f, e_f, status, "", html.Span("", style={"display": "none"}), "", preset] + thresh_outputs + dis_f)
        except Exception as e:
            curr_vals = list(thresh_values) if thresh_values else [getattr(routing_state.get_thresholds(), name) for name, *_ in THRESHOLD_FIELDS]
            return tuple([f_cls, e_cls, f"Error: {e}", "", html.Span("", style={"display": "none"}), "", routing_state.current_preset] + curr_vals + dis_list)

    # Manual thresh edit path (no side effect on state)
    # Centralized threshold read via get_thresholds() (Task 7 Step 1)
    current = routing_state.get_thresholds()
    current_vals = [getattr(current, name) for name, *_ in THRESHOLD_FIELDS]

    # Task 5 Step 3: guard red/invalid + unsaved logic with "user_modified" check
    # against last-known-good (the authoritative current values from state).
    # This prevents showing red font or "unsaved" on initial load / re-sync
    # of a perfectly valid preset. Only treat as a modifying user action when an
    # input value actually differs from the last good value.
    user_modified = False
    for i, (name, *_) in enumerate(THRESHOLD_FIELDS):
        v = thresh_values[i] if i < len(thresh_values) else None
        if v is not None:
            try:
                if abs(float(v) - float(current_vals[i])) > 1e-9:
                    user_modified = True
                    break
            except Exception:
                user_modified = True
                break

    if not user_modified:
        # Not a real edit — e.g. values just re-populated after preset load or
        # tab re-hydration. Emit clean state, no unsaved badge, no red error.
        from dash import no_update as _no_update
        return tuple([
            f_cls, e_cls,
            f"Loaded: {routing_state.current_preset}",
            "",
            html.Span("", style={"display": "none"}),
            "",
            _no_update,
        ] + current_vals + dis_list)

    # Real user modification path (Task 6 cleanup): show unsaved cues ONLY.
    # Do NOT revert value on keystroke. Intermediate/partial input kept via
    # no_update. Full validation only on Apply (see _validate_apply + main cb).
    # Browser-native red avoided by wide min/max in THRESHOLD_FIELDS (updated in Step 3).
    dis_editable = _disabled_list(False, n_fields)
    from dash import no_update as _no_update
    # Return no_update for the 7 thresh value outputs so live typing is not
    # overwritten (main production callback does equivalent suppression now).
    thresh_value_slots = [_no_update] * n_fields
    return tuple([
        f_cls, e_cls,
        f"Loaded: {routing_state.current_preset}",
        "",
        html.Span("● unsaved changes", style={
            "fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
        html.Span("Thresholds modified — click Apply to save.",
                  style={"fontSize": "10px", "color": "#E67E22"}),
        _no_update,
    ] + thresh_value_slots + dis_editable)

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
    {"name": "h_ratio",      "label": "H Ratio",         "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01,  "fmt": "{:.2f}"},
    {"name": "v_ratio",      "label": "V Ratio",         "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01,  "fmt": "{:.2f}"},
    {"name": "r_ohm",        "label": "R (\u03a9)",      "slider_min": 0.0,    "slider_max": 10000.0, "step": 0.1,   "fmt": "{:.1f}"},
    {"name": "c_ff",         "label": "C (fF)",          "slider_min": 0.0,    "slider_max": 100000.0,"step": 1,     "fmt": "{:.1f}"},
    {"name": "tau_ps",       "label": "\u03c4 (ps)",     "slider_min": 0.0,    "slider_max": 1000.0,  "step": 0.1,   "fmt": "{:.1f}"},
    {"name": "via_coverage", "label": "Via Coverage",    "slider_min": 0.0,    "slider_max": 1.0,     "step": 0.01,  "fmt": "{:.2f}"},
    {"name": "similarity",   "label": "Similarity",      "slider_min": 0.0,    "slider_max": 100.0,   "step": 1,     "fmt": "{:.0f}"},
] # noqa: E501


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


def _validate_apply(thresh_values: tuple) -> tuple[Optional[RoutingThresholds], Optional[str]]:
    """Validate 7 threshold input values for Apply.

    Returns:
        (valid_thresholds, None) on success
        (None, error_message) on failure

    A `None` value in thresh_values means "use the current state value" (the
    input was empty). It does NOT mean invalid.

    Task 5 Step 3 + Task 6: Guard with user_modified check against last-known-good.
    Full red/invalid only surfaces for *real differing* bad values on Apply.
    Live keystrokes never call this (no revert); only Apply path does.
    """
    # Centralized threshold read via get_thresholds() (Task 7 Step 1)
    current = routing_state.get_thresholds()
    current_vals = [getattr(current, name) for name, *_ in THRESHOLD_FIELDS]
    tentative_dict = current.to_dict()

    user_modified = False
    for i, (name, *_) in enumerate(THRESHOLD_FIELDS):
        val = thresh_values[i] if i < len(thresh_values) else None
        if val is not None:
            try:
                if abs(float(val) - float(current_vals[i])) > 1e-9:
                    user_modified = True
            except Exception:
                user_modified = True
            tentative_dict[name] = val

    if not user_modified:
        # Values match last known good (or were all None). This is not a
        # modifying action that can be the "cause of failure".
        # Return the known-good thresholds; never surface red for this.
        return current, None

    try:
        tentative = RoutingThresholds.from_dict(tentative_dict)
        tentative.validate()
    except Exception as e:
        return None, str(e)
    return tentative, None


def _apply_thresholds(thresh_values: tuple) -> None:
    """Apply the (possibly edited) threshold values from the UI inputs.

    Task 5 Step 2: Always update state on successful Apply and clear badges.
    Sets is_frozen based on mode: after Apply we adopt the values as custom
    and switch to (or remain in) editable mode (is_frozen=False).
    """
    valid, err = _validate_apply(thresh_values)
    if valid is None:
        routing_state.last_error = err
    else:
        # Commit the values and set is_frozen=False (Editable / applied mode)
        routing_state.set_custom(valid)
        routing_state.last_error = None
    # Apply represents a config change — clear prior review status so it
    # does not linger, and ensure unsaved/apply badges will be cleared on
    # the subsequent render (since authoritative now matches applied values).
    routing_state.last_status = ""


def _render_state(thresh_input_values: list) -> tuple:
    """Project routing_state to 21 UI outputs.

    Output tuple order (matches the single callback's Output list):
      [0]  mode-frozen className
      [1]  mode-editable className
      [2]  routing-preset-status children
      [3]  routing-config-status children
      [4]  thresh-unsaved-badge children
      [5]  thresh-apply-status children
      [6]  routing-preset value
      [7..13] 7 thresh-{name} values
      [14..20] 7 thresh-{name} disabled flags

    `thresh_input_values` is the list of 7 values currently in the inputs;
    used to detect unsaved changes.
    """
    # Centralized threshold reads (Task 7 Step 1)
    thresholds = routing_state.get_thresholds()
    thr = thresholds
    vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
    is_frozen = routing_state.is_frozen
    frozen = is_frozen
    f_cls, e_cls = _mode_button_classes(frozen)
    dis_list = _disabled_list(frozen, len(THRESHOLD_FIELDS))

    # detect unsaved changes (only meaningful in editable mode)
    # Task 5/6: tolerant diff check vs last-known-good. Note: during live
    # keystroke the caller suppresses value outputs, but diff detection
    # (using passed thresh_input_values) still correctly decides badge/status.
    def _vals_differ(a, b):
        try:
            return abs(float(a) - float(b)) > 1e-9
        except Exception:
            return a != b
    has_unsaved = False
    if not frozen:  # Editable mode
        for iv, sv in zip(thresh_input_values, vals):
            if _vals_differ(iv, sv):
                has_unsaved = True
                break

    source = routing_state.get_threshold_source()
    preset_status = html.Span(source, style={"color": "#888", "fontSize": "11px"})

    if routing_state.last_error:
        err = routing_state.last_error
        if err and ("Blocked" in err or "Preset switch" in err or "Edit Mode" in err):
            # Use orange (like unsaved) for preset block warning (step 6 confirmation)
            config_status = html.Span(
                err,
                style={"fontSize": "11px", "color": "#E67E22"},
            )
        else:
            config_status = html.Span(
                f"Error: {err}",
                style={"fontSize": "11px", "color": "#C0392B"},
            )
    elif routing_state.last_status:
        config_status = html.Span(
            routing_state.last_status,
            style={"fontSize": "11px", "color": "#2C7A2C"},
        )
    else:
        config_status = ""

    if has_unsaved:
        unsaved_badge = html.Span(
            "Unsaved Changes",
            style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"},
        )
        apply_status = html.Span(
            "Thresholds modified - click Apply to save.",
            style={"fontSize": "11px", "color": "#E67E22"},
        )
    else:
        unsaved_badge = html.Span("", style={"display": "none"})
        apply_status = ""

    return tuple([
        f_cls, e_cls,
        preset_status,
        config_status,
        unsaved_badge,
        apply_status,
        routing_state.current_preset,
    ] + vals + dis_list)


def _dispatch_action(trigger_id, trigger_value, thresh_values) -> None:
    """Mutate routing_state based on which input triggered the callback.

    trigger_id: e.g. "routing-preset.value", "mode-frozen.n_clicks",
                "btn-apply-thresholds.n_clicks", "thresh-max_tau_ps.value",
                "tabs.value", or None for initial render.
    trigger_value: the value associated with the trigger (preset name,
                   n_clicks count, thresh input value, tab id).
    thresh_values: tuple of 7 current thresh input values (only meaningful
                   for the Apply trigger).
    """
    if trigger_id is None:
        # Initial render: nothing to do; state is already set.
        return

    if trigger_id == "routing-preset.value":
        new_preset = trigger_value
        # Centralized is_frozen read (Task 7); True == Locked mode
        if routing_state.is_frozen:
            routing_state.current_preset = new_preset
            routing_state.thresholds = RoutingThresholds.for_preset(new_preset)
            routing_state.custom_thresholds = None  # preset switch in frozen discards prior draft
            routing_state.last_error = None
            routing_state.last_status = ""
        else:
            # Editable: block with warning (simple status + prevent by not mutating);
            # render will bounce the preset value and surface the message.
            if new_preset and new_preset != routing_state.current_preset:
                routing_state.last_error = "Edit Mode: Preset switch Blocked (unsaved changes). Please click Apply or switch to Locked first."
                routing_state.last_status = ""
        return

    if trigger_id == "mode-frozen.n_clicks":
        routing_state.set_frozen_mode(True)  # Locked: preserves any custom draft (get_thresholds respects is_frozen)
        routing_state.last_error = None
        routing_state.last_status = ""
        return

    if trigger_id == "mode-editable.n_clicks":
        routing_state.set_frozen_mode(False)  # switch to Editable
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        routing_state.last_error = None
        routing_state.last_status = ""
        return

    if trigger_id == "btn-apply-thresholds.n_clicks":
        # Task 5 Step 2: delegate to _apply_thresholds (ensures state update +
        # is_frozen set based on applied/editable mode + badges cleared).
        _apply_thresholds(thresh_values)
        return

    if trigger_id and trigger_id.startswith("thresh-") and trigger_id.endswith(".value"):
        # User typing in a thresh input: no state mutation.
        # _render_state will detect the diff and show the unsaved badge.
        return

    if trigger_id == "tabs.value":
        # Tab switch: nothing to mutate; just re-render.
        return


def _compute_rehydrate_outputs():
    """Return the full tuple of outputs to re-populate Routing Config controls from state.

    Used by the tab-switch rehydration callback (Task 5). Order matches the large
    output list used by preset/mode/apply callbacks:
      [mode-frozen, mode-editable, preset-status, config-status,
       unsaved-badge, apply-status, preset-value]
      + 7 thresh values + 7 disabled.
    Clears transient badges on re-entry for clean re-hydration while restoring
    authoritative values + mode + disabled from routing_state.
    """
    # Centralized threshold reads (Task 7 Step 1)
    thresholds = routing_state.get_thresholds()
    thr = thresholds
    vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
    is_frozen = routing_state.is_frozen
    frozen = is_frozen
    f_cls, e_cls = _mode_button_classes(frozen)
    dis_list = _disabled_list(frozen, len(THRESHOLD_FIELDS))
    # On tab re-activation: reflect current preset/mode/values, clear transient messages.
    return tuple([
        f_cls, e_cls,
        f"Loaded: {routing_state.current_preset}",
        "",
        html.Span("", style={"display": "none"}),
        "",
        routing_state.current_preset,
    ] + vals + dis_list)


def get_threshold_input_ids() -> List[str]:
    """Return the dcc.Input IDs for all threshold fields (used in callbacks)."""
    return [f"thresh-{name}" for name, *_ in THRESHOLD_FIELDS]


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
                # Grid of threshold inputs
                html.Div([
                    html.Div([
                        html.Label(label, className="form-label"),
                        dcc.Input(
                            id=f"thresh-{name}",
                            type="number",
                            value=getattr(thr, name),
                            min=mn, max=mx, step=st,
                            disabled=is_frozen,  # centralized read above
                            className="input-field",
                        ),
                    ], className="form-group")
                    for (name, label, mn, mx, st) in THRESHOLD_FIELDS
                ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px"}),
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
    #         This single callback owns ALL 21 Outputs and uses ctx.triggered
    #         to dispatch state mutations via _dispatch_action + render via
    #         _render_state. NO allow_duplicate=True anywhere. ---
    @app.callback(
        [Output("mode-frozen", "className"),
         Output("mode-editable", "className"),
         Output("routing-preset-status", "children"),
         Output("routing-config-status", "children"),
         Output("thresh-unsaved-badge", "children"),
         Output("thresh-apply-status", "children"),
         Output("routing-preset", "value")]
        + [Output(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS]
        + [Output(f"thresh-{name}", "disabled") for name, *_ in THRESHOLD_FIELDS],
        [Input("routing-preset", "value"),
         Input("mode-frozen", "n_clicks"),
         Input("mode-editable", "n_clicks"),
         Input("btn-apply-thresholds", "n_clicks"),
         Input("tabs", "value")]
        + [Input(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        [State(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        prevent_initial_call=False,
    )
    def _routing_config_ui(
        preset_value, _f_clicks, _e_clicks, _apply_clicks, tab,
        *thresh_inputs_and_state
    ):
        """Single state-driven callback for the entire Routing Config tab.

        - Reads `ctx.triggered` to identify the action
        - Mutates `routing_state` (via _dispatch_action)
        - Projects state to 21 UI outputs (via _render_state)

        NO allow_duplicate=True anywhere. This is the ONLY callback that
        writes to these 21 Outputs.
        """
        from dash import callback_context as _ctx
        from dash.exceptions import PreventUpdate as _PreventUpdate

        # The 7 thresh inputs appear as both Inputs (for "user typed" detection)
        # and State (for Apply action). Since Dash passes them in declaration
        # order, the LAST 7 args (after the 5 head inputs) are the State copies.
        thresh_state = thresh_inputs_and_state[-len(THRESHOLD_FIELDS):]
        # (thresh_inputs slice not needed; values for typing path come via State+trigger)

        if not _ctx.triggered:
            # Initial render: dispatch_action is a no-op, just render.
            return _render_state(list(thresh_state))

        trigger_id = _ctx.triggered[0]["prop_id"]
        trigger_value = _ctx.triggered[0]["value"]

        # Tab switch: only act when switching TO routing-config
        # Task 5 Step 1: Strengthen the tab listener callback.
        # When tab == "tab-routing-config", output to all thresh- inputs
        # the current values from routing_state.get_thresholds(),
        # output disabled state based on is_frozen,
        # and output current mode UI classes. Use clean rehydrate
        # to clear transient badges on re-entry.
        if trigger_id == "tabs.value":
            if trigger_value != "tab-routing-config":
                raise _PreventUpdate
            # Re-hydrate directly from authoritative state (ignore stale browser State values)
            return _compute_rehydrate_outputs()

        # Dispatch state mutation
        _dispatch_action(trigger_id, trigger_value, tuple(thresh_state))

        # Project state to UI
        rendered = _render_state(list(thresh_state))

        # Task 6 Step 2: Remove aggressive revert on every keystroke for valid ranges.
        # When the user is typing directly in a thresh input, return no_update for the
        # 7 value slots. This lets the browser <input> retain the user's in-progress
        # text (including valid edits and intermediate states like '0.' or '12').
        # Previously _render_state always emitted authoritative vals, forcing revert.
        # Full validate + possible error (red) or commit only happens on Apply.
        # (Unsaved badge and other UI still update using the incoming thresh_state.)
        if trigger_id and trigger_id.startswith("thresh-") and trigger_id.endswith(".value"):
            from dash import no_update as _no_update
            outs = list(rendered)
            n = len(THRESHOLD_FIELDS)
            for i in range(n):
                outs[7 + i] = _no_update
            return tuple(outs)
        return rendered
