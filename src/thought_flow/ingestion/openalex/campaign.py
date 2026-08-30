"""OpenAlex backfill campaign planner interface and sequential executor.

Dry-run is the safe default. Live execution requires explicit bounds and never
silently runs the full historical window.
"""

from __future__ import annotations

import json
import signal
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from thought_flow.atomic_io import atomic_write_text
from thought_flow.ingestion.openalex.backfill import (
    BackfillResult,
    production_openalex_client,
    run_openalex_partition_backfill,
)
from thought_flow.ingestion.openalex.checkpoint import (
    PartitionCheckpoint,
    checkpoint_path,
    load_checkpoint,
)
from thought_flow.ingestion.openalex.planner import (
    CAMPAIGN_COUNTRIES,
    plan_daily_partitions,
)
from thought_flow.ingestion.openalex.window import (
    BACKFILL_WINDOW_START,
    RetrievalPartition,
    capture_run_end_date,
)
from thought_flow.observability.identity import new_run_identity
from thought_flow.observability.manifest import RunManifest, start_manifest
from thought_flow.smoke.openalex.client import OpenAlexClient

SCHEMA_VERSION = "m7.openalex.backfill.campaign.v1"

SKIP_STATUSES = frozenset({"success", "zero"})
RESUME_STATUSES = frozenset({"started", "partial", "fetch_failure"})
CampaignOutcome = Literal["started", "succeeded", "partial", "failed", "interrupted"]

PartitionAction = Literal["skip", "resume", "fetch"]


def _utc_now_iso(clock: Callable[[], datetime] | None = None) -> str:
    now = clock() if clock is not None else datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_partition_action(
    checkpoint: PartitionCheckpoint | None,
) -> PartitionAction:
    if checkpoint is None:
        return "fetch"
    status = checkpoint.coverage_status
    if status in SKIP_STATUSES:
        return "skip"
    if status in RESUME_STATUSES:
        return "resume"
    if status == "missing":
        return "fetch"
    # Unknown/other checkpoint states are treated as resume candidates (not skip).
    return "resume"


@dataclass
class PlannedPartitionView:
    partition_id: str
    country: str
    source_date: str
    action: PartitionAction
    prior_coverage_status: str | None


@dataclass
class CampaignPlan:
    schema_version: str
    run_end_date: str
    window_start: str
    countries: list[str]
    range_start: str
    range_end: str
    planned_partitions: int
    skip_complete_or_zero: int
    resume_started_partial_or_fetch_failure: int
    fetch_missing: int
    estimated_min_api_requests: int
    approximate_cost_usd: float | None
    partitions: list[PlannedPartitionView] = field(default_factory=list)

    def to_public_summary(self, *, include_partition_list: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "mode": "dry_run",
            "run_end_date": self.run_end_date,
            "window_start": self.window_start,
            "countries": list(self.countries),
            "range_start": self.range_start,
            "range_end": self.range_end,
            "planned_partitions": self.planned_partitions,
            "skip_complete_or_zero": self.skip_complete_or_zero,
            "resume_started_partial_or_fetch_failure": self.resume_started_partial_or_fetch_failure,
            "fetch_missing": self.fetch_missing,
            "estimated_min_api_requests": self.estimated_min_api_requests,
            # Cost cannot be derived from partition counts alone; never coerce to 0.
            "approximate_cost_usd": self.approximate_cost_usd,
            "network_access": False,
            "writes_raw_or_checkpoint": False,
        }
        if include_partition_list:
            payload["partitions"] = [asdict(p) for p in self.partitions]
        return payload


@dataclass
class CampaignCoverage:
    planned: int = 0
    requested: int = 0
    omitted_by_max_partitions: int = 0
    attempted: int = 0
    skipped: int = 0
    resumed: int = 0
    fetched_new: int = 0
    success: int = 0
    zero: int = 0
    missing: int = 0
    started: int = 0
    partial: int = 0
    fetch_failure: int = 0
    unattempted_due_to_stop: int = 0
    pages_completed: int = 0
    works_persisted: int = 0
    unknown_country_works: int = 0
    http_attempts: int | None = None
    approximate_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CampaignResult:
    run_identity: str
    outcome: CampaignOutcome
    run_end_date: date
    countries: list[str]
    range_start: date
    range_end: date
    coverage: CampaignCoverage
    campaign_manifest_path: Path
    run_manifest_path: Path
    checkpoint_dir: Path
    interruption_category: str | None = None
    failure_category: str | None = None
    failure_message: str | None = None
    code_revision: str | None = None

    def to_public_summary(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_identity": self.run_identity,
            "outcome": self.outcome,
            "run_end_date": self.run_end_date.isoformat(),
            "countries": list(self.countries),
            "range_start": self.range_start.isoformat(),
            "range_end": self.range_end.isoformat(),
            "coverage": self.coverage.to_dict(),
            "campaign_manifest_path": str(self.campaign_manifest_path),
            "run_manifest_path": str(self.run_manifest_path),
            "checkpoint_dir": str(self.checkpoint_dir),
            "interruption_category": self.interruption_category,
            "failure_category": self.failure_category,
            "failure_message": self.failure_message,
            "code_revision": self.code_revision,
            # Never embed Raw payloads or full content-identity lists.
        }


