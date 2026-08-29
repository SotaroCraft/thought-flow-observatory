# M3 Hub reconfirm checklist (Human)

Use this only to reconfirm the **existing** SharePoint Research Hub. Do **not** recreate the site, lists, libraries, or pages unless something is truly missing.

Answer yes / no / unknown (or constrained where noted). Do not paste tenant URLs, site IDs, emails, or screenshots with identifiable tenant chrome into the public repo.

**Reconfirm date:** 2026-08-29  
**Outcome:** Human live reconfirm complete — see `docs/m365-validation.md` §M3 and `docs/decisions/m3-hub-corpus-workflow.md`.

| # | Fact to reconfirm | Answer | Notes (public-safe only) |
|---|---|---|---|
| 1 | The existing TFO Research Hub site is the intended target (same Hub as M4 lead) | yes | Existing Hub only; not rebuilt |
| 2 | A Sources library (or equivalent Capture library) exists | yes | |
| 3 | Copilot can find / read at least one captured Source | yes | Search and reading succeeded |
| 4 | Comparison **and** summarization of Sources were tried at least once | yes | Both succeeded; do not overclaim answer quality |
| 5 | Capture does **not** require immediate Research Card creation | yes | No mandatory tags, classification, summary, or Card |
| 6 | Selective Promote to Research Cards remains usable when wanted | yes | One Card created for Kashima et al. (2019) after Use; Title only mandatory; Card links to original Source |
| 7 | Home / Methodology / Current Findings / M365 Validation Log surfaces exist at least minimally | yes | |
| 8 | Research Cards surface exists and is reachable | yes | Initially zero items; one Card added selectively |
| 9 | Seed sources present: Kashima (2019), Michel (2011), Shiller (2017) | yes | Reused existing captures |
| 10 | New public Source can be Captured without mandatory post-Capture classification | yes | URL shortcut ~3 UI steps; PDF upload also without mandatory structure |
| 11 | Unpromoted Source remains usable (Card not required for Use) | yes | |
| 12 | At least one Source was actually Used (Copilot or research) | yes | Including detailed PDF summary from SPO-stored file |
| 13 | Research Card cross-use with Sources | constrained | Copilot found Source readily; Card discovered reliably only when Research Cards list was explicitly provided. Classification: CONSTRAINED, not FAIL |
| 14 | Original-source checking from Card / Copilot path remains possible | yes | Card links back to SPO Source; PDF body readable when file stored in Sources |
| 15 | Resume after assumed 2-week pause without backlog cleanup | yes | Unstructured Sources and minimal Card metadata left as-is; Copilot located and explained NIST link Source |

## Capture path observations (public-safe)

| Path | Capture load | Copilot body access | Notes |
|---|---|---|---|
| URL / shortcut | Low (~3 UI steps); no mandatory structure | Shortcut discoverable; document body not inside SPO — Copilot needed external access to read | Valid Capture; weaker grounding |
| PDF / file in Sources | Low; no mandatory structure | Copilot read and summarized PDF directly from SPO | Preferred corpus form when redistribution/storage rights allow |

Do **not** commit copyrighted or redistribution-unclear PDFs to GitHub.

After completing this table, update `docs/m365-validation.md` §M3 with date and adopt/defer — still without secrets.

Related requirements: FR-HUB-001〜008, FR-INT-001, AC-HUB-001〜005, TBD-002〜004.
