"""Delegated MSAL auth for Graph SPO smoke. Never log token contents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Delegated read-only SharePoint site/list access for the bounded smoke.
GRAPH_SCOPES: tuple[str, ...] = ("Sites.Read.All",)


@dataclass(frozen=True)
class TokenAcquisitionResult:
    ok: bool
    access_token: str | None
    error_code: str | None
    error_message: str | None


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


def acquire_delegated_token_device_code(
    *,
    client_id: str,
    authority: str,
    scopes: tuple[str, ...] = GRAPH_SCOPES,
    prompt: Callable[[str], None] | None = None,
) -> TokenAcquisitionResult:
    """Acquire a Graph token via public-client device code flow.

    The device-code user message is shown via ``prompt`` (default: print).
    Access tokens are returned only in memory and must not be logged.
    """
    msal = _import_msal()
    app = msal.PublicClientApplication(client_id, authority=authority)

    accounts = app.get_accounts()
    if accounts:
        silent = app.acquire_token_silent(list(scopes), account=accounts[0])
        if silent and "access_token" in silent:
            return TokenAcquisitionResult(
                ok=True,
                access_token=silent["access_token"],
                error_code=None,
                error_message=None,
            )

    flow = app.initiate_device_flow(scopes=list(scopes))
    if "user_code" not in flow:
        return TokenAcquisitionResult(
            ok=False,
            access_token=None,
            error_code="device_flow_init_failed",
            error_message=_safe_error_message(flow),
        )

    message = str(flow.get("message") or "Complete device login in the browser.")
    (prompt or print)(message)

    result = app.acquire_token_by_device_flow(flow)
    if result and "access_token" in result:
        return TokenAcquisitionResult(
            ok=True,
            access_token=result["access_token"],
            error_code=None,
            error_message=None,
        )

    return TokenAcquisitionResult(
        ok=False,
        access_token=None,
        error_code=str(result.get("error") or "token_acquisition_failed")
        if isinstance(result, dict)
        else "token_acquisition_failed",
        error_message=_safe_error_message(result),
    )


def _safe_error_message(payload: Any) -> str:
    """Build a short error string without echoing tokens or large blobs."""
    if not isinstance(payload, dict):
        return "authentication_failed"
    parts: list[str] = []
    for key in ("error", "error_description", "message", "error_codes"):
        if key not in payload:
            continue
        value = payload[key]
        text = str(value).replace("\n", " ").strip()
        # Hard cap; never include fields that look like credentials.
        if any(token in key.lower() for token in ("token", "secret", "password")):
            continue
        if len(text) > 240:
            text = text[:240] + "…"
        parts.append(f"{key}={text}")
    return "; ".join(parts) if parts else "authentication_failed"


def redact_secrets(text: str) -> str:
    """Best-effort redaction if a token accidentally enters a string."""
    import re

    redacted = text
    # JWT-shaped blobs
    redacted = re.sub(
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "[REDACTED_JWT]",
        redacted,
    )
    redacted = re.sub(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer [REDACTED]", redacted)
    return redacted
