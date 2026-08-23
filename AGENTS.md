# AGENTS.md — Thought Flow Observatory

Short navigation and safety contract for Cursor / Codex. **Not** a substitute for requirements.

## Source of Truth

1. Read `docs/requirements.md` (v1.0) and `implementation-plan.md` (v1.0) before changing behavior.
2. Priority: `MUST / MUST NOT > SHOULD > COULD`.
3. Do not edit `docs/requirements.md` to fit an implementation preference.

## Hard boundaries

- **Raw is immutable** — append-only; never update/delete prior Raw; never coerce failures to zero.
- **No country inference** from names, language, or LLM fill-in; keep `unknown`.
- **Sensor ≠ social layer** — sensors are proxies; do not auto-label micro/meso/macro.
- **Research Cards are selective** — Capture must not require Card creation.
- **External integrations are optional** — SharePoint / Graph / BigQuery / Azure / Actions must not be required imports for local Raw → Canonical → Analysis.
- **One milestone at a time** — do not implement adjacent milestones or speculative frameworks.
- **No scope creep** — no dedicated Web UI, generic connector/plugin factory, SNS scraping, or full DDL ahead of Gate freeze.

## Stop and escalate

Stop instead of guessing when you hit unresolved Gates, unclear licensing, privacy expansion, permission escalation, budget risk, or a requirements conflict. Record facts, impact, and options for Human / Codex.

## After each task

Report: changed files, Requirement / AC coverage, commands and tests, public-safety check, remaining TBDs, and recommended next step (without implementing it).
