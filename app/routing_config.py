"""Routing-focused Configuration tab.

Replaces `_create_config_content()` from `app/layout.py`.
Exposes ONLY routing thresholds + preset selector + golden/batch regex — no
rule editor, no per-rule enable/disable.

Reads available nets from `app.state.app_state.nets_data` (populated by the
Layout View tab's upload callbacks). Surfacing this connection in the UI is
critical — without it, the user has no way to know what nets exist or whether
their regex matches anything.
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
    frozen = routing_state.is_frozen
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
            curr_thr = routing_state.get_thresholds()
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

        # frozen load
        try:
            from config.routing_thresholds import _BUILTIN_PRESETS
            if preset in _BUILTIN_PRESETS and preset not in list_yaml_presets():
                t = RoutingThresholds.for_preset(preset)
            else:
                from config.preset_loader import load_preset_yaml as _load  # local alias
                t = _load(preset)
            routing_state.current_preset = preset
            # Base preset load (frozen path): direct set to the backing preset field is the
            # intended design for the "strictly follow preset" mode (no custom). Value reads
            # always go through get_thresholds() which respects is_frozen.
            routing_state.thresholds = t
            routing_state.set_frozen_mode(True)  # also ensures custom_thresholds=None and _is_frozen
            status = f"Loaded preset: {preset}"
            thresh_outputs = [getattr(t, name) for name, *_ in THRESHOLD_FIELDS]
            dis_f = _disabled_list(True, n_fields)
            f_f, e_f = _mode_button_classes(True)
            return tuple([f_f, e_f, status, "", html.Span("", style={"display": "none"}), "", preset] + thresh_outputs + dis_f)
        except Exception as e:
            curr_vals = list(thresh_values) if thresh_values else [getattr(routing_state.get_thresholds(), name) for name, *_ in THRESHOLD_FIELDS]
            return tuple([f_cls, e_cls, f"Error: {e}", "", html.Span("", style={"display": "none"}), "", routing_state.current_preset] + curr_vals + dis_list)

    # Manual thresh edit path (no side effect on state)
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

    # Real user modification (Task 6): show unsaved cues ONLY.
    # Do NOT perform from_dict + validate() + red revert on every keystroke.
    # Intermediate states during typing (None, '1.', partials) must never cause
    # revert of the input. Browser-native invalid (red) from min/max is also
    # eliminated by using 0.0/1.0 in THRESHOLD_FIELDS.
    # Full validation + possible revert happens exclusively in the Apply button
    # handler (or when truly out-of-range after user commits via Apply).
    dis_editable = _disabled_list(False, n_fields)
    from dash import no_update as _no_update
    # Return no_update for the 7 thresh value outputs so the live <input type=number>
    # state in the browser is not overwritten or reverted on each keystroke.
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

THRESHOLD_FIELDS = [
    ("max_h_ratio", "Max H Ratio (WL gate)", "0.0", "1.0", "0.01"),
    ("max_v_ratio", "Max V Ratio (IO gate)", "0.0", "1.0", "0.01"),
    ("max_r_ohm", "Max Total R (Ω)", "0.1", "10000", "0.1"),
    ("max_c_ff", "Max Total C (fF)", "0.1", "100000", "1"),
    ("max_tau_ps", "Max Effective τ (ps)", "0.01", "1000", "0.1"),
    ("min_via_coverage", "Min Via Coverage", "0.0", "1.0", "0.01"),
    ("min_similarity", "Min Golden Similarity", "0", "100", "1"),
]


def _mode_button_classes(frozen: bool) -> tuple[str, str]:
    """Pure helper: return (frozen_button_class, editable_button_class).

    Used by layout builder and all callbacks that touch mode buttons.
    Reduces duplication of the ternary class logic.
    """
    if frozen:
        return "btn btn-primary btn-sm", "btn btn-secondary btn-sm"
    return "btn btn-secondary btn-sm", "btn btn-primary btn-sm"


def _disabled_list(frozen: bool, n_fields: int) -> list[bool]:
    """Pure helper: return disabled flags for threshold inputs.

    frozen=True -> all disabled; frozen=False -> all enabled.
    """
    return [frozen] * n_fields


def _validate_apply(thresh_values: tuple) -> tuple[Optional[RoutingThresholds], Optional[str]]:
    """Validate 7 threshold input values for Apply.

    Returns:
        (valid_thresholds, None) on success
        (None, error_message) on failure

    A `None` value in thresh_values means "use the current state value" (the
    input was empty). It does NOT mean invalid.
    """
    current = routing_state.get_thresholds()
    tentative_dict = current.to_dict()
    for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
        if val is not None:
            tentative_dict[name] = val
    try:
        tentative = RoutingThresholds.from_dict(tentative_dict)
        tentative.validate()
    except Exception as e:
        return None, str(e)
    return tentative, None


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
    thr = routing_state.get_thresholds()
    vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
    frozen = routing_state.is_frozen
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

    Caller is responsible for guarding against an empty `app_state.nets_data`
    (the button click callbacks do that up-front and `raise PreventUpdate`).
    """
    try:
        _run_routing_review()
        return (
            f"Reviewed {len(routing_state.batch_results)} nets, "
            f"golden={routing_state.golden_net_name or '(none)'}"
        )
    except Exception as e:
        routing_state.last_error = str(e)
        return f"Error: {e}"


