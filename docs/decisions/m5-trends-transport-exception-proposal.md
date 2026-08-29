# M5 Trends Acquisition Transport Exception — Proposal

- Status: **PROPOSAL ONLY — NOT APPROVED**. Awaiting Human / Codex review.
- Date: 2026-08-29
- Related PR: [#7](https://github.com/SotaroCraft/thought-flow-observatory/pull/7)
- Frozen SoT unchanged by this file: [`m5-smoke-spec.md`](m5-smoke-spec.md) remains FROZEN (+ Erratum-001) until an approved Erratum / Decision explicitly amends it.
- Scope: Acquisition **transport mechanics** for Google Trends M5 smoke only.

This document does **not** freeze M6 Gate A–E, does **not** decide RF, does **not** assert production `GO`, and does **not** change TFO research semantics (countries, themes, probes, periods, quality states, zero semantics).

---

## 1. SoT conflict (explicit)

Current frozen language prohibits undocumented Trends UI/network endpoints and unofficial clients, including:

- Preflight closed scope: “Unofficial Google Trends libraries and undocumented endpoints are `NO-GO`.” ([`m5-smoke-spec.md`](m5-smoke-spec.md) §3.1)
- UI CSV path: Cursor “MUST NOT automate an undocumented web endpoint or use an unofficial client.” (§6.3)
- Stop/escalation: stop when access would require “an unofficial Trends client, or an undocumented web endpoint.” (§15)
- Self-review: “No unofficial Trends client or scripted undocumented endpoint is permitted.” (§16)

**Proposed Transport B** (operational observation, not TFO research SoT) acquires the same Explore CSV product via:

1. Warm-up `GET https://trends.google.co.jp/trends/`
2. `GET /trends/api/explore`
3. Select widget `id = TIMESERIES`
4. Pass through widget `request` + `token` without semantic modification
5. `GET /trends/api/widgetdata/multiline/csv`
6. Persist exact CSV bytes

**Conflict exists: YES.**  
**Silent implementation / reinterpretation as already permitted: NO.**

“Not pytrends” does **not** equal “documented public API.” Transport B is **not** the official Trends API alpha and is **not** a documented public Google API.

---

## 2. Why an exception might be considered (for reviewers)

Operational arguments **for** a narrow M5-only exception (not a claim of legal/API documentation completeness):

- Reproduces the same official Explore **CSV download product** Human already uses in Transport A, rather than inventing a parallel numeric schema.
- Avoids browser UI automation and avoids the unofficial `pytrends` library.
- Can be bounded to M5 smoke tooling, append-only local evidence, and the existing CSV validation/import boundary from PR #7.
- Keeps TFO Acquisition Contract as the sole authority for geo / terms / dates / category / property / probes.

Operational arguments **against** / residual risks:

- Endpoints are internal Explore/widget routes and may change without notice.
- Not a documented public API; terms/licensing for automated use remain separately evidencable.
- Session/cookie handling risk if mishandled (must never persist secrets).
- Failure modes must remain `fetch_failure` / blocked — never coerced to Trends `zero`.

---

## 3. Proposed Decision text (if approved)

**Title:** M5 Trends acquisition transport exception (Explore/widget CSV)

**If Human / Codex APPROVE**, record an accepted Decision (or smoke-spec Erratum) with **exactly** this scope:

1. **Authorize, for M5 smoke only**, an optional Transport B that fetches official Explore multiline **CSV bytes** via Trends Explore/widget endpoints, solely as an acquisition transport.
2. State explicitly that Transport B is **not** a documented public API and **may change without notice**.
3. State that Transport B failure (HTTP error, missing TIMESERIES widget, 429, parse failure, empty CSV) is **`fetch_failure` / acquisition failure**, **never** a valid Trends numeric `zero`.
4. State that Transport B **MUST NOT** become a production connector, scheduler, cloud dependency, or Canonical/analysis dependency.
5. State that **Transport A (Human official UI CSV Download)** remains the required fallback whenever Transport B is unavailable or unauthorized.
6. State that cookies, auth headers, account/session identifiers, and private URLs **MUST NOT** be persisted in repository or public artifacts; live `request`/`token` material stays local and conservative.
7. State that applicable **terms / licensing / storage / publication** evidence remains a separate Human requirement; this exception does not satisfy licensing by itself.
8. State that this changes **acquisition mechanics only**; TFO research semantics (probes, geos, `TRENDS-FULL`, category/property meaning, quality states, `zero_semantics = low_or_insufficient_relative_interest`, no cross-country level merge) remain unchanged.
9. State that **M6 Gate A–E**, **RF final**, and **production GO** are unchanged by this exception.
10. Require live Transport B to remain **disabled** until this Decision/Erratum is Accepted on `main`.

**If Human / Codex REJECT**, keep Human-CSV-only (Transport A); do not enable Transport B code paths.

---

## 4. Architecture that must accompany any approval

| Layer | Owner | Role |
|---|---|---|
| **A — TFO Acquisition Contract** | TFO SoT / frozen probes & periods | Supplies `obs_id`, geo, term1, term2, date range, category, property, observation index, quality/zero semantics. Transport must not invent these. |
| **B — Transport** | M5 smoke tooling only | A: Human CSV file path; B: Explore/widget → exact CSV bytes (if authorized). |
| **Common import boundary** | Existing PR #7 CSV validate/import | Exact bytes → validate → append-only local run; same zero semantics and privacy rules. |

---

## 5. Current repository posture (pre-approval)

- Transport A: implemented and reviewable.
- Transport B: **designed / fixture-tested only**; **live network acquisition disabled** until this proposal is Accepted.
- Frozen [`m5-smoke-spec.md`](m5-smoke-spec.md): **not silently amended** by this proposal file.

---

## 6. Reviewer checklist

- [ ] Conflict acknowledged (YES)
- [ ] Approve or reject Transport B exception
- [ ] If approve: Accepted Decision/Erratum landed on `main` before first live widget call
- [ ] Confirm research semantics unchanged
- [ ] Confirm Human CSV fallback retained
- [ ] Confirm no production connector / M6 / RF change

M5 TRENDS TRANSPORT EXCEPTION PROPOSAL STATUS: AWAITING HUMAN / CODEX REVIEW
