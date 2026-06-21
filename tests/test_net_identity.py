import pytest
from core.net_identity import (
    DEFAULT_SOURCE,
    derive_source_from_path,
    derive_source_from_relative_path,
    make_net_id,
    parse_net_id,
    resolve_source,
    validate_source_or_net_name,
)


def test_make_net_id_joins_source_and_net_name():
    assert make_net_id("report_32x128", "trk_dbl_sa") == "report_32x128/trk_dbl_sa"


def test_make_net_id_rejects_slash_in_parts():
    with pytest.raises(ValueError):
        make_net_id("bad/path", "net")
    with pytest.raises(ValueError):
        make_net_id("src", "bad/net")


def test_parse_net_id_round_trip():
    net_id = "report_32x64/trk_dbl_sa"
    assert make_net_id(*parse_net_id(net_id)) == net_id


def test_parse_net_id_rejects_missing_slash():
    with pytest.raises(ValueError):
        parse_net_id("flat_name")


def test_derive_source_from_path_uses_immediate_parent():
    path = "/data/report_32x128/shapes_trk_dbl_sa.txt"
    assert derive_source_from_path(path) == "report_32x128"


def test_derive_source_from_path_empty_parent_returns_default():
    assert derive_source_from_path("/shapes_trk.txt") == DEFAULT_SOURCE


def test_derive_source_from_relative_path():
    assert derive_source_from_relative_path("report_32x128/shapes_trk_dbl_sa.txt") == "report_32x128"
    assert derive_source_from_relative_path("shapes_trk_dbl_sa.txt") == DEFAULT_SOURCE


def test_resolve_source_yaml_overrides_path():
    path = "/data/report_32x128/shapes.txt"
    assert resolve_source(path, yaml_source="custom") == "custom"
    assert resolve_source(path) == "report_32x128"


def test_validate_source_or_net_name_strips_whitespace():
    assert validate_source_or_net_name("  foo  ") == "foo"