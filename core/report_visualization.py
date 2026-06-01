#!/usr/bin/env python3
"""
Report Visualization - Generate Plotly figures for report generation.

This module provides standalone visualization functions that don't rely
on app_state, making them suitable for report generation.
"""

import io
from typing import List, Dict, Any, Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ============================================================================
# Layer Color Definitions - Matching visualization.py
# ============================================================================

METAL_LAYER_COLORS = {
    'm0': 'rgba(0, 128, 128, 0.70)',
    'met0': 'rgba(0, 128, 128, 0.70)',
    'm1': 'rgba(30, 144, 255, 0.70)',
    'met1': 'rgba(30, 144, 255, 0.70)',
    'metal1': 'rgba(30, 144, 255, 0.70)',
    'met1a': 'rgba(30, 144, 255, 0.70)',
    'm2': 'rgba(255, 140, 0, 0.70)',
    'met2': 'rgba(255, 140, 0, 0.70)',
    'metal2': 'rgba(255, 140, 0, 0.70)',
    'met2a': 'rgba(255, 140, 0, 0.70)',
    'm3': 'rgba(147, 112, 219, 0.70)',
    'met3': 'rgba(147, 112, 219, 0.70)',
    'metal3': 'rgba(147, 112, 219, 0.70)',
    'met3a': 'rgba(147, 112, 219, 0.70)',
    'm4': 'rgba(255, 105, 180, 0.70)',
    'met4': 'rgba(255, 105, 180, 0.70)',
    'metal4': 'rgba(255, 105, 180, 0.70)',
    'met4a': 'rgba(255, 105, 180, 0.70)',
    'm5': 'rgba(0, 206, 209, 0.70)',
    'met5': 'rgba(0, 206, 209, 0.70)',
    'metal5': 'rgba(0, 206, 209, 0.70)',
    'met5a': 'rgba(0, 206, 209, 0.70)',
    'm6': 'rgba(160, 82, 45, 0.70)',
    'met6': 'rgba(160, 82, 45, 0.70)',
    'metal6': 'rgba(160, 82, 45, 0.70)',
    'met6a': 'rgba(160, 82, 45, 0.70)',
    'm7': 'rgba(107, 142, 35, 0.70)',
    'met7': 'rgba(107, 142, 35, 0.70)',
    'metal7': 'rgba(107, 142, 35, 0.70)',
    'met7a': 'rgba(107, 142, 35, 0.70)',
}

VIA_LAYER_COLORS = {
    'via0': 'rgba(0, 100, 0, 0.85)',
    'v0': 'rgba(0, 100, 0, 0.85)',
    'via1': 'rgba(0, 0, 139, 0.85)',
    'v1': 'rgba(0, 0, 139, 0.85)',
    'via2': 'rgba(210, 105, 30, 0.85)',
    'v2': 'rgba(210, 105, 30, 0.85)',
    'via3': 'rgba(75, 0, 130, 0.85)',
    'v3': 'rgba(75, 0, 130, 0.85)',
    'via4': 'rgba(199, 21, 133, 0.85)',
    'v4': 'rgba(199, 21, 133, 0.85)',
    'via5': 'rgba(0, 139, 139, 0.85)',
    'v5': 'rgba(0, 139, 139, 0.85)',
    'via6': 'rgba(101, 67, 33, 0.85)',
    'v6': 'rgba(101, 67, 33, 0.85)',
}

LAYER_COLORS = {}
LAYER_COLORS.update(METAL_LAYER_COLORS)
LAYER_COLORS.update(VIA_LAYER_COLORS)

DEFAULT_METAL_COLOR = 'rgba(100, 100, 100, 0.70)'
DEFAULT_VIA_COLOR = 'rgba(80, 80, 80, 0.85)'


def get_layer_color(layer_name: str) -> str:
    """Get fill color for a layer."""
    layer_lower = layer_name.lower()
    return LAYER_COLORS.get(layer_lower, DEFAULT_METAL_COLOR if 'met' in layer_lower or 'm' in layer_lower else DEFAULT_VIA_COLOR)


def is_via_layer(layer_name: str) -> bool:
    """Check if a layer is a via layer."""
    layer_lower = layer_name.lower()
    return layer_lower.startswith('via') or layer_lower.startswith('v')


