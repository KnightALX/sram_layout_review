"""Routing-focused Layout Review tab.

Replaces `_create_review_content()` from `app/layout.py`.
Shows the 6 metric cards + sortable similarity table + per-net directional viz.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from dash import dash_table, dcc, html
from dash.exceptions import PreventUpdate

from app.routing_state import routing_state
from app.state import app_state  # for accessing loaded nets/polygons
from core.routing_metrics import compute_for_net, split_metal_via_polygons
from core.routing_violation import RoutingViolation
from core.visualization import create_directional_figure

_ERROR_BANNER_HIDDEN = {
    "display": "none",
    "background": "rgba(220, 38, 38, 0.9)",
    "color": "white",
    "padding": "10px 14px",
    "borderRadius": "6px",
    "marginBottom": "12px",
    "fontSize": "12px",
}
_ERROR_BANNER_VISIBLE = {**_ERROR_BANNER_HIDDEN, "display": "block"}

METRIC_CARD_IDS = [
    ("h_ratio", "H / V Ratio", "%"),
    ("missing_via", "Missing Via", ""),
    ("r_total", "Eff. R (Ω)", "Ω"),
    ("c_total", "Eff. C (fF)", "fF"),
    ("tau_ps", "Eff. τ (ps)", "ps"),
    ("similarity", "Similarity", "/100"),
    ("gate", "Pass / Fail", ""),
]


def _make_card(label: str, value: str, sub: str = "",
               extra_class: str = "metric-card", threshold: str = "") -> html.Div:
    """Build a single metric card div with label / value / optional sub-line.
    If threshold provided, appends " / <threshold>" (gray) inline with value
    so cards display both observed range and active threshold.
    """
    if threshold:
        value_children = [
            html.Span(value, style={"fontSize": "20px", "fontWeight": "600"}),
            html.Span(f" / {threshold}", style={"fontSize": "12px", "color": "#94a3b8", "marginLeft": "4px"}),
        ]
        value_div = html.Div(value_children, className="metric-value",
                             style={"fontSize": "20px", "fontWeight": "600"})
    else:
        value_div = html.Div(value, className="metric-value",
                             style={"fontSize": "20px", "fontWeight": "600"})
    children = [
        html.Div(label, className="metric-label",
                 style={"fontSize": "11px", "color": "#888"}),
        value_div,
    ]
    if sub:
        children.append(html.Div(sub, className="metric-sub",
                                 style={"fontSize": "10px", "color": "#666",
                                        "marginTop": "2px"}))
    return html.Div(children, className=extra_class, style={
        "flex": "1", "padding": "12px", "background": "var(--bg-input)",
        "border": "1px solid var(--border-color)", "borderRadius": "6px",
        "minWidth": "120px",
    })


def _build_threshold_source() -> html.Div:
    """Build the prominent banner showing active threshold source (preset + frozen/custom state)."""
    src = routing_state.get_threshold_source()
    return html.Div([
        html.Span("当前阈值来源: ", style={"fontSize": "11px", "fontWeight": "600"}),
        html.Span(src, style={
            "background": "rgba(5, 46, 22, 0.8)",
            "padding": "2px 6px",
            "borderRadius": "3px",
            "fontSize": "10px",
        }),
    ], style={"marginBottom": "8px"})


def _build_metric_cards(results: Dict[str, Dict[str, Any]]) -> List[html.Div]:
    """Build 6 summary cards showing data ranges (min–max) and pass/fail count.

    Cards: H/V Ratio, Missing Via, Eff. R, Eff. τ, Similarity, Pass/Fail.
    The first 5 show the [min, max] range across all batch nets.
    The 6th shows pass count and total (e.g. "5 / 8").

    Nets with `status="no_data"` are excluded from min/max aggregation
    (so a "0Ω, 0fF" ghost doesn't drag the ranges to zero), but are still
    counted in the pass/fail denominator. The sub-label reports the no_data
    count when nonzero so the user knows why some rows show "⚠".
    """
    cards: List[html.Div] = []
    if not results:
        # Empty state — show dashes for the first 5 cards
        for _key, label, _unit in METRIC_CARD_IDS[:-1]:
            cards.append(_make_card(label, "—", "no review yet"))
    else:
        # Filter out no_data rows for min/max — their zero values would
        # otherwise collapse the ranges. no_data is counted in pass/fail
        # denominator only.
        ok_results = {n: r for n, r in results.items() if r.get("status") != "no_data"}
        if not ok_results:
            # All nets were no_data — show dashes instead of fake ranges
            for _key, label, _unit in METRIC_CARD_IDS[:-1]:
                cards.append(_make_card(label, "—", "no analyzable nets"))
        else:
            def _minmax(extract):
                vals = [extract(r) for r in ok_results.values()]
                return min(vals), max(vals)

            h_lo, h_hi = _minmax(lambda r: r["h_ratio"])
            miss_lo, miss_hi = _minmax(lambda r: r["missing_via_count"])
            r_lo, r_hi = _minmax(lambda r: r["r_total"])
            c_lo, c_hi = _minmax(lambda r: r["c_total"])
            tau_lo, tau_hi = _minmax(lambda r: r["effective_tau_ps"])
            sim_lo, sim_hi = _minmax(lambda r: r["similarity_score"])
            thresholds = routing_state.get_thresholds()
            cards = [
                _make_card("H / V Ratio",  f"{h_lo*100:.0f}–{h_hi*100:.0f}%",     "max H% vs max V%"),
                _make_card("Missing Via",  f"{int(miss_lo)}–{int(miss_hi)}",       "min–max"),
                _make_card("Eff. R (Ω)",   f"{r_lo:.1f}–{r_hi:.1f}Ω",              "min–max", threshold=f"{thresholds.max_r_ohm:.1f}Ω"),
                _make_card("Eff. C (fF)",  f"{c_lo:.1f}–{c_hi:.1f}fF",             "min–max", threshold=f"{thresholds.max_c_ff:.1f}fF"),
                _make_card("Eff. τ (ps)",  f"{tau_lo:.1f}–{tau_hi:.1f}ps",         "min–max", threshold=f"{thresholds.max_tau_ps:.1f}ps"),
                _make_card("Similarity",   f"{sim_lo:.0f}–{sim_hi:.0f}/100",       "min–max", threshold=f"{thresholds.min_similarity:.0f}"),
            ]

    # Pass / Fail card — always show count
    # Numerator: gate_pass=True from ok_results (no_data has gate_pass=False
    # already, so it would inflate failures if included).
    # Denominator: all results (incl. no_data) so the user sees e.g. "3 / 5"
    # meaning 3 passed out of 5 attempted, when 2 are no_data.
    ok_results = {n: r for n, r in results.items() if r.get("status") != "no_data"}
    n_pass = sum(1 for r in ok_results.values() if r.get("gate_pass"))
    n_total = len(results)
    n_no_data = sum(1 for r in results.values() if r.get("status") == "no_data")
    if n_total == 0:
        pf_value = "—"
        pf_sub = "no review yet"
        pf_class = "metric-card"
    else:
        pf_value = f"{n_pass} / {n_total}"
        if n_pass == n_total:
            pf_sub = "pass"
        else:
            pf_sub = f"failing ({n_no_data} no_data)" if n_no_data else "failing"
        pf_class = f"metric-card {'pass' if n_pass == n_total else 'fail'}"
    cards.append(_make_card("Pass / Fail", pf_value, pf_sub, extra_class=pf_class))
    return cards


def _build_similarity_table() -> dash_table.DataTable:
    """Build the per-net sortable results table with minimal styling."""
    rows = _build_table_rows(routing_state.batch_results)
    style_data_conditional = _compute_table_styles(rows)
    return dash_table.DataTable(
        data=rows,
        columns=[{"name": k, "id": k} for k in
                 ("Net", "Dominant", "H %", "V %", "R (Ω)", "C (fF)", "τ (ps)",
                  "Via Cov", "Miss Via", "Sim", "Pass")],
        sort_action="native", filter_action="native",
        row_selectable="single", page_size=10,
        style_cell={"textAlign": "left", "fontSize": "11px",
                    "padding": "6px 10px"},
        style_data_conditional=style_data_conditional,
        id="routing-results-table",
    )


def _build_table_rows(batch_results: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Render the per-net results dict into a list of display rows.

    Numeric cells are stored as formatted strings so the DataTable can
    show them verbatim. The raw float values live in
    `routing_state.batch_results` for callers that need them.

    Nets with `status="no_data"` are rendered as a distinct "⚠" row with
    dashes for all numeric fields — these nets had no polygons to analyze,
    so any zero values would be misleading.

    The C (fF) column (and cards) use routing_state.get_thresholds() so
    table always reflects latest Config tab settings (re-run to refresh
    after changing thresholds).
    """
    thresholds = routing_state.get_thresholds()
    rows: List[Dict[str, Any]] = []
    for name, m in batch_results.items():
        if m.get("status") == "no_data":
            rows.append({
                "Net": name,
                "Dominant": "—",
                "H %": "—",
                "V %": "—",
                "R (Ω)": "—",
                "C (fF)": "—",
                "τ (ps)": "—",
                "Via Cov": "—",
                "Miss Via": "—",
                "Sim": "—",
                "Pass": "⚠",
            })
        else:
            rows.append({
                "Net": name,
                "Dominant": m["dominant"],
                "H %": f"{m['h_ratio']*100:.1f}",
                "V %": f"{m['v_ratio']*100:.1f}",
                "R (Ω)": f"{m['r_total']:.2f}",
                "C (fF)": f"{m['c_total']:.1f} / {thresholds.max_c_ff:.1f}",
                "τ (ps)": f"{m['effective_tau_ps']:.2f}",
                "Via Cov": f"{m['via_coverage']*100:.1f}",
                "Miss Via": m["missing_via_count"],
                "Sim": f"{m['similarity_score']:.1f}",
                "Pass": "✓" if m["gate_pass"] else "✗",
            })
    return rows


def _compute_table_styles(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return style_data_conditional rules for the per-net table.

    Minimal styling per user feedback: just the pill-style Pass cell.
    Data bars and row-level tint were removed — the user found them too flashy.
    Three states: ✓ (green), ✗ (red), ⚠ (amber) — ⚠ means the net had no
    polygons to analyze (status="no_data") and should look distinct from
    a real gate failure.
    """
    return [
        # Pill-style Pass cell — green ✓ / red ✗ / amber ⚠
        {"if": {"column_id": "Pass", "filter_query": '{Pass} = "✗"'},
         "backgroundColor": "rgba(239, 68, 68, 0.85)",
         "color": "white",
         "fontWeight": "700",
         "textAlign": "center",
         "borderRadius": "10px"},
        {"if": {"column_id": "Pass", "filter_query": '{Pass} = "✓"'},
         "backgroundColor": "rgba(34, 197, 94, 0.85)",
         "color": "white",
         "fontWeight": "700",
         "textAlign": "center",
         "borderRadius": "10px"},
        {"if": {"column_id": "Pass", "filter_query": '{Pass} = "⚠"'},
         "backgroundColor": "rgba(245, 158, 11, 0.85)",
         "color": "white",
         "fontWeight": "700",
         "textAlign": "center",
         "borderRadius": "10px"},
    ]


def create_routing_review_tab():
    """Build the routing Layout Review tab content."""
    return html.Div([
        # Error banner — btn-dismiss-error must live in the initial layout
        # (Dash validates Input IDs at startup; do not create it in callbacks).
        html.Div(
            id="routing-error-banner",
            style=_ERROR_BANNER_HIDDEN,
            children=[
                html.Span("✗ ", style={"fontWeight": "700"}),
                html.Span(id="routing-error-text", children=""),
                html.Button(
                    "Dismiss",
                    id="btn-dismiss-error",
                    n_clicks=0,
                    style={
                        "float": "right",
                        "background": "transparent",
                        "border": "1px solid white",
                        "color": "white",
                        "padding": "2px 8px",
                        "fontSize": "10px",
                        "borderRadius": "4px",
                        "cursor": "pointer",
                    },
                ),
            ],
        ),

        # Threshold source banner — shows active source from routing_state
        # (e.g. "当前阈值来源: sram_7nm_wl（冻结）" or "基于 ... 的自定义")
        # Updated by dedicated callback on tab/interval; initial value from state.
        html.Div(id="routing-threshold-source", children=_build_threshold_source()),

        # Summary cards — wrapped so the callback can update them on review
        html.Div(id="routing-metric-cards",
                 children=_build_metric_cards(routing_state.batch_results),
                 style={"display": "flex", "gap": "12px", "marginBottom": "16px"}),

        # Empty-state banner: shown when no review has been run yet
        html.Div(id="routing-review-empty", children=_empty_state_banner()),

        # Visualization
        html.Div([
            html.Div("Directional Visualization (H=Red, V=Blue)", className="card-header"),
            html.Div([
                dcc.Dropdown(
                    id="routing-net-picker",
                    options=[{"label": n, "value": n} for n in routing_state.batch_net_names],
                    value=(routing_state.batch_net_names[0]
                           if routing_state.batch_net_names else None),
                    placeholder="Pick a net to visualize…",
                    className="dropdown",
                    style={"marginBottom": "8px"},
                ),
                dcc.Graph(id="routing-graph", style={"height": "500px"}),
            ], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Per-net table
        html.Div([
            html.Div("Per-Net Results", className="card-header"),
            html.Div([_build_similarity_table()], className="card-body"),
        ], className="card", style={"marginBottom": "16px"}),

        # Report export trigger
        html.Div([
            html.Button("Generate Routing Report (PPTX)", id="btn-gen-routing-pptx",
                        className="btn btn-success btn-block",
                        disabled=True,
                        title="Run a routing review first (Routing Config tab)"),
            html.Div(id="routing-report-status"),
            dcc.Download(id="download-routing-pptx"),
        ]),
    ], style={"padding": "16px"})


def _empty_state_banner():
    """Empty-state hint shown above the metric cards."""
    if routing_state.review_completed and routing_state.batch_results:
        return ""  # Have results — no banner needed
    if not app_state.nets_data:
        return html.Div([
            html.Div([
                html.Span("ℹ ", style={"fontWeight": "600"}),
                html.Span("No nets loaded yet. ", style={"fontWeight": "600"}),
                html.Span("Open the ", style={}),
                html.B("Layout View"),
                html.Span(" tab, upload shape files or a YAML batch config, then "
                          "return here and set the regex on the "),
                html.B("Routing Config"),
                html.Span(" tab."),
            ], style={"fontSize": "12px"}),
        ], className="alert",
           style={"background": "var(--bg-input)", "border": "1px solid var(--border-color)",
                  "borderRadius": "6px", "padding": "10px 12px", "marginBottom": "16px",
                  "color": "var(--text-muted)"})
    return html.Div([
        html.Div([
            html.Span("ℹ ", style={"fontWeight": "600"}),
            html.Span("Nets loaded but no review run yet. ", style={"fontWeight": "600"}),
            html.Span(f"({len(app_state.nets_data)} nets from Layout View) "),
            html.Span("Go to the "),
            html.B("Routing Config"),
            html.Span(" tab, set a Batch Net Regex, then click "),
            html.B("Run Routing Review"),
            html.Span("."),
        ], style={"fontSize": "12px"}),
    ], className="alert",
       style={"background": "var(--bg-input)", "border": "1px solid var(--border-color)",
              "borderRadius": "6px", "padding": "10px 12px", "marginBottom": "16px",
              "color": "var(--text-muted)"})


def _resolve_regex(pattern: str) -> List[str]:
    """Resolve a regex against app_state.nets_data; return matched net names."""
    if not pattern:
        return []
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return []
    return [n for n in app_state.nets_data if rx.search(n)]


def _compute_violations_for_net(metrics: Dict[str, Any], thresholds) -> List[RoutingViolation]:
    """Convert gate failures into structured violations with location."""
    v = []
    if metrics["h_ratio"] > thresholds.max_h_ratio:
        v.append(RoutingViolation.h_ratio(metrics["net_name"], metrics["h_ratio"], thresholds.max_h_ratio))
    if metrics["v_ratio"] > thresholds.max_v_ratio:
        v.append(RoutingViolation.v_ratio(metrics["net_name"], metrics["v_ratio"], thresholds.max_v_ratio))
    if metrics["r_total"] > thresholds.max_r_ohm:
        v.append(RoutingViolation.r_total(metrics["net_name"], metrics["r_total"], thresholds.max_r_ohm))
    if metrics["c_total"] > thresholds.max_c_ff:
        v.append(RoutingViolation.c_total(metrics["net_name"], metrics["c_total"], thresholds.max_c_ff))
    if metrics["effective_tau_ps"] > thresholds.max_tau_ps:
        v.append(RoutingViolation.tau_ps(metrics["net_name"], metrics["effective_tau_ps"], thresholds.max_tau_ps))
    if metrics["via_coverage"] < thresholds.min_via_coverage:
        v.append(RoutingViolation.via_coverage(metrics["net_name"], metrics["via_coverage"], thresholds.min_via_coverage))
    if metrics["similarity_score"] < thresholds.min_similarity:
        v.append(RoutingViolation.similarity(metrics["net_name"], metrics["similarity_score"], thresholds.min_similarity))
    for loc in metrics.get("missing_locations", []):
        v.append(RoutingViolation.missing_via(metrics["net_name"], loc["x"], loc["y"],
                                              f"{loc['layer_a']}/{loc['layer_b']}"))
    return v


def register_routing_review_callbacks(app):
    """Register all callbacks for the routing Layout Review tab."""
    import plotly.graph_objects as go
    from dash import Input, Output, callback_context, no_update

    # --- 0. Refresh the empty-state banner when the user switches to this tab
    #         or when a tick passes while the tab is visible. Keeps the
    #         "loaded but not reviewed" message in sync with Layout View. ---
    @app.callback(
        Output("routing-review-empty", "children"),
        [Input("tabs", "value"),
         Input("interval-component", "n_intervals")],
    )
    def _refresh_empty_banner(tab, _n):
        if tab not in (None, "tab-routing-review"):
            return no_update
        return _empty_state_banner()

    # --- 0b. Threshold source banner — keeps "当前阈值来源: xxx" in sync
    #         with Routing Config (preset + frozen/custom via get_threshold_source).
    @app.callback(
        Output("routing-threshold-source", "children"),
        [Input("tabs", "value"),
         Input("interval-component", "n_intervals")],
    )
    def _refresh_threshold_source(tab, _n):
        if tab not in (None, "tab-routing-review"):
            return no_update
        return _build_threshold_source()

    # --- 0a. Error banner — driven by routing_state.last_error. ---
    @app.callback(
        [Output("routing-error-banner", "style"),
         Output("routing-error-text", "children")],
        [Input("interval-component", "n_intervals"),
         Input("tabs", "value"),
         Input("btn-dismiss-error", "n_clicks")],
    )
    def _refresh_error_banner(_n, tab, dismiss_clicks):
        ctx = callback_context
        trigger_id = (
            ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
        )

        if trigger_id == "btn-dismiss-error" and dismiss_clicks:
            routing_state.last_error = ""

        if tab not in (None, "tab-routing-review"):
            return no_update, no_update

        err = routing_state.last_error
        if not err:
            return _ERROR_BANNER_HIDDEN, ""
        return _ERROR_BANNER_VISIBLE, err

    @app.callback(
        [Output("routing-graph", "figure"),
         Output("routing-results-table", "data"),
         Output("routing-results-table", "style_data_conditional"),
         Output("routing-net-picker", "options"),
         Output("routing-metric-cards", "children"),
         Output("routing-config-status", "children", allow_duplicate=True),
         # Tab navigation: the routing_config companion callback that
         # used to do this is being removed; we own it now.
         Output("tabs", "value", allow_duplicate=True)],
        [Input("btn-run-routing-review", "n_clicks"),
         Input("routing-net-picker", "value")],
        prevent_initial_call=True,
    )
    def update_routing_review(run_clicks, selected_net):
        from dash import callback_context
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        # Picker-only change: just refresh the directional viz, don't
        # rebuild the table/cards/dropdown. Avoids stutter on every
        # dropdown click.
        if trigger == "routing-net-picker":
            if selected_net and selected_net in app_state.nets_data:
                net_data = app_state.nets_data[selected_net]
                polys = net_data.get("polygons", [])
                metals, vias = split_metal_via_polygons(polys)
                m = routing_state.batch_results.get(selected_net)
                if m:
                    fig = create_directional_figure(
                        polygons=metals, vias=vias,
                        net_name=selected_net,
                        per_polygon_dir=m.get("per_polygon_dir", []),
                        violations=[
                            # polygon_index falls back to 0 until via_coverage
                            # exposes per-location origins.
                            {"polygon_index": loc.get("polygon_index", 0),
                             "x": loc["x"], "y": loc["y"]}
                            for loc in m.get("missing_locations", [])
                        ],
                    )
                else:
                    fig = go.Figure()
            else:
                fig = go.Figure()
            return (fig, no_update, no_update, no_update, no_update,
                    no_update, no_update)

        # Run-button path: full rebuild of table/cards + navigate to tab
        if trigger == "btn-run-routing-review":
            try:
                _run_routing_review()
                status = f"Reviewed {len(routing_state.batch_results)} nets, golden={routing_state.golden_net_name or '(none)'}"
            except Exception as e:
                routing_state.last_error = str(e)
                status = f"Error: {e}"
        else:
            status = f"Reviewed {len(routing_state.batch_results)} nets"

        # Visualization (default to first batch net if picker is empty)
        viz_net = selected_net
        if not viz_net and routing_state.batch_net_names:
            viz_net = routing_state.batch_net_names[0]
        if viz_net and viz_net in app_state.nets_data:
            net_data = app_state.nets_data[viz_net]
            polys = net_data.get("polygons", [])
            metals, vias = split_metal_via_polygons(polys)
            m = routing_state.batch_results.get(viz_net)
            if m:
                fig = create_directional_figure(
                    polygons=metals, vias=vias,
                    net_name=viz_net,
                    per_polygon_dir=m.get("per_polygon_dir", []),
                    violations=[
                        # polygon_index falls back to 0 until via_coverage
                        # exposes per-location origins.
                        {"polygon_index": loc.get("polygon_index", 0),
                         "x": loc["x"], "y": loc["y"]}
                        for loc in m.get("missing_locations", [])
                    ],
                )
            else:
                fig = go.Figure()
        else:
            fig = go.Figure()

        # Table + dropdown + metric cards
        rows = _build_table_rows(routing_state.batch_results)
        style_data_conditional = _compute_table_styles(rows)
        opts = [{"label": n, "value": n} for n in routing_state.batch_net_names]
        metric_cards = _build_metric_cards(routing_state.batch_results)
        return (fig, rows, style_data_conditional, opts, metric_cards,
                status, "tab-routing-review")

    @app.callback(
        Output("btn-gen-routing-pptx", "disabled"),
        [Input("btn-run-routing-review", "n_clicks"),
         Input("tabs", "value")],
    )
    def update_pptx_button_state(_run_clicks, tab):
        if tab not in (None, "tab-routing-review"):
            return no_update
        return not routing_state.review_completed

    @app.callback(
        Output("download-routing-pptx", "data"),
        Input("btn-gen-routing-pptx", "n_clicks"),
        prevent_initial_call=True,
    )
    def gen_pptx(n):
        if not n or not routing_state.review_completed:
            raise PreventUpdate
        try:
            import os
            import tempfile

            from report.routing_pptx import generate_routing_pptx
            # mkstemp (not a fixed path) avoids Windows PermissionError
            # when two tabs / two rapid clicks collide on the same filename.
            fd, out = tempfile.mkstemp(suffix=".pptx", prefix="routing_report_")
            os.close(fd)
            generate_routing_pptx(routing_state, app_state, out)
            return dcc.send_file(out, filename="routing_report.pptx")
        except Exception as e:
            routing_state.last_error = f"PPTX generation failed: {e}"
            return no_update


def _run_routing_review():
    """Resolve regex, compute metrics for golden + batch, populate state."""
    routing_state.reset_review()
    golden_names = _resolve_regex(routing_state.golden_regex)
    batch_names = _resolve_regex(routing_state.batch_regex)
    if not batch_names:
        raise ValueError("No batch nets matched. Check the Batch Net Regex in Configuration.")

    tech_layers = app_state.config.tech_config.layers
    thresholds = routing_state.get_thresholds()
    # Default RC path must match Layout View Properties:
    # use legacy tech_layers + calculate_net_rc + lumped tau (rc_model=None).
    # Only pass an RCModelConfig when the user has explicitly set a custom model.
    rc_model_to_use = routing_state.custom_rc_model if routing_state.custom_rc_model else None

    # Compute golden first (if present)
    golden_metrics = None
    golden_name = ""
    if golden_names:
        golden_name = golden_names[0]
        g_data = app_state.nets_data[golden_name]
        g_polys = g_data.get("polygons", [])
        g_metals, g_vias = split_metal_via_polygons(g_polys)
        m = compute_for_net(golden_name, g_metals, g_vias, tech_layers, thresholds,
                            golden_metrics=None, rc_model=rc_model_to_use)
        golden_metrics = {k: m[k] for k in ("h_ratio", "v_ratio", "total_len", "via_count",
                                            "r_total", "c_total", "effective_tau_ps", "bbox_aspect")}
        routing_state.golden_net_name = golden_name
        routing_state.golden_metrics = golden_metrics

    # De-dup: prevent the golden net from being reported twice (once as
    # golden, once in the batch table). The golden's metrics are already
    # accessible via routing_state.golden_metrics; including it in
    # batch_results would also re-run similarity against itself (100%)
    # and pollute the pass/fail counts.
    if golden_name and golden_name in batch_names:
        batch_names = [n for n in batch_names if n != golden_name]

    # Compute batch
    for name in batch_names:
        data = app_state.nets_data[name]
        polys = data.get("polygons", [])
        metals, vias = split_metal_via_polygons(polys)
        m = compute_for_net(name, metals, vias, tech_layers, thresholds,
                            golden_metrics=golden_metrics, rc_model=rc_model_to_use)
        m["violations"] = [vv.to_dict() for vv in _compute_violations_for_net(m, thresholds)]
        routing_state.batch_results[name] = m

    routing_state.batch_net_names = batch_names
    routing_state.review_completed = True
