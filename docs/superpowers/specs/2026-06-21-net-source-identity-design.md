# Net Source Identity — Design Spec

**Date:** 2026-06-21  
**Status:** Approved (brainstorming)  
**Scope:** Layout View tab — file/YAML import, net selection, downstream engine & routing  
**Problem:** Shape files with identical names from different folders overwrite each other in `app_state.nets_data`.

---

## Background

Today `nets_data` is keyed only by net name parsed from the filename (`shapes_trk_dbl_sa.txt` → `trk_dbl_sa`). Importing the same filename from `report_32x128/` and `report_32x64/` causes silent data loss. The filepath is stored in metadata but does not participate in identity. Net filter regex and Routing Config batch/golden regex both resolve against flat net names.

Typical batch layout review loads multiple design variants (e.g. 32×128 vs 32×64) that share shape filenames but represent different physical layouts.

---

## Goals

1. Coexistence of same `net_name` under different `source` values without collision.
2. Canonical net identity is a composite ID: `source/net_name`.
3. `source` is assigned automatically from the file path (immediate parent directory) **or** explicitly in YAML.
4. Net Selection filter regex matches the composite ID (full string).
5. Browser upload supports folder selection (relative path → source) and single-file fallback.

## Non-Goals

- Short-name regex fallback (matching `trk_dbl_sa` across all sources) in v1.
- Multi-level source paths (e.g. `report_32x128/run1`); v1 uses **immediate parent directory only**.
- Changing the shape file format or PDK rules.
- Redesigning the Routing Review metric engine.

---

## Decisions (Brainstorming Outcomes)

| Question | Decision |
|----------|----------|
| How is `source` assigned? | **A+B:** auto from path parent dir; YAML `source:` overrides |
| Canonical identity | **A:** composite key `source/net_name` |
| Browser single-file upload | Fallback `source = _default` |
| Browser folder upload | **C:** `webkitdirectory` / relative path → immediate parent as source |
| Source path depth | **A:** immediate parent directory only |
| Default source name | `_default` |
| v1 regex | Full composite ID only (no short-name fallback) |

---

## Data Model

### `nets_data` entry

```python
# Dict key = net_id = "source/net_name"
nets_data[net_id] = {
    "source": "report_32x128",
    "net_name": "trk_dbl_sa",
    "filepath": "/abs/path/report_32x128/shapes_trk_dbl_sa.txt",
    "filename": "shapes_trk_dbl_sa.txt",
    "shapes": {...},
    "polygons": [...],
}
```

### Helper module (`core/net_identity.py`)

| Function | Behavior |
|----------|----------|
| `make_net_id(source, net_name) -> str` | Returns `f"{source}/{net_name}"`; rejects `/` in either part |
| `parse_net_id(net_id) -> tuple[str, str]` | Splits on first `/`; raises on invalid |
| `derive_source_from_path(filepath) -> str` | `os.path.basename(os.path.dirname(os.path.abspath(filepath)))` |
| `resolve_source(filepath, yaml_source=None) -> str` | YAML explicit wins; else derive from path; empty → `_default` |

### Collision rules

- Re-importing the same `source/net_name` **overwrites** the existing entry; upload status shows a warning count.
- Different `source` + same `net_name` → **two distinct** entries.

### `nets-meta-store` payload

```python
{
    "count": 2,
    "names": ["report_32x128/trk_dbl_sa", "report_32x64/trk_dbl_sa"],
}
```

Optional v1 extension (same store): `"sources": ["report_32x128", "report_32x64"]` for Routing Config hints.

---

## Source Assignment Rules

| Import path | `source` resolution |
|-------------|---------------------|
| YAML with `source:` field | Use YAML value (highest priority) |
| YAML / local file path, no `source` | `derive_source_from_path(filepath)` |
| Browser folder upload (`webkitRelativePath`) | Parent dir of relative path |
| Browser single-file upload | `_default` |

### YAML example

