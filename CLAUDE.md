# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`svdb_shape_plot-main` contains a **Professional Layout Review Tool** for SRAM and analog circuit layouts. It provides RC extraction, EM/IR analysis, signal matching checks, and professional PPTX/PDF report generation.

## Commands

```bash
cd sram_layout_review

# Install dependencies
pip install -r requirements.txt

# Run the application
./start.sh
# or
python3 layout_review_app.py

# Access UI at http://localhost:8050
```

## Architecture

### Core Components

| File | Purpose |
|------|---------|
| `layout_review_app.py` | Dash web UI - main entry point |
| `review_engine.py` | Core analysis engine - RC calc, EM, matching |
| `config_system.py` | Tech configs (7nm/5nm), check rules, rule management |
| `report_generator.py` | PPTX/PDF report generation with charts |
| `rules/base_rule.py` | Abstract base class for all check rules |
| `rules/registry.py` | Plugin registry for rule discovery/loading |

### Rule Plugin System

Rules live in `rules/{category}/` subdirectories:
- `drc/` - Design Rule Checks (width, spacing, via)
- `si/` - Signal Integrity (long wire RC, high R/C)
- `em/` - Electromigration analysis
- `sram/` - SRAM-specific checks (bitline/wordline matching)

Each rule inherits from `BaseRule` and implements `check()`. The `RuleRegistry` auto-discovers and loads rule plugins.

### Data Flow

1. **Shape Import** → polygons loaded from `.txt` files or YAML batch config
2. **RC Calculation** → `ProfessionalLayoutReviewEngine.calculate_net_rc()` converts polygons to wire segments
3. **Rule Execution** → enabled rules checked per net via `_execute_check_rule()`
4. **Analysis** → EM analysis, matching analysis (BL/BLB, WL pairs)
5. **Report Generation** → PPTX/PDF via `report_generator.py`

### Key Data Models

- `Polygon` - layout shape with points, layer, net
- `WireSegment` - extracted from polygons for RC calculation
- `NetRCData` - per-net RC totals and per-layer breakdown
- `Violation` - rule violation with severity, location, suggestion
- `MatchingAnalysis` - pair-wise net matching score

### Configuration System

`LayoutReviewConfig` holds:
- `TechConfig` - per-layer properties (min_width, resistance/μm, capacitance/μm, current_density)
- `CheckRule` list - 19 default rules covering DRC, SI, EM, SRAM, quality

Presets: `get_sram_7nm_config()`, `get_sram_5nm_config()`, `get_analog_config()`
