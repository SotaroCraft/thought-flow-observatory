# Decision Records

Short Decision Records for TBDs and Methodology Gates live here.

M1 does not freeze sensor sources, dictionaries, country aggregation, or metrics.

| ID | Topic | Status |
|---|---|---|
| TBD-001 | Sensor source selection | Open (M5) |
| TBD-002 | Research Card MVP fields | Decided (M3) — see [`m3-hub-corpus-workflow.md`](m3-hub-corpus-workflow.md) |
| TBD-003 | Sources file vs link boundary | Decided (M3) — see [`m3-hub-corpus-workflow.md`](m3-hub-corpus-workflow.md) |
| TBD-004 | Captured / Used / Promoted representation | Decided (M3) — see [`m3-hub-corpus-workflow.md`](m3-hub-corpus-workflow.md) |
| TBD-005 | Graph / Entra auth, API permissions, admin consent | Decided (M4) — see [`m4-auth-interactive-browser.md`](m4-auth-interactive-browser.md); indexed by [`m2-external-readiness.md`](m2-external-readiness.md) |
| TBD-007 | Theme dictionary v1 | Open (M6 Gate D) |
| TBD-008 | Multi-country aggregation | Open (M6 Gate E) |
| TBD-009 | MVP metrics / thresholds | Open (M6 / pre-analysis) |
| TBD-011 | Azure Blob adopt/defer | M2 **NO-GO** / not adopted for current PoC — see [`m2-external-readiness.md`](m2-external-readiness.md); plan allows M10 reconsideration before optional Spike |
| TBD-012 | Azure AI Foundry adopt/defer | M2 **NO-GO** / not adopted for current PoC — see [`m2-external-readiness.md`](m2-external-readiness.md); plan allows M10 reconsideration before optional Spike |
| TBD-013 | Researcher / Analyst / Power Automate | Open (Trial period; not forced into M2) |
| TBD-014 | GitHub Actions migration / Secrets | Open (M10) |

## M2 records

| Document | Topic | Status |
|---|---|---|
| [`m2-external-readiness.md`](m2-external-readiness.md) | S1 Trial + M3 reuse; S3 closed by M4; S6 BigQuery access/cost readiness; S7 Azure NO-GO; AC-ANL-003 left for M9; AC-COST-001 unused path | Accepted |

## M5 records

| Document | Topic | Status |
|---|---|---|
| [`m5-sensor-preflight.md`](m5-sensor-preflight.md) | Sensor preflight (design) | External Review PASS |
| [`m5-smoke-spec.md`](m5-smoke-spec.md) | Bounded smoke specification (+ Erratum-001) | FROZEN |
| [`m5-sensor-decision.md`](m5-sensor-decision.md) | OpenAlex Phase 1 source decision record | OpenAlex Phase 1 recorded; **overall M5 source selection remains Open (TBD-001)** |
| [`m5-trends-transport-exception-proposal.md`](m5-trends-transport-exception-proposal.md) | Optional Explore/widget CSV transport exception | **PROPOSAL ONLY — not approved**; frozen smoke spec unchanged |

Trends acquisition ops (Transport A Human CSV; Transport B gated): [`docs/operations/m5-trends-acquisition.md`](../operations/m5-trends-acquisition.md). No Trends `SMOKE-PASS` / RF final / M6 freeze in that note.

## M3 records

| Document | Topic | Status |
|---|---|---|
| [`m3-hub-corpus-workflow.md`](m3-hub-corpus-workflow.md) | TBD-002〜004 from Human Hub reconfirm; Capture/Use/Promote primitives; future Agent automation out of scope | Accepted |

## M4 records

| Document | Topic | Status |
|---|---|---|
| [`m4-auth-interactive-browser.md`](m4-auth-interactive-browser.md) | Replace Device Code Flow with interactive browser + PKCE after AADSTS530035; live smoke PASS 2026-08-29; closes TBD-005 substance | Accepted / validated |
