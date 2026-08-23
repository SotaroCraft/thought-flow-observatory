# Architecture

## Purpose

Describe how Thought Flow Observatory separates **local quantitative truth**, **Research Hub human surfaces**, and **optional cloud integrations**.

## High-level paths

### Quantitative observation (local-first)

```text
Public Sources → thin connectors → immutable Raw + run manifest
  → Methodology Gates → weekly Canonical → within-sensor analysis
  → Findings artifacts → (optional) SharePoint Current Findings
```

### Research Hub operations

```text
Public Source discovery → one-action Capture → SPO Sources
  → Copilot use → selective Promote → Research Cards
```

These paths cooperate but are **not** one pipeline. Local analysis must continue if SPO / Graph / BigQuery / Azure / Actions are unavailable.

## Component responsibilities (M1)

| Area | Responsibility | Authority |
|---|---|---|
| Local Raw | Immutable acquisition evidence (Parquet under local data root) | Local source of truth |
| Local Canonical | Weekly normalization (after M6 contract freeze) | Local source of truth |
| Local Analysis | Reproducible metrics (M8+) | Local primary path |
| SPO Research Hub | Capture, Copilot, selective Cards, Findings display | Human surface — not analysis SoT |
| Graph / Entra | Minimal SPO integration | Optional; manual fallback |
| BigQuery | Parity comparison | Required once; not primary store |
| Azure Blob / Foundry | Optional spikes | COULD after explicit adopt decision |

## M1 implemented boundary

- Package: `src/thought_flow/` with responsibility folders (`ingestion`, `normalization`, `analysis`, `integrations`, `publishing`, `observability`, `config`).
- Config: environment variables + `.env.example` (names / empty assignments only; defaults in code).
- CLI: `thought-flow smoke` proves config → run manifest → Raw persist → DuckDB query without external services.
- Identities: `run_identity` unique per execution; `record_identity` / `raw_content_identity` stable; `canonical_snapshot_identity` helper only (full Canonical waits for M6).
- Raw layers: content-addressed store holds payload only; per-run provenance artifacts reference content and keep run/record metadata separately.

## Explicit non-dependencies for local core

`integrations/` must not sit on the required import path for Raw → Canonical → Analysis. M1 smoke does not call SharePoint, BigQuery, or Azure.

## Related

- Requirements: `docs/requirements.md` §§5.1, 16.1, 17
- Plan: `implementation-plan.md` §§3, 6 (M1), 7
