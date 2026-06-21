# Net Source Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate net-name collisions across folders by keying `nets_data` on composite IDs `source/net_name`, with auto-derived or YAML-declared `source`.

**Architecture:** Add `core/net_identity.py` helpers (`make_net_id`, `derive_source_from_path`, `resolve_source`). Import pipeline builds composite keys before writing `app_state.nets_data`. UI shows full IDs in Net Selection; browser folder upload uses a clientside callback to capture `webkitRelativePath`. Downstream modules already use string net keys — no engine API rename needed.

**Tech Stack:** Python 3.8+, Dash, pytest, PyYAML (optional for batch tests)

**Spec:** `docs/superpowers/specs/2026-06-21-net-source-identity-design.md`

---

## File Map

| File | Responsibility |
|------|----------------|
| `core/net_identity.py` | **Create** — composite ID helpers, source resolution |
| `tests/test_net_identity.py` | **Create** — unit tests for identity helpers |
| `tests/test_net_import.py` | **Create** — import integration (YAML source, collisions) |
| `core/data_parsing.py` | **Modify** — return `source`, `net_id`, `filepath`; YAML `source` field |
| `app/callbacks.py` | **Modify** — upload callbacks, `_store_net_entry`, properties panel |
| `app/layout.py` | **Modify** — folder upload control, properties Source/Net rows, filter hint |
| `layout_review_app.py` | **Modify** — register clientside folder-upload callback |
| `app/state.py` | **Modify** — docstring: keys are `net_id` |
| `core/visualization.py` | **Modify** — figure title uses composite ID |
| `example_batch_import.yaml` | **Modify** — document `source` field |
| `CLAUDE.md` | **Modify** — one paragraph on composite net IDs |

---

### Task 1: Net identity helpers

**Files:**
- Create: `core/net_identity.py`
- Create: `tests/test_net_identity.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_net_identity.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: core.net_identity`

- [ ] **Step 3: Write minimal implementation**

```python
# core/net_identity.py
"""Composite net identity: source/net_name keys for nets_data."""
from __future__ import annotations

import os
from typing import Optional, Tuple

DEFAULT_SOURCE = "_default"


def validate_source_or_net_name(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("source and net_name must be non-empty")
    if "/" in value:
        raise ValueError("source and net_name must not contain '/'")
    return value


def make_net_id(source: str, net_name: str) -> str:
    source = validate_source_or_net_name(source)
    net_name = validate_source_or_net_name(net_name)
    return f"{source}/{net_name}"


def parse_net_id(net_id: str) -> Tuple[str, str]:
    if not net_id or "/" not in net_id:
        raise ValueError(f"Invalid net_id (expected source/net_name): {net_id!r}")
    source, net_name = net_id.split("/", 1)
    if not source or not net_name:
        raise ValueError(f"Invalid net_id (empty part): {net_id!r}")
    return source, net_name


def derive_source_from_path(filepath: str) -> str:
    parent = os.path.basename(os.path.dirname(os.path.abspath(os.path.expanduser(filepath))))
    if not parent or parent in (".", ""):
        return DEFAULT_SOURCE
    return parent


def derive_source_from_relative_path(relative_path: str) -> str:
    relative_path = (relative_path or "").replace("\\", "/").strip()
    if "/" not in relative_path:
        return DEFAULT_SOURCE
    parent = relative_path.rsplit("/", 1)[0]
    parent = os.path.basename(parent) if "/" in parent else parent
    return parent or DEFAULT_SOURCE


def resolve_source(filepath: str, yaml_source: Optional[str] = None) -> str:
    if yaml_source is not None and str(yaml_source).strip():
        return validate_source_or_net_name(str(yaml_source))
    if filepath:
        return derive_source_from_path(filepath)
    return DEFAULT_SOURCE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_net_identity.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add core/net_identity.py tests/test_net_identity.py
git commit -m "feat: add composite net identity helpers (source/net_name)"
```

