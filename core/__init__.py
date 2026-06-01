"""Core analysis modules for Layout Review Tool."""

from .data_parsing import (
    parse_shape_txt,
    import_shape_from_file,
    process_yaml_batch_import,
    parse_yaml_batch_config,
)
from .visualization import (
    LayerColorManager,
    LAYER_FILL_COLORS,
    LAYER_DISPLAY_NAMES,
    LAYER_PRIORITY_ORDER,
    VIA_STROKE_COLORS,
    get_layer_color,
    get_layer_display_name,
    is_via_layer,
    create_net_visualization,
)
from .path_analysis import (
    analyze_sd_to_gate_path,
    get_view_for_visible_layers,
)
from .rc_calculator import (
    parse_polygons_to_wires,
    calculate_net_rc,
    _extract_layer_number as extract_layer_number,
)
from .matching_analyzer import (
    analyze_pair_matching,
)
from .report_visualization import (
    create_polygons_figure,
    create_violation_figure,
    get_layer_color as report_get_layer_color,
    is_via_layer as report_is_via_layer,
)

__all__ = [
    # data_parsing
    'parse_shape_txt',
    'import_shape_from_file',
    'process_yaml_batch_import',
    'parse_yaml_batch_config',
    # visualization
    'LayerColorManager',
    'LAYER_FILL_COLORS',
    'LAYER_DISPLAY_NAMES',
    'LAYER_PRIORITY_ORDER',
    'VIA_STROKE_COLORS',
    'get_layer_color',
    'get_layer_display_name',
    'is_via_layer',
    'create_net_visualization',
    # path_analysis
    'analyze_sd_to_gate_path',
    'get_view_for_visible_layers',
    # rc_calculator
    'parse_polygons_to_wires',
    'calculate_net_rc',
    '_extract_layer_number as extract_layer_number',
    # matching_analyzer
    'analyze_pair_matching',
    # report_visualization
    'create_polygons_figure',
    'create_violation_figure',
    'report_get_layer_color',
    'report_is_via_layer',
]
