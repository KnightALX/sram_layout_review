"""Visualization components for layout rendering."""

import random
from typing import List, Optional

import plotly.graph_objects as go

from core.layer_style import (
    LAYER_FILL_COLORS,
    is_via_layer,
)

VIA_STROKE_COLORS = {
    'via0': 'rgba(0, 60, 0, 1.0)',
    'via1': 'rgba(0, 0, 100, 1.0)',
    'via2': 'rgba(160, 60, 0, 1.0)',
    'via3': 'rgba(50, 0, 90, 1.0)',
    'via4': 'rgba(150, 0, 90, 1.0)',
    'via5': 'rgba(0, 100, 100, 1.0)',
    'via6': 'rgba(80, 50, 20, 1.0)',
    'via7': 'rgba(60, 80, 30, 1.0)',
    'via8': 'rgba(100, 0, 100, 1.0)',
}

LAYER_DISPLAY_NAMES = {
    'n_sd': 'N+ Diffusion',
    'ndiff': 'N+ Diffusion',
    'p_sd': 'P+ Diffusion',
    'pdiff': 'P+ Diffusion',
    'poly': 'Poly Gate',
    'gate': 'Gate',
    'nwell': 'N-Well',
    'pwell': 'P-Well',
    'm0': 'M0 (Local)',
    'met0': 'M0 (Local)',
    'm1': 'Metal 1',
    'met1': 'Metal 1',
    'met1a': 'Metal 1',
    'm2': 'Metal 2',
    'met2': 'Metal 2',
    'met2a': 'Metal 2',
    'm3': 'Metal 3',
    'met3': 'Metal 3',
    'met3a': 'Metal 3',
    'm4': 'Metal 4',
    'met4': 'Metal 4',
    'met4a': 'Metal 4',
    'm5': 'Metal 5',
    'met5': 'Metal 5',
    'met5a': 'Metal 5',
    'm6': 'Metal 6',
    'met6': 'Metal 6',
    'met6a': 'Metal 6',
    'm7': 'Metal 7',
    'met7': 'Metal 7',
    'met7a': 'Metal 7',
    'm8': 'Metal 8',
    'met8': 'Metal 8',
    'met8a': 'Metal 8',
    'via0': 'VIA 0',
    'v0': 'VIA 0',
    'via1': 'VIA 1',
    'v1': 'VIA 1',
    'via2': 'VIA 2',
    'v2': 'VIA 2',
    'via3': 'VIA 3',
    'v3': 'VIA 3',
    'via4': 'VIA 4',
    'v4': 'VIA 4',
    'via5': 'VIA 5',
    'v5': 'VIA 5',
    'via6': 'VIA 6',
    'via7': 'VIA 7',
    'via8': 'VIA 8',
}

LAYER_PRIORITY_ORDER = [
    'substrate', 'oxide', 'pwell', 'nwell',
    'p_sd', 'pdiff', 'pdiffusion',
    'n_sd', 'ndiff', 'ndiffusion',
    'poly', 'gate', 'polyg',
    'm0', 'met0', 'locali',
    'm1', 'met1', 'metal1', 'met1a',
    'via0', 'v0',
    'm2', 'met2', 'metal2', 'met2a',
    'via1', 'v1',
    'm3', 'met3', 'metal3', 'met3a',
    'via2', 'v2',
    'm4', 'met4', 'metal4', 'met4a',
    'via3', 'v3',
    'm5', 'met5', 'metal5', 'met5a',
    'via4', 'v4',
    'm6', 'met6', 'metal6', 'met6a',
    'via5', 'v5',
    'm7', 'met7', 'metal7', 'met7a',
    'via6', 'v6',
    'm8', 'met8', 'metal8', 'met8a',
    'via7', 'v7',
    'via8', 'v8',
]


# ============================================================================
# Layer Color Manager - Dynamic Color Generation
# ============================================================================

