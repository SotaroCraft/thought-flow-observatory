"""OpenAlex Raw backfill foundation (M7).

Production path: full cursor pagination, append-only Raw, resumable checkpoints.
Smoke ceilings from M5 MUST NOT apply here.
"""

from thought_flow.ingestion.openalex.backfill import (
    BackfillResult,
    OpenAlexBackfillRunner,
    run_openalex_partition_backfill,
)
from thought_flow.ingestion.openalex.campaign import (
    CampaignPlan,
    CampaignResult,
    build_campaign_plan,
    run_openalex_backfill_campaign,
)
from thought_flow.ingestion.openalex.checkpoint import PartitionCheckpoint
from thought_flow.ingestion.openalex.planner import CAMPAIGN_COUNTRIES, plan_daily_partitions
from thought_flow.ingestion.openalex.window import (
    BACKFILL_WINDOW_START,
    RetrievalPartition,
    capture_run_end_date,
)

__all__ = [
    "BACKFILL_WINDOW_START",
    "CAMPAIGN_COUNTRIES",
    "BackfillResult",
    "CampaignPlan",
    "CampaignResult",
    "OpenAlexBackfillRunner",
    "PartitionCheckpoint",
    "RetrievalPartition",
    "build_campaign_plan",
    "capture_run_end_date",
    "plan_daily_partitions",
    "run_openalex_backfill_campaign",
    "run_openalex_partition_backfill",
]
