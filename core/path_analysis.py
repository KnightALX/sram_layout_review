"""Path analysis utilities for layout analysis."""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PathResult:
    """Result of path analysis from SD to Gate."""
    start: 'Point'
    end: 'Point'
    length: float


# Import app_state lazily
_app_state = None


def _get_app_state():
    """Lazily get app_state to avoid circular imports."""
    global _app_state
    if _app_state is None:
        from app.state import app_state
        _app_state = app_state
    return _app_state


class Point:
    """Simple 2D point for path analysis."""
    __slots__ = ('x', 'y')

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x:.2f}, {self.y:.2f})"


def analyze_sd_to_gate_path(shapes_data: dict, app_state=None) -> Optional[Dict]:
    """Analyze longest path from SD (source/drain) to Gate/Poly layer.

    Args:
        shapes_data: Dictionary mapping layer names to polygon lists
        app_state: Application state with sd_layers and poly_layers config.
                   If None, uses global app_state.

    Returns:
        Dictionary with 'start' (Point), 'end' (Point), 'length' (float),
        or None if path cannot be determined.
    """
    if app_state is None:
        app_state = _get_app_state()

    if not app_state.path_configured:
        return None

    sd_layers = app_state.sd_layers
    poly_layers = app_state.poly_layers

    def get_centroid(polygons: List) -> Optional[Point]:
        """Calculate centroid of polygon list."""
        if not polygons:
            return None
        all_points = []
        for poly in polygons:
            for p in poly:
                all_points.append(Point(p[0], p[1]))
        if not all_points:
            return None
        cx = sum(p.x for p in all_points) / len(all_points)
        cy = sum(p.y for p in all_points) / len(all_points)
        return Point(cx, cy)

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


def get_view_for_visible_layers(selected_nets: List[str], visible_layers: Optional[set]) -> Optional[dict]:
    """Calculate view range for currently visible layers.

    Args:
        selected_nets: List of net names to include in view calculation
        visible_layers: Set of visible layer names. None means show all.

    Returns:
        Dictionary with x_min, x_max, y_min, y_max or None if no data
    """
    app_state = _get_app_state()

    if visible_layers is None or not selected_nets:
        return None

    all_x, all_y = [], []

    for net_name in selected_nets:
        if net_name not in app_state.nets_data:
            continue
        net_data = app_state.nets_data[net_name]
        shapes_data = net_data.get('shapes', {})

        for layer_name, polygons in shapes_data.items():
            if layer_name not in visible_layers:
                continue

            for poly in polygons:
                if len(poly) < 2:
                    continue
                for p in poly:
                    all_x.append(p[0])
                    all_y.append(p[1])

    if not all_x or not all_y:
        return None

    return {
        'x_min': min(all_x),
        'x_max': max(all_x),
        'y_min': min(all_y),
        'y_max': max(all_y)
    }
