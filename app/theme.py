"""Professional EDA-style theme and styling for Layout Review Tool.

Inspired by Cadence Virtuoso, Synopsys Design Compiler - industrial/utilitarian aesthetic.
Dark theme for long engineering sessions with high information density.
"""
import os

# EDA Tool Color Palette - Dark Theme
EDA_THEME = {
    # Backgrounds (darkest to lightest)
    'bg_primary': '#1a1a2e',      # Main background - deep navy
    'bg_secondary': '#16213e',    # Panel backgrounds
    'bg_tertiary': '#0f3460',     # Elevated surfaces
    'bg_hover': '#1f4068',        # Hover states

    # Borders and lines
    'border_primary': '#2d4a6f',   # Panel borders
    'border_secondary': '#1a365d', # Subtle borders
    'border_active': '#3b82f6',   # Active/focus borders

    # Text
    'text_primary': '#e2e8f0',    # Primary text - light gray
    'text_secondary': '#94a3b8',   # Secondary text
    'text_muted': '#64748b',      # Muted text
    'text_accent': '#60a5fa',      # Accent text

    # Status Colors (industry standard)
    'status_pass': '#22c55e',     # Green - pass/success
    'status_fail': '#ef4444',     # Red - fail/error
    'status_warning': '#f59e0b',  # Amber - warning
    'status_info': '#3b82f6',     # Blue - info

    # Layer Colors (for layout visualization)
    'layer_metal1': '#60a5fa',    # Blue
    'layer_metal2': '#f97316',     # Orange
    'layer_metal3': '#a855f7',    # Purple
    'layer_poly': '#ef4444',      # Red
    'layer_diff': '#22c55e',      # Green

    # Accent
    'accent_primary': '#3b82f6',  # Primary blue
    'accent_secondary': '#06b6d4', # Cyan

    # Interactive
    'button_primary': '#2563eb',
    'button_hover': '#1d4ed8',
    'button_active': '#1e40af',
}

# Light Theme
LIGHT_THEME = {
    # Backgrounds
    'bg_primary': '#f8fafc',      # Main background - light gray
    'bg_secondary': '#ffffff',    # Panel backgrounds - white
    'bg_tertiary': '#f1f5f9',     # Elevated surfaces
    'bg_hover': '#e2e8f0',        # Hover states

    # Borders and lines
    'border_primary': '#cbd5e1',   # Panel borders
    'border_secondary': '#e2e8f0', # Subtle borders
    'border_active': '#3b82f6',   # Active/focus borders

    # Text
    'text_primary': '#1e293b',    # Primary text - dark slate
    'text_secondary': '#64748b',   # Secondary text
    'text_muted': '#94a3b8',      # Muted text
    'text_accent': '#2563eb',      # Accent text - blue

    # Status Colors (industry standard - same values)
    'status_pass': '#22c55e',     # Green - pass/success
    'status_fail': '#ef4444',     # Red - fail/error
    'status_warning': '#f59e0b',  # Amber - warning
    'status_info': '#3b82f6',     # Blue - info

    # Layer Colors (for layout visualization)
    'layer_metal1': '#3b82f6',    # Blue
    'layer_metal2': '#f97316',     # Orange
    'layer_metal3': '#8b5cf6',    # Purple
    'layer_poly': '#ef4444',      # Red
    'layer_diff': '#22c55e',      # Green

    # Accent
    'accent_primary': '#2563eb',  # Primary blue
    'accent_secondary': '#0891b2', # Cyan

    # Interactive
    'button_primary': '#2563eb',
    'button_hover': '#1d4ed8',
    'button_active': '#1e40af',
}

# Typography
FONT_FAMILY_DISPLAY = '"JetBrains Mono", "Fira Code", "SF Mono", "Consolas", monospace'
FONT_FAMILY_BODY = '"IBM Plex Sans", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
FONT_FAMILY_DATA = '"JetBrains Mono", "Fira Code", "SF Mono", "Consolas", monospace'

FONT_SIZES = {
    'xs': '0.6875rem',    # 11px
    'sm': '0.75rem',       # 12px
    'base': '0.8125rem',  # 13px
    'md': '0.875rem',     # 14px
    'lg': '0.9375rem',    # 15px
    'xl': '1rem',         # 16px
    '2xl': '1.125rem',    # 18px
    '3xl': '1.25rem',     # 20px
}

# Spacing
SPACING = {
    'xs': '0.25rem',   # 4px
    'sm': '0.5rem',    # 8px
    'md': '0.75rem',   # 12px
    'lg': '1rem',      # 16px
    'xl': '1.25rem',   # 20px
    '2xl': '1.5rem',   # 24px
}

# Shadows
SHADOWS = {
    'sm': '0 1px 2px rgba(0, 0, 0, 0.3)',
    'md': '0 4px 6px rgba(0, 0, 0, 0.4)',
    'lg': '0 10px 15px rgba(0, 0, 0, 0.5)',
    'inner': 'inset 0 1px 2px rgba(0, 0, 0, 0.3)',
}

# Border Radius
RADIUS = {
    'none': '0',
    'sm': '2px',
    'md': '4px',
    'lg': '6px',
}

# Complete CSS for EDA-style interface
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets')
_CSS_FILE = os.path.join(_ASSETS_DIR, 'eda-theme.css')


def _load_css() -> str:
    with open(_CSS_FILE, encoding='utf-8') as f:
        return f.read()


EDA_CSS = _load_css()
FULL_CSS = EDA_CSS
INJECTED_CSS = EDA_CSS
THEME = EDA_THEME
