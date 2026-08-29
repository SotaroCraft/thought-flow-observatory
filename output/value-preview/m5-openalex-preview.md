# EXPLORATORY TFO VALUE PREVIEW

> **NOT CANONICAL / NOT M6 / NOT RF FINAL**
>
> This is an exploratory, non-normative preview from existing OpenAlex Phase 1
> privacy-safe derived coverage aggregates. It does **not** claim population
> comparability, causal trends, or production analysis.

## Why this file exists

TFO has already performed **source acquisition**, **structured observation**,
and **evidence-quality classification** on a research-sensor path — beyond
ordinary SharePoint / Copilot document workspace interaction.

## Evidence source (public-safe identity only)

| Field | Value |
|---|---|
| Sensor | OpenAlex Works (Research) |
| Run ID | `3422ccef-6968-4c29-8b7b-74e182d88873` |
| Derived coverage | Erratum-001 `coverage.csv` (Human-held local) |
| Original coverage SHA-256 | `96f09bdc1ef715fc201295c9ae44707cdc06765900a1823212bb2faf59d31641` |
| Decision record | `docs/decisions/m5-sensor-decision.md` |
| Live Raw in git | **No** |

## What was observed (frozen smoke scope)

- Countries: JP, US, KR, CN
- Themes: `generative_ai`, `ai_agent`
- Periods: OA-START, OA-MID, OA-RECENT
- Evidence units: 24 theme cells + 12 denominators + 6 audits = **42**
- Quality mix (Erratum-001): **success 14**, **partial 26**, **zero 2**, fetch_failure **0**

## Country × theme × period — quality and matched counts

Matched counts are smoke-sample qualifying Works under provisional vocabulary,
**not** national research output totals. Many cells are `partial` due to retain/page ceilings.

| Country | Theme | OA-START | OA-MID | OA-RECENT |
|---|---|---|---|---|
| JP | `generative_ai` | zero (matched=0, retained=28) | success (matched=4, retained=34) | partial (matched=28, retained=98) |
| JP | `ai_agent` | partial (matched=1, retained=37) | partial (matched=0, retained=36) | partial (matched=6, retained=41) |
| US | `generative_ai` | partial (matched=1, retained=100) | partial (matched=55, retained=100) | partial (matched=84, retained=100) |
| US | `ai_agent` | partial (matched=2, retained=81) | partial (matched=6, retained=86) | partial (matched=75, retained=100) |
| KR | `generative_ai` | zero (matched=0, retained=13) | success (matched=3, retained=24) | partial (matched=10, retained=82) |
| KR | `ai_agent` | partial (matched=0, retained=20) | partial (matched=0, retained=26) | partial (matched=2, retained=43) |
| CN | `generative_ai` | partial (matched=0, retained=100) | partial (matched=21, retained=100) | partial (matched=65, retained=100) |
| CN | `ai_agent` | partial (matched=1, retained=68) | partial (matched=0, retained=40) | partial (matched=18, retained=93) |

## Simple chart — matched counts by period (theme cells only)

```
generative_ai matched (smoke sample; not population):
  JP: OA-START=0. OA-MID=4## OA-RECENT=28####################
  US: OA-START=1# OA-MID=55############# OA-RECENT=84####################
  KR: OA-START=0. OA-MID=3###### OA-RECENT=10####################
  CN: OA-START=0. OA-MID=21###### OA-RECENT=65####################
ai_agent matched (smoke sample; not population):
  JP: OA-START=1### OA-MID=0. OA-RECENT=6####################
  US: OA-START=2# OA-MID=6# OA-RECENT=75####################
  KR: OA-START=0. OA-MID=0. OA-RECENT=2####################
  CN: OA-START=1# OA-MID=0. OA-RECENT=18####################
```

## Strongest defensible observation

Within this **bounded smoke sample**, several patterns are visible without
claiming national totals or causal trends:

1. **Valid zeros exist** (JP/KR `generative_ai` at OA-START): complete observation
   with zero provisional matches — distinct from fetch failure.
2. **Partial dominates** (26/42): ceilings truncated observation; unobserved remainder remains.
3. **Recent windows show higher matched counts** in this sample for several
   country×theme cells (especially US/CN generative_ai OA-RECENT) than OA-START —
   readable as smoke-sample intensity under the provisional vocabulary, **not**
   as a validated time-series Finding.
4. **Denominators succeeded** (12/12 success after Erratum-001): country-period
   Works counts were observable without theme classification.

## Limitations (read before interpreting)

- Provisional vocabulary only (`PROVISIONAL-M5-SMOKE`); not Gate D v1.
- Retain/inspect ceilings → frequent `partial`; not full-population extract.
- Matched counts are not comparable as absolute country levels.
- No RF PASS, no M6 freeze, no production GO.
- Preview aggregates only; live Raw is not published in git.

## vs ordinary SPO / Copilot workspace

| Capability | SPO/Copilot Hub | This OpenAlex smoke evidence |
|---|---|---|
| Document Capture / Use / Promote | Yes | N/A (different path) |
| External research-sensor acquisition | No | Yes (OpenAlex Works API) |
| Structured country×theme×period cells | No | Yes (24 + denoms + audits) |
| Quality states (success/zero/partial/…) | No | Yes (Erratum-001) |
| Append-only privacy-reduced Raw | Hub files | Yes (local; not in git) |
| Methodology Gate freeze | N/A | Not yet (M6 open) |

---

*Generated for Human visibility from existing derived coverage. Exploratory only.*
