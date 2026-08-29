"""Public-safe sanitization for Graph smoke evidence (allowlist model)."""

from __future__ import annotations

import re
from typing import Any

# Evidence marked public_safe=true may only retain these top-level keys on failure.
_FAILURE_ALLOWLIST = frozenset(
    {
        "status",
        "live",
        "checked_at",
        "auth_mode",
        "permission_scope",
        "failure_category",
        "error_classification",
        "http_status",
        "completed_operations",
        "manual_fallback",
        "public_safe",
    }
)

_SUCCESS_ALLOWLIST = frozenset(
    {
        "status",
        "live",
        "checked_at",
        "auth_mode",
        "permission_scope",
        "graph_operation_categories",
        "operations",
        "constraints",
        "manual_fallback",
        "public_safe",
        "evidence_locator",
    }
)

_OPERATION_ALLOWLIST = frozenset(
    {
        "category",
        "result",
        "mode",
        "display_name_present",
        "name_present",
        "returned_list_count",
        "preferred_found",
        "preferred_display_name",
        "object_kind",
        "template_present",
    }
)

# Stable classifications only — never copy upstream free text into evidence.
_KNOWN_CLASSIFICATIONS = frozenset(
    {
        "invalid_client",
        "consent_or_access_denied",
        "security_defaults_blocked",
        "token_acquisition_failed",
        "msal_unavailable",
        "msal_constructor_failed",
        "msal_account_lookup_failed",
        "msal_silent_failed",
        "msal_interactive_failed",
        "graph_unauthorized",
        "graph_forbidden",
        "graph_http_error",
        "graph_network_error",
        "graph_timeout",
        "graph_invalid_json",
        "graph_unexpected_payload",
        "graph_client_exception",
        "site_resolve_failed",
        "list_enumerate_failed",
        "metadata_read_failed",
        "unexpected_response",
        "no_list_found",
        "dependency_missing",
        "authentication_failed",
        "unknown_failure",
    }
)

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_SHAREPOINT_URL_RE = re.compile(r"https?://[^\s\"']+\.sharepoint\.com[^\s\"']*", re.I)
_CODE_QUERY_RE = re.compile(r"(?i)([?&]code=)[^&\s\"']+")
_WIN_PATH_RE = re.compile(r"(?i)\b[a-z]:\\[^\s\"']+")
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*")


def classify_msal_error_payload(payload: Any) -> str:
    """Map MSAL result dict to a stable classification (no free-text copy)."""
    if not isinstance(payload, dict):
        return "token_acquisition_failed"
    codes = payload.get("error_codes")
    code_list: list[Any] = list(codes) if isinstance(codes, list) else []
    if 530035 in code_list or "530035" in {str(c) for c in code_list}:
        return "security_defaults_blocked"
    err = str(payload.get("error") or "").strip().lower()
    if err in {"invalid_client", "unauthorized_client"}:
        return "invalid_client"
    if err in {"access_denied", "consent_required", "interaction_required"}:
        return "consent_or_access_denied"
    if err:
        # Keep only the short OAuth error code token when it is a simple slug.
        if re.fullmatch(r"[a-z0-9_.-]{1,64}", err):
            if err in _KNOWN_CLASSIFICATIONS:
                return err
            return "token_acquisition_failed"
    return "token_acquisition_failed"


def classify_graph_failure(
    *,
    status_code: int | None,
    error_category: str | None,
) -> str:
    """Map Graph client failure to a stable classification."""
    if status_code == 401:
        return "graph_unauthorized"
    if status_code == 403:
        return "graph_forbidden"
    category = (error_category or "").strip().lower()
    mapping = {
        "http_error": "graph_http_error",
        "network_error": "graph_network_error",
        "timeout": "graph_timeout",
        "invalid_json": "graph_invalid_json",
        "unexpected_payload_type": "graph_unexpected_payload",
        "graph_client_exception": "graph_client_exception",
    }
    if category in mapping:
        return mapping[category]
    return "graph_http_error"


def normalize_classification(value: str | None) -> str:
    text = (value or "").strip()
    if text in _KNOWN_CLASSIFICATIONS:
        return text
    return "unknown_failure"


