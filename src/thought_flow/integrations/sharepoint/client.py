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


def graph_get(
    *,
    path: str,
    access_token: str,
    query: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
) -> GraphHttpResult:
    """GET a Graph path. Does not retain response error bodies for public evidence."""
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
                )
            if not isinstance(payload, (dict, list)):
                return GraphHttpResult(
                    ok=False,
                    status_code=int(status) if status is not None else None,
                    payload=None,
                    error_category="unexpected_payload_type",
                )
            return GraphHttpResult(
                ok=True,
                status_code=int(status) if status is not None else None,
                payload=payload,
                error_category=None,
            )
    except urllib.error.HTTPError as exc:
        # Drain body without retaining it for evidence.
        try:
            exc.read()
        except OSError:
            pass
        return GraphHttpResult(
            ok=False,
            status_code=exc.code,
            payload=None,
            error_category="http_error",
        )
    except urllib.error.URLError:
        return GraphHttpResult(
            ok=False,
            status_code=None,
            payload=None,
            error_category="network_error",
        )
    except TimeoutError:
        return GraphHttpResult(
            ok=False,
            status_code=None,
            payload=None,
            error_category="timeout",
        )
    except Exception:  # noqa: BLE001 — external transport boundary
        return GraphHttpResult(
            ok=False,
            status_code=None,
            payload=None,
            error_category="graph_client_exception",
        )


def site_path_address(hostname: str, site_path: str) -> str:
    """Build Graph site-by-path segment: ``{hostname}:{server-relative-path}``."""
    path = site_path if site_path.startswith("/") else f"/{site_path}"
    return f"{hostname}:{path}"
