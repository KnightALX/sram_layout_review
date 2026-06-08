"""RC Prediction tab — visualize + configure the R/C prediction model.

Layout (3 columns, full-height within the tab):

    | 3D Stack Diagram  |  Resistance Params   | Capacitance Params |
    |                  |  (R_sheet, via R)    | (ε_r, fringe, etc.) |
    |                  |                       |                     |
    |                  |  + Model + Apply (spans all 3 columns at the bottom)

This file exposes:
  * `create_rc_prediction_tab()`  — returns the layout (Dash components only)
  * `register_rc_prediction_callbacks(app)` — registers the 2 callbacks:
      1. live preview: any input change → re-render 3D figure, mark unsaved
      2. apply click   → validate + commit to `routing_state` + show status
"""
from __future__ import annotations
from typing import Dict, List, Tuple

from dash import html, dcc, Input, Output, State, no_update
from dash.exceptions import PreventUpdate

from app.rc_model import RCModelConfig, ModelType
from app.rc_visualization import safe_render_stack_3d_figure
from app.routing_state import routing_state
from app.rc_persistence import (
    save_to_disk, load_from_disk, clear_disk, persist_path,
    parse_pdk_text, merge_pdk_into, to_yaml,
    history as rc_history,
)


# Auto-load on first import (so users don't lose their previous session's
# config even if they open the app without ever clicking Apply again).
_persisted = load_from_disk()
if _persisted is not None:
    _persisted.validate()
    routing_state.custom_rc_model = _persisted


# ---------------------------------------------------------------------------
# Field spec — drives both the UI and the callback.  Each row is
# (id_suffix, label, kind, default, min, max, step, help_text) where
# kind ∈ {"float", "int", "text", "bool", "select"}.
# ---------------------------------------------------------------------------
_PROCESS_FIELDS: List[Tuple[str, str, str, object, object, object, object, str]] = [
    ("tech_node", "Tech Node", "text", "7nm", None, None, None,
     "Process node label (display only)."),
    ("temperature_c", "Temperature (°C)", "float", 85.0, -55.0, 200.0, 1.0,
     "Junction temperature; used to scale R."),
    ("metal_resistivity_tempco", "Cu tempco (1/°C)", "float", 0.004, 0.0, 0.02, 0.0005,
     "Sheet-R temperature coefficient around 25°C ref."),
    ("via_resistance_tempco", "Via tempco (1/°C)", "float", 0.003, 0.0, 0.02, 0.0005,
     "Via-R temperature coefficient around 25°C ref."),
]

_DIELECTRIC_FIELDS: List[Tuple[str, str, str, object, object, object, object, str]] = [
    ("dielectric_constant", "ILD ε_r", "float", 3.9, 1.0, 12.0, 0.1,
     "Effective inter-layer-dielectric constant."),
    ("fringe_cap_factor", "Fringe factor", "float", 0.6, 0.0, 2.0, 0.05,
     "Multiplier on sidewall fringe capacitance."),
    ("coupling_cap_factor", "Coupling fraction", "float", 0.3, 0.0, 1.0, 0.05,
     "Fraction of total C that is to neighboring wires."),
]

_MODEL_FIELDS: List[Tuple[str, str, str, object, object, object, object, str]] = [
    ("model_type", "RC Model", "select", ModelType.LUMPED_PI.value, None, None, None,
     "Delay-line model used for effective-τ."),
    ("length_per_segment_um", "Segment length (µm)", "float", 50.0, 0.1, 10000.0, 1.0,
     "Length of each π/T segment; only affects distributed model."),
    ("use_ground_cap_70_30", "70% gnd / 30% coupling split", "bool", True, None, None, None,
     "If on, total C is split 70/30 ground/coupling; if off the coupling factor above is used."),
]


def _all_scalars() -> List[Tuple[str, str, str, object, object, object, object, str]]:
    """All non-dict scalar fields, in display order."""
    return _PROCESS_FIELDS + _DIELECTRIC_FIELDS + _MODEL_FIELDS


def _input_id(name: str) -> str:
    return f"rc-{name}"


