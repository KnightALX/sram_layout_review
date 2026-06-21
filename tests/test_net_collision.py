from app.state import AppState
from core.data_parsing import build_net_record
import textwrap

SHAPE = textwrap.dedent("""\
    Net_Shapes 20000
    met1
    1 1 1 rect 0 0:0:0 0
    p 4 4
    0 0
    100 0
    100 100
    0 100
""")


def test_two_folders_same_filename_coexist(tmp_path):
    for folder in ("report_32x128", "report_32x64"):
        p = tmp_path / folder / "shapes_same_net.txt"
        p.parent.mkdir(parents=True)
        p.write_text(SHAPE)
    state = AppState()
    for folder in ("report_32x128", "report_32x64"):
        rec = build_net_record(str(tmp_path / folder / "shapes_same_net.txt"))
        state.nets_data[rec["net_id"]] = rec
    assert len(state.nets_data) == 2
    assert "report_32x128/same_net" in state.nets_data
    assert "report_32x64/same_net" in state.nets_data


def test_regex_filter_by_source():
    import re
    names = ["report_32x128/trk", "report_32x64/trk"]
    pattern = re.compile(r"^report_32x128/")
    assert [n for n in names if pattern.search(n)] == ["report_32x128/trk"]