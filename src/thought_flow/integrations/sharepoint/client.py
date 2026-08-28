"""Minimal Microsoft Graph HTTP helpers for the M4 SPO smoke."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass(frozen=True)
class GraphHttpResult:
    ok: bool
    status_code: int | None
    payload: dict[str, Any] | list[Any] | None
    error_category: str | None
    error_message: str | None


def graph_get(
    *,
    path: str,
    access_token: str,
    query: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> GraphHttpResult:
    """GET a Graph path. Does not log Authorization headers or bodies with secrets."""
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = getattr(response, "status", None) or response.getcode()
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return GraphHttpResult(
                    ok=False,
                    status_code=int(status) if status is not None else None,
                    payload=None,
                    error_category="invalid_json",
                    error_message="Graph response was not valid JSON",
                )
            if not isinstance(payload, (dict, list)):
                return GraphHttpResult(
                    ok=False,
                    status_code=int(status) if status is not None else None,
                    payload=None,
                    error_category="unexpected_payload_type",
                    error_message="Graph response JSON was not an object or array",
                )
            return GraphHttpResult(
                ok=True,
                status_code=int(status) if status is not None else None,
                payload=payload,
                error_category=None,
                error_message=None,
            )
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except OSError:
            body = ""
        message = _summarize_http_error(exc.code, body)
        return GraphHttpResult(
            ok=False,
            status_code=exc.code,
            payload=None,
            error_category="http_error",
            error_message=message,
        )
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return GraphHttpResult(
            ok=False,
            status_code=None,
            payload=None,
            error_category="network_error",
            error_message=str(reason)[:240],
        )
    except TimeoutError:
        return GraphHttpResult(
            ok=False,
            status_code=None,
            payload=None,
            error_category="timeout",
            error_message="Graph request timed out",
        )


def site_path_address(hostname: str, site_path: str) -> str:
    """Build Graph site-by-path segment: ``{hostname}:{server-relative-path}``."""
    path = site_path if site_path.startswith("/") else f"/{site_path}"
    # urllib will encode the colon path; pass as raw path segment.
    return f"{hostname}:{path}"


def _summarize_http_error(status: int, body: str) -> str:
    code = None
    message = None
    if body:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict):
                code = err.get("code")
                message = err.get("message")
    parts = [f"HTTP {status}"]
    if code:
        parts.append(f"code={code}")
    if message:
        text = str(message).replace("\n", " ").strip()
        parts.append(f"message={text[:200]}")
    return "; ".join(parts)
