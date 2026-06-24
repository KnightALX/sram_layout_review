"""Tests for routing config tab layout generation + toggle behavior (Task 4/5).

Covers:
- initial disabled + button classes
- mode switches (via state + logic)
- editable preset prevent (via mocked logic invocation)
- Apply side effects
- interactions with shared update paths (thresh edits, status)
- tab switch re-hydration (Task 5): _compute_rehydrate_outputs + state roundtrip
- red/invalid guard (user_modified vs last-known-good)
"""
import sys

sys.path.insert(0, '.')

from dash.exceptions import PreventUpdate

from app.routing_config import (
    _compute_rehydrate_outputs,
    _disabled_list,
    _handle_routing_preset_or_thresh,
    _mode_button_classes,
    create_routing_config_tab,
    get_threshold_input_ids,
)
from app.routing_state import RoutingState
from app.routing_state import routing_state as global_routing_state
from config.routing_thresholds import RoutingThresholds
from core.routing_metrics import check_gates


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
    assert "Edit Mode" in status_txt and "Blocked" in status_txt

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


# --- Task 5: tab re-hydration and red-guard tests ---

def test_compute_rehydrate_outputs_matches_state_frozen():
    """Rehydrate helper must return values + disabled=True + frozen-primary classes when frozen."""
    _reset_routing_state_to_default()
    global_routing_state.set_frozen_mode(True)
    # Make sure a known preset value is present
    thr = global_routing_state.get_thresholds()
    out = _compute_rehydrate_outputs()
    # Indices (0-based) per helper contract:
    # 0:frozen-cls, 1:editable-cls, 2:preset-status, 3:config-status,
    # 4:unsaved-badge, 5:apply-status, 6:preset-value,
    # 7..13: 7 values, 14..20: 7 disabled
    assert "btn-primary" in out[0]
    assert "btn-secondary" in out[1]
    assert out[6] == global_routing_state.current_preset
    # values start at 7
    assert abs(out[7] - thr.max_h_ratio) < 1e-12  # first field
    # disabled start at 14
    assert out[14] is True  # first disabled should be True (frozen)
    assert out[20] is True  # last disabled True


def test_compute_rehydrate_outputs_matches_state_editable_custom():
    """After entering editable + custom value, rehydrate must surface the edited values + disabled=False."""
    _reset_routing_state_to_default()
    # Simulate user entering editable and applying a different value
    if global_routing_state.custom_thresholds is None:
        global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
            global_routing_state.thresholds.to_dict()
        )
    global_routing_state.custom_thresholds.max_tau_ps = 42.0
    global_routing_state.set_frozen_mode(False)

    out = _compute_rehydrate_outputs()
    thr = global_routing_state.get_thresholds()
    assert global_routing_state.is_frozen is False
    # mode buttons: frozen secondary, editable primary
    assert "btn-secondary" in out[0]
    assert "btn-primary" in out[1]
    # locate max_tau_ps index: THRESHOLD_FIELDS order is fixed
    # fields: 0 max_h,1 max_v,2 r,3 c,4 tau,5 via,6 sim
    tau_idx = 7 + 4
    assert abs(out[tau_idx] - 42.0) < 1e-9
    assert abs(thr.max_tau_ps - 42.0) < 1e-9
    dis_start = 14
    assert out[dis_start + 4] is False  # tau disabled == False (editable)
    # transient badges should be cleared by rehydrate
    assert "unsaved" not in str(out[4]).lower()
    assert str(out[5]) == "" or "display" in str(out[5])  # empty or hidden span repr


