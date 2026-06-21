"""Professional EDA-style layout for Layout Review Tool.

Inspired by Cadence Virtuoso, Synopsys Design Compiler - industrial/utilitarian aesthetic.
Multi-panel layout with high information density for chip design workflows.
Uses dcc.Tabs for proper callback integration.
"""

from dash import dcc, html

from app.routing_config import create_routing_config_tab
from app.routing_review import create_routing_review_tab


def create_layout():
    """Create the EDA-style main application layout.

    Returns:
        html.Div with complete EDA-style UI structure
    """
    return html.Div([
        # Theme store - persists theme preference
        dcc.Store(id='theme-store', data='light'),

        # Header Bar
        _create_header_bar(),

        # Main Content with Tabs
        dcc.Tabs(
            id='tabs',
            value='tab-view',
            parent_className='tabs-shell',
            className='eda-tabs',
            content_className='eda-tab-content',
            children=[
                dcc.Tab(label='Layout View', value='tab-view',
                        children=_create_layout_view_content()),
                dcc.Tab(label='Routing Config', value='tab-routing-config',
                        children=create_routing_config_tab()),
                dcc.Tab(label='Routing Review', value='tab-routing-review',
                        children=create_routing_review_tab()),
                dcc.Tab(label='Report Export', value='tab-export',
                        children=_create_export_content()),
            ],
        ),

        # Shared nets metadata (updated on upload; read by routing tabs)
        dcc.Store(id='nets-meta-store', data={'count': 0, 'names': []}),

        # Interval — retained for routing error banner refresh on tab switch
        dcc.Interval(id='interval-component', interval=5000, n_intervals=0),
    ], className='app-container')


def _create_header_bar():
    """Create the header bar with logo and status indicators."""
    return html.Div([
        # Left: Logo and Title
        html.Div([
            html.Div('LAYOUT REVIEW PRO', className='header-logo'),
            html.Div('Advanced IC Layout Verification', className='header-subtitle'),
        ], className='header-title'),

        # Right: Status indicators + Theme Toggle
        html.Div([
            # Config status
            html.Div([
                html.Span('Config:', className='status-indicator-label'),
                html.Span('SRAM 7nm', id='current-config-info', className='status-indicator-value'),
            ], className='header-status'),

            html.Div(className='divider-vertical'),

            # Net count
            html.Div([
                html.Span('Nets:', className='status-indicator-label'),
                html.Span('0', id='net-count-badge', className='status-indicator-value'),
            ], className='header-status'),

            html.Div(className='divider-vertical'),

            # Online indicator
            html.Div([
                html.Span(className='status-dot online'),
                html.Span('Ready', className='status-indicator-ready'),
            ], className='header-status'),

            html.Div(className='divider-vertical'),

            # Theme Toggle
            html.Button([
                html.Span('☀', className='theme-toggle-icon sun'),
                html.Span('☾', className='theme-toggle-icon moon'),
                html.Span('Light', id='theme-label', className='theme-toggle-label'),
            ], id='theme-toggle', className='theme-toggle-btn'),
        ], className='header-status'),
    ], className='header-bar')


# =============================================================================
# Layout View Tab Content
# =============================================================================

def _create_layout_view_content():
    """Create Layout View tab content with EDA-style panels."""
    return html.Div([
        # Left Sidebar
        _create_left_sidebar(),

        # Main Canvas Area
        _create_main_canvas(),

        # Right Panel (Properties)
        _create_right_panel(),
    ], className='main-content')


