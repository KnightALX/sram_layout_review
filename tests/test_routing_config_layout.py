"""Tests for routing config tab layout generation + toggle behavior (Task 4 quality fixes).

Covers:
- initial disabled + button classes
- mode switches (via state + logic)
- editable preset prevent (via mocked logic invocation)
- Apply side effects
- interactions with shared update paths (thresh edits, status)
"""
import sys

sys.path.insert(0, '.')

from dash.exceptions import PreventUpdate

from app.routing_config import (
    _disabled_list,
    _handle_routing_preset_or_thresh,
    _mode_button_classes,
    create_routing_config_tab,
    get_threshold_input_ids,
)
from app.routing_state import RoutingState
from app.routing_state import routing_state as global_routing_state
from config.routing_thresholds import RoutingThresholds


def _find_by_id(node, target_id):
    """Recursively search Dash component tree for one with matching id."""
    if hasattr(node, "id") and node.id == target_id:
        return node
    children = getattr(node, "children", None)
    if isinstance(children, list):
        for c in children:
            found = _find_by_id(c, target_id)
            if found is not None:
                return found
    elif children is not None:
        return _find_by_id(children, target_id)
    return None


def _reset_routing_state_to_default():
    """Helper to reset the module singleton for test isolation (use in try/finally)."""
    global_routing_state.current_preset = "sram_7nm_wl"
    global_routing_state.thresholds = RoutingThresholds.for_preset("sram_7nm_wl")
    global_routing_state.custom_thresholds = None
    global_routing_state.set_frozen_mode(True)
    global_routing_state.golden_regex = ""
    global_routing_state.batch_regex = ""
    global_routing_state.golden_net_name = ""
    global_routing_state.batch_results = {}
    global_routing_state.review_completed = False


def test_create_routing_config_tab_returns_div():
    layout = create_routing_config_tab()
    assert layout is not None


def test_threshold_input_ids_contains_all_thresholds():
    ids = get_threshold_input_ids()
    for name in ("max_h_ratio", "max_v_ratio", "max_r_ohm", "max_c_ff",
                 "max_tau_ps", "min_via_coverage", "min_similarity"):
        assert f"thresh-{name}" in ids, f"Missing input: {name}"


# --- Behavioral tests for toggle (Issue 1) ---

def test_initial_layout_frozen_disabled_and_classes():
    """Initial state: frozen=True produces primary '冻结', secondary '可编辑', inputs disabled."""
    _reset_routing_state_to_default()
    assert global_routing_state.is_frozen is True

    layout = create_routing_config_tab()

    frozen_btn = _find_by_id(layout, "mode-frozen")
    editable_btn = _find_by_id(layout, "mode-editable")
    assert frozen_btn is not None
    assert editable_btn is not None
    assert "btn-primary" in frozen_btn.className
    assert "btn-secondary" in editable_btn.className

    # Spot check a few threshold inputs are present and disabled
    for field in ["max_h_ratio", "max_tau_ps", "min_via_coverage"]:
        inp = _find_by_id(layout, f"thresh-{field}")
        assert inp is not None, f"Missing thresh input {field}"
        assert inp.disabled is True


def test_helpers_pure_mode_and_disabled():
    """Pure helpers cover class and disabled computation used across callbacks + layout."""
    f, e = _mode_button_classes(True)
    assert "btn-primary" in f and "frozen" not in f.lower()
    assert "btn-secondary" in e
    f2, e2 = _mode_button_classes(False)
    assert "btn-secondary" in f2
    assert "btn-primary" in e2

    d7 = _disabled_list(True, 7)
    assert d7 == [True] * 7
    d0 = _disabled_list(False, 3)
    assert d0 == [False] * 3


def test_layout_reflects_editable_after_state_change(monkeypatch):
    """When state is editable, create_ (and callbacks) produce disabled=False + swapped classes."""
    _reset_routing_state_to_default()
    # Force editable on the global used by create_
    global_routing_state.set_frozen_mode(False)
    assert global_routing_state.is_frozen is False

    layout = create_routing_config_tab()

    frozen_btn = _find_by_id(layout, "mode-frozen")
    editable_btn = _find_by_id(layout, "mode-editable")
    assert "btn-secondary" in frozen_btn.className
    assert "btn-primary" in editable_btn.className

    for field in ["max_r_ohm", "min_similarity"]:
        inp = _find_by_id(layout, f"thresh-{field}")
        assert inp is not None
        assert inp.disabled is False


