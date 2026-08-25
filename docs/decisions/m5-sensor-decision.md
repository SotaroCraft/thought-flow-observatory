# M5 Sensor Decision Record — OpenAlex Phase 1

- Status: OpenAlex Phase 1 **decision record** (Cursor-recommended). Not production `GO`. Not RF final.
- Date: 2026-08-26
- Source of Truth: `docs/requirements.md` v1.0; frozen `implementation-plan.md` v1.0; `docs/decisions/m5-sensor-preflight.md`; `docs/decisions/m5-smoke-spec.md` (FROZEN + Erratum-001); `AGENTS.md`.
- Scope: Close the M5 Decision layer for the **OpenAlex** Research Sensor primary candidate after Phase 1 implementation merged to `main`. Does **not** implement further sensors, network fetch, RF final decision, or M6 Gate A–E freeze.
- Normative M5 result vocabulary: §1 of [`m5-smoke-spec.md`](m5-smoke-spec.md). Artifact / RF / handoff alignment: §§11–13 of that specification.

This record stores public-safe aggregates, limitations, a recommended OpenAlex M5 result, RF boundary state, M6 handoff pointers, and reacquisition instructions. Live Raw payloads are **not** stored in the public repository.

---

## 1. OpenAlex candidate identity

| Field | Value |
|---|---|
| Sensor | Research |
| Candidate | OpenAlex Works API (`GET /works`) |
| Candidate role | Research Sensor **primary candidate** (preflight; unchanged by this record) |
| Implementation state | Phase 1 bounded smoke implementation **merged** |
| Reviewed implementation commit | `9fbe14f53846e915d09352e0a20f178fa2c53e96` |
| `main` integration | `933134037841640304d14a1524a4afc2e85faa0e` |
| Pull request | [#2](https://github.com/SotaroCraft/thought-flow-observatory/pull/2) — *M5 OpenAlex Phase 1 — bounded smoke + Erratum-001* |
| Smoke vocabulary | `PROVISIONAL-M5-SMOKE/2026-08-23-r1` (`config/smoke/provisional_m5_smoke_2026_08_23_r1.json`) |
| Fixed periods | `OA-START` (2022-11-30–2022-12-04), `OA-MID` (2024-10-07–2024-10-13), `OA-RECENT` (2026-08-10–2026-08-16) |

---

## 2. Smoke evidence summary (reviewed, public-safe)

Repository-confirmable reviewed evidence for the authenticated bounded live smoke includes Program Memory on [Issue #1](https://github.com/SotaroCraft/thought-flow-observatory/issues/1), merge of PR #2, Erratum-001 in [`m5-smoke-spec.md`](m5-smoke-spec.md), and unit tests under `tests/unit/test_m5_*.py`. **Live privacy-reduced Raw is not present in the public repository.**

| Evidence item | Reviewed state |
|---|---|
| Authenticated bounded live smoke | Completed successfully |
| Country × theme × period cells | 24 |
| Country × period denominators | 12 |
| Global theme × period audits | 6 |
| Total evidence units | 42 |
| `fetch_failure` | 0 |
| Request / cost ceiling | Completed within frozen OpenAlex ceilings (512 HTTP attempts; USD 0.75 / documented free-budget fraction) |
| Persistence | Privacy-reduced Raw envelopes only; author / person fields not retained |
| Country rule | No name / language / LLM country inference; structured authorship countries retained; `unknown` / multi-country preserved |
| Primary theme classifier | Deterministic `PROVISIONAL-M5-SMOKE` on title / reconstructed abstract — **not** OpenAlex topics as primary |
| Original live Raw | Immutable (append-only under unique run); not overwritten by Erratum-001 |
| Erratum-001 derived evidence | Versioned separately from original Raw / query / provenance |
| Unit tests at reviewed exit | **53 passed** |
| Public-safety scan at reviewed exit | **CLEAN** |
| CodeX Phase 1 exit | **M5 OPENALEX PHASE 1 EXIT: PASS** |

### Limitations (explicit)

1. **Live Raw is not in the public repository.** Reacquisition or a Human-held local evidence path is required to inspect privacy-reduced envelopes, per-cell coverage rows, or HTTP attempt logs from the live run.
2. Smoke retention / page / inspect ceilings intentionally produce `partial` observations where an unobserved remainder exists; smoke counts are **not** a full-population extract.
3. `PROVISIONAL-M5-SMOKE` is smoke-only and is **not** Gate D v1.
4. Human stratified provisional match review samples (§4 of the smoke spec) are **UNKNOWN** in this public record (not packaged as a normative public artifact here).
5. Public numeric rates for abstract coverage, `unknown` country share, and multi-country share from the live run are **UNKNOWN** in this public record (aggregates not published without live Raw).
6. This record does **not** decide OpenAlex production adoption, RF final state, or any M6 Gate.

---

## 3. Erratum-001

Normative patch recorded in [`m5-smoke-spec.md`](m5-smoke-spec.md) (Erratum-001). Implementation landed in reviewed commit `9fbe14f`.

| Patch | Effect |
|---|---|
| Complete observation + ≥1 qualifying result | Primary quality state `success` |
| Complete observation + zero qualifying results | `zero` (unchanged meaning) |
| Bounded ceiling / unobserved remainder | `partial` |
| Attribute absence / N/A | `missing` (not a generic success label) |
| Unresolvable allowed attribute | `unknown` |
| Acquisition failure | `fetch_failure` |
| Unknown source-reported cost | `reported_cost_usd = null` (must **not** coerce to `0.0`) |
| Original evidence | Not overwritten; derived evidence versioned separately |
| M6 Gate A–E | **Unchanged / not frozen** by Erratum-001 |

---

## 4. Recommended M5 result (OpenAlex)

| Field | Value |
|---|---|
| **Recommended M5 result** | **`SMOKE-PASS-WITH-LIMITATIONS`** |
| Production `GO` | **NOT DECIDED** (must not be read as `GO`) |
| Reason codes | `mechanical_smoke_complete`; `fetch_failure_zero`; `privacy_reduced_persistence`; `no_country_inference`; `provisional_vocabulary_only`; `live_raw_not_in_public_repo`; `bounded_ceiling_partial_cells`; `erratum001_applied` |
| Reviewer / approval state | Cursor recommendation recorded. Human / Codex own source adoption and RF final (§1 / §12 of smoke spec). |
| Why not `SMOKE-NO-GO` | Mandatory cells completed with `fetch_failure = 0`; documented schema / start boundary / privacy and no-inference boundaries held under review. Sparse / valid zero alone is not no-go (§5.4). |
| Why not bare `SMOKE-PASS` | Publication restriction (no public live Raw) and smoke-ceiling / coverage semantics constrain later use; limitations above must remain explicit (§1 `SMOKE-PASS-WITH-LIMITATIONS`). |
| Why not `SMOKE-BLOCKED` | Authenticated live smoke ran; entitlement was not absent for the completed Phase 1 path. |

OpenAlex remains eligible for M6 **consideration** only; Gate A–E are not frozen by this result.

---

## 5. RF boundary

| Field | Value |
|---|---|
| **RF PASSED** | **NO** |
| Final RF state (`PASS` / `BLOCKED` / `INCONCLUSIVE`) | **UNDETERMINED** — not recorded as Human / Codex final in repository SoT |
| Separation | OpenAlex Phase 1 provides **RF candidate evidence**. That is distinct from an RF final decision (§12). |
| Documentation alone | Insufficient for RF PASS (§12). |
| M7 | Not authorized by this record. |

Cursor notes (non-binding): Phase 1 produced terminal outcomes for the OpenAlex sentinel matrix under frozen ceilings, with structured country evidence and provisional theme matching. Remaining RF closure items include Human review of RF evidence (§14.8), any required provisional vocabulary review samples, and packaging of local coverage evidence that is not public. Those gaps keep final RF **UNDETERMINED**, not silently `PASS`.

---

## 6. M6 handoff package (evidence only; Gates unfrozen)

M5 supplies evidence; it does **not** decide any Gate ([`m5-smoke-spec.md`](m5-smoke-spec.md) §13). **M6 GATE A–E FROZEN: NO.**

| Gate | OpenAlex evidence available from Phase 1 (summary) | Gate decision |
|---|---|---|
| **A** — unit / population / denominator | Distinct Work IDs under privacy-reduced persistence; country × period denominator requests (12) with source-reported totals; theme cells with inspected / retained / matched counts; intentional `partial` under ceilings with unobserved remainder | **Not frozen** |
| **B** — proxy | Observed object = indexed scholarly **Works** via OpenAlex. Proxy is **not** authors, citations, social diffusion, or a social layer. Limitations: affiliation / abstract coverage unevenness (rates **UNKNOWN** publicly here); smoke sample ≠ full extract | **Not frozen** |
| **C** — time | Fields retained in allowlist path: `publication_date` / `publication_year`, `created_date`, `updated_date`, plus local `observed_at` / `ingested_at`. Semantics remain candidate evidence for Gate C, not Canonical time freeze | **Not frozen** |
| **D** — vocabulary | Multilingual `PROVISIONAL-M5-SMOKE/2026-08-23-r1` applied locally to title / reconstructed abstract; OpenAlex topics not primary. **Not Gate D v1**; replaceable by M6 | **Not frozen** |
| **E** — country | Structured authorship countries / institution `country_code` path; multi-country retention; missing / `unknown` preserved; **no** name / language / LLM inference | **Not frozen** |

Unresolved for M6 (remain open): public packaging of live coverage tables; Human provisional review sample outcomes; acceptability thresholds for abstract / `unknown` / imbalance (M5 must not invent them).

---

## 7. Reacquisition (public-safe)

Do **not** store API key values, account IDs, or live Raw in the repository or this record.

| Item | Public-safe reference |
|---|---|
| CLI | `thought-flow m5-smoke-openalex --live` |
| Diagnostic only (not formal SMOKE-PASS) | `thought-flow m5-smoke-openalex --live --diagnostic-cell` |
| Credential env **name** only | `THOUGHT_FLOW_OPENALEX_API_KEY` (see `.env.example`; value stays local / uncommitted) |
| Data root env **name** | `THOUGHT_FLOW_DATA_ROOT` (gitignored local workspace) |
| Vocabulary config | `config/smoke/provisional_m5_smoke_2026_08_23_r1.json` → version `PROVISIONAL-M5-SMOKE/2026-08-23-r1` |
| Periods | `OA-START`, `OA-MID`, `OA-RECENT` as in `src/thought_flow/smoke/periods.py` / smoke spec §2.1 |
| Countries / themes | `JP`, `US`, `KR`, `CN` × `generative_ai`, `ai_agent` |
| Erratum-001 derived regen (no refetch) | `python -m thought_flow.smoke.openalex.regenerate_erratum001 --run-dir <local-runs>/<run_id>` |
| Synthetic public fixture | `data/samples/m5_openalex_synthetic_work.json` |

---

## 8. Related artifacts (links)

- Preflight: [`m5-sensor-preflight.md`](m5-sensor-preflight.md)
- Smoke specification (+ Erratum-001): [`m5-smoke-spec.md`](m5-smoke-spec.md)
- Decisions index: [`README.md`](README.md)
- Merge: [PR #2](https://github.com/SotaroCraft/thought-flow-observatory/pull/2)
- Program Memory: [Issue #1](https://github.com/SotaroCraft/thought-flow-observatory/issues/1)

---

## 9. Self-check

- [x] Recommended OpenAlex M5 result uses frozen vocabulary only.
- [x] Production `GO` not asserted.
- [x] **RF PASSED: NO**; final RF state left **UNDETERMINED**.
- [x] **M6 Gate A–E FROZEN: NO**.
- [x] `PROVISIONAL-M5-SMOKE` not promoted to Gate D v1.
- [x] Live Raw / secrets / account values absent from this record.
- [x] TBD-001 (overall sensor source selection) remains Open at program level.

M5 OPENALEX DECISION RECORD STATUS: READY FOR HUMAN / CODEX REVIEW