class LayerColorManager:
    """Layer color manager - auto-generates distinct colors for new layers."""

    def __init__(self):
        self.predefined_colors = set(LAYER_FILL_COLORS.values())
        self.dynamic_colors = {}
        self.used_rgb_colors = set()
        self.color_index = 0
        self.golden_angle = 137.5077640500378

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> tuple:
        """Convert HSV to RGB color.

        Args:
            h: Hue [0, 360)
            s: Saturation [0, 1]
            v: Value [0, 1]

        Returns:
            Tuple of (r, g, b) each in [0, 255]
        """
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if 0 <= h < 60:
            r, g, b = c, x, 0
        elif 60 <= h < 120:
            r, g, b = x, c, 0
        elif 120 <= h < 180:
            r, g, b = 0, c, x
        elif 180 <= h < 240:
            r, g, b = 0, x, c
        elif 240 <= h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return (
            int((r + m) * 255),
            int((g + m) * 255),
            int((b + m) * 255)
        )

    def _color_distance(self, rgb1: tuple, rgb2: tuple) -> float:
        """Calculate Euclidean distance between two RGB colors."""
        return sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)) ** 0.5

    def _is_color_too_similar(self, rgb: tuple, min_distance: float = 60.0) -> bool:
        """Check if color is too similar to existing colors."""
        for predefined_rgba in self.predefined_colors:
            try:
                parts = predefined_rgba.strip('rgba()').split(',')
                if len(parts) >= 3:
                    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                    if self._color_distance(rgb, (r, g, b)) < min_distance:
                        return True
            except (ValueError, IndexError):
                continue

        for used_rgb in self.used_rgb_colors:
            if self._color_distance(rgb, used_rgb) < min_distance:
                return True

        return False

    def _generate_color(self, layer_name: str) -> str:
        """Generate a distinct color for a new layer.

        Uses golden angle for uniform hue distribution with configurable
        saturation and value for via vs normal layers.
        """
        is_via = 'via' in layer_name.lower() or layer_name.lower() in [
            'v0', 'v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7', 'v8', 'v9'
        ]
        name_hash = hash(layer_name) % 360

        max_attempts = 50
        for attempt in range(max_attempts):
            hue = (name_hash + self.color_index * self.golden_angle) % 360

            if is_via:
                saturation = 0.85
                value = 0.35 + (attempt * 0.02)
                alpha = 0.90
            else:
                saturation = 0.75 + (attempt % 3) * 0.05
                value = 0.65 + (attempt % 4) * 0.04
                alpha = 0.70

            r, g, b = self._hsv_to_rgb(hue, saturation, value)

            min_distance = 50.0 if is_via else 70.0
            if not self._is_color_too_similar((r, g, b), min_distance):
                self.color_index += 1
                self.used_rgb_colors.add((r, g, b))
                return f'rgba({r}, {g}, {b}, {alpha})'

            self.color_index += 1

        r = random.randint(60, 200)
        g = random.randint(60, 200)
        b = random.randint(60, 200)
        self.used_rgb_colors.add((r, g, b))
        return f'rgba({r}, {g}, {b}, 0.70)'

    def get_color(self, layer_name: str) -> str:
        """Get color for layer (predefined or dynamically generated)."""
        if layer_name in LAYER_FILL_COLORS:
            return LAYER_FILL_COLORS[layer_name]

        if layer_name in self.dynamic_colors:
            return self.dynamic_colors[layer_name]

        new_color = self._generate_color(layer_name)
        self.dynamic_colors[layer_name] = new_color

        if layer_name not in LAYER_DISPLAY_NAMES:
            display_name = layer_name.replace('_', ' ').title()
            LAYER_DISPLAY_NAMES[layer_name] = display_name

        if 'via' in layer_name.lower() or layer_name.lower().startswith('v'):
            try:
                parts = new_color.strip('rgba()').split(',')
                if len(parts) >= 3:
                    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                    r = int(r * 0.6)
                    g = int(g * 0.6)
                    b = int(b * 0.6)
                    VIA_STROKE_COLORS[layer_name] = f'rgba({r}, {g}, {b}, 1.0)'
            except (ValueError, IndexError):
                VIA_STROKE_COLORS[layer_name] = 'rgba(50, 50, 50, 1.0)'

        return new_color

    def get_display_name(self, layer_name: str) -> str:
        """Get display name for layer."""
        if layer_name in LAYER_DISPLAY_NAMES:
            return LAYER_DISPLAY_NAMES[layer_name]
        display_name = layer_name.replace('_', ' ').title()
        LAYER_DISPLAY_NAMES[layer_name] = display_name
        return display_name


# Global color manager instance
layer_color_manager = LayerColorManager()


def get_layer_color(layer_name: str) -> str:
    """Get display color for a layer (supports dynamic generation)."""
    return layer_color_manager.get_color(layer_name)


def get_layer_display_name(layer_name: str) -> str:
    """Get display name for a layer."""
    return layer_color_manager.get_display_name(layer_name)


# ============================================================================
# Layout Visualization
# ============================================================================

# Import app_state lazily to avoid circular imports
_app_state = None


def _get_app_state():
    """Lazily get app_state to avoid circular imports."""
    global _app_state
    if _app_state is None:
        from app.state import app_state
        _app_state = app_state
    return _app_state


