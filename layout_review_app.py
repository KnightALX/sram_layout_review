#!/usr/bin/env python3
"""
Professional Layout Review Tool - Main Application
专业级版图Review工具 - 主应用程序

A refactored version with modular architecture:
- core/       - Data parsing, visualization, path analysis
- app/        - State management, theme, layout, callbacks

Usage:
    python layout_review_app.py [port]

    Access at http://localhost:<port>
"""

import os
import sys

# Third-party imports
from dash import Dash

from app.callbacks import register_callbacks
from app.layout import create_layout

# Application imports
from app.theme import FULL_CSS


def create_app() -> Dash:
    """Create and configure the Dash application.

    Returns:
        Configured Dash application instance
    """
    # Use local assets folder for offline-compatible styling
    assets_folder = os.path.join(os.path.dirname(__file__), 'assets')

    # Build external stylesheets from local assets
    external_stylesheets = []
    if os.path.exists(assets_folder):
        # Add local Bootstrap and Font Awesome CSS
        css_files = [f for f in os.listdir(assets_folder) if f.endswith('.css')]
        for css_file in css_files:
            external_stylesheets.append(os.path.join(assets_folder, css_file))

    app = Dash(
        __name__,
        external_stylesheets=external_stylesheets if external_stylesheets else None,
        suppress_callback_exceptions=False,
    )

    app.title = "Layout Review Pro"

    # Set index string with professional styling
    app.index_string = _build_index_string()

    # Set application layout
    app.layout = create_layout()

    # Register all callbacks
    register_callbacks(app)

    return app


def _build_index_string() -> str:
    """Build custom HTML index string with professional styling."""
    css = FULL_CSS
    # Dash uses {% %} template syntax which we must preserve exactly
    template = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            """ + css + """
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            <script>
                // Theme initialization and persistence - default to light
                (function() {
                    function setTheme(theme) {
                        document.documentElement.classList.remove('theme-dark', 'theme-light');
                        document.documentElement.classList.add('theme-' + theme);
                        localStorage.setItem('layout-review-theme', theme);
                        // Update label if exists
                        var label = document.getElementById('theme-label');
                        if (label) {
                            label.textContent = theme === 'dark' ? 'Dark' : 'Light';
                        }
                    }

                    function getStoredTheme() {
                        // Default to light theme if no stored preference
                        return localStorage.getItem('layout-review-theme') || 'light';
                    }

                    function toggleTheme() {
                        var current = getStoredTheme();
                        var newTheme = current === 'dark' ? 'light' : 'dark';
                        setTheme(newTheme);
                    }

                    // Initialize theme on page load
                    setTheme(getStoredTheme());

                    // Set up theme toggle using event delegation on document
                    document.addEventListener('click', function(e) {
                        var target = e.target;
                        var foundToggle = false;

                        // Walk up the DOM to find if we clicked on or inside theme-toggle
                        while (target && target !== document.body) {
                            if (target.id === 'theme-toggle') {
                                foundToggle = true;
                                break;
                            }
                            target = target.parentElement;
                        }

                        if (foundToggle) {
                            e.preventDefault();
                            toggleTheme();
                        }
                    });
                })();
            </script>
            {%renderer%}
        </footer>
    </body>
</html>"""
    return template


def main():
    """Main entry point for the application."""
    # Determine port
    port = 8050
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}, using default 8050")

    print("=" * 70)
    print("Professional Layout Review Tool")
    print("=" * 70)
    print("\nFeatures:")
    print("  - Multi-net layout visualization")
    print("  - Professional RC extraction and analysis")
    print("  - Configurable check rules with regex support")
    print("  - EM/IR analysis")
    print("  - Signal matching analysis (BL/BLB, WL)")
    print("  - PPTX and PDF report generation")
    print("\nStarting server...")
    print(f"  URL: http://localhost:{port}")
    print("=" * 70)

    app = create_app()
    app.run(debug=True, port=port)


if __name__ == '__main__':
    main()
