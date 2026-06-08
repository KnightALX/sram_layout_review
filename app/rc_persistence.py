"""Persistence + history stack for the RC Prediction tab.

Two responsibilities:

1. **Disk persistence** — save the user's custom RCModelConfig to
   `~/.layout_review/rc_model.yaml` on Apply, load on startup.  This makes
   the user's process / EDA / model parameters survive app restarts.

2. **History stack** — every Apply pushes the previous state onto a
   bounded LIFO stack (max 10 entries).  `revert()` pops one.  This
   gives the user a safe "undo" path for misclicks.

PDK import / export share the same on-disk format (YAML).
"""
from __future__ import annotations
import json
import os
from collections import deque
from pathlib import Path
from typing import Deque, Optional

import yaml

from app.rc_model import RCModelConfig


# ---------------------------------------------------------------------------
# Disk location
# ---------------------------------------------------------------------------
_PERSIST_DIR = Path.home() / ".layout_review"
_PERSIST_FILE = _PERSIST_DIR / "rc_model.yaml"

# YAML keys we round-trip.  These mirror `RCModelConfig.__dataclass_fields__`;
# we keep the list explicit (instead of `from_dict` introspection) so
# unknown dict keys never silently leak into the file.
_KNOWN_KEYS = (
    "tech_node", "temperature_c",
    "metal_r_sheet", "metal_thickness", "metal_width",
    "metal_resistivity_tempco", "via_resistance", "via_resistance_tempco",
    "dielectric_constant", "min_space",
    "fringe_cap_factor", "coupling_cap_factor",
    "model_type", "length_per_segment_um", "use_ground_cap_70_30",
    "preset_name",
)

HISTORY_MAX = 10


# ---------------------------------------------------------------------------
# Disk persistence
# ---------------------------------------------------------------------------
def save_to_disk(cfg: RCModelConfig) -> Path:
    """Write `cfg` to ~/.layout_review/rc_model.yaml.

    Returns the path written.  Creates the directory if missing.
    """
    _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    d = {k: cfg.to_dict()[k] for k in _KNOWN_KEYS}
    with open(_PERSIST_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(d, f, default_flow_style=False, sort_keys=False,
                       allow_unicode=True)
    return _PERSIST_FILE


def load_from_disk() -> Optional[RCModelConfig]:
    """Return the saved config, or None if no file / parse error.

    Never raises — the app must keep booting even with a corrupt file.
    """
    if not _PERSIST_FILE.exists():
        return None
    try:
        with open(_PERSIST_FILE, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        return RCModelConfig.from_dict(d)
    except (OSError, yaml.YAMLError, TypeError, ValueError):
        return None


def clear_disk() -> None:
    """Delete the persistence file (used by Reset-to-default)."""
    try:
        if _PERSIST_FILE.exists():
            _PERSIST_FILE.unlink()
    except OSError:
        pass


def persist_path() -> Path:
    """Return the on-disk path the app reads from (for UI display)."""
    return _PERSIST_FILE


# ---------------------------------------------------------------------------
# PDK-style import / export (YAML or JSON)
# ---------------------------------------------------------------------------
def parse_pdk_text(text: str, filename_hint: str = "") -> dict:
    """Parse PDK text (YAML or JSON) and return a dict of overrides.

    The parser auto-detects JSON vs YAML by trying JSON first (which is a
    strict subset of YAML in syntax but uses a different extension
    convention in practice).  Unknown keys are kept — the caller decides
    what to overlay onto RCModelConfig.

    YAML notes:
        PyYAML is strict about `key: value` (colon must be followed by a
        space).  We lightly preprocess the text to insert a space after
        any `:` that is followed by a non-space, non-newline character.
        This is a common source of user pain in copy-pasted PDK files.

    Raises:
        ValueError: if the text cannot be parsed as JSON or YAML, or if
            the resulting object is not a dict.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty payload")
    # JSON first (fast path for .json files)
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Lightly relax YAML "colon-without-space" requirement
        relaxed = _relax_yaml_colons(text)
        try:
            obj = yaml.safe_load(relaxed)
        except yaml.YAMLError as e:
            ext = Path(filename_hint or "").suffix.lower()
            raise ValueError(
                f"Could not parse as JSON or YAML"
                f"{' (.' + ext.lstrip('.') + ')' if ext else ''}: {e}"
            ) from e
    if not isinstance(obj, dict):
        raise ValueError(
            f"PDK payload must be a mapping/object at the top level, got {type(obj).__name__}"
        )
    return obj


def _relax_yaml_colons(text: str) -> str:
    """Insert a space after `:` if it's followed by a non-space character.

    PyYAML refuses `key:100.0` (no space) but accepts `key: 100.0`.  This
    function is a non-invasive way to accept the common copy-paste case
    where users remove the space for compactness.  Indentation is
    preserved (we only touch the line we're on, and only the first `:`).
    """
    out_lines = []
    for line in text.splitlines():
        # Don't touch indented (nested) lines differently — first colon
        # followed by non-space is the only case we care about.
        idx = line.find(":")
        if idx >= 0 and idx + 1 < len(line) and line[idx + 1] not in (" ", "\t", "#", ""):
            # Insert a single space after the colon
            line = line[: idx + 1] + " " + line[idx + 1:]
        out_lines.append(line)
    return "\n".join(out_lines)


def merge_pdk_into(base: RCModelConfig, pdk: dict) -> RCModelConfig:
    """Overlay PDK values onto `base`, returning a new RCModelConfig.

    The merge is per-key, so partial PDKs work.  Layers that exist in
    the PDK are added/overridden; layers not in the PDK are kept.
    """
    d = base.to_dict()
    # Scalar fields
    for k in _KNOWN_KEYS:
        if k in pdk and k not in ("metal_r_sheet", "metal_thickness",
                                  "metal_width", "via_resistance", "min_space"):
            d[k] = pdk[k]
    # Dict-typed fields: merge per-layer rather than wholesale replace
    for k in ("metal_r_sheet", "metal_thickness", "metal_width",
              "via_resistance", "min_space"):
        if k in pdk and isinstance(pdk[k], dict):
            base_dict = d.setdefault(k, {})
            base_dict.update(pdk[k])
    return RCModelConfig.from_dict(d)


def to_yaml(cfg: RCModelConfig) -> str:
    """Serialize `cfg` to a YAML string (for Export / Save)."""
    d = {k: cfg.to_dict()[k] for k in _KNOWN_KEYS}
    return yaml.safe_dump(d, default_flow_style=False, sort_keys=False,
                          allow_unicode=True)


# ---------------------------------------------------------------------------
# History stack (in-memory, lives with the running process)
# ---------------------------------------------------------------------------
class HistoryStack:
    """Bounded LIFO history of applied RCModelConfigs.

    `push` records the *previous* state right before a new Apply.  `pop`
    returns the most recent entry (or None if empty).
    """
    def __init__(self, maxlen: int = HISTORY_MAX):
        self._stack: Deque[RCModelConfig] = deque(maxlen=maxlen)

    def push(self, cfg: RCModelConfig) -> None:
        # Each push drops the oldest if we exceed maxlen
        self._stack.appendleft(cfg)  # newest at left

    def pop(self) -> Optional[RCModelConfig]:
        if not self._stack:
            return None
        return self._stack.popleft()

    def __len__(self) -> int:
        return len(self._stack)

    def is_empty(self) -> bool:
        return not self._stack


# Module-level singleton (shared with routing_state)
_history = HistoryStack()


def history() -> HistoryStack:
    return _history
