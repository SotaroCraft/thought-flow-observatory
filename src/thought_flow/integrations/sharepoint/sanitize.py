"""Public-safe sanitization for Graph smoke evidence."""

from __future__ import annotations

from typing import Any

# Fields that must never appear in persisted smoke evidence.
_BLOCKED_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "password",
    "authorization",
    "mail",
    "userprincipalname",
    "userid",
    "createdby",
    "lastmodifiedby",
    "email",
}


def sanitize_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe to print or write under workspace-data."""
    return _walk(payload)  # type: ignore[return-value]


def _walk(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_l = str(key).lower()
            if key_l in _BLOCKED_KEYS or any(
                token in key_l for token in ("token", "secret", "password", "authorization")
            ):
                out[str(key)] = "[REDACTED]"
                continue
            # Graph resource IDs are tenant-specific; record presence only.
            if key_l in {"id", "siteid", "listid", "driveid", "itemid"} and isinstance(item, str):
                out[f"{key}_present"] = bool(item.strip())
                continue
            out[str(key)] = _walk(item)
        return out
    if isinstance(value, list):
        return [_walk(item) for item in value]
    if isinstance(value, str) and value.startswith("eyJ") and value.count(".") >= 2:
        return "[REDACTED_JWT]"
    return value
