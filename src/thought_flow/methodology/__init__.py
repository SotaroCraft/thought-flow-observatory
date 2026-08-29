"""M6 methodology contract helpers (Gate A–E). Not M7 ingestion / M8 analysis."""

from __future__ import annotations

from thought_flow.methodology.contracts import (
    CONTRACT_VERSION,
    THEME_DICT_VERSION,
    load_gate_contracts,
)
from thought_flow.methodology.country_rules import (
    TARGET_COUNTRIES,
    inclusion_country_hits,
    is_multi_country,
    is_unknown_country,
    matched_share,
)
from thought_flow.methodology.theme_dict import (
    classify_with_theme_dict_v1,
    load_theme_dict_v1,
    theme_terms_unchanged_from_m5_seed,
)
from thought_flow.methodology.time_rules import (
    ANALYSIS_WINDOW_START,
    flag_boundary_week,
    openalex_iso_week_id,
)

__all__ = [
    "ANALYSIS_WINDOW_START",
    "CONTRACT_VERSION",
    "TARGET_COUNTRIES",
    "THEME_DICT_VERSION",
    "classify_with_theme_dict_v1",
    "flag_boundary_week",
    "inclusion_country_hits",
    "is_multi_country",
    "is_unknown_country",
    "load_gate_contracts",
    "load_theme_dict_v1",
    "matched_share",
    "openalex_iso_week_id",
    "theme_terms_unchanged_from_m5_seed",
]
