"""Schema-aware preset loading for RoutingThresholds.

Behavior:
- YAML keys not in `RoutingThresholds` schema -> PresetValidationError
- YAML missing a field -> fallback to `RoutingThresholds` default
- Old key aliases (via_coverage, similarity) are mapped to new keys
- Built-in preset validation (h+v >= 1.0, etc.) runs via __post_init__
"""
from __future__ import annotations

import os
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List

import yaml

from config.routing_thresholds import RoutingThresholds


class PresetValidationError(ValueError):
    """Raised when a preset YAML is invalid (bad field name, type, or value)."""


# Old short-name aliases mapped to canonical RoutingThresholds field names.
_ALIASES = {
    "via_coverage": "min_via_coverage",
    "similarity": "min_similarity",
    "h_ratio": "max_h_ratio",
    "v_ratio": "max_v_ratio",
    "r_total": "max_r_ohm",
    "c_total": "max_c_ff",
    "tau": "max_tau_ps",
    "sim": "min_similarity",
}

_PRESETS_DIR = os.path.join(os.path.dirname(__file__), "presets")


def _schema_field_names() -> set:
    return {f.name for f in fields(RoutingThresholds)}


def _normalize_keys(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Apply alias map; raise on truly unknown keys."""
    schema = _schema_field_names()
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        if k in schema:
            out[k] = v
            continue
        if k in _ALIASES:
            canonical = _ALIASES[k]
            out[canonical] = v
            continue
        raise PresetValidationError(
            f"Unknown field '{k}' in preset YAML. "
            f"Valid fields: {sorted(schema)}"
        )
    return out


def _apply_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in any missing fields with RoutingThresholds default factory."""
    defaults = RoutingThresholds()
    out = dict(payload)
    for f in fields(RoutingThresholds):
        if f.name not in out:
            out[f.name] = getattr(defaults, f.name)
    return out


def load_preset_from_file(path: str) -> RoutingThresholds:
    """Load a YAML preset file. Returns a validated RoutingThresholds.

    Raises:
        FileNotFoundError: path missing
        PresetValidationError: bad field, bad type, or invalid value
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Preset not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        try:
            raw = yaml.safe_load(fh) or {}
        except yaml.YAMLError as e:
            raise PresetValidationError(f"YAML parse error: {e}") from e

    if not isinstance(raw, dict):
        raise PresetValidationError("Preset YAML must be a mapping at the top level.")

    try:
        normalized = _normalize_keys(raw)
        filled = _apply_defaults(normalized)
        result = RoutingThresholds.from_dict(filled)
        # Schema-aware explicit h+v check (mirrors RoutingThresholds.validate but
        # surfaces a single, preset-specific error). The RoutingThresholds
        # dataclass has no __post_init__ so we must enforce here.
        if (result.max_h_ratio + result.max_v_ratio) < 1.0 - 1e-9:
            raise PresetValidationError(
                f"max_h_ratio ({result.max_h_ratio}) + max_v_ratio "
                f"({result.max_v_ratio}) must sum to >= 1.0"
            )
        return result
    except PresetValidationError:
        raise
    except (TypeError, ValueError) as e:
        raise PresetValidationError(f"Invalid value in preset: {e}") from e


def list_presets() -> List[str]:
    """Return the basenames (without .yaml) of all built-in presets."""
    if not os.path.isdir(_PRESETS_DIR):
        return []
    return sorted(
        os.path.splitext(fn)[0]
        for fn in os.listdir(_PRESETS_DIR)
        if fn.endswith(".yaml")
    )


def load_preset_by_name(name: str) -> RoutingThresholds:
    """Load a built-in preset by its short name (e.g. 'sram_7nm_wl')."""
    path = os.path.join(_PRESETS_DIR, f"{name}.yaml")
    return load_preset_from_file(path)


# ---------------------------------------------------------------------------
# Backward-compat aliases for code that still imports the legacy public API.
#
#   app/routing_config.py uses:
#     - list_yaml_presets  (used as set membership)
#     - load_preset_yaml   (accepts a preset name; returns RoutingThresholds)
#
#   tests/test_preset_loader.py and tests/test_routing_thresholds.py use:
#     - list_yaml_presets, load_preset_yaml, save_preset_yaml
#
# `load_preset_yaml` is intentionally kept STRICT (all RoutingThresholds fields
# must be present) so the legacy contract — and the existing
# test_load_raises_on_missing_keys assertion — continue to hold.
# ---------------------------------------------------------------------------

_PRESETS_DIR_PATH = Path(_PRESETS_DIR)


def _resolve_legacy_path(name_or_path: str) -> str:
    """Resolve either a preset short name (in config/presets/) or a full path."""
    p = Path(name_or_path)
    if p.exists():
        return str(p)
    candidate = _PRESETS_DIR_PATH / f"{name_or_path}.yaml"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError(f"Preset not found: {name_or_path}")


def list_yaml_presets() -> List[str]:
    """Legacy alias for :func:`list_presets`."""
    return list_presets()


def load_preset_yaml(name_or_path: str) -> RoutingThresholds:
    """Legacy alias. Strict: every RoutingThresholds field must be present.

    Delegates to the schema-aware :func:`load_preset_from_file` after enforcing
    the legacy "all required fields present" contract on the raw keys (no
    fallback). Raises ``ValueError`` if any canonical RoutingThresholds field is
    missing from the YAML.
    """
    path = _resolve_legacy_path(name_or_path)
    schema = _schema_field_names()
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"YAML root must be a dict, got {type(raw).__name__}")
    missing = schema - set(raw.keys())
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")
    t = load_preset_from_file(path)
    t.validate()
    return t


def save_preset_yaml(thresholds: RoutingThresholds, path: str) -> None:
    """Legacy alias: validate then dump a RoutingThresholds to YAML."""
    thresholds.validate()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(thresholds.to_dict(), f, default_flow_style=False, sort_keys=False)