def test_state_is_frozen_accessor_and_set_side_effects():
    """The thin is_frozen accessor + set_frozen_mode contract."""
    s = RoutingState()
    assert s.is_frozen is True
    assert callable(getattr(s, "is_frozen", None)) is False  # it's property, not method, but readable as attr

    s.set_frozen_mode(False)
    assert s.is_frozen is False
    # custom should be populated on demand by call sites; direct get uses it or falls back

    s.set_frozen_mode(True)
    assert s.is_frozen is True
    assert s.custom_thresholds is None


def test_handle_logic_editable_preset_prevent(monkeypatch):
    """Mocked invocation of preset change logic in editable: returns revert + warn, guard raises on no-op."""
    _reset_routing_state_to_default()
    global_routing_state.set_frozen_mode(False)  # editable
    curr = global_routing_state.current_preset

    # Simulate user changing dropdown to something else (triggered)
    # Should return the prevent-revert tuple (7 fixed outputs + 7 vals + 7 dis)
    # We don't care exact thresh, just that curr_p is used and warn present.
    try:
        out = _handle_routing_preset_or_thresh("some_other_preset", (0.5,)*7, "routing-preset")
    except PreventUpdate:
        out = None
    assert out is not None
    # position 6 (0-based) is the preset value output
    assert out[6] == curr
    # status child (index 3) contains the Chinese prevent message
    status_txt = str(out[3])
    assert "编辑模式" in status_txt and "阻止" in status_txt

    # Now simulate the revert fire (preset now equals current) -> should raise Prevent
    try:
        _handle_routing_preset_or_thresh(curr, (0.5,)*7, "routing-preset")
        raised = False
    except PreventUpdate:
        raised = True
    assert raised, "Guard should suppress re-trigger by raising PreventUpdate"


def test_handle_logic_thresh_edit_shows_unsaved(monkeypatch):
    """Manual thresh edit path (shared with update cb) emits unsaved badge + guidance (editable assumed)."""
    _reset_routing_state_to_default()
    global_routing_state.set_frozen_mode(False)

    # Pass some thresh values; should not raise, return unsaved badge in outputs
    # Use values that pass RoutingThresholds.validate() (h+v >=1.0)
    out = _handle_routing_preset_or_thresh(None, (0.6, 0.5, 100.0, 10.0, 5.0, 0.8, 80), "thresh-max_h_ratio")
    # unsaved badge is index 4
    badge = out[4]
    assert "unsaved changes" in str(badge)


def test_apply_side_effects_on_state():
    """Apply path (simulated via state API used by _apply cb) sets editable + custom."""
    _reset_routing_state_to_default()
    assert global_routing_state.is_frozen is True

    # Mirror what _apply does on success path
    if global_routing_state.custom_thresholds is None:
        global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
            global_routing_state.thresholds.to_dict()
        )
    global_routing_state.custom_thresholds.max_h_ratio = 0.42
    global_routing_state.set_frozen_mode(False)

    thr = global_routing_state.get_thresholds()
    assert global_routing_state.is_frozen is False
    assert abs(thr.max_h_ratio - 0.42) < 0.001
    assert global_routing_state.custom_thresholds is not None


def test_handle_frozen_preset_load_side_effect():
    """Frozen preset change path mutates state (real preset load is safe)."""
    _reset_routing_state_to_default()
    global_routing_state.set_frozen_mode(True)
    # Make current different so guard does not fire on target switch
    global_routing_state.current_preset = "sram_5nm_io_bl"

    out = _handle_routing_preset_or_thresh("sram_7nm_wl", (), "routing-preset")
    assert out[6] == "sram_7nm_wl"
    assert global_routing_state.is_frozen is True
    # state mutated by the load path
    assert global_routing_state.current_preset == "sram_7nm_wl"

