# M5 Google Trends acquisition (smoke only)

Status: M5 operations utility. **Not** a production Trends connector. **Not** RF final. **Not** M6.

## Architecture (two layers)

### Layer A — TFO Acquisition Contract

Authoritative parameters come **only** from TFO frozen SoT / probes / periods:

- geos, theme probes, `TRENDS-FULL`, category, property, Term mode
- quality / zero semantics (`low_or_insufficient_relative_interest`)

Code: `thought_flow.smoke.trends.acquisition_contract`

### Layer B — Transport

| Transport | Description | Live authorized now? |
|---|---|---|
| **A — Human official UI CSV** | Human downloads CSV; Cursor imports | **YES** (post-download only) |
| **B — Explore/widget CSV** | Warm-up → explore → TIMESERIES request/token → multiline CSV bytes | **NO** until Decision Accepted |

Both must converge on the same CSV validation/import boundary (`csv_import.py`).

### SoT conflict

Frozen [`m5-smoke-spec.md`](../decisions/m5-smoke-spec.md) prohibits undocumented Trends UI/network endpoints and unofficial clients. Transport B uses internal Explore/widget endpoints and therefore **conflicts**. Silent implementation is forbidden.

Proposal (not approved): [`m5-trends-transport-exception-proposal.md`](../decisions/m5-trends-transport-exception-proposal.md)

## Official alpha route

Human confirmed entitlement / application preparation / UI access.

Public docs do **not** publish implementable auth/endpoint/quota/terms.

**Route verdict:** `NOT_IMPLEMENTABLE_FROM_PUBLIC_DOCS` (see `m5-trends-alpha-status`).

## Transport A — Human official UI CSV

For each country `JP|US|KR|CN`:

1. Open official Google Trends UI (Human).
2. Compare the two frozen probes for that country in **one** request (Term mode).
3. Geo = that country; custom range **2022-11-30** through **2026-08-16**; All categories; Web Search.
4. Official **CSV Download** only.
5. Repeat identical export after ≥24 hours and ≤7 days (second observation).

```bash
uv run thought-flow m5-trends-csv-import --country US --csv path/to/export.csv --observation-index 1
```

## Transport B — Explore/widget (gated)

Live calls remain **disabled** (`EXPLORE_WIDGET_LIVE_AUTHORIZED = False`).

Non-live fixture tests cover: `)]}'` prefix strip, TIMESERIES selection, request/token pass-through, HTTP/missing-widget ≠ zero, contract-driven explore body.

Do not persist cookies, auth headers, account/session IDs, or private URLs.

## Invariants

1. One acquisition = one GEO × both TFO theme probes in one comparison.
2. Period/category/property identical across geos for the same observation index.
3. Exact CSV bytes at acquisition boundary (no numeric transform / no `<1` rewrite on capture).
4. Never compare raw 0–100 levels across independent country requests.
5. Failed GEO must not overwrite successful GEO evidence.
6. Source numeric zero → TFO `zero` + `zero_semantics = low_or_insufficient_relative_interest`.

## Decision boundary

- Do not record Trends `SMOKE-PASS` until frozen mandatory evidence (including repeat) exists.
- Production GO: NO
- RF final: NO
- M6 frozen: NO
