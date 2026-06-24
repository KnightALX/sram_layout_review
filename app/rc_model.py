"""RC prediction model configuration.

Centralizes all parameters needed to predict resistance and capacitance of
interconnect wires and vias.  This is the "source of truth" for the
`RC Prediction` tab and the values it pushes into the rest of the app.

Three expert perspectives are reflected in the section comments:
  - Process expert: sheet R, thickness, width, tempco, via R
  - EDA expert (extraction): dielectric, min_space, fringe / coupling split
  - Modeling expert: lumped-π / T / distributed, segment length, gnd/cpl ratio
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ModelType(str, Enum):
    """Delay-line RC model used for effective-τ computation."""
    LUMPED_PI = "lumped_pi"        # single π segment — fast, coarse
    T_MODEL = "t_model"           # single T segment — symmetric
    DISTRIBUTED_5 = "distributed_5"  # 5-segment ladder — most accurate


# Default 7nm FinFET metal stack, derived from config_system.TechConfig.
# Used when no other config has been applied.  Values are reasonable
# industry-typical numbers (not foundry-specific).
DEFAULT_METAL_R_SHEET: Dict[str, float] = {
    "met1": 0.15, "met2": 0.12, "met3": 0.10, "met4": 0.08,
    "met5": 0.06, "met6": 0.05, "met7": 0.04,
}
DEFAULT_METAL_THICKNESS: Dict[str, float] = {
    "met1": 0.060, "met2": 0.060, "met3": 0.060, "met4": 0.080,
    "met5": 0.110, "met6": 0.140, "met7": 0.180,
}
DEFAULT_METAL_WIDTH: Dict[str, float] = {
    "met1": 0.032, "met2": 0.032, "met3": 0.032, "met4": 0.042,
    "met5": 0.056, "met6": 0.080, "met7": 0.100,
}
DEFAULT_VIA_RESISTANCE: Dict[str, float] = {
    "via1": 4.0, "via2": 3.5, "via3": 3.0, "via4": 2.5,
    "via5": 2.0, "via6": 1.8,
}
DEFAULT_MIN_SPACE: Dict[str, float] = {
    "met1": 0.032, "met2": 0.032, "met3": 0.032, "met4": 0.042,
    "met5": 0.056, "met6": 0.080, "met7": 0.100,
}


@dataclass
class RCModelConfig:
    """Predict R and C of interconnect using a parameterized model.

    The model is intentionally simple and physical — for production work,
    wire R and C are normally extracted by a signoff tool (StarRC, Quantus,
    xRC) against a real PDK.  This config lets the user express what
    those extraction rules would look like for *this* design.
    """

    # ---- Process foundation (process expert) --------------------------------------
    tech_node: str = "7nm"
    temperature_c: float = 85.0  # junction temperature, °C
    metal_r_sheet: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_METAL_R_SHEET)
    )
    metal_thickness: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_METAL_THICKNESS)
    )
    metal_width: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_METAL_WIDTH)
    )
    # Cu sheet-R temperature coefficient (≈ 0.4 %/°C around 25°C ref)
    metal_resistivity_tempco: float = 0.004
    via_resistance: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_VIA_RESISTANCE)
    )
    via_resistance_tempco: float = 0.003

    # ---- Dielectric / parasitic (EDA / CAD expert) ---------------------------------
    dielectric_constant: float = 3.9  # ILD effective ε_r (low-k ~ 2.5–3.5)
    min_space: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_MIN_SPACE)
    )
    fringe_cap_factor: float = 0.6   # 0.5–0.8 typical
    coupling_cap_factor: float = 0.3  # fraction of total C that is to neighbors

    # ---- Delay-line modeling (delay-line modeling expert) -----------------------
    model_type: str = ModelType.LUMPED_PI.value
    length_per_segment_um: float = 50.0  # length of each π/T segment
    use_ground_cap_70_30: bool = True    # 70 % gnd / 30 % coupling split

    # ---- preset (display only) ------------------------------------------
    preset_name: str = "default_7nm"

    # ---- helpers --------------------------------------------------------
    def metal_layers(self) -> List[str]:
        """Return metal layer names in standard order (met1..metN)."""
        return sorted(self.metal_r_sheet.keys(),
                      key=lambda n: int("".join(c for c in n if c.isdigit()) or 0))

    def via_layers(self) -> List[str]:
        """Return via layer names in standard order."""
        return sorted(self.via_resistance.keys(),
                      key=lambda n: int("".join(c for c in n if c.isdigit()) or 0))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict (nested dicts preserved)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RCModelConfig":
        """Build from dict, ignoring unknown keys for forward compat."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def validate(self) -> None:
        """Sanity check. Raises ValueError on invalid config.

        Range checks are intentionally loose — physical ranges can vary
        wildly between processes.  We only catch *obviously wrong* inputs
        (negative, zero, out-of-band model type, empty layer dicts).
        """
        if not self.tech_node or not isinstance(self.tech_node, str):
            raise ValueError(f"tech_node must be a non-empty string, got {self.tech_node!r}")
        if self.temperature_c < -55.0 or self.temperature_c > 200.0:
            raise ValueError(
                f"temperature_c={self.temperature_c} out of plausible range [-55, 200]"
            )
        if not self.metal_r_sheet:
            raise ValueError("metal_r_sheet is empty — at least one metal layer required")
        for layer, r in self.metal_r_sheet.items():
            if r <= 0:
                raise ValueError(f"metal_r_sheet[{layer!r}] must be positive, got {r}")
        for layer, t in self.metal_thickness.items():
            if t <= 0:
                raise ValueError(f"metal_thickness[{layer!r}] must be positive, got {t}")
        for layer, w in self.metal_width.items():
            if w <= 0:
                raise ValueError(f"metal_width[{layer!r}] must be positive, got {w}")
        if self.metal_resistivity_tempco < 0 or self.metal_resistivity_tempco > 0.02:
            raise ValueError(
                f"metal_resistivity_tempco={self.metal_resistivity_tempco} "
                "out of plausible range [0, 0.02]"
            )
        for via, r in self.via_resistance.items():
            if r < 0:
                raise ValueError(f"via_resistance[{via!r}] must be non-negative, got {r}")
        if self.dielectric_constant < 1.0 or self.dielectric_constant > 12.0:
            raise ValueError(
                f"dielectric_constant={self.dielectric_constant} out of range [1, 12]"
            )
        if self.fringe_cap_factor < 0 or self.fringe_cap_factor > 2.0:
            raise ValueError(
                f"fringe_cap_factor={self.fringe_cap_factor} out of range [0, 2]"
            )
        if self.coupling_cap_factor < 0 or self.coupling_cap_factor > 1.0:
            raise ValueError(
                f"coupling_cap_factor={self.coupling_cap_factor} out of range [0, 1]"
            )
        if self.coupling_cap_factor + (1.0 - self.coupling_cap_factor) < 0.99:
            # defensive — should be impossible, but keeps invariants explicit
            raise ValueError("coupling_cap_factor split is inconsistent")
        if self.model_type not in {m.value for m in ModelType}:
            raise ValueError(
                f"model_type must be one of {[m.value for m in ModelType]}, "
                f"got {self.model_type!r}"
            )
        if self.length_per_segment_um <= 0 or self.length_per_segment_um > 10000.0:
            raise ValueError(
                f"length_per_segment_um={self.length_per_segment_um} "
                "out of range (0, 10000]"
            )

    # ---- model-specific helpers ----------------------------------------
    def effective_model_segments(self, wire_length_um: float) -> int:
        """How many π/T segments a wire of `wire_length_um` should use.

        For lumped_pi and t_model this is always 1.
        For distributed_5 it scales with wire length.
        """
        if self.model_type == ModelType.DISTRIBUTED_5.value:
            return max(1, int(round(wire_length_um / max(self.length_per_segment_um, 1.0))))
        return 1

    def predict_wire_resistance(self, layer: str, length_um: float,
                                width_um: float | None = None) -> float:
        """R of a single straight wire on `layer` (Ω).

        R = R_sheet × (length / width) × (1 + α × (T - 25))
        Width defaults to the layer's configured width if not provided.
        """
        r_sheet = self.metal_r_sheet.get(layer)
        if r_sheet is None or r_sheet <= 0:
            return 0.0
        if width_um is None:
            width_um = self.metal_width.get(layer, 0.032)
        if width_um <= 0 or length_um <= 0:
            return 0.0
        delta_t = self.temperature_c - 25.0
        r = r_sheet * (length_um / width_um) * (1.0 + self.metal_resistivity_tempco * delta_t)
        return r

    def predict_wire_capacitance(self, layer: str, length_um: float) -> float:
        """Total C of a single straight wire on `layer` (fF).

        C_total = C_gnd + C_couple
        C_gnd   = c_per_um × length × (1 - coupling_cap_factor)
        C_couple= c_per_um × length × coupling_cap_factor × fringe_cap_factor
        c_per_um uses layer thickness & ε_r as a simple parallel-plate proxy.
        """
        if length_um <= 0:
            return 0.0
        thickness = self.metal_thickness.get(layer, 0.060)
        width = self.metal_width.get(layer, 0.032)
        space = self.min_space.get(layer, width)
        # Parallel-plate: C ≈ ε0·ε_r·A / d, expressed as fF/µm
        # ε0 ≈ 8.854e-3 fF/µm, scaled by width / (2·(thickness+space)) as a
        # rough top+bottom-plate + fringe approximation
        c_per_um = (8.854e-3 * self.dielectric_constant
                    * (width + 2.0 * self.fringe_cap_factor * thickness)
                    / (2.0 * (thickness + space)))
        c_gnd = c_per_um * length_um * (1.0 - self.coupling_cap_factor)
        c_couple = c_per_um * length_um * self.coupling_cap_factor
        return c_gnd + c_couple

    def predict_via_resistance(self, via: str) -> float:
        """R of a single via (Ω), temperature-corrected."""
        r = self.via_resistance.get(via, 0.0)
        if r <= 0:
            return 0.0
        delta_t = self.temperature_c - 25.0
        return r * (1.0 + self.via_resistance_tempco * delta_t)