```yaml
import_mode: batch
options:
  clear_existing: false
shapes:
  - file: "/data/report_32x128/shapes_trk_dbl_sa.txt"
    # source auto → report_32x128
  - file: "/data/report_32x64/shapes_trk_dbl_sa.txt"
    source: "sram_32x64"   # explicit override
  - file: "/data/shapes_wl0.txt"
    net_name: "WL0"
    source: "golden"
```

### Sanitization

- Strip leading/trailing whitespace from `source`.
- Replace empty or `.` parent with `_default`.
- Reject `source` or `net_name` containing `/` (raise clear import error).

---

## UI Changes (Layout View)

### File Import

1. **Select Files** (existing) — unchanged UX; all nets land under `_default/<net_name>`.
2. **Select Folder** (new) — `html.Input(type="file", webkitdirectory=True, multiple=True)` or Dash Upload wrapper; callback reads relative paths from `filename` state (browser may supply `folder/file.txt` despite Dash docs saying pathless — verify at implementation; fallback: clientside callback to capture `webkitRelativePath`).

Upload status shows: `Imported 3 files → 2 sources (report_32x128, report_32x64)`.

### Net Selection

- Dropdown `label` and `value`: full composite ID (`report_32x128/trk_dbl_sa`).
- `net-filter` regex: unchanged mechanism (`re.compile(filter_text).search(net_id)`).
- Placeholder hint: `e.g. ^report_32x128/ or trk_dbl_sa$`.

### Properties panel

- Show `Source` and `Net` as separate read-only rows (parsed from selected composite ID), or single row `ID: report_32x128/trk_dbl_sa`.

---

## Downstream Impact

| Module | Change |
|--------|--------|
| `app/callbacks.py` | Build composite keys on upload; pass `net_id` to engine |
| `core/data_parsing.py` | `import_shape_from_file` returns `source`, `net_id`; YAML parses `source` |
| `app/state.py` | Docstring: keys are `net_id` |
| `review_engine` | Uses `net_id` as net key throughout (no API rename required if already string keys) |
| `app/routing_config.py` | Regex preview / examples use composite IDs |
| `app/routing_review.py` | `_resolve_regex` unchanged logic, new name set |
| `core/visualization.py` | Plot title / legend: `source/net_name` |
| `report/*` | Slide/table headers show composite ID |

### Backward compatibility

- Existing sessions with flat names: **breaking change** — users re-import or update regex to `_default/<net>` or `^.*/<net>$`.
- YAML `net_name` override still sets the **net_name portion** only; `source` assigned per rules above.
- YAML `auto_prefix` applies to `net_name` before `make_net_id` (unchanged semantics, now scoped per source).

---

## Error Handling

| Case | Behavior |
|------|----------|
| Invalid `/` in source or net_name | Skip file; status error line |
| Duplicate `source/net_name` on re-import | Overwrite + increment `overwritten` counter in status |
| Folder upload with flat filenames (no path separator) | Treat as `_default` |
| Missing file in YAML | Existing `skip_missing` behavior |

---

## Testing

New tests in `tests/test_net_identity.py`:

1. `make_net_id` / `parse_net_id` round-trip
2. `derive_source_from_path` — parent dir extraction
3. `resolve_source` — YAML override beats path
4. Import two identical filenames, different parents → two keys in `nets_data`
5. Re-import same path → overwrite, count unchanged
6. Net filter `^report_32x128/` returns only that source's nets
7. Routing `_resolve_regex(r"^report_32x64/trk_dbl_sa$")` → single match

Integration: extend `tests/test_data_parsing.py` or callback fixture for YAML `source` field.

---

## Implementation Phases (for writing-plans)

1. **Core identity** — `core/net_identity.py` + unit tests
2. **Import pipeline** — `data_parsing.py`, `callbacks.py` upload paths
3. **UI** — folder upload control, properties source/net rows, filter hint
4. **Downstream** — routing examples, visualization titles, report labels
5. **Docs** — update `example_batch_import.yaml`, CLAUDE.md one-liner

---

## Open Items (Deferred)

- Short-name regex fallback (`trk_dbl_sa` matches all sources)
- Configurable `source_depth` in YAML
- Source filter dropdown separate from net-name regex