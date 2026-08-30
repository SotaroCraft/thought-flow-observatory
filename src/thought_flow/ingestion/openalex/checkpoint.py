"""Resumable partition checkpoint / page journal for OpenAlex backfill.

Completed pages are recorded with cursor identity and content hashes so retries
skip already-persisted immutable Raw without duplication.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from thought_flow.smoke.quality import QUALITY_STATES, QualityState, require_quality_state

CheckpointStatus = Literal[
    "missing",
    "started",
    "success",
    "zero",
    "partial",
    "fetch_failure",
]

SCHEMA_VERSION = "m7.openalex.backfill.checkpoint.v1"


def _safe_partition_filename(partition_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", partition_id)


@dataclass
class CompletedPage:
    page_index: int
    request_cursor: str
    next_cursor: str | None
    source_count: int | None
    result_count: int
    work_ids: list[str]
    raw_content_identities: list[str]
    page_quality_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletedPage:
        return cls(
            page_index=int(data["page_index"]),
            request_cursor=str(data["request_cursor"]),
            next_cursor=data.get("next_cursor"),
            source_count=data.get("source_count"),
            result_count=int(data["result_count"]),
            work_ids=list(data.get("work_ids") or []),
            raw_content_identities=list(data.get("raw_content_identities") or []),
            page_quality_state=require_quality_state(str(data["page_quality_state"])),
        )


@dataclass
class PartitionCheckpoint:
    partition_id: str
    country: str
    inclusive_start: str
    inclusive_end: str
    run_end_date: str
    coverage_status: CheckpointStatus = "missing"
    pages: list[CompletedPage] = field(default_factory=list)
    next_cursor: str | None = "*"
    exhausted: bool = False
    works_persisted: int = 0
    unknown_country_works: int = 0
    last_run_identity: str | None = None
    failure_category: str | None = None
    failure_message: str | None = None
    schema_version: str = SCHEMA_VERSION

    @property
    def completed_cursors(self) -> set[str]:
        return {p.request_cursor for p in self.pages}

    @property
    def pages_completed(self) -> int:
        return len(self.pages)

    def page_by_cursor(self, cursor: str) -> CompletedPage | None:
        for page in self.pages:
            if page.request_cursor == cursor:
                return page
        return None

    def record_page(self, page: CompletedPage) -> None:
        existing = self.page_by_cursor(page.request_cursor)
        if existing is not None:
            # Idempotent resume: identical completion is a no-op; conflict fails closed.
            if (
                existing.next_cursor != page.next_cursor
                or existing.work_ids != page.work_ids
                or existing.raw_content_identities != page.raw_content_identities
            ):
                raise FileExistsError(
                    f"Checkpoint conflict for completed cursor {page.request_cursor!r} "
                    f"in partition {self.partition_id}"
                )
            return
        self.pages.append(page)
        self.works_persisted = sum(len(p.raw_content_identities) for p in self.pages)
        self.next_cursor = page.next_cursor
        if page.next_cursor is None:
            self.exhausted = True
            self.next_cursor = None

    def set_coverage(self, status: QualityState | CheckpointStatus) -> None:
        if status not in QUALITY_STATES and status not in {"started", "missing"}:
            raise ValueError(f"Invalid coverage status: {status!r}")
        if status in QUALITY_STATES:
            require_quality_state(status)
        self.coverage_status = status  # type: ignore[assignment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "partition_id": self.partition_id,
            "country": self.country,
            "inclusive_start": self.inclusive_start,
            "inclusive_end": self.inclusive_end,
            "run_end_date": self.run_end_date,
            "coverage_status": self.coverage_status,
            "pages": [p.to_dict() for p in self.pages],
            "next_cursor": self.next_cursor,
            "exhausted": self.exhausted,
            "works_persisted": self.works_persisted,
            "unknown_country_works": self.unknown_country_works,
            "last_run_identity": self.last_run_identity,
            "failure_category": self.failure_category,
            "failure_message": self.failure_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartitionCheckpoint:
        pages = [CompletedPage.from_dict(p) for p in data.get("pages") or []]
        status = data.get("coverage_status", "missing")
        return cls(
            partition_id=str(data["partition_id"]),
            country=str(data["country"]),
            inclusive_start=str(data["inclusive_start"]),
            inclusive_end=str(data["inclusive_end"]),
            run_end_date=str(data["run_end_date"]),
            coverage_status=status,
            pages=pages,
            next_cursor=data.get("next_cursor", "*"),
            exhausted=bool(data.get("exhausted", False)),
            works_persisted=int(data.get("works_persisted") or 0),
            unknown_country_works=int(data.get("unknown_country_works") or 0),
            last_run_identity=data.get("last_run_identity"),
            failure_category=data.get("failure_category"),
            failure_message=data.get("failure_message"),
            schema_version=str(data.get("schema_version") or SCHEMA_VERSION),
        )

    @classmethod
    def new(
        cls,
        *,
        partition_id: str,
        country: str,
        inclusive_start: str,
        inclusive_end: str,
        run_end_date: str,
    ) -> PartitionCheckpoint:
        return cls(
            partition_id=partition_id,
            country=country,
            inclusive_start=inclusive_start,
            inclusive_end=inclusive_end,
            run_end_date=run_end_date,
            coverage_status="started",
            next_cursor="*",
        )


def checkpoint_path(checkpoint_dir: Path, partition_id: str) -> Path:
    return checkpoint_dir / f"{_safe_partition_filename(partition_id)}.json"


def load_checkpoint(path: Path) -> PartitionCheckpoint | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Checkpoint must be a JSON object: {path}")
    return PartitionCheckpoint.from_dict(data)


def save_checkpoint(path: Path, checkpoint: PartitionCheckpoint) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(checkpoint.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
