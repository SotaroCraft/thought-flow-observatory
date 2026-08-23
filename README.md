# Thought Flow Observatory

Microsoft 365を中心とした公開情報Research Hubを構築し、思考潮流観測PoCを実施したプロジェクト。

This public repository implements **Thought Flow Observatory**: a SharePoint Online–centered Research Hub for public sources, plus a local-first PoC that observes information flow around Generative AI and AI Agents across Japan, the United States, South Korea, and China.

## What this project is

| Axis | Intent |
|---|---|
| Research | Observe distribution and dynamics of public information before mean shifts dominate |
| Microsoft | Validate SPO, Copilot, Graph / Entra as one practical Research Hub |
| Portfolio | Keep purpose → design → implementation → validation → results → decision traceable |

Local source of truth for quantitative work is **Python + DuckDB + Parquet**. SharePoint is the human-facing Hub, not the analysis store. External services are optional boundaries and must not block local analysis.

## Current status (M1)

M1 establishes a **public-safe repository and local skeleton**:

- Configuration without required external credentials
- Append-only Raw persistence (Parquet) and DuckDB catalog smoke path
- Run manifests with distinct `run_identity` vs stable `record_identity` / `raw_content_identity`
- Portfolio documentation entry points (placeholders where not yet evaluated)

Later milestones add SPO Hub, sensors, methodology gates, backfill, analysis, and cloud comparison.

## Quick start (local, no external services)

Requirements: Python 3.12+, [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run thought-flow smoke
uv run pytest
```

Synthetic sample: `data/samples/m1_synthetic_raw.json`.  
Local Raw / manifests land under `workspace-data/` (git-ignored). Override with `THOUGHT_FLOW_DATA_ROOT`.

Copy `.env.example` to `.env` only when you need local overrides. Never commit secrets.

## Documentation map

| Document | Role |
|---|---|
| [`docs/requirements.md`](docs/requirements.md) | Requirements Source of Truth (v1.0) |
| [`implementation-plan.md`](implementation-plan.md) | Frozen implementation Plan (v1.0) |
| [`docs/architecture.md`](docs/architecture.md) | Architecture and boundaries |
| [`docs/methodology.md`](docs/methodology.md) | Measurement model and gates |
| [`docs/m365-validation.md`](docs/m365-validation.md) | Microsoft 365 validation log |
| [`docs/research-findings.md`](docs/research-findings.md) | Research findings (observation / limits / interpretation) |
| [`docs/cloud-comparison.md`](docs/cloud-comparison.md) | DuckDB / BigQuery / Azure comparison |
| [`AGENTS.md`](AGENTS.md) | Short agent safety / navigation contract |

## License

MIT — see [`LICENSE`](LICENSE). Public samples are synthetic or rights-cleared only; do not add redistributability-unclear PDFs.
