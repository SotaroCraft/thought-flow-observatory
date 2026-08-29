# M4 Graph → SPO smoke (Human gate)

Bounded proof: Entra delegated auth → Microsoft Graph → resolve existing TFO site → enumerate lists/libraries → read one non-sensitive list metadata object.

Graph remains **optional**. Local Raw / smoke must work with SharePoint disabled.

## Auth mode (current)

- **Delegated** `Sites.Read.All`
- **Public client** (no client secret)
- **Interactive browser + PKCE** via MSAL `acquire_token_interactive`
- Redirect URI: `http://localhost` (Mobile and desktop applications platform)

### Observed Device Code Flow blocker (do not reintroduce without policy change)

Live attempt with Device Code Flow returned **AADSTS530035 / Error 530035 / BlockedBySecurityDefaults**. That is a **tenant authentication constraint**, not a SharePoint permission failure. Admin consent for delegated `Sites.Read.All` did not change the Device Code result.

**Program decision:** keep Security Defaults enabled; do **not** add Conditional Access exceptions merely to preserve Device Code Flow; do **not** broaden Graph permissions. Adapt the app to interactive browser auth instead. See `docs/decisions/m4-auth-interactive-browser.md`.

## Exact Entra app registration steps

1. Open **Microsoft Entra admin center** → **App registrations** → select the existing TFO smoke app (or **New registration** if creating fresh).
2. Supported account types: **Accounts in this organizational directory only** (single tenant).
3. Copy **Application (client) ID** into local `.env` as `THOUGHT_FLOW_GRAPH_CLIENT_ID` (do not paste into chat or Git).
4. Copy **Directory (tenant) ID** into local `.env` as `THOUGHT_FLOW_GRAPH_TENANT_ID` (do not paste into chat or Git).
5. **Authentication** → **Add a platform** → **Mobile and desktop applications** → enable / add redirect URI **`http://localhost`** → Save.
6. **Authentication** → **Advanced settings** → **Allow public client flows** = **Yes** → Save (public client; still **no** client secret).
7. **API permissions** → Microsoft Graph → **Delegated** → **`Sites.Read.All`** only. Do not add write scopes.
8. Consent: Graph marks delegated **`Sites.Read.All`** as **AdminConsentRequired: No**. Normal **user consent** during interactive sign-in is sufficient when tenant user-consent policy allows it. If policy blocks user consent, Human/Admin grants consent for the app — then retry. If consent remains blocked, record BLOCKED — do **not** escalate to write scopes.
9. Do **not** create a client secret.
10. Do **not** disable Security Defaults to make Device Code Flow work.

### Do not request for this proof

- `Sites.ReadWrite.All`
- `Sites.FullControl.All`
- Application permissions (unless delegated path is proven impossible — escalate instead of improvising)
- Client secrets / certificates for this read-only public-client smoke
- Disabling Security Defaults or CA exceptions solely for Device Code Flow

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

After the **`http://localhost`** redirect URI is saved on the app:

```bash
uv sync --extra sharepoint
uv run thought-flow m4-graph-spo-smoke
uv run thought-flow m4-graph-spo-smoke --live
```

Without `--live`, the command only checks configuration readiness.

With `--live`, complete sign-in in the **system browser**, then the CLI performs:

1. token acquisition (delegated interactive + PKCE)
2. site resolve by hostname + path
3. list/library enumerate
4. one list metadata read (`$select` only; no file body download)

Sanitized JSON is printed and may be written under the gitignored local data root at `m4-smoke/` (default under `workspace-data/`). **Do not commit** that file or paste machine-specific absolute paths into the public repo. Public-safe evidence lives in `docs/m365-validation.md` §M4.

## Live result (2026-08-29)

**M4 SPO PROGRAMMATIC CONNECTIVITY: PASS**

- `status=succeeded`
- `auth_mode=delegated_interactive_browser`
- `permission_scope=Sites.Read.All`
- Operations: authentication, site_resolve, list_enumerate, metadata_read
- List enumeration succeeded; preferred library display name `Sources` was found; metadata read succeeded
- Do **not** interpret the live evidence as a total Lists/Libraries inventory count
- Constraints confirmed: read_only; no file body download; no site/list IDs in evidence; Graph optional to local core
- Prior Device Code attempt: AADSTS530035 / Security Defaults (defaults **not** disabled)
- Permission limitation: delegated `Sites.Read.All` accepted for this bounded Human-operated proof; broader than one site; `Sites.Selected` may be evaluated later for persistent automation (not in M4)
- Manual SPO fallback remains valid
- Public-safe failure evidence is allowlisted (classifications / HTTP status / completed ops only)

## Manual fallback

If Graph auth or consent fails: continue Capture / Copilot / Pages manually in SPO. Record the blocker; do not treat Graph as required for local quantitative work.