def _create_left_sidebar():
    """Create the left sidebar with file tree and net selection."""
    return html.Div([
        # File Import Section
        html.Div([
            html.Div([
                html.Span('File Import'),
                html.Span(id='upload-status', className='text-muted', style={'fontSize': '10px'}),
            ], className='sidebar-header', id='file-import-header'),
            html.Div([
                dcc.Upload(
                    id='upload-data',
                    children=html.Div([
                        html.Span('+ Select Files', className='tree-item'),
                    ], className='upload-area'),
                    multiple=True,
                ),
                html.Label(
                    [
                        html.Span("+ Select Folder", className="tree-item"),
                    ],
                    id="folder-upload-label",
                    className="upload-area",
                    style={"marginTop": "8px", "cursor": "pointer"},
                ),
                dcc.Store(id="folder-upload-payload"),
                html.Button(id="folder-upload-trigger", style={"display": "none"}, n_clicks=0),
                html.Div([
                    html.Span('YAML Config', className='text-muted', style={'fontSize': '10px', 'marginTop': '8px', 'display': 'block'}),
                    dcc.Upload(
                        id='upload-yaml',
                        children=html.Div([
                            html.Span('+ Import YAML', className='tree-item'),
                        ], className='upload-area'),
                        accept='.yaml,.yml',
                        multiple=False,
                    ),
                    html.Div(id='yaml-upload-status', className='text-muted', style={'fontSize': '10px', 'marginTop': '4px'}),
                ]),
            ], className='sidebar-content', id='file-import-content'),
        ], className='sidebar-section'),

        # Net Selection Section
        html.Div([
            html.Div([
                html.Span('Net Selection'),
                html.Span(id='net-selector-count', className='text-muted', style={'fontSize': '10px'}),
            ], className='sidebar-header', id='net-selection-header'),
            html.Div([
                # Net filter
                dcc.Input(
                    id='net-filter',
                    type='text',
                    placeholder='Filter nets...',
                    className='input-field',
                    style={'marginBottom': '8px'},
                ),

                # Net dropdown selector
                dcc.Dropdown(
                    id='net-selector',
                    options=[],
                    value=[],
                    multi=True,
                    placeholder='Select nets...',
                    className='net-dropdown',
                ),

                # Selection controls
                html.Div([
                    html.Button('Select All', id='btn-select-all', className='btn btn-secondary btn-sm', style={'flex': 1}),
                    html.Button('Clear', id='btn-clear', className='btn btn-secondary btn-sm', style={'flex': 1}),
                ], className='btn-group', style={'marginTop': '8px'}),
            ], className='net-selection-body', id='net-selection-content'),
        ], className='sidebar-section-fixed'),

        # Path Config Section
        html.Div([
            html.Div([
                html.Span('Path Config'),
            ], className='sidebar-header', id='path-config-header'),
            html.Div([
                html.Div([
                    html.Label('Start Layers (SD)', className='form-label'),
                    dcc.Input(id='sd-layers', type='text', value='n_sd,p_sd', className='input-field'),
                ], className='form-group', style={'marginBottom': '8px'}),
                html.Div([
                    html.Label('End Layers (Gate)', className='form-label'),
                    dcc.Input(id='poly-layers', type='text', value='poly', className='input-field'),
                ], className='form-group', style={'marginBottom': '8px'}),
                html.Div(id='path-config-status', className='text-muted', style={'fontSize': '10px'}),
                html.Button('Apply', id='btn-apply-path-config', className='btn btn-primary btn-sm btn-block'),
            ], className='sidebar-content', id='path-config-content'),
        ], className='sidebar-section'),

        # View Options Section
        html.Div([
            html.Div([
                html.Span('View Options'),
            ], className='sidebar-header', id='view-options-header'),
            html.Div([
                html.Div([
                    html.Button('Fit', id='btn-fit', className='btn btn-secondary btn-sm', style={'flex': 1}),
                    html.Button('Zoom In', id='btn-zoom-in', className='btn btn-secondary btn-sm', style={'flex': 1}),
                    html.Button('Zoom Out', id='btn-zoom-out', className='btn btn-secondary btn-sm', style={'flex': 1}),
                ], className='btn-group', style={'marginBottom': '8px'}),
                html.Div([
                    html.Button('All Layers', id='btn-all-layer', className='btn btn-secondary btn-sm', style={'flex': 1}),
                    html.Button('No Layers', id='btn-no-layer', className='btn btn-secondary btn-sm', style={'flex': 1}),
                ], className='btn-group'),
            ], className='sidebar-content', id='view-options-content'),
        ], className='sidebar-section'),
    ], className='sidebar')


