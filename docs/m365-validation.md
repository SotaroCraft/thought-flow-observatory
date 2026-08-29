# M365 Validation Log

## Status

M3 and M4 have separate entries below. Do **not** treat Human historical recollection as automatic PASS without reconfirmation or live smoke evidence.

- **M3:** Human reconfirm **complete** 2026-08-29 — Adopt (AC-HUB-001〜005; TBD-002〜004 decided). See §M3.
- **M4:** Graph connectivity **Adopt** (AC-M365-001). See §M4.

## M3 — SharePoint Research Hub / Copilot

| Field | Content |
|---|---|
| Date | 2026-08-29 |
| Feature | SPO Research Hub + Copilot Capture / Use / Promote |
| What was tried | Human live reconfirm of **existing** Research Hub (no rebuild). Verified six Hub surfaces; confirmed seed Sources Kashima (2019), Michel (2011), Shiller (2017); Capture via public URL shortcut and via public research PDF in Sources; Copilot search / read / compare / summarize / original-source check; selective Promote of one Card (Kashima); Card cross-use; 2-week-pause Resume without backlog cleanup. |
| What worked | **AC-HUB-001〜005 PASS** (AC-HUB-003 with documented limitation). **AC-HUB-001:** PDF/file Capture into Sources completed with **one direct drag-and-drop**; no subsequent mandatory save / confirm / tag / classification / summary / Research Card. Capture without mandatory structure on both paths. PDF-in-Sources path: Copilot read and summarized file body directly. Seeds present and reusable. One Source Used; one valuable Source Promoted (Title mandatory only; Card links to Source). All required surfaces present. Resume without cleanup succeeded. |
| What did not work / limitations | URL shortcut Capture: ~3 UI steps, no mandatory structure, discoverable, but body not inside SPO — Copilot needed external access to read; URL path is **not** the AC-HUB-001 one-operation evidence. Research Card discoverability weaker than Source retrieval: Copilot found the Source readily; Card cross-use worked when the Research Cards list was **explicitly provided** — classification **CONSTRAINED**, not FAIL. Copilot answer quality not overclaimed. |
| Required permissions / prerequisites | Human M365 access to existing Research Hub; Copilot entitlement as licensed. |
| Constraints | No Hub rebuild; no bulk Cards; no Graph expansion; no Power Automate; no ingestion Agent in this milestone. Prefer PDF/file in Sources when rights allow; use URL when rights/storage prefer external canonical. Do not commit redistribution-unclear PDFs to GitHub. |
| Usefulness to Research Hub | Proves manual Capture → Use → selective Promote primitives and Hub surfaces for ongoing research (requirements §§13, FR-HUB, FR-INT-001). |
| Adopt / defer decision | **Adopt** Research Hub corpus workflow for M3 Exit. TBD-002〜004 **decided** from live use — see `docs/decisions/m3-hub-corpus-workflow.md`. Future Agent ingestion/Card automation recorded as opportunity only — **not** implemented. |
| Evidence location (public-safe) | `docs/operations/m3-hub-reconfirm-checklist.md`; this log; `docs/decisions/m3-hub-corpus-workflow.md`. No tenant URLs / site or list IDs / emails / tenant-chrome screenshots. |

### M3 AC summary (public-safe)

| AC | Verdict | Limitation |
|---|---|---|
| AC-HUB-001 | PASS | One-operation evidence: **one direct drag-and-drop** of PDF/file into Sources; no mandatory follow-up. Limitation: URL shortcut path remained ~3 UI steps and is **not** the one-operation evidence. |
| AC-HUB-002 | PASS | Seeds present; Use without Card; ≥1 Used; selective Promote with Source link-back. |
| AC-HUB-003 | PASS with limitation | Search/read/compare/summarize/original-source OK. Card cross-use **CONSTRAINED** (needs explicit Card surface). |
| AC-HUB-004 | PASS | Resume without backlog cleanup. |
| AC-HUB-005 | PASS | Home, Sources, Research Cards, Methodology, Current Findings, M365 Validation Log present. |

## M4 — Graph / Entra minimum SPO connectivity

| Field | Content |
|---|---|
| Date | 2026-08-29 |
| Feature | Microsoft Graph / Entra delegated read smoke against existing SPO site |
| What was tried | (1) Device Code Flow live auth → **AADSTS530035 / BlockedBySecurityDefaults**. (2) Kept Security Defaults enabled; switched to delegated interactive browser + PKCE (`http://localhost`). (3) Human live `thought-flow m4-graph-spo-smoke --live` with delegated **`Sites.Read.All` only**. |
| What worked | **PASS (connectivity).** `status=succeeded`, `auth_mode=delegated_interactive_browser`, `permission_scope=Sites.Read.All`. Operations: authentication, site_resolve, list_enumerate, metadata_read. Target site resolved; list enumeration succeeded; preferred display name `Sources` was found; one list metadata object read. **Do not** treat this as proof of total Lists/Libraries count on the site. |
| What did not work | Device Code Flow under Security Defaults (expected after policy; not reintroduced). |
| Required permissions / prerequisites | Delegated `Sites.Read.All` (public client; interactive browser redirect `http://localhost`; no client secret). **Limitation (CodeX):** acceptable for this bounded Human-operated proof; effective scope is broader than one selected site; future persistent automation may evaluate `Sites.Selected` (not authorized in M4). See `docs/operations/m4-graph-spo-smoke.md`. |
| Constraints | Confirmed: `read_only`, `no_file_body_download`, `no_site_or_list_ids_in_evidence`, `optional_to_local_core`. Security Defaults preserved; no CA exception for Device Code; no write/sync. Failure evidence uses allowlisted classifications only (no upstream `error_description` / URLs / IDs / paths). |
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

- Requirements: `docs/requirements.md` §§13, 14.1, 19.2, FR-HUB-001〜008, FR-INT-001〜002, AC-HUB-001〜005, AC-M365-001〜003
- Plan: `implementation-plan.md` §§5.1 (S1–S3), 6 (M3–M4), 10
- Ops: `docs/operations/m3-hub-reconfirm-checklist.md`, `docs/operations/m4-graph-spo-smoke.md`
- Decisions: `docs/decisions/m3-hub-corpus-workflow.md`, `docs/decisions/m4-auth-interactive-browser.md`
