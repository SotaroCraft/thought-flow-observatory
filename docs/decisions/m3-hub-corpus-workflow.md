# M3 — Research Hub corpus workflow (TBD-002〜004)

| Field | Content |
|---|---|
| Date | 2026-08-29 |
| Status | Accepted (from Human live reconfirm) |
| Milestone | M3 SharePoint Research Hub MVP / corpus workflow |
| Related | FR-HUB-001〜008, FR-INT-001, AC-HUB-001〜005, TBD-002〜004; `docs/operations/m3-hub-reconfirm-checklist.md`; `docs/m365-validation.md` §M3 |

## Context

M3 Exit requires AC-HUB-001〜005 evidence and TBD-002〜004 decided or deferred from **actual Hub use**, not desk design. Human reconfirmed the existing Research Hub on 2026-08-29. Hub was **not** rebuilt. No Graph permission expansion, Power Automate, bulk Card generation, or ingestion Agent was added.

## TBD-002 — Research Card MVP fields

**Decision:** Keep Human-facing Card **minimal**.

Mandatory at MVP:

- Title
- Source / original reference (link back to the SPO Source or public reference)

Optional / future enrichment (not mandatory for M3):

- Summary, Why it matters, relationships, and other candidate fields from `docs/requirements.md` §12.7

**Rationale:** Live Promote succeeded with **Title** as the only mandatory SPO field; Card linked to the original Source; Human found creation easy. Adding many mandatory fields would violate Capture/Promote usability (R-001 / §16.2). Future Agent-generated enrichment is out of M3 scope.

## TBD-003 — file vs link boundary

**Decision:**

1. Prefer **PDF/file in Sources** as the normal corpus form when legally and technically appropriate (redistribution/storage rights allow).
2. Use **URL/link (shortcut)** when redistribution/storage rights are uncertain, file storage is inappropriate, or keeping an external canonical location is preferable.
3. **Do not** commit copyrighted or redistribution-unclear PDFs to the public Git repository.

**Rationale:** URL Capture was easy and discoverable, but the shortcut did not expose document body inside SPO; Copilot needed external access to read. A public research PDF stored in Sources allowed Copilot to read and summarize directly — stronger source-grounded Use.

## TBD-004 — Captured / Used / Promoted

**Decision:** Treat these as **semantic states**, not Capture-time mandatory status fields.

| State | Meaning (SoT-aligned) |
|---|---|
| Captured | Source exists in Sources |
| Used | Source was actually consumed by Copilot or Human research |
| Promoted | Human selected a valuable Source and created a Research Card |

**Rules:**

- Do **not** require status updates during Capture.
- Do **not** require a Card for Use.
- M3 remains valid without Agent automation that updates metadata/state.
- Future automation may maintain state markers; that is not required to close M3.

**Rationale:** Observed workflow matched FR-HUB-002〜004: Capture without structure, Use without Card, selective Promote of one valued seed (Kashima et al., 2019).

## Future automation (explicitly out of M3 scope)

Recorded desire (not implemented):

Human literature list → Agent resolves DOI/URL → retrieves legally usable PDF when possible → normalizes metadata → uploads to Sources → generates Research Card linked to Source → Copilot as user-facing interface → SPO as corpus backend.

M3 only proves the **manual primitives** that architecture would automate. Do not implement the Agent in the M3 evidence PR.

## Non-goals

- Rebuilding the Hub or duplicating Sources / Research Cards / Pages
- Bulk Research Card generation
- Graph permission expansion or write/sync
- Power Automate or ingestion pipelines
- Committing tenant URLs, entity IDs, or private SharePoint identifiers
