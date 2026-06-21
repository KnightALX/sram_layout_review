"""YAML preset loader/saver for routing thresholds."""
from __future__ import annotations

from pathlib import Path
from typing import List

import yaml

from config.routing_thresholds import RoutingThresholds

PRESETS_DIR = Path(__file__).parent / "presets"
REQUIRED_FIELDS = set(RoutingThresholds.__dataclass_fields__.keys())


def list_yaml_presets() -> List[str]:
    """List preset names from config/presets/*.yaml (without extension)."""
    if not PRESETS_DIR.exists():
        return []
    return sorted(p.stem for p in PRESETS_DIR.glob("*.yaml"))


def _resolve_path(name_or_path: str) -> Path:
    """Resolve either a preset name (e.g. 'sram_7nm_wl') or a full path."""
    p = Path(name_or_path)
    if p.exists():
        return p
    candidate = PRESETS_DIR / f"{name_or_path}.yaml"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Preset not found: {name_or_path}")


def load_preset_yaml(name_or_path: str) -> RoutingThresholds:
    """Load a preset YAML by name (in config/presets/) or absolute path."""
    path = _resolve_path(name_or_path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a dict, got {type(data).__name__}")
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")
    t = RoutingThresholds.from_dict(data)
    t.validate()
    return t


def save_preset_yaml(thresholds: RoutingThresholds, path: str) -> None:
    """Save thresholds to a YAML file."""
    thresholds.validate()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(thresholds.to_dict(), f, default_flow_style=False, sort_keys=False)