def create_net_visualization(selected_nets: List[str], mode: str = 'auto_fit') -> go.Figure:
    """Create net visualization figure - Cadence LayoutXL Display DRF style.

    Features:
    - All nets use same layer styles (no color differentiation between nets)
    - Different layers use different dash patterns for distinction
    - Net names shown via annotations in the figure
    - Single legend on right side, grouped by layer

    Args:
        selected_nets: List of net names to visualize
        mode: Display mode - 'auto_fit', 'fit', 'zoom_in', 'zoom_out'

    Returns:
        Plotly go.Figure object
    """
    app_state = _get_app_state()

    fig = go.Figure()

    if not selected_nets or not app_state.nets_data:
        fig.update_layout(
            title='No nets selected',
            xaxis_title='X (μm)',
            yaxis_title='Y (μm)'
        )
        return fig

    all_x, all_y = [], []
    unique_layers = set()

    for net_name in selected_nets:
        if net_name in app_state.nets_data:
            shapes_data = app_state.nets_data[net_name].get('shapes', {})
            unique_layers.update(shapes_data.keys())

    sorted(unique_layers, key=lambda x: (
        1000 if x not in LAYER_PRIORITY_ORDER else LAYER_PRIORITY_ORDER.index(x)
    ))

    layer_shown = {}

    for idx, net_name in enumerate(selected_nets):
        if net_name not in app_state.nets_data:
            continue

        net_data = app_state.nets_data[net_name]
        shapes_data = net_data.get('shapes', {})

        for layer_name, polygons in shapes_data.items():
            if app_state.visible_layers is not None and layer_name not in app_state.visible_layers:
                continue

            display_name = get_layer_display_name(layer_name)
            fill_color = get_layer_color(layer_name)

            via_stroke = VIA_STROKE_COLORS.get(layer_name, 'rgba(60,60,60,1.0)')
            is_via = is_via_layer(layer_name)

            for poly_idx, poly in enumerate(polygons):
                if len(poly) < 2:
                    continue

                display_poly = poly if poly[0] == poly[-1] else poly + [poly[0]]
                x, y = zip(*display_poly)
                all_x.extend(x)
                all_y.extend(y)

                is_first = layer_shown.get(layer_name, True)
                layer_shown[layer_name] = False

                if is_via:
                    line_props = dict(width=1.5, color=via_stroke)
                else:
                    line_props = dict(width=0)

                fig.add_trace(go.Scatter(
                    x=x, y=y,
                    fill='toself',
                    name=display_name,
                    mode='lines',
                    line=line_props,
                    fillcolor=fill_color,
                    legendgroup=layer_name,
                    showlegend=is_first,
                    hovertemplate=(
                        f'<b>Net:</b> {net_name}<br>'
                        f'<b>Layer:</b> {display_name}<br>'
                        f'<b>Points:</b> {len(poly)}'
                        '<extra></extra>'
                    )
                ))

        path_info = _analyze_sd_to_gate_path(shapes_data, app_state)

        if path_info:
            start_point = path_info['start']
            end_point = path_info['end']
            path_info['length']

            mid_x = (start_point.x + end_point.x) / 2
            mid_y = (start_point.y + end_point.y) / 2

            fig.add_annotation(
                x=end_point.x,
                y=end_point.y,
                xref='x',
                yref='y',
                ax=start_point.x,
                ay=start_point.y,
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.2,
                arrowwidth=2.5,
                arrowcolor='#e74c3c',
                axref='x',
                ayref='y'
            )

            total_nets = len(selected_nets)
            net_idx = selected_nets.index(net_name)
            row = net_idx // 3
            col = net_idx % 3
            offset_scale = max(3, total_nets * 1.5)
            offset_x = col * offset_scale
            offset_y = row * offset_scale

            fig.add_annotation(
                x=mid_x + offset_x,
                y=mid_y + offset_y,
                xref='x',
                yref='y',
                text=f"<b>{net_name}</b>",
                showarrow=False,
                font=dict(
                    size=11,
                    color='#c0392b',
                    family="Consolas, monospace"
                ),
                bgcolor='rgba(255,245,240,0.25)',
                bordercolor='rgba(231,76,60,0.5)',
                borderwidth=1,
                borderpad=4,
                xanchor='center',
                yanchor='middle'
            )
        else:
            all_net_points = []
            for polys in shapes_data.values():
                for poly in polys:
                    all_net_points.extend([_Point(p[0], p[1]) for p in poly])

            if all_net_points:
                centroid_x = sum(p.x for p in all_net_points) / len(all_net_points)
                centroid_y = sum(p.y for p in all_net_points) / len(all_net_points)

                total_nets = len(selected_nets)
                net_idx = selected_nets.index(net_name)
                row = net_idx // 3
                col = net_idx % 3
                offset_scale = max(3, total_nets * 1.5)
                offset_x = col * offset_scale
                offset_y = row * offset_scale

                fig.add_annotation(
                    x=centroid_x + offset_x,
                    y=centroid_y + offset_y,
                    text=f"<b>{net_name}</b>",
                    showarrow=False,
                    font=dict(
                        size=12,
                        color='#2c3e50',
                        family="Consolas, monospace"
                    ),
                    bgcolor='rgba(255,255,255,0.25)',
                    bordercolor='rgba(44,62,80,0.4)',
                    borderwidth=1,
                    borderpad=5,
                    xanchor='left' if col % 2 == 0 else 'right',
                    ax=30 if col % 2 == 0 else -30,
                    ay=0
                )

    if app_state.visible_layers is not None:
        all_x, all_y = [], []
        filtered_unique_layers = set()

        for net_name in selected_nets:
            if net_name not in app_state.nets_data:
                continue
            net_data = app_state.nets_data[net_name]
            shapes_data = net_data.get('shapes', {})

            for layer_name, polygons in shapes_data.items():
                if layer_name not in app_state.visible_layers:
                    continue
                filtered_unique_layers.add(layer_name)

                for poly in polygons:
                    if len(poly) < 2:
                        continue
                    for p in poly:
                        all_x.append(p[0])
                        all_y.append(p[1])

    if all_x and all_y:
        if mode == 'zoom_in' or mode == 'zoom_out':
            if app_state.current_view:
                x_min = app_state.current_view['x_min']
                x_max = app_state.current_view['x_max']
                y_min = app_state.current_view['y_min']
                y_max = app_state.current_view['y_max']
            else:
                x_min, x_max = min(all_x), max(all_x)
                y_min, y_max = min(all_y), max(all_y)
        elif mode == 'fit':
            x_min, x_max = min(all_x), max(all_x)
            y_min, y_max = min(all_y), max(all_y)
            padding = 0.05
            x_range = max(x_max - x_min, 1)
            y_range = max(y_max - y_min, 1)
            fig.update_xaxes(range=[x_min - padding*x_range, x_max + padding*x_range])
            fig.update_yaxes(range=[y_min - padding*y_range, y_max + padding*y_range],
                           scaleanchor="x", scaleratio=1)
            app_state.current_view = {'x_min': x_min, 'x_max': x_max, 'y_min': y_min, 'y_max': y_max}
        else:
            x_min, x_max = min(all_x), max(all_x)
            y_min, y_max = min(all_y), max(all_y)
            padding = 0.12
            x_range = max(x_max - x_min, 1)
            y_range = max(y_max - y_min, 1)
            fig.update_xaxes(range=[x_min - padding*x_range, x_max + padding*x_range])
            fig.update_yaxes(range=[y_min - padding*y_range, y_max + padding*y_range],
                           scaleanchor="x", scaleratio=1)

        if mode == 'zoom_in' or mode == 'zoom_out':
            fig.update_xaxes(range=[x_min, x_max])
            fig.update_yaxes(range=[y_min, y_max], scaleanchor="x", scaleratio=1)

    visible_count = len(app_state.visible_layers) if app_state.visible_layers is not None else 0
    total_layers = len(unique_layers)

    nets_label = ", ".join(selected_nets) if len(selected_nets) <= 3 else f"{len(selected_nets)} nets"
    if visible_count == 0:
        title_text = f"Layout View - {nets_label}, No Layers Visible"
    else:
        title_text = f"Layout View - {nets_label}, {visible_count}/{total_layers} Layer(s)"

    fig.update_layout(
        title=dict(
            text=title_text,
            x=0.5,
            font=dict(size=16, color='#2c3e50')
        ),
        xaxis=dict(
            title="X (μm)",
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            gridwidth=1,
            linecolor='#2c3e50',
            linewidth=1,
            mirror=True
        ),
        yaxis=dict(
            title="Y (μm)",
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            gridwidth=1,
            linecolor='#2c3e50',
            linewidth=1,
            mirror=True
        ),
        showlegend=True,
        legend=dict(
            title=dict(text="<b>Layers</b>", font=dict(size=14, color='#2c3e50')),
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=1.02,
            font=dict(size=11),
            bgcolor='rgba(252,252,252,0.95)',
            bordercolor='#bdc3c7',
            borderwidth=1.5,
            groupclick="togglegroup",
            itemsizing='constant'
        ),
        plot_bgcolor='white',
        paper_bgcolor='#fafafa',
        margin=dict(l=70, r=220, t=90, b=70),
        hovermode='closest',
        height=700
    )

    return fig


