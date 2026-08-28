# M365 Validation Log

## Status

M3 and M4 have separate entries below. Do **not** treat Human historical recollection as automatic PASS without reconfirmation or live smoke evidence.

## M3 — SharePoint Research Hub / Copilot

| Field | Content |
|---|---|
| Date | 2026-08-29 (checklist issued; live reconfirm pending Human) |
| Feature | SPO Research Hub + Copilot Capture / Use / Promote |
| What was tried | Repository rediscovery only. Existing Hub may already exist in tenant; not recreated from Git. |
| What worked | Not yet reconfirmed via Human checklist. (M4 live smoke observed a library preferred display name `Sources` — useful lead only; does **not** satisfy M3 Exit criteria alone.) |
| What did not work | In-repo M3 PASS not recorded; checklist answers still empty. |
| Required permissions / prerequisites | Human M365 access to the existing Research Hub site; Copilot entitlement as licensed. |
| Constraints | Capturing a Source must not require Card creation. Do not rebuild Hub solely for evidence. |
| Usefulness to Research Hub | Foundational human surface (requirements §§13, FR-HUB). |
| Adopt / defer decision | **Pending** Human checklist in `docs/operations/m3-hub-reconfirm-checklist.md`. **Not complete.** |
| Evidence location (public-safe) | Checklist + this log after Human answers (no tenant URLs / IDs). |

## M4 — Graph / Entra minimum SPO connectivity

| Field | Content |
|---|---|
| Date | 2026-08-29 |
| Feature | Microsoft Graph / Entra delegated read smoke against existing SPO site |
| What was tried | (1) Device Code Flow live auth → **AADSTS530035 / BlockedBySecurityDefaults**. (2) Kept Security Defaults enabled; switched to delegated interactive browser + PKCE (`http://localhost`). (3) Human live `thought-flow m4-graph-spo-smoke --live` with delegated **`Sites.Read.All` only**. |
| What worked | **PASS.** `status=succeeded`, `auth_mode=delegated_interactive_browser`, `permission_scope=Sites.Read.All`. Operations: authentication, site_resolve, list_enumerate, metadata_read. Target site resolved; one List/Library enumerated; preferred display name `Sources`; one list metadata object read. |
| What did not work | Device Code Flow under Security Defaults (expected after policy; not reintroduced). |
| Required permissions / prerequisites | Delegated `Sites.Read.All`; public client; interactive browser redirect `http://localhost`. No client secret. See `docs/operations/m4-graph-spo-smoke.md`. |
| Constraints | Confirmed: `read_only`, `no_file_body_download`, `no_site_or_list_ids_in_evidence`, `optional_to_local_core`. Security Defaults preserved; no CA exception for Device Code; no write/sync. |
| Usefulness to Research Hub | Proves programmatic SPO reachability for later optional automation. |
| Adopt / defer decision | **Adopt** for minimum Graph connectivity (AC-M365-001). Manual SPO Capture / Pages remains valid fallback. Do not expand permissions or implement sync on this evidence alone. |
| Evidence location (public-safe) | This log; `docs/decisions/m4-auth-interactive-browser.md`; runbook `docs/operations/m4-graph-spo-smoke.md`. Local CLI may write a sanitized JSON under the gitignored data root `*/m4-smoke/` — **do not commit** that file or any machine-specific absolute path. |

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
- Do **not** paste Tenant IDs, tokens, client secrets, site/list/drive IDs, personal identifiers, or machine-specific absolute paths.
- Record inability and constraints as valid Microsoft-axis outcomes.

## Related

- Requirements: `docs/requirements.md` §§14.1, 19.2, FR-INT-002, AC-M365-001〜003
- Plan: `implementation-plan.md` §§5.1 (S1–S3), 6 (M3–M4), 10
- Ops: `docs/operations/m3-hub-reconfirm-checklist.md`, `docs/operations/m4-graph-spo-smoke.md`
- Decision: `docs/decisions/m4-auth-interactive-browser.md`
