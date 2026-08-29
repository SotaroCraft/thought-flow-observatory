# M4 auth: interactive browser instead of Device Code Flow

| Field | Content |
|---|---|
| Date | 2026-08-29 |
| Status | Accepted |
| Milestone | M4 Graph / Entra minimum SPO connectivity |
| Related | FR-INT-002, AC-M365-001, `docs/operations/m4-graph-spo-smoke.md` |

## Context

The M4 smoke initially used MSAL public-client **Device Code Flow**. A live attempt against the project tenant failed with **AADSTS530035 / Error 530035 / BlockedBySecurityDefaults**. This occurred even after admin consent for delegated `Sites.Read.All`. The failure is an **authentication / Security Defaults** constraint, not a SharePoint Graph permission gap.

## Decision

1. **Do not** disable Security Defaults.
2. **Do not** add Conditional Access exceptions merely to preserve Device Code Flow.
3. **Do not** broaden Graph permissions beyond delegated `Sites.Read.All`.
4. **Replace** Device Code Flow with MSAL **`acquire_token_interactive`** (system browser + PKCE) on the same public-client app.
5. Register redirect URI **`http://localhost`** under **Mobile and desktop applications**.

## Consequences

- Human registers `http://localhost` on the Entra app (Mobile and desktop applications).
- Security Defaults remain the tenant baseline; the application adapts.
- Manual SPO Capture / Pages remain the fallback if Graph is unavailable.

## Live validation (2026-08-29)

Human-operated interactive smoke **succeeded** (`auth_mode=delegated_interactive_browser`, scope `Sites.Read.All`): authentication → site_resolve → list_enumerate → metadata_read. Security Defaults were **not** disabled. See `docs/m365-validation.md` §M4. Program status: **M4 SPO PROGRAMMATIC CONNECTIVITY: PASS**.

Permission note: delegated `Sites.Read.All` is accepted for this bounded Human-operated proof with the limitation that effective scope is broader than one selected site; future persistent automation may evaluate `Sites.Selected` (out of scope for M4).

## Non-goals

- Client secrets / confidential client
- Application permissions or write scopes
- Sync / provisioning / PnP
