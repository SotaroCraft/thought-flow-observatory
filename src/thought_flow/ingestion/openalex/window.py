"""Backfill analysis window and operational retrieval partitions.

The inclusive source-date interval starts at 2022-11-30 (requirements).
The end date is captured once at run start and must not drift.

A RetrievalPartition is an operational checkpoint only — it does not redefine
M6's ISO weekly Canonical analysis bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Callable

from thought_flow.methodology.country_rules import TARGET_COUNTRIES
from thought_flow.methodology.time_rules import ANALYSIS_WINDOW_START

BACKFILL_WINDOW_START: date = ANALYSIS_WINDOW_START  # 2022-11-30 inclusive


def capture_run_end_date(*, clock: Callable[[], date] | None = None) -> date:
    """Capture the run end date once. Injectable for deterministic tests."""
    if clock is not None:
        return clock()
    return datetime.now(UTC).date()


@dataclass(frozen=True)
class RetrievalPartition:
    """Operational retrieval slice (country × inclusive source-date range)."""

    country: str
    inclusive_start: date
    inclusive_end: date

    def __post_init__(self) -> None:
        country = str(self.country).upper()
        if country not in TARGET_COUNTRIES:
            raise ValueError(f"Unsupported target country for backfill partition: {self.country!r}")
        object.__setattr__(self, "country", country)
        if self.inclusive_end < self.inclusive_start:
            raise ValueError(
                f"inclusive_end {self.inclusive_end} precedes inclusive_start {self.inclusive_start}"
            )

    @property
    def partition_id(self) -> str:
        if self.inclusive_start == self.inclusive_end:
            return f"openalex|{self.country}|{self.inclusive_start.isoformat()}"
        return (
            f"openalex|{self.country}|"
            f"{self.inclusive_start.isoformat()}_{self.inclusive_end.isoformat()}"
        )

    @property
    def filter_expr(self) -> str:
        return ",".join(
            [
                f"from_publication_date:{self.inclusive_start.isoformat()}",
                f"to_publication_date:{self.inclusive_end.isoformat()}",
                f"authorships.countries:{self.country.lower()}",
            ]
        )

    def to_manifest(self) -> dict[str, str]:
        return {
            "partition_id": self.partition_id,
            "country": self.country,
            "inclusive_start": self.inclusive_start.isoformat(),
            "inclusive_end": self.inclusive_end.isoformat(),
            "role": "operational_checkpoint_not_iso_week_bucket",
        }

    @classmethod
    def full_window(cls, *, country: str, run_end_date: date) -> RetrievalPartition:
        """Country slice over the full authorized backfill window."""
        if run_end_date < BACKFILL_WINDOW_START:
            raise ValueError(
                f"run_end_date {run_end_date} precedes backfill start {BACKFILL_WINDOW_START}"
            )
        return cls(
            country=country,
            inclusive_start=BACKFILL_WINDOW_START,
            inclusive_end=run_end_date,
        )

    @classmethod
    def canary_day(cls, *, country: str, source_date: date) -> RetrievalPartition:
        """Single-day live canary partition (one country × one source date)."""
        return cls(country=country, inclusive_start=source_date, inclusive_end=source_date)