# Need Point class for path analysis
class _Point:
    """Simple point class for internal use."""
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _analyze_sd_to_gate_path(shapes_data: dict, app_state) -> Optional[dict]:
    """Analyze longest path from SD to Gate/Poly.

    Args:
        shapes_data: Dictionary of layer -> polygon lists
        app_state: Application state with sd_layers and poly_layers config

    Returns:
        Dictionary with start, end, length or None
    """
    if not app_state.path_configured:
        return None

    sd_layers = app_state.sd_layers
    poly_layers = app_state.poly_layers

    def get_centroid(polygons):
        if not polygons:
            return None
        all_points = []
        for poly in polygons:
            for p in poly:
                all_points.append(_Point(p[0], p[1]))
        if not all_points:
            return None
        cx = sum(p.x for p in all_points) / len(all_points)
        cy = sum(p.y for p in all_points) / len(all_points)
        return _Point(cx, cy)

    sd_centroids = []
    for layer_name in sd_layers:
        if layer_name in shapes_data and shapes_data[layer_name]:
            centroid = get_centroid(shapes_data[layer_name])
            if centroid:
                sd_centroids.append(centroid)

    gate_centroids = []
    for layer_name in poly_layers:
        if layer_name in shapes_data and shapes_data[layer_name]:
            centroid = get_centroid(shapes_data[layer_name])
            if centroid:
                gate_centroids.append(centroid)

    if not sd_centroids or not gate_centroids:
        return None

    max_length = 0
    best_start = None
    best_end = None

    for sd in sd_centroids:
        for gate in gate_centroids:
            length = ((gate.x - sd.x)**2 + (gate.y - sd.y)**2)**0.5
            if length > max_length:
                max_length = length
                best_start = sd
                best_end = gate

    if best_start and best_end:
        return {
            'start': best_start,
            'end': best_end,
            'length': max_length
        }

    return None



