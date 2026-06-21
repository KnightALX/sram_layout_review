"""Integration tests for rules/ plugin registry."""
import sys

sys.path.insert(0, '.')

import rules  # noqa: F401 — triggers registration
from rules.registry import create_rule, list_rules


def test_registry_lists_drc_rules():
    all_ids = list_rules()
    assert "DRC001" in all_ids
    assert "SI001" in all_ids


def test_drc001_instantiates():
    rule = create_rule("DRC001", {"safety_factor": 0.95})
    assert rule is not None
    assert rule.RULE_ID == "DRC001"
