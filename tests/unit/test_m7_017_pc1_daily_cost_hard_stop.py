"""TFO-M7-017-PC1: OpenAlex UTC-day $1 cost hard stop."""

from __future__ import annotations

import json
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
    DailyCostCeilingExceeded,
    DailyCostGuard,
    DailyCostLedgerError,
    credential_ledger_id,
)
from thought_flow.ingestion.openalex.window import RetrievalPartition
from thought_flow.smoke.http_client import RequestBudget, SmokeHttpClient


FIXED = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)


def _guard(tmp_path: Path, *, spent: float = 0.0, clock_day: datetime = FIXED) -> DailyCostGuard:
    guard = DailyCostGuard(
        ledger_root=tmp_path / "ledger",
        credential_id="test_cred",
        clock=lambda: clock_day,
    )
    if spent > 0:
        # Seed ledger without going through authorize.
        path = guard.ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "m7.openalex.daily_cost_ledger.v1",
                    "utc_date": clock_day.date().isoformat(),
                    "credential_id": "test_cred",
                    "accumulated_usd": spent,
                    "attempt_count": int(spent / OPENALEX_BILLABLE_ATTEMPT_COST_USD),
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
    guard.authorize_next_attempt()
    guard.record_billable_attempt(source_reported_cost_usd=0.0001)
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
    g1.record_billable_attempt(source_reported_cost_usd=0.4)
    # New process / new guard instance, same ledger root + credential + UTC day.
    g2 = DailyCostGuard(
        ledger_root=tmp_path / "ledger",
        credential_id="test_cred",
        clock=lambda: FIXED,
    )
    assert g2.snapshot().accumulated_usd == pytest.approx(0.4)


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
        credential_id="test_cred",
        clock=lambda: day2,
    )
    g2.authorize_next_attempt()
    assert g2.snapshot().accumulated_usd == 0.0


def test_unreadable_ledger_fails_closed(tmp_path: Path) -> None:
    guard = _guard(tmp_path, spent=0.0)
    path = guard.ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(DailyCostLedgerError):
        guard.authorize_next_attempt()


def test_dry_run_no_network_no_ledger_write(tmp_path: Path) -> None:
    ck = tmp_path / "manifests" / "openalex_backfill" / "checkpoints"
    ck.mkdir(parents=True)
    # data_root = tmp_path when checkpoint_dir parents[2] == tmp_path
    plan = build_campaign_plan(
        checkpoint_dir=ck,
        run_end_date=date(2026, 8, 30),
        countries=["US"],
        range_start=date(2022, 12, 1),
        range_end=date(2022, 12, 1),
    )
    summary = plan.to_public_summary()
    assert summary["network_access"] is False
    assert summary["writes_raw_or_checkpoint"] is False
    assert summary["daily_cost_ceiling_usd"] == OPENALEX_DAILY_COST_CEILING_USD
    assert "live_execution_permitted" in summary["daily_cost_ledger"]
    ledger_root = tmp_path / "manifests" / "openalex_backfill" / "daily_cost_ledger"
    # Dry-run snapshot may create nothing when empty; ensure no writes required.
    # Reading empty day does not create files.
    assert not ledger_root.exists() or not any(ledger_root.rglob("*.json"))


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
        enable_daily_cost_guard=True,
        api_key="test-key",
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
