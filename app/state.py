"""Application state management."""

from typing import Dict, List, Optional
from config_system import LayoutReviewConfig, get_sram_7nm_config


class AppState:
    """Application state singleton for Layout Review Tool.

    Attributes:
        config: Current LayoutReviewConfig instance
        engine: ProfessionalLayoutReviewEngine instance
        nets_data: Dictionary mapping net names to shape data
        review_completed: Whether review has been run
        current_file: Currently loaded file path
        sd_layers: Start layers for path analysis (SD layers)
        poly_layers: End layers for path analysis (Gate/Poly layers)
        path_configured: Whether path configuration has been set
        zoom_level: Current zoom level
        zoom_step: Zoom step factor
        visible_layers: Set of visible layer names (None=all, empty=hidden)
        current_view: Current view range for zoom operations
    """

    def __init__(self):
        self.config: LayoutReviewConfig = get_sram_7nm_config()
        self.engine = None
        self.nets_data: Dict[str, Dict] = {}
        self.review_completed: bool = False
        self.current_file: Optional[str] = None
        self.sd_layers: List[str] = ['n_sd', 'p_sd']
        self.poly_layers: List[str] = ['poly']
        self.path_configured: bool = False
        self.zoom_level: float = 1.0
        self.zoom_step: float = 1.5
        self.visible_layers: Optional[set] = None
        self.current_view: Optional[dict] = None

    def reset(self):
        """Reset application state to initial values."""
        self.nets_data.clear()
        self.review_completed = False
        self.current_file = None
        self.path_configured = False
        self.zoom_level = 1.0
        self.visible_layers = None
        self.current_view = None

    def clear_nets(self):
        """Clear all loaded net data."""
        self.nets_data.clear()
        self.review_completed = False
        self.engine = None


# Global application state instance
app_state = AppState()