def create_polygons_figure(
    polygons: List[Any],
    title: str = "",
    x_range: Optional[List[float]] = None,
    y_range: Optional[List[float]] = None,
    showgrid: bool = False
) -> go.Figure:
    """Create a Plotly figure from a list of Polygon objects.

    Args:
        polygons: List of Polygon objects from review_engine
        title: Figure title
        x_range: [xmin, xmax] for x-axis
        y_range: [ymin, ymax] for y-axis
        showgrid: Whether to show grid lines

    Returns:
        Plotly go.Figure object
    """
    fig = go.Figure()

    if not polygons:
        fig.update_layout(title=title or 'No polygons')
        return fig

    # Group polygons by layer
    layer_polygons: Dict[str, List] = {}
    for poly in polygons:
        layer = getattr(poly, 'layer', 'unknown')
        if layer not in layer_polygons:
            layer_polygons[layer] = []
        layer_polygons[layer].append(poly)

    # Track axis ranges
    all_x, all_y = [], []

    for layer_name, layer_polys in layer_polygons.items():
        fill_color = get_layer_color(layer_name)
        is_via = is_via_layer(layer_name)

        for poly in layer_polys:
            points = getattr(poly, 'points', [])
            if len(points) < 2:
                continue

            # Close the polygon if not already closed
            x_coords = [p.x for p in points]
            y_coords = [p.y for p in points]

            # Close polygon
            if x_coords[0] != x_coords[-1] or y_coords[0] != y_coords[-1]:
                x_coords.append(x_coords[0])
                y_coords.append(y_coords[0])

            all_x.extend(x_coords)
            all_y.extend(y_coords)

            line_props = dict(width=1.0, color='rgba(60,60,60,1.0)') if is_via else dict(width=0.5, color='rgba(100,100,100,0.5)')

            fig.add_trace(go.Scatter(
                x=x_coords,
                y=y_coords,
                fill='toself',
                name=layer_name,
                mode='lines',
                line=line_props,
                fillcolor=fill_color,
                legendgroup=layer_name,
                showlegend=True,
                hovertemplate=(
                    f'<b>Layer:</b> {layer_name}<br>'
                    f'<b>Points:</b> {len(points)}'
                    '<extra></extra>'
                )
            ))

    # Update layout
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color='#2C3E50')),
        xaxis_title='X (μm)',
        yaxis_title='Y (μm)',
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=50, r=20, t=50, b=50)
    )

    fig.update_xaxes(showgrid=showgrid, zeroline=False)
    fig.update_yaxes(showgrid=showgrid, zeroline=False)

    if x_range:
        fig.update_xaxes(range=x_range)
    if y_range:
        fig.update_yaxes(range=y_range)

    # Auto-fit if no ranges provided
    if not x_range and not y_range and all_x and all_y:
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        x_margin = (x_max - x_min) * 0.05 if x_max > x_min else 1.0
        y_margin = (y_max - y_min) * 0.05 if y_max > y_min else 1.0
        fig.update_xaxes(range=[x_min - x_margin, x_max + x_margin])
        fig.update_yaxes(range=[y_min - y_margin, y_max + y_margin])

    return fig


def create_violation_figure(
    polygons: List[Any],
    violation_points: List[Any] = None,
    title: str = "Violation Areas",
    x_range: Optional[List[float]] = None,
    y_range: Optional[List[float]] = None
) -> go.Figure:
    """Create a figure highlighting violation areas.

    Args:
        polygons: List of Polygon objects in violation areas
        violation_points: List of Point objects marking violations
        title: Figure title
        x_range: [xmin, xmax] for x-axis
        y_range: [ymin, ymax] for y-axis

    Returns:
        Plotly go.Figure object
    """
    fig = create_polygons_figure(
        polygons=polygons,
        title=title,
        x_range=x_range,
        y_range=y_range,
        showgrid=False
    )

    # Add violation markers
    if violation_points:
        marker_x = [p.x for p in violation_points]
        marker_y = [p.y for p in violation_points]

        fig.add_trace(go.Scatter(
            x=marker_x,
            y=marker_y,
            mode='markers',
            name='Violation Points',
            marker=dict(
                size=12,
                color='red',
                symbol='x',
                line=dict(width=2, color='red')
            ),
            hovertemplate='<b>Violation</b><br>x: %{x:.3f}<br>y: %{y:.3f}<extra></extra>'
        ))

    return fig
