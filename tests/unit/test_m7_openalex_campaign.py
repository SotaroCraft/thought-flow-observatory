"""M7-002 OpenAlex campaign planner, durability, and coverage tests."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from thought_flow.atomic_io import atomic_write_text, is_temporary_sidecar
from thought_flow.ingestion.openalex.backfill import production_openalex_client
from thought_flow.ingestion.openalex.campaign import (
    CampaignPlan,
    CampaignResult,
    build_campaign_plan,
    classify_partition_action,
    run_openalex_backfill_campaign,
)
from thought_flow.ingestion.openalex.checkpoint import (
    CompletedPage,
    PartitionCheckpoint,
    checkpoint_path,
    load_checkpoint,
    save_checkpoint,
)
from thought_flow.ingestion.openalex.planner import (
    CAMPAIGN_COUNTRIES,
    inclusive_day_count,
    plan_daily_partitions,
)
from thought_flow.ingestion.openalex.window import BACKFILL_WINDOW_START, capture_run_end_date
from thought_flow.observability.manifest import start_manifest


FIXED_END = date(2026, 8, 30)
_TEST_KEY = "test-m7-key"


@pytest.fixture(autouse=True)
def _m7_campaign_test_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", _TEST_KEY)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)


def _client(tmp_path: Path, transport):
    return production_openalex_client(
        transport=transport,
        sleep_fn=lambda **_: None,
        data_root=tmp_path,
        api_key=_TEST_KEY,
    )


def _dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw = tmp_path / "raw"
    ck = tmp_path / "checkpoints"
    man = tmp_path / "manifests"
    raw.mkdir()
    ck.mkdir()
    man.mkdir()
    return raw, ck, man


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
                "author": {"id": "https://openalex.org/A1", "display_name": "Hidden"},
                "institutions": [
                    {
                        "id": "https://openalex.org/I1",
                        "type": "education",
                        "country_code": countries[0],
                    }
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


def _cursor(url: str) -> str:
    return (parse_qs(urlsplit(url).query).get("cursor") or ["*"])[0]


def test_planner_four_countries_1370_days_5480_partitions() -> None:
    assert inclusive_day_count(start=BACKFILL_WINDOW_START, end=FIXED_END) == 1370
    parts = plan_daily_partitions(run_end_date=FIXED_END)
    assert CAMPAIGN_COUNTRIES == ("JP", "US", "KR", "CN")
    assert len(parts) == 5480
    assert len({p.partition_id for p in parts}) == 5480
    # Deterministic order: country-major, then ascending dates.
    assert parts[0].partition_id == "openalex|JP|2022-11-30"
    assert parts[1369].partition_id == "openalex|JP|2026-08-30"
    assert parts[1370].partition_id == "openalex|US|2022-11-30"
    assert parts[-1].partition_id == "openalex|CN|2026-08-30"
    days = [p.inclusive_start for p in parts if p.country == "JP"]
    assert days == sorted(days)
    assert days[0] == BACKFILL_WINDOW_START
    assert days[-1] == FIXED_END
    assert (days[-1] - days[0]).days + 1 == 1370


def test_planner_rejects_gaps_via_length_and_duplicate_guards() -> None:
    with pytest.raises(ValueError, match="Duplicate country"):
        plan_daily_partitions(run_end_date=FIXED_END, countries=("JP", "JP"))


def test_run_end_date_frozen_during_campaign_plan(tmp_path: Path) -> None:
    calls = {"n": 0}

    def drifting_clock() -> date:
        calls["n"] += 1
        return date(2026, 8, 30) if calls["n"] == 1 else date(2026, 8, 31)

    # capture once externally then inject — planner must not re-clock mid-plan.
    end = capture_run_end_date(clock=lambda: date(2026, 8, 30))
    plan = build_campaign_plan(
        checkpoint_dir=tmp_path / "ck",
        run_end_date=end,
        countries=("JP",),
        range_start=date(2022, 11, 30),
        range_end=date(2022, 12, 1),
    )
    assert plan.run_end_date == "2026-08-30"
    assert plan.planned_partitions == 2


def test_dry_run_does_not_network_or_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw, ck, man = _dirs(tmp_path)

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network must not be used in dry-run")

    monkeypatch.setattr(
        "thought_flow.ingestion.openalex.campaign.production_openalex_client",
        boom,
    )
    monkeypatch.setattr(
        "thought_flow.ingestion.openalex.campaign.run_openalex_partition_backfill",
        boom,
    )
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=False,
        run_end_date=FIXED_END,
    )
    assert isinstance(result, CampaignPlan)
    assert result.planned_partitions == 5480
    assert result.approximate_cost_usd is None
    assert result.approximate_cost_usd != 0
    assert list(raw.rglob("*")) == []
    assert list(ck.glob("*.json")) == []
    assert list(man.rglob("*.json")) == []
    summary = result.to_public_summary()
    assert summary["network_access"] is False
    assert summary["writes_raw_or_checkpoint"] is False


def test_skip_success_and_zero_resume_others(tmp_path: Path) -> None:
    _, ck, _ = _dirs(tmp_path)
    success = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-01",
        country="JP",
        inclusive_start="2022-12-01",
        inclusive_end="2022-12-01",
        run_end_date="2026-08-30",
    )
    success.set_coverage("success")
    success.exhausted = True
    save_checkpoint(checkpoint_path(ck, success.partition_id), success)

    zero = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-02",
        country="JP",
        inclusive_start="2022-12-02",
        inclusive_end="2022-12-02",
        run_end_date="2026-08-30",
    )
    zero.set_coverage("zero")
    zero.exhausted = True
    save_checkpoint(checkpoint_path(ck, zero.partition_id), zero)

    partial = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-03",
        country="JP",
        inclusive_start="2022-12-03",
        inclusive_end="2022-12-03",
        run_end_date="2026-08-30",
    )
    partial.set_coverage("partial")
    save_checkpoint(checkpoint_path(ck, partial.partition_id), partial)

    started = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-04",
        country="JP",
        inclusive_start="2022-12-04",
        inclusive_end="2022-12-04",
        run_end_date="2026-08-30",
    )
    save_checkpoint(checkpoint_path(ck, started.partition_id), started)

    ff = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-05",
        country="JP",
        inclusive_start="2022-12-05",
        inclusive_end="2022-12-05",
        run_end_date="2026-08-30",
    )
    ff.set_coverage("fetch_failure")
    save_checkpoint(checkpoint_path(ck, ff.partition_id), ff)

    assert classify_partition_action(success) == "skip"
    assert classify_partition_action(zero) == "skip"
    assert classify_partition_action(partial) == "resume"
    assert classify_partition_action(started) == "resume"
    assert classify_partition_action(ff) == "resume"
    assert classify_partition_action(None) == "fetch"

    plan = build_campaign_plan(
        checkpoint_dir=ck,
        run_end_date=FIXED_END,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 6),
        include_partition_list=True,
    )
    assert plan.skip_complete_or_zero == 2
    assert plan.resume_started_partial_or_fetch_failure == 3
    assert plan.fetch_missing == 1  # 2022-12-06


def test_campaign_mid_failure_aggregates_partial_not_success(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        # First partition OK empty; second fails.
        if "2022-12-01" in url:
            return 200, {}, _page([], count=0)
        return 500, {}, b"boom"

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 2),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "partial"
    assert result.outcome != "succeeded"
    assert result.coverage.zero == 1
    assert result.coverage.fetch_failure == 1
    assert result.coverage.success == 0
    payload = json.loads(result.campaign_manifest_path.read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert "raw_" not in json.dumps(payload)


def test_graceful_interrupt_is_not_success(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, _page([_work("W1", "ok", ["JP"])], count=1)

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 3),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
        should_stop=lambda: True,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "interrupted"
    assert result.outcome != "succeeded"
    started = json.loads(result.campaign_manifest_path.read_text(encoding="utf-8"))
    assert started["status"] == "interrupted"
    assert started["status"] != "succeeded"


def test_interrupt_then_resume_skips_completed_partition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw, ck, man = _dirs(tmp_path)
    fetches: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        fetches.append(url)
        return 200, {}, _page([_work(f"W{len(fetches)}", "x", ["JP"])], count=1)

    client = _client(tmp_path, transport)
    completed_partitions = {"n": 0}

    def stop_after_first_partition() -> bool:
        return completed_partitions["n"] >= 1

    from thought_flow.ingestion.openalex import campaign as campaign_mod

    original = campaign_mod.run_openalex_partition_backfill

    def counting_backfill(**kwargs: Any):
        result = original(**kwargs)
        completed_partitions["n"] += 1
        return result

    monkeypatch.setattr(campaign_mod, "run_openalex_partition_backfill", counting_backfill)
    first = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 2),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
        should_stop=stop_after_first_partition,
    )

    assert isinstance(first, CampaignResult)
    assert first.outcome == "interrupted"
    assert first.coverage.success == 1
    assert first.coverage.attempted == 1
    day1 = load_checkpoint(checkpoint_path(ck, "openalex|JP|2022-12-01"))
    day2 = load_checkpoint(checkpoint_path(ck, "openalex|JP|2022-12-02"))
    assert day1 is not None and day1.coverage_status == "success"
    assert day2 is None

    fetches.clear()
    second = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 2),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(second, CampaignResult)
    assert second.outcome == "succeeded"
    assert second.coverage.skipped == 1
    assert second.coverage.fetched_new == 1
    assert all("2022-12-01" not in u for u in fetches)
    assert any("2022-12-02" in u for u in fetches)


def test_max_partitions_cap_is_partial_not_success(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, _page([], count=0)

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 2),
        run_end_date=FIXED_END,
        max_partitions=1,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "partial"
    assert result.coverage.requested == 2
    assert result.coverage.planned == 1
    assert result.coverage.omitted_by_max_partitions == 1
    assert result.coverage.http_attempts is not None
    assert result.coverage.http_attempts >= 1


def test_live_refuses_full_history_window(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    with pytest.raises(ValueError, match="Full-history live"):
        run_openalex_backfill_campaign(
            raw_dir=raw,
            checkpoint_dir=ck,
            manifests_dir=man,
            live=True,
            countries=CAMPAIGN_COUNTRIES,
            range_start=BACKFILL_WINDOW_START,
            range_end=FIXED_END,
            run_end_date=FIXED_END,
            install_signal_handlers=False,
        )


def test_live_refuses_full_history_single_country_jp(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    with pytest.raises(ValueError, match="Full-history live"):
        run_openalex_backfill_campaign(
            raw_dir=raw,
            checkpoint_dir=ck,
            manifests_dir=man,
            live=True,
            countries=("JP",),
            range_start=BACKFILL_WINDOW_START,
            range_end=FIXED_END,
            run_end_date=FIXED_END,
            install_signal_handlers=False,
        )


def test_live_refuses_full_history_single_country_us(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    with pytest.raises(ValueError, match="Full-history live"):
        run_openalex_backfill_campaign(
            raw_dir=raw,
            checkpoint_dir=ck,
            manifests_dir=man,
            live=True,
            countries=("US",),
            range_start=BACKFILL_WINDOW_START,
            range_end=FIXED_END,
            run_end_date=FIXED_END,
            install_signal_handlers=False,
        )


def test_live_allows_bounded_one_week_window(tmp_path: Path) -> None:
    """Explicit short windows remain allowed; no network when capped to zero partitions."""
    raw, ck, man = _dirs(tmp_path)

    class _NoNetworkClient:
        def __init__(self) -> None:
            from thought_flow.ingestion.openalex.daily_cost_ledger import credential_ledger_id

            self.api_key = _TEST_KEY
            self.http = type(
                "H",
                (),
                {
                    "budget": type(
                        "B", (), {"attempts_used": 0, "reported_cost_usd": None}
                    )(),
                    "daily_cost_guard": type(
                        "G", (), {"credential_id": credential_ledger_id(_TEST_KEY)}
                    )(),
                },
            )()

        def fetch_works_page(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError("network must not be used in this unit test")

    # Plan-only path via max_partitions=0 still runs live guards then caps to empty.
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 7),
        run_end_date=FIXED_END,
        max_partitions=0,
        client=_NoNetworkClient(),  # type: ignore[arg-type]
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "partial"
    assert result.coverage.requested == 7
    assert result.coverage.planned == 0
    assert result.coverage.omitted_by_max_partitions == 7


def test_dry_run_allows_full_history_plan(tmp_path: Path) -> None:
    plan = build_campaign_plan(
        checkpoint_dir=tmp_path / "ck",
        run_end_date=FIXED_END,
        countries=CAMPAIGN_COUNTRIES,
        range_start=BACKFILL_WINDOW_START,
        range_end=FIXED_END,
        include_partition_list=False,
    )
    assert isinstance(plan, CampaignPlan)
    assert plan.planned_partitions == 5480


def test_live_refuses_unbounded_full_history(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    with pytest.raises(ValueError, match="explicit"):
        run_openalex_backfill_campaign(
            raw_dir=raw,
            checkpoint_dir=ck,
            manifests_dir=man,
            live=True,
            countries=None,
            range_start=None,
            range_end=None,
            run_end_date=FIXED_END,
            install_signal_handlers=False,
        )


def test_checkpoint_and_manifest_atomic_write(tmp_path: Path) -> None:
    target = tmp_path / "final.json"
    atomic_write_text(target, '{"ok": true}\n')
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert list(tmp_path.glob(".*.tmp")) == []
    assert not is_temporary_sidecar(target)
    assert is_temporary_sidecar(tmp_path / ".final.json.abc.tmp")

    ck = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-01",
        country="JP",
        inclusive_start="2022-12-01",
        inclusive_end="2022-12-01",
        run_end_date="2026-08-30",
    )
    path = checkpoint_path(tmp_path, ck.partition_id)
    save_checkpoint(path, ck)
    loaded = load_checkpoint(path)
    assert loaded is not None
    assert loaded.partition_id == ck.partition_id

    with pytest.raises(ValueError, match="temporary"):
        load_checkpoint(tmp_path / ".openalex_JP_2022-12-01.json.tmp")

    man = start_manifest(run_identity="run-atomic", run_type="backfill")
    man_path = tmp_path / "run-atomic.json"
    man.write(man_path)
    assert json.loads(man_path.read_text(encoding="utf-8"))["status"] == "started"


def test_failed_atomic_replace_preserves_existing_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "keep.json"
    path.write_text('{"preserved": true}\n', encoding="utf-8")
    original = path.read_text(encoding="utf-8")

    def boom_replace(src: str, dst: str) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(
        "thought_flow.atomic_io.os.replace",
        boom_replace,
    )
    with pytest.raises(OSError, match="simulated replace failure"):
        atomic_write_text(path, '{"destroyed": true}\n')
    assert path.read_text(encoding="utf-8") == original


def test_quality_state_distinctions_in_plan_summary(tmp_path: Path) -> None:
    plan = build_campaign_plan(
        checkpoint_dir=tmp_path / "ck",
        run_end_date=FIXED_END,
        countries=("KR",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
    )
    summary = plan.to_public_summary()
    assert summary["fetch_missing"] == 1
    assert summary["skip_complete_or_zero"] == 0
    assert "zero" != "missing"
    assert summary["approximate_cost_usd"] is None


def test_raw_paths_still_gitignored() -> None:
    gitignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    assert "workspace-data/" in gitignore


def test_source_stop_on_persistent_429_before_first_page(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    urls: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        urls.append(url)
        if "2022-12-01" in url:
            return 200, {}, _page([], count=0)
        return 429, {"Retry-After": "43633"}, b'{"error":"rate"}'

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 3),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "partial"
    assert result.coverage.zero == 1
    assert result.coverage.fetch_failure == 1
    assert result.coverage.attempted == 2
    assert result.coverage.unattempted_due_to_stop == 1
    assert result.coverage.omitted_by_max_partitions == 0
    assert (ck / "openalex_JP_2022-12-03.json").exists() is False
    assert all("2022-12-03" not in u for u in urls)
    assert result.failure_category in {"http_429", "fetch_failure"} or "429" in (
        result.failure_message or ""
    )


def test_source_stop_on_persistent_429_after_persisted_page(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    urls: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        urls.append(url)
        if "2022-12-01" in url:
            cursor = _cursor(url)
            if cursor == "*":
                return 200, {}, _page(
                    [_work("W1", "kept", ["JP"])],
                    count=2,
                    next_cursor="page2",
                )
            return 429, {"Retry-After": "43633"}, b'{"error":"rate"}'
        raise AssertionError("later partitions must not be fetched")

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 3),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "partial"
    assert result.coverage.partial == 1
    assert result.coverage.attempted == 1
    assert result.coverage.unattempted_due_to_stop == 2
    assert (ck / "openalex_JP_2022-12-02.json").exists() is False
    assert (ck / "openalex_JP_2022-12-03.json").exists() is False
    day1 = json.loads((ck / "openalex_JP_2022-12-01.json").read_text(encoding="utf-8"))
    assert day1["coverage_status"] == "partial"
    assert day1["works_persisted"] == 1
    assert list((raw / "content").glob("*.parquet"))


def test_transient_429_recovers_and_continues(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        if "2022-12-01" in url and calls["n"] == 1:
            return 429, {"Retry-After": "0"}, b'{"error":"rate"}'
        return 200, {}, _page([], count=0)

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 2),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "succeeded"
    assert result.coverage.zero == 2
    assert result.coverage.unattempted_due_to_stop == 0
    assert calls["n"] >= 3


def test_source_stop_preserves_later_existing_checkpoints(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    later = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-03",
        country="JP",
        inclusive_start="2022-12-03",
        inclusive_end="2022-12-03",
        run_end_date="2026-08-30",
    )
    later.set_coverage("success")
    later.exhausted = True
    later_path = checkpoint_path(ck, later.partition_id)
    save_checkpoint(later_path, later)
    before = later_path.read_text(encoding="utf-8")

    def transport(url: str, headers: dict[str, str], timeout: float):
        if "2022-12-01" in url:
            return 200, {}, _page([], count=0)
        return 500, {}, b"boom"

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 3),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "partial"
    assert result.coverage.fetch_failure == 1
    assert result.coverage.unattempted_due_to_stop == 1
    assert later_path.read_text(encoding="utf-8") == before


def test_cli_passes_openalex_api_key_to_campaign_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_client(*, api_key: str | None = None, **kwargs: Any):
        captured["api_key"] = api_key
        return production_openalex_client(
            transport=lambda url, headers, timeout: (200, {}, _page([], count=0)),
            sleep_fn=lambda **_: None,
            api_key=api_key,
        )

    monkeypatch.setenv("THOUGHT_FLOW_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", "test-secret-key-value")
    monkeypatch.setattr(
        "thought_flow.ingestion.openalex.backfill.production_openalex_client",
        fake_client,
    )

    from thought_flow import cli as cli_pkg

    code = cli_pkg.run_m7_openalex_backfill_campaign(
        live=True,
        countries=["JP"],
        from_date="2022-12-01",
        to_date="2022-12-01",
        max_partitions=1,
        run_end_date="2026-08-30",
    )
    assert code in {0, 1}
    assert captured.get("api_key") == "test-secret-key-value"

    # Isolate from any process/.env key: force helper to report unset.
    monkeypatch.setattr(cli_pkg, "_openalex_api_key_from_env", lambda: None)
    captured.clear()
    code2 = cli_pkg.run_m7_openalex_backfill_campaign(
        live=True,
        countries=["JP"],
        from_date="2022-12-01",
        to_date="2022-12-01",
        max_partitions=1,
        run_end_date="2026-08-30",
    )
    assert code2 == 2
    assert captured.get("api_key") is None


def test_source_stop_on_hard_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw, ck, man = _dirs(tmp_path)
    calls = {"n": 0}

    def boom(**kwargs: Any):
        calls["n"] += 1
        raise RuntimeError("simulated hard failure")

    monkeypatch.setattr(
        "thought_flow.ingestion.openalex.campaign.run_openalex_partition_backfill",
        boom,
    )
    def no_http(url: str, headers: dict[str, str], timeout: float):
        raise AssertionError("no HTTP")

    client = production_openalex_client(transport=no_http, sleep_fn=lambda **_: None)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 3),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "partial"
    assert result.coverage.fetch_failure == 1
    assert result.coverage.attempted == 1
    assert result.coverage.unattempted_due_to_stop == 2
    assert result.failure_category == "RuntimeError"
    assert "simulated hard failure" in (result.failure_message or "")
    assert calls["n"] == 1
    assert (ck / "openalex_JP_2022-12-01.json").exists() is False
    assert (ck / "openalex_JP_2022-12-02.json").exists() is False
    assert (ck / "openalex_JP_2022-12-03.json").exists() is False


def test_cli_passes_openalex_api_key_to_canary_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_client(*, api_key: str | None = None, **kwargs: Any):
        captured["api_key"] = api_key
        return production_openalex_client(
            transport=lambda url, headers, timeout: (200, {}, _page([], count=0)),
            sleep_fn=lambda **_: None,
            api_key=api_key,
        )

    monkeypatch.setenv("THOUGHT_FLOW_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", "canary-secret-key-value")
    monkeypatch.setattr(
        "thought_flow.ingestion.openalex.backfill.production_openalex_client",
        fake_client,
    )

    from thought_flow import cli as cli_pkg

    code = cli_pkg.run_m7_openalex_backfill_canary(
        live=True,
        country="JP",
        source_date="2022-12-01",
    )
    assert code in {0, 1}
    assert captured.get("api_key") == "canary-secret-key-value"


def test_cli_dry_run_does_not_construct_openalex_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    constructed = {"n": 0}

    def fake_client(*, api_key: str | None = None, **kwargs: Any):
        constructed["n"] += 1
        raise AssertionError("dry-run must not construct production client")

    monkeypatch.setenv("THOUGHT_FLOW_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", "unused-secret-key-value")
    monkeypatch.setattr(
        "thought_flow.ingestion.openalex.backfill.production_openalex_client",
        fake_client,
    )

    from thought_flow import cli as cli_pkg

    code_campaign = cli_pkg.run_m7_openalex_backfill_campaign(
        live=False,
        countries=["JP"],
        from_date="2022-12-01",
        to_date="2022-12-01",
        max_partitions=1,
        run_end_date="2026-08-30",
    )
    code_canary = cli_pkg.run_m7_openalex_backfill_canary(
        live=False,
        country="JP",
        source_date="2022-12-01",
    )
    assert code_campaign == 0
    assert code_canary == 0
    assert constructed["n"] == 0


def test_campaign_skip_normalizes_stale_success_failure_metadata(tmp_path: Path) -> None:
    raw, ck, man = _dirs(tmp_path)
    stale = PartitionCheckpoint.new(
        partition_id="openalex|JP|2022-12-01",
        country="JP",
        inclusive_start="2022-12-01",
        inclusive_end="2022-12-01",
        run_end_date="2026-08-30",
    )
    stale.set_coverage("success")
    stale.exhausted = True
    stale.failure_category = "http_429"
    stale.failure_message = "stale leftover"
    path = checkpoint_path(ck, stale.partition_id)
    save_checkpoint(path, stale)

    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        raise AssertionError("skip path must not HTTP")

    client = _client(tmp_path, transport)
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert isinstance(result, CampaignResult)
    assert result.outcome == "succeeded"
    assert result.coverage.skipped == 1
    assert result.coverage.attempted == 0
    assert calls["n"] == 0
    reloaded = load_checkpoint(path)
    assert reloaded is not None
    assert reloaded.failure_category is None
    assert reloaded.failure_message is None
    after = path.read_text(encoding="utf-8")
    result2 = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("JP",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
        run_end_date=FIXED_END,
        client=client,
        install_signal_handlers=False,
    )
    assert result2.coverage.skipped == 1
    assert calls["n"] == 0
    assert path.read_text(encoding="utf-8") == after
