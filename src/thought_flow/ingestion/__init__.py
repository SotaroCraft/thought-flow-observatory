"""Thin ingestion package. OpenAlex backfill foundation lives under ingestion.openalex."""

from thought_flow.ingestion.raw_store import (
    RawPageRecord,
    RawPersistResult,
    RunProvenance,
    iter_content_parquet_paths,
    load_content_payload,
    load_run_provenance,
    persist_raw_page_batch,
    persist_raw_record,
)

__all__ = [
    "RawPageRecord",
    "RawPersistResult",
    "RunProvenance",
    "iter_content_parquet_paths",
    "load_content_payload",
    "load_run_provenance",
    "persist_raw_page_batch",
    "persist_raw_record",
]
