"""Graph / SPO smoke configuration (env names only; values stay local)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GraphSmokeConfig:
    """Minimal settings for a delegated, read-only Graph → SPO smoke."""

    enable_sharepoint: bool
    client_id: str | None
    tenant_id: str | None
    spo_hostname: str | None
    spo_site_path: str | None

    @property
    def authority(self) -> str | None:
        if not self.tenant_id:
            return None
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    def missing_required(self) -> list[str]:
        missing: list[str] = []
        if not self.client_id:
            missing.append("THOUGHT_FLOW_GRAPH_CLIENT_ID")
        if not self.tenant_id:
            missing.append("THOUGHT_FLOW_GRAPH_TENANT_ID")
        if not self.spo_hostname:
            missing.append("THOUGHT_FLOW_SPO_HOSTNAME")
        if not self.spo_site_path:
            missing.append("THOUGHT_FLOW_SPO_SITE_PATH")
        return missing

    def is_ready(self) -> bool:
        return self.enable_sharepoint and not self.missing_required()


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_hostname(raw: str | None) -> str | None:
    value = _strip_or_none(raw)
    if value is None:
        return None
    # Accept accidental URL paste; store hostname only.
    if "://" in value:
        value = value.split("://", 1)[1]
    value = value.split("/", 1)[0].strip().lower()
    return value or None


def _normalize_site_path(raw: str | None) -> str | None:
    value = _strip_or_none(raw)
    if value is None:
        return None
    if "://" in value:
        # If a full site URL was pasted, keep path after hostname.
        without_scheme = value.split("://", 1)[1]
        if "/" in without_scheme:
            value = without_scheme.split("/", 1)[1]
        else:
            return None
    value = value.strip()
    if not value.startswith("/"):
        value = "/" + value
    # Graph path addressing uses server-relative path without trailing slash noise.
    if len(value) > 1:
        value = value.rstrip("/")
    return value


def load_graph_smoke_config() -> GraphSmokeConfig:
    """Load Graph smoke config from process environment (optional .env already loaded)."""
    return GraphSmokeConfig(
        enable_sharepoint=_as_bool(os.getenv("THOUGHT_FLOW_ENABLE_SHAREPOINT"), False),
        client_id=_strip_or_none(os.getenv("THOUGHT_FLOW_GRAPH_CLIENT_ID")),
        tenant_id=_strip_or_none(os.getenv("THOUGHT_FLOW_GRAPH_TENANT_ID")),
        spo_hostname=_normalize_hostname(os.getenv("THOUGHT_FLOW_SPO_HOSTNAME")),
        spo_site_path=_normalize_site_path(os.getenv("THOUGHT_FLOW_SPO_SITE_PATH")),
    )