def create_routing_config_tab():
    """Build the routing Configuration tab content (Dash components only)."""
    preset = routing_state.current_preset
    thr = routing_state.get_thresholds()
    f_cls, e_cls = _mode_button_classes(routing_state.is_frozen)

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
                            disabled=routing_state.is_frozen,
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


    # --- 1. Regex preview / loaded-nets status (cheap, no thresh updates) ---
    @app.callback(
        [Output("golden-regex-preview", "children"),
         Output("batch-regex-preview", "children"),
         Output("loaded-nets-status", "children"),
         Output("routing-config-status", "children")],
        [Input("golden-regex", "value"),
         Input("batch-regex", "value"),
         Input("tabs", "value"),
         Input("nets-meta-store", "data")],
    )
    def _refresh_previews(golden_re, batch_re, tab, _nets_meta):
        # Only run when this tab is visible (cheap) — otherwise no_update.
        # Strengthened tab listener pattern (Task 5): guard ensures we only
        # act for tab-routing-config (or initial None). The heavy re-hydration
        # of thresh-* values + disabled + mode UI lives in the dedicated
        # _rehydrate_on_tab callback below.
        if tab not in (None, "tab-routing-config"):
            return no_update, no_update, no_update, no_update
        return (
            _regex_match_preview(golden_re or "", "Golden"),
            _regex_match_preview(batch_re or "", "Batch"),
            _loaded_nets_status(),
            "",
        )

    # --- 1b. Tab switch re-hydration (Task 5 Step 1).
    #         When the user activates (or returns to) the Routing Config tab,
    #         re-populate all threshold inputs from the *authoritative* state
    #         (routing_state.get_thresholds()), set correct disabled flags per
    #         current is_frozen, and restore the mode button classes.
    #         This fixes "tab switch loses values" / "apply invalid" symptoms.
    @app.callback(
        [Output("mode-frozen", "className", allow_duplicate=True),
         Output("mode-editable", "className", allow_duplicate=True),
         Output("routing-preset-status", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True),
         Output("thresh-unsaved-badge", "children", allow_duplicate=True),
         Output("thresh-apply-status", "children", allow_duplicate=True),
         Output("routing-preset", "value", allow_duplicate=True)]
        + [Output(f"thresh-{name}", "value", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS]
        + [Output(f"thresh-{name}", "disabled", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS],
        Input("tabs", "value"),
        prevent_initial_call=True,
    )
    def _rehydrate_on_tab(active_tab):
        """Rehydrate the Routing Config tab when the user switches to it.

        This is the bug fix: previously, switching tabs away and back did not
        re-populate the threshold inputs from state, so Apply'd values were
        not visible on the UI after returning. We now emit all thresh values
        + disabled flags + mode classes on every tab activation.
        """
        from dash.exceptions import PreventUpdate as _PreventUpdate
        if active_tab != "tab-routing-config":
            # Don't disturb other tabs
            raise _PreventUpdate
        # Delegate to pure helper (testable, mirrors the "if tab == ..." shape in the plan).
        return _compute_rehydrate_outputs()

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

    # --- 4. Preset switch → reload thresholds immediately (presets should
    #         apply instantly — only manual threshold edits require Apply).
    #         Respects is_frozen: frozen loads immediately; editable uses simple
    #         status + revert (dropdown) to avoid losing unsaved edits.
    #         Revert improved with ctx-based no-op guard: after emitting revert
    #         value we PreventUpdate on the follow-up fire (when preset==current)
    #         to avoid duplicate status/flicker/extra triggers. Uses pure helpers.
    #         Also hooks thresh-* inputs + outputs disabled for mode support.
    #         Also hooks thresh-* inputs to prevent the preview refresh from
    #         killing thresh values. ---
    @app.callback(
        [Output("mode-frozen", "className", allow_duplicate=True),
         Output("mode-editable", "className", allow_duplicate=True),
         Output("routing-preset-status", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True),
         Output("thresh-unsaved-badge", "children", allow_duplicate=True),
         Output("thresh-apply-status", "children", allow_duplicate=True),
         Output("routing-preset", "value", allow_duplicate=True)]
        + [Output(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS]
        + [Output(f"thresh-{name}", "disabled") for name, *_ in THRESHOLD_FIELDS],
        [Input("routing-preset", "value")]
        + [Input(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        prevent_initial_call=True,
    )
    def update_routing_config(preset, *thresh_values):
        ctx = dash_ctx
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
        # Delegate to the extracted testable logic (keeps callback thin, enables direct mocked calls in tests)
        try:
            return _handle_routing_preset_or_thresh(preset, thresh_values, trigger)
        except Exception:
            # Re-raise PreventUpdate etc. as-is; other errors fall to Dash
            raise

    # --- 5. Apply Thresholds button — validates and commits to routing_state ---
    # Always updates state (custom + is_frozen) and clears badges on success (Task 5 Step 2).
    # Sets is_frozen based on the post-apply mode (editable after committing edits).
    @app.callback(
        [Output("mode-frozen", "className", allow_duplicate=True),
         Output("mode-editable", "className", allow_duplicate=True),
         Output("thresh-apply-status", "children", allow_duplicate=True),
         Output("thresh-unsaved-badge", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)]
        + [Output(f"thresh-{name}", "value", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS]
        + [Output(f"thresh-{name}", "disabled", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS],
        Input("btn-apply-thresholds", "n_clicks"),
        [State(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        prevent_initial_call=True,
    )
    def _apply_thresholds(_n, *thresh_values):
        current = routing_state.get_thresholds()
        tentative_dict = current.to_dict()
        for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
            if val is not None:
                tentative_dict[name] = val
        try:
            tentative = RoutingThresholds.from_dict(tentative_dict)
            tentative.validate()
        except Exception as e:
            safe_values = [getattr(current, name) for name, *_ in THRESHOLD_FIELDS]
            frozen_now = routing_state.is_frozen
            dis = _disabled_list(frozen_now, len(THRESHOLD_FIELDS))
            f_cls, e_cls = _mode_button_classes(frozen_now)
            return (
                [f_cls, e_cls,
                 html.Span(f"✗ Apply failed: {e}", style={"fontSize": "11px", "color": "#C0392B"}),
                 html.Span("● unsaved changes", style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
                 f"Apply failed: {e}"]
                + safe_values + dis
            )

        # Commit to routing_state + switch to editable mode (custom active).
        # Always update state and clear badges (Task 5).
        if routing_state.custom_thresholds is None:
            # centralize read: use get_thresholds() (frozen at this point => returns base preset)
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.get_thresholds().to_dict()
            )
        for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
            if val is not None:
                setattr(routing_state.custom_thresholds, name, val)

        # Set is_frozen based on the applied mode: after Apply we are in editable (not frozen).
        post_apply_frozen = False
        routing_state.set_frozen_mode(post_apply_frozen)

        f_cls, e_cls = _mode_button_classes(routing_state.is_frozen)
        dis_editable = _disabled_list(routing_state.is_frozen, len(THRESHOLD_FIELDS))
        # Success path explicitly clears unsaved badge and sets clean apply status.
        return (
            [f_cls, e_cls,
             html.Span("✓ Thresholds applied successfully.",
                       style={"fontSize": "11px", "color": "#27AE60", "fontWeight": "600"}),
             html.Span("", style={"display": "none"}),  # clear unsaved badge
             f"Thresholds applied (preset: {routing_state.current_preset})"]
            + list(thresh_values) + dis_editable
        )

    # --- Mode switch callbacks (Task 4 step 3) ---
    # New callbacks for mode buttons that set routing_state.is_frozen (via set_frozen_mode)
    # and reload values. When switching to editable from frozen, always copy current to custom.
    mode_button_outputs = (
        [Output("mode-frozen", "className", allow_duplicate=True),
         Output("mode-editable", "className", allow_duplicate=True),
         Output("routing-preset-status", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True),
         Output("thresh-unsaved-badge", "children", allow_duplicate=True),
         Output("thresh-apply-status", "children", allow_duplicate=True)]
        + [Output(f"thresh-{name}", "value", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS]
        + [Output(f"thresh-{name}", "disabled", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS]
    )

    @app.callback(
        mode_button_outputs,
        [Input("mode-frozen", "n_clicks"),
         Input("mode-editable", "n_clicks")],
        prevent_initial_call=True,
    )
    def _switch_mode(f_nclicks, e_nclicks):
        ctx = dash_ctx
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
        n_fields = len(THRESHOLD_FIELDS)

        if trigger == "mode-frozen":
            routing_state.set_frozen_mode(True)
            thr = routing_state.get_thresholds()
            vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
            f_cls, e_cls = _mode_button_classes(routing_state.is_frozen)
            dis_list = _disabled_list(routing_state.is_frozen, n_fields)
            return [
                f_cls, e_cls,
                f"Mode: Locked ({routing_state.current_preset})",
                "",
                html.Span("", style={"display": "none"}),
                "",
            ] + vals + dis_list

        if trigger == "mode-editable":
            # Always copy current (from preset) to custom if needed (per spec + requirement)
            if routing_state.custom_thresholds is None:
                # centralize read via get_thresholds() (at switch time, base preset is active)
                routing_state.custom_thresholds = RoutingThresholds.from_dict(
                    routing_state.get_thresholds().to_dict()
                )
            routing_state.set_frozen_mode(False)
            thr = routing_state.get_thresholds()
            vals = [getattr(thr, name) for name, *_ in THRESHOLD_FIELDS]
            f_cls, e_cls = _mode_button_classes(routing_state.is_frozen)
            dis_list = _disabled_list(routing_state.is_frozen, n_fields)
            return [
                f_cls, e_cls,
                "Mode: Editable (based on preset, Apply required after edits)",
                "",
                html.Span("", style={"display": "none"}),
                "",
            ] + vals + dis_list

        # Should not reach
        raise dash_ctx.PreventUpdate
