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

THRESHOLD_FIELDS = [
    ("max_h_ratio", "Max H Ratio (WL gate)", "0.01", "0.99", "0.01"),
    ("max_v_ratio", "Max V Ratio (IO gate)", "0.01", "0.99", "0.01"),
    ("max_r_ohm", "Max Total R (Ω)", "0.1", "10000", "0.1"),
    ("max_c_ff", "Max Total C (fF)", "0.1", "100000", "1"),
    ("max_tau_ps", "Max Effective τ (ps)", "0.01", "1000", "0.1"),
    ("min_via_coverage", "Min Via Coverage", "0.0", "1.0", "0.01"),
    ("min_similarity", "Min Golden Similarity", "0", "100", "1"),
]


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

    from config.preset_loader import load_preset_yaml

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
        # Only run when this tab is visible (cheap) — otherwise no_update
        if tab not in (None, "tab-routing-config"):
            return no_update, no_update, no_update, no_update
        return (
            _regex_match_preview(golden_re or "", "Golden"),
            _regex_match_preview(batch_re or "", "Batch"),
            _loaded_nets_status(),
            "",
        )

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
    #         Also hooks thresh-* inputs to prevent the preview refresh from
    #         killing thresh values. ---
    @app.callback(
        [Output("routing-preset-status", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True),
         Output("thresh-unsaved-badge", "children", allow_duplicate=True),
         Output("thresh-apply-status", "children", allow_duplicate=True)]
        + [Output(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        [Input("routing-preset", "value")]
        + [Input(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        prevent_initial_call=True,
    )
    def update_routing_config(preset, *thresh_values):
        ctx = dash_ctx
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        # Preset switch → reload thresholds into state AND inputs immediately.
        if trigger == "routing-preset" and preset:
            try:
                from config.routing_thresholds import _BUILTIN_PRESETS
                if preset in _BUILTIN_PRESETS and preset not in list_yaml_presets():
                    t = RoutingThresholds.for_preset(preset)  # code-only path
                else:
                    t = load_preset_yaml(preset)  # YAML path
                routing_state.current_preset = preset
                routing_state.thresholds = t
                routing_state.custom_thresholds = None
                status = f"Loaded preset: {preset}"
                thresh_outputs = [getattr(t, name) for name, *_ in THRESHOLD_FIELDS]
                return [status, "", html.Span("", style={"display": "none"}), ""] + thresh_outputs
            except Exception as e:
                return [f"Error: {e}", "", html.Span("", style={"display": "none"}), ""] + list(thresh_values)

        # Manual threshold edit → validate UI only, do NOT commit to state.
        # Show "unsaved changes" badge so the user knows to click Apply.
        current = routing_state.get_thresholds()
        tentative_dict = current.to_dict()
        for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
            if val is not None:
                tentative_dict[name] = val
        try:
            tentative = RoutingThresholds.from_dict(tentative_dict)
            tentative.validate()
            # Validation passed — show unsaved badge, keep inputs as-is
            return [
                f"Loaded: {routing_state.current_preset}",
                "",
                html.Span("● unsaved changes", style={
                    "fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
                html.Span("Thresholds modified — click Apply to save.",
                          style={"fontSize": "10px", "color": "#E67E22"}),
            ] + list(thresh_values)
        except Exception as e:
            # Invalid values — snap back to last-known-good, show error
            safe_values = [getattr(current, name) for name, *_ in THRESHOLD_FIELDS]
            return [
                f"Loaded: {routing_state.current_preset}",
                f"Invalid: {e} (reverted)",
                html.Span("", style={"display": "none"}),
                html.Span(f"Invalid: {e}", style={"fontSize": "10px", "color": "#C0392B"}),
            ] + safe_values

    # --- 5. Apply Thresholds button — validates and commits to routing_state ---
    @app.callback(
        [Output("thresh-apply-status", "children", allow_duplicate=True),
         Output("thresh-unsaved-badge", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)]
        + [Output(f"thresh-{name}", "value", allow_duplicate=True) for name, *_ in THRESHOLD_FIELDS],
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
            return (
                [html.Span(f"✗ Apply failed: {e}", style={"fontSize": "11px", "color": "#C0392B"}),
                 html.Span("● unsaved changes", style={"fontSize": "10px", "color": "#E67E22", "fontWeight": "600"}),
                 f"Apply failed: {e}"]
                + safe_values
            )

        # Commit to routing_state
        if routing_state.custom_thresholds is None:
            routing_state.custom_thresholds = RoutingThresholds.from_dict(
                routing_state.thresholds.to_dict()
            )
        for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
            if val is not None:
                setattr(routing_state.custom_thresholds, name, val)

        return (
            [html.Span("✓ Thresholds applied successfully.",
                       style={"fontSize": "11px", "color": "#27AE60", "fontWeight": "600"}),
             html.Span("", style={"display": "none"}),
             f"Thresholds applied (preset: {routing_state.current_preset})"]
            + list(thresh_values)
        )
