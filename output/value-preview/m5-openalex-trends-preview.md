# EXPLORATORY TFO VALUE PREVIEW

> **NOT CANONICAL / NOT M6 / NOT RF FINAL**
>
> Bounded descriptive comparison of **OpenAlex M5 smoke** (Research) and
> **Google Trends Observation 1** (Search Interest).
>
> **Do not numerically merge incompatible scales.**
> OpenAlex matched counts ≠ Trends 0–100 relative interest.
> Trends values are **not** comparable as absolute levels across countries.

## Sensors in scope

| Sensor | Evidence | Scale |
|---|---|---|
| OpenAlex Works | Existing preview `m5-openalex-preview.md` / run `3422ccef-…88873` | Matched Works under provisional vocabulary; many cells `partial` |
| Google Trends Obs1 | `m5-trends-obs1-preview.md` / four Transport A imports | Within-request 0–100 relative interest |

OpenAlex windows (frozen smoke):

| Period | Inclusive dates |
|---|---|
| OA-START | 2022-11-30 … 2022-12-04 |
| OA-MID | 2024-10-07 … 2024-10-13 |
| OA-RECENT | 2026-08-10 … 2026-08-16 |

Trends Obs1: continuous weekly series over `TRENDS-FULL` (same overall calendar span; different sampling grain).

## Method (bounded)

For each GEO × theme:

1. Note OpenAlex **direction across OA-START → OA-MID → OA-RECENT** matched counts (smoke sample only).
2. Note Trends **early / mid / late third means** and first visible rise thresholds **within that GEO**.
3. Describe whether Research and Search Interest **appear** to intensify in similar or different temporal regions.
4. Label every claim **OBSERVED** or **HYPOTHESIS / NEXT QUESTION**.
5. Never claim causation, population totals, or cross-country absolute ranking.

## Per-country descriptive notes

### JP

**OBSERVED (OpenAlex):** `generative_ai` matched 0 → 4 → 28 across START/MID/RECENT; `ai_agent` matched 1 → 0 → 6, with all three cells `partial`; the MID matched=0 is not a complete valid-zero observation.

**OBSERVED (Trends):** `generative_ai` early/mid/late means 26 → 54 → 78; first ≥50 in Nov 2023; peak 100 in May 2026. `ai_agent` remains low on shared scale (late mean ~7.5, peak 12).

**OBSERVED (cross-sensor, descriptive):** Both sensors show **higher late-window intensity than early** for JP `generative_ai` in this smoke/Obs1 evidence — Research matched counts rise across OA windows; Search Interest within-request means rise across series thirds.

**HYPOTHESIS / NEXT QUESTION:** Does JP `ai_agent` Search Interest stay structurally below `generative_ai` on shared Trends scale while Research `ai_agent` matched counts remain small/partial — or is Obs1 noise / probe sensitivity? Needs repeat Obs2 + vocabulary gate, not a Finding.

### US

**OBSERVED (OpenAlex):** `generative_ai` 1 → 55 → 84; `ai_agent` 2 → 6 → 75 (mostly partial).

**OBSERVED (Trends):** Both themes low early; late third rises. `ai_agent` first ≥20 mid-2025; peaks at 100 in Jun 2026 while same-week `generative_ai` is 67 (shared scale).

**OBSERVED (cross-sensor):** Research matched counts are already elevated by OA-MID (Oct 2024) for `generative_ai`, whereas Search Interest means for both US themes stay modest until the **late** third (2025–2026). Temporal regions of visible increase **differ** between sensors in this sample.

**HYPOTHESIS / NEXT QUESTION:** Is US Search Interest lagging Research vocabulary matches, or are ceilings/partial cells and Trends normalization producing a timing illusion? Not answerable without Canonical design.

### KR

**OBSERVED (OpenAlex):** `generative_ai` matched 0 → 3 → 10; `ai_agent` matched 0 → 0 → 2, with all three cells `partial`; START/MID matched=0 are not complete valid-zero observations.

**OBSERVED (Trends):** `generative_ai` means 14 → 40 → 51; `ai_agent` sparse early (many zeros), late mean ~24, peak 51 (May 2026).

**OBSERVED (cross-sensor):** Both sensors show **weak early** and **stronger recent** signals for KR `generative_ai` in this evidence set. `ai_agent` remains thin on Research matched counts and intermittent on Trends.

**HYPOTHESIS / NEXT QUESTION:** Whether KR `ai_agent` is genuinely later/rarer than `generative_ai` under frozen probes — or probe/coverage artifact.

### CN

**OBSERVED (OpenAlex):** `generative_ai` matched 0 → 21 → 65, with all three cells `partial`; the START matched=0 is not a complete valid-zero observation. `ai_agent` matched 1 → 0 → 18, with all three cells `partial`; the MID matched=0 is not a complete valid-zero observation.

**OBSERVED (Trends):** `generative_ai` mostly zeros (158/195), peak only 39; `ai_agent` mostly zeros early, late rise, peak 100 (Jul 2026).

**OBSERVED (cross-sensor):** Research matched counts for CN `generative_ai` rise across OA windows, while Trends `generative_ai` stays sparse on the within-request scale. For `ai_agent`, Research recent matched counts rise and Trends late-third mean also rises — **similar late region**, different early texture (Research partial vs Trends zero-dense).

**HYPOTHESIS / NEXT QUESTION:** Does CN Web-Search Trends under-represent `生成式人工智能` relative to OpenAlex Works coverage under provisional terms? Quality/zero density suggests caution; no causal claim.

## Strongest defensible cross-sensor observation

**OBSERVED:** Across JP/US/KR/CN smoke evidence, **Research (OpenAlex matched counts)** and **Search Interest (Trends within-request series)** do **not** share one numeric scale, but several GEO×theme cells show **broadly similar late-vs-early direction** (higher recent intensity), while **US timing of visible increase differs** (Research elevated by OA-MID; Trends rise concentrated later).

## Hypotheses raised (not findings)

1. Sensor timing may diverge by GEO/theme (especially US).
2. CN Trends zero density vs OpenAlex partial/success cells may reflect channel/probe coverage differences.
3. Within-US shared Trends scale favoring `ai_agent` at peak may or may not align with Research matched-count growth — needs Canonical methods.

## Prohibited conclusions avoided

- No causal claims (research ↔ search).
- No absolute cross-country ranking of either sensor.
- No merge of OpenAlex counts with Trends 0–100 into a single index.
- No RF PASS / M6 freeze / production GO.
- No claim that Obs1 alone completes Trends mandatory evidence (Obs2 pending).

---

*Exploratory two-sensor preview only. Not Canonical / not M6 / not RF final.*
