"""Centralized layer color and display-name definitions."""
from __future__ import annotations

BASE_LAYER_COLORS = {
    'n_sd': 'rgba(0, 180, 0, 0.65)',
    'ndiff': 'rgba(0, 180, 0, 0.65)',
    'ndiffusion': 'rgba(0, 180, 0, 0.65)',
    'p_sd': 'rgba(255, 200, 0, 0.65)',
    'pdiff': 'rgba(255, 200, 0, 0.65)',
    'pdiffusion': 'rgba(255, 200, 0, 0.65)',
    'poly': 'rgba(220, 20, 60, 0.65)',
    'gate': 'rgba(220, 20, 60, 0.65)',
    'polyg': 'rgba(220, 20, 60, 0.65)',
    'nwell': 'rgba(144, 238, 144, 0.35)',
    'pwell': 'rgba(255, 218, 185, 0.35)',
    'substrate': 'rgba(240, 240, 240, 0.4)',
    'oxide': 'rgba(200, 220, 240, 0.4)',
}

METAL_LAYER_COLORS = {
    'm0': 'rgba(0, 128, 128, 0.70)',
    'met0': 'rgba(0, 128, 128, 0.70)',
    'locali': 'rgba(0, 128, 128, 0.70)',
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
    'm8': 'rgba(148, 0, 211, 0.70)',
    'met8': 'rgba(148, 0, 211, 0.70)',
    'metal8': 'rgba(148, 0, 211, 0.70)',
    'met8a': 'rgba(148, 0, 211, 0.70)',
    'm9': 'rgba(70, 70, 70, 0.70)',
    'met9': 'rgba(70, 70, 70, 0.70)',
    'metal9': 'rgba(70, 70, 70, 0.70)',
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
    'via7': 'rgba(85, 107, 47, 0.85)',
    'v7': 'rgba(85, 107, 47, 0.85)',
    'via8': 'rgba(128, 0, 128, 0.85)',
    'v8': 'rgba(128, 0, 128, 0.85)',
}


LAYER_FILL_COLORS = {}
LAYER_FILL_COLORS.update(BASE_LAYER_COLORS)
LAYER_FILL_COLORS.update(METAL_LAYER_COLORS)
LAYER_FILL_COLORS.update(VIA_LAYER_COLORS)

DEFAULT_METAL_COLOR = 'rgba(100, 100, 100, 0.70)'
DEFAULT_VIA_COLOR = 'rgba(80, 80, 80, 0.85)'


def is_via_layer(layer_name: str) -> bool:
    """Return True if layer name looks like a via."""
    layer_lower = layer_name.lower()
    via_patterns = ['via', 'v0', 'v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7', 'v8', 'v9']
    return any(pattern in layer_lower for pattern in via_patterns)


def get_report_layer_color(layer_name: str) -> str:
    """Static layer color lookup for report figures (no dynamic generation)."""
    layer_lower = layer_name.lower()
    if layer_lower in LAYER_FILL_COLORS:
        return LAYER_FILL_COLORS[layer_lower]
    if 'met' in layer_lower or layer_lower.startswith('m'):
        return DEFAULT_METAL_COLOR
    if is_via_layer(layer_name):
        return DEFAULT_VIA_COLOR
    return DEFAULT_METAL_COLOR