def create_directional_figure(
    polygons,
    vias,
    net_name: str = "",
    per_polygon_dir=None,
    violations=None,
):
    """Plotly figure with H=Red, V=Blue coloring, plus optional violation overlay.

    Args:
        polygons: List of Polygon to draw.
        vias: List of via polygons (drawn in grey).
        net_name: Title suffix.
        per_polygon_dir: Optional list of {"class": "H"|"V"|"MIXED", "polygon_index": int}.
        violations: Optional list of {"polygon_index": int, "x": float, "y": float}.

    Returns:
        plotly.graph_objects.Figure
    """
    import plotly.graph_objects as go

    H_COLOR = "rgba(255, 50, 50, 0.65)"   # red
    V_COLOR = "rgba(50, 80, 255, 0.65)"   # blue
    MIX_COLOR = "rgba(160, 100, 200, 0.65)"  # purple
    VIA_COLOR = "rgba(80, 80, 80, 0.85)"

    cls_lookup = {}
    if per_polygon_dir:
        cls_lookup = {d["polygon_index"]: d["class"] for d in per_polygon_dir}

    fig = go.Figure()
    for idx, poly in enumerate(polygons):
        cls = cls_lookup.get(idx, "H")
        color = {"H": H_COLOR, "V": V_COLOR, "MIXED": MIX_COLOR}.get(cls, H_COLOR)
        xs = [p.x for p in poly.points]
        ys = [p.y for p in poly.points]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself", mode="lines",
            line=dict(color=color, width=1.5),
            fillcolor=color, name=f"{cls}", showlegend=False,
            hovertemplate=f"{net_name} [{poly.layer}] {cls}<extra></extra>",
        ))

    for v in vias:
        xs = [p.x for p in v.points]
        ys = [p.y for p in v.points]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself", mode="lines",
            line=dict(color=VIA_COLOR, width=1),
            fillcolor=VIA_COLOR, showlegend=False, hoverinfo="skip",
        ))

    if violations:
        for vio in violations:
            fig.add_trace(go.Scatter(
                x=[vio["x"]], y=[vio["y"]],
                mode="markers",
                marker=dict(symbol="x", size=14, color="red",
                            line=dict(width=2, color="darkred")),
                showlegend=False, name="violation",
            ))

    fig.update_layout(
        title=f"Routing Direction: {net_name}" if net_name else "Routing Direction",
        xaxis_title="X (μm)", yaxis_title="Y (μm)",
        yaxis=dict(scaleanchor="x", scaleratio=1),
        template="plotly_white",
    )
    return fig
