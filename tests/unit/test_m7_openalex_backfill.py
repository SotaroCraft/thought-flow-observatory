"""M7 OpenAlex backfill foundation — cursor, Raw immutability, coverage, resume."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pyarrow.parquet as pq
import pytest

from thought_flow.ingestion.openalex.backfill import (
    PRODUCTION_PER_PAGE,
    OpenAlexBackfillRunner,
    assert_no_smoke_ceilings_on_production_path,
    classify_partition_coverage,
    production_openalex_client,
    run_openalex_partition_backfill,
)
from thought_flow.ingestion.openalex.checkpoint import load_checkpoint
from thought_flow.ingestion.openalex.window import (
    BACKFILL_WINDOW_START,
    RetrievalPartition,
    capture_run_end_date,
)
from thought_flow.ingestion.raw_store import load_content_payload, persist_raw_record
from thought_flow.observability.identity import new_run_identity, raw_content_identity
from thought_flow.smoke.http_client import MAX_RETRIES, SmokeHttpClient
from thought_flow.smoke.openalex.client import (
    MAX_INSPECTED_PER_CELL,
    MAX_PAGES_PER_CELL,
    MAX_RETAINED_PER_CELL,
    PER_PAGE,
)


def _page(results: list[dict[str, Any]], count: int, next_cursor: str | None = None) -> bytes:
    meta: dict[str, Any] = {"count": count}
    if next_cursor:
        meta["next_cursor"] = next_cursor
    return json.dumps({"meta": meta, "results": results}).encode("utf-8")


def _work(
    wid: str,
    title: str,
    *,
    countries: list[str] | None = None,
    institution_countries: list[str] | None = None,
) -> dict[str, Any]:
    authorships: list[dict[str, Any]] = []
    if countries or institution_countries:
        inst_codes = institution_countries or (countries[:1] if countries else [])
        institutions = [
            {
                "id": f"https://openalex.org/I{wid}-{i}",
                "type": "education",
                "country_code": code,
                "display_name": f"Inst {code}",
            }
            for i, code in enumerate(inst_codes)
        ]
        authorships = [
            {
                "author": {"id": "https://openalex.org/A1", "display_name": "Hidden Person"},
                "institutions": institutions,
                "countries": countries or [],
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


def _cursor_from_url(url: str) -> str:
    query = parse_qs(urlsplit(url).query)
    values = query.get("cursor") or ["*"]
    return values[0]


def _dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw = tmp_path / "raw"
    ck = tmp_path / "checkpoints"
    man = tmp_path / "manifests"
    raw.mkdir()
    ck.mkdir()
    man.mkdir()
    return raw, ck, man


def test_capture_run_end_date_once_and_deterministic() -> None:
    fixed = date(2026, 8, 30)
    assert capture_run_end_date(clock=lambda: fixed) == fixed
    assert BACKFILL_WINDOW_START == date(2022, 11, 30)
    part = RetrievalPartition.full_window(country="US", run_end_date=fixed)
    assert part.inclusive_start == BACKFILL_WINDOW_START
    assert part.inclusive_end == fixed
    # Injected end date must not drift across calls when frozen on runner.
    raw = Path(".")
    runner = OpenAlexBackfillRunner(
        raw_dir=raw,
        checkpoint_dir=raw,
        manifests_dir=raw,
        run_end_date=fixed,
        client=production_openalex_client(sleep_fn=lambda **_: None),
    )
    assert runner._resolve_run_end_date() == fixed
    assert runner._resolve_run_end_date() == fixed


def test_production_path_has_no_smoke_ceiling() -> None:
    assert_no_smoke_ceilings_on_production_path()
    assert PRODUCTION_PER_PAGE != PER_PAGE or PRODUCTION_PER_PAGE == 200
    assert PRODUCTION_PER_PAGE == 200
    assert MAX_PAGES_PER_CELL == 12
    assert MAX_RETAINED_PER_CELL == 100
    assert MAX_INSPECTED_PER_CELL == 300
    client = production_openalex_client(sleep_fn=lambda **_: None)
    assert client.http.budget.max_attempts > MAX_PAGES_PER_CELL
    assert client.http.budget.max_cost_usd > 0.75
    runner = OpenAlexBackfillRunner(
        raw_dir=Path("."),
        checkpoint_dir=Path("."),
        manifests_dir=Path("."),
        client=client,
    )
    assert runner.has_smoke_page_ceiling is False


def test_classify_coverage_states() -> None:
    assert (
        classify_partition_coverage(
            attempted=False, pages_completed=0, exhausted=False, fetch_failed=False, works_count=0
        )
        == "missing"
    )
    assert (
        classify_partition_coverage(
            attempted=True, pages_completed=0, exhausted=False, fetch_failed=True, works_count=0
        )
        == "fetch_failure"
    )
    assert (
        classify_partition_coverage(
            attempted=True, pages_completed=2, exhausted=False, fetch_failed=True, works_count=10
        )
        == "partial"
    )
    assert (
        classify_partition_coverage(
            attempted=True, pages_completed=1, exhausted=True, fetch_failed=False, works_count=0
        )
        == "zero"
    )
    assert (
        classify_partition_coverage(
            attempted=True, pages_completed=2, exhausted=True, fetch_failed=False, works_count=5
        )
        == "success"
    )
    assert (
        classify_partition_coverage(
            attempted=True,
            pages_completed=1,
            exhausted=True,
            fetch_failed=False,
            works_count=1,
            source_reported_count=100,
        )
        == "partial"
    )
    assert "zero" != "missing"
    assert "fetch_failure" != "zero"
    assert "partial" != "success"


def test_premature_terminal_page_is_partial_not_success(tmp_path: Path) -> None:
    """Source claims more Works than returned with next_cursor absent → partial."""

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, _page([_work("W60", "OnlyOne", countries=["US"])], count=50)

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "partial"
    assert result.coverage_status != "success"
    assert result.works_persisted == 1
    assert result.source_reported_count == 50


def test_repeated_cursor_fails_closed_as_partial(tmp_path: Path) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, _page(
            [_work("W70", "Loop", countries=["US"])],
            count=2,
            next_cursor="*",  # repeats the request cursor
        )

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "partial"
    assert result.failure_category == "cursor_loop"
    assert result.pages_completed == 1
    assert result.works_persisted == 1


def test_resume_completed_page_cycle_fails_closed(tmp_path: Path) -> None:
    """Corrupt checkpoint A→B→A must not spin forever on resume."""
    from thought_flow.ingestion.openalex.checkpoint import (
        CompletedPage,
        PartitionCheckpoint,
        save_checkpoint,
        checkpoint_path,
    )

    raw, ck, man = _dirs(tmp_path)
    partition = RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1))
    corrupted = PartitionCheckpoint.new(
        partition_id=partition.partition_id,
        country="US",
        inclusive_start="2022-12-01",
        inclusive_end="2022-12-01",
        run_end_date="2026-08-30",
    )
    corrupted.record_page(
        CompletedPage(
            page_index=0,
            request_cursor="*",
            next_cursor="page2",
            source_count=2,
            result_count=1,
            work_ids=["https://openalex.org/WA"],
            raw_content_identities=["raw_a"],
            page_quality_state="success",
        )
    )
    corrupted.record_page(
        CompletedPage(
            page_index=1,
            request_cursor="page2",
            next_cursor="*",  # cycle back
            source_count=2,
            result_count=1,
            work_ids=["https://openalex.org/WB"],
            raw_content_identities=["raw_b"],
            page_quality_state="success",
        )
    )
    corrupted.exhausted = False
    corrupted.next_cursor = "*"
    save_checkpoint(checkpoint_path(ck, partition.partition_id), corrupted)

    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        return 200, {}, _page([], count=0)

    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=partition,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "partial"
    assert result.failure_category == "cursor_loop"
    assert calls["n"] == 0  # failed during resume walk, no refetch


def test_cursor_traversal_through_all_fixture_pages(tmp_path: Path) -> None:
    calls: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        cursor = _cursor_from_url(url)
        calls.append(cursor)
        if cursor == "*":
            return 200, {}, _page(
                [_work("W1", "One", countries=["US"])],
                count=3,
                next_cursor="page2",
            )
        if cursor == "page2":
            return 200, {}, _page(
                [_work("W2", "Two", countries=["US"])],
                count=3,
                next_cursor="page3",
            )
        if cursor == "page3":
            return 200, {}, _page(
                [_work("W3", "Three", countries=["US", "JP"])],
                count=3,
                next_cursor=None,
            )
        raise AssertionError(f"unexpected cursor {cursor}")

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    partition = RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1))
    result = run_openalex_partition_backfill(
        partition=partition,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
        per_page=1,
    )
    assert calls == ["*", "page2", "page3"]
    assert result.pages_completed == 3
    assert result.works_persisted == 3
    assert result.coverage_status == "success"
    assert result.exhausted is True
    assert result.source_reported_count == 3
    # No smoke page ceiling stopped early.
    assert len(calls) > 2


def test_successful_empty_is_zero_not_missing_or_failure(tmp_path: Path) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, _page([], count=0, next_cursor=None)

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="JP", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "zero"
    assert result.coverage_status != "missing"
    assert result.coverage_status != "fetch_failure"
    assert result.works_persisted == 0
    assert result.exhausted is True


def test_failure_before_any_page_is_fetch_failure(tmp_path: Path) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float):
        return 503, {}, b"unavailable"

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "fetch_failure"
    assert result.pages_completed == 0
    assert result.works_persisted == 0


def test_failure_after_persisted_pages_is_partial(tmp_path: Path) -> None:
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        cursor = _cursor_from_url(url)
        if cursor == "*":
            return 200, {}, _page(
                [_work("W10", "Keep", countries=["US"])],
                count=2,
                next_cursor="page2",
            )
        return 500, {}, b"boom"

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "partial"
    assert result.coverage_status != "success"
    assert result.pages_completed == 1
    assert result.works_persisted == 1
    assert list((raw / "content").glob("*.parquet"))


def test_retry_honors_existing_retry_contract(tmp_path: Path) -> None:
    calls = {"n": 0}
    sleeps: list[Any] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        if calls["n"] < 3:
            return 429, {"Retry-After": "0"}, b'{"error":"rate"}'
        return 200, {}, _page([], count=0)

    def sleep_fn(*, attempt_index: int, retry_after: str | None) -> None:
        sleeps.append((attempt_index, retry_after))

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=sleep_fn)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="KR", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert MAX_RETRIES == 2
    assert calls["n"] == 3
    assert sleeps[0][1] == "0"
    assert result.coverage_status == "zero"


def test_resume_skips_completed_immutable_pages(tmp_path: Path) -> None:
    phase = {"resume": False}
    fetched: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        cursor = _cursor_from_url(url)
        fetched.append(cursor)
        if cursor == "*":
            return 200, {}, _page(
                [_work("W20", "First", countries=["US"])],
                count=2,
                next_cursor="page2",
            )
        if not phase["resume"]:
            return 500, {}, b"fail-after-page1"
        return 200, {}, _page(
            [_work("W21", "Second", countries=["US"])],
            count=2,
            next_cursor=None,
        )

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    partition = RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1))
    first = run_openalex_partition_backfill(
        partition=partition,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert first.coverage_status == "partial"
    assert first.pages_completed == 1
    content_files_after_first = sorted(p.name for p in (raw / "content").glob("*.parquet"))

    phase["resume"] = True
    fetched.clear()
    second = run_openalex_partition_backfill(
        partition=partition,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert "*" not in fetched  # completed first page skipped
    assert fetched == ["page2"]
    assert second.coverage_status == "success"
    assert second.pages_completed == 2
    assert second.works_persisted == 2
    assert sorted(p.name for p in (raw / "content").glob("*.parquet")) != []
    # First page content untouched.
    assert content_files_after_first[0] in {p.name for p in (raw / "content").glob("*.parquet")}


def test_rerun_completed_partition_does_not_duplicate(tmp_path: Path) -> None:
    fetches = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        fetches["n"] += 1
        return 200, {}, _page([_work("W30", "Only", countries=["CN"])], count=1)

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    partition = RetrievalPartition.canary_day(country="CN", source_date=date(2022, 12, 1))
    first = run_openalex_partition_backfill(
        partition=partition,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    content_count = len(list((raw / "content").glob("*.parquet")))
    ck_data = load_checkpoint(first.checkpoint_path)
    assert ck_data is not None
    page_count = len(ck_data.pages)

    second = run_openalex_partition_backfill(
        partition=partition,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert second.coverage_status == "success"
    assert fetches["n"] == 1  # no refetch
    assert len(list((raw / "content").glob("*.parquet"))) == content_count
    ck_data2 = load_checkpoint(second.checkpoint_path)
    assert ck_data2 is not None
    assert len(ck_data2.pages) == page_count


def test_content_conflict_at_existing_raw_identity_fails_closed(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    payload = {"schema": "test", "work_id": "Wconflict", "title": "A"}
    first = persist_raw_record(
        raw_dir=raw_dir,
        run_identity=new_run_identity(),
        source_identity="openalex.works",
        logical_key="work:Wconflict",
        payload=payload,
        ingestion_time="2026-08-30T00:00:00Z",
    )
    # Corrupt the content-addressed object while keeping the identity path.
    table = pq.read_table(first.content_store_path)
    # Replace payload_json with conflicting bytes under the same content identity file.
    import pyarrow as pa

    bad = pa.table(
        {
            "raw_content_identity": [first.raw_content_identity],
            "payload_json": [json.dumps({"schema": "test", "work_id": "Wconflict", "title": "B"})],
        }
    )
    pq.write_table(bad, first.content_store_path)

    with pytest.raises(FileExistsError, match="Content conflict"):
        persist_raw_record(
            raw_dir=raw_dir,
            run_identity=new_run_identity(),
            source_identity="openalex.works",
            logical_key="work:Wconflict-other",
            payload=payload,
            ingestion_time="2026-08-30T01:00:00Z",
        )


def test_multi_country_structured_evidence_survives_raw(tmp_path: Path) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, _page(
            [
                _work(
                    "W40",
                    "Multi",
                    countries=["US", "JP"],
                    institution_countries=["US", "JP"],
                )
            ],
            count=1,
        )

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "success"
    content_path = next((raw / "content").glob("*.parquet"))
    payload = load_content_payload(content_path)
    assert payload["authorship_countries"] == ["JP", "US"]
    assert payload["multi_country"] is True
    evidence_codes = {e["country_code"] for e in payload["country_evidence"]}
    assert evidence_codes == {"JP", "US"}
    assert "Hidden Person" not in json.dumps(payload)


def test_absent_country_evidence_remains_unknown_not_zero(tmp_path: Path) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float):
        # Work without structured country evidence.
        return 200, {}, _page([_work("W50", "NoCountry", countries=None)], count=1)

    raw, ck, man = _dirs(tmp_path)
    client = production_openalex_client(transport=transport, sleep_fn=lambda **_: None)
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition.canary_day(country="US", source_date=date(2022, 12, 1)),
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        run_end_date=date(2026, 8, 30),
    )
    assert result.unknown_country_works == 1
    assert result.coverage_status == "success"  # retrieval succeeded; attribute unknown ≠ zero
    payload = load_content_payload(next((raw / "content").glob("*.parquet")))
    assert payload["missing_country"] is True
    assert payload["authorship_countries"] == []
    assert payload["country_evidence"] == []
    # Provenance quality_state is unknown, not coerced to numeric zero.
    run_dir = raw / "runs" / result.run_identity
    prov = pq.read_table(next(run_dir.glob("*.parquet")))
    assert prov.column("quality_state")[0].as_py() == "unknown"


def test_raw_output_paths_excluded_from_git(tmp_path: Path) -> None:
    gitignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    assert "workspace-data/" in gitignore
    # Default data root class used by settings.
    from thought_flow.config.settings import DEFAULT_DATA_ROOT, Settings

    assert DEFAULT_DATA_ROOT.name == "workspace-data"
    settings = Settings(
        repo_root=tmp_path,
        data_root=tmp_path / "workspace-data",
        samples_dir=tmp_path / "samples",
        enable_sharepoint=False,
        enable_bigquery=False,
        enable_azure=False,
    )
    assert "workspace-data" in str(settings.raw_dir).replace("\\", "/")
    assert settings.raw_dir == settings.data_root / "raw"
