"""Thin ingestion package. Connectors arrive in later milestones."""

from thought_flow.ingestion.raw_store import RawPersistResult, persist_raw_record

__all__ = ["RawPersistResult", "persist_raw_record"]
