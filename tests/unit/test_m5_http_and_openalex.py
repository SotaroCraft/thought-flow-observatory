"""HTTP retry, ceiling, and quality-state tests for M5 smoke."""

from __future__ import annotations

import json
from typing import Any

import pytest

from thought_flow.smoke.http_client import (
    MAX_RETRIES,
    OPENALEX_COST_CEILING_USD,
    RequestBudget,
    SmokeHttpClient,
    openalex_cost_ceiling_usd,
)
from thought_flow.smoke.openalex.client import (
    MAX_INSPECTED_PER_CELL,
    MAX_PAGES_PER_CELL,
    MAX_RETAINED_PER_CELL,
    PER_PAGE,
)
from thought_flow.smoke.openalex.runner import OpenAlexSmokeRunner
from thought_flow.smoke.quality import QUALITY_STATES


def test_frozen_quality_states() -> None:
    assert QUALITY_STATES == {"zero", "missing", "unknown", "fetch_failure", "partial"}


def test_openalex_ceilings_match_spec() -> None:
    assert PER_PAGE == 25
    assert MAX_RETAINED_PER_CELL == 100
    assert MAX_INSPECTED_PER_CELL == 300
    assert MAX_PAGES_PER_CELL == 12
    assert OPENALEX_COST_CEILING_USD == 0.75
    assert openalex_cost_ceiling_usd(has_api_key=True) == 0.75
    assert openalex_cost_ceiling_usd(has_api_key=False) == pytest.approx(0.075)


def test_retry_on_429_respects_operable_retry_after() -> None:
    calls = {"n": 0}
    sleeps: list[tuple[int, str | None]] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        if calls["n"] < 3:
            return 429, {"Retry-After": "0"}, b'{"error":"rate"}'
        return 200, {"X-API-Cost": "0.01"}, b'{"meta":{"count":0},"results":[]}'

    def sleep_fn(*, attempt_index: int, retry_after: str | None) -> None:
        sleeps.append((attempt_index, retry_after))

    client = SmokeHttpClient(transport=transport, sleep_fn=sleep_fn)
    resp = client.get("https://api.openalex.org/works")
    assert resp.status_code == 200
    assert len(resp.attempts) == 3
    assert MAX_RETRIES == 2
    assert sleeps[0][1] == "0"


def test_429_with_non_operable_retry_after_does_not_retry_or_shorten() -> None:
    sleeps: list[Any] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 429, {"Retry-After": "43633"}, b'{"error":"rate"}'

    def sleep_fn(*, attempt_index: int, retry_after: str | None) -> None:
        sleeps.append((attempt_index, retry_after))

    client = SmokeHttpClient(transport=transport, sleep_fn=sleep_fn)
    resp = client.get("https://api.openalex.org/works")
    assert resp.status_code == 429
    assert len(resp.attempts) == 1
    assert sleeps == []
    assert resp.terminal_blocker == "retry_after_not_operable"
    assert resp.attempts[0].retry_skipped_reason == "retry_after_not_operable"


def test_retry_on_5xx_then_success() -> None:
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        if calls["n"] == 1:
            return 503, {}, b"unavailable"
        return 200, {}, b'{"ok":true}'

    client = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    resp = client.get("https://example.test/")
    assert resp.status_code == 200
    assert len(resp.attempts) == 2


def test_no_retry_on_400() -> None:
    def transport(url: str, headers: dict[str, str], timeout: float):
        return 400, {}, b"bad"

    client = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    resp = client.get("https://example.test/")
    assert resp.status_code == 400
    assert len(resp.attempts) == 1


def test_request_ceiling_stops() -> None:
    budget = RequestBudget(max_attempts=2, max_cost_usd=10.0)

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, b"{}"

    client = SmokeHttpClient(budget=budget, transport=transport, sleep_fn=lambda **_: None)
    client.get("https://example.test/1")
    client.get("https://example.test/2")
    with pytest.raises(RuntimeError, match="ceiling|budget"):
        client.get("https://example.test/3")


def _page(results: list[dict[str, Any]], count: int, next_cursor: str | None = None) -> bytes:
    meta: dict[str, Any] = {"count": count}
    if next_cursor:
        meta["next_cursor"] = next_cursor
    return json.dumps({"meta": meta, "results": results}).encode("utf-8")


