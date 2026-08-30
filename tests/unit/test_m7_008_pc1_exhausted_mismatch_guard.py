"""TFO-M7-008-PC1: exhausted count-mismatch fail-closed guard."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from thought_flow.ingestion.openalex.backfill import (
    last_nonnull_source_reported_count,
    run_openalex_partition_backfill,
)
from thought_flow.ingestion.openalex.checkpoint import (
    CompletedPage,
    PartitionCheckpoint,
    checkpoint_path,
    load_checkpoint,
    save_checkpoint,
)
from thought_flow.ingestion.openalex.window import RetrievalPartition
from thought_flow.smoke.http_client import SmokeHttpClient


FIXED_END = date(2026, 8, 30)


def _partition() -> RetrievalPartition:
    return RetrievalPartition(
        country="JP",
        inclusive_start=date(2024, 4, 1),
        inclusive_end=date(2024, 4, 1),
    )


def _exhausted_mismatch_checkpoint() -> PartitionCheckpoint:
    ck = PartitionCheckpoint.new(
        partition_id="openalex|JP|2024-04-01",
        country="JP",
        inclusive_start="2024-04-01",
        inclusive_end="2024-04-01",
        run_end_date="2026-08-30",
    )
    # 9 full pages + terminal page with 1 work; source claims 1802.
    cursor = "*"
    for i in range(9):
        nxt = f"c{i+1}"
        ck.record_page(
            CompletedPage(
                page_index=i,
                request_cursor=cursor,
                next_cursor=nxt,
                source_count=1802,
                result_count=200,
                work_ids=[f"https://openalex.org/W{i}-{j}" for j in range(200)],
                raw_content_identities=[f"raw_{i}_{j}" for j in range(200)],
                page_quality_state="success",
            )
        )
        cursor = nxt
    ck.record_page(
        CompletedPage(
            page_index=9,
            request_cursor=cursor,
            next_cursor=None,
            source_count=1802,
            result_count=1,
            work_ids=["https://openalex.org/W9-0"],
            raw_content_identities=["raw_9_0"],
            page_quality_state="success",
        )
    )
    ck.set_coverage("partial")
    assert ck.exhausted is True
    assert ck.works_persisted == 1801
    return ck


def test_last_nonnull_source_count_prefers_final_page() -> None:
    pages = [
        CompletedPage(
            page_index=0,
            request_cursor="*",
            next_cursor="a",
            source_count=10,
            result_count=1,
            work_ids=["W1"],
            raw_content_identities=["r1"],
            page_quality_state="success",
        ),
        CompletedPage(
            page_index=1,
            request_cursor="a",
            next_cursor=None,
            source_count=12,
            result_count=1,
            work_ids=["W2"],
            raw_content_identities=["r2"],
            page_quality_state="success",
        ),
    ]
    assert last_nonnull_source_reported_count(pages) == 12
    assert last_nonnull_source_reported_count([]) is None


def test_exhausted_mismatch_http0_stays_partial_and_sha_stable(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    raw.mkdir()
    ck_dir.mkdir()
    man.mkdir()
    part = _partition()
    existing = _exhausted_mismatch_checkpoint()
    path = checkpoint_path(ck_dir, existing.partition_id)
    save_checkpoint(path, existing)
    before = path.read_bytes()
    before_sha = hashlib.sha256(before).hexdigest()

    calls = {"n": 0}

    def transport(url: str, headers: dict[str, str], timeout: float):
        calls["n"] += 1
        raise AssertionError("HTTP must not be used for exhausted reclassify")

    http = SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    from thought_flow.ingestion.openalex.backfill import production_openalex_client

    client = production_openalex_client(http=http)
    first = run_openalex_partition_backfill(
        partition=part,
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=client,
        run_end_date=FIXED_END,
    )
    assert calls["n"] == 0
    assert first.coverage_status == "partial"
    assert first.exhausted is True
    assert first.source_reported_count == 1802
    assert first.failure_category == "source_count_mismatch"
    assert first.coverage_status != "success"
    after = load_checkpoint(path)
    assert after is not None
    assert after.coverage_status == "partial"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["failure_category"] == "source_count_mismatch"
    assert "api_key" not in json.dumps(manifest).lower()

    second = run_openalex_partition_backfill(
        partition=part,
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=client,
        run_end_date=FIXED_END,
    )
    assert calls["n"] == 0
    assert second.coverage_status == "partial"
    assert second.source_reported_count == 1802
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha


def test_equal_count_exhausted_success_unchanged(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    for d in (raw, ck_dir, man):
        d.mkdir()
    ck = PartitionCheckpoint.new(
        partition_id="openalex|JP|2024-04-02",
        country="JP",
        inclusive_start="2024-04-02",
        inclusive_end="2024-04-02",
        run_end_date="2026-08-30",
    )
    ck.record_page(
        CompletedPage(
            page_index=0,
            request_cursor="*",
            next_cursor=None,
            source_count=1,
            result_count=1,
            work_ids=["https://openalex.org/W1"],
            raw_content_identities=["raw_1"],
            page_quality_state="success",
        )
    )
    ck.set_coverage("success")
    path = checkpoint_path(ck_dir, ck.partition_id)
    save_checkpoint(path, ck)
    before_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    def transport(url: str, headers: dict[str, str], timeout: float):
        raise AssertionError("no HTTP")

    from thought_flow.ingestion.openalex.backfill import production_openalex_client

    client = production_openalex_client(
        http=SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    )
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition(
            country="JP", inclusive_start=date(2024, 4, 2), inclusive_end=date(2024, 4, 2)
        ),
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=client,
        run_end_date=FIXED_END,
    )
    assert result.coverage_status == "success"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha


def _raw_inventory(raw_dir: Path) -> str:
    lines: list[str] = []
    if raw_dir.exists():
        for p in sorted(raw_dir.rglob("*")):
            if p.is_file():
                lines.append(f"{p.relative_to(raw_dir).as_posix()}\t{p.stat().st_size}")
    return "\n".join(lines)


def _no_http_client() -> object:
    from thought_flow.ingestion.openalex.backfill import production_openalex_client

    def transport(url: str, headers: dict[str, str], timeout: float):
        raise AssertionError("HTTP must not be used")

    return production_openalex_client(
        http=SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
    )


def _exhausted_partial_day(
    *,
    day: str,
    source_count: int | None,
    works: int,
    coverage: str = "partial",
) -> PartitionCheckpoint:
    ck = PartitionCheckpoint.new(
        partition_id=f"openalex|JP|{day}",
        country="JP",
        inclusive_start=day,
        inclusive_end=day,
        run_end_date="2026-08-30",
    )
    work_ids = [f"https://openalex.org/W{i}" for i in range(works)]
    raw_ids = [f"raw_{i}" for i in range(works)]
    ck.record_page(
        CompletedPage(
            page_index=0,
            request_cursor="*",
            next_cursor=None,
            source_count=source_count,
            result_count=works,
            work_ids=work_ids,
            raw_content_identities=raw_ids,
            page_quality_state="success",
        )
    )
    ck.set_coverage(coverage)  # type: ignore[arg-type]
    assert ck.exhausted is True
    return ck


def test_exhausted_partial_equal_count_stays_partial_sha_stable(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    for d in (raw, ck_dir, man):
        d.mkdir()
    (raw / "marker.bin").write_bytes(b"keep")
    before_inv = _raw_inventory(raw)
    ck = _exhausted_partial_day(day="2024-04-03", source_count=2, works=2)
    path = checkpoint_path(ck_dir, ck.partition_id)
    save_checkpoint(path, ck)
    before_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition(
            country="JP", inclusive_start=date(2024, 4, 3), inclusive_end=date(2024, 4, 3)
        ),
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=_no_http_client(),
        run_end_date=FIXED_END,
    )
    assert result.coverage_status == "partial"
    assert result.coverage_status != "success"
    assert result.source_reported_count == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha
    assert _raw_inventory(raw) == before_inv


def test_exhausted_partial_persisted_gt_reported_stays_partial(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    for d in (raw, ck_dir, man):
        d.mkdir()
    before_inv = _raw_inventory(raw)
    ck = _exhausted_partial_day(day="2024-04-04", source_count=1, works=2)
    path = checkpoint_path(ck_dir, ck.partition_id)
    save_checkpoint(path, ck)
    before_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition(
            country="JP", inclusive_start=date(2024, 4, 4), inclusive_end=date(2024, 4, 4)
        ),
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=_no_http_client(),
        run_end_date=FIXED_END,
    )
    assert result.coverage_status == "partial"
    assert result.source_reported_count == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha
    assert _raw_inventory(raw) == before_inv


def test_exhausted_partial_missing_source_count_stays_partial(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    for d in (raw, ck_dir, man):
        d.mkdir()
    before_inv = _raw_inventory(raw)
    ck = _exhausted_partial_day(day="2024-04-05", source_count=None, works=3)
    path = checkpoint_path(ck_dir, ck.partition_id)
    save_checkpoint(path, ck)
    before_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition(
            country="JP", inclusive_start=date(2024, 4, 5), inclusive_end=date(2024, 4, 5)
        ),
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=_no_http_client(),
        run_end_date=FIXED_END,
    )
    assert result.coverage_status == "partial"
    assert result.source_reported_count is None
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha
    assert _raw_inventory(raw) == before_inv


def test_exhausted_started_does_not_promote_to_success(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    for d in (raw, ck_dir, man):
        d.mkdir()
    ck = _exhausted_partial_day(
        day="2024-04-06", source_count=1, works=1, coverage="started"
    )
    path = checkpoint_path(ck_dir, ck.partition_id)
    save_checkpoint(path, ck)
    before_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    result = run_openalex_partition_backfill(
        partition=RetrievalPartition(
            country="JP", inclusive_start=date(2024, 4, 6), inclusive_end=date(2024, 4, 6)
        ),
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=_no_http_client(),
        run_end_date=FIXED_END,
    )
    assert result.coverage_status == "started"
    assert result.coverage_status not in {"success", "zero"}
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha


def test_fresh_equal_count_pagination_still_success(tmp_path: Path) -> None:
    from thought_flow.ingestion.openalex.backfill import production_openalex_client

    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    for d in (raw, ck_dir, man):
        d.mkdir()

    payload = {
        "meta": {"count": 1, "next_cursor": None},
        "results": [
            {
                "id": "https://openalex.org/Wfresh1",
                "display_name": "Fresh",
                "publication_date": "2024-04-07",
                "authorships": [
                    {"institutions": [{"country_code": "JP"}], "author": {"id": "A1"}}
                ],
            }
        ],
    }

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, json.dumps(payload).encode("utf-8")

    result = run_openalex_partition_backfill(
        partition=RetrievalPartition(
            country="JP", inclusive_start=date(2024, 4, 7), inclusive_end=date(2024, 4, 7)
        ),
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=production_openalex_client(
            http=SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
        ),
        run_end_date=FIXED_END,
    )
    assert result.coverage_status == "success"
    assert result.source_reported_count == 1
    assert result.works_persisted == 1


def test_fresh_zero_pagination_still_zero(tmp_path: Path) -> None:
    from thought_flow.ingestion.openalex.backfill import production_openalex_client

    raw = tmp_path / "raw"
    ck_dir = tmp_path / "ck"
    man = tmp_path / "man"
    for d in (raw, ck_dir, man):
        d.mkdir()

    payload = {"meta": {"count": 0, "next_cursor": None}, "results": []}

    def transport(url: str, headers: dict[str, str], timeout: float):
        return 200, {}, json.dumps(payload).encode("utf-8")

    result = run_openalex_partition_backfill(
        partition=RetrievalPartition(
            country="JP", inclusive_start=date(2024, 4, 8), inclusive_end=date(2024, 4, 8)
        ),
        raw_dir=raw,
        checkpoint_dir=ck_dir,
        manifests_dir=man,
        client=production_openalex_client(
            http=SmokeHttpClient(transport=transport, sleep_fn=lambda **_: None)
        ),
        run_end_date=FIXED_END,
    )
    assert result.coverage_status == "zero"
