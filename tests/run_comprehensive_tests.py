#!/usr/bin/env python3
"""
Comprehensive Test Suite for Layout Review Tool
Tests shape parsing, RC calculation, and rule checking with realistic scenarios
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_system import LayoutReviewConfig
from layout_review_app import parse_shape_txt
from review_engine import ProfessionalLayoutReviewEngine, TechConfig


def create_test_config():
    """Create a test config with TSMC N7-like layer parameters"""
    tech = TechConfig(
        name="TSMC_N7_Test",
        node="7nm",
        voltage=0.75,
        temperature=85.0,
        layers={
            'M1': {'type': 'metal', 'direction': 'vertical', 'min_width': 0.034,
                   'resistance_per_sq': 0.15, 'capacitance_per_um': 0.20,
                   'current_density': 10.0, 'color': '#1f77b4', 'order': 10},
            'M2': {'type': 'metal', 'direction': 'horizontal', 'min_width': 0.020,
                   'resistance_per_sq': 0.12, 'capacitance_per_um': 0.16,
                   'current_density': 12.0, 'color': '#ff7f0e', 'order': 20},
            'M3': {'type': 'metal', 'direction': 'vertical', 'min_width': 0.020,
                   'resistance_per_sq': 0.10, 'capacitance_per_um': 0.14,
                   'current_density': 14.0, 'color': '#2ca02c', 'order': 30},
            'M4': {'type': 'metal', 'direction': 'horizontal', 'min_width': 0.038,
                   'resistance_per_sq': 0.08, 'capacitance_per_um': 0.12,
                   'current_density': 18.0, 'color': '#d62728', 'order': 40},
            'M5': {'type': 'metal', 'direction': 'vertical', 'min_width': 0.038,
                   'resistance_per_sq': 0.06, 'capacitance_per_um': 0.10,
                   'current_density': 25.0, 'color': '#9467bd', 'order': 50},
            'M6': {'type': 'metal', 'direction': 'horizontal', 'min_width': 0.038,
                   'resistance_per_sq': 0.04, 'capacitance_per_um': 0.08,
                   'current_density': 35.0, 'color': '#8c564b', 'order': 60},
            'VIA1': {'type': 'via', 'min_size': 0.020, 'resistance': 0.8,
                     'current_capacity': 60.0, 'color': '#7f7f7f', 'order': 15},
            'VIA2': {'type': 'via', 'min_size': 0.020, 'resistance': 0.6,
                     'current_capacity': 70.0, 'color': '#bcbd22', 'order': 25},
            'VIA3': {'type': 'via', 'min_size': 0.020, 'resistance': 0.5,
                     'current_capacity': 80.0, 'color': '#17becf', 'order': 35},
            'VIA4': {'type': 'via', 'min_size': 0.036, 'resistance': 0.4,
                     'current_capacity': 100.0, 'color': '#637939', 'order': 45},
            'VIA5': {'type': 'via', 'min_size': 0.038, 'resistance': 0.3,
                     'current_capacity': 120.0, 'color': '#8c6d31', 'order': 55},
            # Aliases for lowercase layer names from Calibre
            'met1': {'type': 'metal', 'direction': 'vertical', 'min_width': 0.034,
                     'resistance_per_sq': 0.15, 'capacitance_per_um': 0.20,
                     'current_density': 10.0, 'color': '#1f77b4', 'order': 10},
            'met2': {'type': 'metal', 'direction': 'horizontal', 'min_width': 0.020,
                     'resistance_per_sq': 0.12, 'capacitance_per_um': 0.16,
                     'current_density': 12.0, 'color': '#ff7f0e', 'order': 20},
            'met3': {'type': 'metal', 'direction': 'vertical', 'min_width': 0.020,
                     'resistance_per_sq': 0.10, 'capacitance_per_um': 0.14,
                     'current_density': 14.0, 'color': '#2ca02c', 'order': 30},
            'via0': {'type': 'via', 'min_size': 0.020, 'resistance': 1.0,
                     'current_capacity': 50.0, 'color': '#7f7f7f', 'order': 15},
            'via1': {'type': 'via', 'min_size': 0.020, 'resistance': 0.8,
                     'current_capacity': 60.0, 'color': '#bcbd22', 'order': 25},
        },
        design_rules={
            'max_metal_length': 500,
            'max_via_chain': 4,
            'min_via_coverage': 0.02,
            'max_aspect_ratio': 200,
            'matching_tolerance': 0.05,
            'max_rc_variation': 0.10,
            'em_safety_factor': 0.8,
        }
    )
    return LayoutReviewConfig(
        name="Test_Config",
        tech_config=tech,
        check_rules=[]
    )


def test_case(name, filepath):
    """Run a single test case and report results"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    config = create_test_config()
    engine = ProfessionalLayoutReviewEngine(config)

    with open(filepath, 'r') as f:
        content = f.read()

    result = parse_shape_txt(content, os.path.basename(filepath))
    if result is None:
        print("  [FAIL] Failed to parse file")
        return False

    net_name, shapes_data, polygons = result
    print(f"  Net: {net_name}")
    print(f"  Layers: {list(shapes_data.keys())}")
    print(f"  Polygons: {len(polygons)}")

    engine.add_net_polygons(net_name, polygons)
    rc_data = engine.calculate_net_rc(net_name)

    print(f"  RC: R={rc_data.total_resistance:.2f} Ohm, C={rc_data.total_capacitance:.2f} fF")
    print(f"  Length: {rc_data.total_length:.2f} um")
    print(f"  Layer usage: {rc_data.layer_usage}")

    # Run applicable rules
    violations = []
    enabled_rules = engine.config.get_enabled_rules()
    for rule in enabled_rules:
        if rule.matches_net(net_name):
            engine._execute_check_rule(net_name, rule)
            for v in engine.violations:
                if v.net_name == net_name:
                    violations.append(v)

    print(f"  Violations found: {len(violations)}")
    for v in violations:
        print(f"    [{v.severity.value.upper()}] {v.rule_id}: {v.message}")

    return True


