"""Minimal machine-readable run manifest for M1 local smoke runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

RunType = Literal["smoke", "backfill", "incremental", "rebuild", "analysis", "publish", "spike"]
RunStatus = Literal["started", "succeeded", "failed"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class RunManifest:
    run_identity: str
    run_type: RunType
    status: RunStatus
    started_at: str
    ended_at: str | None = None
    input_sample_identity: str | None = None
    record_identity: str | None = None
    raw_content_identity: str | None = None
    raw_artifact_path: str | None = None
    content_store_path: str | None = None
    content_was_new: bool | None = None
    duckdb_row_count: int | None = None
    code_revision: str | None = None
    failure_category: str | None = None
    failure_message: str | None = None
    notes: dict[str, Any] = field(default_factory=dict)

    def mark_succeeded(self, **updates: Any) -> None:
        for key, value in updates.items():
            setattr(self, key, value)
        self.status = "succeeded"
        self.ended_at = _utc_now_iso()

    def mark_failed(self, *, category: str, message: str) -> None:
        self.status = "failed"
        self.failure_category = category
        # Never include secrets or raw external response bodies.
        self.failure_message = message[:500]
        self.ended_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> Path:
        from thought_flow.atomic_io import atomic_write_text

        text = json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"
        return atomic_write_text(path, text)


def start_manifest(*, run_identity: str, run_type: RunType, code_revision: str | None = None) -> RunManifest:
    return RunManifest(
        run_identity=run_identity,
        run_type=run_type,
        status="started",
        started_at=_utc_now_iso(),
        code_revision=code_revision,
    )
