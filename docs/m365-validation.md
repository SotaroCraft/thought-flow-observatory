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
| What was tried | Optional CLI smoke; live Device Code Flow auth attempt; then auth-only switch to interactive browser + PKCE (code ready; live retry pending `http://localhost` redirect). |
| What worked | Config-absent / disabled paths explicit; local core independent; SPO site/list/read path unchanged; Security Defaults left enabled. |
| What did not work | Device Code Flow blocked by **AADSTS530035 / BlockedBySecurityDefaults** (auth constraint, not SharePoint permission). Admin consent for `Sites.Read.All` did not unblock Device Code. |
| Required permissions / prerequisites | Delegated `Sites.Read.All`; public client; interactive browser redirect `http://localhost`. See `docs/operations/m4-graph-spo-smoke.md`. |
| Constraints | Read-only; no file body download; no sync; Graph optional; Security Defaults preserved; no CA exception for Device Code. |
| Usefulness to Research Hub | Proves programmatic SPO reachability for later optional automation; manual SPO remains fallback. |
| Adopt / defer decision | **Pending interactive live smoke** after Human adds localhost redirect. Auth design recorded in `docs/decisions/m4-auth-interactive-browser.md`. |
| Evidence location (public-safe) | This log; decision record; local sanitized artifact under gitignored `workspace-data/m4-smoke/` (do not commit). |

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
- Decision: `docs/decisions/m4-auth-interactive-browser.md`