---

### Task 2: Extend data_parsing import pipeline

**Files:**
- Modify: `core/data_parsing.py`
- Create: `tests/test_net_import.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_net_import.py
import os
import tempfile
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_net_import.py -v`
Expected: FAIL — `build_net_record` not defined

- [ ] **Step 3: Implement `build_net_record` and update `import_shape_from_file`**

In `core/data_parsing.py`, add imports:

```python
from core.net_identity import (
    DEFAULT_SOURCE,
    derive_source_from_relative_path,
    make_net_id,
    resolve_source,
)
```

Add function:

```python
def build_net_record(
    filepath: str,
    *,
    custom_net_name: str | None = None,
    yaml_source: str | None = None,
    relative_path: str | None = None,
) -> dict | None:
    """Parse a shape file and return a nets_data-ready record with composite net_id."""
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
        filename = os.path.basename(filepath)
        parsed = parse_shape_txt(content, filename)
        if not parsed:
            return None
        net_name, shapes_data, polygons = parsed
        if custom_net_name:
            net_name = custom_net_name
        if relative_path:
            source = derive_source_from_relative_path(relative_path)
        else:
            source = resolve_source(filepath, yaml_source=yaml_source)
        net_id = make_net_id(source, net_name)
        return {
            "net_id": net_id,
            "source": source,
            "net_name": net_name,
            "filepath": os.path.abspath(os.path.expanduser(filepath)),
            "filename": filename,
            "shapes": shapes_data,
            "polygons": polygons,
        }
    except (ValueError, OSError) as exc:
        print(f"Error building net record for {filepath}: {exc}")
        return None
```

Replace `import_shape_from_file` body to delegate:

```python
def import_shape_from_file(filepath: str, custom_net_name: str = None, yaml_source: str = None) -> Optional[dict]:
    return build_net_record(filepath, custom_net_name=custom_net_name, yaml_source=yaml_source)
```

Update `process_yaml_batch_import` loop:

```python
        yaml_source = shape_item.get("source") if isinstance(shape_item, dict) else None
        ...
        result = import_shape_from_file(filepath, custom_net_name, yaml_source=yaml_source)
        if result:
            imported_nets.append(result)
            print(f"Imported: {result['net_id']} from {result['filename']}")
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_net_import.py tests/test_net_identity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/data_parsing.py tests/test_net_import.py
git commit -m "feat: import pipeline returns composite net_id and source"
```

---

### Task 3: Wire composite keys in upload callbacks

**Files:**
- Modify: `app/callbacks.py`

- [ ] **Step 1: Add `_store_net_entry` helper (top of file, after imports)**

```python
from core.net_identity import (
    DEFAULT_SOURCE,
    derive_source_from_relative_path,
    make_net_id,
    parse_net_id,
    resolve_source,
    validate_source_or_net_name,
)
from core.data_parsing import build_net_record


def _store_net_entry(record: dict) -> tuple[str, bool]:
    """Store a parsed net record in app_state.nets_data. Returns (net_id, overwritten)."""
    net_id = record["net_id"]
    overwritten = net_id in app_state.nets_data
    app_state.nets_data[net_id] = {
        "source": record["source"],
        "net_name": record["net_name"],
        "filepath": record.get("filepath", ""),
        "filename": record["filename"],
        "shapes": record["shapes"],
        "polygons": record["polygons"],
    }
    return net_id, overwritten


def _record_from_uploaded_txt(decoded: str, filename: str, relative_path: str | None = None) -> dict | None:
    """Build net record from in-browser upload (no server filepath)."""
    parsed = parse_shape_txt(decoded, os.path.basename(filename))
    if not parsed:
        return None
    net_name, shapes_data, polygons = parsed
    if relative_path:
        source = derive_source_from_relative_path(relative_path)
    else:
        source = DEFAULT_SOURCE
    net_id = make_net_id(source, net_name)
    return {
        "net_id": net_id,
        "source": source,
        "net_name": net_name,
        "filepath": "",
        "filename": os.path.basename(filename),
        "shapes": shapes_data,
        "polygons": polygons,
    }
```

