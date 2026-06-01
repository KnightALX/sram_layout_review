"""H/V directional routing analyzer.

Algorithm:
- For axis-aligned rectangles (4 distinct points with 2 unique x and 2 unique y),
  use the CENTERLINE length: the longer dimension is the routing length.
  (A rect of width 10, height 1 represents a horizontal wire of length 10.)
- For non-rectangular polygons, decompose edges:
  - Purely-H edge (dy=0): all length → H
  - Purely-V edge (dx=0): all length → V
  - Diagonal edge (dx>0, dy>0): split 50/50 (half to H, half to V)
- Per-polygon classification: H if h_ratio ≥ 0.75, V if v_ratio ≥ 0.75, else MIXED.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import Polygon


@dataclass
class DirectionalResult:
    """Result of H/V directional analysis for a single net."""
    h_len: float = 0.0
    v_len: float = 0.0
    h_ratio: float = 0.0
    v_ratio: float = 0.0
    dominant: str = "H"  # "H" or "V"
    per_polygon: List[Dict[str, Any]] = field(default_factory=list)
    # per_polygon entries: {"polygon_index": int, "class": "H"|"V"|"MIXED", "h_len": float, "v_len": float}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "h_len": self.h_len,
            "v_len": self.v_len,
            "h_ratio": self.h_ratio,
            "v_ratio": self.v_ratio,
            "dominant": self.dominant,
            "per_polygon": self.per_polygon,
        }


def _is_axis_aligned_rect(pts: List) -> bool:
    """Detect axis-aligned rectangle: 4 unique points with 2 unique x and 2 unique y."""
    if len(pts) != 4:
        return False
    xs = {p.x for p in pts}
    ys = {p.y for p in pts}
    return len(xs) == 2 and len(ys) == 2


def _classify_polygon(poly: "Polygon") -> Dict[str, Any]:
    """Decompose polygon into H and V routing-length contributions."""
    pts = poly.points
    if len(pts) < 2:
        return {"h_len": 0.0, "v_len": 0.0, "class": "H"}

    # Axis-aligned rectangle: use centerline length
    if _is_axis_aligned_rect(pts):
        xs = sorted({p.x for p in pts})
        ys = sorted({p.y for p in pts})
        w = xs[1] - xs[0]
        h = ys[1] - ys[0]
        if w >= h:
            return {"h_len": w, "v_len": 0.0, "class": "H"}
        else:
            return {"h_len": 0.0, "v_len": h, "class": "V"}

    # Non-rect: edge decomposition with diagonal splitting
    h_len = 0.0
    v_len = 0.0
    n = len(pts)
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        dx = abs(p2.x - p1.x)
        dy = abs(p2.y - p1.y)
        if dx == 0 and dy == 0:
            continue  # degenerate
        edge_len = math.sqrt(dx * dx + dy * dy)
        if dx == 0:
            v_len += edge_len
        elif dy == 0:
            h_len += edge_len
        else:
            # Diagonal: split 50/50 by length
            half = edge_len / 2
            h_len += half
            v_len += half

    total = h_len + v_len
    if total == 0:
        cls = "H"
    elif h_len / total >= 0.75:
        cls = "H"
    elif v_len / total >= 0.75:
        cls = "V"
    else:
        cls = "MIXED"

    return {"h_len": h_len, "v_len": v_len, "class": cls}


def analyze_net_directional(polygons: List["Polygon"]) -> DirectionalResult:
    """Analyze H/V routing ratios for a net (list of polygons).

    Args:
        polygons: All polygons belonging to the net (across all layers).

    Returns:
        DirectionalResult with total H/V lengths, ratios, dominant direction,
        and per-polygon classification for visualization.
    """
    result = DirectionalResult()
    for idx, poly in enumerate(polygons):
        info = _classify_polygon(poly)
        result.h_len += info["h_len"]
        result.v_len += info["v_len"]
        result.per_polygon.append({
            "polygon_index": idx,
            "class": info["class"],
            "h_len": info["h_len"],
            "v_len": info["v_len"],
        })

    total = result.h_len + result.v_len
    if total > 0:
        result.h_ratio = result.h_len / total
        result.v_ratio = result.v_len / total
        result.dominant = "H" if result.h_len >= result.v_len else "V"

    return result
