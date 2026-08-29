# EXPLORATORY TFO VALUE PREVIEW

> **NOT CANONICAL / NOT M6 / NOT RF FINAL**
>
> Google Trends Observation 1 — Human official UI CSV (Transport A).
> Exploratory only. Not Canonical analysis. Not a causal Finding.

## WARNING (read first)

**0–100 relative-interest values must NOT be compared as absolute levels across
independently normalized country requests.** Each GEO export is normalized
within that request. Within-country theme comparison (both probes in one CSV)
shares a scale; cross-country level comparison does not.

## Evidence identity (public-safe)

| Field | Value |
|---|---|
| Sensor | Google Trends (Search Interest) |
| Transport | **A** — `human_official_csv` (no Transport B; no undocumented network) |
| Observation index | **1** |
| Period | `TRENDS-FULL` `[2022-11-30, 2026-08-17)` |
| Geos | JP, US, KR, CN |
| Themes (paired per GEO) | `generative_ai` × `ai_agent` |
| Category / property (UI) | All categories (`カテゴリ: すべてのカテゴリ`); Web Search / Term mode (Human contract) |
| Live Raw in git | **No** (local `workspace-data/`, gitignored) |

### Import runs (Obs1)

| GEO | Run ID | Source SHA-256 | Byte-preserved |
|---|---|---|---|
| JP | `5d28e7e1-3c19-4a7b-ad3e-ad04da5ad4ff` | `b2645c68…20f555` | YES |
| US | `a967275e-0288-4c33-b124-a41902889781` | `b8054947…15995a` | YES |
| KR | `031a52b1-35fe-4de3-81f6-f9400944853f` | `425d36ea…3035f1` | YES |
| CN | `6df9f8c6-f79f-44a4-bd30-a01cade4622d` | `6f28b0f8…e50beb` | YES |

Successful imports: **4 / 4**. Failures: **0**.

Frozen probes matched (UI geo suffix stripped for label check only; CSV bytes unchanged):

| GEO | generative_ai | ai_agent |
|---|---|---|
| JP | 生成AI | AIエージェント |
| US | generative AI | AI agent |
| KR | 생성형 AI | AI 에이전트 |
| CN | 生成式人工智能 | AI智能体 |

Zero semantics: `low_or_insufficient_relative_interest` (includes numeric `0` and UI low markers such as `1 未満` / `<1`).

## Series coverage (OBSERVED)

Each series: **195** weekly points, week labels `2022-11-27` … `2026-08-16` (week starts may precede inclusive start; end aligns with TRENDS-FULL end).

| GEO | Theme | success | zero | missing | fetch_failure | Peak week | Peak value* |
|---|---|---|---:|---:|---:|---:|---|---:|
| JP | generative_ai | 195 | 0 | 0 | 0 | 2026-05-10 | 100 |
| JP | ai_agent | 130 | 65 | 0 | 0 | 2026-05-10 | 12 |
| US | generative_ai | 195 | 0 | 0 | 0 | 2026-06-07 | 67 |
| US | ai_agent | 173 | 22 | 0 | 0 | 2026-06-07 | 100 |
| KR | generative_ai | 183 | 12 | 0 | 0 | 2026-05-10 | 100 |
| KR | ai_agent | 100 | 95 | 0 | 0 | 2026-05-10 | 51 |
| CN | generative_ai | 37 | 158 | 0 | 0 | 2025-02-16 | 39 |
| CN | ai_agent | 43 | 152 | 0 | 0 | 2026-07-05 | 100 |

\*Peak value is **within-request** relative interest only.

### Third-of-series means (OBSERVED, within-country)

Equal thirds of each 195-week series (exploratory summary, not Canonical periods):

| GEO | Theme | Early mean | Mid mean | Late mean |
|---|---|---:|---:|---:|
| JP | generative_ai | 26.3 | 53.8 | 78.5 |
| JP | ai_agent | 0.1 | 2.2 | 7.5 |
| US | generative_ai | 7.3 | 10.2 | 30.9 |
| US | ai_agent | 0.7 | 3.8 | 42.1 |
| KR | generative_ai | 13.8 | 40.0 | 51.2 |
| KR | ai_agent | 0.0 | 3.4 | 24.1 |
| CN | generative_ai | 2.1 | 2.6 | 8.2 |
| CN | ai_agent | 0.0 | 0.4 | 27.0 |

## Visible timing / peaks (OBSERVED)

Within each GEO request only:

1. **JP** — `generative_ai` rises through early→late thirds; first ≥50 on **2023-11-12**; series max **100** on **2026-05-10**. `ai_agent` stays low vs shared scale (peak **12**); many early zeros / `1 未満`.
2. **US** — Both themes remain low early; late third rises. `ai_agent` first ≥20 on **2025-06-15**, reaches **100** on **2026-06-07**; same week `generative_ai` peaks at **67** (shared scale: agent higher at peak).
3. **KR** — `generative_ai` climbs early→late; max **100** on **2026-05-10**. `ai_agent` sparse early (many zeros); late mean higher; peak **51** on **2026-05-10**.
4. **CN** — `generative_ai` mostly zero (**158/195**); intermittent spikes; peak only **39** (**2025-02-16**). `ai_agent` mostly zero early (**152/195** zeros); late rise with peak **100** on **2026-07-05**.

## Quality / missing / zero notes (OBSERVED)

- No `missing` or `fetch_failure` points in Obs1 extracted series.
- Zeros are concentrated on `ai_agent` (JP/US/KR) and on **both** CN themes — classified as low/insufficient relative interest, **not** absence of all public interest, and **not** fetch failure.
- CN sparsity is a quality signal for interpretation caution within that GEO’s shared scale.

## Simple chart (subsample)

Subsample CSV (≈12 points/series, public-safe derived): `output/value-preview/m5-trends-obs1-spark.csv`

ASCII bars = within-series relative height of that subsample (`#` ≈ 5 interest units; `.` = 0). **Not** cross-country comparable.

```
JP generative_ai: ###################################################################################################################
JP ai_agent:      .....####
US generative_ai: ################################
US ai_agent:      ..########################
KR generative_ai: .#######################################################################
KR ai_agent:      .......##############
CN generative_ai: ..####.......####.
CN ai_agent:      ..........#####.
```

## Strongest defensible observations

1. Transport A Obs1 succeeded for all four geos with exact source-byte preservation and frozen probe labels.
2. Within several GEO requests, late-third means exceed early-third means for at least one theme (visible in the table above).
3. Within-US shared scale: late `ai_agent` relative interest exceeds late `generative_ai` at the series peak week.
4. CN series show heavy zero density — observation succeeded, but interest is sparse on the 0–100 within-request scale.

## Limitations

- Observation **2** (repeat) not yet imported → Trends RF / SMOKE-PASS not claimed.
- Weekly UI labels vs calendar TRENDS-FULL inclusive start differ by week-start convention.
- Exploratory thirds ≠ OpenAlex OA-START/MID/RECENT windows.
- No causal claims; no Canonical merge; no cross-country absolute level ranking.

---

*Generated from Obs1 Transport A imports. Exploratory only.*
