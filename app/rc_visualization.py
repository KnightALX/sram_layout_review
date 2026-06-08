"""3D visualization of the metal/via stack for the RC Prediction tab.

The figure is rendered to PNG bytes and returned as a base64 string so it
can be embedded directly in a Dash `dcc.Graph` (via `figure=`) without
shipping a separate static-asset directory.
"""
from __future__ import annotations
import base64
import io
from typing import Dict

import matplotlib
matplotlib.use("Agg")  # non-interactive backend (no display required)
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3d projection)

from app.rc_model import RCModelConfig


# EDA-style colors keyed by metal layer number so the figure is consistent
# with the rest of the app's palette.
_METAL_COLORS = [
    "#60a5fa",  # met1  blue
    "#f97316",  # met2  orange
    "#a855f7",  # met3  purple
    "#22c55e",  # met4  green
    "#ef4444",  # met5  red
    "#06b6d4",  # met6  cyan
    "#eab308",  # met7  yellow
]
_VIA_COLOR = "#94a3b8"  # slate gray
_DIELECTRIC_COLOR = "#1e293b"  # deep navy (matches EDA dark theme)


def _layer_color(layer: str) -> str:
    """Pick a color for a metal layer based on its trailing number."""
    digits = "".join(c for c in layer if c.isdigit())
    if not digits:
        return _METAL_COLORS[0]
    idx = (int(digits) - 1) % len(_METAL_COLORS)
    return _METAL_COLORS[idx]


def render_stack_3d_png(cfg: RCModelConfig) -> bytes:
    """Render the metal/via stack as a 3D PNG.  Returns raw PNG bytes.

    Layout convention: z-axis is vertical (stack height), x/y are the
    in-plane directions.  Each metal layer is a thin colored slab; each
    via is a small cylindrical pillar connecting two adjacent metals.
    """
    metals = cfg.metal_layers()
    vias = cfg.via_layers()
    fig = plt.figure(figsize=(8.0, 5.0), dpi=110)
    ax = fig.add_subplot(111, projection="3d")

    # Z is stack height.  Each metal is one slab; vias sit between them.
    z_cursor = 0.0
    metal_zs: Dict[str, tuple[float, float]] = {}  # layer -> (z_lo, z_hi)
    via_zs: Dict[str, tuple[float, float]] = {}   # via -> (z_lo, z_hi)

    # Width of every layer is normalized to 1.0 in the in-plane direction
    # (this is a schematic — actual dimensions are listed in labels).
    xy_lo, xy_hi = 0.0, 1.0

    # Build metal slabs
    for layer in metals:
        thickness = cfg.metal_thickness.get(layer, 0.060)
        # Visually amplify thickness — 0.06 µm would be invisible
        viz_thickness = max(thickness * 80.0, 0.12)
        z_lo, z_hi = z_cursor, z_cursor + viz_thickness
        metal_zs[layer] = (z_lo, z_hi)
        z_cursor = z_hi

    # Build via pillars between adjacent metals
    for i, via in enumerate(vias):
        via_r = cfg.via_resistance.get(via, 3.0)
        # Visual height proportional to the metals it connects
        if i + 1 < len(metals):
            bot_layer = metals[i]
            top_layer = metals[i + 1]
            z_lo = metal_zs[bot_layer][1]
            z_hi = metal_zs[top_layer][0] if top_layer in metal_zs else z_lo + 0.1
        else:
            z_lo = metal_zs[metals[-1]][1] if metals else 0.0
            z_hi = z_lo + 0.1
        via_zs[via] = (z_lo, z_hi)

    # Draw metal slabs as 3D boxes (six faces) using `bar3d`
    for layer, (z_lo, z_hi) in metal_zs.items():
        height = z_hi - z_lo
        ax.bar3d(
            x=xy_lo, y=xy_lo, z=z_lo,
            dx=xy_hi - xy_lo, dy=xy_hi - xy_lo, dz=height,
            color=_layer_color(layer), alpha=0.85,
            edgecolor="black", linewidth=0.4, shade=True,
        )

    # Draw vias as small cylinders (approximated by short fat bars at corners)
    for via, (z_lo, z_hi) in via_zs.items():
        via_dz = max(z_hi - z_lo, 0.05)
        # Place four via bars at corners of the unit square
        for cx, cy in [(0.10, 0.10), (0.10, 0.80), (0.80, 0.10), (0.80, 0.80)]:
            ax.bar3d(
                x=cx, y=cy, z=z_lo,
                dx=0.10, dy=0.10, dz=via_dz,
                color=_VIA_COLOR, alpha=0.95,
                edgecolor="black", linewidth=0.2,
            )

    # Annotate layers on the right edge
    for layer, (z_lo, z_hi) in metal_zs.items():
        z_mid = (z_lo + z_hi) / 2.0
        r_sheet = cfg.metal_r_sheet.get(layer, 0.0)
        thick = cfg.metal_thickness.get(layer, 0.0)
        ax.text(
            1.15, 0.5, z_mid,
            f"{layer}\nRs={r_sheet:.2f}\nt={thick*1000:.0f}nm",
            fontsize=8, color="black",
            ha="left", va="center",
            family="monospace",
        )

    # Title + axis cosmetics
    ax.set_title(
        f"Metal/Via Stack 3D  ({cfg.tech_node}  T={cfg.temperature_c:.0f}°C  "
        f"ε_r={cfg.dielectric_constant:.2f})",
        fontsize=11, color="black", pad=18, family="monospace",
    )
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.set_zlim(0, max((z_hi for _, z_hi in metal_zs.values()), default=1.0) * 1.05)
    ax.set_xlabel("x", fontsize=8, color="black")
    ax.set_ylabel("y", fontsize=8, color="black")
    ax.set_zlabel("stack", fontsize=8, color="black")
    ax.tick_params(axis="both", which="major", labelsize=7, colors="black")
    ax.view_init(elev=22, azim=-55)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    return buf.getvalue()