def public_safe_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Allowlist evidence for repository / CLI JSON marked public_safe=true."""
    status = payload.get("status")
    if status == "failed":
        out: dict[str, Any] = {}
        for key in _FAILURE_ALLOWLIST:
            if key not in payload:
                continue
            value = payload[key]
            if key == "error_classification":
                out[key] = normalize_classification(str(value) if value is not None else None)
            elif key == "http_status":
                if isinstance(value, int):
                    out[key] = value
            elif key == "completed_operations":
                if isinstance(value, list):
                    out[key] = [str(item) for item in value if isinstance(item, (str, int))]
            elif key in {"status", "auth_mode", "permission_scope", "failure_category", "manual_fallback"}:
                out[key] = str(value)
            elif key in {"live", "public_safe"}:
                out[key] = bool(value)
            elif key == "checked_at":
                out[key] = str(value)
        out.setdefault("public_safe", True)
        out.setdefault("status", "failed")
        return out

    if status == "succeeded":
        out = {}
        for key in _SUCCESS_ALLOWLIST:
            if key not in payload:
                continue
            value = payload[key]
            if key == "operations" and isinstance(value, list):
                out[key] = [_sanitize_operation(item) for item in value if isinstance(item, dict)]
            elif key == "graph_operation_categories" and isinstance(value, list):
                out[key] = [str(item) for item in value]
            elif key == "constraints" and isinstance(value, list):
                out[key] = [str(item) for item in value]
            elif key == "evidence_locator":
                # Relative locator only — never absolute machine paths.
                text = str(value).replace("\\", "/")
                if re.match(r"^[A-Za-z]:/", text) or text.startswith("/"):
                    out[key] = "m4-smoke/m4_graph_spo_smoke_latest.json"
                else:
                    out[key] = text
            elif key in {"live", "public_safe"}:
                out[key] = bool(value)
            else:
                out[key] = value if not isinstance(value, (dict, list)) else value
                if key in {
                    "status",
                    "checked_at",
                    "auth_mode",
                    "permission_scope",
                    "manual_fallback",
                }:
                    out[key] = str(value)
        out.setdefault("public_safe", True)
        return out

    # Preflight / non-live summaries: strip obviously hostile strings if present.
    return _scrub_strings({k: v for k, v in payload.items() if k != "access_token"})


def _sanitize_operation(op: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in op.items():
        if key not in _OPERATION_ALLOWLIST:
            continue
        if key == "preferred_display_name" and isinstance(value, str):
            # Allow short non-URL library labels only (e.g. Sources).
            if _looks_hostile(value) or len(value) > 80:
                cleaned["preferred_display_name_present"] = True
            else:
                cleaned[key] = value
        elif key in {"returned_list_count"} and isinstance(value, int):
            cleaned[key] = value
        elif key in {"display_name_present", "name_present", "preferred_found", "template_present"}:
            cleaned[key] = bool(value)
        else:
            cleaned[key] = str(value) if not isinstance(value, (bool, int)) else value
    return cleaned


def _scrub_strings(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            out[key] = _scrub_strings(value)
        elif isinstance(value, list):
            out[key] = [
                _scrub_strings(item) if isinstance(item, dict) else _scrub_one(item) for item in value
            ]
        else:
            out[key] = _scrub_one(value)
    return out


def _scrub_one(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value
    text = _JWT_RE.sub("[REDACTED_JWT]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = _SHAREPOINT_URL_RE.sub("[REDACTED_URL]", text)
    text = _CODE_QUERY_RE.sub(r"\1[REDACTED]", text)
    text = _UUID_RE.sub("[REDACTED_UUID]", text)
    text = _WIN_PATH_RE.sub("[REDACTED_PATH]", text)
    return text


def _looks_hostile(value: str) -> bool:
    return bool(
        _UUID_RE.search(value)
        or _SHAREPOINT_URL_RE.search(value)
        or _CODE_QUERY_RE.search(value)
        or _JWT_RE.search(value)
        or _BEARER_RE.search(value)
        or _WIN_PATH_RE.search(value)
        or "trace" in value.lower()
        or "correlation" in value.lower()
    )


def redact_secrets(text: str) -> str:
    """Best-effort scrub for non-persisted local troubleshooting strings only."""
    return str(_scrub_one(text))


# Back-compat alias used by older call sites / tests.
def sanitize_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    return public_safe_evidence(payload)