def build_campaign_plan(
    *,
    checkpoint_dir: Path,
    run_end_date: date | None = None,
    run_end_clock: Callable[[], date] | None = None,
    countries: Sequence[str] = CAMPAIGN_COUNTRIES,
    range_start: date | None = None,
    range_end: date | None = None,
    include_partition_list: bool = False,
) -> CampaignPlan:
    """Dry-run planner: no network, no Raw/checkpoint mutation."""
    captured_end = run_end_date if run_end_date is not None else capture_run_end_date(clock=run_end_clock)
    partitions = plan_daily_partitions(
        run_end_date=captured_end,
        countries=countries,
        range_start=range_start,
        range_end=range_end,
    )
    views: list[PlannedPartitionView] = []
    skip_n = resume_n = fetch_n = 0
    for part in partitions:
        ck = load_checkpoint(checkpoint_path(checkpoint_dir, part.partition_id))
        action = classify_partition_action(ck)
        if action == "skip":
            skip_n += 1
        elif action == "resume":
            resume_n += 1
        else:
            fetch_n += 1
        if include_partition_list:
            views.append(
                PlannedPartitionView(
                    partition_id=part.partition_id,
                    country=part.country,
                    source_date=part.inclusive_start.isoformat(),
                    action=action,
                    prior_coverage_status=None if ck is None else ck.coverage_status,
                )
            )
    return CampaignPlan(
        schema_version=SCHEMA_VERSION,
        run_end_date=captured_end.isoformat(),
        window_start=BACKFILL_WINDOW_START.isoformat(),
        countries=[str(c).upper() for c in countries],
        range_start=(range_start or BACKFILL_WINDOW_START).isoformat(),
        range_end=(range_end or captured_end).isoformat(),
        planned_partitions=len(partitions),
        skip_complete_or_zero=skip_n,
        resume_started_partial_or_fetch_failure=resume_n,
        fetch_missing=fetch_n,
        # At least one HTTP request per non-skipped partition; further pages unknown.
        estimated_min_api_requests=resume_n + fetch_n,
        approximate_cost_usd=None,
        partitions=views,
    )


def _is_full_history_live_request(
    *,
    range_start: date,
    range_end: date,
    run_end_date: date,
) -> bool:
    """True when live date bounds equal the full authorized backfill window (any country count)."""
    return range_start == BACKFILL_WINDOW_START and range_end == run_end_date


def _require_live_bounds(
    *,
    countries: Sequence[str] | None,
    range_start: date | None,
    range_end: date | None,
) -> tuple[tuple[str, ...], date, date]:
    if not countries:
        raise ValueError(
            "Live campaign requires explicit --country (no unbounded full-history live run)"
        )
    if range_start is None or range_end is None:
        raise ValueError(
            "Live campaign requires explicit --from-date and --to-date bounds"
        )
    normalized = tuple(str(c).upper() for c in countries)
    return normalized, range_start, range_end


def _sync_http_telemetry(coverage: CampaignCoverage, client: OpenAlexClient | None) -> None:
    if client is None:
        return
    coverage.http_attempts = int(client.http.budget.attempts_used)
    # Preserve null when the source never reported cost; never coerce to 0.
    coverage.approximate_cost_usd = client.http.budget.reported_cost_usd


