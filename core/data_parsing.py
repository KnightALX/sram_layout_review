"""Data parsing functions for shape files and YAML batch imports.

This module handles parsing of layout shape files (txt format) and
YAML batch import configurations.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    # Import only for type checking, not at runtime
    # This avoids circular imports while maintaining type safety
    pass


def _get_shape_classes() -> Tuple:
    """Lazily import shape classes to avoid circular imports at runtime.

    This function is called within parse_shape_txt and other parsing
    functions to ensure review_engine is fully loaded before we
    import Point and Polygon.

    Returns:
        Tuple of (Point, Polygon) classes
    """
    from review_engine import Point, Polygon
    return Point, Polygon


def parse_shape_txt(content: str, filename: str) -> Optional[tuple]:
    """Parse shape txt file.

    Args:
        content: File content as string
        filename: Name of the file

    Returns:
        Tuple of (net_name, shapes_data, polygons) or None if parsing fails
    """
    # Get classes at runtime to avoid circular imports
    Point_cls, Polygon_cls = _get_shape_classes()

    match = re.match(r'shapes_(.+)\.txt', filename)
    if not match:
        return None

    name_parts = match.group(1).split('_', 1)
    layout_id = name_parts[0]
    cdl_id = name_parts[1] if len(name_parts) > 1 else ""
    net_name = f"{layout_id}_{cdl_id}" if cdl_id else layout_id

    lines = content.strip().split('\n')
    scale = 20000
    current_layer = None
    shapes_data = {}
    polygons = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith('Net_Shapes'):
            parts = line.split()
            if len(parts) > 1:
                scale = int(parts[1])
            i += 1
            continue

        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', line) and not line.startswith('p '):
            current_layer = line
            shapes_data[current_layer] = []
            i += 1
            if i < len(lines) and re.match(r'^\d+ \d+ \d+ \w+ \d+ \d+:\d+:\d+ \d+$', lines[i].strip()):
                i += 1
            continue

        if line.startswith('p ') and current_layer:
            parts = line.split()
            if len(parts) >= 3:
                num_points = int(parts[2])
                points = []

                for j in range(num_points):
                    i += 1
                    if i >= len(lines):
                        break
                    try:
                        x, y = map(int, lines[i].strip().split())
                        points.append(Point_cls(x / scale, y / scale))
                    except (ValueError, TypeError):
                        continue

                if points:
                    shapes_data[current_layer].append([(p.x, p.y) for p in points])
                    polygons.append(Polygon_cls(points=points, layer=current_layer))

        i += 1

    return net_name, shapes_data, polygons


def parse_yaml_batch_config(yaml_content: str) -> Optional[dict]:
    """Parse YAML batch import configuration.

    YAML format example:
    ```yaml
    import_mode: "batch"

    shapes:
      - file: "/path/to/shapes_20000_net1.txt"
        net_name: "custom_net1"
      - file: "/path/to/shapes_20001_net2.txt"
        net_name: "custom_net2"

    options:
      auto_prefix: "batch_"
      clear_existing: false
    ```

    Args:
        yaml_content: YAML file content as string

    Returns:
        Parsed configuration dict or None if parsing fails
    """
    try:
        import yaml
    except ImportError:
        print("Warning: PyYAML not installed. YAML batch import not available.")
        return None

    try:
        config = yaml.safe_load(yaml_content)
        return config
    except Exception as e:
        print(f"Error parsing YAML: {e}")
        return None


def import_shape_from_file(filepath: str, custom_net_name: str = None) -> Optional[dict]:
    """Import shape data from a file path.

    Args:
        filepath: Path to shape file
        custom_net_name: Optional custom net name override

    Returns:
        Dictionary with net_name, shapes, polygons, filename or None
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        filename = os.path.basename(filepath)
        result = parse_shape_txt(content, filename)

        if result:
            net_name, shapes_data, polygons = result
            if custom_net_name:
                net_name = custom_net_name
            return {
                'net_name': net_name,
                'shapes': shapes_data,
                'polygons': polygons,
                'filename': filename
            }
    except Exception as e:
        print(f"Error importing {filepath}: {e}")

    return None


def process_yaml_batch_import(yaml_content: str, base_dir: str = None) -> list:
    """Process YAML batch import configuration.

    Args:
        yaml_content: YAML configuration content
        base_dir: Base directory for relative paths

    Returns:
        List of successfully imported net data dictionaries
    """
    config = parse_yaml_batch_config(yaml_content)
    if not config:
        return []

    imported_nets = []

    options = config.get('options', {})
    auto_prefix = options.get('auto_prefix', '')

    shapes_config = config.get('shapes', [])

    for shape_item in shapes_config:
        if isinstance(shape_item, dict):
            filepath = shape_item.get('file', '')
            custom_net_name = shape_item.get('net_name')
        elif isinstance(shape_item, str):
            filepath = shape_item
            custom_net_name = None
        else:
            continue

        if base_dir and not os.path.isabs(filepath):
            filepath = os.path.join(base_dir, filepath)

        filepath = os.path.expanduser(filepath)

        if not os.path.exists(filepath):
            print(f"Warning: File not found: {filepath}")
            continue

        if custom_net_name and auto_prefix:
            custom_net_name = auto_prefix + custom_net_name

        result = import_shape_from_file(filepath, custom_net_name)
        if result:
            imported_nets.append(result)
            print(f"Imported: {result['net_name']} from {result['filename']}")

    return imported_nets
