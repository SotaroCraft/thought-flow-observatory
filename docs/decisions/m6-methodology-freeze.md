# M6 Methodology Gates A–E + Data Contract Freeze

- Status: **FROZEN — Human approved** (`承認`, 2026-08-29). Gates A–E including TBD-008 inclusion counting are frozen. M5 `RF PASS WITH LIMITATIONS` (delegated vocabulary review sufficient for RF #6 WITH LIMITATION) accepted as part of the same bounded approval.
- Management ID: **TFO-M6-001**
- Date: 2026-08-29
- Base commit (branch start): `a9a3a7befcc741f8e54f3ede595acab80d9b0650`
- Source of Truth: `docs/requirements.md` v1.0; frozen `implementation-plan.md` v1.0; M5 smoke-spec (+ Errata); [`m5-narrow-closeout.md`](m5-narrow-closeout.md); [`m5-openalex-vocabulary-review.md`](m5-openalex-vocabulary-review.md); `AGENTS.md`.
- Machine-readable companion: [`config/rules/m6_gate_contracts_v1.json`](../../config/rules/m6_gate_contracts_v1.json)
- Theme dictionary: [`config/themes/theme_dict_v1.json`](../../config/themes/theme_dict_v1.json) (`THEME-DICT/v1`)

This record freezes the **minimum** scientifically defensible methodology for OpenAlex + Google Trends Transport A so M7 Raw backfill and M8 Canonical Finding can proceed **without** importing M5 smoke ceilings, deferred sensors, or exploratory preview machinery.

**Does not implement M7/M8 in this milestone.** Does **not** start backfill, analysis, Obs2, Transport B, Company, GitHub, or arXiv methodology.

---

## 1. Canonical architecture

| Decision | Value |
|---|---|
| Model | **Separate sensor-specific Canonical datasets** |
| Cross-sensor comparison | **Analysis layer only** (descriptive) |
| Merged cross-sensor measurement table / index | **MUST NOT** |
| Shared numerical scale | **MUST NOT** |
| Shared metadata / identity concepts | Allowed (sensor, week, theme, country/unknown, rule versions, quality counts) |

OpenAlex measures (counts / shares against an observable denominator) and Trends measures (0–100 within-request relative interest) are incommensurable. They MUST NOT be numerically merged.

---

## 2. Gate A — Unit / Population / Denominator

### 2.1 OpenAlex (FROZEN)

| Element | Contract |
|---|---|
| Unit identity | OpenAlex **Work ID** |
| Deduplication | Deterministic by Work ID for repeated observations of the same Work |
| Theme counting | A Work MAY count **once per theme** if it independently matches both themes under `THEME-DICT/v1` |
| Numerator | country × week × `THEME-DICT/v1`-matching Works |
| Denominator | country × week **total** Works with compatible **structured** country evidence |
| Denominator theme filter | **MUST NOT** include theme phrase / dictionary filters |
| Compatible semantics | Numerator and denominator MUST use compatible **country**, **time**, and **inclusion** semantics |
| Primary derived measure | `matched_share = matched_works / denominator_works` |
| Retain separately | `matched_works` count |
| Smoke ceilings | **Not** production / backfill semantics |
| `partial` | Remains a **quality state**, not a desired M7 retrieval mode |

### 2.2 Google Trends Transport A (FROZEN)

| Element | Contract |
|---|---|
| Measurement | Source-returned weekly **0–100 within-request** relative interest |
| Denominator | None (source-relative) |
| Scope identity | MUST identify the export/request the scale belongs to (geo, paired probes, period, observation index, file hash / run id) |
| Prohibited | Absolute JP vs US (or other) level comparison; cross-country absolute interpretation; normalization against OpenAlex; unified OpenAlex/Trends index |

---

## 3. Gate B — Proxy Meaning (FROZEN)

### OpenAlex observes

Indexed scholarly **Works** that satisfy the frozen matching rule and carry approved structured country evidence.

**Does not** directly observe: society, adoption, opinion, researchers themselves, causal diffusion, or a social layer.

### Google Trends observes

Google Web Search **within-request relative interest** for the frozen query/geo scope.

**Does not** directly observe: adoption, opinion, population prevalence, or macro-level society.

**MUST NOT** auto-map sensors to micro / meso / macro.

---

## 4. Gate C — Time (FROZEN)

### OpenAlex

| Element | Contract |
|---|---|
| Canonical analysis time | `publication_date` |
| Week bucket | ISO 8601 week in UTC: `YYYY-Www` (from `publication_date`) |
| Retain separately (not analysis time) | `created_date`, `updated_date`, `observed_at`, `ingested_at` when available |
| Boundary weeks | **Flag**; do **not** pad or fabricate days outside the analysis window |
| Analysis window start | Inclusive `2022-11-30` (requirements). Weeks that contain this boundary or otherwise sit at the window edge are flagged |

### Google Trends

| Element | Contract |
|---|---|
| Week labels | Preserve **source-returned** week labels |
| Convention | Document week-start convention on the series / Canonical metadata |
| Prohibited machinery | Lead/lag correction; publication-lag estimation; propagation-lag models; cross-sensor temporal resampling solely to force alignment |
| Cross-sensor timing | Descriptive comparison only |

---

## 5. Gate D — Theme Classification (FROZEN)

| Field | Value |
|---|---|
| Version | **`THEME-DICT/v1`** |
| Seed | `PROVISIONAL-M5-SMOKE/2026-08-23-r1` **unchanged** (no micro-delta) |
| Vocabulary modified after M5 | **NO** |
| Matching | Deterministic phrase match (NFKC, Latin case-fold, hyphen→space, whitespace normalize). No translation, stemming, acronym expansion, or **LLM-only primary** classification |
| Standalone `agent` | **MUST NOT** qualify alone |
| Canonical wording | **“THEME-DICT/v1 matching Works”** |
| Forbidden wording | “all generative-AI research”; “all AI-agent research” |

### M5 review provenance (accurate; not rewritten)

| Field | Value |
|---|---|
| Mode | **Human-delegated AI-assisted** semantic review |
| Manual Human row-by-row review | **NO** |
| AGREE | 62 |
| DISAGREE | 11 |
| UNSURE | 2 |
| Vocabulary mutated by review | **NO** |
| Evidence record | [`m5-openalex-vocabulary-review.md`](m5-openalex-vocabulary-review.md) |

Interpretation for Canonical limitations:

- **DISAGREE** = observed disagreement under delegated review — **not** automatically confirmed false negatives and **not** authority to expand terms in v1.
- **UNSURE** = insufficient displayed context.
- Narrow-recall risk of a precision-biased dictionary remains an expected limitation.

Improvements → **`THEME-DICT/v2+`** only, under separate versioned review. M7 Raw that retains text evidence MAY be reclassified later without refetch when a new dictionary version is adopted.

### Term-emergence confounding (FROZEN limitation)

Terms such as `generative AI`, `agentic AI`, `AI智能体`, and related dictionary phrases themselves emerged and spread during the study period. A rising match series may reflect some combination of:

1. change in underlying activity, and/or
2. change in terminology adoption.

The first Canonical Finding **MUST NOT** silently call this “growth of AI research.” Prefer: **growth in Works matching THEME-DICT/v1 terminology**.

---

## 6. Gate E — Country

### 6.1 Evidence rules (FROZEN)

| Element | Contract |
|---|---|
| OpenAlex evidence | Structured only — e.g. `authorships.countries`, institution `country_code` (as already used in M5 privacy-reduced envelopes) |
| Prohibited | Name inference; language inference; LLM inference |
| Trends geo | Requested geo parameter defines geographic scope |
| `unknown` | Explicit category when **no structured country code** is present; **`unknown ≠ zero`**; report measured ratios where relevant. A Work with only non-target structured codes (e.g. `DE`) is **not** `unknown` — it simply does not enter JP/US/KR/CN inclusion counts |
| Invented acceptance threshold for unknown | **MUST NOT** invent one merely to close M6 |
| Target countries | `JP`, `US`, `KR`, `CN` |

### 6.2 Multi-country counting — TBD-008 (**FROZEN — Human ratified**)

Per `docs/requirements.md` TBD-008 and `implementation-plan.md` Gate E Decision Table (`codex-review` + **Human**), multi-country aggregation required Human authority before country-level Canonical.

**Rule (Human-ratified 2026-08-29):**

| Field | Value |
|---|---|
| Rule | **Inclusion counting** |
| Definition | A Work with structured evidence for multiple target countries counts **once in each** distinct target country |
| Denominator | Compatible inclusion semantics (Works with that country’s structured authorship evidence in the week) |
| Fractionalization | **Not** in v1 |
| Reporting | Report multi-country rate alongside country figures |
| Raw | Preserve multi-country evidence; do not collapse |
| Freeze status | **FROZEN — Human ratified (`承認`, 2026-08-29)** |

**M7 implication (plan-aligned):** Raw acquisition for OpenAlex MAY proceed after Gate D freeze. Country-level Canonical MAY use TBD-008 inclusion counting as frozen.

---

## 7. Quality states (carried forward)

Primary states remain those frozen by M5 Erratum-001:

`success` | `zero` | `missing` | `unknown` | `fetch_failure` | `partial`

Invariants: `unknown ≠ zero`, `missing ≠ zero`, `fetch_failure ≠ zero`, `partial ≠ success`. Failures and attribute gaps MUST NOT be coerced to numeric zero.

---

## 8. Trends Obs1 / Obs2 (methodology only; no Obs2 execution)

| Item | Status |
|---|---|
| Obs1 (Transport A, 4 geos) | **Eligible** for a **sensor-specific** Trends Canonical contract **with limitations** (no Obs2 repeat; source-relative scale; not absolute cross-country levels) |
| Obs2 | **Deferred** — not executed in M6 |
| Obs2 blocks OpenAlex M7? | **NO** (unless a later SoT change says otherwise) |

Promotion of Trends series to Canonical does **not** require merging scales with OpenAlex.

---

## 9. Explicit non-scope (DROP / DEFER for this freeze)

Do **not** build or freeze in M6:

- M7 historical backfill; M8 analysis
- Production-perfect / multilingual-perfection dictionary campaign; new 75-row Human review
- Trends Transport B; Company methodology; GitHub methodology; arXiv methodology (fallback only if later triggered)
- Cross-sensor unified index; cross-country Trends normalization
- Lead/lag rule; statistical significance testing; causal inference; dashboard
- Generalized connector framework; temporal orchestration; new cloud infrastructure

Current PoC sensor disposition (from M5 narrow close-out): OpenAlex **KEEP**; Trends Transport A **KEEP**; Transport B / GitHub **DEFER**; Company four-country comparative **DROP**; arXiv **fallback only**.

---

## 10. Version identity

| Artifact | Version / ID |
|---|---|
| Gate contracts JSON | `M6-GATE-CONTRACTS/v1` |
| Theme dictionary | `THEME-DICT/v1` |
| Quality states | M5 Erratum-001 vocabulary |
| Country multi-count rule | TBD-008 / inclusion counting (**Human ratified 2026-08-29**) |
| Rule module (code) | `thought_flow.methodology` helpers — contract enforcement fixtures only; **not** M7 connectors |

Canonical regeneration MUST record dictionary version, aggregation/country rule version, time rule version, and input Raw snapshot identity.

---

## 11. M7 / M8 handoff conditions

1. This Decision Record Human-approved (including RF acceptance and TBD-008).
2. `THEME-DICT/v1` frozen and unchanged from M5 provisional seed.
3. Gate A denominator remains theme-independent; Gate B/C wording preserved.
4. M7 OpenAlex backfill uses full lawful pagination — not M5 smoke ceilings — and append-only Raw.
5. M8 builds **separate** sensor Canonical tables; first Finding uses THEME-DICT/v1 wording and term-emergence limitation.
6. No M7/M8 work is started by this M6 package itself.

---

## 12. Human approval (bounded bundle — ACCEPTED)

Human signal: **`承認`** (2026-08-29).

Accepted as one bundled decision:

1. **M5 `RF PASS WITH LIMITATIONS`** via OpenAlex-alone route, including acceptance that Human-delegated AI-assisted vocabulary review is sufficient for RF §12.1 #6 **WITH LIMITATION** (not manual row-by-row review).
2. **M6 Gates A–D** and Gate E structured-evidence / unknown rules as frozen in this record (unknown = no structured country code; non-target codes ≠ unknown).
3. **TBD-008** multi-country rule = **inclusion counting**.

No row-level review, no dictionary micro-delta, and no Obs2 execution were requested or performed for this freeze.

---

## 13. Self-check

- [x] Separate Canonical datasets; no merged scale
- [x] Gate A denominator theme-independent
- [x] Gate D = r1 seed unchanged; delegated-review provenance accurate
- [x] Term-emergence confounding explicit
- [x] No invented unknown threshold
- [x] Unknown ≠ non-target structured country
- [x] No country inference
- [x] Deferred sensors not re-entered
- [x] M7/M8 not implemented here
- [x] TBD-008 Human ratified
- [x] RF acceptance included in Human bundle

M6 METHODOLOGY FREEZE STATUS: FROZEN — HUMAN APPROVED
