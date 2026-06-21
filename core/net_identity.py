"""Composite net identity: source/net_name keys for nets_data."""
from __future__ import annotations

import os
from typing import Optional, Tuple

DEFAULT_SOURCE = "_default"


def validate_source_or_net_name(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("source and net_name must be non-empty")
    if "/" in value:
        raise ValueError("source and net_name must not contain '/'")
    return value


def make_net_id(source: str, net_name: str) -> str:
    source = validate_source_or_net_name(source)
    net_name = validate_source_or_net_name(net_name)
    return f"{source}/{net_name}"


def parse_net_id(net_id: str) -> Tuple[str, str]:
    if not net_id or "/" not in net_id:
        raise ValueError(f"Invalid net_id (expected source/net_name): {net_id!r}")
    source, net_name = net_id.split("/", 1)
    if not source or not net_name:
        raise ValueError(f"Invalid net_id (empty part): {net_id!r}")
    return source, net_name


def derive_source_from_path(filepath: str) -> str:
    parent = os.path.basename(os.path.dirname(os.path.abspath(os.path.expanduser(filepath))))
    if not parent or parent in (".", ""):
        return DEFAULT_SOURCE
    return parent


def derive_source_from_relative_path(relative_path: str) -> str:
    relative_path = (relative_path or "").replace("\\", "/").strip()
    if "/" not in relative_path:
        return DEFAULT_SOURCE
    parent = relative_path.rsplit("/", 1)[0]
    parent = os.path.basename(parent) if "/" in parent else parent
    return parent or DEFAULT_SOURCE


def resolve_source(filepath: str, yaml_source: Optional[str] = None) -> str:
    if yaml_source is not None and str(yaml_source).strip():
        return validate_source_or_net_name(str(yaml_source))
    if filepath:
        return derive_source_from_path(filepath)
    return DEFAULT_SOURCE