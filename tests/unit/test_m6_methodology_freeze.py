"""M6 methodology freeze contract tests (Gate A–E). No live source requests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from thought_flow.methodology.contracts import CONTRACT_VERSION, THEME_DICT_VERSION, load_gate_contracts
from thought_flow.methodology.country_rules import (
    TARGET_COUNTRIES,
    assert_denominator_query_theme_independent,
    inclusion_country_hits,
    is_multi_country,
    is_unknown_country,
    matched_share,
    work_counts_in_country,
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
from thought_flow.smoke.quality import QUALITY_STATES
from thought_flow.smoke.vocabulary import SMOKE_VOCABULARY_VERSION, load_provisional_vocabulary

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_gate_contracts_load_and_architecture() -> None:
    c = load_gate_contracts()
    assert c["contract_version"] == CONTRACT_VERSION
    arch = c["canonical_architecture"]
    assert arch["model"] == "separate_sensor_specific_canonical_datasets"
    assert arch["merged_cross_sensor_measurement_table"] is False
    assert arch["shared_numerical_scale"] is False
    assert c["gate_a"]["openalex"]["denominator_must_not_include_theme_phrase_filter"] is True
    assert c["gate_d"]["vocabulary_modified_after_m5"] is False
    assert c["gate_d"]["dictionary_version"] == THEME_DICT_VERSION
    assert c["status"] == "FROZEN_HUMAN_APPROVED"
    assert c["gate_e"]["multi_country"]["freeze_status"] == "FROZEN_HUMAN_RATIFIED"
    assert c["gate_e"]["unknown"]["non_target_structured_code_is_not_unknown"] is True
    assert c["gate_e"]["unknown"]["invented_acceptance_threshold"] is False
    assert "m5_rf_pass_with_limitations" in c["human_approval"]["accepted"]
    assert c["trends_obs1_obs2"]["obs2_blocks_openalex_m7"] is False
    excluded = set(c["deferred_or_excluded_from_m6"])
    assert "m7_historical_backfill" in excluded
    assert "github_methodology" in excluded
    assert "company_methodology" in excluded


def test_theme_dict_v1_unchanged_from_m5_seed() -> None:
    td = load_theme_dict_v1()
    assert td["version"] == THEME_DICT_VERSION
    assert td["seed_from"] == SMOKE_VOCABULARY_VERSION
    assert td["vocabulary_modified_after_m5"] is False
    assert theme_terms_unchanged_from_m5_seed() is True
    seed = load_provisional_vocabulary()
    assert td["themes"] == seed["themes"]


def test_theme_dict_v1_deterministic_match_and_no_standalone_agent() -> None:
    ev = classify_with_theme_dict_v1(
        "Advances in generative AI systems", theme="generative_ai", field_name="title"
    )
    assert ev.provisional_match is True
    assert ev.smoke_vocabulary_version == THEME_DICT_VERSION

    agent = classify_with_theme_dict_v1("An agent for booking", theme="ai_agent")
    assert agent.provisional_match is False

    ai_agent = classify_with_theme_dict_v1("Building an AI agent", theme="ai_agent")
    assert ai_agent.provisional_match is True


def test_m5_review_provenance_in_contract() -> None:
    c = load_gate_contracts()
    prov = c["gate_d"]["m5_review_provenance"]
    assert prov["mode"] == "human_delegated_ai_assisted"
    assert prov["manual_row_by_row_human_review"] is False
    assert prov["agree"] == 62
    assert prov["disagree"] == 11
    assert prov["unsure"] == 2
    assert "term_emergence_confounding" in c["gate_d"]
    assert c["gate_d"]["term_emergence_confounding"]["frozen"] is True


def test_gate_a_denominator_theme_independent() -> None:
    assert_denominator_query_theme_independent(
        {
            "query_kind": "country_week_denominator",
            "country": "JP",
            "publication_date_from": "2024-10-07",
            "publication_date_to": "2024-10-13",
        }
    )
    with pytest.raises(ValueError, match="theme"):
        assert_denominator_query_theme_independent(
            {
                "query_kind": "denominator",
                "country": "JP",
                "search": "generative AI",
            }
        )
    with pytest.raises(ValueError, match="search"):
        assert_denominator_query_theme_independent(
            {
                "query_kind": "denominator",
                "filter_search": "AI agent",
            }
        )


def test_matched_share_and_compatible_counts() -> None:
    assert matched_share(matched_works=3, denominator_works=10) == 0.3
    assert matched_share(matched_works=0, denominator_works=0) is None
    with pytest.raises(ValueError):
        matched_share(matched_works=5, denominator_works=2)


def test_inclusion_counting_unknown_and_multi_country() -> None:
    assert TARGET_COUNTRIES == frozenset({"JP", "US", "KR", "CN"})
    assert inclusion_country_hits(["JP", "US", "jp"]) == frozenset({"JP", "US"})
    assert work_counts_in_country(["JP", "US"], "JP") is True
    assert work_counts_in_country(["JP", "US"], "KR") is False
    assert is_multi_country(["JP", "CN"]) is True
    assert is_unknown_country([]) is True
    assert is_unknown_country([None, ""]) is True
    assert is_unknown_country(["JP"]) is False
    # Non-target structured codes: not unknown; also not target inclusion hits.
    assert inclusion_country_hits(["DE", "FR"]) == frozenset()
    assert is_unknown_country(["DE"]) is False
    assert is_unknown_country(["DE", "JP"]) is False


def test_openalex_iso_week_and_boundary_flag() -> None:
    assert openalex_iso_week_id("2022-11-30") == "2022-W48"
    assert ANALYSIS_WINDOW_START == date(2022, 11, 30)
    # 2022-W48 contains 2022-11-28..2022-12-04; start mid-week → boundary.
    assert flag_boundary_week("2022-W48") is True
    # A fully interior week after start should not flag on start alone.
    assert flag_boundary_week("2024-W41") is False
    assert flag_boundary_week("2024-W41", window_end=date(2024, 10, 10)) is True


def test_quality_states_preserved() -> None:
    c = load_gate_contracts()
    assert set(c["quality_states"]["states"]) == set(QUALITY_STATES)
    assert "unknown_neq_zero" in c["quality_states"]["invariants"]


def test_decision_record_exists_and_names_tbd008() -> None:
    path = REPO_ROOT / "docs" / "decisions" / "m6-methodology-freeze.md"
    text = path.read_text(encoding="utf-8")
    assert "TFO-M6-001" in text
    assert "THEME-DICT/v1" in text
    assert "TBD-008" in text
    assert "inclusion counting" in text.lower() or "Inclusion counting" in text
    assert "term-emergence" in text.lower() or "Term-emergence" in text
    assert "Human-delegated AI-assisted" in text
    assert "M7 historical backfill" in text or "m7_historical_backfill" in text


def test_theme_dict_json_roundtrip_public() -> None:
    raw = json.loads(
        (REPO_ROOT / "config" / "themes" / "theme_dict_v1.json").read_text(encoding="utf-8")
    )
    assert raw["version"] == THEME_DICT_VERSION
    assert "api_key" not in json.dumps(raw).lower()
