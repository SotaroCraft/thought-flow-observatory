"""TFO-M7-017-PC1 / R2: OpenAlex UTC-day $1 cost hard stop."""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from thought_flow.ingestion.openalex.backfill import (
    FAILURE_DAILY_COST_CEILING,
    production_http_client,
    production_openalex_client,
)
from thought_flow.ingestion.openalex.campaign import build_campaign_plan
from thought_flow.ingestion.openalex.daily_cost_ledger import (
    OPENALEX_BILLABLE_ATTEMPT_COST_USD,
    OPENALEX_DAILY_COST_CEILING_USD,
    CostModelMismatch,
    DailyCostCeilingExceeded,
    DailyCostGuard,
    DailyCostLedgerError,
    credential_ledger_id,
    resolve_openalex_api_key,
)
from thought_flow.ingestion.openalex.window import RetrievalPartition


FIXED = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
_TEST_KEY = "test-key"


@pytest.fixture(autouse=True)
def _m7_cost_test_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", _TEST_KEY)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)


def _guard(tmp_path: Path, *, spent: float = 0.0, clock_day: datetime = FIXED) -> DailyCostGuard:
    guard = DailyCostGuard(
        ledger_root=tmp_path / "ledger",
        credential_id=credential_ledger_id(_TEST_KEY),
        clock=lambda: clock_day,
    )
    if spent > 0:
        path = guard.ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "m7.openalex.daily_cost_ledger.v1",
                    "utc_date": clock_day.date().isoformat(),
                    "credential_id": credential_ledger_id(_TEST_KEY),
                    "accumulated_usd": spent,
                    "attempt_count": int(round(spent / OPENALEX_BILLABLE_ATTEMPT_COST_USD)),
                    "cost_model_mismatch": False,
                    "entries": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return guard


def test_request_allowed_below_ceiling(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.5)
    rid = guard.authorize_next_attempt()
    guard.record_billable_attempt(source_reported_cost_usd=0.0001, reservation_id=rid)
    assert guard.snapshot().accumulated_usd == pytest.approx(0.5001)


def test_request_allowed_when_projected_equals_ceiling(tmp_path: Path) -> None:
    spent = OPENALEX_DAILY_COST_CEILING_USD - OPENALEX_BILLABLE_ATTEMPT_COST_USD
    guard = _guard(tmp_path, spent=spent)
    guard.authorize_next_attempt()  # projected == 1.00 exactly


def test_request_blocked_before_http_when_projected_exceeds(tmp_path: Path) -> None:
    spent = OPENALEX_DAILY_COST_CEILING_USD - (OPENALEX_BILLABLE_ATTEMPT_COST_USD / 2)
    guard = _guard(tmp_path, spent=spent)
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        return 200, {"X-API-Cost": "0.0001"}, b"{}"

    client = production_http_client(transport=transport, sleep_fn=lambda **_: None, daily_cost_guard=guard)
    with pytest.raises(DailyCostCeilingExceeded):
        client.get("https://example.test/")
    assert calls["n"] == 0


def test_retry_attempts_counted(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.0)
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        if calls["n"] == 1:
            return 500, {"X-API-Cost": "0.0001"}, b"err"
        return 200, {"X-API-Cost": "0.0001"}, b"{}"

    client = production_http_client(transport=transport, sleep_fn=lambda **_: None, daily_cost_guard=guard)
    resp = client.get("https://example.test/")
    assert resp.status_code == 200
    assert calls["n"] == 2
    assert guard.snapshot().attempt_count == 2
    assert guard.snapshot().accumulated_usd == pytest.approx(0.0002)


def test_aggregation_across_sequential_clients(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.0)

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {"X-API-Cost": "0.0001"}, b"{}"

    c1 = production_http_client(transport=transport, sleep_fn=lambda **_: None, daily_cost_guard=guard)
    c1.get("https://example.test/a")
    c2 = production_http_client(transport=transport, sleep_fn=lambda **_: None, daily_cost_guard=guard)
    c2.get("https://example.test/b")
    assert guard.snapshot().attempt_count == 2


def test_process_restart_does_not_reset_same_day_usage(tmp_path: Path) -> None:
    g1 = _guard(tmp_path, spent=0.0)
    g1.authorize_next_attempt()
    g2 = DailyCostGuard(
        ledger_root=tmp_path / "ledger",
        credential_id=credential_ledger_id(_TEST_KEY),
        clock=lambda: FIXED,
    )
    assert g2.snapshot().accumulated_usd == pytest.approx(OPENALEX_BILLABLE_ATTEMPT_COST_USD)