def run_openalex_backfill_campaign(
    *,
    raw_dir: Path,
    checkpoint_dir: Path,
    manifests_dir: Path,
    live: bool = False,
    countries: Sequence[str] | None = None,
    range_start: date | None = None,
    range_end: date | None = None,
    run_end_date: date | None = None,
    run_end_clock: Callable[[], date] | None = None,
    max_partitions: int | None = None,
    client: OpenAlexClient | None = None,
    code_revision: str | None = None,
    clock: Callable[[], datetime] | None = None,
    install_signal_handlers: bool = True,
    should_stop: Callable[[], bool] | None = None,
) -> CampaignPlan | CampaignResult:
    """
    Dry-run (default) returns a CampaignPlan without I/O side effects beyond reads.

    Live mode requires explicit country and date bounds and runs partitions sequentially.
    """
    captured_end = run_end_date if run_end_date is not None else capture_run_end_date(clock=run_end_clock)
    # Freeze end date for the campaign.
    frozen_end = captured_end

    if not live:
        return build_campaign_plan(
            checkpoint_dir=checkpoint_dir,
            run_end_date=frozen_end,
            countries=countries or CAMPAIGN_COUNTRIES,
            range_start=range_start,
            range_end=range_end,
            include_partition_list=False,
        )

    live_countries, live_start, live_end = _require_live_bounds(
        countries=countries,
        range_start=range_start,
        range_end=range_end,
    )
    if _is_full_history_live_request(
        range_start=live_start,
        range_end=live_end,
        run_end_date=frozen_end,
    ):
        raise ValueError(
            "Full-history live campaign is refused in this milestone; "
            "narrow --from-date/--to-date, or use dry-run for the full plan"
        )
    requested_partitions = plan_daily_partitions(
        run_end_date=frozen_end,
        countries=live_countries,
        range_start=live_start,
        range_end=live_end,
    )
    omitted_by_cap = 0
    partitions = list(requested_partitions)
    if max_partitions is not None:
        if max_partitions < 0:
            raise ValueError("max_partitions must be >= 0")
        if max_partitions < len(requested_partitions):
            omitted_by_cap = len(requested_partitions) - max_partitions
            partitions = requested_partitions[:max_partitions]

    run_id = new_run_identity()
    campaign_dir = manifests_dir / "openalex_backfill" / "campaigns"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    campaign_path = campaign_dir / f"{run_id}.json"
    run_manifest_path = manifests_dir / f"{run_id}.json"

    run_manifest = start_manifest(
        run_identity=run_id,
        run_type="backfill",
        code_revision=code_revision,
    )
    coverage = CampaignCoverage(
        planned=len(partitions),
        requested=len(requested_partitions),
        omitted_by_max_partitions=omitted_by_cap,
    )
    outcome: CampaignOutcome = "started"
    interruption_category: str | None = None
    failure_category: str | None = None
    failure_message: str | None = None
    interrupt_flag = {"stop": False}

    def _write_campaign(*, final: bool = False) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "run_identity": run_id,
            "run_type": "backfill",
            "code_revision": code_revision,
            "status": outcome,
            "started_at": run_manifest.started_at,
            "ended_at": run_manifest.ended_at if final else None,
            "source": "openalex.works",
            "window_start": BACKFILL_WINDOW_START.isoformat(),
            "run_end_date": frozen_end.isoformat(),
            "target_period": {
                "inclusive_start": live_start.isoformat(),
                "inclusive_end": live_end.isoformat(),
            },
            "target_countries": list(live_countries),
            "coverage": coverage.to_dict(),
            "api_constraints": {
                "sequential_only": True,
                "smoke_ceilings_applied": False,
                "max_partitions": max_partitions,
            },
            "request_attempt_counts": {
                "estimated_min_api_requests": coverage.resumed + coverage.fetched_new,
                "http_attempts": coverage.http_attempts,
            },
            "approximate_cost_usd": coverage.approximate_cost_usd,
            "interruption_category": interruption_category,
            "failure_category": failure_category,
            "failure_message": failure_message,
            "checkpoint_dir": str(checkpoint_dir),
            # Coverage summary only — no Raw payloads / identity dumps.
        }
        atomic_write_text(
            campaign_path,
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )
        run_manifest.notes = {
            "campaign_manifest_path": str(campaign_path),
            "outcome": outcome,
            "coverage": coverage.to_dict(),
        }
        run_manifest.write(run_manifest_path)

    # Persist started evidence before any partition work.
    _write_campaign(final=False)

    previous_sigint = None
    if install_signal_handlers:
        def _handle_sigint(signum: int, frame: Any) -> None:  # noqa: ARG001
            interrupt_flag["stop"] = True

        previous_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _handle_sigint)

    active_client = client
    had_partition_failure = False
    source_stop = False
    try:
        for part_index, part in enumerate(partitions):
            if interrupt_flag["stop"] or (should_stop is not None and should_stop()):
                outcome = "interrupted"
                interruption_category = interruption_category or (
                    "SIGINT" if interrupt_flag["stop"] else "interrupt"
                )
                remaining = partitions[part_index:]
                coverage.unattempted_due_to_stop = len(remaining)
                break

            ck = load_checkpoint(checkpoint_path(checkpoint_dir, part.partition_id))
            action = classify_partition_action(ck)
            if action == "skip":
                coverage.skipped += 1
                status = ck.coverage_status if ck is not None else "success"
                if status == "success":
                    coverage.success += 1
                elif status == "zero":
                    coverage.zero += 1
                if ck is not None:
                    coverage.pages_completed += ck.pages_completed
                    coverage.works_persisted += ck.works_persisted
                    coverage.unknown_country_works += ck.unknown_country_works
                continue

            coverage.attempted += 1
            if action == "resume":
                coverage.resumed += 1
            else:
                coverage.fetched_new += 1

            if active_client is None:
                active_client = production_openalex_client()

            try:
                result = run_openalex_partition_backfill(
                    partition=part,
                    raw_dir=raw_dir,
                    checkpoint_dir=checkpoint_dir,
                    manifests_dir=manifests_dir,
                    client=active_client,
                    code_revision=code_revision,
                    run_end_date=frozen_end,
                    clock=clock,
                )
            except Exception as exc:  # noqa: BLE001
                coverage.fetch_failure += 1
                had_partition_failure = True
                source_stop = True
                failure_category = type(exc).__name__
                failure_message = str(exc)[:500]
                _sync_http_telemetry(coverage, active_client)
                # Stop sequential work; do not attempt remaining partitions.
                remaining = partitions[part_index + 1 :]
                coverage.unattempted_due_to_stop = len(remaining)
                break

            status = result.coverage_status
            if status == "success":
                coverage.success += 1
            elif status == "zero":
                coverage.zero += 1
            elif status == "partial":
                coverage.partial += 1
                had_partition_failure = True
                source_stop = True
            elif status == "fetch_failure":
                coverage.fetch_failure += 1
                had_partition_failure = True
                source_stop = True
            elif status == "started":
                coverage.started += 1
                had_partition_failure = True
                source_stop = True
            elif status == "missing":
                coverage.missing += 1
                had_partition_failure = True
                source_stop = True
            else:
                coverage.partial += 1
                had_partition_failure = True
                source_stop = True

            coverage.pages_completed += result.pages_completed
            coverage.works_persisted += result.works_persisted
            coverage.unknown_country_works += result.unknown_country_works
            _sync_http_telemetry(coverage, active_client)

            if status in {"partial", "fetch_failure", "started", "missing"} or status not in {
                "success",
                "zero",
            }:
                failure_category = result.failure_category or status
                failure_message = result.failure_message

            if interrupt_flag["stop"] or (should_stop is not None and should_stop()):
                outcome = "interrupted"
                interruption_category = interruption_category or (
                    "SIGINT" if interrupt_flag["stop"] else "interrupt"
                )
                remaining = partitions[part_index + 1 :]
                coverage.unattempted_due_to_stop = len(remaining)
                break

            if source_stop:
                remaining = partitions[part_index + 1 :]
                coverage.unattempted_due_to_stop = len(remaining)
                break

            _write_campaign(final=False)

        _sync_http_telemetry(coverage, active_client)

        if outcome == "interrupted":
            pass
        elif (
            had_partition_failure
            or coverage.partial > 0
            or coverage.fetch_failure > 0
            or coverage.started > 0
            or coverage.missing > 0
            or coverage.omitted_by_max_partitions > 0
            or coverage.unattempted_due_to_stop > 0
        ):
            # Capped / stopped runs are incomplete relative to the requested period.
            outcome = "partial"
        else:
            outcome = "succeeded"

        if outcome == "succeeded" and (
            coverage.partial > 0
            or coverage.fetch_failure > 0
            or coverage.started > 0
            or coverage.missing > 0
            or coverage.omitted_by_max_partitions > 0
            or coverage.unattempted_due_to_stop > 0
            or interruption_category
        ):
            outcome = "partial"

        if outcome == "succeeded":
            run_manifest.mark_succeeded()
        elif outcome == "interrupted":
            run_manifest.mark_failed(
                category=interruption_category or "interrupted",
                message="campaign interrupted before completion",
            )
        else:
            run_manifest.mark_failed(
                category=failure_category or outcome,
                message=failure_message or f"campaign ended with outcome={outcome}",
            )
        _write_campaign(final=True)
    finally:
        if install_signal_handlers and previous_sigint is not None:
            signal.signal(signal.SIGINT, previous_sigint)

    return CampaignResult(
        run_identity=run_id,
        outcome=outcome,
        run_end_date=frozen_end,
        countries=list(live_countries),
        range_start=live_start,
        range_end=live_end,
        coverage=coverage,
        campaign_manifest_path=campaign_path,
        run_manifest_path=run_manifest_path,
        checkpoint_dir=checkpoint_dir,
        interruption_category=interruption_category,
        failure_category=failure_category,
        failure_message=failure_message,
        code_revision=code_revision,
    )
