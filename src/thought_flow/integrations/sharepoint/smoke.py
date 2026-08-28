"""Bounded Graph → SPO read smoke (M4). Optional; never touches local Raw."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from thought_flow.integrations.sharepoint.auth import (
    AUTH_MODE,
    GRAPH_SCOPES,
    MsalUnavailableError,
    acquire_delegated_token_interactive,
    redact_secrets,
)
from thought_flow.integrations.sharepoint.client import graph_get, site_path_address
from thought_flow.integrations.sharepoint.config import GraphSmokeConfig, load_graph_smoke_config
from thought_flow.integrations.sharepoint.sanitize import sanitize_evidence

GetFn = Callable[..., Any]
AcquireFn = Callable[..., Any]


@dataclass(frozen=True)
class SmokeDependencies:
    acquire_token: AcquireFn = acquire_delegated_token_interactive
    graph_get: GetFn = graph_get


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def preflight(config: GraphSmokeConfig | None = None) -> dict[str, Any]:
    """Deterministic readiness check without network or auth."""
    cfg = config or load_graph_smoke_config()
    if not cfg.enable_sharepoint:
        return {
            "status": "disabled",
            "reason": "THOUGHT_FLOW_ENABLE_SHAREPOINT is not enabled",
            "auth_mode": AUTH_MODE,
            "permission_scope": GRAPH_SCOPES[0],
            "live": False,
        }
    missing = cfg.missing_required()
    if missing:
        return {
            "status": "not_configured",
            "reason": "Missing required environment variables",
            "missing": missing,
            "auth_mode": AUTH_MODE,
            "permission_scope": GRAPH_SCOPES[0],
            "live": False,
        }
    return {
        "status": "ready",
        "reason": "Config present; pass --live to run delegated Graph smoke",
        "auth_mode": AUTH_MODE,
        "permission_scope": GRAPH_SCOPES[0],
        "spo_hostname_configured": True,
        "spo_site_path_configured": True,
        "live": False,
    }


def run_graph_spo_smoke(
    *,
    live: bool = False,
    config: GraphSmokeConfig | None = None,
    deps: SmokeDependencies | None = None,
    prompt: Callable[[str], None] | None = None,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Run preflight or live bounded Graph SPO smoke.

    Live path: interactive browser auth → site resolve → list enumerate → one metadata read.
    Failures are explicit and never write to Raw.
    """
    cfg = config or load_graph_smoke_config()
    summary = preflight(cfg)
    if not live:
        return summary
    if summary["status"] != "ready":
        summary["live"] = True
        return summary

    dependencies = deps or SmokeDependencies()
    operations: list[dict[str, Any]] = []
    try:
        token = dependencies.acquire_token(
            client_id=cfg.client_id or "",
            authority=cfg.authority or "",
            scopes=GRAPH_SCOPES,
            prompt=prompt,
        )
    except MsalUnavailableError as exc:
        return _failure(
            category="dependency_missing",
            message=str(exc),
            operations=operations,
        )

    if not token.ok or not token.access_token:
        return _failure(
            category="authentication_failed",
            message=redact_secrets(token.error_message or token.error_code or "auth_failed"),
            operations=operations,
            extra={"auth_error_code": token.error_code},
        )
    operations.append({"category": "authentication", "result": "ok", "mode": AUTH_MODE})

    access_token = token.access_token
    try:
        site_segment = site_path_address(cfg.spo_hostname or "", cfg.spo_site_path or "")
        site_result = dependencies.graph_get(
            path=f"sites/{site_segment}",
            access_token=access_token,
            query={"$select": "id,displayName,name,webUrl"},
        )
        if not site_result.ok or not isinstance(site_result.payload, dict):
            return _failure(
                category=site_result.error_category or "site_resolve_failed",
                message=redact_secrets(site_result.error_message or "site_resolve_failed"),
                operations=operations,
                extra={"http_status": site_result.status_code},
            )

        site = site_result.payload
        site_id = site.get("id")
        if not isinstance(site_id, str) or not site_id.strip():
            return _failure(
                category="unexpected_response",
                message="Site payload missing id",
                operations=operations,
            )
        operations.append(
            {
                "category": "site_resolve",
                "result": "ok",
                "display_name_present": bool(str(site.get("displayName") or "").strip()),
                "name_present": bool(str(site.get("name") or "").strip()),
            }
        )

        lists_result = dependencies.graph_get(
            path=f"sites/{site_id}/lists",
            access_token=access_token,
            query={"$select": "id,displayName,name,list", "$top": "20"},
        )
        if not lists_result.ok or not isinstance(lists_result.payload, dict):
            return _failure(
                category=lists_result.error_category or "list_enumerate_failed",
                message=redact_secrets(lists_result.error_message or "list_enumerate_failed"),
                operations=operations,
                extra={"http_status": lists_result.status_code},
            )

        values = lists_result.payload.get("value")
        if not isinstance(values, list):
            return _failure(
                category="unexpected_response",
                message="Lists payload missing value array",
                operations=operations,
            )
        list_summaries = []
        preferred = None
        fallback = None
        for entry in values:
            if not isinstance(entry, dict):
                continue
            display = str(entry.get("displayName") or entry.get("name") or "").strip()
            list_summaries.append({"display_name_present": bool(display)})
            if fallback is None:
                fallback = entry
            if display.lower() in {"sources", "documents", "shared documents"}:
                preferred = entry
                break
        preferred = preferred or fallback

        preferred_label = None
        if isinstance(preferred, dict):
            preferred_label = str(
                preferred.get("displayName") or preferred.get("name") or ""
            ).strip() or None

        operations.append(
            {
                "category": "list_enumerate",
                "result": "ok",
                "count": len(list_summaries),
                "preferred_display_name": preferred_label,
            }
        )

        if not preferred or not isinstance(preferred.get("id"), str):
            return _failure(
                category="no_list_found",
                message="Site resolved but no List/Library was returned",
                operations=operations,
            )

        list_id = preferred["id"]
        meta_result = dependencies.graph_get(
            path=f"sites/{site_id}/lists/{list_id}",
            access_token=access_token,
            query={"$select": "id,displayName,name,list"},
        )
        if not meta_result.ok or not isinstance(meta_result.payload, dict):
            return _failure(
                category=meta_result.error_category or "metadata_read_failed",
                message=redact_secrets(meta_result.error_message or "metadata_read_failed"),
                operations=operations,
                extra={"http_status": meta_result.status_code},
            )

        meta = meta_result.payload
        list_facet = meta.get("list") if isinstance(meta.get("list"), dict) else {}
        operations.append(
            {
                "category": "metadata_read",
                "result": "ok",
                "object_kind": "list",
                "display_name_present": bool(str(meta.get("displayName") or "").strip()),
                "template_present": bool(str(list_facet.get("template") or "").strip())
                if isinstance(list_facet, dict)
                else False,
            }
        )

        result: dict[str, Any] = {
            "status": "succeeded",
            "live": True,
            "checked_at": _utc_now(),
            "auth_mode": AUTH_MODE,
            "permission_scope": GRAPH_SCOPES[0],
            "graph_operation_categories": [op["category"] for op in operations],
            "operations": operations,
            "constraints": [
                "read_only",
                "no_file_body_download",
                "no_site_or_list_ids_in_evidence",
                "optional_to_local_core",
            ],
            "manual_fallback": "Human Capture / Pages update in SPO remains valid without Graph",
            "public_safe": True,
        }
        return _maybe_write_evidence(sanitize_evidence(result), evidence_dir)
    finally:
        del access_token


def _failure(
    *,
    category: str,
    message: str,
    operations: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "live": True,
        "checked_at": _utc_now(),
        "auth_mode": AUTH_MODE,
        "permission_scope": GRAPH_SCOPES[0],
        "failure_category": category,
        "failure_message": redact_secrets(message)[:500],
        "operations": operations,
        "manual_fallback": "Use manual SPO Capture / Pages; Graph remains optional",
        "public_safe": True,
    }
    if extra:
        payload.update(extra)
    return sanitize_evidence(payload)


def _maybe_write_evidence(result: dict[str, Any], evidence_dir: Path | None) -> dict[str, Any]:
    if evidence_dir is None:
        return result
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / "m4_graph_spo_smoke_latest.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = dict(result)
    result["evidence_path"] = str(path)
    return result