def test_utc_day_rollover_permits_resume(tmp_path: Path) -> None:
    day1 = datetime(2026, 8, 30, 23, 0, 0, tzinfo=UTC)
    day2 = datetime(2026, 8, 31, 0, 30, 0, tzinfo=UTC)
    g1 = _guard(
        tmp_path,
        spent=OPENALEX_DAILY_COST_CEILING_USD - (OPENALEX_BILLABLE_ATTEMPT_COST_USD / 2),
        clock_day=day1,
    )
    with pytest.raises(DailyCostCeilingExceeded):
        g1.authorize_next_attempt()
    g2 = DailyCostGuard(
        ledger_root=tmp_path / "ledger",
        credential_id=credential_ledger_id(_TEST_KEY),
        clock=lambda: day2,
    )
    assert g2.snapshot().accumulated_usd == 0.0
    g2.authorize_next_attempt()
    assert g2.snapshot().accumulated_usd == pytest.approx(OPENALEX_BILLABLE_ATTEMPT_COST_USD)


def test_unreadable_ledger_fails_closed(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.0)
    path = guard.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(DailyCostLedgerError):
        guard.authorize_next_attempt()


def test_dry_run_no_network_no_ledger_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", _TEST_KEY)
    ck = tmp_path / "manifests" / "openalex_backfill" / "checkpoints"
    ck.mkdir(parents=True)

    def _tree() -> set[str]:
        return {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")}

    before = _tree()
    plan = build_campaign_plan(
        checkpoint_dir=ck,
        run_end_date=date(2026, 8, 30),
        countries=["US"],
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
    )
    after = _tree()
    summary = plan.to_public_summary()
    assert summary["network_access"] is False
    assert summary["writes_raw_or_checkpoint"] is False
    assert summary["daily_cost_ceiling_usd"] == OPENALEX_DAILY_COST_CEILING_USD
    assert "live_execution_permitted" in summary["daily_cost_ledger"]
    assert after == before


def test_dry_run_missing_key_reports_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("THOUGHT_FLOW_OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    ck = tmp_path / "manifests" / "openalex_backfill" / "checkpoints"
    ck.mkdir(parents=True)
    before = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")}
    plan = build_campaign_plan(
        checkpoint_dir=ck,
        run_end_date=date(2026, 8, 30),
        countries=["US"],
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
    )
    after = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")}
    assert after == before
    assert plan.daily_cost_ledger is not None
    assert plan.daily_cost_ledger["live_execution_permitted"] is False
    assert plan.daily_cost_ledger["reason"] == "api_key_missing"


def test_mid_date_cost_stop_keeps_partial_cursor(tmp_path: Path) -> None:
    from thought_flow.ingestion.openalex.backfill import run_openalex_partition_backfill
    from thought_flow.ingestion.openalex.checkpoint import checkpoint_path, load_checkpoint

    guard = _guard(tmp_path, spent=OPENALEX_DAILY_COST_CEILING_USD - OPENALEX_BILLABLE_ATTEMPT_COST_USD)
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        body = {
            "meta": {"count": 400, "next_cursor": "CURSOR2"},
            "results": [{"id": "https://openalex.org/W1", "authorships": []}],
        }
        return 200, {"X-API-Cost": "0.0001"}, json.dumps(body).encode()

    client = production_openalex_client(
        transport=transport,
        sleep_fn=lambda **_: None,
        daily_cost_guard=guard,
        data_root=tmp_path,
        api_key=_TEST_KEY,
    )
    raw = tmp_path / "raw"
    ck = tmp_path / "ck"
    man = tmp_path / "man"
    raw.mkdir()
    ck.mkdir()
    man.mkdir()
    part = RetrievalPartition(
        country="US", inclusive_start=date(2022, 12, 1), inclusive_end=date(2022, 12, 1)
    )
    result = run_openalex_partition_backfill(
        partition=part,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        code_revision="test",
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "partial"
    assert result.failure_category == FAILURE_DAILY_COST_CEILING
    assert result.exhausted is False
    assert result.pages_completed >= 1
    saved = load_checkpoint(checkpoint_path(ck, part.partition_id))
    assert saved is not None
    assert saved.exhausted is False
    assert saved.failure_category == FAILURE_DAILY_COST_CEILING
    assert saved.next_cursor is not None
    assert calls["n"] == 1


def test_credential_id_stable_and_non_secret() -> None:
    a = credential_ledger_id("secret-key")
    b = credential_ledger_id("secret-key")
    assert a == b
    assert "secret-key" not in a
    assert credential_ledger_id(None) == "keyless"


def test_production_inprocess_budget_does_not_share_daily_ceiling() -> None:
    client = production_http_client(sleep_fn=lambda **_: None)
    assert client.budget.max_cost_usd > OPENALEX_DAILY_COST_CEILING_USD


def test_authorize_reserves_before_http_survives_missing_record(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.0)
    guard.authorize_next_attempt()
    assert guard.snapshot().accumulated_usd == pytest.approx(OPENALEX_BILLABLE_ATTEMPT_COST_USD)
    restarted = DailyCostGuard(
        ledger_root=tmp_path / "ledger",
        credential_id=credential_ledger_id(_TEST_KEY),
        clock=lambda: FIXED,
    )
    assert restarted.snapshot().accumulated_usd == pytest.approx(OPENALEX_BILLABLE_ATTEMPT_COST_USD)
    assert restarted.snapshot().attempt_count == 1


def test_between_date_cost_stop_leaves_next_day_unattempted(tmp_path: Path) -> None:
    from thought_flow.ingestion.openalex.campaign import (
        CampaignResult,
        run_openalex_backfill_campaign,
    )
    from thought_flow.ingestion.openalex.checkpoint import checkpoint_path

    guard = _guard(
        tmp_path,
        spent=OPENALEX_DAILY_COST_CEILING_USD - OPENALEX_BILLABLE_ATTEMPT_COST_USD,
    )
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        body = {
            "meta": {"count": 1, "next_cursor": None},
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "authorships": [{"institutions": [{"country_code": "US"}]}],
                }
            ],
        }
        return 200, {"X-API-Cost": "0.0001"}, json.dumps(body).encode()

    client = production_openalex_client(
        transport=transport,
        sleep_fn=lambda **_: None,
        daily_cost_guard=guard,
        data_root=tmp_path,
        api_key=_TEST_KEY,
    )
    raw = tmp_path / "raw"
    ck = tmp_path / "ck"
    man = tmp_path / "man"
    raw.mkdir()
    ck.mkdir()
    man.mkdir()
    result = run_openalex_backfill_campaign(
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        live=True,
        countries=("US",),
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 2),
        run_end_date=date(2026, 8, 30),
        client=client,
        install_signal_handlers=False,
        clock=lambda: FIXED,
    )
    assert isinstance(result, CampaignResult)
    assert result.coverage.attempted == 1
    assert result.coverage.unattempted_due_to_stop == 1
    assert result.failure_category == FAILURE_DAILY_COST_CEILING
    day2 = RetrievalPartition(
        country="US", inclusive_start=date(2022, 12, 2), inclusive_end=date(2022, 12, 2)
    )
    assert not checkpoint_path(ck, day2.partition_id).exists()
    assert calls["n"] == 1