def _create_main_canvas():
    """Create the main canvas area with toolbar and graph."""
    return html.Div([
        # Toolbar
        html.Div([
            html.Div([
                html.Span('Zoom:', className='toolbar-label'),
                html.Span('1.00x', id='zoom-level', className='toolbar-value'),
            ], className='toolbar-group'),

            html.Div([
                html.Button('◀', id='btn-canvas-zoom-out', className='toolbar-btn', title='Zoom Out'),
                html.Button('▶', id='btn-canvas-zoom-in', className='toolbar-btn', title='Zoom In'),
                html.Button('⊞', id='btn-canvas-fit', className='toolbar-btn', title='Fit to View'),
            ], className='toolbar-group'),

            html.Div([
                html.Button('▲', id='btn-pan-up', className='toolbar-btn', title='Pan Up'),
                html.Button('▼', id='btn-pan-down', className='toolbar-btn', title='Pan Down'),
                html.Button('◀', id='btn-pan-left', className='toolbar-btn', title='Pan Left'),
                html.Button('▶', id='btn-pan-right', className='toolbar-btn', title='Pan Right'),
            ], className='toolbar-group'),
        ], className='canvas-toolbar'),

        # Graph Container
        html.Div([
            dcc.Graph(
                id='layout-graph',
                style={'width': '100%', 'height': '100%'},
                config={
                    'displayModeBar': True,
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                    'displaylogo': False,
                }
            ),
        ], className='graph-container', id='layout-graph-container'),
    ], className='canvas-area')


