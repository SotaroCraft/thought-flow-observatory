# Operations

## Local smoke (M1)

```bash
uv sync
uv run thought-flow smoke
uv run --frozen pytest -q
python scripts/public_safety_scan.py
```

Artifacts (default data root `workspace-data/`):

- `raw/content/<raw_content_identity>.parquet` — payload-only content object; never overwritten
- `raw/runs/<run_identity>/<record_identity>.parquet` — per-run provenance + content reference
- `manifests/<run_identity>.json` — run evidence
- `catalog.duckdb` — local DuckDB catalog file

## M3 / M4 (SharePoint / Graph)

- M3 Human reconfirm (existing Hub only): `docs/operations/m3-hub-reconfirm-checklist.md`
- M4 Graph SPO smoke: `docs/operations/m4-graph-spo-smoke.md`

```bash
uv sync --extra sharepoint
uv run thought-flow m4-graph-spo-smoke
uv run thought-flow m4-graph-spo-smoke --live
```

External credentials are never required for local M1 smoke or unit tests.

## Later runbooks

Weekly differential runs and further cloud procedures will be added in later milestones.
