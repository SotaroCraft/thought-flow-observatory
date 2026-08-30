# M7 OpenAlex Completion Contract (TFO-M7-017-PC1)

- Status: **Program Control frozen** (2026-08-30) via TFO-M7-016 acceptance + TFO-M7-017-PC1
- Scope: OpenAlex production Raw backfill completion rules and daily cost hard stop
- Does **not** authorize M8 analysis or Trends production connector implementation

## OpenAlex acquisition window

| Item | Frozen value |
|---|---|
| Inclusive start | `2022-11-30` |
| Inclusive end | `2026-08-30` |
| Expected daily partitions per country | **1,370** |
| Countries | JP, US, KR, CN |
| Acquisition identity | country × publication-date Works |
| Theme filtering at Raw | **No** (themes applied later via `THEME-DICT/v1`) |
| Raw behavior | append-only |
| Stage policy | calendar quarter; short remainder periods only |
| US canary | Resume existing `2022-12-01` partial (cursor resume; no restart) |
| JP remaining | `2026-01-01..2026-08-30` (242 days) still required for M7 completion |

## Daily cost hard stop

| Item | Frozen value |
|---|---|
| Ceiling | **`$1.00` USD per UTC calendar day** |
| Billable attempt unit (projection / fallback accounting) | `$0.0001` (`OPENALEX_BILLABLE_ATTEMPT_COST_USD`) |
| Enforcement | **Pre-request** (before HTTP); never post-hoc-only |
| Aggregation | Across campaigns / countries / retries sharing the same credential + UTC day |
| Durability | Persistent ledger under `workspace-data/manifests/openalex_backfill/daily_cost_ledger/` |
| Unknown cost | Fail closed; never coerce unknown to zero |
| Automatic purchase / paid overage | **Prohibited** |

### Stop semantics

- **Between dates:** preserve completed dates; leave the next date **unattempted**; no false partial journal for an untouched day.
- **Within a date:** preserve completed pages; nonterminal partial; `exhausted=false`; retain `next_cursor`; failure category `daily_cost_ceiling`; governed resume on a later UTC day.
- Must **not** classify incomplete coverage as `success` or `source_count_mismatch`.

## Google Trends (recorded; not implemented by this change)

| Item | Frozen value |
|---|---|
| Transport A smoke | Does **not** count as production Raw |
| Official alpha API | Unavailable until entitlement evidenced |
| Authorized future route | Bounded UI CSV (Human) |
| Inclusive end | `2026-08-16` (`TRENDS_FULL`) |
| Reproducibility | Minimum **two** identical-setting captures with separated provenance |
| Production connector | Remains an M7 capability blocker until a later order |

## M8

Still blocked. TBD-009 Dynamics metrics and numeric lead/lag width remain unresolved. No M8 analysis is authorized by this record.

## Implementation pointer

- Guard / ledger: `src/thought_flow/ingestion/openalex/daily_cost_ledger.py`
- HTTP pre-request hook: `SmokeHttpClient.daily_cost_guard`
- Production wiring: `production_openalex_client` / campaign dry-run summary fields