def test_handle_logic_no_red_or_unsaved_when_values_match_last_good():
    """Non-modifying thresh input fire (values == current) must NOT emit unsaved badge or red Invalid."""
    _reset_routing_state_to_default()
    global_routing_state.set_frozen_mode(True)
    curr = global_routing_state.get_thresholds()

    # Pass values that match exactly (as would happen on re-populate after load or tab switch)
    # Pull the canonical field order
    from app.routing_config import THRESHOLD_FIELDS as _TF
    auth_vals = [getattr(curr, name) for name, *_ in _TF]

    out = _handle_routing_preset_or_thresh(None, tuple(auth_vals), "thresh-max_h_ratio")

    # unsaved badge is index 4; apply guidance is index 5
    badge = str(out[4])
    guidance = str(out[5])
    status = str(out[3])
    # Must not contain the unsaved indicator or red Invalid text
    assert "unsaved" not in badge.lower()
    assert "invalid" not in status.lower()
    assert "invalid" not in guidance.lower()
    assert "#C0392B" not in str(out)  # red color only appears on real failure path


def test_rehydrate_after_tab_switch_simulation():
    """Simulate tab switch re-hydration after state mutation (as done by _rehydrate_on_tab)."""
    _reset_routing_state_to_default()
    # User switches mode + edits (via apply side-effect simulation)
    global_routing_state.set_frozen_mode(False)
    if global_routing_state.custom_thresholds is None:
        global_routing_state.custom_thresholds = RoutingThresholds.from_dict(
            global_routing_state.thresholds.to_dict()
        )
    global_routing_state.custom_thresholds.min_via_coverage = 0.77

    # "Tab switch" = calling the rehydrate computer directly
    out = _compute_rehydrate_outputs()
    # Verify authoritative value is restored to UI
    via_idx = 7 + 5  # 5th custom field after the 7 fixed prefix
    assert abs(out[via_idx] - 0.77) < 1e-12
    # And disabled reflects editable
    assert out[14 + 5] is False


# --- Task 7 Step 3: frozen vs editable apply persistence test ---
# Simulates state changes, Apply-like commits, and tab switches (via rehydrate helpers).
# Uses public APIs (get_thresholds, set_frozen_mode, is_frozen) for the flow where possible.
# Asserts values shown in inputs (rehydrate outs) + values used for review gates.

def test_frozen_vs_editable_apply_persistence():
    """Apply + frozen/editable + tab rehydrate must persist the right values.
    Review code must see the thresholds from get_thresholds() after changes.
    """
    _reset_routing_state_to_default()
    rs = global_routing_state

    # 1. Start in frozen (default)
    assert rs.is_frozen is True
    thr_frozen = rs.get_thresholds()
    orig_tau = thr_frozen.max_tau_ps

    # Tab switch rehydrate in frozen must give disabled + preset vals
    out = _compute_rehydrate_outputs()
    assert "btn-primary" in out[0]  # frozen class
    assert out[14] is True  # first disabled
    assert abs(out[7 + 4] - orig_tau) < 1e-12  # tau value (index 4 in thresh)

    # 2. Switch to editable via public helper (simulates mode-editable click)
    rs.set_frozen_mode(False)
    assert rs.is_frozen is False
    # get still returns preset (custom not yet created)
    assert abs(rs.get_thresholds().max_tau_ps - orig_tau) < 1e-12

    # Rehydrate (tab switch) reflects editable + same values
    out_e = _compute_rehydrate_outputs()
    assert "btn-primary" in out_e[1]  # editable primary
    assert out_e[14] is False
    assert abs(out_e[7 + 4] - orig_tau) < 1e-12

    # 3. Simulate Apply: user changes a value, Apply commits custom + stays editable
    # (use minimal direct for test setup only; production Apply in config uses similar)
    if rs.custom_thresholds is None:
        rs.custom_thresholds = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    new_tau = orig_tau + 5.0
    new_sim = 95
    rs.custom_thresholds.max_tau_ps = new_tau
    rs.custom_thresholds.min_similarity = new_sim
    # (Apply would also call set_frozen_mode(False) but already is)

    assert rs.is_frozen is False
    thr_custom = rs.get_thresholds()
    assert abs(thr_custom.max_tau_ps - new_tau) < 1e-9
    assert abs(thr_custom.min_similarity - new_sim) < 1e-9

    # 4. Tab switch (rehydrate) after apply must show the applied custom values + editable
    out_after = _compute_rehydrate_outputs()
    tau_idx = 7 + 4
    sim_idx = 7 + 6
    assert abs(out_after[tau_idx] - new_tau) < 1e-9
    assert abs(out_after[sim_idx] - new_sim) < 1e-9
    assert out_after[14] is False  # still editable

    # 5. Values used for review gates must come from get_thresholds() (current custom)
    # Pick a tau value between tight (orig-1) and preset orig so:
    #  - fails when using tightened custom
    #  - passes when frozen back to preset
    mid_tau = orig_tau - 0.5
    dummy_metrics = {
        "net_name": "t",
        "h_ratio": 0.1, "v_ratio": 0.1,
        "r_total": 1.0, "c_total": 1.0,
        "effective_tau_ps": mid_tau,
        "via_coverage": 0.99, "missing_via_count": 0,
        "similarity_score": 99.0,
    }
    # direct call would use thresholds from state in real _run, here we simulate gate using get
    rs.custom_thresholds.max_tau_ps = orig_tau - 1.0
    pass_tight, _ = check_gates(dummy_metrics, rs.get_thresholds(), has_golden=False)
    assert pass_tight is False  # fails tightened (custom) gate
    # Switch to frozen: custom is cleared, get returns preset (higher tolerance)
    rs.set_frozen_mode(True)
    pass_frozen, _ = check_gates(dummy_metrics, rs.get_thresholds(), has_golden=False)
    assert pass_frozen is True  # old preset allows the mid_tau

    # rehydrate after frozen switch shows original
    out_f2 = _compute_rehydrate_outputs()
    assert abs(out_f2[tau_idx] - orig_tau) < 1e-12  # Custom is preserved (draft area); get() returns preset because frozen

    # cleanup
    _reset_routing_state_to_default()


