"""Human official Google Trends UI CSV export contract (no UI automation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thought_flow.smoke.periods import TRENDS_FULL
from thought_flow.smoke.trends.probes import (
    TRENDS_CATEGORY,
    TRENDS_MODE,
    TRENDS_PROPERTY,
    paired_probes,
)


@dataclass(frozen=True)
class HumanCsvExportContract:
    """Exact steps Human must perform before Cursor may import files."""

    period_id: str = TRENDS_FULL.period_id
    inclusive_start: str = TRENDS_FULL.inclusive_start.isoformat()
    inclusive_end: str = TRENDS_FULL.inclusive_end.isoformat()
    half_open_form: str = TRENDS_FULL.half_open_form
    category: str = TRENDS_CATEGORY
    search_property: str = TRENDS_PROPERTY
    mode: str = TRENDS_MODE
    compare_both_themes_in_one_request: bool = True
    repeat_min_hours: int = 24
    repeat_max_days: int = 7
    forbidden: tuple[str, ...] = (
        "unofficial_libraries",
        "browser_login_automation",
        "undocumented_ui_network_endpoints",
        "reverse_engineered_trends_web_api",
    )

    def human_checklist(self, country: str) -> dict[str, Any]:
        gen, agent = paired_probes(country)
        return {
            "country": country,
            "steps": [
                "Open official Google Trends UI (Human-operated).",
                f"Compare exactly two terms in one request: {gen!r} and {agent!r}.",
                f"Set geo/country explicitly to {country}.",
                f"Custom range {self.inclusive_start} through {self.inclusive_end}.",
                "All categories; Web Search; Term mode (not Topic unless separately approved).",
                "Use official CSV Download only.",
                "Do not rename columns; keep export as downloaded.",
                "Repeat the identical export after ≥24h and ≤7 days for the second observation.",
            ],
            "cursor_after_download_may": [
                "validate schema",
                "normalize filename",
                "write metadata sidecar",
                "import into local gitignored smoke workspace",
                "prepare comparison between observation runs",
            ],
            "cursor_must_not": list(self.forbidden),
            "period": {
                "period_id": self.period_id,
                "inclusive_start": self.inclusive_start,
                "inclusive_end": self.inclusive_end,
                "half_open_form": self.half_open_form,
            },
            "category": self.category,
            "property": self.search_property,
            "mode": self.mode,
        }


DEFAULT_CSV_CONTRACT = HumanCsvExportContract()