- [ ] **Step 2: Update `upload-data` branch in `update_net_selector`**

Replace direct `nets_data[net_name] = {...}` with:

```python
            imported = 0
            overwritten = 0
            for content, filename in zip(contents, filenames):
                try:
                    content_type, content_string = content.split(',')
                    decoded = base64.b64decode(content_string).decode('utf-8')
                    # filename may be "folder/shapes_xxx.txt" for folder uploads
                    rel = filename.replace("\\", "/") if filename else None
                    record = _record_from_uploaded_txt(decoded, filename, relative_path=rel)
                    if record:
                        _, ow = _store_net_entry(record)
                        imported += 1
                        if ow:
                            overwritten += 1
                except Exception as e:
                    print(f"Error importing {filename}: {e}")

            ...
            status = f"Imported {imported} files"
            if overwritten:
                status += f" ({overwritten} overwritten)"
```

- [ ] **Step 3: Update YAML upload branch**

Replace `nets_data[result['net_name']] = {...}` with:

```python
                    yaml_source = shape_item.get('source') if isinstance(shape_item, dict) else None
                    ...
                    result = import_shape_from_file(filepath, custom_net_name, yaml_source=yaml_source)
                    if result:
                        _, ow = _store_net_entry(result)
                        imported += 1
```

- [ ] **Step 4: Extend `_nets_meta_payload`**

```python
def _nets_meta_payload():
    names = sorted(app_state.nets_data.keys(), key=natural_sort_key)
    sources = sorted({d.get("source", "") for d in app_state.nets_data.values() if d.get("source")})
    return {'count': len(names), 'names': names, 'sources': sources}
```

- [ ] **Step 5: Update net-selector options labels**

Options already use `name` as label — composite IDs appear automatically. Verify sort uses `natural_sort_key` on full ID.

- [ ] **Step 6: Run existing tests**

Run: `python -m pytest tests/test_net_identity.py tests/test_net_import.py tests/test_full_review_callback.py -v`
Expected: PASS (fix `test_full_review_callback.py` if it asserts flat `net_name` key — update to use `result["net_id"]`)

- [ ] **Step 7: Commit**

```bash
git add app/callbacks.py tests/test_full_review_callback.py
git commit -m "feat: store nets_data under composite source/net_name keys"
```

---

### Task 4: Properties panel — Source + Net rows

**Files:**
- Modify: `app/layout.py`
- Modify: `app/callbacks.py`

- [ ] **Step 1: Add UI rows in `_create_right_panel` (replace single Name row)**

```python
                html.Div([
                    html.Span('ID:', className='prop-label'),
                    html.Span('--', id='prop-net-id', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Source:', className='prop-label'),
                    html.Span('--', id='prop-source', className='prop-value'),
                ], className='prop-row'),
                html.Div([
                    html.Span('Net:', className='prop-label'),
                    html.Span('--', id='prop-net-name', className='prop-value'),
                ], className='prop-row'),
```

- [ ] **Step 2: Update `_properties_panel_values` to return 13 fields**

```python
    def _properties_panel_values(selected_nets):
        empty = ['--'] * 13
        if not selected_nets or len(selected_nets) != 1:
            return tuple(empty)
        net_id = selected_nets[0]
        if net_id not in app_state.nets_data:
            return (net_id,) + tuple(empty[1:])
        try:
            source, net_name = parse_net_id(net_id)
        except ValueError:
            source, net_name = "--", net_id
        data = app_state.nets_data[net_id]
        ...
        return (
            net_id, source, net_name,
            str(len(shapes)), str(total_polys),
            resistance, capacitance, length,
            tau_rc, tpd,
            critical, warnings, info,
        )
```

