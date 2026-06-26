def test_threshold_source_banner_no_green_background():
    from app.routing_review import _build_threshold_source
    el = _build_threshold_source("Locked preset: sram_7nm_wl")
    s = str(el)
    # The dark-green background should be gone
    assert "rgba(5, 46, 22" not in s
    # The text should still be there
    assert "Active Threshold Source" in s
    assert "Locked preset: sram_7nm_wl" in s