def test_zero_page_cost_stop_keeps_started_not_fetch_failure(tmp_path: Path) -> None:
    from thought_flow.ingestion.openalex.backfill import run_openalex_partition_backfill
    from thought_flow.ingestion.openalex.checkpoint import checkpoint_path, load_checkpoint

    guard = _guard(tmp_path, spent=OPENALEX_DAILY_COST_CEILING_USD)
    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        return 200, {"X-API-Cost": "0.0001"}, b"{}"

    client = production_openalex_client(
        transport=transport,
        sleep_fn=lambda **_: None,
        daily_cost_guard=guard,
        data_root=tmp_path,
        api_key=_TEST_KEY,
    )
    raw = tmp_path / "raw"
    ck = tmp_path / "ck"
    man = tmp_path / "man"
    raw.mkdir()
    ck.mkdir()
    man.mkdir()
    part = RetrievalPartition(
        country="US", inclusive_start=date(2022, 12, 1), inclusive_end=date(2022, 12, 1)
    )
    result = run_openalex_partition_backfill(
        partition=part,
        raw_dir=raw,
        checkpoint_dir=ck,
        manifests_dir=man,
        client=client,
        code_revision="test",
        run_end_date=date(2026, 8, 30),
    )
    assert result.coverage_status == "started"
    assert result.failure_category == FAILURE_DAILY_COST_CEILING
    assert calls["n"] == 0
    saved = load_checkpoint(checkpoint_path(ck, part.partition_id))
    assert saved is not None
    assert saved.coverage_status == "started"


