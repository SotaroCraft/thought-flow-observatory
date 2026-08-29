# Cloud Comparison

## Status

**M2 external readiness recorded 2026-08-29.** See `docs/decisions/m2-external-readiness.md`.

| Area | M2 outcome | Later work |
|---|---|---|
| BigQuery | **Access / cost readiness PASS** (Human live smoke) | **Parity / AC-ANL-003 → M9** |
| Azure Blob / AI Foundry | **NO-GO for this PoC** (technically available; insufficient incremental value vs MUST path) | Plan allows M10 reconsideration before any optional Spike; no resources created |

BigQuery parity (identical/equivalent analysis + seven comparison dimensions + execution cost for **AC-ANL-003**) remains **OPEN** until M9 after a minimal DuckDB analysis contract exists.

## M2 — BigQuery access / cost readiness

Public-safe Human readiness smoke (first-time GCP user). **No** Project ID, Billing Account ID, or account identifiers are recorded.

| Check | Outcome |
|---|---|
| GCP Project selectable | YES |
| Billing linked / active | YES |
| $300 Credit available for validation | YES |
| BigQuery Studio opened | YES |
| Pre-execution processing / cost information visible | YES |
| Query | `SELECT 1 AS ok;` → SUCCESS (`ok = 1`) |
| Job / execution details accessible | YES |
| Bytes processed / billed or equivalent cost observation | YES |
| Dataset creation path visible | YES |
| Blocker | none |

**Plan tension (explicit):** `implementation-plan.md` lists AC-ANL-003 among M2 Acceptance Criteria IDs while assigning access checks to M2 and equivalent-query execution to M9. This document records **readiness only**; it does **not** claim AC-ANL-003 closed.

## M2 — Azure optional branches

| Check | Outcome |
|---|---|
| Subscription usable | YES |
| Budget / Cost Alert configurable | YES |
| Azure AI Foundry available | YES |
| Azure Blob available | YES |
| Incremental value outranks Local + SPO + BigQuery MUST path | NO |
| Decision | **NO-GO** (not an availability failure) |
| Resources created | NO |

**AC-COST-001 (unused path):** Non-adoption reason recorded — Azure is available but not adopted because incremental PoC value does not justify diverting effort from the MUST path. No Azure AI API usage.

## Comparison dimensions (required when M9 parity is executed)

1. Implementation ease
2. Query compatibility
3. Performance (with data volume stated)
4. Scale adaptability
5. Cost
6. Operational load
7. Fit for this PoC

## Guardrails

- GCP is **not** the primary store and **not** used for AI processing.
- Local DuckDB + Parquet remains the quantitative source of truth.
- Azure AI Foundry initial budget cap: ¥1,000 (if used). Unused under current NO-GO.
- Do not commit GCP Project IDs, Billing Account IDs, Azure Subscription IDs, or account identifiers.

## Related

- Requirements: `docs/requirements.md` §§14.2–14.3, 18; AC-ANL-003; AC-COST-001
- Plan: `implementation-plan.md` §§5.1 (S6–S7), 6 (M2, M9, M10), 9.2, 14
- Decision: `docs/decisions/m2-external-readiness.md`
