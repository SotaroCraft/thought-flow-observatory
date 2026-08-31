"""Append-only Raw persistence for M1 local smoke path.

Content store holds payload-only objects addressed by raw_content_identity.
Per-run provenance artifacts reference that content and never rewrite it.

P1 physical layout (new artifacts only):
  raw/content/<2-hex>/<raw_content_identity>.parquet
  raw/runs/<run_identity>/<2-hex>/<record_identity>.parquet

Legacy flat artifacts remain readable; never migrated/renamed/deleted.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from thought_flow.atomic_io import is_temporary_sidecar, write_parquet_via_temp_no_clobber
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

_HEX = frozenset("0123456789abcdef")


class RawStorageIntegrityError(FileExistsError):
    """Fail-closed storage conflict (e.g. legacy + sharded both present)."""


@dataclass(frozen=True)
class RawPersistTimings:
    content_persist_seconds: float = 0.0
    provenance_persist_seconds: float = 0.0

    @property
    def local_persist_seconds(self) -> float:
        return self.content_persist_seconds + self.provenance_persist_seconds


@dataclass(frozen=True)
class RawPersistResult:
    record_identity: str
    raw_content_identity: str
    run_artifact_path: Path
    content_store_path: Path
    content_was_new: bool
    payload: dict[str, Any]
    timings: RawPersistTimings = field(default_factory=RawPersistTimings)


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


@dataclass(frozen=True)
class LegacyContentIndex:
    """Read-only in-memory lookup of legacy flat content identities."""

    identities: frozenset[str]
    preload_seconds: float
    identity_count: int
    memory_bytes: int

    def __contains__(self, content_id: str) -> bool:
        return content_id in self.identities


def shard_prefix_from_content_id(content_id: str) -> str:
    """First 2 hex chars of the digest after stripping ``raw_``."""
    if not content_id.startswith("raw_") or len(content_id) < 6:
        raise ValueError(f"Invalid raw_content_identity for sharding: {content_id!r}")
    digest = content_id[4:]
    prefix = digest[:2].lower()
    if len(prefix) != 2 or any(c not in _HEX for c in prefix):
        raise ValueError(f"raw_content_identity digest prefix is not hex: {content_id!r}")
    return prefix


def shard_prefix_from_record_id(record_id: str) -> str:
    """First 2 hex chars of the digest after stripping ``rec_``."""
    if not record_id.startswith("rec_") or len(record_id) < 6:
        raise ValueError(f"Invalid record_identity for sharding: {record_id!r}")
    digest = record_id[4:]
    prefix = digest[:2].lower()
    if len(prefix) != 2 or any(c not in _HEX for c in prefix):
        raise ValueError(f"record_identity digest prefix is not hex: {record_id!r}")
    return prefix


def legacy_content_path(raw_dir: Path, content_id: str) -> Path:
    return raw_dir / "content" / f"{content_id}.parquet"


def sharded_content_path(raw_dir: Path, content_id: str) -> Path:
    return raw_dir / "content" / shard_prefix_from_content_id(content_id) / f"{content_id}.parquet"


def legacy_run_artifact_path(raw_dir: Path, run_id: str, record_id: str) -> Path:
    return raw_dir / "runs" / run_id / f"{record_id}.parquet"


def sharded_run_artifact_path(raw_dir: Path, run_id: str, record_id: str) -> Path:
    return (
        raw_dir
        / "runs"
        / run_id
        / shard_prefix_from_record_id(record_id)
        / f"{record_id}.parquet"
    )


def _is_shard_dir_name(name: str) -> bool:
    return len(name) == 2 and name[0] in _HEX and name[1] in _HEX


def _content_id_from_filename(path: Path) -> str | None:
    if path.suffix != ".parquet" or is_temporary_sidecar(path):
        return None
    stem = path.stem
    if stem.startswith("raw_"):
        return stem
    return None


def _record_id_from_filename(path: Path) -> str | None:
    if path.suffix != ".parquet" or is_temporary_sidecar(path):
        return None
    stem = path.stem
    if stem.startswith("rec_"):
        return stem
    return None


def preload_legacy_content_index(raw_dir: Path) -> LegacyContentIndex:
    """
    Load legacy flat content identities once (non-recursive ``content/*.parquet`` only).

    Sharded paths under ``content/<xx>/`` are intentionally excluded from this index.
    """
    started = time.perf_counter()
    content_root = raw_dir / "content"
    identities: set[str] = set()
    if content_root.is_dir():
        # Non-recursive: only immediate files (legacy flat layout).
        with os_scandir(content_root) as entries:
            for entry in entries:
                if not entry.is_file(follow_symlinks=False):
                    continue
                name = entry.name
                if not name.endswith(".parquet") or name.startswith(".") or name.endswith(".tmp"):
                    continue
                if name.startswith("raw_") and name.endswith(".parquet"):
                    identities.add(name[: -len(".parquet")])
    elapsed = time.perf_counter() - started
    frozen = frozenset(identities)
    memory_bytes = sys.getsizeof(frozen) + sum(sys.getsizeof(x) for x in frozen)
    return LegacyContentIndex(
        identities=frozen,
        preload_seconds=elapsed,
        identity_count=len(frozen),
        memory_bytes=memory_bytes,
    )


def os_scandir(path: Path):
    """Local wrapper so tests can patch scandir if needed."""
    import os

    return os.scandir(path)


def resolve_content_path(
    raw_dir: Path,
    content_id: str,
    *,
    legacy_index: LegacyContentIndex | None = None,
) -> Path | None:
    """
    Resolve an existing content artifact path.

    Returns None when neither legacy nor sharded exists (caller creates sharded).
    Raises RawStorageIntegrityError when both exist (fail closed).
    """
    legacy = legacy_content_path(raw_dir, content_id)
    sharded = sharded_content_path(raw_dir, content_id)
    if legacy_index is not None:
        legacy_exists = content_id in legacy_index
    else:
        legacy_exists = legacy.is_file()
    # Sharded dirs stay small; a single is_file here is intentional for conflict detection.
    sharded_exists = sharded.is_file()
    if legacy_exists and sharded_exists:
        raise RawStorageIntegrityError(
            f"Content identity present in both legacy and sharded paths "
            f"(fail closed): {content_id}"
        )
    if legacy_exists:
        return legacy
    if sharded_exists:
        return sharded
    return None


def resolve_run_artifact_path(raw_dir: Path, run_id: str, record_id: str) -> Path | None:
    """Resolve existing run provenance path; None if absent; fail closed if both."""
    legacy = legacy_run_artifact_path(raw_dir, run_id, record_id)
    sharded = sharded_run_artifact_path(raw_dir, run_id, record_id)
    legacy_exists = legacy.is_file()
    sharded_exists = sharded.is_file()
    if legacy_exists and sharded_exists:
        raise RawStorageIntegrityError(
            f"Run provenance present in both legacy and sharded paths "
            f"(fail closed): run={run_id} record={record_id}"
        )
    if legacy_exists:
        return legacy
    if sharded_exists:
        return sharded
    return None


def iter_content_artifact_paths(raw_dir: Path) -> Iterator[Path]:
    """Yield completed content artifacts (legacy flat + one-level shards). Skips temps."""
    content_root = raw_dir / "content"
    if not content_root.is_dir():
        return
    for entry in sorted(content_root.iterdir(), key=lambda p: p.name):
        if entry.is_file():
            if _content_id_from_filename(entry) is not None:
                yield entry
        elif entry.is_dir() and _is_shard_dir_name(entry.name.lower()):
            for child in sorted(entry.iterdir(), key=lambda p: p.name):
                if child.is_file() and _content_id_from_filename(child) is not None:
                    yield child


def discover_content_artifacts(raw_dir: Path) -> dict[str, Path]:
    """Map content identity -> path; fail closed on duplicate logical identities."""
    found: dict[str, Path] = {}
    for path in iter_content_artifact_paths(raw_dir):
        content_id = _content_id_from_filename(path)
        if content_id is None:
            continue
        prior = found.get(content_id)
        if prior is not None and prior != path:
            raise RawStorageIntegrityError(
                f"Duplicate content identity in discovery (fail closed): {content_id}"
            )
        found[content_id] = path
    return found


def iter_run_artifact_paths(raw_dir: Path, run_id: str) -> Iterator[Path]:
    """Yield completed provenance artifacts for one run (legacy + sharded)."""
    run_root = raw_dir / "runs" / run_id
    if not run_root.is_dir():
        return
    for entry in sorted(run_root.iterdir(), key=lambda p: p.name):
        if entry.is_file():
            if _record_id_from_filename(entry) is not None:
                yield entry
        elif entry.is_dir() and _is_shard_dir_name(entry.name.lower()):
            for child in sorted(entry.iterdir(), key=lambda p: p.name):
                if child.is_file() and _record_id_from_filename(child) is not None:
                    yield child


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


def _validate_existing_content(path: Path, payload: dict[str, Any]) -> None:
    existing = load_content_payload(path)
    existing_norm = json.dumps(existing, sort_keys=True, ensure_ascii=False)
    incoming_norm = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    if existing_norm != incoming_norm:
        raise FileExistsError(
            f"Content conflict at existing Raw identity (refusing overwrite): {path}"
        )


def _publish_new_content(
    *,
    content_id: str,
    payload: dict[str, Any],
    target: Path,
) -> bool:
    """
    Publish new content at ``target`` (sharded path).

    Returns True if this call created the artifact; False if an identical
    concurrent artifact was reused. Raises on conflicting content.
    """
    table = _content_table(content_id=content_id, payload=payload)
    try:
        write_parquet_via_temp_no_clobber(table, target)
        return True
    except FileExistsError:
        _validate_existing_content(target, payload)
        return False


def persist_raw_record(
    *,
    raw_dir: Path,
    run_identity: str,
    source_identity: str,
    logical_key: str,
    payload: dict[str, Any],
    ingestion_time: str,
    quality_state: str = "success",
    legacy_content_index: LegacyContentIndex | None = None,
) -> RawPersistResult:
    """
    Persist one Raw record without overwriting existing content-addressed artifacts.

    - Content store: payload only, keyed by raw_content_identity (append-only).
    - Run artifact: provenance + content reference (unique per run/record).
    - New artifacts use one-level hash-prefix sharding; legacy flat remains readable.
    """
    rec_id = record_identity(source_identity=source_identity, logical_key=logical_key)
    content_id = raw_content_identity(payload)

    t_content0 = time.perf_counter()
    existing_content = resolve_content_path(
        raw_dir, content_id, legacy_index=legacy_content_index
    )
    if existing_content is not None:
        # Prefer direct open over an extra exists() on huge legacy directories.
        _validate_existing_content(existing_content, payload)
        content_path = existing_content
        content_was_new = False
    else:
        content_path = sharded_content_path(raw_dir, content_id)
        content_was_new = _publish_new_content(
            content_id=content_id, payload=payload, target=content_path
        )
    content_seconds = time.perf_counter() - t_content0

    t_prov0 = time.perf_counter()
    existing_run = resolve_run_artifact_path(raw_dir, run_identity, rec_id)
    if existing_run is not None:
        raise FileExistsError(f"Run artifact already exists (refusing overwrite): {existing_run}")

    run_path = sharded_run_artifact_path(raw_dir, run_identity, rec_id)
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
    try:
        write_parquet_via_temp_no_clobber(_provenance_table(provenance), run_path)
    except FileExistsError as exc:
        raise FileExistsError(
            f"Run artifact already exists (refusing overwrite): {run_path}"
        ) from exc
    provenance_seconds = time.perf_counter() - t_prov0

    return RawPersistResult(
        record_identity=rec_id,
        raw_content_identity=content_id,
        run_artifact_path=run_path,
        content_store_path=content_path,
        content_was_new=content_was_new,
        payload=payload,
        timings=RawPersistTimings(
            content_persist_seconds=content_seconds,
            provenance_persist_seconds=provenance_seconds,
        ),
    )


# Back-compat aliases used by older call sites / docs mentally mapping flat helpers.
def _content_store_path(raw_dir: Path, content_id: str) -> Path:
    """Preferred path for *new* content (sharded). Prefer resolve_* for reads."""
    return sharded_content_path(raw_dir, content_id)


def _run_artifact_path(raw_dir: Path, run_id: str, record_id: str) -> Path:
    """Preferred path for *new* provenance (sharded)."""
    return sharded_run_artifact_path(raw_dir, run_id, record_id)
