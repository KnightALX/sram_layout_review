"""Via coverage and missing-via detection.

Strategy:
1. For each pair of metal polygons on adjacent layers (e.g. met1 + met2),
   compute their 2D overlap (rect-rect exact, non-rect conservative).
2. Count via polygons that sit inside the overlap.
3. coverage = fraction of overlap regions that have at least min_via_per_overlap vias.
4. missing = max(0, min_required - actual_count) per overlap region.

Layer-pair convention (matches typical 7nm/5nm FinFET BEOL):
- met1 ↔ met2: via is via0 OR via1 (via0 = poly contact; via1 = M1↔M2)
- met2 ↔ met3: via is via1 OR via2
- met3 ↔ met4: via is via2 OR via3
- ...
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import Polygon


# Each entry: (metal_a_names, metal_b_names, via_names)
# via N is the via between metN and metN+1
# (via0 is the poly↔M1 contact, also sits between met1 and met2)
ADJACENT_LAYER_PAIRS = [
    # (met_a, met_b, via_options)
    (("met1", "m1"), ("met2", "m2"), ("via0", "v0", "via1", "v1")),
    (("met2", "m2"), ("met3", "m3"), ("via1", "v1", "via2", "v2")),
    (("met3", "m3"), ("met4", "m4"), ("via2", "v2", "via3", "v3")),
    (("met4", "m4"), ("met5", "m5"), ("via3", "v3", "via4", "v4")),
    (("met5", "m5"), ("met6", "m6"), ("via4", "v4", "via5", "v5")),
    (("met6", "m6"), ("met7", "m7"), ("via5", "v5", "via6", "v6")),
    (("met7", "m7"), ("met8", "m8"), ("via6", "v6", "via7", "v7")),
]


def _layer_set(names) -> set:
    return {n.lower() for n in names}


def _rect_overlap_area(p1: "Polygon", p2: "Polygon") -> Tuple[float, Tuple[float, float, float, float]]:
    """Compute overlap area (assumes both are rectangles, returns bbox of overlap)."""
    b1 = p1.bbox
    b2 = p2.bbox
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0, (0, 0, 0, 0)
    return (x2 - x1) * (y2 - y1), (x1, y1, x2, y2)


def _polygon_area_inside_bbox(poly: "Polygon", bbox) -> float:
    """Conservative: use bbox intersection area (exact for rects)."""
    pb = poly.bbox
    x1 = max(pb[0], bbox[0])
    y1 = max(pb[1], bbox[1])
    x2 = min(pb[2], bbox[2])
    y2 = min(pb[3], bbox[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


@dataclass
class ViaCoverageResult:
    missing_via_count: int = 0
    via_coverage: float = 1.0  # 0-1, ratio of overlap regions with ≥ min_via_per_overlap vias
    missing_locations: List[Dict[str, Any]] = field(default_factory=list)
    # missing_locations entries: {"x": float, "y": float, "layer_a": str, "layer_b": str, "overlap_area": float}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "missing_via_count": self.missing_via_count,
            "via_coverage": self.via_coverage,
            "missing_locations": self.missing_locations,
        }


def analyze_via_coverage(
    polygons: List["Polygon"],
    vias: List["Polygon"],
    min_via_per_overlap: int = 1,
    min_size: float = 0.024,
) -> ViaCoverageResult:
    """Analyze via coverage and missing vias for a net.

    Args:
        polygons: All metal polygons of the net.
        vias: All via polygons of the net.
        min_via_per_overlap: Minimum vias required in each overlap region.
        min_size: Minimum via size in μm.

    Returns:
        ViaCoverageResult with counts and locations.
    """
    # Group by layer
    by_layer: Dict[str, List["Polygon"]] = {}
    for p in polygons:
        by_layer.setdefault(p.layer.lower(), []).append(p)
    vias_by_layer: Dict[str, List["Polygon"]] = {}
    for v in vias:
        vias_by_layer.setdefault(v.layer.lower(), []).append(v)

    total_overlap_count = 0
    covered_overlap_count = 0
    missing = 0
    missing_locs: List[Dict[str, Any]] = []

    layer_names = set(by_layer.keys())

    for metal_a_names, metal_b_names, via_names in ADJACENT_LAYER_PAIRS:
        a_set = _layer_set(metal_a_names)
        b_set = _layer_set(metal_b_names)
        via_set = _layer_set(via_names)

        matched_a = layer_names & a_set
        matched_b = layer_names & b_set
        if not matched_a or not matched_b:
            continue
        layer_a = next(iter(matched_a))
        layer_b = next(iter(matched_b))

        # Find any via layer in the union of via_set that is present in vias_by_layer
        available_via_layers = [v for v in vias_by_layer if v in via_set]
        if not available_via_layers:
            # No vias on this connecting layer — every overlap is missing
            for pa in by_layer[layer_a]:
                for pc in by_layer[layer_b]:
                    ov_area, ov_bbox = _rect_overlap_area(pa, pc)
                    if ov_area <= 0:
                        continue
                    total_overlap_count += 1
                    missing += min_via_per_overlap
                    cx = (ov_bbox[0] + ov_bbox[2]) / 2
                    cy = (ov_bbox[1] + ov_bbox[3]) / 2
                    missing_locs.append({
                        "x": cx, "y": cy,
                        "layer_a": layer_a, "layer_b": layer_b,
                        "overlap_area": ov_area,
                    })
            continue

        via_layer = available_via_layers[0]
        vias_here = vias_by_layer[via_layer]

        for pa in by_layer[layer_a]:
            for pc in by_layer[layer_b]:
                ov_area, ov_bbox = _rect_overlap_area(pa, pc)
                if ov_area <= 0:
                    continue
                total_overlap_count += 1
                # Count vias inside this overlap region
                via_count = 0
                for v in vias_here:
                    va = _polygon_area_inside_bbox(v, ov_bbox)
                    if va > 0:
                        via_count += 1
                if via_count >= min_via_per_overlap:
                    covered_overlap_count += 1
                else:
                    deficit = min_via_per_overlap - via_count
                    missing += deficit
                    cx = (ov_bbox[0] + ov_bbox[2]) / 2
                    cy = (ov_bbox[1] + ov_bbox[3]) / 2
                    missing_locs.append({
                        "x": cx, "y": cy,
                        "layer_a": layer_a, "layer_b": layer_b,
                        "overlap_area": ov_area,
                    })

    # via_coverage = fraction of overlap regions that are sufficiently covered.
    # 1.0 if there are no overlaps (trivially nothing to cover).
    if total_overlap_count == 0:
        coverage = 1.0
    else:
        coverage = covered_overlap_count / total_overlap_count

    return ViaCoverageResult(
        missing_via_count=missing,
        via_coverage=coverage,
        missing_locations=missing_locs,
    )
