"""Professional EDA-style theme and styling for Layout Review Tool.

Inspired by Cadence Virtuoso, Synopsys Design Compiler - industrial/utilitarian aesthetic.
Dark theme for long engineering sessions with high information density.
"""

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
EDA_CSS = """
/* Reset & Base */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* Dark Theme (default) */
:root, .theme-dark {
    /* Colors */
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-tertiary: #0f3460;
    --bg-hover: #1f4068;
    --bg-input: #0d1b2a;

    --border-primary: #2d4a6f;
    --border-secondary: #1a365d;
    --border-active: #3b82f6;

    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --text-accent: #60a5fa;

    --status-pass: #22c55e;
    --status-fail: #ef4444;
    --status-warning: #f59e0b;
    --status-info: #3b82f6;

    --accent-primary: #3b82f6;
    --accent-secondary: #06b6d4;

    --button-primary: #2563eb;
    --button-hover: #1d4ed8;
    --button-active: #1e40af;

    /* Graph container - dark in dark mode */
    --graph-bg: #0a0a14;

    /* Shadows */
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
    --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);

    /* Scrollbar */
    --scrollbar-track: var(--bg-secondary);
    --scrollbar-thumb: var(--border-primary);
}

/* Light Theme */
.theme-light {
    --bg-primary: #f8fafc;
    --bg-secondary: #ffffff;
    --bg-tertiary: #f1f5f9;
    --bg-hover: #e2e8f0;
    --bg-input: #ffffff;

    --border-primary: #cbd5e1;
    --border-secondary: #e2e8f0;
    --border-active: #3b82f6;

    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --text-muted: #94a3b8;
    --text-accent: #2563eb;

    --accent-primary: #2563eb;
    --accent-secondary: #0891b2;

    --button-primary: #2563eb;
    --button-hover: #1d4ed8;
    --button-active: #1e40af;

    /* Graph container - light in light mode */
    --graph-bg: #f1f5f9;

    /* Shadows - lighter for light mode */
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.15);

    /* Scrollbar */
    --scrollbar-track: var(--bg-tertiary);
    --scrollbar-thumb: var(--border-primary);
}

/* Typography - shared */
:root {
    --font-display: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
    --font-body: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --font-data: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;

    /* Spacing */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 12px;
    --space-lg: 16px;
    --space-xl: 20px;
    --space-2xl: 24px;

    /* Radius */
    --radius-sm: 2px;
    --radius-md: 4px;
    --radius-lg: 6px;
}

html, body {
    height: 100%;
    overflow: hidden;
}

body {
    font-family: var(--font-body);
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-primary);
    background: var(--bg-primary);
    transition: background-color 0.3s ease, color 0.3s ease;
}

/* Scrollbar Styling */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--scrollbar-track); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-primary); }
::-webkit-scrollbar-corner { background: var(--scrollbar-track); }

/* Application Container */
.app-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
}

/* Header Bar */
.header-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 40px;
    padding: 0 var(--space-md);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-primary);
    flex-shrink: 0;
}

.header-title {
    display: flex;
    align-items: center;
    gap: var(--space-md);
}

.header-logo {
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-accent);
    letter-spacing: 0.05em;
}

.header-subtitle {
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.02em;
}

.header-status {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
}

.status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-family: var(--font-data);
}

.status-indicator-label {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-data);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: 10px;
    color: var(--text-secondary);
}

.status-indicator-value {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-data);
    background: var(--bg-input);
    border: 1px solid var(--border-primary);
    border-radius: 10px;
    color: var(--text-primary);
}

.status-indicator-ready {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    font-size: 11px;
    font-family: var(--font-data);
    background: var(--bg-input);
    border: 1px solid var(--border-primary);
    border-radius: 12px;
    gap: 6px;
}

.status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-muted);
}

.status-dot.online { background: var(--status-pass); }
.status-dot.warning { background: var(--status-warning); animation: pulse 2s infinite; }
.status-dot.error { background: var(--status-fail); animation: pulse 1s infinite; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Theme Toggle Button */
.theme-toggle-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-width: 70px;
    padding: 4px 12px;
    font-size: 11px;
    font-family: var(--font-data);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: 14px;
    cursor: pointer;
    transition: all 0.2s;
    color: var(--text-secondary);
}

.theme-toggle-btn:hover {
    background: var(--bg-hover);
    border-color: var(--accent-primary);
}

.theme-toggle-icon {
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
}

.theme-toggle-icon .sun { display: none; color: #f59e0b; }
.theme-toggle-icon .moon { display: block; color: #94a3b8; }

.theme-light .theme-toggle-icon .sun { display: block; color: #f59e0b; }
.theme-light .theme-toggle-icon .moon { display: none; color: #94a3b8; }

.theme-toggle-label {
    font-size: 11px;
    font-family: var(--font-data);
    color: var(--text-secondary);
}

/* Main Content Area */
.main-content {
    display: flex;
    flex: 1;
    overflow: hidden;
}

/* Left Sidebar */
.sidebar {
    width: 240px;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-primary);
    flex-shrink: 0;
    overflow: hidden;
}

.sidebar-section {
    display: flex;
    flex-direction: column;
    border-bottom: 1px solid var(--border-primary);
    flex-shrink: 0;
}

.sidebar-section-grow {
    display: flex;
    flex-direction: column;
    border-bottom: 1px solid var(--border-primary);
    flex: 1;
    min-height: 0;
    overflow: hidden;
}

.sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg-tertiary);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
}

.sidebar-header:hover {
    background: var(--bg-hover);
}

.sidebar-content {
    padding: var(--space-sm);
    overflow-y: auto;
    flex: 1;
    min-height: 0;
}

.sidebar-content.collapsed {
    display: none;
}

/* Net selection section - FIXED SIZE, never shrinks */
.sidebar-section-fixed {
    display: flex;
    flex-direction: column;
    border-bottom: 1px solid var(--border-primary);
    flex-shrink: 0;
    flex-grow: 0;
}

/* Net selection body - fixed layout */
.net-selection-body {
    display: flex;
    flex-direction: column;
    padding: var(--space-sm);
    flex-shrink: 0;
    flex-grow: 0;
}

/* Net Dropdown - PROMINENT DASHED BORDER professional style */
.net-dropdown {
    width: 100%;
    height: 120px;
    max-height: 120px;
    min-height: 120px;
    padding: 0;
    font-size: 12px;
    font-family: var(--font-data);
    color: var(--text-primary);
    background: var(--bg-input);
    border: 2px dashed var(--border-primary) !important;
    border-radius: var(--radius-sm);
    outline: none;
    cursor: pointer;
    transition: all 0.2s ease;
}

.net-dropdown:hover {
    border-color: var(--accent-primary) !important;
}

.net-dropdown:focus,
.net-dropdown.is-focused {
    border: 2px dashed var(--accent-primary) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
}

/* Dropdown control - the visible part with SCROLL for overflow */
.net-dropdown .Select-control {
    height: 120px;
    max-height: 120px;
    min-height: 120px;
    background: transparent;
    border: none !important;
    border-radius: 0;
    box-shadow: none !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}

/* Multi-value wrapper - selected items with proper wrapping */
.net-dropdown .Select-multi-value-wrapper {
    padding: 6px 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: flex-start;
    max-height: 110px;
    overflow-y: auto;
}

/* Selected value chips */
.net-dropdown .Select-placeholder,
.net-dropdown .css-1gcymg5-placeholder {
    padding: 8px 12px;
    color: var(--text-muted);
    font-style: italic;
}

/* Input field in dropdown */
.net-dropdown .Select-input {
    padding: 8px 12px;
    min-height: 32px;
}

.net-dropdown .Select-input input {
    padding: 0;
    min-height: 20px;
}

/* Dropdown menu */
.net-dropdown .Select-menu-outer {
    max-height: 180px;
    overflow-y: auto;
    background: var(--bg-input);
    border: 2px dashed var(--accent-primary) !important;
    border-radius: var(--radius-sm);
    margin-top: 4px;
    box-shadow: var(--shadow-lg);
    z-index: 1000;
}

/* Dropdown options */
.net-dropdown .Select-option {
    padding: 8px 12px;
    color: var(--text-primary);
    cursor: pointer;
    transition: background 0.1s;
}

.net-dropdown .Select-option:hover {
    background: var(--bg-hover);
}

.net-dropdown .Select-option.is-selected {
    background: var(--accent-primary);
    color: white;
}

.net-dropdown .Select-option.is-active {
    background: var(--bg-hover);
}

/* Value chip (selected item) */
.net-dropdown .Select-value {
    display: inline-flex;
    align-items: center;
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: 10px;
    font-size: 11px;
    color: var(--text-primary);
    margin: 2px;
}

.net-dropdown .Select-value-icon {
    padding: 2px 4px;
    margin-left: 4px;
    cursor: pointer;
    color: var(--text-muted);
}

.net-dropdown .Select-value-icon:hover {
    color: var(--status-fail);
}

/* Clear indicator */
.net-dropdown .Select-clear {
    padding: 4px 8px;
    color: var(--text-muted);
}

.net-dropdown .Select-clear:hover {
    color: var(--status-fail);
}

/* Dropdown arrow */
.net-dropdown .Select-arrow {
    border-color: var(--text-muted) transparent transparent;
    border-style: solid;
    border-width: 5px 5px 0;
    margin-top: -2px;
}

.net-dropdown .Select-arrow-zone:hover .Select-arrow {
    border-color: var(--text-primary) transparent transparent;
}

/* Tree View (for nets/layers) */
.tree-item {
    display: flex;
    align-items: center;
    padding: 4px var(--space-sm);
    font-size: 12px;
    font-family: var(--font-data);
    color: var(--text-primary);
    cursor: pointer;
    border-radius: var(--radius-sm);
    gap: var(--space-xs);
}

.tree-item:hover {
    background: var(--bg-hover);
}

.tree-item.selected {
    background: var(--accent-primary);
    color: white;
}

.tree-item .icon {
    width: 14px;
    height: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--text-muted);
}

.tree-item .label {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.tree-item .badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    background: var(--bg-tertiary);
    color: var(--text-muted);
}

/* Tab Bar */
.tab-bar {
    display: flex;
    align-items: center;
    height: 32px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-primary);
    padding: 0 var(--space-sm);
    gap: 2px;
    overflow-x: auto;
    flex-shrink: 0;
}

.tab-bar::-webkit-scrollbar { height: 0; }

.tab-item {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: 0 var(--space-md);
    height: 28px;
    font-size: 12px;
    font-family: var(--font-body);
    font-weight: 500;
    color: var(--text-muted);
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
}

.tab-item:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
}

.tab-item.active {
    color: var(--text-accent);
    border-bottom-color: var(--accent-primary);
    background: var(--bg-tertiary);
}

.tab-item .close {
    width: 14px;
    height: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    border-radius: 2px;
    opacity: 0;
    transition: opacity 0.15s;
}

.tab-item:hover .close {
    opacity: 0.6;
}

.tab-item .close:hover {
    opacity: 1;
    background: var(--status-fail);
    color: white;
}

/* Main Canvas Area */
.canvas-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-primary);
}

.canvas-toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-primary);
}

.toolbar-group {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 0 var(--space-sm);
    border-right: 1px solid var(--border-primary);
}

.toolbar-group:last-child {
    border-right: none;
}

.toolbar-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
    font-size: 12px;
}

.toolbar-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-primary);
}

.toolbar-btn.active {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
}

.toolbar-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.toolbar-label {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-data);
    margin-right: var(--space-xs);
}

.toolbar-value {
    font-size: 11px;
    color: var(--text-accent);
    font-family: var(--font-data);
}

/* Graph Container */
.graph-container {
    flex: 1;
    position: relative;
    overflow: hidden;
    background: var(--graph-bg);
}

/* Right Panel (Properties) */
.right-panel {
    width: 280px;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-left: 1px solid var(--border-primary);
    flex-shrink: 0;
    overflow: hidden;
}

.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-primary);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-secondary);
}

.panel-content {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-md);
}

/* Property Groups */
.prop-group {
    margin-bottom: var(--space-lg);
}

.prop-group-header {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin-bottom: var(--space-sm);
    padding-bottom: var(--space-xs);
    border-bottom: 1px solid var(--border-secondary);
}

.prop-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 12px;
}

.prop-label {
    color: var(--text-secondary);
    font-family: var(--font-data);
}

.prop-value {
    color: var(--text-primary);
    font-family: var(--font-data);
    text-align: right;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
}

.prop-value.pass { color: var(--status-pass); }
.prop-value.fail { color: var(--status-fail); }
.prop-value.warning { color: var(--status-warning); }

/* Input Fields */
.input-field {
    width: 100%;
    padding: 6px var(--space-sm);
    font-size: 12px;
    font-family: var(--font-data);
    color: var(--text-primary);
    background: var(--bg-input);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    outline: none;
    transition: border-color 0.15s, background-color 0.3s;
}

.input-field:focus {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.input-field::placeholder {
    color: var(--text-muted);
}

/* Dropdown */
.dropdown {
    width: 100%;
    padding: 6px var(--space-sm);
    font-size: 12px;
    font-family: var(--font-data);
    color: var(--text-primary);
    background: var(--bg-input);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    outline: none;
    cursor: pointer;
    min-height: 44px;
    flex-shrink: 0;
}

.dropdown:focus {
    border-color: var(--accent-primary);
}

/* Select dropdown options (for light theme) */
.theme-light select option {
    background: var(--bg-input);
    color: var(--text-primary);
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-xs);
    padding: 6px 12px;
    font-size: 12px;
    font-family: var(--font-body);
    font-weight: 500;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.15s;
    border: 1px solid transparent;
    white-space: nowrap;
}

.btn-primary {
    background: var(--button-primary);
    color: white;
    border-color: var(--button-primary);
}

.btn-primary:hover {
    background: var(--button-hover);
}

.btn-secondary {
    background: transparent;
    color: var(--text-secondary);
    border-color: var(--border-primary);
}

.btn-secondary:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

.btn-success {
    background: var(--status-pass);
    color: white;
}

.btn-danger {
    background: var(--status-fail);
    color: white;
}

.btn-sm {
    padding: 4px 8px;
    font-size: 11px;
}

.btn-lg {
    padding: 10px 20px;
    font-size: 14px;
}

.btn-block {
    width: 100%;
}

.btn-group {
    display: flex;
    gap: 2px;
}

.btn-group .btn {
    border-radius: 0;
}

.btn-group .btn:first-child {
    border-radius: var(--radius-sm) 0 0 var(--radius-sm);
}

.btn-group .btn:last-child {
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

/* Cards */
.card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    overflow: hidden;
}

.card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-primary);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
}

.card-body {
    padding: var(--space-md);
}

/* Data Tables */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-family: var(--font-data);
}

.data-table th {
    padding: var(--space-sm);
    text-align: left;
    font-weight: 600;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-primary);
    position: sticky;
    top: 0;
    z-index: 1;
}

.data-table td {
    padding: 6px var(--space-sm);
    border-bottom: 1px solid var(--border-secondary);
    color: var(--text-primary);
}

.data-table tr:hover td {
    background: var(--bg-hover);
}

.data-table tr.selected td {
    background: rgba(59, 130, 246, 0.2);
}

.data-table .cell-pass { color: var(--status-pass); }
.data-table .cell-fail { color: var(--status-fail); }
.data-table .cell-warning { color: var(--status-warning); }

/* Status Badges */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    font-family: var(--font-data);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-radius: 10px;
}

.badge-pass {
    background: rgba(34, 197, 94, 0.2);
    color: var(--status-pass);
}

.badge-fail {
    background: rgba(239, 68, 68, 0.2);
    color: var(--status-fail);
}

.badge-warning {
    background: rgba(245, 158, 11, 0.2);
    color: var(--status-warning);
}

.badge-info {
    background: rgba(59, 130, 246, 0.2);
    color: var(--status-info);
}

/* Alert/Message Boxes */
.alert {
    padding: var(--space-md);
    border-radius: var(--radius-md);
    font-size: 12px;
    margin-bottom: var(--space-md);
}

.alert-success {
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid var(--status-pass);
    color: var(--status-pass);
}

.alert-error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--status-fail);
    color: var(--status-fail);
}

.alert-warning {
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid var(--status-warning);
    color: var(--status-warning);
}

/* Progress/Loading */
.progress-bar {
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: 2px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: var(--accent-primary);
    transition: width 0.3s ease;
}

.spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-primary);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Bottom Panel */
.bottom-panel {
    height: 200px;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-primary);
    flex-shrink: 0;
}

.bottom-panel.collapsed {
    height: 32px;
}

.panel-tabs {
    display: flex;
    align-items: center;
    height: 32px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-primary);
    padding: 0 var(--space-sm);
    gap: 2px;
}

.panel-tab {
    padding: 0 var(--space-md);
    height: 28px;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
}

.panel-tab:hover {
    color: var(--text-primary);
}

.panel-tab.active {
    color: var(--text-accent);
    border-bottom-color: var(--accent-primary);
}

.panel-tab .count {
    margin-left: var(--space-xs);
    padding: 1px 6px;
    font-size: 10px;
    border-radius: 10px;
    background: var(--bg-hover);
}

.panel-tab .count.error {
    background: var(--status-fail);
    color: white;
}

.panel-tab .count.warning {
    background: var(--status-warning);
    color: black;
}

.panel-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-sm);
    font-family: var(--font-data);
    font-size: 11px;
}

.log-entry {
    padding: 2px 0;
    color: var(--text-secondary);
}

.log-entry .timestamp {
    color: var(--text-muted);
    margin-right: var(--space-sm);
}

.log-entry.error { color: var(--status-fail); }
.log-entry.warning { color: var(--status-warning); }
.log-entry.success { color: var(--status-pass); }

/* Modal */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(4px);
}

.modal {
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    min-width: 400px;
    max-width: 90vw;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-lg);
}

.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border-primary);
}

.modal-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.modal-close {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: var(--radius-sm);
}

.modal-close:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

.modal-body {
    flex: 1;
    padding: var(--space-lg);
    overflow-y: auto;
}

.modal-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-sm);
    padding: var(--space-md) var(--space-lg);
    border-top: 1px solid var(--border-primary);
}

/* Form */
.form-group {
    margin-bottom: var(--space-md);
}

.form-label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-secondary);
    margin-bottom: var(--space-xs);
}

.form-row {
    display: flex;
    gap: var(--space-md);
}

.form-row > * {
    flex: 1;
}

/* Checklist */
.checklist {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-md);
}

.checklist-item {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: 12px;
    cursor: pointer;
}

.checklist-item input {
    width: 14px;
    height: 14px;
    accent-color: var(--accent-primary);
}

/* Upload Area */
.upload-area {
    border: 2px dashed var(--border-primary);
    border-radius: var(--radius-md);
    padding: 12px 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.upload-area:hover {
    border-color: var(--accent-primary);
    background: rgba(59, 130, 246, 0.05);
}

.upload-area .icon {
    font-size: 24px;
    color: var(--text-muted);
    margin-bottom: var(--space-sm);
}

.upload-area .text {
    font-size: 12px;
    color: var(--text-secondary);
}

/* Divider */
.divider {
    height: 1px;
    background: var(--border-primary);
    margin: var(--space-md) 0;
}

.divider-vertical {
    width: 1px;
    background: var(--border-primary);
    margin: 0 var(--space-md);
}

/* Utilities */
.text-muted { color: var(--text-muted); }
.text-secondary { color: var(--text-secondary); }
.text-primary { color: var(--text-primary); }
.text-accent { color: var(--text-accent); }
.text-pass { color: var(--status-pass); }
.text-fail { color: var(--status-fail); }
.text-warning { color: var(--status-warning); }

.font-mono { font-family: var(--font-data); }
.font-display { font-family: var(--font-display); }

.mt-sm { margin-top: var(--space-sm); }
.mt-md { margin-top: var(--space-md); }
.mt-lg { margin-top: var(--space-lg); }
.mb-sm { margin-bottom: var(--space-sm); }
.mb-md { margin-bottom: var(--space-md); }
.mb-lg { margin-bottom: var(--space-lg); }

.flex { display: flex; }
.flex-1 { flex: 1; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-sm { gap: var(--space-sm); }
.gap-md { gap: var(--space-md); }

.hidden { display: none !important; }
.collapsed { display: none; }

/* Empty State */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-2xl);
    color: var(--text-muted);
    text-align: center;
}

.empty-state .icon {
    font-size: 48px;
    margin-bottom: var(--space-md);
    opacity: 0.5;
}

.empty-state .title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: var(--space-xs);
}

.empty-state .description {
    font-size: 12px;
}
"""

# Keep FULL_CSS for compatibility
FULL_CSS = EDA_CSS
INJECTED_CSS = EDA_CSS
THEME = EDA_THEME
LIGHT_THEME = LIGHT_THEME
