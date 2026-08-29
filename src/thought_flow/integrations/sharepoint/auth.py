"""Delegated MSAL auth for Graph SPO smoke. Never log token contents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from thought_flow.integrations.sharepoint.sanitize import classify_msal_error_payload

# Delegated read-only SharePoint site/list access for the bounded smoke.
GRAPH_SCOPES: tuple[str, ...] = ("Sites.Read.All",)
AUTH_MODE = "delegated_interactive_browser"
# Public-client desktop redirect registered in Entra (any localhost port accepted).
PUBLIC_CLIENT_REDIRECT_URI = "http://localhost"


@dataclass(frozen=True)
class TokenAcquisitionResult:
    ok: bool
    access_token: str | None
    error_classification: str | None


class MsalUnavailableError(RuntimeError):
    """Raised when the optional ``msal`` dependency is not installed."""


def _import_msal() -> Any:
    try:
        import msal  # type: ignore[import-untyped]
    except ImportError as exc:
        raise MsalUnavailableError(
            "Optional dependency 'msal' is required for live Graph smoke. "
            "Install with: pip install 'thought-flow[sharepoint]' "
            "or: uv sync --extra sharepoint"
        ) from exc
    return msal


def acquire_delegated_token_interactive(
    *,
    client_id: str,
    authority: str,
    scopes: tuple[str, ...] = GRAPH_SCOPES,
    prompt: Callable[[str], None] | None = None,
) -> TokenAcquisitionResult:
    """Acquire a Graph token via public-client interactive browser + PKCE.

    Uses the system browser and ``http://localhost`` redirect (no client secret).
    Access tokens are returned only in memory and must not be logged.

    Failures return a stable ``error_classification`` only — never upstream
    ``error_description``, URLs, codes, or trace identifiers for public evidence.
    """
    try:
        msal = _import_msal()
    except MsalUnavailableError:
        raise

    try:
        app = msal.PublicClientApplication(client_id, authority=authority)
    except Exception:  # noqa: BLE001 — external SDK boundary
        return TokenAcquisitionResult(
            ok=False,
            access_token=None,
            error_classification="msal_constructor_failed",
        )

    accounts: list[Any] = []
    try:
        accounts = list(app.get_accounts() or [])
    except Exception:  # noqa: BLE001 — external SDK boundary
        return TokenAcquisitionResult(
            ok=False,
            access_token=None,
            error_classification="msal_account_lookup_failed",
        )

    if accounts:
        try:
            silent = app.acquire_token_silent(list(scopes), account=accounts[0])
        except Exception:  # noqa: BLE001 — external SDK boundary
            return TokenAcquisitionResult(
                ok=False,
                access_token=None,
                error_classification="msal_silent_failed",
            )
        if silent and "access_token" in silent:
            return TokenAcquisitionResult(
                ok=True,
                access_token=silent["access_token"],
                error_classification=None,
            )

    (prompt or print)(
        "Opening the system browser for interactive Microsoft sign-in "
        f"(redirect {PUBLIC_CLIENT_REDIRECT_URI}; PKCE public client)."
    )

    try:
        result = app.acquire_token_interactive(scopes=list(scopes))
    except Exception:  # noqa: BLE001 — external SDK boundary
        return TokenAcquisitionResult(
            ok=False,
            access_token=None,
            error_classification="msal_interactive_failed",
        )

    if result and "access_token" in result:
        return TokenAcquisitionResult(
            ok=True,
            access_token=result["access_token"],
            error_classification=None,
        )

    return TokenAcquisitionResult(
        ok=False,
        access_token=None,
        error_classification=classify_msal_error_payload(result),
    )
