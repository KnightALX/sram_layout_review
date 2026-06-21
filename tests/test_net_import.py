import textwrap
import pytest
from core.data_parsing import build_net_record, import_shape_from_file


@pytest.fixture
def shape_content():
    return textwrap.dedent("""\
        Net_Shapes 20000
        met1
        1 1 1 rect 0 0:0:0 0
        p 4 4
        0 0
        100 0
        100 100
        0 100
    """)


def test_import_shape_from_file_returns_net_id(shape_content, tmp_path):
    f = tmp_path / "report_32x128" / "shapes_demo_net.txt"
    f.parent.mkdir(parents=True)
    f.write_text(shape_content)
    rec = import_shape_from_file(str(f))
    assert rec is not None
    assert rec["net_id"] == "report_32x128/demo_net"
    assert rec["source"] == "report_32x128"
    assert rec["net_name"] == "demo_net"


def test_build_net_record_yaml_source_override(shape_content, tmp_path):
    f = tmp_path / "report_32x128" / "shapes_demo_net.txt"
    f.parent.mkdir(parents=True)
    f.write_text(shape_content)
    rec = build_net_record(str(f), yaml_source="sram_32x64")
    assert rec["net_id"] == "sram_32x64/demo_net"
    assert rec["source"] == "sram_32x64"


def test_build_net_record_custom_net_name(shape_content, tmp_path):
    f = tmp_path / "report_32x128" / "shapes_demo_net.txt"
    f.parent.mkdir(parents=True)
    f.write_text(shape_content)
    rec = build_net_record(str(f), custom_net_name="WL0")
    assert rec["net_id"] == "report_32x128/WL0"