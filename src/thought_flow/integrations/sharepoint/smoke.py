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
)
from thought_flow.integrations.sharepoint.client import graph_get, site_path_address
from thought_flow.integrations.sharepoint.config import GraphSmokeConfig, load_graph_smoke_config
from thought_flow.integrations.sharepoint.sanitize import (
    classify_graph_failure,
    normalize_classification,
    public_safe_evidence,
)

GetFn = Callable[..., Any]
AcquireFn = Callable[..., Any]

_EVIDENCE_RELATIVE = "m4-smoke/m4_graph_spo_smoke_latest.json"


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
    Failures are explicit, allowlisted for public_safe evidence, and never write to Raw.
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
    except MsalUnavailableError:
        return _failure(
            category="dependency_missing",
            error_classification="msal_unavailable",
            operations=operations,
        )
    except Exception:  # noqa: BLE001 — acquire_token dependency boundary
        return _failure(
            category="authentication_failed",
            error_classification="msal_interactive_failed",
            operations=operations,
        )

    if not token.ok or not token.access_token:
        return _failure(
            category="authentication_failed",
            error_classification=normalize_classification(token.error_classification),
            operations=operations,
        )
    operations.append({"category": "authentication", "result": "ok", "mode": AUTH_MODE})

    access_token = token.access_token
    try:
        site_segment = site_path_address(cfg.spo_hostname or "", cfg.spo_site_path or "")
        try:
            site_result = dependencies.graph_get(
                path=f"sites/{site_segment}",
                access_token=access_token,
                query={"$select": "id,displayName,name,webUrl"},
            )
        except Exception:  # noqa: BLE001 — Graph dependency boundary
            return _failure(
                category="site_resolve_failed",
                error_classification="graph_client_exception",
                operations=operations,
            )
        if not site_result.ok or not isinstance(site_result.payload, dict):
            return _failure(
                category="site_resolve_failed",
                error_classification=classify_graph_failure(
                    status_code=site_result.status_code,
                    error_category=site_result.error_category,
                ),
                operations=operations,
                http_status=site_result.status_code,
            )

        site = site_result.payload
        site_id = site.get("id")
        if not isinstance(site_id, str) or not site_id.strip():
            return _failure(
                category="unexpected_response",
                error_classification="unexpected_response",
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

        try:
            lists_result = dependencies.graph_get(
                path=f"sites/{site_id}/lists",
                access_token=access_token,
                query={"$select": "id,displayName,name,list", "$top": "20"},
            )
        except Exception:  # noqa: BLE001 — Graph dependency boundary
            return _failure(
                category="list_enumerate_failed",
                error_classification="graph_client_exception",
                operations=operations,
            )
        if not lists_result.ok or not isinstance(lists_result.payload, dict):
            return _failure(
                category="list_enumerate_failed",
                error_classification=classify_graph_failure(
                    status_code=lists_result.status_code,
                    error_category=lists_result.error_category,
                ),
                operations=operations,
                http_status=lists_result.status_code,
            )

        values = lists_result.payload.get("value")
        if not isinstance(values, list):
            return _failure(
                category="unexpected_response",
                error_classification="unexpected_response",
                operations=operations,
            )

        # Scan the full returned page so returned_list_count means Graph value size.
        preferred = None
        fallback = None
        returned_entries = [entry for entry in values if isinstance(entry, dict)]
        for entry in returned_entries:
            display = str(entry.get("displayName") or entry.get("name") or "").strip()
            if fallback is None:
                fallback = entry
            if preferred is None and display.lower() in {
                "sources",
                "documents",
                "shared documents",
            }:
                preferred = entry
        preferred = preferred or fallback

        preferred_label = None
        preferred_found = False
        if isinstance(preferred, dict):
            preferred_label = str(
                preferred.get("displayName") or preferred.get("name") or ""
            ).strip() or None
            preferred_found = bool(
                preferred_label
                and preferred_label.lower() in {"sources", "documents", "shared documents"}
            )

        operations.append(
            {
                "category": "list_enumerate",
                "result": "ok",
                "returned_list_count": len(returned_entries),
                "preferred_found": preferred_found,
                "preferred_display_name": preferred_label,
            }
        )

        if not preferred or not isinstance(preferred.get("id"), str):
            return _failure(
                category="no_list_found",
                error_classification="no_list_found",
                operations=operations,
            )

        list_id = preferred["id"]
        try:
            meta_result = dependencies.graph_get(
                path=f"sites/{site_id}/lists/{list_id}",
                access_token=access_token,
                query={"$select": "id,displayName,name,list"},
            )
        except Exception:  # noqa: BLE001 — Graph dependency boundary
            return _failure(
                category="metadata_read_failed",
                error_classification="graph_client_exception",
                operations=operations,
            )
        if not meta_result.ok or not isinstance(meta_result.payload, dict):
            return _failure(
                category="metadata_read_failed",
                error_classification=classify_graph_failure(
                    status_code=meta_result.status_code,
                    error_category=meta_result.error_category,
                ),
                operations=operations,
                http_status=meta_result.status_code,
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
        return _maybe_write_evidence(public_safe_evidence(result), evidence_dir)
    finally:
        del access_token


def _failure(
    *,
    category: str,
    error_classification: str,
    operations: list[dict[str, Any]],
    http_status: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "live": True,
        "checked_at": _utc_now(),
        "auth_mode": AUTH_MODE,
        "permission_scope": GRAPH_SCOPES[0],
        "failure_category": category,
        "error_classification": normalize_classification(error_classification),
        "completed_operations": [
            str(op["category"]) for op in operations if isinstance(op, dict) and "category" in op
        ],
        "manual_fallback": "Use manual SPO Capture / Pages; Graph remains optional",
        "public_safe": True,
    }
    if isinstance(http_status, int):
        payload["http_status"] = http_status
    return public_safe_evidence(payload)


def _maybe_write_evidence(result: dict[str, Any], evidence_dir: Path | None) -> dict[str, Any]:
    if evidence_dir is None:
        return result
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / "m4_graph_spo_smoke_latest.json"
    to_write = public_safe_evidence(result)
    path.write_text(json.dumps(to_write, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out = dict(to_write)
    out["evidence_locator"] = _EVIDENCE_RELATIVE
    return public_safe_evidence(out)
