"""Independent state for the Routing Review workflow.

Kept separate from `app/state.py` (the original global state) so the
routing rewrite does not affect the existing tabs.

USAGE CONTRACT (important for callers):
- Do NOT mutate .custom_thresholds, .thresholds, or .is_frozen directly.
- Always read the active thresholds via .get_thresholds() (it is authoritative).
- Use .set_frozen_mode() (and related setters if any) to change mode.
- Direct assignment can bypass frozen invariant and cause preset/custom
  mismatch. Prefer get_thresholds() + set_frozen_mode() over raw access.
- For presentation/UI (button classes, disabled state, layout decisions):
  .is_frozen (property) is the supported thin read accessor. Direct attribute
  read is acceptable via the property for these cases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.rc_model import RCModelConfig
from config.routing_thresholds import RoutingThresholds


@dataclass
class RoutingState:
    """State for the Configuration + Layout Review tabs (routing-focused).

    See module docstring for the usage contract: use get_thresholds()
    and set_frozen_mode() rather than direct field mutation.
    """
    # Current preset
    current_preset: str = "sram_7nm_wl"
    thresholds: RoutingThresholds = field(
        default_factory=lambda: RoutingThresholds.for_preset("sram_7nm_wl")
    )
    # Custom overrides (None means use preset)
    custom_thresholds: Optional[RoutingThresholds] = None

    # Explicit frozen mode (default True). Internal storage uses _is_frozen;
    # the public .is_frozen property is the thin accessor for UI reads.
    # When True, get_thresholds() returns the preset value (ignores custom).
    # UI inputs are disabled. Enforcement is now authoritative in get_thresholds().
    _is_frozen: bool = field(default=True, repr=False)

    @property
    def is_frozen(self) -> bool:
        """Thin accessor for frozen mode (read-only for presentation/UI).

        UI code (layout builders + callbacks) reads this for button classes,
        disabled flags, and mode decisions. This fulfills the documented
        contract while allowing simple attribute-style reads like `if s.is_frozen`.
        Writes MUST use set_frozen_mode(); direct assignment is forwarded for
        backward compat in tests but is not recommended.
        """
        return self._is_frozen

    @is_frozen.setter
    def is_frozen(self, value: bool):
        """Allow assignment for compat (e.g. test code), but delegates to set_frozen_mode."""
        self.set_frozen_mode(bool(value))

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
        """Enforce defaults: frozen mode starts with no custom overrides.

        Note: get_thresholds() is now the authoritative reader and also
        respects is_frozen regardless of custom_thresholds state.
        """
        if self._is_frozen:
            self.custom_thresholds = None

    def get_thresholds(self) -> RoutingThresholds:
        """Return active thresholds.

        Authoritative: when is_frozen, always return the preset (custom is ignored).
        Callers should use this instead of accessing .custom_thresholds or .thresholds.
        """
        if self._is_frozen:
            return self.thresholds
        return self.custom_thresholds or self.thresholds

    def set_frozen_mode(self, frozen: bool):
        """Set frozen mode. Does NOT discard custom_thresholds — it is a
        'draft area' that survives Locked<->Editable toggles (see spec 3.2.4).
        get_thresholds() returns preset when frozen and custom (or preset
        fallback) when editable; UI rehydrate handles the rest.
        """
        self._is_frozen = bool(frozen)

    def set_custom(self, thresholds: "RoutingThresholds"):
        """Adopt a custom thresholds object and switch to editable mode.

        Replaces the previous custom_thresholds (if any). The state is now
        editable; get_thresholds() will return this object.
        """
        self.custom_thresholds = thresholds
        self._is_frozen = False

    def get_threshold_source(self) -> str:
        """Human-readable source description for UI banners (English)."""
        if self._is_frozen:
            return f"Locked preset: {self.current_preset}"
        if self.custom_thresholds is not None:
            return f"Custom (based on {self.current_preset})"
        return f"Preset: {self.current_preset}"

    def get_rc_model(self) -> RCModelConfig:
        """Return the active RC model (custom override or built-in default)."""
        return self.custom_rc_model or self.rc_model

    def reset_review(self):
        """Clear only review execution results.

        Threshold mode (is_frozen via _is_frozen, custom_thresholds, current_preset, thresholds)
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
