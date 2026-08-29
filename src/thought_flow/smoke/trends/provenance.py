"""Transport provenance for Trends CSV import boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TransportProvenance:
    transport_id: str
    source: str
    acquisition_mode: str
    undocumented_endpoint_used: bool
    description: str

    def to_sidecar_fields(self) -> dict[str, Any]:
        return asdict(self)


HUMAN_OFFICIAL_CSV_PROVENANCE = TransportProvenance(
    transport_id="human_official_csv",
    source="google_trends_official_ui_csv",
    acquisition_mode="human_official_csv_download",
    undocumented_endpoint_used=False,
    description="Human official UI CSV acquisition",
)

EXPLORE_WIDGET_CSV_PROVENANCE = TransportProvenance(
    transport_id="explore_widget_csv",
    source="google_trends_explore_widget_csv",
    acquisition_mode="explore_widget_undocumented_endpoint",
    undocumented_endpoint_used=True,
    description=(
        "Explore/widget acquisition using an undocumented internal endpoint"
    ),
)

PROVENANCE_BY_TRANSPORT_ID = {
    HUMAN_OFFICIAL_CSV_PROVENANCE.transport_id: HUMAN_OFFICIAL_CSV_PROVENANCE,
    EXPLORE_WIDGET_CSV_PROVENANCE.transport_id: EXPLORE_WIDGET_CSV_PROVENANCE,
}
