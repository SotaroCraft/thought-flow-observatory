"""Identity and Raw immutability tests for M1."""

from __future__ import annotations

from pathlib import Path

from thought_flow.ingestion.raw_store import persist_raw_record
from thought_flow.observability.identity import (
    canonical_snapshot_identity,
    new_run_identity,
    raw_content_identity,
    record_identity,
)


SAMPLE_PAYLOAD = {
    "title": "M1 synthetic public-safe sample",
    "theme_hint": "generative_ai",
    "country": "unknown",
    "measurement": {"unit": "count", "value": 1},
}


def test_run_identities_differ() -> None:
    a = new_run_identity()
    b = new_run_identity()
    assert a != b


def test_record_identity_stable_for_same_logical_input() -> None:
    a = record_identity(source_identity="synthetic.m1_smoke", logical_key="sample-001")
    b = record_identity(source_identity="synthetic.m1_smoke", logical_key="sample-001")
    c = record_identity(source_identity="synthetic.m1_smoke", logical_key="sample-002")
    assert a == b
    assert a != c


def test_raw_content_identity_stable_for_identical_content() -> None:
    a = raw_content_identity(SAMPLE_PAYLOAD)
    b = raw_content_identity(dict(SAMPLE_PAYLOAD))
    c = raw_content_identity({**SAMPLE_PAYLOAD, "title": "changed"})
    assert a == b
    assert a != c
    assert a.startswith("raw_")


def test_canonical_snapshot_identity_deterministic() -> None:
    ids = ["raw_aaa", "raw_bbb"]
    a = canonical_snapshot_identity(
        raw_content_identities=ids,
        dictionary_version="dict-v0",
        aggregation_rule_version="agg-v0",
        code_revision="abc123",
    )
    b = canonical_snapshot_identity(
        raw_content_identities=list(reversed(ids)),
        dictionary_version="dict-v0",
        aggregation_rule_version="agg-v0",
        code_revision="abc123",
    )
    c = canonical_snapshot_identity(
        raw_content_identities=ids,
        dictionary_version="dict-v1",
        aggregation_rule_version="agg-v0",
        code_revision="abc123",
    )
    assert a == b
    assert a != c


def test_second_persist_does_not_overwrite_raw(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    run_1 = new_run_identity()
    run_2 = new_run_identity()

    first = persist_raw_record(
        raw_dir=raw_dir,
        run_identity=run_1,
        source_identity="synthetic.m1_smoke",
        logical_key="sample-001",
        payload=SAMPLE_PAYLOAD,
        ingestion_time="2026-08-23T00:00:00Z",
    )
    first_bytes = first.content_store_path.read_bytes()
    first_mtime = first.content_store_path.stat().st_mtime_ns

    second = persist_raw_record(
        raw_dir=raw_dir,
        run_identity=run_2,
        source_identity="synthetic.m1_smoke",
        logical_key="sample-001",
        payload=SAMPLE_PAYLOAD,
        ingestion_time="2026-08-23T01:00:00Z",
    )

    assert first.record_identity == second.record_identity
    assert first.raw_content_identity == second.raw_content_identity
    assert first.content_was_new is True
    assert second.content_was_new is False
    assert first.content_store_path == second.content_store_path
    assert first.run_artifact_path != second.run_artifact_path
    assert first.run_artifact_path.exists()
    assert second.run_artifact_path.exists()
    assert second.content_store_path.read_bytes() == first_bytes
    assert second.content_store_path.stat().st_mtime_ns == first_mtime
