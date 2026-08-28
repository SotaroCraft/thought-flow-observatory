# M4 Graph → SPO smoke (Human gate)

Bounded proof: Entra delegated auth → Microsoft Graph → resolve existing TFO site → enumerate lists/libraries → read one non-sensitive list metadata object.

Graph remains **optional**. Local Raw / smoke must work with SharePoint disabled.

## Exact Entra app registration steps

1. Open **Microsoft Entra admin center** → **App registrations** → **New registration**.
2. Name: e.g. `TFO Graph SPO Smoke` (local PoC).
3. Supported account types: **Accounts in this organizational directory only** (single tenant).
4. Redirect URI: leave empty for device-code (public client). Click **Register**.
5. Copy **Application (client) ID** into local `.env` as `THOUGHT_FLOW_GRAPH_CLIENT_ID` (do not paste into chat or Git).
6. Copy **Directory (tenant) ID** into local `.env` as `THOUGHT_FLOW_GRAPH_TENANT_ID` (do not paste into chat or Git).
7. **Authentication** → **Advanced settings** → **Allow public client flows** = **Yes** → Save.
8. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions** → add **`Sites.Read.All`** only for this smoke.
9. Consent: Microsoft Graph marks delegated **`Sites.Read.All`** as **AdminConsentRequired: No**. Normal **user consent** during device-code sign-in is sufficient when the tenant’s user-consent policy allows it. If tenant policy blocks user consent, a Human/Admin must grant consent for the app — then retry. If consent remains blocked, stop and record BLOCKED in `docs/m365-validation.md`. Do **not** escalate to write scopes.
10. Do **not** create a client secret for this smoke. Auth mode remains **public client + device code flow**.

### Do not request for this proof

- `Sites.ReadWrite.All`
- `Sites.FullControl.All`
- Application permissions (unless delegated path is proven impossible — escalate instead of improvising)
- Client secrets / certificates for this read-only public-client smoke

## Local `.env` variable names

Copy from `.env.example`. Assignments stay empty in Git; fill only local `.env`:

| Name | Form |
|---|---|
| `THOUGHT_FLOW_ENABLE_SHAREPOINT` | `true` |
| `THOUGHT_FLOW_GRAPH_CLIENT_ID` | Entra application (client) ID |
| `THOUGHT_FLOW_GRAPH_TENANT_ID` | Entra directory (tenant) ID |
| `THOUGHT_FLOW_SPO_HOSTNAME` | Hostname only, e.g. `contoso.sharepoint.com` |
| `THOUGHT_FLOW_SPO_SITE_PATH` | Server-relative site path, e.g. `/sites/YourResearchHub` |

Optional dependency:

```bash
uv sync --extra sharepoint
```

## First live command after config

```bash
uv run thought-flow m4-graph-spo-smoke
uv run thought-flow m4-graph-spo-smoke --live
```

Without `--live`, the command only checks configuration readiness.

With `--live`, complete the device-code prompt in the browser, then the CLI performs:

1. token acquisition (delegated)
2. site resolve by hostname + path
3. list/library enumerate
4. one list metadata read (`$select` only; no file body download)

Sanitized JSON is printed and also written under gitignored `workspace-data/m4-smoke/` (default data root). **Do not commit** that file. Update `docs/m365-validation.md` §M4 with public-safe PASS/BLOCKED fields only.

## Manual fallback

If Graph auth or consent fails: continue Capture / Copilot / Pages manually in SPO. Record the blocker; do not treat Graph as required for local quantitative work.
