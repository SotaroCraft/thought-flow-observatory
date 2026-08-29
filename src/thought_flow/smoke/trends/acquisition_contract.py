"""Layer A — TFO Acquisition Contract (authoritative research/query parameters).

Transport adapters MUST consume this contract and MUST NOT invent geos, terms,
dates, category, property, or Topic substitutions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from thought_flow.smoke.periods import TRENDS_COUNTRIES, TRENDS_FULL, TRENDS_THEMES
from thought_flow.smoke.trends.probes import (
    TRENDS_CATEGORY,
    TRENDS_MODE,
    TRENDS_PROPERTY,
    ZERO_SEMANTICS_TRENDS,
    paired_probes,
)

TransportId = Literal["human_official_csv", "explore_widget_csv"]


@dataclass(frozen=True)
class TrendsAcquisitionContract:
    """Single authoritative acquisition request for one GEO × both theme probes."""

    obs_id: str
    geo: str
    term1: str
    term2: str
    inclusive_start: str
    inclusive_end: str
    half_open_form: str
    period_id: str
    category: str
    property: str
    mode: str
    observation_index: int
    zero_semantics: str
    # Explore time string derived from TFO period only (not an external project constant).
    explore_time: str

    def to_public_dict(self) -> dict[str, Any]:
        return asdict(self)

    def explore_comparison_payload(self) -> dict[str, Any]:
        """Shape for Explore transport — values solely from this contract."""
        # Google Explore uses numeric category; TFO frozen "all" maps to 0.
        category_code = 0 if self.category in {"all", "All", "ALL"} else self.category
        # Web Search property is empty string in Explore wire format.
        prop = "" if self.property in {"web_search", "Web Search", ""} else self.property
        return {
            "comparisonItem": [
                {
                    "keyword": self.term1,
                    "geo": self.geo,
                    "time": self.explore_time,
                },
                {
                    "keyword": self.term2,
                    "geo": self.geo,
                    "time": self.explore_time,
                },
            ],
            "category": category_code,
            "property": prop,
        }


def build_acquisition_contract(
    *,
    geo: str,
    observation_index: int,
    obs_id: str | None = None,
) -> TrendsAcquisitionContract:
    geo_u = geo.upper()
    if geo_u not in TRENDS_COUNTRIES:
        raise ValueError(f"Unsupported TFO Trends geo: {geo!r}")
    if observation_index < 1:
        raise ValueError("observation_index must be >= 1")
    term1, term2 = paired_probes(geo_u)
    start = TRENDS_FULL.inclusive_start.isoformat()
    end = TRENDS_FULL.inclusive_end.isoformat()
    return TrendsAcquisitionContract(
        obs_id=obs_id or f"trends-{geo_u}-obs{observation_index:02d}-{TRENDS_FULL.period_id}",
        geo=geo_u,
        term1=term1,
        term2=term2,
        inclusive_start=start,
        inclusive_end=end,
        half_open_form=TRENDS_FULL.half_open_form,
        period_id=TRENDS_FULL.period_id,
        category=TRENDS_CATEGORY,
        property=TRENDS_PROPERTY,
        mode=TRENDS_MODE,
        observation_index=observation_index,
        zero_semantics=ZERO_SEMANTICS_TRENDS,
        explore_time=f"{start} {end}",
    )


def assert_contract_matches_tfo_sot(contract: TrendsAcquisitionContract) -> None:
    """Guard: contract values must equal frozen TFO configuration."""
    assert contract.geo in TRENDS_COUNTRIES
    assert set(TRENDS_THEMES) == {"generative_ai", "ai_agent"}
    expected = paired_probes(contract.geo)
    assert (contract.term1, contract.term2) == expected
    assert contract.period_id == TRENDS_FULL.period_id
    assert contract.inclusive_start == TRENDS_FULL.inclusive_start.isoformat()
    assert contract.inclusive_end == TRENDS_FULL.inclusive_end.isoformat()
    assert contract.category == TRENDS_CATEGORY
    assert contract.property == TRENDS_PROPERTY
    assert contract.mode == TRENDS_MODE
    assert contract.zero_semantics == ZERO_SEMANTICS_TRENDS
    assert contract.mode == "term"  # never silent Topic substitution
