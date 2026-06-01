"""Professional EDA-style layout for Layout Review Tool.

Inspired by Cadence Virtuoso, Synopsys Design Compiler - industrial/utilitarian aesthetic.
Multi-panel layout with high information density for chip design workflows.
Uses dcc.Tabs for proper callback integration.
"""

from dash import html, dcc
from app.routing_config import create_routing_config_tab
from app.routing_review import create_routing_review_tab


def create_layout():
    """Create the EDA-style main application layout.

    Returns:
        html.Div with complete EDA-style UI structure
    """
    return html.Div([
        # Theme store - persists theme preference
        dcc.Store(id='theme-store', data='dark'),

        # Header Bar
        _create_header_bar(),

        # Main Content with Tabs
        dcc.Tabs(id='tabs', value='tab-view', children=[
            dcc.Tab(label='Layout View', value='tab-view', children=_create_layout_view_content()),
            dcc.Tab(label='Routing Config', value='tab-routing-config',
                    children=create_routing_config_tab()),
            dcc.Tab(label='Routing Review', value='tab-routing-review',
                    children=create_routing_review_tab()),
            dcc.Tab(label='Report Export', value='tab-export', children=_create_export_content()),
        ], className='eda-tabs'),

        # Hidden modals
        html.Div(id='rule-editor-modal', style={'display': 'none'}, children=_create_rule_editor_modal_content()),
        html.Div(id='net-detail-modal', style={'display': 'none'}, children=_create_net_detail_modal_content()),

        # Download components
        dcc.Download(id='download-config'),
        dcc.Download(id='download-report'),

        # Store components
        dcc.Store(id='app-state-store'),
        dcc.Store(id='selected-rule-store'),
        dcc.Store(id='filtered-nets-store'),
        dcc.Store(id='selected-net-detail-store'),

        # Interval
        dcc.Interval(id='interval-component', interval=1000, n_intervals=0),
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
        html.Div([
            # Left Sidebar
            _create_left_sidebar(),

            # Main Canvas Area
            _create_main_canvas(),

            # Right Panel (Properties)
            _create_right_panel(),
        ], className='main-content'),

        # Bottom Panel (Logs/Output)
        _create_bottom_panel(),
    ])


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
                    html.Span('Name:', className='prop-label'),
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
                    html.Span('0 ns', id='prop-tau-rc', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('t_pd(50%):', className='prop-label'),
                    html.Span('0 ns', id='prop-tpd', className='prop-value'),
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


def _create_bottom_panel():
    """Create the bottom panel with logs and output."""
    return html.Div([
        # Panel Tabs
        html.Div([
            html.Button([
                html.Span('Output'),
                html.Span('0', id='output-count', className='count'),
            ], className='panel-tab active', id='tab-output'),
            html.Button([
                html.Span('Violations'),
                html.Span('0', id='violations-panel-count', className='count error'),
            ], className='panel-tab', id='tab-violations'),
            html.Button([
                html.Span('Matching'),
                html.Span('0', id='matching-count', className='count'),
            ], className='panel-tab', id='tab-matching'),
        ], className='panel-tabs'),

        # Panel Content
        html.Div([
            # Output Log
            html.Div(id='output-log', className='panel-body', style={'display': 'block'}),
            # Violations Table
            html.Div(id='violations-panel', className='panel-body', style={'display': 'none'}),
            # Matching Table
            html.Div(id='matching-panel', className='panel-body', style={'display': 'none'}),
        ], style={'flex': 1, 'overflow': 'hidden'}),
    ], className='bottom-panel', id='bottom-panel')


# =============================================================================
# Configuration Tab Content
# =============================================================================

def _create_config_content():
    """Create configuration tab content."""
    from dash import dash_table
    return html.Div([
        # Config Management Card
        html.Div([
            html.Div('Configuration Management', className='card-header'),
            html.Div([
                html.Div([
                    html.Div([
                        html.Label('Load Preset', className='form-label'),
                        dcc.Dropdown(
                            id='preset-selector-config',
                            options=[
                                {'label': 'SRAM 7nm', 'value': 'sram_7nm'},
                                {'label': 'SRAM 5nm', 'value': 'sram_5nm'},
                                {'label': 'Analog Layout', 'value': 'analog'},
                            ],
                            value='sram_7nm',
                            className='dropdown',
                        ),
                    ], className='form-group'),
                    html.Div([
                        html.Label('Import/Export', className='form-label'),
                        html.Div([
                            html.Button('Import Config', id='btn-import-config', className='btn btn-secondary btn-sm'),
                            html.Button('Export Config', id='btn-export-config', className='btn btn-success btn-sm'),
                        ], className='btn-group'),
                    ], className='form-group'),
                ], className='form-row'),
            ], className='card-body'),
        ], className='card'),

        # Technology Parameters
        html.Div([
            html.Div('Technology Parameters', className='card-header'),
            html.Div([
                html.Div([
                    html.Div([
                        html.Label('Process Node', className='form-label'),
                        dcc.Input(id='tech-node', value='7nm', disabled=True, className='input-field'),
                    ], className='form-group'),
                    html.Div([
                        html.Label('Voltage (V)', className='form-label'),
                        dcc.Input(id='tech-voltage', value='0.75', disabled=True, className='input-field'),
                    ], className='form-group'),
                    html.Div([
                        html.Label('Temperature (°C)', className='form-label'),
                        dcc.Input(id='tech-temp', value='85', disabled=True, className='input-field'),
                    ], className='form-group'),
                    html.Div([
                        html.Label('Total Rules', className='form-label'),
                        dcc.Input(id='total-rules', value='19', disabled=True, className='input-field'),
                    ], className='form-group'),
                ], className='form-row'),
            ], className='card-body'),
        ], className='card'),

        # Check Rules Card
        html.Div([
            html.Div([
                html.Span('Check Rules'),
                html.Div([
                    html.Button('+ Add Rule', id='btn-add-rule', className='btn btn-primary btn-sm'),
                    html.Button('Refresh', id='btn-refresh-rules', className='btn btn-secondary btn-sm'),
                ], style={'display': 'flex', 'gap': '8px'}),
            ], className='card-header'),
            html.Div([
                dash_table.DataTable(
                    id='rules-datatable',
                    data=[],
                    columns=[
                        {'name': 'Name', 'id': 'Name', 'editable': True},
                        {'name': 'Type', 'id': 'Type', 'presentation': 'dropdown'},
                        {'name': 'Severity', 'id': 'Severity', 'presentation': 'dropdown'},
                        {'name': 'Enabled', 'id': 'Enabled'},
                        {'name': 'Targets', 'id': 'Targets', 'editable': True},
                    ],
                    editable=True,
                    dropdown={
                        'Type': {'options': [{'label': 'hard', 'value': 'hard'}, {'label': 'soft', 'value': 'soft'}]},
                        'Severity': {'options': [{'label': 'critical', 'value': 'critical'}, {'label': 'warning', 'value': 'warning'}, {'label': 'info', 'value': 'info'}]},
                    },
                    style_cell={'textAlign': 'left', 'fontSize': 11, 'fontFamily': 'var(--font-data)', 'backgroundColor': 'var(--bg-input)', 'color': 'var(--text-primary)'},
                    style_header={'fontWeight': '600', 'backgroundColor': 'var(--bg-tertiary)', 'color': 'var(--text-secondary)', 'textTransform': 'uppercase', 'fontSize': '10px'},
                    style_data_conditional=[
                        {'if': {'filter_query': '{Severity} = "critical"'}, 'color': 'var(--status-fail)'},
                        {'if': {'filter_query': '{Severity} = "warning"'}, 'color': 'var(--status-warning)'},
                    ],
                    page_size=15,
                    sort_action='native',
                    filter_action='native',
                    row_selectable='single',
                ),
                html.Div([
                    html.Button('Apply Changes', id='btn-apply-table-changes', className='btn btn-success btn-sm'),
                    html.Span(id='table-edit-status', className='text-muted', style={'fontSize': '11px', 'marginLeft': '8px'}),
                ], style={'marginTop': '8px'}),
            ], id='rules-table-container', className='card-body'),
        ], className='card'),
    ], style={'padding': '16px'})


# =============================================================================
# Review Tab Content
# =============================================================================

def _create_review_content():
    """Create review tab content."""
    from dash import dash_table
    return html.Div([
        # Review Summary
        html.Div([
            html.Div('Review Summary', className='card-header'),
            html.Div([
                html.Div([
                    html.Div([
                        html.H4('0', id='summary-total-nets', style={'textAlign': 'center', 'margin': '0', 'fontFamily': 'var(--font-data)'}),
                        html.Span('Total Nets', className='text-muted', style={'fontSize': '10px', 'display': 'block'}),
                    ], className='flex-1'),
                    html.Div([
                        html.H4('0', id='summary-critical', className='text-fail', style={'textAlign': 'center', 'margin': '0', 'fontFamily': 'var(--font-data)'}),
                        html.Span('Critical', className='text-muted', style={'fontSize': '10px', 'display': 'block'}),
                    ], className='flex-1'),
                    html.Div([
                        html.H4('0', id='summary-warnings', className='text-warning', style={'textAlign': 'center', 'margin': '0', 'fontFamily': 'var(--font-data)'}),
                        html.Span('Warnings', className='text-muted', style={'fontSize': '10px', 'display': 'block'}),
                    ], className='flex-1'),
                    html.Div([
                        html.H4('0', id='summary-info', className='text-accent', style={'textAlign': 'center', 'margin': '0', 'fontFamily': 'var(--font-data)'}),
                        html.Span('Info', className='text-muted', style={'fontSize': '10px', 'display': 'block'}),
                    ], className='flex-1'),
                ], className='flex', style={'gap': '16px'}),
            ], className='card-body'),
        ], className='card', style={'marginBottom': '16px'}),

        # Quick Filters
        html.Div([
            html.Div('Quick Filters', className='card-header'),
            html.Div([
                dcc.Checklist(
                    id='check-filter',
                    options=[
                        {'label': ' Critical Only', 'value': 'critical'},
                        {'label': ' Warnings', 'value': 'warning'},
                        {'label': ' Info', 'value': 'info'},
                    ],
                    value=['critical', 'warning'],
                    className='checklist',
                ),
            ], className='card-body'),
        ], className='card', style={'marginBottom': '16px'}),

        # Violations Table
        html.Div([
            html.Div([
                html.Span('Violations'),
                html.Span('0', id='violation-count-badge', className='badge badge-fail'),
            ], className='card-header'),
            html.Div([
                dash_table.DataTable(
                    id='violations-table',
                    data=[],
                    columns=[{'name': k, 'id': k} for k in ['Rule', 'Severity', 'Net', 'Type', 'Message']],
                    style_cell={'textAlign': 'left', 'fontSize': 11, 'fontFamily': 'var(--font-data)', 'backgroundColor': 'var(--bg-input)', 'color': 'var(--text-primary)'},
                    style_header={'fontWeight': '600', 'backgroundColor': 'var(--bg-tertiary)', 'color': 'var(--text-secondary)', 'textTransform': 'uppercase', 'fontSize': '10px'},
                    style_data_conditional=[
                        {'if': {'filter_query': '{Severity} = "critical"'}, 'backgroundColor': 'rgba(239, 68, 68, 0.1)'},
                        {'if': {'filter_query': '{Severity} = "warning"'}, 'backgroundColor': 'rgba(245, 158, 11, 0.1)'},
                    ],
                    page_size=10,
                    sort_action='native',
                    row_selectable='single',
                ),
            ], id='violations-table-container', className='card-body'),
        ], className='card', style={'marginBottom': '16px'}),

        # Matching Analysis
        html.Div([
            html.Div([
                html.Span('Matching Analysis'),
                html.Span('0', id='matching-count-badge', className='badge badge-info'),
            ], className='card-header'),
            html.Div([
                dash_table.DataTable(
                    id='matching-table',
                    data=[],
                    columns=[{'name': k, 'id': k} for k in ['Net Pair', 'Score', 'Length Ratio', 'R Ratio', 'Issues']],
                    style_cell={'textAlign': 'left', 'fontSize': 11, 'fontFamily': 'var(--font-data)', 'backgroundColor': 'var(--bg-input)', 'color': 'var(--text-primary)'},
                    style_header={'fontWeight': '600', 'backgroundColor': 'var(--bg-tertiary)', 'color': 'var(--text-secondary)', 'textTransform': 'uppercase', 'fontSize': '10px'},
                    style_data_conditional=[
                        {'if': {'filter_query': '{Score} < 60'}, 'backgroundColor': 'rgba(239, 68, 68, 0.1)'},
                        {'if': {'filter_query': '{Score} >= 80'}, 'backgroundColor': 'rgba(34, 197, 94, 0.1)'},
                    ],
                    page_size=10,
                    sort_action='native',
                ),
            ], id='matching-table-container', className='card-body'),
        ], className='card'),
    ], style={'padding': '16px'})


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
