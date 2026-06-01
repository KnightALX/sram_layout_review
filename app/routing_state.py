"""Independent state for the Routing Review workflow.

Kept separate from `app/state.py` (the original global state) so the
routing rewrite does not affect the existing tabs.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
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

    # Golden + batch (regex strings; resolved against app_state.nets_data)
    golden_regex: str = ""
    batch_regex: str = ""

    # Resolved (after Run Review)
    golden_net_name: str = ""
    golden_metrics: Optional[Dict[str, Any]] = None
    batch_net_names: List[str] = field(default_factory=list)
    batch_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # batch_results: net_name -> 6-metric dict (from core.routing_metrics.compute_for_net)

    review_completed: bool = False
    last_error: Optional[str] = None

    def get_thresholds(self) -> RoutingThresholds:
        return self.custom_thresholds or self.thresholds

    def reset_review(self):
        self.golden_net_name = ""
        self.golden_metrics = None
        self.batch_net_names = []
        self.batch_results = {}
        self.review_completed = False
        self.last_error = None


# Module-level singleton
routing_state = RoutingState()
