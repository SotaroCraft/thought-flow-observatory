"""M5 Google Trends smoke package (not a production connector)."""

from __future__ import annotations

from thought_flow.smoke.trends.acquisition_contract import (
    build_acquisition_contract,
)
from thought_flow.smoke.trends.alpha_route import (
    assess_alpha_route,
    refuse_alpha_live_call,
)
from thought_flow.smoke.trends.csv_contract import DEFAULT_CSV_CONTRACT
from thought_flow.smoke.trends.csv_import import import_human_csv, parse_official_trends_csv
from thought_flow.smoke.trends.pipeline import acquire_and_import
from thought_flow.smoke.trends.probes import TRENDS_PROBES, ZERO_SEMANTICS_TRENDS
from thought_flow.smoke.trends.transport import (
    EXPLORE_WIDGET_LIVE_AUTHORIZED,
    ExploreWidgetCsvTransport,
    HumanOfficialCsvTransport,
)

__all__ = [
    "DEFAULT_CSV_CONTRACT",
    "EXPLORE_WIDGET_LIVE_AUTHORIZED",
    "ExploreWidgetCsvTransport",
    "HumanOfficialCsvTransport",
    "TRENDS_PROBES",
    "ZERO_SEMANTICS_TRENDS",
    "acquire_and_import",
    "assess_alpha_route",
    "build_acquisition_contract",
    "import_human_csv",
    "parse_official_trends_csv",
    "refuse_alpha_live_call",
]
