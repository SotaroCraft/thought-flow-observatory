# Operations

## Local smoke (M1)

```bash
uv sync
uv run thought-flow smoke
uv run pytest
```

Artifacts (default data root `workspace-data/`):

- `raw/content/<raw_content_identity>.parquet` — content-addressed, never overwritten
- `raw/runs/<run_identity>/<record_identity>.parquet` — per-run artifact
- `manifests/<run_identity>.json` — run evidence
- `catalog.duckdb` — local DuckDB catalog file

## Later runbooks

SPO setup, weekly differential runs, and Graph smoke procedures will be added in M2–M10. Until then, do not assume automation or cloud credentials are required for local core work.
