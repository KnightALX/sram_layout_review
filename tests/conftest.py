"""Shared pytest configuration. pythonpath set in pyproject.toml."""
import pytest


@pytest.fixture
def tech_layers_met12():
    return {
        "met1": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.15,
                 "capacitance_per_um": 0.20, "min_space": 0.032},
        "met2": {"type": "metal", "min_width": 0.032, "resistance_per_sq": 0.12,
                 "capacitance_per_um": 0.16, "min_space": 0.032},
        "via1": {"type": "via", "min_size": 0.024, "resistance": 1.0},
    }
