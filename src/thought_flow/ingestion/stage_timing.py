"""Stage timing telemetry for OpenAlex page persistence (P1)."""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class PageStageTiming:
    page_index: int
    http_seconds: float = 0.0
    json_parse_seconds: float = 0.0
    projection_seconds: float = 0.0
    content_persist_seconds: float = 0.0
    provenance_persist_seconds: float = 0.0
    checkpoint_seconds: float = 0.0
    total_seconds: float = 0.0
    works_count: int = 0
    content_new: int = 0
    content_reused: int = 0

    @property
    def local_persist_seconds(self) -> float:
        return self.content_persist_seconds + self.provenance_persist_seconds


@dataclass
class StageTimingSession:
    """Collects per-page timings for one bounded run / benchmark."""

    pages: list[PageStageTiming] = field(default_factory=list)
    legacy_preload_seconds: float = 0.0
    legacy_preload_identities: int = 0
    legacy_preload_memory_bytes: int = 0
    sink_path: Path | None = None

    def record_page(self, timing: PageStageTiming) -> None:
        self.pages.append(timing)
        if self.sink_path is not None:
            self.sink_path.parent.mkdir(parents=True, exist_ok=True)
            with self.sink_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(timing), sort_keys=True) + "\n")

    def aggregate(self) -> dict[str, Any]:
        totals = [p.total_seconds for p in self.pages]
        locals_ = [p.local_persist_seconds for p in self.pages]
        works = sum(p.works_count for p in self.pages)
        wall = sum(totals)
        first20 = totals[:20]
        last20 = totals[-20:] if len(totals) >= 20 else totals

        def _median(xs: list[float]) -> float | None:
            return float(statistics.median(xs)) if xs else None

        def _p95(xs: list[float]) -> float | None:
            if not xs:
                return None
            ordered = sorted(xs)
            idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
            return float(ordered[idx])

        first_med = _median(first20)
        last_med = _median(last20)
        degradation = (
            (last_med / first_med) if first_med and last_med and first_med > 0 else None
        )
        works_per_hour = (works / wall * 3600.0) if wall > 0 else None
        return {
            "pages_completed": len(self.pages),
            "works_persisted": works,
            "content_new": sum(p.content_new for p in self.pages),
            "content_reused": sum(p.content_reused for p in self.pages),
            "median_sec_per_page": _median(totals),
            "p95_sec_per_page": _p95(totals),
            "local_persist_median": _median(locals_),
            "local_persist_p95": _p95(locals_),
            "works_per_hour": works_per_hour,
            "first20_median": first_med,
            "last20_median": last_med,
            "degradation_ratio": degradation,
            "legacy_preload_seconds": self.legacy_preload_seconds,
            "legacy_preload_identities": self.legacy_preload_identities,
            "legacy_preload_memory_bytes": self.legacy_preload_memory_bytes,
            "total_wall_including_preload": wall + self.legacy_preload_seconds,
            "steady_state_wall_excluding_preload": wall,
            "stage_medians": {
                "http": _median([p.http_seconds for p in self.pages]),
                "json_parse": _median([p.json_parse_seconds for p in self.pages]),
                "projection": _median([p.projection_seconds for p in self.pages]),
                "content_persist": _median([p.content_persist_seconds for p in self.pages]),
                "provenance_persist": _median(
                    [p.provenance_persist_seconds for p in self.pages]
                ),
                "checkpoint": _median([p.checkpoint_seconds for p in self.pages]),
            },
        }


class timed_span:
    """Context manager measuring elapsed seconds into a setter callback."""

    def __init__(self, setter: Callable[[float], None]) -> None:
        self._setter = setter
        self._start = 0.0

    def __enter__(self) -> timed_span:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self._setter(time.perf_counter() - self._start)