- [ ] **Step 3: Add Outputs `prop-net-id`, `prop-source`; keep `prop-net-name`**

Update callback Output list and return tuple accordingly.

- [ ] **Step 4: Run app smoke test**

Run: `python3 -c "from layout_review_app import create_app; create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add app/layout.py app/callbacks.py
git commit -m "feat: properties panel shows composite net ID, source, and net name"
```

---

### Task 5: Folder upload UI + clientside callback

**Files:**
- Modify: `app/layout.py`
- Modify: `layout_review_app.py`

- [ ] **Step 1: Add folder picker below file upload in `_create_left_sidebar`**

```python
                html.Div([
                    html.Label([
                        html.Input(
                            id='upload-folder',
                            type='file',
                            **{'webkitdirectory': '', 'directory': ''},
                            multiple=True,
                            style={'display': 'none'},
                        ),
                        html.Span('+ Select Folder', className='tree-item'),
                    ], className='upload-area', style={'marginTop': '8px', 'cursor': 'pointer'}),
                ]),
                dcc.Store(id='folder-upload-store', data=None),
```

- [ ] **Step 2: Register clientside callback in `layout_review_app.py` inside `create_app()` after `register_callbacks(app)`**

```python
    app.clientside_callback(
        """
        function(n_clicks) {
            return window.dash_clientside.no_update;
        }
        """,
        Output('folder-upload-store', 'data'),
        Input('upload-folder', 'n_clicks'),
        prevent_initial_call=True,
    )
```

**Replace Step 2 with full FileReader clientside** (register before server callbacks):

```python
    app.clientside_callback(
        """
        function(files) {
            if (!files || files.length === 0) {
                return window.dash_clientside.no_update;
            }
            const readFile = (file) => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve({
                    contents: reader.result,
                    relativePath: file.webkitRelativePath || file.name,
                    filename: file.name,
                });
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
            return Promise.all(Array.from(files).map(readFile));
        }
        """,
        Output('folder-upload-store', 'data'),
        Input('upload-folder', 'contents'),
    )
```

Note: `html.Input type=file` does not expose `contents` in Dash — use **`dcc.Upload` with custom children** or switch to a small JS asset. **Pragmatic v1 fallback:** add second `dcc.Upload` labeled "Select Folder" and pass `filename` from browser; if path separator absent, document YAML for multi-folder workflows. **Preferred:** add `assets/folder_upload.js` + `dcc.Store` pattern.

**Implement via `assets/folder_upload.js`:**

```javascript
// assets/folder_upload.js
if (!window.dash_clientside) { window.dash_clientside = {}; }
window.dash_clientside.folder_upload = {
    pack_folder: function(_id) {
        const input = document.getElementById('upload-folder');
        if (!input || !input.files || !input.files.length) {
            return window.dash_clientside.no_update;
        }
        const files = Array.from(input.files).filter(f => f.name.endsWith('.txt'));
        if (!files.length) return [];
        return files.map(f => ({
            relativePath: f.webkitRelativePath || f.name,
            filename: f.name,
        }));
    }
};
```

Wire `Input('upload-folder', 'n_clicks')` is insufficient. **Use `dcc.Interval` polling or event listener** — simplest plan: **on `upload-folder` change, use Dash 2.14+ `dcc.Upload` duplicate with `directory` attribute via `html.Div` + manual JS in `layout_review_app.py` index_string**.

**Final v1 approach for plan:** Extend existing `upload-data` `dcc.Upload` to accept folder drag-drop by adding a parallel `dcc.Upload(id='upload-folder-data', ...)` and document that users click "Select Folder" which opens directory picker using:

```python
dcc.Upload(
    id='upload-folder-data',
    children=html.Div([html.Span('+ Select Folder', className='tree-item')], className='upload-area'),
    multiple=True,
    # Dash 2.17+ supports directory prop; if unavailable, filename from OS may include path on folder pick
)
```