def main():
    test_dir = os.path.dirname(__file__)

    tests = [
        ("shapes_test_long_wire_rc.txt", "Long Wire RC (>100um, triggers SI001)"),
        ("shapes_test_parallel_coupling.txt", "Parallel Lines (coupling capacitance)"),
        ("shapes_test_via_chain.txt", "Via Chain (stacked vias, triggers QTY001)"),
        ("shapes_test_high_load.txt", "High Load (large capacitance, triggers SI003)"),
        ("shapes_test_power_net_em.txt", "Power Net EM (narrow width, triggers EM002)"),
        ("shapes_test_narrow_long.txt", "Narrow Long Wire (aspect ratio, triggers QTY004)"),
        ("shapes_test_missing_via.txt", "Missing Via (adjacent layers, triggers DRC003)"),
        ("shapes_test_bitline_mismatch_BL0.txt", "Bitline BL0 (for matching with BLB0)"),
        ("shapes_test_bitline_mismatch_BLB0.txt", "Bitline BLB0 (mismatched with BL0)"),
        ("shapes_test_wordline_WL0.txt", "Wordline WL0 (for matching with WL1)"),
        ("shapes_test_wordline_WL1.txt", "Wordline WL1 (mismatched with WL0)"),
        ("shapes_test_complex_route.txt", "Complex Multi-layer Route (triggers QTY006)"),
    ]

    print("="*60)
    print("Layout Review Tool - Comprehensive Test Suite")
    print("="*60)
    print(f"Test directory: {test_dir}")

    passed = 0
    failed = 0

    for filename, description in tests:
        filepath = os.path.join(test_dir, filename)
        if not os.path.exists(filepath):
            print(f"\n[SKIP] {filename} - file not found")
            continue

        if test_case(description, filepath):
            passed += 1
        else:
            failed += 1

    # Test matching pairs
    print(f"\n{'='*60}")
    print("TEST: Bitline/Wordline Matching Analysis")
    print(f"{'='*60}")

    config = create_test_config()
    engine = ProfessionalLayoutReviewEngine(config)

    # Load bitlines
    for filename in ["shapes_test_bitline_mismatch_BL0.txt", "shapes_test_bitline_mismatch_BLB0.txt"]:
        filepath = os.path.join(test_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                result = parse_shape_txt(f.read(), filename)
            if result:
                net_name, shapes_data, polygons = result
                engine.add_net_polygons(net_name, polygons)
                rc = engine.calculate_net_rc(net_name)
                print(f"  {net_name}: R={rc.total_resistance:.2f} Ohm, L={rc.total_length:.2f} um")

    # Analyze matching
    if "BL0" in engine.nets and "BLB0" in engine.nets:
        matching = engine.analyze_matching("BL0", "BLB0")
        print("\n  BL0 vs BLB0 Matching:")
        print(f"    Score: {matching.match_score:.1f}")
        print(f"    Length ratio: {matching.length_ratio:.4f}")
        print(f"    Resistance ratio: {matching.resistance_ratio:.4f}")
        print(f"    Via count diff: {matching.via_count_diff}")
        if matching.issues:
            print(f"    Issues: {', '.join(matching.issues)}")

    # Load wordlines
    engine2 = ProfessionalLayoutReviewEngine(config)
    for filename in ["shapes_test_wordline_WL0.txt", "shapes_test_wordline_WL1.txt"]:
        filepath = os.path.join(test_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                result = parse_shape_txt(f.read(), filename)
            if result:
                net_name, shapes_data, polygons = result
                engine2.add_net_polygons(net_name, polygons)
                rc = engine2.calculate_net_rc(net_name)
                print(f"  {net_name}: R={rc.total_resistance:.2f} Ohm, L={rc.total_length:.2f} um")

    if "WL0" in engine2.nets and "WL1" in engine2.nets:
        matching2 = engine2.analyze_matching("WL0", "WL1")
        print("\n  WL0 vs WL1 Matching:")
        print(f"    Score: {matching2.match_score:.1f}")
        print(f"    Length ratio: {matching2.length_ratio:.4f}")
        print(f"    Resistance ratio: {matching2.resistance_ratio:.4f}")
        print(f"    Via count diff: {matching2.via_count_diff}")
        if matching2.issues:
            print(f"    Issues: {', '.join(matching2.issues)}")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
