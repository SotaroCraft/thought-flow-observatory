"""Identity helpers for runs, records, Raw content, and Canonical snapshot boundaries."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Mapping
from typing import Any


def new_run_identity() -> str:
    """Unique identity for every execution (never reused across runs)."""
    return str(uuid.uuid4())


def record_identity(*, source_identity: str, logical_key: str) -> str:
    """Stable identity for the same logical source record across runs."""
    material = f"{source_identity}\0{logical_key}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return f"rec_{digest[:32]}"


def _canonical_json_bytes(payload: Mapping[str, Any] | str | bytes) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def raw_content_identity(payload: Mapping[str, Any] | str | bytes) -> str:
    """Stable identity for identical Raw content, independent of run_identity."""
    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return f"raw_{digest}"


def canonical_snapshot_identity(
    *,
    raw_content_identities: Iterable[str],
    dictionary_version: str,
    aggregation_rule_version: str,
    code_revision: str,
) -> str:
    """
    Deterministic snapshot identity concept for M1.

    Full Canonical semantics (weekly schema, country rules, etc.) wait for M6.
    Same Raw content set + rule versions + code revision => same identity.
    """
    ordered = sorted(set(raw_content_identities))
    material = {
        "raw_content_identities": ordered,
        "dictionary_version": dictionary_version,
        "aggregation_rule_version": aggregation_rule_version,
        "code_revision": code_revision,
    }
    digest = hashlib.sha256(_canonical_json_bytes(material)).hexdigest()
    return f"can_{digest[:32]}"