def test_concurrent_reservations_both_retained(tmp_path: Path) -> None:
    root = tmp_path / "ledger"
    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker() -> None:
        g = DailyCostGuard(ledger_root=root, credential_id=credential_ledger_id(_TEST_KEY), clock=lambda: FIXED)
        barrier.wait()
        try:
            g.authorize_next_attempt()
            results.append("ok")
        except DailyCostCeilingExceeded:
            results.append("blocked")

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    snap = DailyCostGuard(ledger_root=root, credential_id=credential_ledger_id(_TEST_KEY), clock=lambda: FIXED).snapshot()
    assert results.count("ok") == 2
    assert snap.attempt_count == 2
    assert snap.accumulated_usd == pytest.approx(0.0002)


def test_concurrent_final_unit_only_one_wins(tmp_path: Path) -> None:
    guard = _guard(
        tmp_path,
        spent=OPENALEX_DAILY_COST_CEILING_USD - OPENALEX_BILLABLE_ATTEMPT_COST_USD,
    )
    root = tmp_path / "ledger"
    cred = guard.credential_id
    barrier = threading.Barrier(2)
    results: list[str] = []

    def worker() -> None:
        g = DailyCostGuard(ledger_root=root, credential_id=cred, clock=lambda: FIXED)
        barrier.wait()
        try:
            g.authorize_next_attempt()
            results.append("ok")
        except DailyCostCeilingExceeded:
            results.append("blocked")

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    snap = DailyCostGuard(ledger_root=root, credential_id=cred, clock=lambda: FIXED).snapshot()
    assert results.count("ok") == 1
    assert results.count("blocked") == 1
    assert snap.attempt_count == int(OPENALEX_DAILY_COST_CEILING_USD / OPENALEX_BILLABLE_ATTEMPT_COST_USD)
    assert snap.accumulated_usd == pytest.approx(OPENALEX_DAILY_COST_CEILING_USD)


