"""Independent state for the Routing Review workflow.

Kept separate from `app/state.py` (the original global state) so the
routing rewrite does not affect the existing tabs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.rc_model import RCModelConfig
from config.routing_thresholds import RoutingThresholds


@dataclass
class RoutingState:
    """State for the Configuration + Layout Review tabs (routing-focused)."""
    # Current preset
    current_preset: str = "sram_7nm_wl"
    thresholds: RoutingThresholds = field(
        default_factory=lambda: RoutingThresholds.for_preset("sram_7nm_wl")
    )
    # Custom overrides (None means use preset)
    custom_thresholds: Optional[RoutingThresholds] = None

    # Explicit frozen mode (default True). When True, get_thresholds() uses
    # the preset (custom_thresholds is forced to None). UI inputs are disabled.
    is_frozen: bool = True

    # Golden + batch (regex strings; resolved against app_state.nets_data)
    golden_regex: str = ""
    batch_regex: str = ""

    # Resolved (after Run Review)
    golden_net_name: str = ""
    golden_metrics: Optional[Dict[str, Any]] = None
    batch_net_names: List[str] = field(default_factory=list)
    batch_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # batch_results: net_name -> 6-metric dict (from core.routing_metrics.compute_for_net)

    # ---- RC prediction model ---------------------------------------------
    # The default config matches the 7nm FinFET stack.  Callers that have
    # applied a custom config (via the RC Prediction tab) will populate
    # `custom_rc_model`; `get_rc_model()` returns whichever is active.
    rc_model: RCModelConfig = field(default_factory=RCModelConfig)
    custom_rc_model: Optional[RCModelConfig] = None

    review_completed: bool = False
    last_error: Optional[str] = None

    def __post_init__(self):
        """Enforce defaults: frozen mode starts with no custom overrides."""
        if self.is_frozen:
            self.custom_thresholds = None

    def get_thresholds(self) -> RoutingThresholds:
        return self.custom_thresholds or self.thresholds

    def set_frozen_mode(self, frozen: bool):
        """Set frozen mode. When enabling frozen, discard any custom overrides."""
        self.is_frozen = frozen
        if frozen:
            self.custom_thresholds = None

    def get_threshold_source(self) -> str:
        """Human-readable source description for UI banners."""
        if self.is_frozen:
            return f"{self.current_preset}（冻结）"
        return f"基于 {self.current_preset} 的自定义"

    def get_rc_model(self) -> RCModelConfig:
        """Return the active RC model (custom override or built-in default)."""
        return self.custom_rc_model or self.rc_model

    def reset_review(self):
        """Clear only review execution results.

        Threshold mode (is_frozen, custom_thresholds, current_preset, thresholds)
        is intentionally preserved — reset_review is used before re-running
        analysis, not to reset configuration.
        """
        self.golden_net_name = ""
        self.golden_metrics = None
        self.batch_net_names = []
        self.batch_results = {}
        self.review_completed = False
        self.last_error = None


# Module-level singleton
routing_state = RoutingState()
