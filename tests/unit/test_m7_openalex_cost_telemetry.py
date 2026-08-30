"""TFO-M7-006: OpenAlex source-reported cost telemetry."""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from thought_flow.ingestion.openalex.backfill import production_openalex_client
from thought_flow.ingestion.openalex.campaign import run_openalex_backfill_campaign
from thought_flow.smoke.http_client import (
    RequestBudget,
    SmokeHttpClient,
    coerce_source_reported_cost_usd,
    resolve_openalex_cost_usd,
)
from thought_flow.smoke.openalex.client import OpenAlexClient

FIXED_END = date(2026, 8, 30)


def test_coerce_rejects_invalid_keeps_zero() -> None:
    assert coerce_source_reported_cost_usd(0) == 0.0
    assert coerce_source_reported_cost_usd(0.0) == 0.0
    assert coerce_source_reported_cost_usd("0.0001") == pytest.approx(0.0001)
    assert coerce_source_reported_cost_usd(None) is None
    assert coerce_source_reported_cost_usd(True) is None
    assert coerce_source_reported_cost_usd(False) is None
    assert coerce_source_reported_cost_usd("nope") is None
    assert coerce_source_reported_cost_usd(-0.01) is None
    assert coerce_source_reported_cost_usd(float("nan")) is None
    assert coerce_source_reported_cost_usd(float("inf")) is None
    assert coerce_source_reported_cost_usd(float("-inf")) is None


def test_resolve_prefers_header_over_payload() -> None:
    payload = {"meta": {"cost_usd": 0.99}}
    assert resolve_openalex_cost_usd(
        headers={"X-API-Cost": "0.02"}, payload=payload
    ) == pytest.approx(0.02)
    assert resolve_openalex_cost_usd(headers={}, payload=payload) == pytest.approx(0.99)
    assert resolve_openalex_cost_usd(headers={}, payload={"meta": {}}) is None
    assert resolve_openalex_cost_usd(headers={}, payload=None) is None


def test_header_cost_only_registered_once_on_retry() -> None:
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        if calls["n"] == 1:
            return 500, {"X-API-Cost": "0.02"}, b"err"
        return 200, {"X-API-Cost": "0.03"}, b"{}"

    budget = RequestBudget(max_attempts=10, max_cost_usd=10.0)
    client = SmokeHttpClient(budget=budget, transport=transport, sleep_fn=lambda **_: None)
    resp = client.get("https://example.test/")
    assert resp.status_code == 200
    assert len(resp.attempts) == 2
    assert budget.attempts_used == 2
    # Only terminal response cost — not 0.02 + 0.03.
    assert budget.reported_cost_usd == pytest.approx(0.03)
    assert budget.cost_report_count == 1


def test_payload_meta_cost_fallback_without_header() -> None:
    body = json.dumps({"meta": {"cost_usd": 0.0001, "count": 1}, "results": []}).encode()

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, body

    budget = RequestBudget(max_attempts=5, max_cost_usd=10.0)
    http = SmokeHttpClient(budget=budget, transport=transport, sleep_fn=lambda **_: None)
    client = OpenAlexClient(http=http, api_key=None)
    payload, meta = client.fetch_works_page(
        filter_expr="from_publication_date:2023-01-01,to_publication_date:2023-01-01",
        search=None,
        cursor="*",
        per_page=1,
    )
    assert payload["meta"]["cost_usd"] == pytest.approx(0.0001)
    assert meta["cost_usd"] == pytest.approx(0.0001)
    assert budget.reported_cost_usd == pytest.approx(0.0001)
    assert budget.cost_report_count == 1


def test_header_and_payload_not_double_counted() -> None:
    body = json.dumps({"meta": {"cost_usd": 0.99}, "results": []}).encode()

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {"X-API-Cost": "0.02"}, body

    budget = RequestBudget(max_attempts=5, max_cost_usd=10.0)
    http = SmokeHttpClient(budget=budget, transport=transport, sleep_fn=lambda **_: None)
    client = OpenAlexClient(http=http, api_key=None)
    _, meta = client.fetch_works_page(
        filter_expr="from_publication_date:2023-01-01,to_publication_date:2023-01-01",
        search=None,
        cursor="*",
        per_page=1,
    )
    assert meta["cost_usd"] == pytest.approx(0.02)
    assert budget.reported_cost_usd == pytest.approx(0.02)
    assert budget.cost_report_count == 1


def test_source_reported_zero_preserved() -> None:
    body = json.dumps({"meta": {"cost_usd": 0.0}, "results": []}).encode()

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, body

    budget = RequestBudget(max_attempts=5, max_cost_usd=10.0)
    http = SmokeHttpClient(budget=budget, transport=transport, sleep_fn=lambda **_: None)
    client = OpenAlexClient(http=http, api_key=None)
    _, meta = client.fetch_works_page(
        filter_expr="from_publication_date:2023-01-01,to_publication_date:2023-01-01",
        search=None,
        cursor="*",
        per_page=1,
    )
    assert meta["cost_usd"] == 0.0
    assert budget.reported_cost_usd == 0.0
    assert budget.reported_cost_usd is not None


