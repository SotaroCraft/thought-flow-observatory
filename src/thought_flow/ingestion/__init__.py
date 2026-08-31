"""Thin ingestion package. OpenAlex backfill foundation lives under ingestion.openalex."""

from thought_flow.ingestion.raw_store import (
    LegacyContentIndex,
    RawPersistResult,
    RawStorageIntegrityError,
    RunProvenance,
    discover_content_artifacts,
    iter_content_artifact_paths,
    load_content_payload,
    load_run_provenance,
    persist_raw_record,
    preload_legacy_content_index,
)

__all__ = [
    "LegacyContentIndex",
    "RawPersistResult",
    "RawStorageIntegrityError",
    "RunProvenance",
    "discover_content_artifacts",
    "iter_content_artifact_paths",
    "load_content_payload",
    "load_run_provenance",
    "persist_raw_record",
    "preload_legacy_content_index",
]