def render_stack_3d_figure(cfg: RCModelConfig) -> Dict:
    """Return a `dcc.Graph`-ready figure dict from a 3D PNG render.

    The figure is base64-encoded into a Plotly `layout.image` source URL
    so it can be displayed inside a Dash `dcc.Graph` without any external
    asset hosting.
    """
    png_bytes = render_stack_3d_png(cfg)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return {
        "data": [],
        "layout": {
            "margin": {"l": 0, "r": 0, "t": 8, "b": 0},
            "xaxis": {"visible": False, "range": [0, 1]},
            "yaxis": {"visible": False, "range": [0, 1]},
            "images": [{
                "source": f"data:image/png;base64,{b64}",
                "xref": "x", "yref": "y",
                "x": 0, "y": 1, "sizex": 1, "sizey": 1,
                "xanchor": "left", "yanchor": "top",
                "layer": "above",
            }],
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "height": 340,
        },
    }


def _stub_figure(message: str) -> Dict:
    """Return an empty figure with a centered annotation (used on errors)."""
    return {
        "data": [],
        "layout": {
            "xaxis": {"visible": False, "range": [0, 1]},
            "yaxis": {"visible": False, "range": [0, 1]},
            "annotations": [{
                "x": 0.5, "y": 0.5, "xref": "x", "yref": "y",
                "showarrow": False,
                "text": message, "font": {"color": "#ef4444", "size": 12},
            }],
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "height": 340,
        },
    }


def safe_render_stack_3d_figure(cfg: RCModelConfig) -> Dict:
    """Wrap `render_stack_3d_figure` with a try/except for the UI.

    On any rendering error (e.g. matplotlib failure, OOM), returns a
    stub figure with the error message — never raises into Dash.
    """
    try:
        return render_stack_3d_figure(cfg)
    except Exception as e:  # noqa: BLE001  (we DO want to catch everything here)
        return _stub_figure(f"3D render error: {e}")
