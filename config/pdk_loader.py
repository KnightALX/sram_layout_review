"""YAML PDK loader for TechConfig."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from config_system import TechConfig

PDK_DIR = Path(__file__).parent.parent / "pdk"


def _resolve_path(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.exists():
        return p
    candidate = PDK_DIR / f"{name_or_path}.yaml"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"PDK not found: {name_or_path}")


def load_pdk_yaml(name_or_path: str) -> TechConfig:
    """Load a PDK YAML by name (in pdk/) or absolute path."""
    path = _resolve_path(name_or_path)
    with open(path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a dict, got {type(data).__name__}")
    required = ("name", "node", "voltage", "temperature", "layers", "design_rules")
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Missing required PDK fields: {missing}")
    return TechConfig(
        name=data["name"],
        node=data["node"],
        voltage=float(data["voltage"]),
        temperature=float(data["temperature"]),
        layers=data["layers"],
        design_rules=data["design_rules"],
    )
