"""Trends transport reconciliation — non-live contract and fixture tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_flow.smoke.periods import TRENDS_FULL
from thought_flow.smoke.trends.acquisition_contract import (
    assert_contract_matches_tfo_sot,
    build_acquisition_contract,
)
from thought_flow.smoke.trends.csv_import import import_human_csv
from thought_flow.smoke.trends.pipeline import acquire_and_import, human_csv_transport
from thought_flow.smoke.trends.probes import ZERO_SEMANTICS_TRENDS, paired_probes
from thought_flow.smoke.trends.transport import (
    EXPLORE_WIDGET_LIVE_AUTHORIZED,
    ExploreWidgetCsvTransport,
    TrendsTransportError,
    extract_timeseries_request_token,
    map_http_failure_to_transport_error,
    parse_explore_widgets,
    select_timeseries_widget,
    strip_google_json_prefix,
)

SAMPLE = Path("data/samples/m5_trends_ui_synthetic_us.csv")

# Fixture shaped like Explore widgets (not from an external project's hard-coded research rules).
_EXPLORE_FIXTURE = (
    ")]}'\n"
    + json.dumps(
        {
            "widgets": [
                {"id": "RELATED_QUERIES", "request": {"x": 1}, "token": "ignore"},
                {
                    "id": "TIMESERIES",
                    "request": {"time": "2022-11-30 2026-08-16", "resolution": "WEEK"},
                    "token": "timeseries-token-fixture",
                },
            ]
        }
    )
)


def test_contract_driven_by_tfo_not_external_hardcode() -> None:
    c = build_acquisition_contract(geo="JP", observation_index=1)
    assert_contract_matches_tfo_sot(c)
    assert c.term1 == "生成AI"
    assert c.term2 == "AIエージェント"
    assert c.inclusive_start == "2022-11-30"
    assert c.inclusive_end == "2026-08-16"
    assert c.period_id == TRENDS_FULL.period_id
    assert c.zero_semantics == ZERO_SEMANTICS_TRENDS
    # Must not embed a foreign project's observation calendar / term list.
    assert "OBSERVATIONS" not in c.obs_id


def test_both_probes_in_one_comparison_payload() -> None:
    c = build_acquisition_contract(geo="US", observation_index=1)
    body = c.explore_comparison_payload()
    items = body["comparisonItem"]
    assert len(items) == 2
    assert items[0]["keyword"] == paired_probes("US")[0]
    assert items[1]["keyword"] == paired_probes("US")[1]
    assert items[0]["geo"] == items[1]["geo"] == "US"
    assert items[0]["time"] == items[1]["time"] == c.explore_time
    assert body["category"] == 0
    assert body["property"] == ""


def test_geo_date_category_property_preserved_exactly() -> None:
    c = build_acquisition_contract(geo="KR", observation_index=2)
    body = ExploreWidgetCsvTransport().build_explore_body(c)
    assert body == c.explore_comparison_payload()
    assert c.explore_time == f"{c.inclusive_start} {c.inclusive_end}"


def test_google_anti_xssi_prefix_parsing() -> None:
    assert strip_google_json_prefix(")]}'\n{\"a\":1}") == '{"a":1}'
    assert strip_google_json_prefix(b')]}\'\n{"a":1}') == '{"a":1}'
    assert strip_google_json_prefix('{"a":1}') == '{"a":1}'


def test_timeseries_widget_selection_and_passthrough() -> None:
    widgets = parse_explore_widgets(_EXPLORE_FIXTURE)
    ts = select_timeseries_widget(widgets)
    assert ts["id"] == "TIMESERIES"
    request, token = extract_timeseries_request_token(ts)
    assert request == {"time": "2022-11-30 2026-08-16", "resolution": "WEEK"}
    assert token == "timeseries-token-fixture"


def test_missing_timeseries_is_not_zero() -> None:
    raw = ")]}'\n" + json.dumps({"widgets": [{"id": "RELATED_TOPICS"}]})
    widgets = parse_explore_widgets(raw)
    with pytest.raises(TrendsTransportError) as ei:
        select_timeseries_widget(widgets)
    assert ei.value.code == "missing_timeseries_widget"
    assert "zero" not in ei.value.code


def test_http_failure_and_429_not_zero() -> None:
    e429 = map_http_failure_to_transport_error(429)
    e500 = map_http_failure_to_transport_error(500)
    assert e429.code == "http_429"
    assert e500.code == "http_500"
    assert "not a valid Trends zero" in str(e429)


def test_transport_b_live_disabled() -> None:
    assert EXPLORE_WIDGET_LIVE_AUTHORIZED is False
    c = build_acquisition_contract(geo="US", observation_index=1)
    with pytest.raises(TrendsTransportError) as ei:
        ExploreWidgetCsvTransport().acquire_csv(c)
    assert ei.value.code == "transport_b_smoke_blocked"


def test_failed_geo_does_not_overwrite_prior_success(tmp_path: Path) -> None:
    csv_path = tmp_path / "us.csv"
    csv_path.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    data_root = tmp_path / "ws"
    ok = acquire_and_import(
        transport=human_csv_transport(csv_path),
        geo="US",
        observation_index=1,
        data_root=data_root,
        code_revision="test",
        staging_dir=tmp_path / "stage",
    )
    assert ok["status"] == "succeeded"
    success_root = Path(ok["artifact_root"])
    manifest_before = (success_root / "manifest.json").read_text(encoding="utf-8")

    # Simulate later GEO failure via unauthorized Transport B — must not touch prior run.
    fail = acquire_and_import(
        transport=ExploreWidgetCsvTransport(),
        geo="JP",
        observation_index=1,
        data_root=data_root,
        code_revision="test",
        staging_dir=tmp_path / "stage2",
    )
    assert fail["status"] in {"fetch_failure", "SMOKE-BLOCKED"}
    assert fail["zero_coerced"] is False
    assert (success_root / "manifest.json").read_text(encoding="utf-8") == manifest_before


def test_human_csv_import_regression(tmp_path: Path) -> None:
    csv_path = tmp_path / "export.csv"
    csv_path.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    m = import_human_csv(
        csv_path=csv_path,
        country="US",
        data_root=tmp_path / "ws",
        code_revision="test",
        observation_index=1,
    )
    assert m["status"] == "succeeded"
    assert m["ui_automation"] is False
    assert m["production_connector"] is False


def test_exact_csv_bytes_preserved_through_human_transport(tmp_path: Path) -> None:
    raw = SAMPLE.read_bytes()
    csv_path = tmp_path / "exact.csv"
    csv_path.write_bytes(raw)
    result = human_csv_transport(csv_path).acquire_csv(
        build_acquisition_contract(geo="US", observation_index=1)
    )
    assert result.csv_bytes == raw


def test_no_production_connector_registration() -> None:
    assert Path("src/thought_flow/smoke/trends/transport.py").is_file()
    integrations = Path("src/thought_flow/integrations")
    if integrations.exists():
        names = {p.name for p in integrations.iterdir()}
        assert "trends" not in names
        assert "google_trends" not in names