# --- Task 6: preserve custom_thresholds across Locked toggle ---


def test_set_frozen_mode_true_preserves_custom_thresholds():
    """Switching to Locked should NOT discard custom_thresholds (spec:draft area)."""
    _reset_routing_state_to_default()
    rs = global_routing_state
    rs.set_frozen_mode(False)
    # Simulate user applying a custom value
    if rs.custom_thresholds is None:
        rs.custom_thresholds = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    rs.custom_thresholds.max_tau_ps = 99.0
    assert rs.custom_thresholds.max_tau_ps == 99.0

    # Switch to Locked: custom should be preserved
    rs.set_frozen_mode(True)
    assert rs.custom_thresholds is not None
    assert rs.custom_thresholds.max_tau_ps == 99.0
    # get_thresholds() still returns the preset (frozen behavior)
    preset = RoutingThresholds.for_preset(rs.current_preset)
    assert abs(rs.get_thresholds().max_tau_ps - preset.max_tau_ps) < 1e-9


def test_switch_back_to_editable_restores_custom():
    """After Locked -> Editable, custom values should be visible again."""
    _reset_routing_state_to_default()
    rs = global_routing_state
    rs.set_frozen_mode(False)
    if rs.custom_thresholds is None:
        rs.custom_thresholds = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    rs.custom_thresholds.max_tau_ps = 77.0
    rs.set_frozen_mode(True)
    rs.set_frozen_mode(False)
    assert rs.custom_thresholds is not None
    assert rs.custom_thresholds.max_tau_ps == 77.0
    assert abs(rs.get_thresholds().max_tau_ps - 77.0) < 1e-9


def test_set_custom_writes_and_keeps_editable():
    """set_custom() should write to custom_thresholds and leave mode editable."""
    _reset_routing_state_to_default()
    rs = global_routing_state
    new_thr = RoutingThresholds.from_dict(rs.get_thresholds().to_dict())
    new_thr.max_r_ohm = 12.0
    rs.set_custom(new_thr)
    assert rs.custom_thresholds is new_thr
    assert rs.is_frozen is False
    assert abs(rs.get_thresholds().max_r_ohm - 12.0) < 1e-9

