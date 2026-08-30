"""OpenAlex Raw backfill foundation (M7).

Production path: full cursor pagination, append-only Raw, resumable checkpoints.
Smoke ceilings from M5 MUST NOT apply here.
"""

from thought_flow.ingestion.openalex.backfill import (
    BackfillResult,
    OpenAlexBackfillRunner,
    run_openalex_partition_backfill,
)
from thought_flow.ingestion.openalex.checkpoint import PartitionCheckpoint
from thought_flow.ingestion.openalex.window import (
    BACKFILL_WINDOW_START,
    RetrievalPartition,
    capture_run_end_date,
)

__all__ = [
    "BACKFILL_WINDOW_START",
    "BackfillResult",
    "OpenAlexBackfillRunner",
    "PartitionCheckpoint",
    "RetrievalPartition",
    "capture_run_end_date",
    "run_openalex_partition_backfill",
]
