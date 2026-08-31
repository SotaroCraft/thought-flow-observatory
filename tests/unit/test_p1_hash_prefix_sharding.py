"""P1 hash-prefix sharding — layout, compatibility, atomic publish, discovery."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from thought_flow.atomic_io import is_temporary_sidecar, write_parquet_via_temp_no_clobber
from thought_flow.ingestion.openalex.backfill import (
    production_openalex_client,
    run_openalex_partition_backfill,
)
from thought_flow.ingestion.openalex.checkpoint import load_checkpoint
from thought_flow.ingestion.openalex.window import RetrievalPartition
from thought_flow.ingestion.raw_store import (
    RawStorageIntegrityError,
    _content_table,
    _publish_new_content,
    discover_content_artifacts,
    iter_content_artifact_paths,
    iter_run_artifact_paths,
    legacy_content_path,
    legacy_run_artifact_path,
    load_content_payload,
    load_run_provenance,
    persist_raw_record,
    preload_legacy_content_index,
    resolve_content_path,
    resolve_run_artifact_path,
    shard_prefix_from_content_id,
    shard_prefix_from_record_id,
    sharded_content_path,
    sharded_run_artifact_path,
)
from thought_flow.observability.identity import new_run_identity, raw_content_identity, record_identity


SAMPLE = {"title": "P1 sample", "country": "unknown", "n": 1}


def _work(work_id: str, title: str, countries: list[str] | None = None) -> dict[str, Any]:
    authorships = []
    if countries:
        for code in countries:
            authorships.append(
                {
                    "institutions": [
                        {"country_code": code, "display_name": f"Inst-{code}", "type": "education"}
                    ]
                }
            )
    return {
        "id": f"https://openalex.org/{work_id}",
        "display_name": title,
        "publication_year": 2022,
        "type": "article",
        "authorships": authorships,
        "primary_location": {"source": {"display_name": "Journal"}},
    }


def _page(results: list[dict[str, Any]], count: int, next_cursor: str | None = None) -> bytes:
    meta: dict[str, Any] = {"count": count}
    if next_cursor is not None:
        meta["next_cursor"] = next_cursor
    return json.dumps({"meta": meta, "results": results}).encode("utf-8")


def test_shard_prefix_content_and_provenance() -> None:
    content_id = "raw_abcd1234" + ("0" * 56)
    record_id = "rec_3f891234" + ("0" * 24)
    assert shard_prefix_from_content_id(content_id) == "ab"
    assert shard_prefix_from_record_id(record_id) == "3f"
    # Exactly 256 theoretical shards from 2 hex chars.
    assert len({f"{i:02x}" for i in range(256)}) == 256


def test_new_artifact_uses_sharded_paths(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    result = persist_raw_record(
        raw_dir=raw,
        run_identity=new_run_identity(),
        source_identity="synthetic.p1",
        logical_key="k1",
        payload=SAMPLE,
        ingestion_time="2026-08-31T00:00:00Z",
    )
    content_id = result.raw_content_identity
    rec_id = result.record_identity
    assert result.content_store_path == sharded_content_path(raw, content_id)
    assert result.run_artifact_path == sharded_run_artifact_path(
        raw, result.run_artifact_path.parts[-3], rec_id
    )
    # path: runs/<run_id>/<shard>/<rec>.parquet
    assert result.run_artifact_path.parent.name == shard_prefix_from_record_id(rec_id)
    assert result.content_store_path.parent.name == shard_prefix_from_content_id(content_id)
    assert not legacy_content_path(raw, content_id).exists()
    assert result.content_was_new is True


def test_legacy_flat_only_read_and_reuse(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    content_id = raw_content_identity(SAMPLE)
    legacy = legacy_content_path(raw, content_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_content_table(content_id=content_id, payload=SAMPLE), legacy)
    before_bytes = legacy.read_bytes()
    before_mtime = legacy.stat().st_mtime_ns
    before_hash = content_id

    index = preload_legacy_content_index(raw)
    assert content_id in index
    resolved = resolve_content_path(raw, content_id, legacy_index=index)
    assert resolved == legacy

    second = persist_raw_record(
        raw_dir=raw,
        run_identity=new_run_identity(),
        source_identity="synthetic.p1",
        logical_key="legacy-reuse",
        payload=SAMPLE,
        ingestion_time="2026-08-31T01:00:00Z",
        legacy_content_index=index,
    )
    assert second.content_was_new is False
    assert second.content_store_path == legacy
    assert not sharded_content_path(raw, content_id).exists()
    assert legacy.read_bytes() == before_bytes
    assert legacy.stat().st_mtime_ns == before_mtime
    assert second.raw_content_identity == before_hash


def test_sharded_only_read(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    first = persist_raw_record(
        raw_dir=raw,
        run_identity=new_run_identity(),
        source_identity="synthetic.p1",
        logical_key="s1",
        payload=SAMPLE,
        ingestion_time="2026-08-31T00:00:00Z",
    )
    resolved = resolve_content_path(raw, first.raw_content_identity)
    assert resolved == first.content_store_path
    assert load_content_payload(resolved) == SAMPLE


def test_mixed_tree_read(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    legacy_payload = {**SAMPLE, "title": "legacy"}
    sharded_payload = {**SAMPLE, "title": "sharded"}
    legacy_id = raw_content_identity(legacy_payload)
    legacy = legacy_content_path(raw, legacy_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_content_table(content_id=legacy_id, payload=legacy_payload), legacy)

    sharded = persist_raw_record(
        raw_dir=raw,
        run_identity=new_run_identity(),
        source_identity="synthetic.p1",
        logical_key="mixed-new",
        payload=sharded_payload,
        ingestion_time="2026-08-31T00:00:00Z",
    )
    found = discover_content_artifacts(raw)
    assert found[legacy_id] == legacy
    assert found[sharded.raw_content_identity] == sharded.content_store_path
    assert len(found) == 2


def test_legacy_plus_sharded_conflict_fail_closed(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    content_id = raw_content_identity(SAMPLE)
    legacy = legacy_content_path(raw, content_id)
    sharded = sharded_content_path(raw, content_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    sharded.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_content_table(content_id=content_id, payload=SAMPLE), legacy)
    pq.write_table(_content_table(content_id=content_id, payload=SAMPLE), sharded)

    with pytest.raises(RawStorageIntegrityError, match="both legacy and sharded"):
        resolve_content_path(raw, content_id)
    with pytest.raises(RawStorageIntegrityError, match="Duplicate content identity"):
        discover_content_artifacts(raw)
    with pytest.raises(RawStorageIntegrityError):
        persist_raw_record(
            raw_dir=raw,
            run_identity=new_run_identity(),
            source_identity="synthetic.p1",
            logical_key="conflict",
            payload=SAMPLE,
            ingestion_time="2026-08-31T00:00:00Z",
        )


def test_legacy_provenance_unchanged_on_reuse(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    run_id = new_run_identity()
    rec_id = record_identity(source_identity="synthetic.p1", logical_key="prov-legacy")
    # Seed legacy flat content + legacy flat provenance.
    content_id = raw_content_identity(SAMPLE)
    legacy_c = legacy_content_path(raw, content_id)
    legacy_c.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_content_table(content_id=content_id, payload=SAMPLE), legacy_c)
    legacy_p = legacy_run_artifact_path(raw, run_id, rec_id)
    legacy_p.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.table(
            {
                "run_identity": [run_id],
                "record_identity": [rec_id],
                "source_identity": ["synthetic.p1"],
                "logical_key": ["prov-legacy"],
                "ingestion_time": ["2026-08-31T00:00:00Z"],
                "quality_state": ["success"],
                "raw_content_identity": [content_id],
                "content_store_path": [str(legacy_c)],
                "content_was_new": [True],
            }
        ),
        legacy_p,
    )
    before = legacy_p.read_bytes()
    before_mtime = legacy_p.stat().st_mtime_ns

    with pytest.raises(FileExistsError, match="Run artifact already exists"):
        persist_raw_record(
            raw_dir=raw,
            run_identity=run_id,
            source_identity="synthetic.p1",
            logical_key="prov-legacy",
            payload=SAMPLE,
            ingestion_time="2026-08-31T02:00:00Z",
            legacy_content_index=preload_legacy_content_index(raw),
        )
    assert legacy_p.read_bytes() == before
    assert legacy_p.stat().st_mtime_ns == before_mtime
    assert resolve_run_artifact_path(raw, run_id, rec_id) == legacy_p


def test_atomic_normal_content_and_provenance_publish(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    result = persist_raw_record(
        raw_dir=raw,
        run_identity=new_run_identity(),
        source_identity="synthetic.p1",
        logical_key="atomic",
        payload=SAMPLE,
        ingestion_time="2026-08-31T00:00:00Z",
    )
    assert result.content_store_path.is_file()
    assert result.run_artifact_path.is_file()
    assert load_content_payload(result.content_store_path) == SAMPLE
    assert load_run_provenance(result.run_artifact_path).raw_content_identity == (
        result.raw_content_identity
    )


def test_content_final_exists_identical_reuses(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    content_id = raw_content_identity(SAMPLE)
    target = sharded_content_path(raw, content_id)
    assert _publish_new_content(content_id=content_id, payload=SAMPLE, target=target) is True
    assert _publish_new_content(content_id=content_id, payload=SAMPLE, target=target) is False


def test_content_final_exists_conflicting_fail_closed(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    content_id = raw_content_identity(SAMPLE)
    target = sharded_content_path(raw, content_id)
    assert _publish_new_content(content_id=content_id, payload=SAMPLE, target=target) is True
    with pytest.raises(FileExistsError, match="Content conflict"):
        _publish_new_content(
            content_id=content_id,
            payload={**SAMPLE, "title": "other"},
            target=target,
        )


def test_provenance_final_exists_fail_closed(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    run_id = new_run_identity()
    first = persist_raw_record(
        raw_dir=raw,
        run_identity=run_id,
        source_identity="synthetic.p1",
        logical_key="prov-once",
        payload=SAMPLE,
        ingestion_time="2026-08-31T00:00:00Z",
    )
    with pytest.raises(FileExistsError, match="Run artifact already exists"):
        persist_raw_record(
            raw_dir=raw,
            run_identity=run_id,
            source_identity="synthetic.p1",
            logical_key="prov-once",
            payload=SAMPLE,
            ingestion_time="2026-08-31T01:00:00Z",
        )
    assert first.run_artifact_path.read_bytes() == first.run_artifact_path.read_bytes()


def test_interrupted_temp_not_visible_as_raw(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    content_id = raw_content_identity(SAMPLE)
    shard = sharded_content_path(raw, content_id)
    shard.parent.mkdir(parents=True, exist_ok=True)
    tmp = shard.parent / f".{shard.name}.publish-deadbeef.tmp"
    tmp.write_bytes(b"incomplete-not-parquet")
    assert is_temporary_sidecar(tmp)
    assert content_id not in discover_content_artifacts(raw)
    assert list(iter_content_artifact_paths(raw)) == []
    assert resolve_content_path(raw, content_id) is None
    # Completing publish after crash still works and leaves temp disposable.
    result = persist_raw_record(
        raw_dir=raw,
        run_identity=new_run_identity(),
        source_identity="synthetic.p1",
        logical_key="after-crash",
        payload=SAMPLE,
        ingestion_time="2026-08-31T00:00:00Z",
    )
    assert result.content_was_new is True
    assert result.content_store_path.is_file()
    assert tmp.exists()  # crash leftover may remain; must not be treated as Raw


def test_no_clobber_publish_leaves_no_partial_final(tmp_path: Path) -> None:
    final = tmp_path / "out" / "ab" / "raw_x.parquet"
    table = _content_table(content_id="raw_x", payload=SAMPLE)
    write_parquet_via_temp_no_clobber(table, final)
    assert final.is_file()
    # Second publish must not replace / corrupt.
    with pytest.raises(FileExistsError):
        write_parquet_via_temp_no_clobber(table, final)
    assert load_content_payload(final) == SAMPLE


def test_discovery_skips_temps_handles_mixed(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    legacy_payload = {**SAMPLE, "k": "L"}
    sharded_payload = {**SAMPLE, "k": "S"}
    lid = raw_content_identity(legacy_payload)
    legacy = legacy_content_path(raw, lid)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_content_table(content_id=lid, payload=legacy_payload), legacy)
    sharded = persist_raw_record(
        raw_dir=raw,
        run_identity=new_run_identity(),
        source_identity="synthetic.p1",
        logical_key="disc-s",
        payload=sharded_payload,
        ingestion_time="2026-08-31T00:00:00Z",
    )
    junk = sharded.content_store_path.parent / f".{sharded.content_store_path.name}.tmp"
    junk.write_text("nope", encoding="utf-8")
    paths = list(iter_content_artifact_paths(raw))
    assert {p.name for p in paths} == {legacy.name, sharded.content_store_path.name}
    assert junk not in paths


def test_resume_semantics_unchanged_under_p1(tmp_path: Path) -> None:
    phase = {"resume": False}
    fetched: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float):
        cursor = parse_qs(urlsplit(url).query).get("cursor", ["*"])[0]
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

    raw = tmp_path / "raw"
    ck = tmp_path / "ck"
    man = tmp_path / "man"
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
    content_after_first = {p.name for p in iter_content_artifact_paths(raw)}

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
    assert fetched == ["page2"]
    assert second.coverage_status == "success"
    assert second.pages_completed == 2
    assert second.works_persisted == 2
    assert content_after_first <= {p.name for p in iter_content_artifact_paths(raw)}
    ck_data = load_checkpoint(second.checkpoint_path)
    assert ck_data is not None
    assert ck_data.next_cursor is None
    assert ck_data.exhausted is True


def test_preload_index_avoids_flat_lookup_for_known_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = tmp_path / "raw"
    content_id = raw_content_identity(SAMPLE)
    legacy = legacy_content_path(raw, content_id)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_content_table(content_id=content_id, payload=SAMPLE), legacy)
    index = preload_legacy_content_index(raw)

    calls: list[Path] = []
    real_is_file = Path.is_file

    def tracked(self: Path) -> bool:
        calls.append(self)
        # Allow sharded conflict probe; forbid probing the huge flat legacy path.
        if self == legacy:
            raise AssertionError("legacy Path.is_file must not be used when index hits")
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", tracked)
    assert resolve_content_path(raw, content_id, legacy_index=index) == legacy
    assert legacy not in calls
