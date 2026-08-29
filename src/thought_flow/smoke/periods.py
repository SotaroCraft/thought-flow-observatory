"""Fixed M5 smoke calendar periods (fixtures only; not production week rule)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SmokePeriod:
    period_id: str
    inclusive_start: date
    inclusive_end: date
    half_open_end: date

    @property
    def inclusive_dates(self) -> tuple[str, str]:
        return (self.inclusive_start.isoformat(), self.inclusive_end.isoformat())

    @property
    def half_open_form(self) -> str:
        return f"[{self.inclusive_start.isoformat()}, {self.half_open_end.isoformat()})"

    def to_manifest(self) -> dict[str, str]:
        return {
            "period_id": self.period_id,
            "inclusive_start": self.inclusive_start.isoformat(),
            "inclusive_end": self.inclusive_end.isoformat(),
            "half_open_form": self.half_open_form,
        }


OA_START = SmokePeriod(
    period_id="OA-START",
    inclusive_start=date(2022, 11, 30),
    inclusive_end=date(2022, 12, 4),
    half_open_end=date(2022, 12, 5),
)
OA_MID = SmokePeriod(
    period_id="OA-MID",
    inclusive_start=date(2024, 10, 7),
    inclusive_end=date(2024, 10, 13),
    half_open_end=date(2024, 10, 14),
)
OA_RECENT = SmokePeriod(
    period_id="OA-RECENT",
    inclusive_start=date(2026, 8, 10),
    inclusive_end=date(2026, 8, 16),
    half_open_end=date(2026, 8, 17),
)

OPENALEX_PERIODS: tuple[SmokePeriod, ...] = (OA_START, OA_MID, OA_RECENT)

OPENALEX_PERIOD_BY_ID: dict[str, SmokePeriod] = {p.period_id: p for p in OPENALEX_PERIODS}

OPENALEX_COUNTRIES: tuple[str, ...] = ("JP", "US", "KR", "CN")
OPENALEX_THEMES: tuple[str, ...] = ("generative_ai", "ai_agent")

TRENDS_FULL = SmokePeriod(
    period_id="TRENDS-FULL",
    inclusive_start=date(2022, 11, 30),
    inclusive_end=date(2026, 8, 16),
    half_open_end=date(2026, 8, 17),
)

TRENDS_COUNTRIES: tuple[str, ...] = ("JP", "US", "KR", "CN")
TRENDS_THEMES: tuple[str, ...] = ("generative_ai", "ai_agent")