def _make_input(spec: Tuple) -> html.Div:
    """Render a single labeled input from a field spec tuple."""
    name, label, kind, default, mn, mx, step, help_text = spec
    common_style = {"fontFamily": "var(--font-data)", "fontSize": "12px"}
    if kind == "text":
        control = dcc.Input(
            id=_input_id(name), type="text", value=str(default),
            className="input-field", style=common_style,
        )
    elif kind == "bool":
        control = dcc.Checklist(
            id=_input_id(name),
            options=[{"label": " enable", "value": "on"}],
            value=["on"] if default else [],
            className="checklist",
            style={"fontSize": "11px"},
        )
    elif kind == "select":
        if name == "model_type":
            options = [{"label": m.value, "value": m.value} for m in ModelType]
        else:
            options = []
        control = dcc.Dropdown(
            id=_input_id(name), options=options, value=default,
            className="dropdown", clearable=False, style=common_style,
        )
    else:  # float / int
        ctype = "number"
        control = dcc.Input(
            id=_input_id(name), type=ctype, value=default,
            min=mn, max=mx, step=step,
            className="input-field", style=common_style,
        )
    return html.Div([
        html.Label(label, className="form-label", title=help_text),
        control,
        html.Div(help_text, className="text-muted",
                 style={"fontSize": "10px", "marginTop": "2px"}),
    ], className="form-group", style={"marginBottom": "10px"})


def _metal_layer_card(cfg: RCModelConfig) -> html.Div:
    """A read-only card listing the active metal/via R-sheets and dimensions.

    This is a *preview* — it shows what the current inputs would produce.
    The user cannot edit the per-layer values from this tab (we don't want
    a 14-row editor on the first tab); the per-layer values come from
    the TechConfig that is loaded with the active preset.
    """
    rows: List[html.Div] = []
    for layer in cfg.metal_layers():
        r = cfg.metal_r_sheet.get(layer, 0.0)
        t = cfg.metal_thickness.get(layer, 0.0) * 1000.0  # µm → nm
        w = cfg.metal_width.get(layer, 0.0) * 1000.0
        rows.append(html.Tr([
            html.Td(layer, style={"padding": "3px 8px", "color": "#60a5fa",
                                  "fontWeight": "600"}),
            html.Td(f"{r:.3f} Ω/□", style={"textAlign": "right"}),
            html.Td(f"{t:.0f} nm", style={"textAlign": "right"}),
            html.Td(f"{w:.0f} nm", style={"textAlign": "right"}),
        ]))
    for via in cfg.via_layers():
        r = cfg.via_resistance.get(via, 0.0)
        rows.append(html.Tr([
            html.Td(via, style={"padding": "3px 8px", "color": "#94a3b8",
                                "fontStyle": "italic"}),
            html.Td(f"{r:.2f} Ω", style={"textAlign": "right", "color": "#94a3b8"}),
            html.Td("—", style={"textAlign": "right", "color": "#94a3b8"}),
            html.Td("—", style={"textAlign": "right", "color": "#94a3b8"}),
        ]))
    return html.Div([
        html.Div("Metal/Via R-sheet (preview)", className="prop-group-header"),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Layer", style={"textAlign": "left"}),
                html.Th("R", style={"textAlign": "right"}),
                html.Th("thick", style={"textAlign": "right"}),
                html.Th("width", style={"textAlign": "right"}),
            ])),
            html.Tbody(rows),
        ], className="data-table",
            style={"fontFamily": "var(--font-data)", "fontSize": "11px",
                   "width": "100%"}),
    ], className="prop-group",
        style={"marginTop": "8px", "padding": "8px 4px",
               "background": "var(--bg-input)", "borderRadius": "4px"})


def _cap_estimator_card(cfg: RCModelConfig) -> html.Div:
    """A read-only card listing C/µm and total C for a 100 µm wire per layer."""
    rows: List[html.Tr] = []
    for layer in cfg.metal_layers():
        c100 = cfg.predict_wire_capacitance(layer, 100.0)
        # Convert fF → aF/µm for a friendlier display
        c_per_um_af = c100 * 1000.0 / 100.0
        rows.append(html.Tr([
            html.Td(layer, style={"padding": "3px 8px", "color": "#60a5fa",
                                  "fontWeight": "600"}),
            html.Td(f"{c_per_um_af:.1f} aF/µm", style={"textAlign": "right"}),
            html.Td(f"{c100:.2f} fF", style={"textAlign": "right"}),
        ]))
    return html.Div([
        html.Div("C estimate @ 100 µm wire (preview)", className="prop-group-header"),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Layer", style={"textAlign": "left"}),
                html.Th("c/µm", style={"textAlign": "right"}),
                html.Th("total", style={"textAlign": "right"}),
            ])),
            html.Tbody(rows),
        ], className="data-table",
            style={"fontFamily": "var(--font-data)", "fontSize": "11px",
                   "width": "100%"}),
    ], className="prop-group",
        style={"marginTop": "8px", "padding": "8px 4px",
               "background": "var(--bg-input)", "borderRadius": "4px"})


