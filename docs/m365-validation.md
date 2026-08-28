# M365 Validation Log

## Status

M3 and M4 have separate entries below. Do **not** treat Human historical recollection as automatic PASS without reconfirmation or live smoke evidence.

## M3 — SharePoint Research Hub / Copilot

| Field | Content |
|---|---|
| Date | 2026-08-29 (checklist issued; live reconfirm pending Human) |
| Feature | SPO Research Hub + Copilot Capture / Use / Promote |
| What was tried | Repository rediscovery only. Existing Hub may already exist in tenant; not recreated from Git. |
| What worked | Not yet reconfirmed in this session. |
| What did not work | In-repo evidence was previously "Not yet evaluated"; no public-safe M3 PASS recorded yet. |
| Required permissions / prerequisites | Human M365 access to the existing Research Hub site; Copilot entitlement as licensed. |
| Constraints | Capturing a Source must not require Card creation. Do not rebuild Hub solely for evidence. |
| Usefulness to Research Hub | Foundational human surface (requirements §§13, FR-HUB). |
| Adopt / defer decision | **Pending** Human checklist in `docs/operations/m3-hub-reconfirm-checklist.md`. |
| Evidence location (public-safe) | Checklist + this log after Human answers (no tenant URLs / IDs). |

## M4 — Graph / Entra minimum SPO connectivity

| Field | Content |
|---|---|
| Date | 2026-08-29 |
| Feature | Microsoft Graph / Entra delegated read smoke against existing SPO site |
| What was tried | Implemented optional local CLI smoke (`thought-flow m4-graph-spo-smoke`); unit tests without live Microsoft access. **Live Entra/Graph call pending Human app registration + `.env`.** |
| What worked | Config-absent / disabled paths are explicit; local core remains independent; sanitized evidence shape defined. |
| What did not work | Live auth + Graph read not executed in this session (Human config gate). |
| Required permissions / prerequisites | Delegated `Sites.Read.All` (AdminConsentRequired: No); public client + device code; user consent normally sufficient unless tenant policy blocks it. See `docs/operations/m4-graph-spo-smoke.md`. |
| Constraints | Read-only; no file body download; no sync; Graph optional to Raw → Canonical → Analysis. |
| Usefulness to Research Hub | Proves programmatic SPO reachability for later optional automation; manual SPO remains fallback. |
| Adopt / defer decision | **Pending live smoke.** Code path ready; adopt only after PASS or record BLOCKED with fallback. |
| Evidence location (public-safe) | This log (update after live run); local sanitized artifact under gitignored `workspace-data/m4-smoke/` (do not commit). |

## Log template (per later feature insight)

| Field | Content |
|---|---|
| Date | |
| Feature | |
| What was tried | |
| What worked | |
| What did not work | |
| Required permissions / prerequisites | |
| Constraints | |
| Usefulness to Research Hub | |
| Adopt / defer decision | |
| Evidence location (public-safe) | |

## Rules

- Do **not** turn this into a per-Source ledger.
- Do **not** paste Tenant IDs, tokens, client secrets, site/list/drive IDs, or personal identifiers.
- Record inability and constraints as valid Microsoft-axis outcomes.

## Related

- Requirements: `docs/requirements.md` §§14.1, 19.2, FR-INT-002, AC-M365-001〜003
- Plan: `implementation-plan.md` §§5.1 (S1–S3), 6 (M3–M4), 10
- Ops: `docs/operations/m3-hub-reconfirm-checklist.md`, `docs/operations/m4-graph-spo-smoke.md`
