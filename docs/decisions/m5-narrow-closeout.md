# M5 Narrow Close-out — RF Candidate + PoC Scope

- Status: Cursor close-out recommendation for Human / Codex final. **Not** production `GO`. **Not** M6 Gate freeze. **Not** M7 authorization.
- Management IDs: TFO-M5-017 (initial close-out); **TFO-M5-018** (RF #5 public-safe aggregates + stale-text fix)
- Date: 2026-08-29
- Source of Truth: `docs/requirements.md` v1.0; frozen `implementation-plan.md` v1.0; `docs/decisions/m5-smoke-spec.md` (§12 RF); OpenAlex Decision Record; Trends Obs1 evidence; this file.
- RF route: **OpenAlex alone** (smoke-spec §12.1 permits a single route)

---

## 1. RF recommendation

| Field | Value |
|---|---|
| **Recommended RF state** | **`RF PASS` WITH LIMITATIONS** |
| Anchor route | OpenAlex Works smoke run `3422ccef-6968-4c29-8b7b-74e182d88873` |
| Trends required for this RF | **NO** (Obs2 deferred; Trends not the RF anchor) |
| Production `GO` | **NO** |
| M6 Gate A–E frozen | **NO** |
| M7 large backfill authorized | **NO** until Human / Codex accept RF and Gate D allows acquisition |
| Documentation alone | **Not** used as RF PASS — live smoke + delegated §4 review evidence exist |

### 1.1 §12.1 checklist (OpenAlex)

| # | Requirement | State | Note |
|---|---|---|---|
| 1 | JP/US/KR/CN × both themes; no inferred country / fabricated cells | SATISFIED WITH LIMITATION | 24 cells; `fetch_failure=0`; structured countries |
| 2 | 2022-11-30 + mid + recent; weekly construction | SATISFIED WITH LIMITATION | Three sentinels; weekly path documented, not fully backfilled |
| 3 | Terminal sentinel outcomes; lawful partials | SATISFIED WITH LIMITATION | 14 success / 26 partial / 2 zero; ceilings + cursor path |
| 4 | Population / denominator | SATISFIED | 12 country×period denominators |
| 5 | Structured country; unknown; multi-country; no inference | SATISFIED WITH LIMITATION | Public-safe measured aggregates in §1.2 (smoke retained-work denominators; not Canonical / not Gate E) |
| 6 | Theme evidence + basic positive/negative review | SATISFIED WITH LIMITATION | See [`m5-openalex-vocabulary-review.md`](m5-openalex-vocabulary-review.md); **Human-delegated AI-assisted**, not manual row-by-row |
| 7 | Time-field separation for Gate C handoff | SATISFIED WITH LIMITATION | Candidate fields only |
| 8 | Repeatable under terms / quota / cost / storage | SATISFIED WITH LIMITATION | CC0; cost `null` under Erratum-001; Raw local |

Cross-source patching was **not** used.

### 1.2 RF §12.1 #5 — public-safe country aggregates (TFO-M5-018)

Derived **read-only** from immutable OpenAlex smoke Raw run `3422ccef-6968-4c29-8b7b-74e182d88873`. **Raw is not published.** No new fetch. No name / language / LLM country inference.

**Country evidence mechanism (structured only):** privacy-reduced envelopes retain `authorships.countries` and `authorships.institutions.country_code` when present. `missing_country` / `unknown` means no structured country code on the Work after allowlisted projection. `multi_country` means two or more distinct structured country codes retained on the Work. Counts below use **deduplicated retained Work IDs** (first envelope wins under sorted Raw filenames). These denominators are **smoke retained/inspected samples**, not the full OpenAlex source population and **not** a Canonical or Gate E threshold.

#### A. Global theme audit retained Works (primary unknown measurement)

Population / denominator: distinct Work IDs retained in the six `global_theme_audit` cells (no country filter; theme × OA-START/MID/RECENT). This is the smoke path designed to observe unknown / multi-country among topic candidates.

| Metric | Count | Rate |
|---|---:|---:|
| Deduplicated retained Works (N) | 514 | 1 |
| Unknown-country (`missing_country` = true) | 159 | 159/514 ≈ 0.309 |
| Multi-country (`multi_country` = true) | 101 | 101/514 ≈ 0.196 |

Unknown is **not** coerced to zero: 159 unknown Works are counted separately from numeric theme zeros / `quality_state=zero` cells.

#### B. Country×theme retained Works (multi-country retention under country filter)

Population / denominator: distinct Work IDs retained in the 24 `country_theme` cells (JP/US/KR/CN × themes × periods). Country filter is a retrieval aid; multi-country authorship is still retained when present.

| Metric | Count | Rate |
|---|---:|---:|
| Deduplicated retained Works (N) | 1340 | 1 |
| Unknown-country (`missing_country` = true) | 0 | 0/1340 = 0 |
| Multi-country (`multi_country` = true) | 513 | 513/1340 ≈ 0.383 |

Unknown = 0 in this scope is **expected under country-filtered retrieval**, not a claim that the global corpus has no unknown. Use Scope A for unknown measurement.

**Inference confirmation:** no person-name, language, or LLM fill-in was used to assign country. Unknown remains a measured result.

---

## 2. Limitations (must remain explicit)

1. §4 review mode is **Human-delegated AI-assisted** (ChatGPT under explicit Human instruction). It is **not** manual Human row-by-row review.
2. DISAGREE=11 / UNSURE=2 show provisional vocabulary narrowness / snippet limits → **Gate D evidence**, vocabulary **unchanged**.
3. Live OpenAlex Raw remains outside the public repository (hashes in OpenAlex Decision Record); §1.2 publishes only aggregates.
4. Intentional smoke `partial` cells constrain completeness claims; §1.2 rates are over smoke retained Works, not full source population.
5. Google Trends Obs1 is exploratory Transport A evidence only; Obs2 not done; Trends is **not** RF PASS for this close-out.
6. Company four-country comparative lane is out of current PoC (China access cutoff without evidenced route).
7. No causal claims; no Canonical; no production sensor GO; no Gate E freeze from §1.2 rates.

---

## 3. Current PoC sensor scope (AC-DATA-001 dispositions)

| Item | Decision | Reasoned basis |
|---|---|---|
| OpenAlex | **KEEP** | RF-capable route with completed smoke + §4 review packaging |
| Google Trends Transport A | **KEEP** | Obs1 UI CSV imports succeeded (4/4 geos); limitation: relative scale / Obs2 absent |
| Google Trends Obs2 | **DEFER** | Needed for Trends SMOKE-PASS path only; **not** required for OpenAlex-alone RF |
| Google Trends Transport B | **DEFER** | Erratum-002 exists; dual live gate / not current PoC work |
| Company (four-country comparative) | **DROP** (current PoC) | Smoke-spec China access deadline passed without evidenced official route → four-country comparative `SMOKE-NO-GO`; not a forever ban on all company sources |
| GitHub | **DEFER** | No Org registry / smoke; privacy + Events history limits; forgo current PoC expansion |
| arXiv | **DEFER** / fallback only | CONDITIONAL country evidence; OpenAlex did not require it for RF cells |

TBD-001 (overall production source selection) remains open at program level until M6.

---

## 4. M6 handoff (evidence only)

M5 does **not** freeze Gates. Handoff pointers:

| Gate | Evidence pointer | Frozen? |
|---|---|---|
| A | OpenAlex denominators / Work IDs / partial ceilings | NO |
| B | Indexed Works proxy limitations | NO |
| C | publication / created / updated / observed / ingested samples | NO |
| D | `PROVISIONAL-M5-SMOKE` + delegated review DISAGREE/UNSURE list | NO |
| E | Structured authorship countries; no inference | NO |

Trends Obs1 relative-interest series remain optional secondary evidence for Gate A/B/C discussion; not Canonical.

---

## 5. What this close-out does **not** do

- Start M6 / M7 / M8 implementation
- Create another Value Preview
- Implement Company / GitHub / arXiv / Transport B live
- Mutate smoke vocabulary
- Claim production GO or causal Findings
- Invent a new governance framework or Erratum

---

## 6. Human / Codex next

1. Accept or reject **RF PASS WITH LIMITATIONS** given delegated §4 mode.
2. If accepted: begin M6 Gate work on OpenAlex (+ optional Trends limitations); do not treat deferred sensors as silent GO.
3. If rejected solely because delegation ≠ manual Human review: escalate — do **not** auto-Erratum; Human decides whether to re-review manually or amend process.

M5 NARROW CLOSE-OUT STATUS: READY FOR HUMAN / CODEX REVIEW
