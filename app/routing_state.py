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

    # Explicit frozen mode (default True). When True, get_thresholds() returns
    # the preset (authoritative); custom_thresholds may still hold a preserved
    # "draft" for restore on next Editable toggle. set_frozen_mode(True) does
    # NOT clear custom_thresholds (draft preservation).
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
    # Human-readable status of the most recent review run (e.g.
    # "Reviewed 5 nets, golden=clk_buf_0"). Distinct from `last_error`,
    # which is reserved for error states. The single _routing_config_ui
    # callback renders this into routing-config-status.children.
    last_status: str = ""

    def __post_init__(self):
        """Enforce defaults: initial frozen mode starts with no custom overrides.
        (Later set_frozen_mode(True) preserves any existing custom draft.)
        """
        if self.is_frozen:
            self.custom_thresholds = None

    def get_thresholds(self) -> RoutingThresholds:
        """Return active thresholds. Frozen mode is authoritative: always the
        preset backing `thresholds`, ignoring any custom draft. In editable
        mode, prefer custom if present, else preset.
        """
        if self.is_frozen:
            return self.thresholds
        return self.custom_thresholds or self.thresholds

    def set_frozen_mode(self, frozen: bool):
        """Set frozen/locked mode flag.

        Does NOT clear custom_thresholds; the custom object (if any) is
        preserved as a draft. Callers must use get_thresholds() which gates
        on is_frozen.
        """
        self.is_frozen = frozen
        # Deliberately do not clear custom_thresholds here (preserve draft).

    def set_custom(self, thresholds: "RoutingThresholds"):
        """Adopt a custom thresholds object and switch to editable mode.

        Replaces the previous custom_thresholds (if any). The state is now
        editable; get_thresholds() will return this object (unless later frozen).
        """
        self.custom_thresholds = thresholds
        self.is_frozen = False

    def get_threshold_source(self) -> str:
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
        self.last_status = ""


# Module-level singleton
routing_state = RoutingState()
