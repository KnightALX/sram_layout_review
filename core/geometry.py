"""Polygon/segment distance helpers shared by review engine and rules."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from review_engine import Point, Polygon


def point_to_segment_distance(seg_start: "Point", seg_end: "Point", point: "Point") -> float:
    """Minimum distance from a point to a line segment."""
    dx = seg_end.x - seg_start.x
    dy = seg_end.y - seg_start.y
    px = point.x - seg_start.x
    py = point.y - seg_start.y

    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-10:
        return math.sqrt(px * px + py * py)

    t = max(0, min(1, (px * dx + py * dy) / seg_len_sq))
    nearest_x = seg_start.x + t * dx
    nearest_y = seg_start.y + t * dy
    dist_x = point.x - nearest_x
    dist_y = point.y - nearest_y
    return math.sqrt(dist_x * dist_x + dist_y * dist_y)


def min_polygon_distance(poly1: "Polygon", poly2: "Polygon") -> float:
    """Minimum distance between two polygons (μm)."""
    b1 = poly1.bbox
    b2 = poly2.bbox

    x_overlap = min(b1[2], b2[2]) - max(b1[0], b2[0])
    y_overlap = min(b1[3], b2[3]) - max(b1[1], b2[1])
    if x_overlap > 0 and y_overlap > 0:
        return 0.0

    if b1[2] < b2[0] or b2[2] < b1[0] or b1[3] < b2[1] or b2[3] < b1[1]:
        if b1[2] < b2[0] or b2[2] < b1[0]:
            gap_x = max(b1[0] - b2[2], b2[0] - b1[2], 0)
        else:
            gap_x = 0

        if b1[3] < b2[1] or b2[3] < b1[1]:
            gap_y = max(b1[1] - b2[3], b2[1] - b1[3], 0)
        else:
            gap_y = 0

        if gap_x > 0 and gap_y > 0:
            return math.sqrt(gap_x * gap_x + gap_y * gap_y)
        if gap_x > 0:
            return gap_x
        if gap_y > 0:
            return gap_y
        return 0.0

    min_dist = float("inf")

    def segment_to_segment_dist(p1, p2, p3, p4) -> float:
        d1 = point_to_segment_distance(p1, p2, p3)
        d2 = point_to_segment_distance(p1, p2, p4)
        d3 = point_to_segment_distance(p3, p4, p1)
        d4 = point_to_segment_distance(p3, p4, p2)
        return min(d1, d2, d3, d4)

    pts1 = poly1.points
    pts2 = poly2.points
    for i in range(len(pts1)):
        p1 = pts1[i]
        p2 = pts1[(i + 1) % len(pts1)]
        for j in range(len(pts2)):
            p3 = pts2[j]
            p4 = pts2[(j + 1) % len(pts2)]
            dist = segment_to_segment_dist(p1, p2, p3, p4)
            min_dist = min(min_dist, dist)

    return min_dist if min_dist < float("inf") else 0.0