# ---------------------------------------------------------------------------
# Tentative-config builder — used by the live-preview callback.
# Reads every input value, packages it into a RCModelConfig, and validates.
# If validation fails the function returns (None, error_message); the
# caller re-renders with the last known-good values and shows the error.
# ---------------------------------------------------------------------------
def _build_tentative_config(values: Dict[str, object]) -> Tuple[RCModelConfig | None, str | None]:
    current = routing_state.get_rc_model()
    d = current.to_dict()
    # Overlay scalar inputs
    for spec in _all_scalars():
        name, _label, kind, default, mn, mx, step, _help = spec
        if name in values:
            v = values[name]
            if kind == "bool":
                d[name] = bool(v)
            elif kind in ("float", "int"):
                try:
                    d[name] = float(v) if v is not None and v != "" else float(default)
                except (TypeError, ValueError):
                    return None, f"{name}: not a number ({v!r})"
            else:
                d[name] = v
    try:
        cfg = RCModelConfig.from_dict(d)
        cfg.validate()
        return cfg, None
    except ValueError as e:
        return None, str(e)


def _values_from_inputs(**kwargs) -> Dict[str, object]:
    """Pull scalar values out of the callback kwargs by field name."""
    result: Dict[str, object] = {}
    for spec in _all_scalars():
        name = spec[0]
        if name in kwargs:
            v = kwargs[name]
            if isinstance(v, list):  # Checklist values come in as a list
                result[name] = bool(v) and v != []
            else:
                result[name] = v
    return result


