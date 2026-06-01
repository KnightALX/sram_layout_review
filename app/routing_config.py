"""Routing-focused Configuration tab.

Replaces `_create_config_content()` from `app/layout.py`.
Exposes ONLY routing thresholds + preset selector — no regex, no rule
editor, no per-rule enable/disable.
"""
from __future__ import annotations
from typing import List
from dash import html, dcc
from config.routing_thresholds import RoutingThresholds
from config.preset_loader import list_yaml_presets
from app.routing_state import routing_state


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
    return [{"label": name, "value": name} for name in list_yaml_presets()]


def create_routing_config_tab():
    """Build the routing Configuration tab content (Dash components only)."""
    preset = routing_state.current_preset
    thr = routing_state.get_thresholds()

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
            html.Div("Routing Thresholds", className="card-header"),
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
                ], className="form-group", style={"marginBottom": "12px"})
                for (name, label, mn, mx, st) in THRESHOLD_FIELDS
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Golden / Batch regex
        html.Div([
            html.Div("Net Selection (Regex)", className="card-header"),
            html.Div([
                html.Div([
                    html.Label("Golden Net Regex", className="form-label"),
                    dcc.Input(id="golden-regex", type="text",
                              value=routing_state.golden_regex,
                              placeholder="e.g. ^WL_0$ or ^WL.*$",
                              className="input-field"),
                ], className="form-group", style={"marginBottom": "12px"}),
                html.Div([
                    html.Label("Batch Net Regex", className="form-label"),
                    dcc.Input(id="batch-regex", type="text",
                              value=routing_state.batch_regex,
                              placeholder="e.g. ^WL_.*$ or ^BL.*$",
                              className="input-field"),
                ], className="form-group", style={"marginBottom": "12px"}),
                html.Button("Run Routing Review", id="btn-run-routing-review",
                            className="btn btn-primary btn-block"),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Status
        html.Div(id="routing-config-status"),
    ], style={"padding": "16px"})


def register_routing_config_callbacks(app):
    """Register all callbacks for the routing Configuration tab."""
    from dash import Input, Output, State
    from config.preset_loader import load_preset_yaml

    @app.callback(
        [Output("routing-preset-status", "children"),
         Output("routing-config-status", "children")]
        + [Output(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
        [Input("routing-preset", "value"),
         Input("golden-regex", "value"),
         Input("batch-regex", "value")]
        + [Input(f"thresh-{name}", "value") for name, *_ in THRESHOLD_FIELDS],
    )
    def update_routing_config(preset, golden_re, batch_re, *thresh_values):
        from dash import callback_context
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        # Preset switch → reload thresholds
        if trigger == "routing-preset" and preset:
            try:
                t = load_preset_yaml(preset)
                routing_state.current_preset = preset
                routing_state.thresholds = t
                routing_state.custom_thresholds = None
                status = f"Loaded preset: {preset}"
                thresh_outputs = [getattr(t, name) for name, *_ in THRESHOLD_FIELDS]
                return [status, ""] + thresh_outputs
            except Exception as e:
                return [f"Error: {e}", ""] + list(thresh_values)

        # Update regex state
        if trigger == "golden-regex":
            routing_state.golden_regex = golden_re or ""
        if trigger == "batch-regex":
            routing_state.batch_regex = batch_re or ""

        # Update custom thresholds
        for (name, *_), val in zip(THRESHOLD_FIELDS, thresh_values):
            if val is not None and routing_state.custom_thresholds is None:
                routing_state.custom_thresholds = RoutingThresholds.from_dict(
                    routing_state.thresholds.to_dict()
                )
            if val is not None and routing_state.custom_thresholds is not None:
                setattr(routing_state.custom_thresholds, name, val)
        try:
            routing_state.custom_thresholds and routing_state.custom_thresholds.validate()
        except Exception as e:
            return [f"Loaded: {routing_state.current_preset}", f"Invalid: {e}"] + list(thresh_values)

        return [f"Loaded: {routing_state.current_preset}", ""] + list(thresh_values)
