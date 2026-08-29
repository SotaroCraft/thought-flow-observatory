# M2 — Deadline-dependent External Readiness

| Field | Content |
|---|---|
| Date | 2026-08-29 |
| Status | Accepted (Human evidence + M3/M4 reuse) |
| Milestone | M2 Deadline-dependent External Readiness |
| Related | §§14.1–14.3, 17.3, 18; FR-INT-001〜006; AC-M365-001〜003; AC-ANL-003 (readiness only); AC-COST-001; TBD-005, TBD-011〜014; `docs/m365-validation.md`; `docs/cloud-comparison.md` |

## Context

M2 surfaces blocking conditions around M365 Trial / Copilot, Graph / Entra, BigQuery access / cost, and Azure budget / availability before later milestones depend on them. M3 and M4 already closed Hub / Copilot and Graph connectivity. This record closes M2 with Human Trial, BigQuery readiness, and Azure NO-GO evidence without reopening M3/M4 or pulling M9 parity / M10 Azure implementation forward.

## S1 — M365 Trial / Copilot readiness

**Verdict:** PASS (readiness)

| Item | Public-safe outcome |
|---|---|
| Trial / environment usable through 2026-09-20 | **YES** |
| Material Trial constraint beyond documented M3 limitations | **NO** |
| Functional evidence | **Reused from M3** — SPO Research Hub usable; Copilot usable; Capture → Use → selective Promote demonstrated |

Do **not** treat this as a re-run of Hub surfaces or Copilot demos. See `docs/m365-validation.md` §M3 and `docs/decisions/m3-hub-corpus-workflow.md`.

Researcher / Analyst / Power Automate remain **TBD-013** (not forced into M2).

## S3 — Graph / Entra readiness

**Verdict:** PASS (closed by M4)

| Item | Public-safe outcome |
|---|---|
| Auth | Delegated interactive browser + PKCE |
| Security Defaults | Preserved |
| Live smoke | Bounded Graph / SPO read succeeded |
| Manual fallback | Preserved |
| Retest in M2 | **NO** |

Evidence: `docs/m365-validation.md` §M4; `docs/decisions/m4-auth-interactive-browser.md`; `docs/operations/m4-graph-spo-smoke.md`.

**TBD-005** (Graph / Entra auth method, API permissions, admin consent) is **decided** by the accepted M4 auth decision. PnP / other admin tooling remains **TBD-006** if Graph later proves insufficient.

## S6 — BigQuery access / cost readiness

**Verdict:** PASS (access / cost readiness only)

Human first-time GCP bounded readiness smoke (public-safe outcomes only):

| Check | Outcome |
|---|---|
| GCP Project selectable | YES |
| Billing linked to Project | YES |
| Billing account active / not stopped | YES |
| $300 Credit available for validation | YES |
| BigQuery Studio opened | YES |
| Pre-execution processing / cost information visible | YES |
| Query smoke | `SELECT 1 AS ok;` → **SUCCESS** (`ok = 1`) |
| Job / execution details accessible | YES |
| Bytes processed / billed or equivalent cost observation | YES |
| Create dataset path visible | YES |
| Blocker | **none** |

**Boundary:** This proves M2 BigQuery **access / cost readiness** only.

- **AC-ANL-003 remains OPEN** for **M9**.
- DuckDB ↔ BigQuery equivalent analysis and the seven comparison dimensions are **not** closed here.
- Plan tension (recorded, not silently resolved): `implementation-plan.md` lists AC-ANL-003 under M2 Acceptance IDs while assigning access checks to M2 and equivalent-query / parity execution to M9. M2 contributes readiness evidence only; final AC-ANL-003 closure is M9.

No GCP Project ID, Billing Account ID, account email, or other private identifiers are recorded.

## S7 — Azure budget / availability

**Verdict:** **NO-GO** for this PoC (not an availability failure)

| Check | Outcome |
|---|---|
| Azure Subscription usable | YES |
| Budget / Cost Alert can be configured | YES |
| Azure AI Foundry available | YES |
| Azure Blob available | YES |
| Incremental value outranks Local + SPO + BigQuery MUST path | **NO** |
| M2 decision | **NO-GO** |
| Azure resources created | **NO** |

**Interpretation:** Azure is technically available and budget controls are feasible, but is intentionally **not adopted** because incremental PoC value does not justify diverting effort from the MUST path (Local + SPO + BigQuery readiness).

**AC-COST-001 (unused path):** Satisfied by this explicit non-adoption reason. No Azure AI API usage; no ¥1,000 usage ledger required while unused.

**TBD-011 (Azure Blob)** / **TBD-012 (Azure AI Foundry):** M2 records **NO-GO / not adopted for the current PoC**. Per plan Gate Decision Table (`implementation-plan.md` §9.2), Azure TBDs are preliminary in M2 with final freeze before optional Spike / M10 — reconsideration remains possible then if MUST progress and value change; M2 does **not** authorize Blob or Foundry implementation.

## Acceptance Criteria mapping (M2 contribution only)

| AC | M2 contribution | Final closure |
|---|---|---|
| AC-M365-001 | Cite / reuse M4 | **M4** (already closed) |
| AC-M365-002 | Trial usability through 2026-09-20 + M3/M4 Validation Log entries for adopted candidates | Ongoing for later Trial candidates (TBD-013); core Hub/Copilot/Graph logged |
| AC-M365-003 | Reference only — local-core independence established in M1 / architecture | Not newly proven in M2 |
| AC-ANL-003 | Access / billing / cost-observation readiness only | **M9** — remains OPEN |
| AC-COST-001 | Unused Azure path + explicit NO-GO reason | Satisfied for unused path by this record |

## Non-goals

- Reopening or re-running M3 Hub / Copilot demos
- Reopening M4 Graph smoke or expanding Graph permissions
- BigQuery client code, parity SQL, or seven-dimension comparison (M9)
- Azure resource creation or optional-branch implementation (M10 only if reconsidered)
- Researcher / Analyst / Power Automate trials (TBD-013)
- GitHub Actions (TBD-014)
- Committing tenant, subscription, project, billing, or account identifiers

## Exit Gate

SPO / Copilot / Graph / BigQuery execution paths are documented with public-safe evidence (or clear blockers — none for S6). Azure optional branch is **NO-GO** for this PoC with rationale. M2 Exit Gate: **satisfied** pending CodeX Review Gate.