Server callback adds second Input `upload-folder-data` contents/filename to same handler; `_record_from_uploaded_txt` uses `filename` as `relative_path` when it contains `/`.

- [ ] **Step 3: Add `upload-folder-data` Input to `update_net_selector`**

```python
        [Input('upload-data', 'contents'),
         Input('upload-folder-data', 'contents'),
         ...
        [State('upload-data', 'filename'),
         State('upload-folder-data', 'filename'),
```

Merge both upload paths in `upload-data` / `upload-folder-data` trigger branches (shared loop).

- [ ] **Step 4: Manual test checklist**

1. YAML import two paths under different parent dirs → two composite IDs in dropdown
2. Single file upload → `_default/<net>`
3. Folder upload (if supported in browser) → `parent/<net>`

- [ ] **Step 5: Commit**

```bash
git add app/layout.py app/callbacks.py layout_review_app.py
git commit -m "feat: folder upload control for source-aware net import"
```

---

### Task 6: Net filter hint + visualization title

**Files:**
- Modify: `app/layout.py`
- Modify: `core/visualization.py`

- [ ] **Step 1: Update net-filter placeholder**

```python
                    placeholder='Filter: ^report_32x128/ or trk_dbl_sa',
```

- [ ] **Step 2: Set figure title to composite IDs in `create_net_visualization`**

After building figure, before return:

```python
    title = ", ".join(selected_nets) if len(selected_nets) <= 3 else f"{len(selected_nets)} nets"
    fig.update_layout(title=title)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_visualization_directional.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/layout.py core/visualization.py
git commit -m "feat: show composite net IDs in filter hint and graph title"
```

---

### Task 7: Docs and examples

**Files:**
- Modify: `example_batch_import.yaml`
- Modify: `CLAUDE.md`
- Modify: `app/state.py`

- [ ] **Step 1: Add `source` examples to `example_batch_import.yaml`**

```yaml
  - file: "/path/report_32x128/shapes_trk_dbl_sa.txt"
  - file: "/path/report_32x64/shapes_trk_dbl_sa.txt"
    source: "sram_32x64"
```

- [ ] **Step 2: Add CLAUDE.md note under Data flow**

```markdown
- **Net identity:** `app_state.nets_data` keys are composite `source/net_name` (e.g. `report_32x128/trk_dbl_sa`). `source` is the file's parent directory or YAML `source:` override; browser single-file uploads use `_default`.
```

- [ ] **Step 3: Update `app/state.py` docstring for `nets_data`**

- [ ] **Step 4: Commit**

```bash
git add example_batch_import.yaml CLAUDE.md app/state.py
git commit -m "docs: document composite net source identity"
```

---

### Task 8: Collision + routing integration tests

**Files:**
- Create: `tests/test_net_collision.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_net_collision.py
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
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -q --ignore=tests/test_routing_pptx.py`
Expected: all pass

- [ ] **Step 3: Run ruff**

Run: `python -m ruff check core/net_identity.py core/data_parsing.py app/callbacks.py`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add tests/test_net_collision.py
git commit -m "test: composite net identity collision and source regex"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
|------------------|------|
| Composite key `source/net_name` | Task 1, 2, 3 |
| YAML `source:` override | Task 2, 3 |
| Auto parent-dir source | Task 1, 2 |
| Browser single-file → `_default` | Task 3 |
| Browser folder upload | Task 5 |
| Net filter regex on full ID | Task 3 (unchanged mechanism) |
| Properties Source/Net display | Task 4 |
| nets-meta-store sources list | Task 3 |
| Collision overwrite vs coexist | Task 3, 8 |
| Visualization/report labels | Task 6 |
| Tests | Task 1, 2, 8 |
| Docs | Task 7 |

## Deferred (per spec)

- Short-name regex fallback
- `source_depth` YAML option
- Separate source dropdown filter

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-21-net-source-identity.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — implement task-by-task in this session with checkpoints

Which approach do you want?