def test_client_key_matches_ledger_credential(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", "shared-secret-key")
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    key = resolve_openalex_api_key()
    client = production_openalex_client(data_root=tmp_path, api_key=key)
    expected = credential_ledger_id(key)
    assert client.api_key == key
    assert client.http.daily_cost_guard is not None
    assert client.http.daily_cost_guard.credential_id == expected
    ck = tmp_path / "manifests" / "openalex_backfill" / "checkpoints"
    ck.mkdir(parents=True)
    plan = build_campaign_plan(
        checkpoint_dir=ck,
        run_end_date=date(2026, 8, 30),
        countries=["US"],
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
    )
    assert plan.daily_cost_ledger is not None
    assert plan.daily_cost_ledger["credential_id"] == expected


def test_custom_transport_keeps_guard(tmp_path: Path) -> None:
    client = production_openalex_client(
        transport=lambda u, h, t: (200, {}, b"{}"),
        sleep_fn=lambda **_: None,
        data_root=tmp_path,
        api_key="k",
    )
    assert client.http.daily_cost_guard is not None


def test_guardless_injected_live_client_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from thought_flow.ingestion.openalex.campaign import run_openalex_backfill_campaign
    from thought_flow.smoke.http_client import SmokeHttpClient
    from thought_flow.smoke.openalex.client import OpenAlexClient

    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", "k")
    client = OpenAlexClient(http=SmokeHttpClient(), api_key="k")
    assert client.http.daily_cost_guard is None
    with pytest.raises(ValueError, match="DailyCostGuard"):
        run_openalex_backfill_campaign(
            raw_dir=tmp_path / "raw",
            checkpoint_dir=tmp_path / "ck",
            manifests_dir=tmp_path / "man",
            live=True,
            countries=("US",),
            range_start=date(2022, 12, 1),
            range_end=date(2022, 12, 1),
            run_end_date=date(2026, 8, 30),
            client=client,
            install_signal_handlers=False,
        )


def test_injected_key_mismatch_blocks_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from thought_flow.ingestion.openalex.campaign import run_openalex_backfill_campaign

    monkeypatch.setenv("THOUGHT_FLOW_OPENALEX_API_KEY", "env-key-value")
    client = production_openalex_client(
        transport=lambda u, h, t: (_ for _ in ()).throw(AssertionError("no HTTP")),
        sleep_fn=lambda **_: None,
        data_root=tmp_path,
        api_key="other-key-value",
    )
    man = tmp_path / "man"
    man.mkdir()
    with pytest.raises(ValueError, match="must equal"):
        run_openalex_backfill_campaign(
            raw_dir=tmp_path / "raw",
            checkpoint_dir=tmp_path / "ck",
            manifests_dir=man,
            live=True,
            countries=("US",),
            range_start=date(2022, 12, 1),
            range_end=date(2022, 12, 1),
            run_end_date=date(2026, 8, 30),
            client=client,
            install_signal_handlers=False,
        )
    assert not list(man.rglob("*.json"))


def test_no_synthetic_transport_credential_in_production_code() -> None:
    from thought_flow.ingestion.openalex import backfill as bf

    assert not hasattr(bf, "_TEST_TRANSPORT_CREDENTIAL")
    assert not hasattr(bf, "_TEST_TRANSPORT_API_KEY")


def test_cost_model_mismatch_survives_utc_rollover(tmp_path: Path) -> None:
    day1 = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    day2 = datetime(2026, 8, 31, 1, 0, 0, tzinfo=UTC)
    g1 = _guard(tmp_path, spent=0.0, clock_day=day1)
    rid = g1.authorize_next_attempt()
    with pytest.raises(CostModelMismatch):
        g1.record_billable_attempt(source_reported_cost_usd=0.001, reservation_id=rid)
    assert g1.mismatch_block_path().exists()
    g2 = DailyCostGuard(
        ledger_root=tmp_path / "ledger",
        credential_id=credential_ledger_id(_TEST_KEY),
        clock=lambda: day2,
    )
    assert g2.snapshot_readonly().live_execution_permitted is False
    with pytest.raises(CostModelMismatch):
        g2.authorize_next_attempt()


def test_unit_network_deny_blocks_urllib() -> None:
    import urllib.request

    with pytest.raises(RuntimeError, match="UNIT_TEST_NETWORK_DENIED"):
        urllib.request.urlopen("https://example.test/")


def test_unit_network_deny_blocks_socket() -> None:
    import socket

    with pytest.raises(RuntimeError, match="UNIT_TEST_NETWORK_DENIED"):
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)


def test_missing_key_blocks_live_before_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from thought_flow.ingestion.openalex.campaign import run_openalex_backfill_campaign

    monkeypatch.delenv("THOUGHT_FLOW_OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    raw = tmp_path / "raw"
    ck = tmp_path / "ck"
    man = tmp_path / "man"
    raw.mkdir()
    ck.mkdir()
    man.mkdir()
    with pytest.raises(ValueError, match="API_KEY"):
        run_openalex_backfill_campaign(
            raw_dir=raw,
            checkpoint_dir=ck,
            manifests_dir=man,
            live=True,
            countries=("US",),
            range_start=date(2022, 12, 1),
            range_end=date(2022, 12, 1),
            run_end_date=date(2026, 8, 30),
            client=None,
            install_signal_handlers=False,
        )
    assert not list(man.rglob("*.json"))


def test_larger_source_cost_mismatch_no_overflow(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.0)
    rid = guard.authorize_next_attempt()
    with pytest.raises(CostModelMismatch):
        guard.record_billable_attempt(source_reported_cost_usd=0.001, reservation_id=rid)
    snap = guard.snapshot()
    assert snap.accumulated_usd == pytest.approx(OPENALEX_BILLABLE_ATTEMPT_COST_USD)
    assert snap.accumulated_usd <= OPENALEX_DAILY_COST_CEILING_USD
    assert snap.cost_model_mismatch is True
    with pytest.raises(CostModelMismatch):
        guard.authorize_next_attempt()


def test_smaller_source_cost_does_not_reduce_reservation(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.0)
    rid = guard.authorize_next_attempt()
    guard.record_billable_attempt(source_reported_cost_usd=0.0, reservation_id=rid)
    assert guard.snapshot().accumulated_usd == pytest.approx(OPENALEX_BILLABLE_ATTEMPT_COST_USD)


def test_no_public_enable_daily_cost_guard_disable() -> None:
    import inspect

    from thought_flow.ingestion.openalex import backfill as bf

    sig = inspect.signature(bf.production_openalex_client)
    assert "enable_daily_cost_guard" not in sig.parameters
