"""Identity and Raw immutability / provenance separation tests for M1."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from thought_flow.ingestion.raw_store import (
    load_content_payload,
    load_run_provenance,
    persist_raw_record,
)
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


def test_same_record_across_runs_reuses_content_without_overwrite(tmp_path: Path) -> None:
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
    assert list((raw_dir / "content").glob("*.parquet")) == [first.content_store_path]
    assert second.content_store_path.read_bytes() == first_bytes
    assert second.content_store_path.stat().st_mtime_ns == first_mtime

    prov_1 = load_run_provenance(first.run_artifact_path)
    prov_2 = load_run_provenance(second.run_artifact_path)
    assert prov_1.run_identity == run_1
    assert prov_2.run_identity == run_2
    assert prov_1.record_identity == prov_2.record_identity == first.record_identity
    assert prov_1.ingestion_time == "2026-08-23T00:00:00Z"
    assert prov_2.ingestion_time == "2026-08-23T01:00:00Z"


def test_different_records_identical_payload_share_content_keep_provenance(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    run_a = new_run_identity()
    run_b = new_run_identity()

    result_a = persist_raw_record(
        raw_dir=raw_dir,
        run_identity=run_a,
        source_identity="synthetic.source_a",
        logical_key="key-a",
        payload=SAMPLE_PAYLOAD,
        ingestion_time="2026-08-23T02:00:00Z",
    )
    result_b = persist_raw_record(
        raw_dir=raw_dir,
        run_identity=run_b,
        source_identity="synthetic.source_b",
        logical_key="key-b",
        payload=SAMPLE_PAYLOAD,
        ingestion_time="2026-08-23T03:00:00Z",
    )

    assert result_a.record_identity != result_b.record_identity
    assert result_a.raw_content_identity == result_b.raw_content_identity
    assert result_a.content_store_path == result_b.content_store_path
    assert result_a.content_was_new is True
    assert result_b.content_was_new is False
    assert len(list((raw_dir / "content").glob("*.parquet"))) == 1

    content_cols = set(pq.read_table(result_a.content_store_path).column_names)
    assert content_cols == {"raw_content_identity", "payload_json"}
    assert load_content_payload(result_a.content_store_path) == SAMPLE_PAYLOAD

    prov_a = load_run_provenance(result_a.run_artifact_path)
    prov_b = load_run_provenance(result_b.run_artifact_path)
    assert prov_a.record_identity == result_a.record_identity
    assert prov_b.record_identity == result_b.record_identity
    assert prov_a.source_identity == "synthetic.source_a"
    assert prov_b.source_identity == "synthetic.source_b"
    assert prov_a.logical_key == "key-a"
    assert prov_b.logical_key == "key-b"
    assert prov_a.run_identity == run_a
    assert prov_b.run_identity == run_b
    # Reconstructing B never yields A's provenance.
    assert prov_b.record_identity != prov_a.record_identity
    assert prov_b.source_identity != prov_a.source_identity
    assert prov_b.logical_key != prov_a.logical_key
    assert prov_b.ingestion_time != prov_a.ingestion_time