def test_unreported_cost_stays_null() -> None:
    body = json.dumps({"meta": {"count": 0}, "results": []}).encode()

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, body

    budget = RequestBudget(max_attempts=5, max_cost_usd=10.0)
    http = SmokeHttpClient(budget=budget, transport=transport, sleep_fn=lambda **_: None)
    client = OpenAlexClient(http=http, api_key=None)
    _, meta = client.fetch_works_page(
        filter_expr="from_publication_date:2023-01-01,to_publication_date:2023-01-01",
        search=None,
        cursor="*",
        per_page=1,
    )
    assert meta["cost_usd"] is None
    assert budget.reported_cost_usd is None


@pytest.mark.parametrize(
    "bad",
    [None, "x", -1, float("inf"), True],
)
def test_invalid_payload_cost_ignored(bad: Any) -> None:
    meta: dict[str, Any] = {"count": 0, "cost_usd": bad}
    body = json.dumps({"meta": meta, "results": []}).encode()

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, body

    budget = RequestBudget(max_attempts=5, max_cost_usd=10.0)
    http = SmokeHttpClient(budget=budget, transport=transport, sleep_fn=lambda **_: None)
    client = OpenAlexClient(http=http, api_key=None)
    _, m = client.fetch_works_page(
        filter_expr="from_publication_date:2023-01-01,to_publication_date:2023-01-01",
        search=None,
        cursor="*",
        per_page=1,
    )
    assert m["cost_usd"] is None
    assert budget.reported_cost_usd is None


def test_nan_payload_cost_ignored() -> None:
    assert coerce_source_reported_cost_usd(float("nan")) is None
    # Inject NaN after JSON round-trip is impossible; unit-test coerce only.


def test_multi_page_payload_costs_sum_into_campaign(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    ck = tmp_path / "ck"
    man = tmp_path / "man"
    raw.mkdir()
    ck.mkdir()
    man.mkdir()
    pages = [
        {
            "meta": {"count": 2, "cost_usd": 0.0001, "next_cursor": "page2"},
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "A",
                    "display_name": "A",
                    "type": "article",
                    "language": "en",
                    "publication_date": "2022-12-01",
                    "publication_year": 2022,
                    "created_date": "2022-12-02",
                    "updated_date": "2022-12-03",
                    "abstract_inverted_index": None,
                    "authorships": [
                        {
                            "author": {"id": "https://openalex.org/A1", "display_name": "Hidden"},
                            "institutions": [
                                {
                                    "id": "https://openalex.org/I1",
                                    "type": "education",
                                    "country_code": "JP",
                                }
                            ],
                            "countries": ["JP"],
                        }
                    ],
                    "primary_location": {
                        "source": {"id": "S1", "display_name": "J", "type": "journal"}
                    },
                }
            ],
        },
        {
            "meta": {"count": 2, "cost_usd": 0.0002, "next_cursor": None},
            "results": [
                {
                    "id": "https://openalex.org/W2",
                    "title": "B",
                    "display_name": "B",
                    "type": "article",
                    "language": "en",
                    "publication_date": "2022-12-01",
                    "publication_year": 2022,
                    "created_date": "2022-12-02",
                    "updated_date": "2022-12-03",
                    "abstract_inverted_index": None,
                    "authorships": [
                        {
                            "author": {"id": "https://openalex.org/A2", "display_name": "Hidden2"},
                            "institutions": [
                                {
                                    "id": "https://openalex.org/I1",
                                    "type": "education",
                                    "country_code": "JP",
                                }
                            ],
                            "countries": ["JP"],
                        }
                    ],
                    "primary_location": {
                        "source": {"id": "S1", "display_name": "J", "type": "journal"}
                    },
                }
            ],
        },
    ]
    idx = {"i": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        i = idx["i"]
        idx["i"] += 1
        return 200, {}, json.dumps(pages[i]).encode()

    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
        run_end_date=FIXED_END,
        max_partitions=1,
        client=client,
        install_signal_handlers=False,
    )
    summary = result.to_public_summary()
    assert summary["coverage"]["approximate_cost_usd"] == pytest.approx(0.0003)
    assert summary["coverage"]["approximate_cost_usd"] != 0
    manifest = json.loads(Path(result.campaign_manifest_path).read_text(encoding="utf-8"))
    assert manifest["approximate_cost_usd"] == pytest.approx(0.0003)
    blob = json.dumps(summary) + json.dumps(manifest)
    assert "api_key" not in blob.lower()
    assert "Hidden" not in blob
