# Cloud Comparison

## Status

**Not yet evaluated.** BigQuery parity is planned for M9 after a minimal DuckDB analysis contract exists. Azure optional branches are judged in M2 (adopt/defer) and exercised only if adopted (M10).

## Comparison dimensions (required when executed)

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
- Azure AI Foundry initial budget cap: ¥1,000 (if used).

## Related

- Requirements: `docs/requirements.md` §§14.2–14.3, 18
- Plan: `implementation-plan.md` §§6 (M2, M9, M10), 14
