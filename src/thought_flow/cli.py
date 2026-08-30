"""Local CLI entry for M1 smoke, M4 Graph SPO smoke, and M5 OpenAlex smoke."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from thought_flow import __version__
from thought_flow.config import load_settings
from thought_flow.ingestion.catalog import count_rows, open_catalog, register_raw_parquet
from thought_flow.ingestion.raw_store import persist_raw_record
from thought_flow.observability import new_run_identity, start_manifest

SYNTHETIC_SOURCE = "synthetic.m1_smoke"
SYNTHETIC_LOGICAL_KEY = "sample-001"
DEFAULT_SAMPLE_RELATIVE = Path("data") / "samples" / "m1_synthetic_raw.json"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _code_revision(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except OSError:
        pass
    return "unknown"


def _load_sample_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Sample payload must be a JSON object")
    return data


def run_smoke(*, sample_path: Path | None = None) -> int:
    settings = load_settings()
    if settings.external_integrations_enabled():
        pass

    settings.ensure_directories()
    run_id = new_run_identity()
    manifest = start_manifest(
        run_identity=run_id,
        run_type="smoke",
        code_revision=_code_revision(settings.repo_root),
    )
    manifest_path = settings.manifests_dir / f"{run_id}.json"

    try:
        path = sample_path or (settings.samples_dir / "m1_synthetic_raw.json")
        if not path.exists():
            candidate = settings.repo_root / DEFAULT_SAMPLE_RELATIVE
            if candidate.exists():
                path = candidate
            else:
                raise FileNotFoundError(f"Sample not found: {path}")

        payload = _load_sample_payload(path)
        sample_identity = path.name

        result = persist_raw_record(
            raw_dir=settings.raw_dir,
            run_identity=run_id,
            source_identity=SYNTHETIC_SOURCE,
            logical_key=SYNTHETIC_LOGICAL_KEY,
            payload=payload,
            ingestion_time=_utc_now(),
            quality_state="success",
        )

        conn = open_catalog(settings.duckdb_path)
        try:
            register_raw_parquet(conn, result.run_artifact_path)
            row_count = count_rows(conn)
        finally:
            conn.close()

        manifest.mark_succeeded(
            input_sample_identity=sample_identity,
            record_identity=result.record_identity,
            raw_content_identity=result.raw_content_identity,
            raw_artifact_path=str(result.run_artifact_path),
            content_store_path=str(result.content_store_path),
            content_was_new=result.content_was_new,
            duckdb_row_count=row_count,
            notes={
                "external_integrations_enabled": settings.external_integrations_enabled(),
                "package_version": __version__,
            },
        )
        manifest.write(manifest_path)
        print(
            json.dumps(
                {
                    "status": "succeeded",
                    "run_identity": run_id,
                    "manifest_path": str(manifest_path),
                    "record_identity": result.record_identity,
                    "raw_content_identity": result.raw_content_identity,
                    "raw_artifact_path": str(result.run_artifact_path),
                    "content_was_new": result.content_was_new,
                    "duckdb_row_count": row_count,
                },
                indent=2,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        manifest.mark_failed(category=type(exc).__name__, message=str(exc))
        manifest.write(manifest_path)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "run_identity": run_id,
                    "manifest_path": str(manifest_path),
                    "failure_category": manifest.failure_category,
                    "failure_message": manifest.failure_message,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def run_m4_graph_spo_smoke(*, live: bool = False) -> int:
    """Run M4 Graph → SPO bounded read smoke. Network/auth only when --live."""
    from thought_flow.integrations.sharepoint.smoke import run_graph_spo_smoke

    settings = load_settings()
    evidence_dir = settings.data_root / "m4-smoke" if live else None
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)

    summary = run_graph_spo_smoke(live=live, evidence_dir=evidence_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    status = summary.get("status")
    if status in {"succeeded", "ready", "disabled", "not_configured"} and not live:
        return 0
    if status == "succeeded":
        return 0
    if status in {"disabled", "not_configured"} and live:
        return 2
    return 1


def run_m5_openalex_smoke(*, live: bool = False, diagnostic_cell: bool = False) -> int:
    """Run OpenAlex M5 bounded smoke. Live network only when --live is set."""
    from thought_flow.smoke.http_client import RequestBudget, SmokeHttpClient
    from thought_flow.smoke.openalex.runner import run_openalex_smoke
    from thought_flow.smoke.progress import progress

    progress("CLI entered", "command=m5-smoke-openalex")
    settings = load_settings()
    progress(
        "config loaded",
        f"data_root={settings.data_root} has_openalex_key_env="
        f"{bool((os.getenv('THOUGHT_FLOW_OPENALEX_API_KEY') or '').strip())}",
    )
    settings.ensure_directories()
    revision = _code_revision(settings.repo_root)
    api_key = os.getenv("THOUGHT_FLOW_OPENALEX_API_KEY")
    if api_key is not None and not api_key.strip():
        api_key = None

    if not live:
        print(
            json.dumps(
                {
                    "status": "not_executed",
                    "reason": "Pass --live to perform bounded OpenAlex network smoke.",
                    "data_root": str(settings.data_root),
                },
                indent=2,
            )
        )
        return 0

    if diagnostic_cell:
        progress(
            "diagnostic mode",
            "cell=US×generative_ai×OA-RECENT (not formal SMOKE-PASS)",
        )

    try:
        summary = run_openalex_smoke(
            data_root=settings.data_root,
            code_revision=revision,
            api_key=api_key,
            http=SmokeHttpClient(budget=RequestBudget(), timeout_seconds=30.0),
            diagnostic_one_cell=diagnostic_cell,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary.get("status") in {"succeeded", "partial"} else 1
    except Exception as exc:  # noqa: BLE001
        progress("CLI failure", f"category={type(exc).__name__}")
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_category": type(exc).__name__,
                    "failure_message": str(exc)[:500],
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def run_m5_trends_alpha_status() -> int:
    """Print public-safe Trends alpha route assessment (no network)."""
    from thought_flow.smoke.trends.alpha_route import assess_alpha_route

    print(json.dumps(assess_alpha_route().to_public_dict(), indent=2, ensure_ascii=False))
    return 0


def run_m5_trends_csv_import(
    *,
    country: str,
    csv_path: Path,
    observation_index: int,
) -> int:
    """Import a Human-exported official Trends CSV into local M5 smoke workspace."""
    from thought_flow.smoke.trends.csv_import import import_human_csv

    settings = load_settings()
    settings.ensure_directories()
    try:
        summary = import_human_csv(
            csv_path=csv_path,
            country=country.upper(),
            data_root=settings.data_root,
            code_revision=_code_revision(settings.repo_root),
            observation_index=observation_index,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary.get("status") == "succeeded" else 1
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_category": type(exc).__name__,
                    "failure_message": str(exc)[:500],
                    "ui_automation": False,
                    "alpha_route_used": False,
                },
                indent=2,
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


def run_m5_trends_alpha_live_blocked() -> int:
    """Hard-block live alpha acquisition until invitation docs exist."""
    from thought_flow.smoke.trends.alpha_route import refuse_alpha_live_call

    try:
        refuse_alpha_live_call()
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "fallback": "m5-trends-csv-import",
                    "production_connector": False,
                    "ui_automation": False,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2
    return 1


def run_m7_openalex_backfill_canary(
    *,
    live: bool,
    country: str = "US",
    source_date: str | None = None,
) -> int:
    """Live canary: one target country × one source date; full cursor pages; no Raw in Git."""
    from datetime import date as date_cls

    from thought_flow.ingestion.openalex.backfill import (
        production_openalex_client,
        run_openalex_partition_backfill,
    )
    from thought_flow.ingestion.openalex.window import RetrievalPartition, capture_run_end_date

    settings = load_settings()
    settings.ensure_directories()
    checkpoint_dir = settings.manifests_dir / "openalex_backfill" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    day = date_cls.fromisoformat(source_date) if source_date else date_cls(2022, 12, 1)
    partition = RetrievalPartition.canary_day(country=country, source_date=day)
    run_end = capture_run_end_date()

    if not live:
        print(
            json.dumps(
                {
                    "status": "LIVE CANARY NOT RUN",
                    "reason": "pass --live to perform network retrieval",
                    "partition": partition.to_manifest(),
                    "run_end_date": run_end.isoformat(),
                },
                indent=2,
            )
        )
        return 0

    client = production_openalex_client()
    result = run_openalex_partition_backfill(
        partition=partition,
        raw_dir=settings.raw_dir,
        checkpoint_dir=checkpoint_dir,
        manifests_dir=settings.manifests_dir,
        client=client,
        run_end_date=run_end,
        code_revision=_code_revision(settings.repo_root),
    )
    print(json.dumps(result.to_public_summary(), indent=2, ensure_ascii=False))
    return 0 if result.coverage_status in {"success", "zero"} else 1


def run_m7_openalex_backfill_campaign(
    *,
    live: bool,
    countries: list[str] | None,
    from_date: str | None,
    to_date: str | None,
    max_partitions: int | None,
    run_end_date: str | None,
) -> int:
    """Dry-run campaign plan by default; live requires explicit country + date bounds."""
    from datetime import date as date_cls

    from thought_flow.ingestion.openalex.campaign import (
        CampaignPlan,
        CampaignResult,
        run_openalex_backfill_campaign,
    )

    settings = load_settings()
    settings.ensure_directories()
    checkpoint_dir = settings.manifests_dir / "openalex_backfill" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    range_start = date_cls.fromisoformat(from_date) if from_date else None
    range_end = date_cls.fromisoformat(to_date) if to_date else None
    frozen_end = date_cls.fromisoformat(run_end_date) if run_end_date else None

    if live and (not countries or range_start is None or range_end is None):
        print(
            json.dumps(
                {
                    "error": "live_requires_explicit_bounds",
                    "message": (
                        "Live campaign requires --country and --from-date/--to-date. "
                        "Full-history live is refused."
                    ),
                },
                indent=2,
            )
        )
        return 2

    try:
        result = run_openalex_backfill_campaign(
            raw_dir=settings.raw_dir,
            checkpoint_dir=checkpoint_dir,
            manifests_dir=settings.manifests_dir,
            live=live,
            countries=countries,
            range_start=range_start,
            range_end=range_end,
            run_end_date=frozen_end,
            max_partitions=max_partitions,
            code_revision=_code_revision(settings.repo_root),
        )
    except ValueError as exc:
        print(json.dumps({"error": "invalid_campaign_request", "message": str(exc)}, indent=2))
        return 2

    if isinstance(result, CampaignPlan):
        print(json.dumps(result.to_public_summary(), indent=2, ensure_ascii=False))
        return 0
    assert isinstance(result, CampaignResult)
    print(json.dumps(result.to_public_summary(), indent=2, ensure_ascii=False))
    return 0 if result.outcome == "succeeded" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thought-flow",
        description="Thought Flow Observatory local entry (M1 / M4 / M5 / M7).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("smoke", help="Run local Raw + DuckDB smoke without external services.")
    smoke.add_argument(
        "--sample",
        type=Path,
        default=None,
        help="Path to a public-safe JSON sample (default: data/samples/m1_synthetic_raw.json).",
    )

    m4 = sub.add_parser(
        "m4-graph-spo-smoke",
        help="Run bounded Graph → SPO read smoke (network/auth only with --live).",
    )
    m4.add_argument(
        "--live",
        action="store_true",
        help="Perform delegated interactive browser auth and one Graph read against configured SPO site.",
    )

    m5 = sub.add_parser(
        "m5-smoke-openalex",
        help="Run bounded OpenAlex M5 smoke (network only with --live).",
    )
    m5.add_argument(
        "--live",
        action="store_true",
        help="Perform live OpenAlex requests within frozen ceilings.",
    )
    m5.add_argument(
        "--diagnostic-cell",
        action="store_true",
        help=(
            "Live pipeline diagnostic only: US × generative_ai × OA-RECENT. "
            "Not a formal M5 SMOKE-PASS."
        ),
    )

    sub.add_parser(
        "m5-trends-alpha-status",
        help="Show Trends alpha public-doc route assessment (no network).",
    )
    sub.add_parser(
        "m5-trends-alpha-live",
        help="Blocked placeholder: refuses undocumented/live alpha until invitation docs exist.",
    )

    trends_import = sub.add_parser(
        "m5-trends-csv-import",
        help="Import Human-exported official Trends UI CSV (no UI automation).",
    )
    trends_import.add_argument("--country", required=True, help="JP|US|KR|CN")
    trends_import.add_argument("--csv", type=Path, required=True, help="Path to official CSV export")
    trends_import.add_argument(
        "--observation-index",
        type=int,
        default=1,
        help="1 = first observation; 2 = repeat (do not fabricate).",
    )

    m7_canary = sub.add_parser(
        "m7-openalex-backfill-canary",
        help="M7 OpenAlex canary: one country × one source date (network only with --live).",
    )
    m7_canary.add_argument(
        "--live",
        action="store_true",
        help="Perform live OpenAlex retrieval with full cursor pagination (no smoke ceilings).",
    )
    m7_canary.add_argument(
        "--country",
        default="JP",
        help="Target country JP|US|KR|CN (default: JP — bounded canary vs full-day US volume).",
    )
    m7_canary.add_argument(
        "--source-date",
        default="2022-12-01",
        help="Single inclusive publication date for the canary partition (YYYY-MM-DD).",
    )

    m7_campaign = sub.add_parser(
        "m7-openalex-backfill-campaign",
        help=(
            "M7 OpenAlex campaign planner/executor. Default is dry-run (no network/Raw writes). "
            "Live requires --live plus --country and --from-date/--to-date."
        ),
    )
    m7_campaign.add_argument(
        "--live",
        action="store_true",
        help="Execute bounded live campaign (refuses unbounded full-history).",
    )
    m7_campaign.add_argument(
        "--country",
        action="append",
        dest="countries",
        default=None,
        help="Target country JP|US|KR|CN (repeatable). Required for --live.",
    )
    m7_campaign.add_argument(
        "--from-date",
        default=None,
        help="Inclusive publication-date start (YYYY-MM-DD). Required for --live.",
    )
    m7_campaign.add_argument(
        "--to-date",
        default=None,
        help="Inclusive publication-date end (YYYY-MM-DD). Required for --live.",
    )
    m7_campaign.add_argument(
        "--max-partitions",
        type=int,
        default=None,
        help="Optional operational cap on partitions processed (not a smoke page ceiling).",
    )
    m7_campaign.add_argument(
        "--run-end-date",
        default=None,
        help="Optional fixed run end date (YYYY-MM-DD) for deterministic planning.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "smoke":
        return run_smoke(sample_path=args.sample)
    if args.command == "m4-graph-spo-smoke":
        return run_m4_graph_spo_smoke(live=args.live)
    if args.command == "m5-smoke-openalex":
        if getattr(args, "diagnostic_cell", False) and not args.live:
            parser.error("--diagnostic-cell requires --live")
        return run_m5_openalex_smoke(
            live=args.live,
            diagnostic_cell=getattr(args, "diagnostic_cell", False),
        )
    if args.command == "m5-trends-alpha-status":
        return run_m5_trends_alpha_status()
    if args.command == "m5-trends-alpha-live":
        return run_m5_trends_alpha_live_blocked()
    if args.command == "m5-trends-csv-import":
        return run_m5_trends_csv_import(
            country=args.country,
            csv_path=args.csv,
            observation_index=args.observation_index,
        )
    if args.command == "m7-openalex-backfill-canary":
        return run_m7_openalex_backfill_canary(
            live=args.live,
            country=args.country,
            source_date=args.source_date,
        )
    if args.command == "m7-openalex-backfill-campaign":
        return run_m7_openalex_backfill_campaign(
            live=args.live,
            countries=args.countries,
            from_date=args.from_date,
            to_date=args.to_date,
            max_partitions=args.max_partitions,
            run_end_date=args.run_end_date,
        )
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
