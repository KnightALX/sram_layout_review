#!/usr/bin/env python3
"""
Test suite for Layout Review Tool
Tests shape parsing, RC calculation, and rule checking

.. deprecated::
    Use ``python -m pytest tests/`` from the repo root instead.
    This script remains for backward compatibility only.

Usage:
    python tests/run_tests.py              # Run all tests
    python tests/run_tests.py -v           # Verbose mode
    python tests/run_tests.py TestRC       # Run specific test class
"""
import os
import sys
import unittest
import warnings

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

warnings.warn(
    "tests/run_tests.py is deprecated; use: python -m pytest tests/",
    DeprecationWarning,
    stacklevel=1,
)

from config_system import get_sram_7nm_config
from core.data_parsing import parse_shape_txt
from review_engine import ProfessionalLayoutReviewEngine


def test_parse_shape_txt():
    """Test shape file parsing"""
    print("\n=== Test: Shape File Parsing ===")

    test_dir = os.path.dirname(__file__)

    # Test 1: Normal net
    filepath = os.path.join(test_dir, "shapes_test_normal.txt")
    with open(filepath, 'r') as f:
        content = f.read()

    result = parse_shape_txt(content, "shapes_test_normal.txt")
    assert result is not None, "Failed to parse normal net"
    net_name, shapes_data, polygons = result

    print(f"  Net name: {net_name}")
    print(f"  Layers found: {list(shapes_data.keys())}")
    print(f"  Total polygons: {len(polygons)}")

    # Verify polygons have points
    for poly in polygons:
        assert len(poly.points) >= 3, f"Polygon has < 3 points: {len(poly.points)}"

    print("  [OK] Normal net parsing passed")

    # Test 2: Parse all test files
    test_files = [
        "shapes_test_drc_violation.txt",
        "shapes_test_long_wire.txt",
        "shapes_test_power_net.txt",
        "shapes_test_bitline_BL0.txt",
        "shapes_test_bitline_BLB0.txt",
    ]

    for filename in test_files:
        filepath = os.path.join(test_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()
        result = parse_shape_txt(content, filename)
        assert result is not None, f"Failed to parse {filename}"
        net_name, shapes_data, polygons = result
        print(f"  [OK] {filename}: {net_name}, {len(shapes_data)} layers, {len(polygons)} polygons")


def test_rc_calculation():
    """Test RC calculation"""
    print("\n=== Test: RC Calculation ===")

    test_dir = os.path.dirname(__file__)
    config = get_sram_7nm_config()
    engine = ProfessionalLayoutReviewEngine(config)

    # Load normal net
    filepath = os.path.join(test_dir, "shapes_test_normal.txt")
    with open(filepath, 'r') as f:
        content = f.read()

    result = parse_shape_txt(content, "shapes_test_normal.txt")
    net_name, shapes_data, polygons = result

    # Add to engine
    engine.add_net_polygons(net_name, polygons)

    # Calculate RC
    rc_data = engine.calculate_net_rc(net_name)

    print(f"  Net: {net_name}")
    print(f"  Total R: {rc_data.total_resistance:.4f} Ω")
    print(f"  Total C: {rc_data.total_capacitance:.4f} fF")
    print(f"  Total length: {rc_data.total_length:.4f} μm")
    print(f"  Layer usage: {rc_data.layer_usage}")

    assert rc_data.total_resistance >= 0, "Negative resistance"
    assert rc_data.total_capacitance >= 0, "Negative capacitance"
    assert rc_data.total_length > 0, "Zero length"

    print("  [OK] RC calculation passed")


def test_drc_violation():
    """Test DRC violation detection"""
    print("\n=== Test: DRC Violation Detection ===")

    test_dir = os.path.dirname(__file__)
    config = get_sram_7nm_config()
    engine = ProfessionalLayoutReviewEngine(config)

    # Load DRC violation net
    filepath = os.path.join(test_dir, "shapes_test_drc_violation.txt")
    with open(filepath, 'r') as f:
        content = f.read()

    result = parse_shape_txt(content, "shapes_test_drc_violation.txt")
    net_name, shapes_data, polygons = result

    engine.add_net_polygons(net_name, polygons)
    engine.calculate_net_rc(net_name)

    print(f"  Net: {net_name}")
    print(f"  Polygons: {len(polygons)}")

    # Check for width violations
    tech = engine.tech
    for poly in polygons:
        layer_info = tech.layers.get(poly.layer, {})
        min_width = layer_info.get('min_width', 0.032)
        actual_width = min(poly.width, poly.height)
        print(f"  Layer {poly.layer}: width={actual_width:.4f}μm, min={min_width}μm")

        if actual_width < min_width * 0.95:
            print("    → Width VIOLATION detected!")

    print("  [OK] DRC violation check passed")


def test_matching_analysis():
    """Test bitline matching analysis"""
    print("\n=== Test: Matching Analysis ===")

    test_dir = os.path.dirname(__file__)
    config = get_sram_7nm_config()
    engine = ProfessionalLayoutReviewEngine(config)

    # Load BL_0 and BLB_0
    for filename in ["shapes_test_bitline_BL0.txt", "shapes_test_bitline_BLB0.txt"]:
        filepath = os.path.join(test_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()

        result = parse_shape_txt(content, filename)
        net_name, shapes_data, polygons = result

        engine.add_net_polygons(net_name, polygons)
        rc_data = engine.calculate_net_rc(net_name)

        print(f"  {net_name}: R={rc_data.total_resistance:.2f}Ω, C={rc_data.total_capacitance:.2f}fF, L={rc_data.total_length:.2f}μm, Vias={rc_data.via_count}")

    # Analyze matching
    matching = engine.analyze_matching("BL_0", "BLB_0")

    print(f"  Matching score: {matching.match_score:.1f}")
    print(f"  Length ratio: {matching.length_ratio:.4f}")
    print(f"  Resistance ratio: {matching.resistance_ratio:.4f}")
    print(f"  Via count diff: {matching.via_count_diff}")

    if matching.issues:
        print("  Issues found:")
        for issue in matching.issues:
            print(f"    - {issue}")

    print("  [OK] Matching analysis passed")


def test_full_review():
    """Test full review pipeline"""
    print("\n=== Test: Full Review Pipeline ===")

    test_dir = os.path.dirname(__file__)
    config = get_sram_7nm_config()
    engine = ProfessionalLayoutReviewEngine(config)

    # Load all test nets
    test_files = [
        "shapes_test_normal.txt",
        "shapes_test_drc_violation.txt",
        "shapes_test_long_wire.txt",
        "shapes_test_power_net.txt",
        "shapes_test_bitline_BL0.txt",
        "shapes_test_bitline_BLB0.txt",
    ]

    for filename in test_files:
        filepath = os.path.join(test_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()

        result = parse_shape_txt(content, filename)
        net_name, shapes_data, polygons = result
        engine.add_net_polygons(net_name, polygons)

    print(f"  Loaded {len(engine.nets)} nets")

    # Run full review
    summary = engine.run_full_review()

    print("\n  Summary:")
    print(f"    Total nets: {summary.total_nets}")
    print(f"    Total violations: {summary.total_violations}")
    print(f"    Critical: {summary.critical_count}")
    print(f"    Warning: {summary.warning_count}")
    print(f"    Info: {summary.info_count}")

    print("  [OK] Full review passed")


def test_layer_parsing_issue():
    """Test for layer naming consistency issue"""
    print("\n=== Test: Layer Naming Consistency ===")

    test_dir = os.path.dirname(__file__)

    # Test with met2a (from real data)
    filepath = os.path.join(test_dir, "shapes_test_normal.txt")
    with open(filepath, 'r') as f:
        content = f.read()

    result = parse_shape_txt(content, "shapes_test_normal.txt")
    net_name, shapes_data, polygons = result

    print(f"  Layers in file: {list(shapes_data.keys())}")

    config = get_sram_7nm_config()
    ProfessionalLayoutReviewEngine(config)

    # Check if layers match
    for layer in shapes_data.keys():
        if layer in config.tech_config.layers:
            print(f"    {layer}: FOUND in tech config")
        else:
            print(f"    {layer}: NOT FOUND in tech config → RC calculation will fail!")

            # Try lowercase
            lower_layer = layer.lower()
            if lower_layer in config.tech_config.layers:
                print(f"      → lowercase '{lower_layer}' FOUND")


def run_unit_tests():
    """运行单元测试"""
    test_dir = os.path.dirname(os.path.abspath(__file__))

    # Discover and run all unit tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test modules
    test_modules = [
        'test_rc_calculator',
        'test_polygon_distance',
        'test_matching_analyzer',
    ]

    for module in test_modules:
        try:
            suite.addTests(loader.discover(test_dir, pattern=f'{module}.py'))
        except Exception as e:
            print(f"Warning: Could not load {module}: {e}")

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 60)
    print("Layout Review Tool - Test Suite")
    print("=" * 60)

    # Check if running unit tests only
    if '--unit' in sys.argv:
        success = run_unit_tests()
        sys.exit(0 if success else 1)

    try:
        test_parse_shape_txt()
        test_layer_parsing_issue()
        test_rc_calculation()
        test_drc_violation()
        test_matching_analysis()
        test_full_review()

        print("\n" + "=" * 60)
        print("All functional tests passed! [OK]")
        print("=" * 60)

        # Optionally run unit tests
        if '--all' in sys.argv:
            print("\n" + "=" * 60)
            print("Running unit tests...")
            print("=" * 60)
            success = run_unit_tests()
            sys.exit(0 if success else 1)

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