def _create_right_panel():
    """Create the right properties panel."""
    return html.Div([
        # Properties Header
        html.Div([
            html.Span('Properties'),
        ], className='panel-header'),

        # Properties Content
        html.Div([
            # Selected Net Info
            html.Div([
                html.Div('SELECTED NET', className='prop-group-header'),
                html.Div([
                    html.Span('ID:', className='prop-label'),
                    html.Span('--', id='prop-net-id', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Source:', className='prop-label'),
                    html.Span('--', id='prop-source', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Net:', className='prop-label'),
                    html.Span('--', id='prop-net-name', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Layers:', className='prop-label'),
                    html.Span('0', id='prop-layer-count', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Shapes:', className='prop-label'),
                    html.Span('0', id='prop-shape-count', className='prop-value'),
                ], className='prop-row'),
            ], className='prop-group'),

            # RC Summary
            html.Div([
                html.Div('RC SUMMARY', className='prop-group-header'),
                html.Div([
                    html.Span('Resistance:', className='prop-label'),
                    html.Span('0 Ω', id='prop-resistance', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Capacitance:', className='prop-label'),
                    html.Span('0 fF', id='prop-capacitance', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Length:', className='prop-label'),
                    html.Span('0 μm', id='prop-length', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('tau_rc:', className='prop-label'),
                    html.Span('0 ps', id='prop-tau-rc', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('t_pd(50%):', className='prop-label'),
                    html.Span('0 ps', id='prop-tpd', className='prop-value'),
                ], className='prop-row'),
            ], className='prop-group'),

            # Violations Summary
            html.Div([
                html.Div('VIOLATIONS', className='prop-group-header'),
                html.Div([
                    html.Span('Critical:', className='prop-label'),
                    html.Span('0', id='prop-critical', className='prop-value fail'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Warnings:', className='prop-label'),
                    html.Span('0', id='prop-warnings', className='prop-value warning'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Info:', className='prop-label'),
                    html.Span('0', id='prop-info', className='prop-value'),
                ], className='prop-row'),
            ], className='prop-group'),

            # Quick Actions
            html.Div([
                html.Div('ACTIONS', className='prop-group-header'),
                html.Button('Run Full Review', id='btn-run-review-panel', className='btn btn-success btn-block btn-sm'),
                html.Button('Generate Report', id='btn-generate-report-panel', className='btn btn-secondary btn-block btn-sm', style={'marginTop': '8px'}),
            ], className='prop-group'),

            # Config Summary
            html.Div([
                html.Div('CONFIGURATION', className='prop-group-header'),
                html.Div([
                    html.Span('Preset:', className='prop-label'),
                    html.Span('SRAM 7nm', id='prop-preset', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Node:', className='prop-label'),
                    html.Span('7nm', id='prop-node', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Voltage:', className='prop-label'),
                    html.Span('0.75V', id='prop-voltage', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Rules:', className='prop-label'),
                    html.Span('19', id='prop-rules', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    dcc.Dropdown(
                        id='preset-selector',
                        options=[
                            {'label': 'SRAM 7nm', 'value': 'sram_7nm'},
                            {'label': 'SRAM 5nm', 'value': 'sram_5nm'},
                            {'label': 'Analog Layout', 'value': 'analog'},
                        ],
                        value='sram_7nm',
                        className='dropdown',
                        style={'marginTop': '8px'},
                    ),
                ]),
            ], className='prop-group'),
        ], className='panel-content'),
    ], className='right-panel')


# =============================================================================
# Configuration Tab Content / Review Tab Content
# =============================================================================
# Note: the legacy helpers `_create_config_content` and `_create_review_content`
# were removed in 2026-06-06 cleanup. Their replacements live in:
#   - app/routing_config.py :: create_routing_config_tab
#   - app/routing_review.py :: create_routing_review_tab
# (See git history for the deleted implementations if needed.)


# =============================================================================
# Analysis Tab Content
# =============================================================================
# Export Tab Content
# =============================================================================

def _create_export_content():
    """Create export tab content."""
    return html.Div([
        # Report Generation Card
        html.Div([
            html.Div('Generate Report', className='card-header'),
            html.Div([
                html.Div([
                    html.Label('Report Title', className='form-label'),
                    dcc.Input(id='report-title', value='Layout Review Report', className='input-field'),
                ], className='form-group'),
                html.Div([
                    html.Label('Output Directory', className='form-label'),
                    dcc.Input(id='output-dir', value='./output', className='input-field'),
                ], className='form-group'),
                html.Div([
                    html.Label('Export Formats', className='form-label'),
                    dcc.Checklist(
                        id='export-formats',
                        options=[
                            {'label': ' PowerPoint (.pptx)', 'value': 'pptx'},
                            {'label': ' PDF Document (.pdf)', 'value': 'pdf'},
                        ],
                        value=['pptx', 'pdf'],
                        className='checklist',
                    ),
                ], className='form-group'),
                html.Button([html.Span('▶'), 'Generate Reports'], id='btn-generate-report', className='btn btn-primary btn-lg btn-block'),
            ], className='card-body'),
        ], className='card'),

        # Export Status
        html.Div(id='export-status'),

        # Report Preview
        html.Div([
            html.Div('Report Preview', className='card-header'),
            html.Div([
                html.Div('CONTENTS', className='prop-group-header'),
                html.Ul([
                    html.Li('Cover Page with Title and Technology Info'),
                    html.Li('Executive Summary with Statistics'),
                    html.Li('Net Statistics Table (RC, Length, Via Count)'),
                    html.Li('Violation Analysis (Critical/Warning/Info)'),
                    html.Li('Matching Analysis for Signal Pairs'),
                    html.Li('RC Distribution Charts'),
                    html.Li('Net Rankings'),
                    html.Li('Recommendations and Action Items'),
                ], className='font-mono', style={'fontSize': '11px', 'paddingLeft': '16px'}),
            ], className='card-body'),
        ], className='card'),
    ], style={'padding': '16px'})


# =============================================================================
# Modal Content
# =============================================================================

def _create_rule_editor_modal_content():
    """Create rule editor modal content."""
    return html.Div([
        html.Div([
            html.Span('Edit Rule', className='modal-title'),
            html.Button('×', id='btn-close-rule-modal', className='modal-close'),
        ], className='modal-header'),
        html.Div([
            html.Div([
                html.Div([
                    html.Label('Rule ID *', className='form-label'),
                    dcc.Input(id='edit-rule-id', placeholder='e.g., DRC001', className='input-field'),
                ], className='form-group'),
                html.Div([
                    dcc.Checklist(
                        id='edit-rule-enabled',
                        options=[{'label': ' Enabled', 'value': True}],
                        value=[True],
                        className='checklist-item',
                    ),
                ], className='form-group'),
            ], className='form-row'),
            html.Div([
                html.Label('Rule Name *', className='form-label'),
                dcc.Input(id='edit-rule-name', placeholder='Rule name', className='input-field'),
            ], className='form-group'),
            html.Div([
                html.Label('Description', className='form-label'),
                dcc.Textarea(id='edit-rule-description', placeholder='Rule description', className='input-field', rows=2),
            ], className='form-group'),
            html.Div([
                html.Div([
                    html.Label('Constraint Type', className='form-label'),
                    dcc.Dropdown(
                        id='edit-rule-constraint-type',
                        options=[{'label': 'Hard', 'value': 'hard'}, {'label': 'Soft', 'value': 'soft'}, {'label': 'Info', 'value': 'info'}],
                        value='soft',
                        className='dropdown',
                    ),
                ], className='form-group'),
                html.Div([
                    html.Label('Severity', className='form-label'),
                    dcc.Dropdown(
                        id='edit-rule-severity',
                        options=[{'label': 'Critical', 'value': 'critical'}, {'label': 'Warning', 'value': 'warning'}, {'label': 'Info', 'value': 'info'}],
                        value='warning',
                        className='dropdown',
                    ),
                ], className='form-group'),
            ], className='form-row'),
            html.Div([
                html.Label('Target Nets (Regex, comma-separated)', className='form-label'),
                dcc.Input(id='edit-rule-target-nets', placeholder='.*, BL.*, VDD.*', className='input-field'),
            ], className='form-group'),
            html.Div([
                html.Label('Parameters (JSON)', className='form-label'),
                dcc.Textarea(id='edit-rule-parameters', placeholder='{"max_length": 100}', className='input-field', rows=2),
            ], className='form-group'),
            html.Div([
                html.Label('Suggestion', className='form-label'),
                dcc.Textarea(id='edit-rule-suggestion', placeholder='Improvement suggestion', className='input-field', rows=2),
            ], className='form-group'),
            html.Div([
                html.Label('Reference', className='form-label'),
                dcc.Input(id='edit-rule-reference', placeholder='Document reference', className='input-field'),
            ], className='form-group'),
            html.Div(id='rule-edit-validation', className='text-fail', style={'fontSize': '11px'}),
        ], className='modal-body'),
        html.Div([
            html.Button('Delete', id='btn-delete-rule', className='btn btn-danger'),
            html.Button('Cancel', id='btn-cancel-rule-edit', className='btn btn-secondary'),
            html.Button('Apply', id='btn-apply-rule', className='btn btn-secondary'),
            html.Button('Save', id='btn-save-rule', className='btn btn-primary'),
        ], className='modal-footer'),
    ], className='modal')


def _create_net_detail_modal_content():
    """Create net detail modal content."""
    return html.Div([
        html.Div([
            html.Span('Net Details', className='modal-title'),
            html.Button('×', id='btn-close-net-detail-header', className='modal-close'),
        ], className='modal-header'),
        html.Div([
            html.H5(id='detail-net-name', style={'marginBottom': '16px'}),
            html.Div([
                html.Div('RC SUMMARY', className='prop-group-header'),
                html.Div(id='detail-rc-summary'),
            ], className='prop-group'),
            html.Div([
                html.Div('LAYER BREAKDOWN', className='prop-group-header'),
                html.Div(id='detail-layer-breakdown'),
            ], className='prop-group'),
            html.Div([
                html.Div('VIOLATIONS', className='prop-group-header'),
                html.Div(id='detail-violations'),
            ], className='prop-group'),
        ], className='modal-body'),
        html.Div([
            html.Button('Highlight in Layout', id='btn-highlight-net', className='btn btn-primary'),
            html.Button('Close', id='btn-close-net-detail', className='btn btn-secondary'),
        ], className='modal-footer'),
    ], className='modal')
