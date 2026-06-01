"""Routing-focused Layout Review tab.

Replaces `_create_review_content()` from `app/layout.py`.
Shows the 6 metric cards + sortable similarity table + per-net directional viz.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any
from dash import html, dcc, dash_table
from app.routing_state import routing_state
from app.state import app_state  # for accessing loaded nets/polygons
from core.routing_metrics import compute_for_net
from core.routing_violation import RoutingViolation, ViolationKind
from core.visualization import create_directional_figure


METRIC_CARD_IDS = [
    ("h_ratio", "H / V Ratio", "%"),
    ("missing_via", "Missing Via", ""),
    ("r_total", "Eff. R (Ω)", "Ω"),
    ("tau_ps", "Eff. τ (ps)", "ps"),
    ("similarity", "Similarity", "/100"),
    ("gate", "Pass / Fail", ""),
]


def _build_metric_cards(results: Dict[str, Dict[str, Any]]) -> List[html.Div]:
    """Build the 6 summary cards (averages across batch)."""
    if not results:
        avg = {"h_ratio": 0, "v_ratio": 0, "missing_via": 0, "r_total": 0,
               "tau_ps": 0, "similarity": 0, "gate": 0}
    else:
        n = len(results)
        avg = {
            "h_ratio": sum(r["h_ratio"] for r in results.values()) / n,
            "v_ratio": sum(r["v_ratio"] for r in results.values()) / n,
            "missing_via": sum(r["missing_via_count"] for r in results.values()) / n,
            "r_total": sum(r["r_total"] for r in results.values()) / n,
            "tau_ps": sum(r["effective_tau_ps"] for r in results.values()) / n,
            "similarity": sum(r["similarity_score"] for r in results.values()) / n,
            "gate": sum(1 for r in results.values() if r["gate_pass"]) / n * 100,
        }
    cards = []
    for key, label, unit in METRIC_CARD_IDS:
        if key in ("h_ratio", "v_ratio"):
            value = f"{avg[key]*100:.1f}%"
        elif key == "missing_via":
            value = f"{avg[key]:.1f}"
        elif key == "r_total":
            value = f"{avg[key]:.2f}Ω"
        elif key == "tau_ps":
            value = f"{avg[key]:.2f}ps"
        elif key == "similarity":
            value = f"{avg[key]:.1f}/100"
        else:  # gate
            value = f"{avg[key]:.0f}%"
        cards.append(html.Div([
            html.Div(label, className="metric-label",
                     style={"fontSize": "11px", "color": "#888"}),
            html.Div(value, className="metric-value",
                     style={"fontSize": "20px", "fontWeight": "600"}),
        ], className="metric-card", style={
            "flex": "1", "padding": "12px", "background": "var(--bg-input)",
            "border": "1px solid var(--border-color)", "borderRadius": "6px",
            "minWidth": "120px",
        }))
    return cards


def _build_similarity_table() -> dash_table.DataTable:
    """Build the per-net sortable results table."""
    rows = []
    for name, m in routing_state.batch_results.items():
        rows.append({
            "Net": name,
            "Dominant": m["dominant"],
            "H %": f"{m['h_ratio']*100:.1f}",
            "V %": f"{m['v_ratio']*100:.1f}",
            "R (Ω)": f"{m['r_total']:.2f}",
            "τ (ps)": f"{m['effective_tau_ps']:.2f}",
            "Via Cov": f"{m['via_coverage']*100:.1f}",
            "Miss Via": m["missing_via_count"],
            "Sim": f"{m['similarity_score']:.1f}",
            "Pass": "✓" if m["gate_pass"] else "✗",
        })
    return dash_table.DataTable(
        data=rows,
        columns=[{"name": k, "id": k} for k in
                 ("Net", "Dominant", "H %", "V %", "R (Ω)", "τ (ps)",
                  "Via Cov", "Miss Via", "Sim", "Pass")],
        sort_action="native", filter_action="native",
        row_selectable="single", page_size=10,
        style_cell={"textAlign": "left", "fontSize": "11px"},
        style_data_conditional=[
            {"if": {"filter_query": '{Pass} = "✗"'}, "backgroundColor": "rgba(239, 68, 68, 0.15)"},
            {"if": {"filter_query": '{Pass} = "✓"'}, "backgroundColor": "rgba(34, 197, 94, 0.10)"},
        ],
        id="routing-results-table",
    )


def create_routing_review_tab():
    """Build the routing Layout Review tab content."""
    return html.Div([
        # Summary cards
        html.Div(_build_metric_cards(routing_state.batch_results),
                 style={"display": "flex", "gap": "12px", "marginBottom": "16px"}),

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
                        className="btn btn-success btn-block"),
            html.Div(id="routing-report-status"),
            dcc.Download(id="download-routing-pptx"),
        ]),
    ], style={"padding": "16px"})


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
    from dash import Input, Output
    import plotly.graph_objects as go

    @app.callback(
        [Output("routing-graph", "figure"),
         Output("routing-results-table", "data"),
         Output("routing-net-picker", "options"),
         Output("routing-config-status", "children")],
        [Input("btn-run-routing-review", "n_clicks"),
         Input("routing-net-picker", "value")],
    )
    def update_routing_review(run_clicks, selected_net):
        from dash import callback_context
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

        # Trigger review run
        if trigger == "btn-run-routing-review":
            try:
                _run_routing_review()
                status = f"Reviewed {len(routing_state.batch_results)} nets, golden={routing_state.golden_net_name or '(none)'}"
            except Exception as e:
                routing_state.last_error = str(e)
                status = f"Error: {e}"
        else:
            status = f"Reviewed {len(routing_state.batch_results)} nets"

        # Visualization
        if selected_net and selected_net in app_state.nets_data:
            net_data = app_state.nets_data[selected_net]
            polys = net_data.get("polygons", [])
            m = routing_state.batch_results.get(selected_net)
            if m:
                fig = create_directional_figure(
                    polygons=polys, vias=[],
                    net_name=selected_net,
                    per_polygon_dir=m.get("per_polygon_dir", []),
                    violations=[
                        {"polygon_index": 0, "x": loc["x"], "y": loc["y"]}
                        for loc in m.get("missing_locations", [])
                    ],
                )
            else:
                fig = go.Figure()
        else:
            fig = go.Figure()

        # Table + dropdown
        rows = []
        for name, mr in routing_state.batch_results.items():
            rows.append({
                "Net": name, "Dominant": mr["dominant"],
                "H %": f"{mr['h_ratio']*100:.1f}", "V %": f"{mr['v_ratio']*100:.1f}",
                "R (Ω)": f"{mr['r_total']:.2f}", "τ (ps)": f"{mr['effective_tau_ps']:.2f}",
                "Via Cov": f"{mr['via_coverage']*100:.1f}", "Miss Via": mr["missing_via_count"],
                "Sim": f"{mr['similarity_score']:.1f}",
                "Pass": "✓" if mr["gate_pass"] else "✗",
            })
        opts = [{"label": n, "value": n} for n in routing_state.batch_net_names]
        return fig, rows, opts, status

    @app.callback(
        Output("download-routing-pptx", "data"),
        Input("btn-gen-routing-pptx", "n_clicks"),
        prevent_initial_call=True,
    )
    def gen_pptx(n):
        if not n or not routing_state.review_completed:
            raise dash.exceptions.PreventUpdate
        from report.routing_pptx import generate_routing_pptx
        import tempfile, os
        out = os.path.join(tempfile.gettempdir(), "routing_report.pptx")
        generate_routing_pptx(routing_state, app_state, out)
        return dcc.send_file(out, filename="routing_report.pptx")


def _run_routing_review():
    """Resolve regex, compute metrics for golden + batch, populate state."""
    routing_state.reset_review()
    golden_names = _resolve_regex(routing_state.golden_regex)
    batch_names = _resolve_regex(routing_state.batch_regex)
    if not batch_names:
        raise ValueError("No batch nets matched. Check the Batch Net Regex in Configuration.")

    tech_layers = app_state.config.tech_config.layers
    thresholds = routing_state.get_thresholds()

    # Compute golden first (if present)
    golden_metrics = None
    golden_name = ""
    if golden_names:
        golden_name = golden_names[0]
        g_data = app_state.nets_data[golden_name]
        g_polys = g_data.get("polygons", [])
        g_vias = []  # to be populated when Via support is wired up
        m = compute_for_net(golden_name, g_polys, g_vias, tech_layers, thresholds,
                            golden_metrics=None)
        golden_metrics = {k: m[k] for k in ("h_ratio", "v_ratio", "total_len", "via_count",
                                            "r_total", "c_total", "effective_tau_ps", "bbox_aspect")}
        routing_state.golden_net_name = golden_name
        routing_state.golden_metrics = golden_metrics

    # Compute batch
    for name in batch_names:
        data = app_state.nets_data[name]
        polys = data.get("polygons", [])
        vias = []
        m = compute_for_net(name, polys, vias, tech_layers, thresholds,
                            golden_metrics=golden_metrics)
        m["violations"] = [vv.to_dict() for vv in _compute_violations_for_net(m, thresholds)]
        routing_state.batch_results[name] = m

    routing_state.batch_net_names = batch_names
    routing_state.review_completed = True
