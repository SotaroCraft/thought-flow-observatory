"""Append-only Raw persistence for M1 local smoke path.

Content store holds payload-only objects addressed by raw_content_identity.
Per-run provenance artifacts reference that content and never rewrite it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from thought_flow.observability.identity import raw_content_identity, record_identity

# Columns that must never appear in the content-addressed object.
_PROVENANCE_KEYS = frozenset(
    {
        "run_identity",
        "record_identity",
        "source_identity",
        "logical_key",
        "ingestion_time",
        "quality_state",
        "content_was_new",
        "content_store_path",
    }
)


@dataclass(frozen=True)
class RawPersistResult:
    record_identity: str
    raw_content_identity: str
    run_artifact_path: Path
    content_store_path: Path
    content_was_new: bool
    payload: dict[str, Any]


@dataclass(frozen=True)
class RunProvenance:
    run_identity: str
    record_identity: str
    source_identity: str
    logical_key: str
    ingestion_time: str
    quality_state: str
    raw_content_identity: str
    content_store_path: str
    content_was_new: bool


def _content_store_path(raw_dir: Path, content_id: str) -> Path:
    return raw_dir / "content" / f"{content_id}.parquet"


def _run_artifact_path(raw_dir: Path, run_id: str, record_id: str) -> Path:
    return raw_dir / "runs" / run_id / f"{record_id}.parquet"


def _content_table(*, content_id: str, payload: dict[str, Any]) -> pa.Table:
    return pa.table(
        {
            "raw_content_identity": [content_id],
            "payload_json": [json.dumps(payload, sort_keys=True, ensure_ascii=False)],
        }
    )


def _provenance_table(prov: dict[str, Any]) -> pa.Table:
    return pa.table({key: [value] for key, value in prov.items()})


def load_run_provenance(path: Path) -> RunProvenance:
    """Load per-run / per-record provenance from a run artifact (not the content store)."""
    table = pq.read_table(path)
    if table.num_rows != 1:
        raise ValueError(f"Expected single-row provenance artifact, got {table.num_rows}: {path}")
    row = {name: table.column(name)[0].as_py() for name in table.column_names}
    return RunProvenance(
        run_identity=row["run_identity"],
        record_identity=row["record_identity"],
        source_identity=row["source_identity"],
        logical_key=row["logical_key"],
        ingestion_time=row["ingestion_time"],
        quality_state=row["quality_state"],
        raw_content_identity=row["raw_content_identity"],
        content_store_path=row["content_store_path"],
        content_was_new=bool(row["content_was_new"]),
    )


def load_content_payload(path: Path) -> dict[str, Any]:
    """Load payload-only content object; rejects provenance columns."""
    table = pq.read_table(path)
    names = set(table.column_names)
    leaked = sorted(names & _PROVENANCE_KEYS)
    if leaked:
        raise ValueError(f"Content object contains provenance columns: {leaked}")
    if "payload_json" not in names or "raw_content_identity" not in names:
        raise ValueError(f"Content object missing required columns: {path}")
    if table.num_rows != 1:
        raise ValueError(f"Expected single-row content object, got {table.num_rows}: {path}")
    return json.loads(table.column("payload_json")[0].as_py())


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

    - Content store: payload only, keyed by raw_content_identity (append-only).
    - Run artifact: provenance + content reference (unique per run/record).
    """
    rec_id = record_identity(source_identity=source_identity, logical_key=logical_key)
    content_id = raw_content_identity(payload)
    content_path = _content_store_path(raw_dir, content_id)
    run_path = _run_artifact_path(raw_dir, run_identity, rec_id)

    content_was_new = not content_path.exists()
    if content_was_new:
        content_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(_content_table(content_id=content_id, payload=payload), content_path)
    elif content_path.is_file():
        # Existing content must remain untouched (immutable Raw).
        # Conflicting bytes at the same content identity fail closed.
        existing = load_content_payload(content_path)
        existing_norm = json.dumps(existing, sort_keys=True, ensure_ascii=False)
        incoming_norm = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        if existing_norm != incoming_norm:
            raise FileExistsError(
                f"Content conflict at existing Raw identity (refusing overwrite): {content_path}"
            )
    else:
        raise FileExistsError(f"Content path exists but is not a file: {content_path}")

    if run_path.exists():
        raise FileExistsError(f"Run artifact already exists (refusing overwrite): {run_path}")

    provenance = {
        "run_identity": run_identity,
        "record_identity": rec_id,
        "source_identity": source_identity,
        "logical_key": logical_key,
        "ingestion_time": ingestion_time,
        "quality_state": quality_state,
        "raw_content_identity": content_id,
        "content_store_path": str(content_path),
        "content_was_new": content_was_new,
    }
    run_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(_provenance_table(provenance), run_path)

    return RawPersistResult(
        record_identity=rec_id,
        raw_content_identity=content_id,
        run_artifact_path=run_path,
        content_store_path=content_path,
        content_was_new=content_was_new,
        payload=payload,
    )