def _work(wid: str, title: str, countries: list[str] | None = None) -> dict[str, Any]:
    authorships = []
    if countries:
        authorships = [
            {
                "author": {"id": "https://openalex.org/A1", "display_name": "Hidden Person"},
                "institutions": [
                    {"id": "https://openalex.org/I1", "type": "education", "country_code": countries[0]}
                ],
                "countries": countries,
            }
        ]
    return {
        "id": f"https://openalex.org/{wid}",
        "title": title,
        "display_name": title,
        "type": "article",
        "language": "en",
        "publication_date": "2022-12-01",
        "publication_year": 2022,
        "created_date": "2022-12-02",
        "updated_date": "2022-12-03",
        "abstract_inverted_index": None,
        "authorships": authorships,
        "primary_location": {"source": {"id": "S1", "display_name": "J", "type": "journal"}},
    }


def test_synthetic_openalex_runner_append_only_and_privacy(tmp_path) -> None:
    # Deterministic fixture transport: empty for most phrases; one hit for GenAI US OA-START.
    def transport(url: str, headers: dict[str, str], timeout: float):
        if "search=" in url and "generative" in url.lower() and "authorships.countries%3Aus" in url.lower().replace(
            "%3a", ":"
        ).replace("%3A", ":"):
            # Normalize check: country filter present and generative search.
            pass
        lower = url.lower()
        if "search=generative+ai" in lower or "search=generative%20ai" in lower:
            if "authorships.countries:us" in lower or "authorships.countries%3aus" in lower:
                body = _page([_work("W100", "Survey of generative AI", ["US"])], count=1)
                return 200, {}, body
        if "search=" not in lower:
            # denominator
            body = _page([], count=42)
            return 200, {}, body
        body = _page([], count=0)
        return 200, {}, body

    http = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    data_root = tmp_path / "workspace-data"
    runner = OpenAlexSmokeRunner(
        data_root=data_root,
        code_revision="testrev",
        api_key=None,
        http=http,
    )
    summary1 = runner.run()
    assert summary1["status"] in {"succeeded", "partial"}
    run1 = summary1["run_id"]
    assert (data_root / "m5-smoke" / "runs" / run1 / "manifest.json").is_file()
    assert (data_root / "m5-smoke" / "runs" / run1 / "queries.jsonl").is_file()
    assert (data_root / "m5-smoke" / "runs" / run1 / "coverage.csv").is_file()

    raw_files = list((data_root / "m5-smoke" / "runs" / run1 / "raw" / "openalex").glob("*.jsonl"))
    assert raw_files
    raw_row = json.loads(raw_files[0].read_text(encoding="utf-8").splitlines()[0])
    assert "Hidden Person" not in json.dumps(raw_row)
    assert "author" not in raw_row["envelope"]
    content_id_1 = raw_row["raw_content_identity"]
    assert content_id_1 == raw_row["envelope"]["raw_content_identity"]
    assert content_id_1.startswith("raw_")
    assert not content_id_1.startswith("sha256:")
    assert raw_row["envelope"]["persisted_envelope_checksum"].startswith("sha256:")

    # Second run must create a new run directory (append-only) with same content identity.
    http2 = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    runner2 = OpenAlexSmokeRunner(
        data_root=data_root,
        code_revision="testrev",
        api_key=None,
        http=http2,
    )
    summary2 = runner2.run()
    assert summary2["run_id"] != run1
    runs = list((data_root / "m5-smoke" / "runs").iterdir())
    assert len(runs) == 2

    raw_files_2 = list(
        (data_root / "m5-smoke" / "runs" / summary2["run_id"] / "raw" / "openalex").glob("*.jsonl")
    )
    assert raw_files_2
    raw_row_2 = json.loads(raw_files_2[0].read_text(encoding="utf-8").splitlines()[0])
    assert raw_row_2["raw_content_identity"] == content_id_1
    assert raw_row_2["run_id"] != raw_row["run_id"]

    # Phrase counts must not be summed into cell source_total.
    theme_rows = [r for r in runner.coverage if r["cell_kind"] == "country_theme"]
    assert theme_rows
    for row in theme_rows:
        assert row["source_total"] is None
        assert isinstance(row["phrase_source_counts"], dict)

    denom_rows = [r for r in runner.coverage if r["cell_kind"] == "country_period_denominator"]
    assert denom_rows
    for row in denom_rows:
        assert row["source_total"] == 42
        assert row["observation_complete"] is True
        assert row["quality_state"] != "partial"

    # Quality states used are subset of frozen set.
    for row in runner.coverage:
        assert row["quality_state"] in QUALITY_STATES


