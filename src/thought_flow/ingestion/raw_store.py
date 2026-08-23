"""Append-only Raw persistence for M1 local smoke path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from thought_flow.observability.identity import raw_content_identity, record_identity


@dataclass(frozen=True)
class RawPersistResult:
    record_identity: str
    raw_content_identity: str
    run_artifact_path: Path
    content_store_path: Path
    content_was_new: bool
    payload: dict[str, Any]


def _content_store_path(raw_dir: Path, content_id: str) -> Path:
    return raw_dir / "content" / f"{content_id}.parquet"


def _run_artifact_path(raw_dir: Path, run_id: str, record_id: str) -> Path:
    return raw_dir / "runs" / run_id / f"{record_id}.parquet"


def _payload_to_table(envelope: dict[str, Any]) -> pa.Table:
    # Store as a single-row table with JSON columns for M1 smoke (DDL freeze waits for M6).
    row = {
        "record_identity": [envelope["record_identity"]],
        "raw_content_identity": [envelope["raw_content_identity"]],
        "run_identity": [envelope["run_identity"]],
        "source_identity": [envelope["source_identity"]],
        "logical_key": [envelope["logical_key"]],
        "ingestion_time": [envelope["ingestion_time"]],
        "quality_state": [envelope["quality_state"]],
        "payload_json": [json.dumps(envelope["payload"], sort_keys=True, ensure_ascii=False)],
    }
    return pa.table(row)


def persist_raw_record(
    *,
    raw_dir: Path,
    run_identity: str,
    source_identity: str,
    logical_key: str,
    payload: dict[str, Any],
    ingestion_time: str,
    quality_state: str = "success",
) -> RawPersistResult:
    """
    Persist one Raw record without overwriting existing content-addressed artifacts.

    - Content store is append-only: identical content is not rewritten.
    - Each run writes its own run-scoped artifact path (unique under the run directory).
    """
    rec_id = record_identity(source_identity=source_identity, logical_key=logical_key)
    content_id = raw_content_identity(payload)
    content_path = _content_store_path(raw_dir, content_id)
    run_path = _run_artifact_path(raw_dir, run_identity, rec_id)

    envelope = {
        "record_identity": rec_id,
        "raw_content_identity": content_id,
        "run_identity": run_identity,
        "source_identity": source_identity,
        "logical_key": logical_key,
        "ingestion_time": ingestion_time,
        "quality_state": quality_state,
        "payload": payload,
    }
    table = _payload_to_table(envelope)

    content_was_new = not content_path.exists()
    if content_was_new:
        content_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, content_path)
    elif content_path.is_file():
        # Existing content must remain untouched (immutable Raw).
        pass
    else:
        raise FileExistsError(f"Content path exists but is not a file: {content_path}")

    if run_path.exists():
        raise FileExistsError(f"Run artifact already exists (refusing overwrite): {run_path}")

    run_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, run_path)

    return RawPersistResult(
        record_identity=rec_id,
        raw_content_identity=content_id,
        run_artifact_path=run_path,
        content_store_path=content_path,
        content_was_new=content_was_new,
        payload=payload,
    )
