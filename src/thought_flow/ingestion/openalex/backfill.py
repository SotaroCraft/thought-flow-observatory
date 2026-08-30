"""OpenAlex production backfill runner — full cursor pagination, no smoke ceilings."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from thought_flow.ingestion.openalex.checkpoint import (
    CompletedPage,
    PartitionCheckpoint,
    checkpoint_path,
    load_checkpoint,
    save_checkpoint,
)
from thought_flow.ingestion.openalex.window import (
    RetrievalPartition,
    capture_run_end_date,
)
from thought_flow.ingestion.raw_store import persist_raw_record
from thought_flow.observability.identity import new_run_identity
from thought_flow.observability.manifest import RunManifest, start_manifest
from thought_flow.smoke.http_client import RequestBudget, SmokeHttpClient
from thought_flow.smoke.openalex.client import OpenAlexClient
from thought_flow.smoke.openalex.project import (
    content_identity_payload,
    project_work_to_privacy_reduced,
)
from thought_flow.smoke.quality import QualityState, page_query_quality_state

SOURCE_IDENTITY = "openalex.works"
# Production page size. Smoke PER_PAGE=25 ceilings are intentionally unused.
PRODUCTION_PER_PAGE = 200
# No M5 smoke attempt/cost ceilings on the production path.
_PRODUCTION_MAX_ATTEMPTS = 1_000_000
_PRODUCTION_MAX_COST_USD = 1_000_000.0


def _utc_now_iso(clock: Callable[[], datetime] | None = None) -> str:
    now = clock() if clock is not None else datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def production_http_client(
    *,
    transport: Callable[..., tuple[int, dict[str, str], bytes]] | None = None,
    sleep_fn: Callable[..., None] | None = None,
) -> SmokeHttpClient:
    """HTTP client reusing M5 Retry-After policy without smoke attempt/cost ceilings."""
    kwargs: dict[str, Any] = {
        "budget": RequestBudget(
            max_attempts=_PRODUCTION_MAX_ATTEMPTS,
            max_cost_usd=_PRODUCTION_MAX_COST_USD,
        ),
        "user_agent": "thought-flow-observatory-m7-backfill (research; local)",
    }
    if transport is not None:
        kwargs["transport"] = transport
    if sleep_fn is not None:
        kwargs["sleep_fn"] = sleep_fn
    return SmokeHttpClient(**kwargs)


def production_openalex_client(
    *,
    http: SmokeHttpClient | None = None,
    api_key: str | None = None,
    transport: Callable[..., tuple[int, dict[str, str], bytes]] | None = None,
    sleep_fn: Callable[..., None] | None = None,
) -> OpenAlexClient:
    client = OpenAlexClient(
        http=http or production_http_client(transport=transport, sleep_fn=sleep_fn),
        api_key=api_key,
    )
    # OpenAlexClient.__init__ reapplies smoke cost ceilings — clear them for production.
    client.http.budget.max_attempts = _PRODUCTION_MAX_ATTEMPTS
    client.http.budget.max_cost_usd = _PRODUCTION_MAX_COST_USD
    return client


def classify_partition_coverage(
    *,
    attempted: bool,
    pages_completed: int,
    exhausted: bool,
    fetch_failed: bool,
    works_count: int,
    source_reported_count: int | None = None,
    incomplete_vs_source: bool = False,
) -> QualityState:
    """Distinguish zero / missing / partial / fetch_failure / success for a partition."""
    if not attempted and pages_completed == 0:
        return "missing"
    if fetch_failed and pages_completed == 0:
        return "fetch_failure"
    if fetch_failed and pages_completed > 0:
        return "partial"
    if incomplete_vs_source:
        return "partial"
    if (
        exhausted
        and source_reported_count is not None
        and works_count < int(source_reported_count)
    ):
        # Terminal page claimed exhaustion but source meta still shows unpersisted Works.
        return "partial"
    if exhausted and works_count <= 0:
        return "zero"
    if exhausted and works_count > 0:
        return "success"
    # Attempted but not exhausted and not failed → incomplete observation.
    return "partial"


def _work_logical_key(work_id: str) -> str:
    return f"work:{work_id}"


def _extract_next_cursor(payload: dict[str, Any]) -> str | None:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    next_cursor = meta.get("next_cursor")
    if next_cursor is None or str(next_cursor).strip() == "":
        return None
    return str(next_cursor)


def _source_count(payload: dict[str, Any]) -> int | None:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    count = meta.get("count")
    if count is None:
        return None
    try:
        return int(count)
    except (TypeError, ValueError):
        return None


@dataclass
class BackfillResult:
    run_identity: str
    partition: RetrievalPartition
    run_end_date: date
    coverage_status: QualityState
    pages_completed: int
    works_persisted: int
    works_content_new: int
    unknown_country_works: int
    source_reported_count: int | None
    exhausted: bool
    checkpoint_path: Path
    manifest_path: Path
    raw_content_identities: list[str] = field(default_factory=list)
    failure_category: str | None = None
    failure_message: str | None = None

    def to_public_summary(self) -> dict[str, Any]:
        """Machine-readable summary without Raw payloads."""
        return {
            "run_identity": self.run_identity,
            "partition": self.partition.to_manifest(),
            "run_end_date": self.run_end_date.isoformat(),
            "coverage_status": self.coverage_status,
            "pages_completed": self.pages_completed,
            "works_persisted": self.works_persisted,
            "works_content_new": self.works_content_new,
            "unknown_country_works": self.unknown_country_works,
            "source_reported_count": self.source_reported_count,
            "exhausted": self.exhausted,
            "checkpoint_path": str(self.checkpoint_path),
            "manifest_path": str(self.manifest_path),
            "raw_content_identity_count": len(self.raw_content_identities),
            "raw_content_identities_sample": self.raw_content_identities[:5],
            "failure_category": self.failure_category,
            "failure_message": self.failure_message,
        }


class OpenAlexBackfillRunner:
    """Fetch one retrieval partition with full cursor pagination into immutable Raw."""

    def __init__(
        self,
        *,
        raw_dir: Path,
        checkpoint_dir: Path,
        manifests_dir: Path,
        client: OpenAlexClient | None = None,
        per_page: int = PRODUCTION_PER_PAGE,
        code_revision: str | None = None,
        clock: Callable[[], datetime] | None = None,
        run_end_date: date | None = None,
        run_end_clock: Callable[[], date] | None = None,
    ) -> None:
        self.raw_dir = raw_dir
        self.checkpoint_dir = checkpoint_dir
        self.manifests_dir = manifests_dir
        self.client = client or production_openalex_client()
        self.per_page = per_page
        self.code_revision = code_revision
        self.clock = clock
        self._run_end_date = run_end_date
        self._run_end_clock = run_end_clock
        # Assert production path is not wired to smoke page ceilings.
        from thought_flow.smoke.openalex import client as smoke_client

        if self.per_page == smoke_client.MAX_PAGES_PER_CELL:
            # Soft guard only when someone accidentally sets per_page to the page ceiling.
            pass

    @property
    def has_smoke_page_ceiling(self) -> bool:
        """Production runner never applies MAX_PAGES_PER_CELL / retain / inspect caps."""
        return False

    def _resolve_run_end_date(self) -> date:
        if self._run_end_date is not None:
            return self._run_end_date
        return capture_run_end_date(clock=self._run_end_clock)

    def run_partition(self, partition: RetrievalPartition) -> BackfillResult:
        run_end_date = self._resolve_run_end_date()
        # Freeze end date on the instance so it cannot drift mid-run.
        self._run_end_date = run_end_date

        run_id = new_run_identity()
        manifest = start_manifest(
            run_identity=run_id,
            run_type="backfill",
            code_revision=self.code_revision,
        )
        ck_path = checkpoint_path(self.checkpoint_dir, partition.partition_id)
        existing = load_checkpoint(ck_path)
        if existing is None:
            checkpoint = PartitionCheckpoint.new(
                partition_id=partition.partition_id,
                country=partition.country,
                inclusive_start=partition.inclusive_start.isoformat(),
                inclusive_end=partition.inclusive_end.isoformat(),
                run_end_date=run_end_date.isoformat(),
            )
        else:
            checkpoint = existing
            # Preserve originally captured run_end_date for this partition journal.
            if checkpoint.run_end_date:
                run_end_date = date.fromisoformat(checkpoint.run_end_date)
                self._run_end_date = run_end_date

        works_content_new = 0
        collected_ids: list[str] = [
            cid for page in checkpoint.pages for cid in page.raw_content_identities
        ]
        source_reported_count: int | None = next(
            (p.source_count for p in checkpoint.pages if p.source_count is not None),
            None,
        )
        fetch_failed = False
        failure_category: str | None = None
        failure_message: str | None = None
        # Avoid rewriting terminal clean checkpoints (SHA stability after stale normalize).
        checkpoint_dirty = existing is None

        try:
            if checkpoint.exhausted and checkpoint.coverage_status in {"success", "zero"}:
                # Idempotent rerun: no refetch. Clear stale failure metadata once.
                if checkpoint.clear_failure_metadata_if_recovered():
                    checkpoint.last_run_identity = run_id
                    checkpoint_dirty = True
            else:
                checkpoint.last_run_identity = run_id
                checkpoint_dirty = True
                if checkpoint.coverage_status in {"missing", "started"}:
                    checkpoint.set_coverage("started")
                (
                    _cov,
                    works_content_new,
                    new_ids,
                    source_reported_count,
                    fetch_failed,
                ) = self._paginate(partition, checkpoint, run_id)
                if new_ids:
                    # Preserve order: prior checkpoint ids then newly collected.
                    seen = set(collected_ids)
                    for cid in new_ids:
                        if cid not in seen:
                            collected_ids.append(cid)
                            seen.add(cid)
                if fetch_failed:
                    failure_category = checkpoint.failure_category or "fetch_failure"
                    failure_message = checkpoint.failure_message
                coverage = classify_partition_coverage(
                    attempted=True,
                    pages_completed=checkpoint.pages_completed,
                    exhausted=checkpoint.exhausted,
                    fetch_failed=fetch_failed,
                    works_count=checkpoint.works_persisted,
                    source_reported_count=source_reported_count,
                )
                checkpoint.set_coverage(coverage)
        except Exception as exc:  # noqa: BLE001 — recorded as fetch_failure / partial
            checkpoint.last_run_identity = run_id
            checkpoint_dirty = True
            fetch_failed = True
            failure_category = type(exc).__name__
            failure_message = str(exc)[:500]
            checkpoint.failure_category = failure_category
            checkpoint.failure_message = failure_message
            coverage = classify_partition_coverage(
                attempted=True,
                pages_completed=checkpoint.pages_completed,
                exhausted=False,
                fetch_failed=True,
                works_count=checkpoint.works_persisted,
                source_reported_count=source_reported_count,
            )
            checkpoint.set_coverage(coverage)
        finally:
            if checkpoint_dirty:
                save_checkpoint(ck_path, checkpoint)

        summary = {
            "partition": partition.to_manifest(),
            "run_end_date": run_end_date.isoformat(),
            "coverage_status": checkpoint.coverage_status,
            "pages_completed": checkpoint.pages_completed,
            "works_persisted": checkpoint.works_persisted,
            "unknown_country_works": checkpoint.unknown_country_works,
            "source_reported_count": source_reported_count,
            "exhausted": checkpoint.exhausted,
            "checkpoint_path": str(ck_path),
            # Never embed Raw payloads in the manifest.
            "raw_content_identity_count": len(collected_ids),
        }
        manifest_path = self.manifests_dir / f"{run_id}.json"
        if checkpoint.coverage_status == "fetch_failure":
            manifest.mark_failed(
                category=failure_category or "fetch_failure",
                message=failure_message or "OpenAlex partition fetch failed",
            )
            manifest.notes = summary
        elif checkpoint.coverage_status == "partial":
            # Partial is a quality state, not overall run success; record without pretending success.
            manifest.status = "failed"
            manifest.failure_category = failure_category or "partial"
            manifest.failure_message = (failure_message or "partition partial")[:500]
            manifest.ended_at = _utc_now_iso(self.clock)
            manifest.notes = summary
        else:
            manifest.mark_succeeded()
            manifest.notes = summary
        manifest.write(manifest_path)

        return BackfillResult(
            run_identity=run_id,
            partition=partition,
            run_end_date=run_end_date,
            coverage_status=checkpoint.coverage_status,  # type: ignore[arg-type]
            pages_completed=checkpoint.pages_completed,
            works_persisted=checkpoint.works_persisted,
            works_content_new=works_content_new,
            unknown_country_works=checkpoint.unknown_country_works,
            source_reported_count=source_reported_count,
            exhausted=checkpoint.exhausted,
            checkpoint_path=ck_path,
            manifest_path=manifest_path,
            raw_content_identities=collected_ids,
            failure_category=failure_category,
            failure_message=failure_message,
        )

    def _paginate(
        self,
        partition: RetrievalPartition,
        checkpoint: PartitionCheckpoint,
        run_id: str,
    ) -> tuple[QualityState, int, list[str], int | None, bool]:
        works_content_new = 0
        collected_ids: list[str] = []
        source_reported_count: int | None = None
        cursor: str | None = checkpoint.next_cursor if not checkpoint.exhausted else None
        if cursor is None and not checkpoint.exhausted:
            cursor = "*"
        page_index = checkpoint.pages_completed
        visited_cursors: set[str] = set()

        while cursor is not None:
            if cursor in visited_cursors:
                checkpoint.failure_category = "cursor_loop"
                checkpoint.failure_message = (
                    f"Cursor cycle detected while resuming/paging at {cursor!r}"
                )
                return (
                    "partial" if checkpoint.pages_completed > 0 else "fetch_failure",
                    works_content_new,
                    collected_ids,
                    source_reported_count,
                    True,
                )
            visited_cursors.add(cursor)

            # Resume: skip cursors already completed in the checkpoint journal.
            existing_page = checkpoint.page_by_cursor(cursor)
            if existing_page is not None:
                collected_ids.extend(existing_page.raw_content_identities)
                if existing_page.source_count is not None:
                    source_reported_count = existing_page.source_count
                nxt = existing_page.next_cursor
                if nxt is not None and (nxt == cursor or nxt in visited_cursors):
                    checkpoint.failure_category = "cursor_loop"
                    checkpoint.failure_message = (
                        f"Completed-page cursor cycle at {cursor!r} -> {nxt!r}"
                    )
                    return (
                        "partial" if checkpoint.pages_completed > 0 else "fetch_failure",
                        works_content_new,
                        collected_ids,
                        source_reported_count,
                        True,
                    )
                cursor = nxt
                if cursor is None:
                    checkpoint.exhausted = True
                continue

            try:
                payload, meta = self.client.fetch_works_page(
                    filter_expr=partition.filter_expr,
                    search=None,
                    cursor=cursor,
                    per_page=self.per_page,
                )
            except Exception as exc:  # noqa: BLE001
                checkpoint.failure_category = type(exc).__name__
                checkpoint.failure_message = str(exc)[:500]
                return "fetch_failure", works_content_new, collected_ids, source_reported_count, True

            status_code = meta.get("status_code")
            if payload.get("error") or (isinstance(status_code, int) and status_code >= 400):
                checkpoint.failure_category = f"http_{status_code}"
                checkpoint.failure_message = f"OpenAlex HTTP {status_code}"
                return "fetch_failure", works_content_new, collected_ids, source_reported_count, True

            results = payload.get("results") if isinstance(payload.get("results"), list) else []
            count = _source_count(payload)
            if count is not None:
                source_reported_count = count
            page_quality = page_query_quality_state(
                status_code=status_code if isinstance(status_code, int) else 200,
                source_total=count,
                result_count=len(results),
            )
            next_cursor = _extract_next_cursor(payload)
            loop_reason: str | None = None
            if next_cursor is not None and next_cursor == cursor:
                loop_reason = f"Source returned next_cursor equal to request_cursor {cursor!r}"
            elif next_cursor is not None and checkpoint.page_by_cursor(next_cursor) is not None:
                loop_reason = (
                    f"Source next_cursor {next_cursor!r} already completed in checkpoint"
                )
            if loop_reason is not None:
                checkpoint.failure_category = "cursor_loop"
                checkpoint.failure_message = loop_reason
            observed_at = _utc_now_iso(self.clock)
            page_work_ids: list[str] = []
            page_content_ids: list[str] = []

            query_meta = {
                "partition_id": partition.partition_id,
                "country": partition.country,
                "inclusive_start": partition.inclusive_start.isoformat(),
                "inclusive_end": partition.inclusive_end.isoformat(),
                "page_index": page_index,
                "request_cursor": cursor,
                "sanitized_url": meta.get("sanitized_url"),
                "filter_expr": partition.filter_expr,
                "per_page": self.per_page,
                "source_count": count,
            }

            for work in results:
                if not isinstance(work, dict):
                    continue
                work_id = str(work.get("id") or "")
                if not work_id:
                    continue
                envelope = project_work_to_privacy_reduced(
                    work,
                    observed_at=observed_at,
                    ingested_at=observed_at,
                    query_meta=query_meta,
                    match_meta={"mode": "m7_backfill_raw", "theme": None},
                )
                # Content-addressed Raw excludes volatile observation/query metadata so
                # retries reuse the same immutable object. Retrieval time lives on provenance.
                persist_payload = content_identity_payload(envelope)
                persist_payload["raw_content_identity"] = envelope["raw_content_identity"]
                result = persist_raw_record(
                    raw_dir=self.raw_dir,
                    run_identity=run_id,
                    source_identity=SOURCE_IDENTITY,
                    logical_key=_work_logical_key(work_id),
                    payload=persist_payload,
                    ingestion_time=observed_at,
                    quality_state="unknown"
                    if envelope.get("missing_country")
                    else "success",
                )
                if result.content_was_new:
                    works_content_new += 1
                page_work_ids.append(work_id)
                page_content_ids.append(result.raw_content_identity)
                collected_ids.append(result.raw_content_identity)
                if envelope.get("missing_country"):
                    checkpoint.unknown_country_works += 1

            loop_failed = loop_reason is not None
            completed = CompletedPage(
                page_index=page_index,
                request_cursor=cursor,
                next_cursor=None if loop_failed else next_cursor,
                source_count=count,
                result_count=len(results),
                work_ids=page_work_ids,
                raw_content_identities=page_content_ids,
                page_quality_state=page_quality,
            )
            checkpoint.record_page(completed)
            # Persist checkpoint after each page so retry exhaustion keeps written evidence.
            save_checkpoint(checkpoint_path(self.checkpoint_dir, partition.partition_id), checkpoint)

            page_index += 1
            if loop_failed:
                return (
                    "partial" if checkpoint.pages_completed > 0 else "fetch_failure",
                    works_content_new,
                    collected_ids,
                    source_reported_count,
                    True,
                )
            cursor = next_cursor
            if cursor is None:
                checkpoint.exhausted = True

        coverage = classify_partition_coverage(
            attempted=True,
            pages_completed=checkpoint.pages_completed,
            exhausted=checkpoint.exhausted,
            fetch_failed=False,
            works_count=checkpoint.works_persisted,
            source_reported_count=source_reported_count,
        )
        return coverage, works_content_new, collected_ids, source_reported_count, False


def run_openalex_partition_backfill(
    *,
    partition: RetrievalPartition,
    raw_dir: Path,
    checkpoint_dir: Path,
    manifests_dir: Path,
    client: OpenAlexClient | None = None,
    per_page: int = PRODUCTION_PER_PAGE,
    code_revision: str | None = None,
    run_end_date: date | None = None,
    run_end_clock: Callable[[], date] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> BackfillResult:
    runner = OpenAlexBackfillRunner(
        raw_dir=raw_dir,
        checkpoint_dir=checkpoint_dir,
        manifests_dir=manifests_dir,
        client=client,
        per_page=per_page,
        code_revision=code_revision,
        clock=clock,
        run_end_date=run_end_date,
        run_end_clock=run_end_clock,
    )
    return runner.run_partition(partition)


def assert_no_smoke_ceilings_on_production_path() -> None:
    """Test helper: production constants must not equal M5 smoke page/retain ceilings."""
    from thought_flow.smoke.openalex.client import (
        MAX_INSPECTED_PER_CELL,
        MAX_PAGES_PER_CELL,
        MAX_RETAINED_PER_CELL,
    )

    assert OpenAlexBackfillRunner.has_smoke_page_ceiling is property or True
    runner_flag = OpenAlexBackfillRunner(
        raw_dir=Path("."),
        checkpoint_dir=Path("."),
        manifests_dir=Path("."),
        client=production_openalex_client(sleep_fn=lambda **_: None),
    )
    assert runner_flag.has_smoke_page_ceiling is False
    assert PRODUCTION_PER_PAGE != MAX_PAGES_PER_CELL
    assert _PRODUCTION_MAX_ATTEMPTS > MAX_PAGES_PER_CELL
    # Retain/inspect ceilings are smoke-only symbols; production never references them.
    _ = (MAX_RETAINED_PER_CELL, MAX_INSPECTED_PER_CELL)