def test_retain_cap_marks_partial(tmp_path) -> None:
    works = [_work(f"W{i}", f"Paper {i} on generative AI", ["US"]) for i in range(120)]

    def transport(url: str, headers: dict[str, str], timeout: float):
        lower = url.lower()
        if "search=" not in lower:
            return 200, {}, _page([], count=0)
        # Always return first 25 of a large population for generative AI US searches.
        if "generative" in lower and ("countries:us" in lower or "countries%3aus" in lower):
            page = works[:25]
            return 200, {}, _page(page, count=120, next_cursor="nextpage")
        return 200, {}, _page([], count=0)

    # Monkeypatch ceilings for a fast unit test.
    import thought_flow.smoke.openalex.runner as runner_mod
    import thought_flow.smoke.openalex.client as client_mod

    old = (
        runner_mod.MAX_RETAINED_PER_CELL,
        runner_mod.MAX_INSPECTED_PER_CELL,
        runner_mod.MAX_PAGES_PER_CELL,
        client_mod.MAX_RETAINED_PER_CELL,
    )
    runner_mod.MAX_RETAINED_PER_CELL = 5
    runner_mod.MAX_INSPECTED_PER_CELL = 50
    runner_mod.MAX_PAGES_PER_CELL = 3
    try:
        http = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
        runner = OpenAlexSmokeRunner(
            data_root=tmp_path / "ws",
            code_revision="test",
            http=http,
        )
        # Run a single cell path via private helper for speed.
        from thought_flow.smoke.periods import OA_START

        cell = runner._run_theme_cell(country="US", theme="generative_ai", period=OA_START)
        assert cell.retained_count <= 5
        assert cell.quality_state == "partial"
        assert cell.truncation is True
        assert cell.observation_complete is False
        assert cell.source_total is None
    finally:
        (
            runner_mod.MAX_RETAINED_PER_CELL,
            runner_mod.MAX_INSPECTED_PER_CELL,
            runner_mod.MAX_PAGES_PER_CELL,
            client_mod.MAX_RETAINED_PER_CELL,
        ) = old


def test_complete_small_population_is_not_partial(tmp_path) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float):
        lower = url.lower()
        if "search=" not in lower:
            return 200, {}, _page([], count=0)
        if "generative+ai" in lower or "generative%20ai" in lower:
            if "countries:us" in lower or "countries%3aus" in lower:
                return 200, {}, _page(
                    [_work("W1", "Survey of generative AI", ["US"])], count=1
                )
        return 200, {}, _page([], count=0)

    http = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    runner = OpenAlexSmokeRunner(data_root=tmp_path / "ws", code_revision="test", http=http)
    from thought_flow.smoke.periods import OA_START

    cell = runner._run_theme_cell(country="US", theme="generative_ai", period=OA_START)
    assert cell.retained_count >= 1
    assert cell.matched_count >= 1
    assert cell.truncation is False
    assert cell.observation_complete is True
    assert cell.quality_state != "partial"
    assert cell.source_total is None
    assert cell.phrase_source_counts.get("generative AI") == 1


def test_denominator_uses_per_page_one(tmp_path) -> None:
    seen: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        seen.append(url)
        return 200, {}, _page([], count=7)

    http = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    runner = OpenAlexSmokeRunner(data_root=tmp_path / "ws", code_revision="test", http=http)
    from thought_flow.smoke.periods import OA_START

    cell = runner._run_denominator(country="US", period=OA_START)
    assert cell.source_total == 7
    assert cell.quality_state != "partial"
    assert any("per-page=1" in u or "per-page%3D1" in u for u in seen)