# ---------------------------------------------------------------------------
# Public layout factory
# ---------------------------------------------------------------------------
def create_rc_prediction_tab() -> html.Div:
    """Build the RC Prediction tab content (Dash components only)."""
    cfg = routing_state.get_rc_model()
    initial_fig = safe_render_stack_3d_figure(cfg)

    # Column 1: 3D figure
    col_left = html.Div([
        html.Div([
            html.Span("3D Stack Diagram", style={"flex": "1"}),
            html.Span(id="rc-unsaved-badge",
                      style={"fontSize": "10px", "color": "#E67E22",
                             "fontWeight": "600", "display": "none"}),
        ], className="card-header"),
        html.Div([
            dcc.Graph(
                id="rc-stack-3d",
                figure=initial_fig,
                config={"displayModeBar": False, "displaylogo": False,
                        "staticPlot": True},
                style={"width": "100%", "height": "340px",
                       "background": "white", "borderRadius": "4px"},
            ),
            html.Div([
                html.Div("Metal/Via R-sheet (preview)", className="prop-group-header"),
                _metal_layer_card(cfg),
            ], style={"marginTop": "8px"}),
        ], className="card-body"),
    ], className="card", style={"flex": "1", "minWidth": "300px",
                                "marginRight": "12px", "marginBottom": "12px"})

    # Column 2: Resistance params
    col_mid = html.Div([
        html.Div("Resistance Parameters", className="card-header"),
        html.Div([
            _make_input(spec) for spec in _PROCESS_FIELDS
        ], className="card-body"),
    ], className="card", style={"flex": "1", "minWidth": "260px",
                                "marginRight": "12px", "marginBottom": "12px"})

    # Column 3: Capacitance params
    col_right = html.Div([
        html.Div("Capacitance Parameters", className="card-header"),
        html.Div([
            _make_input(spec) for spec in _DIELECTRIC_FIELDS
        ], className="card-body"),
    ], className="card", style={"flex": "1", "minWidth": "260px",
                                "marginBottom": "12px"})

    # Bottom: Model + Apply (spans full width)
    bottom = html.Div([
        html.Div("Delay-line Model & Apply", className="card-header"),
        html.Div([
            html.Div([
                html.Div([
                    _make_input(spec) for spec in _MODEL_FIELDS
                ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr",
                         "gap": "12px", "flex": "1"}),
                html.Div([
                    html.Div("Per-layer C estimate (preview)", className="prop-group-header",
                             style={"marginTop": "0px"}),
                    _cap_estimator_card(cfg),
                ], style={"minWidth": "280px"}),
            ], style={"display": "flex", "gap": "16px", "alignItems": "flex-start"}),
            # Apply row
            html.Div([
                html.Button("✓ Apply", id="btn-apply-rc",
                            className="btn btn-primary",
                            style={"minWidth": "120px", "minHeight": "34px",
                                   "fontWeight": "600"}),
                html.Button("↶ Revert", id="btn-revert-rc",
                            className="btn btn-secondary",
                            title="Undo last Apply (max 10 steps)",
                            style={"minWidth": "100px", "minHeight": "34px"}),
                html.Button("⟲ Reset", id="btn-reset-rc",
                            className="btn btn-secondary",
                            title="Reset to built-in 7nm default",
                            style={"minWidth": "100px", "minHeight": "34px"}),
                dcc.Upload(
                    id="btn-import-rc",
                    children=html.Button("⬆ Import PDK",
                                         className="btn btn-secondary",
                                         style={"minWidth": "120px",
                                                "minHeight": "34px"}),
                    accept=".yaml,.yml,.json,.txt",
                    max_size=2 * 1024 * 1024,  # 2 MB cap
                    multiple=False,
                    style={"display": "inline-block"},
                ),
                html.Button("⬇ Save Preset", id="btn-export-rc",
                            className="btn btn-secondary",
                            title="Download current config as YAML",
                            style={"minWidth": "120px", "minHeight": "34px"}),
                html.Div(id="rc-apply-status",
                         style={"fontSize": "12px", "marginLeft": "12px",
                                "flex": "1", "textAlign": "right"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                      "marginTop": "12px", "paddingTop": "10px",
                      "borderTop": "1px solid var(--border-primary)"}),
            # Hidden Download component for the Save Preset flow
            dcc.Download(id="rc-download-yaml"),
            # Hidden storage for Import result (textarea / status)
            html.Div(id="rc-import-status",
                     style={"fontSize": "11px", "marginTop": "6px",
                            "color": "#94a3b8"}),
        ], className="card-body"),
    ], className="card")

    return html.Div([
        html.Div([col_left, col_mid, col_right],
                 style={"display": "flex", "flexWrap": "wrap"}),
        bottom,
    ], style={"padding": "16px", "overflowY": "auto", "height": "100%"})


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
def register_rc_prediction_callbacks(app):
    """Register the 2 callbacks used by the RC Prediction tab."""

    # Build the Inputs list once — used by both callbacks.
    scalar_inputs = [Input(_input_id(spec[0]), "value")
                     for spec in _all_scalars()]

    # ------------------------------------------------------------------
    # 1. Live preview: any input change → re-render 3D, update previews.
    # ------------------------------------------------------------------
    @app.callback(
        [Output("rc-stack-3d", "figure", allow_duplicate=True),
         Output("rc-unsaved-badge", "children", allow_duplicate=True),
         Output("rc-unsaved-badge", "style", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)],
        scalar_inputs,
        prevent_initial_call=True,
    )
    def _on_input_change(*args):
        # Map positional args back to field names
        values = _values_from_inputs(**{spec[0]: v for spec, v in zip(_all_scalars(), args)})
        cfg, err = _build_tentative_config(values)
        if err is not None:
            # Invalid — keep current figure, show error badge
            return (
                no_update,
                f"● invalid: {err}",
                {"fontSize": "10px", "color": "#C0392B",
                 "fontWeight": "600", "display": "inline"},
                f"Invalid input: {err}",
            )
        # Valid tentative config — render preview + mark unsaved
        fig = safe_render_stack_3d_figure(cfg)
        return (
            fig,
            "● unsaved",
            {"fontSize": "10px", "color": "#E67E22",
             "fontWeight": "600", "display": "inline"},
            f"RC model: {cfg.preset_name} (unsaved)",
        )

    # ------------------------------------------------------------------
    # 2. Apply: validate + commit to routing_state + push history + persist.
    # ------------------------------------------------------------------
    @app.callback(
        [Output("rc-apply-status", "children"),
         Output("rc-unsaved-badge", "children", allow_duplicate=True),
         Output("rc-unsaved-badge", "style", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)],
        Input("btn-apply-rc", "n_clicks"),
        [State(_input_id(spec[0]), "value") for spec in _all_scalars()],
        prevent_initial_call=True,
    )
    def _on_apply(_n, *args):
        if not _n:
            raise PreventUpdate
        values = _values_from_inputs(**{spec[0]: v for spec, v in zip(_all_scalars(), args)})
        cfg, err = _build_tentative_config(values)
        if err is not None:
            return (
                html.Span(f"✗ Apply failed: {err}",
                          style={"color": "#C0392B", "fontWeight": "600"}),
                "● invalid",
                {"fontSize": "10px", "color": "#C0392B",
                 "fontWeight": "600", "display": "inline"},
                f"Apply failed: {err}",
            )
        # Push the *previous* active config onto the history stack so Revert
        # can restore it.  This must happen before we overwrite the active.
        prev = routing_state.get_rc_model()
        rc_history().push(prev)
        # Commit: write to custom_rc_model (or clear it if same as default)
        if cfg.to_dict() == routing_state.rc_model.to_dict():
            routing_state.custom_rc_model = None
        else:
            routing_state.custom_rc_model = cfg
        # Persist to disk so it survives an app restart
        try:
            saved_path = save_to_disk(routing_state.get_rc_model())
            persist_msg = f"  ·  saved to {saved_path}"
        except OSError as e:
            persist_msg = f"  ·  ⚠ save failed: {e}"
        return (
            html.Span(
                f"✓ RC model applied. ({len(cfg.metal_layers())} metals, "
                f"{len(cfg.via_layers())} vias, model={cfg.model_type})"
                f"{persist_msg}",
                style={"color": "#27AE60", "fontWeight": "600"},
            ),
            "",
            {"display": "none"},
            f"RC model applied: {cfg.tech_node} / {cfg.model_type}",
        )

    # ------------------------------------------------------------------
    # 3. Revert: pop history stack → restore previous config.
    # ------------------------------------------------------------------
    @app.callback(
        [Output("rc-apply-status", "children", allow_duplicate=True),
         Output("rc-import-status", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)]
        + [Output(_input_id(spec[0]), "value", allow_duplicate=True)
           for spec in _all_scalars()],
        Input("btn-revert-rc", "n_clicks"),
        prevent_initial_call=True,
    )
    def _on_revert(_n):
        if not _n:
            raise PreventUpdate
        prev = rc_history().pop()
        if prev is None:
            return (
                html.Span("Revert: history is empty.",
                          style={"color": "#94a3b8"}),
                "",
                "Revert: nothing to undo.",
            ) + tuple(getattr(routing_state.get_rc_model(), spec[0])
                      for spec in _all_scalars())
        # Re-commit prev
        if prev.to_dict() == routing_state.rc_model.to_dict():
            routing_state.custom_rc_model = None
        else:
            routing_state.custom_rc_model = prev
        # Re-persist
        try:
            save_to_disk(routing_state.get_rc_model())
        except OSError:
            pass
        return (
            html.Span(
                f"↶ Reverted. ({len(prev.metal_layers())} metals, "
                f"model={prev.model_type}, T={prev.temperature_c:.0f}°C)",
                style={"color": "#60a5fa", "fontWeight": "600"},
            ),
            f"Revert: history has {len(rc_history())} more step(s).",
            f"RC reverted: {prev.tech_node} / {prev.model_type}",
        ) + tuple(getattr(prev, spec[0]) for spec in _all_scalars())

    # ------------------------------------------------------------------
    # 4. Reset: clear custom override → back to built-in default.
    # ------------------------------------------------------------------
    @app.callback(
        [Output("rc-apply-status", "children", allow_duplicate=True),
         Output("rc-import-status", "children", allow_duplicate=True),
         Output("routing-config-status", "children", allow_duplicate=True)]
        + [Output(_input_id(spec[0]), "value", allow_duplicate=True)
           for spec in _all_scalars()],
        Input("btn-reset-rc", "n_clicks"),
        prevent_initial_call=True,
    )
    def _on_reset(_n):
        if not _n:
            raise PreventUpdate
        prev = routing_state.get_rc_model()
        rc_history().push(prev)
        # Reset to default
        routing_state.custom_rc_model = None
        # Remove the disk file too so next launch doesn't reload
        clear_disk()
        default = routing_state.get_rc_model()
        return (
            html.Span(
                "⟲ Reset to built-in default.",
                style={"color": "#94a3b8", "fontWeight": "600"},
            ),
            f"Reset: cleared custom override (history: {len(rc_history())} step(s)).",
            f"RC reset: {default.tech_node} / {default.model_type}",
        ) + tuple(getattr(default, spec[0]) for spec in _all_scalars())

    # ------------------------------------------------------------------
    # 5. Import PDK: parse uploaded file → merge into a new config and
    #    push the values into the inputs (so the user sees the change
    #    before re-clicking Apply).
    # ------------------------------------------------------------------
    @app.callback(
        [Output("rc-import-status", "children"),
         Output("rc-unsaved-badge", "children", allow_duplicate=True),
         Output("rc-unsaved-badge", "style", allow_duplicate=True)]
        + [Output(_input_id(spec[0]), "value", allow_duplicate=True)
           for spec in _all_scalars()],
        Input("btn-import-rc", "contents"),
        Input("btn-import-rc", "filename"),
        prevent_initial_call=True,
    )
    def _on_import_pdk(contents, filename):
        if contents is None:
            raise PreventUpdate
        # `contents` is a base64 data URL: "data:<mime>;base64,<...>"
        try:
            import base64
            header, _, b64 = contents.partition(",")
            raw = base64.b64decode(b64 or header)
            text = raw.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return (
                html.Span(f"✗ Import decode failed: {e}",
                          style={"color": "#C0392B"}),
                "● invalid",
                {"fontSize": "10px", "color": "#C0392B",
                 "fontWeight": "600", "display": "inline"},
            ) + tuple(getattr(routing_state.get_rc_model(), spec[0])
                      for spec in _all_scalars())

        try:
            pdk = parse_pdk_text(text, filename or "")
        except ValueError as e:
            return (
                html.Span(f"✗ Import parse failed: {e}",
                          style={"color": "#C0392B"}),
                "● invalid",
                {"fontSize": "10px", "color": "#C0392B",
                 "fontWeight": "600", "display": "inline"},
            ) + tuple(getattr(routing_state.get_rc_model(), spec[0])
                      for spec in _all_scalars())

        current = routing_state.get_rc_model()
        try:
            new_cfg = merge_pdk_into(current, pdk)
            new_cfg.validate()
        except ValueError as e:
            return (
                html.Span(f"✗ PDK validation failed: {e}",
                          style={"color": "#C0392B"}),
                "● invalid",
                {"fontSize": "10px", "color": "#C0392B",
                 "fontWeight": "600", "display": "inline"},
            ) + tuple(getattr(current, spec[0]) for spec in _all_scalars())

        # Push the merged values into the inputs (NOT yet applied to state).
        # Show a "PDK loaded" status; user still has to click Apply.
        return (
            html.Span(
                f"✓ Loaded PDK from {filename or 'pasted text'}: "
                f"{len(new_cfg.metal_layers())} metals, "
                f"{len(new_cfg.via_layers())} vias  ·  click Apply to commit.",
                style={"color": "#60a5fa", "fontWeight": "600"},
            ),
            "● unsaved (PDK)",
            {"fontSize": "10px", "color": "#E67E22",
             "fontWeight": "600", "display": "inline"},
        ) + tuple(getattr(new_cfg, spec[0]) for spec in _all_scalars())

    # ------------------------------------------------------------------
    # 6. Save Preset: emit a YAML download of the *active* (custom or
    #    default) config.
    # ------------------------------------------------------------------
    @app.callback(
        Output("rc-download-yaml", "data"),
        Input("btn-export-rc", "n_clicks"),
        prevent_initial_call=True,
    )
    def _on_export_yaml(_n):
        if not _n:
            raise PreventUpdate
        cfg = routing_state.get_rc_model()
        text = to_yaml(cfg)
        return dict(content=text, filename=f"rc_model_{cfg.tech_node}.yaml",
                    type="text/yaml", base64=False)
