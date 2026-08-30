"""Deterministic OpenAlex daily partition planner (operational checkpoints only).

Does not redefine M6 ISO weekly Canonical analysis buckets.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Sequence

from thought_flow.ingestion.openalex.window import (
    BACKFILL_WINDOW_START,
    RetrievalPartition,
)
from thought_flow.smoke.periods import OPENALEX_COUNTRIES

# Deterministic campaign country order (Repository target set).
CAMPAIGN_COUNTRIES: tuple[str, ...] = tuple(OPENALEX_COUNTRIES)


def inclusive_day_count(*, start: date, end: date) -> int:
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")
    return (end - start).days + 1


def iter_inclusive_dates(start: date, end: date) -> Iterable[date]:
    if end < start:
        raise ValueError(f"end {end} precedes start {start}")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def plan_daily_partitions(
    *,
    run_end_date: date,
    countries: Sequence[str] = CAMPAIGN_COUNTRIES,
    window_start: date = BACKFILL_WINDOW_START,
    range_start: date | None = None,
    range_end: date | None = None,
) -> list[RetrievalPartition]:
    """
    Build country × publication-date daily partitions in deterministic order.

    Order: countries in the given sequence, then dates ascending within each country.
    Gaps and duplicate partition IDs are rejected.
    """
    if run_end_date < window_start:
        raise ValueError(
            f"run_end_date {run_end_date} precedes backfill window start {window_start}"
        )
    start = range_start if range_start is not None else window_start
    end = range_end if range_end is not None else run_end_date
    if start < window_start:
        raise ValueError(f"range_start {start} precedes window start {window_start}")
    if end > run_end_date:
        raise ValueError(f"range_end {end} exceeds captured run_end_date {run_end_date}")
    if end < start:
        raise ValueError(f"range_end {end} precedes range_start {start}")

    normalized_countries: list[str] = []
    seen_country: set[str] = set()
    for raw in countries:
        country = str(raw).upper()
        if country not in CAMPAIGN_COUNTRIES:
            raise ValueError(f"Unsupported campaign country: {raw!r}")
        if country in seen_country:
            raise ValueError(f"Duplicate country in planner input: {country}")
        seen_country.add(country)
        normalized_countries.append(country)

    partitions: list[RetrievalPartition] = []
    seen_ids: set[str] = set()
    for country in normalized_countries:
        for day in iter_inclusive_dates(start, end):
            part = RetrievalPartition.canary_day(country=country, source_date=day)
            if part.partition_id in seen_ids:
                raise ValueError(f"Duplicate partition_id planned: {part.partition_id}")
            seen_ids.add(part.partition_id)
            partitions.append(part)

    expected = inclusive_day_count(start=start, end=end) * len(normalized_countries)
    if len(partitions) != expected:
        raise ValueError(
            f"Planner length mismatch: got {len(partitions)}, expected {expected}"
        )
    return partitions
