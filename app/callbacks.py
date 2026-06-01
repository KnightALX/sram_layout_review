"""Dash application callbacks for interactivity."""

import base64
import os
import re

from dash import Dash, html, Input, Output, State, callback_context
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go

from app.state import app_state
from core.data_parsing import parse_shape_txt, import_shape_from_file
from core.visualization import create_net_visualization
from core.path_analysis import get_view_for_visible_layers


def natural_sort_key(s):
    """Natural sort key for numeric strings.

    Enables sorting like: net1, net2, net10, net20 (not net1, net10, net2, net20)
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def register_callbacks(app: Dash):
    """Register all Dash callbacks on the application.

    Args:
        app: Dash application instance
    """

    # =========================================================================
    # Net Selector Callbacks
    # =========================================================================

    @app.callback(
        [Output('upload-status', 'children'),
         Output('yaml-upload-status', 'children'),
         Output('net-selector', 'options'),
         Output('net-selector', 'value'),
         Output('net-count-badge', 'children')],
        [Input('upload-data', 'contents'),
         Input('upload-yaml', 'contents'),
         Input('net-filter', 'value'),
         Input('btn-select-all', 'n_clicks'),
         Input('btn-clear', 'n_clicks')],
        [State('upload-data', 'filename'),
         State('upload-yaml', 'filename')],
        prevent_initial_call=True
    )
    def update_net_selector(contents, yaml_content, filter_text, select_all, clear,
                            filenames, yaml_filename):
        """Update net selector - handles file upload, YAML batch import, filtering, select all/clear."""
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        # Handle shape file upload
        if trigger_id == 'upload-data':
            if not contents:
                raise PreventUpdate

            imported = 0
            for content, filename in zip(contents, filenames):
                try:
                    content_type, content_string = content.split(',')
                    decoded = base64.b64decode(content_string).decode('utf-8')

                    result = parse_shape_txt(decoded, filename)
                    if result:
                        net_name, shapes_data, polygons = result
                        app_state.nets_data[net_name] = {
                            'shapes': shapes_data,
                            'polygons': polygons,
                            'filename': filename
                        }
                        imported += 1
                except Exception as e:
                    print(f"Error importing {filename}: {e}")

            if app_state.nets_data:
                from review_engine import ProfessionalLayoutReviewEngine
                app_state.engine = ProfessionalLayoutReviewEngine(app_state.config)
                for net_name, data in app_state.nets_data.items():
                    app_state.engine.add_net_polygons(net_name, data['polygons'])
                # Calculate RC for all imported nets
                for net_name in app_state.nets_data.keys():
                    app_state.engine.calculate_net_rc(net_name)

            status = f"Imported {imported} files"
            options = [{'label': name, 'value': name} for name in
                       sorted(app_state.nets_data.keys(), key=natural_sort_key)]

            return status, "", options, [], f"{len(app_state.nets_data)} nets"

        # Handle YAML batch import
        if trigger_id == 'upload-yaml':
            if not yaml_content:
                raise PreventUpdate

            try:
                content_type, content_string = yaml_content.split(',')
                decoded = base64.b64decode(content_string).decode('utf-8')

                try:
                    import yaml
                except ImportError:
                    return "", "PyYAML not installed. Run: pip install pyyaml", [], [], "0 nets"

                # Handle empty YAML content
                if not decoded.strip():
                    return "", "Error: YAML file is empty", [], [], "0 nets"

                yaml_config = yaml.safe_load(decoded)

                # Validate yaml_config is a dict with 'shapes'
                if not isinstance(yaml_config, dict):
                    return "", "Error: Invalid YAML format - expected a dictionary", [], [], "0 nets"

                if 'shapes' not in yaml_config:
                    return "", "Error: Missing 'shapes' key in YAML", [], [], "0 nets"

                options_cfg = yaml_config.get('options', {})
                auto_prefix = options_cfg.get('auto_prefix', '')
                clear_existing = options_cfg.get('clear_existing', False)
                skip_missing = options_cfg.get('skip_missing', True)

                if clear_existing:
                    app_state.nets_data.clear()

                imported = 0
                failed_files = []
                shapes_list = yaml_config.get('shapes', [])

                for shape_item in shapes_list:
                    if isinstance(shape_item, dict):
                        filepath = shape_item.get('file', '')
                        custom_net_name = shape_item.get('net_name')
                    elif isinstance(shape_item, str):
                        filepath = shape_item
                        custom_net_name = None
                    else:
                        continue

                    filepath = os.path.expanduser(filepath)

                    if not os.path.exists(filepath):
                        # Track failed files for better user feedback
                        failed_files.append(os.path.basename(filepath))
                        if skip_missing:
                            continue
                        else:
                            return "", f"File not found: {filepath}", [], [], f"{len(app_state.nets_data)} nets"

                    if custom_net_name and auto_prefix:
                        custom_net_name = auto_prefix + custom_net_name

                    result = import_shape_from_file(filepath, custom_net_name)
                    if result:
                        app_state.nets_data[result['net_name']] = {
                            'shapes': result['shapes'],
                            'polygons': result['polygons'],
                            'filename': result['filename']
                        }
                        imported += 1
                    else:
                        failed_files.append(os.path.basename(filepath))

                if app_state.nets_data:
                    from review_engine import ProfessionalLayoutReviewEngine
                    app_state.engine = ProfessionalLayoutReviewEngine(app_state.config)
                    for net_name, data in app_state.nets_data.items():
                        app_state.engine.add_net_polygons(net_name, data['polygons'])
                    # Calculate RC for all imported nets
                    for net_name in app_state.nets_data.keys():
                        app_state.engine.calculate_net_rc(net_name)

                # Build informative status message
                total = len(shapes_list)
                if failed_files:
                    yaml_status = f"YAML batch: {imported}/{total} files imported, {len(failed_files)} failed: {', '.join(failed_files[:3])}{'...' if len(failed_files) > 3 else ''}"
                else:
                    yaml_status = f"YAML batch: {imported}/{total} files imported successfully"

                options = [{'label': name, 'value': name} for name in
                          sorted(app_state.nets_data.keys(), key=natural_sort_key)]

                return "", yaml_status, options, [], f"{len(app_state.nets_data)} nets"

            except yaml.YAMLError as e:
                error_msg = f"YAML parse error: {str(e)[:100]}"
                return "", error_msg, [], [], f"{len(app_state.nets_data)} nets"
            except Exception as e:
                error_msg = f"Error: {str(e)[:100]}"
                return "", error_msg, [], [], f"{len(app_state.nets_data)} nets"

        # Handle filter, select all, clear
        all_nets = sorted(app_state.nets_data.keys(), key=natural_sort_key)

        if trigger_id == 'net-filter':
            if filter_text:
                try:
                    pattern = re.compile(filter_text, re.IGNORECASE)
                    filtered = [n for n in all_nets if pattern.search(n)]
                except re.error:
                    filtered = all_nets
            else:
                filtered = all_nets
            options = [{'label': n, 'value': n} for n in filtered]
            return "", "", options, [], f"{len(app_state.nets_data)} nets"

        elif trigger_id == 'btn-select-all':
            options = [{'label': n, 'value': n} for n in all_nets]
            return "", "", options, all_nets, f"{len(app_state.nets_data)} nets"

        elif trigger_id == 'btn-clear':
            options = [{'label': n, 'value': n} for n in all_nets]
            return "", "", options, [], f"{len(app_state.nets_data)} nets"

        raise PreventUpdate

    # =========================================================================
    # Layout Graph Callback
    # =========================================================================

    @app.callback(
        [Output('path-config-status', 'children'),
         Output('layout-graph', 'figure'),
         Output('zoom-level', 'children')],
        [Input('net-selector', 'value'),
         Input('btn-apply-path-config', 'n_clicks'),
         Input('btn-canvas-fit', 'n_clicks'),
         Input('btn-canvas-zoom-in', 'n_clicks'),
         Input('btn-canvas-zoom-out', 'n_clicks'),
         Input('btn-all-layer', 'n_clicks'),
         Input('btn-no-layer', 'n_clicks'),
         Input('btn-fit', 'n_clicks'),
         Input('btn-zoom-in', 'n_clicks'),
         Input('btn-zoom-out', 'n_clicks'),
         Input('btn-pan-up', 'n_clicks'),
         Input('btn-pan-down', 'n_clicks'),
         Input('btn-pan-left', 'n_clicks'),
         Input('btn-pan-right', 'n_clicks')],
        [State('sd-layers', 'value'),
         State('poly-layers', 'value')],
        prevent_initial_call=True
    )
    def update_layout_graph(selected_nets, path_config_clicks, btn_fit, btn_zoom_in,
                           btn_zoom_out, btn_all_layer, btn_no_layer,
                           btn_fit_sidebar, btn_zoom_in_sidebar, btn_zoom_out_sidebar,
                           btn_pan_up, btn_pan_down, btn_pan_left, btn_pan_right,
                           sd_value, poly_value):
        """Update layout graph - handles path config, zoom, and layer visibility."""
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        # Handle path configuration button
        if trigger_id == 'btn-apply-path-config':
            if not path_config_clicks:
                raise PreventUpdate

            sd_layers = [s.strip() for s in sd_value.split(',') if s.strip()]
            poly_layers = [s.strip() for s in poly_value.split(',') if s.strip()]

            app_state.sd_layers = sd_layers
            app_state.poly_layers = poly_layers
            app_state.path_configured = True

            status = f"SD: {', '.join(sd_layers)} -> Gate: {', '.join(poly_layers)}"

            if selected_nets:
                fig = create_net_visualization(selected_nets)
            else:
                fig = go.Figure()

            zoom_display = f"{app_state.zoom_level:.2f}x"
            return status, fig, zoom_display

        # Other triggers
        if not selected_nets:
            return "", go.Figure(), "1.00x"

        # Collect all layers
        all_layers = set()
        for net_name in selected_nets:
            if net_name in app_state.nets_data:
                shapes_data = app_state.nets_data[net_name].get('shapes', {})
                all_layers.update(shapes_data.keys())

        if app_state.visible_layers is None:
            app_state.visible_layers = all_layers.copy()

        # Handle button events - zoom/pan handlers
        if trigger_id in ('btn-canvas-fit', 'btn-fit'):
            app_state.zoom_level = 1.0
            app_state.current_view = None
            fig = create_net_visualization(selected_nets, mode='fit')

        elif trigger_id in ('btn-canvas-zoom-in', 'btn-zoom-in'):
            if app_state.current_view is None:
                app_state.current_view = get_view_for_visible_layers(
                    selected_nets, app_state.visible_layers)

            if app_state.current_view:
                x_center = (app_state.current_view['x_min'] + app_state.current_view['x_max']) / 2
                y_center = (app_state.current_view['y_min'] + app_state.current_view['y_max']) / 2
                x_range = (app_state.current_view['x_max'] - app_state.current_view['x_min']) / app_state.zoom_step
                y_range = (app_state.current_view['y_max'] - app_state.current_view['y_min']) / app_state.zoom_step
                app_state.current_view = {
                    'x_min': x_center - x_range/2,
                    'x_max': x_center + x_range/2,
                    'y_min': y_center - y_range/2,
                    'y_max': y_center + y_range/2,
                }
                app_state.zoom_level = min(app_state.zoom_level * app_state.zoom_step, 100.0)
            fig = create_net_visualization(selected_nets, mode='zoom_in')

        elif trigger_id in ('btn-canvas-zoom-out', 'btn-zoom-out'):
            if app_state.current_view is None:
                app_state.current_view = get_view_for_visible_layers(
                    selected_nets, app_state.visible_layers)

            if app_state.current_view:
                x_center = (app_state.current_view['x_min'] + app_state.current_view['x_max']) / 2
                y_center = (app_state.current_view['y_min'] + app_state.current_view['y_max']) / 2
                x_range = (app_state.current_view['x_max'] - app_state.current_view['x_min']) * app_state.zoom_step
                y_range = (app_state.current_view['y_max'] - app_state.current_view['y_min']) * app_state.zoom_step
                app_state.current_view = {
                    'x_min': x_center - x_range/2,
                    'x_max': x_center + x_range/2,
                    'y_min': y_center - y_range/2,
                    'y_max': y_center + y_range/2,
                }
                app_state.zoom_level = max(app_state.zoom_level / app_state.zoom_step, 0.01)
            fig = create_net_visualization(selected_nets, mode='zoom_out')

        elif trigger_id in ('btn-pan-up', 'btn-pan-down', 'btn-pan-left', 'btn-pan-right'):
            if app_state.current_view is None:
                app_state.current_view = get_view_for_visible_layers(
                    selected_nets, app_state.visible_layers)

            if app_state.current_view:
                x_range = app_state.current_view['x_max'] - app_state.current_view['x_min']
                y_range = app_state.current_view['y_max'] - app_state.current_view['y_min']
                pan_step = 0.15

                if trigger_id == 'btn-pan-up':
                    y_shift = y_range * pan_step
                    app_state.current_view = {
                        'x_min': app_state.current_view['x_min'],
                        'x_max': app_state.current_view['x_max'],
                        'y_min': app_state.current_view['y_min'] + y_shift,
                        'y_max': app_state.current_view['y_max'] + y_shift,
                    }
                elif trigger_id == 'btn-pan-down':
                    y_shift = y_range * pan_step
                    app_state.current_view = {
                        'x_min': app_state.current_view['x_min'],
                        'x_max': app_state.current_view['x_max'],
                        'y_min': app_state.current_view['y_min'] - y_shift,
                        'y_max': app_state.current_view['y_max'] - y_shift,
                    }
                elif trigger_id == 'btn-pan-left':
                    x_shift = x_range * pan_step
                    app_state.current_view = {
                        'x_min': app_state.current_view['x_min'] - x_shift,
                        'x_max': app_state.current_view['x_max'] - x_shift,
                        'y_min': app_state.current_view['y_min'],
                        'y_max': app_state.current_view['y_max'],
                    }
                elif trigger_id == 'btn-pan-right':
                    x_shift = x_range * pan_step
                    app_state.current_view = {
                        'x_min': app_state.current_view['x_min'] + x_shift,
                        'x_max': app_state.current_view['x_max'] + x_shift,
                        'y_min': app_state.current_view['y_min'],
                        'y_max': app_state.current_view['y_max'],
                    }
            fig = create_net_visualization(selected_nets, mode='zoom_in')

        elif trigger_id == 'btn-all-layer':
            app_state.visible_layers = all_layers.copy()
            app_state.current_view = None
            fig = create_net_visualization(selected_nets, mode='fit')

        elif trigger_id == 'btn-no-layer':
            app_state.visible_layers = set()
            fig = create_net_visualization(selected_nets, mode='fit')

        else:
            fig = create_net_visualization(selected_nets, mode='fit')

        status = ""
        if app_state.path_configured:
            status = f"SD: {', '.join(app_state.sd_layers)} -> Gate: {', '.join(app_state.poly_layers)}"

        zoom_display = f"{app_state.zoom_level:.2f}x"
        return status, fig, zoom_display

    # =========================================================================
    # Properties Panel Callbacks
    # =========================================================================

    @app.callback(
        [Output('prop-net-name', 'children'),
         Output('prop-layer-count', 'children'),
         Output('prop-shape-count', 'children'),
         Output('prop-resistance', 'children'),
         Output('prop-capacitance', 'children'),
         Output('prop-length', 'children'),
         Output('prop-tau-rc', 'children'),
         Output('prop-tpd', 'children'),
         Output('prop-critical', 'children'),
         Output('prop-warnings', 'children'),
         Output('prop-info', 'children')],
        [Input('net-selector', 'value')]
    )
    def update_properties_panel(selected_nets):
        """Update properties panel with selected net info."""
        # 返回11个值: net_name, layer_count, shape_count, resistance, capacitance,
        #           length, tau_rc, tpd, critical, warnings, info
        if not selected_nets or len(selected_nets) != 1:
            return ['--'] + ['0'] * 10

        net_name = selected_nets[0]
        if net_name not in app_state.nets_data:
            return [net_name] + ['0'] * 10

        data = app_state.nets_data[net_name]
        shapes = data['shapes']
        total_polys = sum(len(p) for p in shapes.values())

        # Get RC data if engine exists
        resistance = '0 Ω'
        capacitance = '0 fF'
        length = '0 μm'
        tau_rc = '0 ns'
        tpd = '0 ns'

        if app_state.engine and hasattr(app_state.engine, 'net_rc_data'):
            if net_name in app_state.engine.net_rc_data:
                rc_data = app_state.engine.net_rc_data[net_name]
                resistance = f"{rc_data.total_resistance:.2f} Ω"
                capacitance = f"{rc_data.total_capacitance:.2f} fF"
                length = f"{rc_data.total_length:.2f} μm"
                tau_rc = f"{rc_data.tau_rc:.4f} ns"
                tpd = f"{rc_data.tpd_50:.4f} ns"

        # Count violations
        critical = '0'
        warnings = '0'
        info = '0'

        if app_state.engine and hasattr(app_state.engine, 'violations'):
            for v in app_state.engine.violations:
                if v.net_name == net_name:
                    if v.severity.value == 'critical':
                        critical = str(int(critical) + 1)
                    elif v.severity.value == 'warning':
                        warnings = str(int(warnings) + 1)
                    else:
                        info = str(int(info) + 1)

        return (net_name, str(len(shapes)), str(total_polys),
                resistance, capacitance, length,
                tau_rc, tpd,
                critical, warnings, info)

    # =========================================================================
    # Configuration Tab Callbacks
    # =========================================================================
    # Export Callbacks
    # =========================================================================

    @app.callback(
        Output('export-status', 'children'),
        [Input('btn-generate-report', 'n_clicks')]
    )
    def generate_report(btn_clicks):
        """Generate PPTX and PDF reports."""
        ctx = callback_context
        if not ctx.triggered:
            raise PreventUpdate

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        n_clicks = btn_clicks
        if not n_clicks or not app_state.engine:
            raise PreventUpdate

        if not app_state.review_completed:
            return html.Div("Please run a review first before generating reports.", className="alert alert-warning")

        try:
            from report_generator import generate_reports

            pptx_path, pdf_path = generate_reports(
                app_state.engine,
                "./output",
                base_name="layout_review_report"
            )

            status = html.Div([
                html.H5("Reports Generated Successfully!", className="alert-heading"),
                html.Hr(),
                html.P(f"PPTX: {pptx_path}"),
                html.P(f"PDF: {pdf_path}" if pdf_path else "PDF: Not available (reportlab required)"),
            ], className="alert alert-success")

            return status

        except Exception as e:
            return html.Div(f"Error generating reports: {str(e)}", className="alert alert-danger")

    # ---------------------------------------------------------------------
    # Routing review tab callbacks (replaces old Configuration + Review tabs)
    # ---------------------------------------------------------------------
    from app.routing_config import register_routing_config_callbacks
    from app.routing_review import register_routing_review_callbacks
    register_routing_config_callbacks(app)
    register_routing_review_callbacks(app)
