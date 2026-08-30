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

## M5 OpenAlex / Trends (smoke only)

- OpenAlex: `uv run thought-flow m5-smoke-openalex --live`
- Trends acquisition (Human CSV import; no UI automation): `docs/operations/m5-trends-acquisition.md`

```bash
uv run thought-flow m5-trends-alpha-status
uv run thought-flow m5-trends-csv-import --country US --csv data/samples/m5_trends_ui_synthetic_us.csv --observation-index 1
```

Trends live Raw/CSV evidence remains under gitignored `workspace-data/` unless a frozen licensing decision permits publication.

## M7 OpenAlex backfill campaign

Operational partitions are `country × publication date` (not ISO week Canonical buckets).

Dry-run (default — no network, no Raw/checkpoint writes):

```bash
uv run thought-flow m7-openalex-backfill-campaign --run-end-date 2026-08-30
```

Bounded live campaign (explicit country + date range required). Full-window live
(`JP+US+KR+CN` × `2022-11-30`…run-end) is refused; use dry-run for the full plan:

```bash
uv run thought-flow m7-openalex-backfill-campaign --live --country JP --from-date 2022-12-01 --to-date 2022-12-02
```

Resume uses existing checkpoints under `workspace-data/manifests/openalex_backfill/checkpoints/`. Completed `success` / `zero` partitions are skipped. Artifacts stay outside Git.
