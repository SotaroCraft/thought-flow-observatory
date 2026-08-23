# Methodology

## Status

**Not yet evaluated** for Gate A–E freeze. This page is the portfolio entry for measurement rules.

## Fixed Plan stance (do not reinterpret)

- Weekly Canonical is the analysis time grain; Raw keeps source grain.
- Compare within sensor first; do not treat raw values from different sources as the same scale.
- Sensors are social-layer *proxies*, not micro/meso/macro labels themselves.
- Separate event / publication / observed / ingestion time; do not equate publication lag with social propagation delay.
- Country uses primary attributes only; keep `unknown`; never infer from name, language, or LLM fill-in.
- Theme classification uses versioned multilingual dictionaries (M6); LLM is assistive only if ever used.
- Separate observation, quality/limits, interpretation, and causal hypotheses.

## Methodology Gates (M6)

| Gate | Topic | Freeze before |
|---|---|---|
| A | Unit / population / denominator | Canonical + distribution metrics |
| B | Sensor vs social-layer proxy | Methodology publication |
| C | Time semantics | Weekly Canonical generation |
| D | Theme dictionary quality | Large backfill (M7) |
| E | Country rules | Country-level Canonical |

Decision Records will live under `docs/decisions/` when Gates complete.

## Related

- Requirements: `docs/requirements.md` §§12, 15
- Plan: `implementation-plan.md` §§5.2, 8, 9
