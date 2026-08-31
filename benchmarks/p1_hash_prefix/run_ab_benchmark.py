#!/usr/bin/env python3
"""Isolated A/B benchmark for P1 hash-prefix sharding (no live OpenAlex / no live Raw).

A = authoritative current-main flat writer (vendored snapshot)
B = P1 sharded writer + legacy preload

Writes only under an isolated data root. Does not touch workspace-data / M7-019.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import uuid
from pathlib import Path

# Allow running from repo root without install.
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from thought_flow.ingestion.raw_store import (  # noqa: E402
    persist_raw_record as persist_p1,
    preload_legacy_content_index,
)
from thought_flow.ingestion.stage_timing import PageStageTiming, StageTimingSession  # noqa: E402
from thought_flow.observability.identity import new_run_identity  # noqa: E402

import flat_baseline_raw_store as flat_baseline  # noqa: E402


WORKS_PER_PAGE = 200
DEFAULT_PAGES = 100
DEFAULT_CARDINALITY = 123_200
FILLER_PREFIX = "raw_benchfill_"


def _payload(i: int, *, tag: str) -> dict:
    # Representative ~7KB-class payload shape (title + body padding).
    body = ("x" * 64 + str(i % 9973)) * 100
    return {
        "schema": "p1.benchmark.v1",
        "work_id": f"W{tag}{i:08d}",
        "title": f"Benchmark work {tag} {i}",
        "publication_year": 2023,
        "type": "article",
        "authorship_countries": ["US"],
        "country_evidence": [{"country_code": "US", "source": "bench"}],
        "multi_country": False,
        "missing_country": False,
        "abstract_pad": body[:6000],
        "tag": tag,
        "n": i,
    }


def _seed_flat_filler(content_dir: Path, cardinality: int) -> None:
    """Create many tiny flat files to reproduce NTFS large-directory pressure.

    Filenames mimic raw_*.parquet but are not valid Raw content objects for reuse:
    identities are reserved under FILLER_PREFIX and never collide with benchmark payloads.
    """
    content_dir.mkdir(parents=True, exist_ok=True)
    # Minimal parquet-like placeholder bytes are expensive; use tiny unique files with
    # .parquet suffix matching live naming length characteristics without full payloads.
    # Parsers are not run against filler. Name length ≈ live raw_<64hex>.parquet.
    existing = 0
    # Fast path: if directory already near target, skip reseeding.
    try:
        existing = sum(1 for _ in os.scandir(content_dir) if _.name.endswith(".parquet"))
    except FileNotFoundError:
        existing = 0
    if existing >= cardinality:
        return
    for i in range(existing, cardinality):
        digest = hashlib.sha256(f"filler:{i}".encode()).hexdigest()
        name = f"{FILLER_PREFIX}{digest}.parquet"
        path = content_dir / name
        if path.exists():
            continue
        # Tiny unique content (~64B) — namespace cardinality is the goal.
        path.write_bytes(b"BENCHFILL\n" + digest.encode("ascii") + b"\n")


def _median(xs: list[float]) -> float | None:
    return float(statistics.median(xs)) if xs else None


def _p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    ordered = sorted(xs)
    idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return float(ordered[idx])


def _run_writer(
    *,
    label: str,
    raw_dir: Path,
    pages: int,
    works_per_page: int,
    use_p1: bool,
) -> dict:
    session = StageTimingSession()
    preload = None
    preload_s = 0.0
    if use_p1:
        t0 = time.perf_counter()
        preload = preload_legacy_content_index(raw_dir)
        preload_s = time.perf_counter() - t0
        session.legacy_preload_seconds = preload.preload_seconds
        session.legacy_preload_identities = preload.identity_count
        session.legacy_preload_memory_bytes = preload.memory_bytes

    page_totals: list[float] = []
    page_local: list[float] = []
    content_new = 0
    content_reused = 0
    works = 0
    persist_fn = persist_p1 if use_p1 else flat_baseline.persist_raw_record

    steady_t0 = time.perf_counter()
    for page_index in range(pages):
        run_id = new_run_identity()
        page_t0 = time.perf_counter()
        c_sec = 0.0
        p_sec = 0.0
        page_new = 0
        page_reused = 0
        base = page_index * works_per_page
        for j in range(works_per_page):
            i = base + j
            payload = _payload(i, tag=label)
            kwargs = dict(
                raw_dir=raw_dir,
                run_identity=run_id,
                source_identity="bench.openalex.works",
                logical_key=f"work:{payload['work_id']}",
                payload=payload,
                ingestion_time="2026-08-31T00:00:00Z",
            )
            if use_p1:
                kwargs["legacy_content_index"] = preload
            t_item0 = time.perf_counter()
            result = persist_fn(**kwargs)
            item_dt = time.perf_counter() - t_item0
            if use_p1:
                c_sec += result.timings.content_persist_seconds
                p_sec += result.timings.provenance_persist_seconds
            else:
                # Baseline has no stage split; attribute full item time to local persist.
                c_sec += item_dt
            if result.content_was_new:
                content_new += 1
                page_new += 1
            else:
                content_reused += 1
                page_reused += 1
            works += 1
        # Simulated checkpoint cost (tiny JSON) — not on live Raw.
        ck_t0 = time.perf_counter()
        ck_path = raw_dir.parent / "bench_ck" / f"{label}_page_{page_index}.json"
        ck_path.parent.mkdir(parents=True, exist_ok=True)
        ck_path.write_text(json.dumps({"page": page_index, "works": works_per_page}), encoding="utf-8")
        ck_s = time.perf_counter() - ck_t0
        total = time.perf_counter() - page_t0
        page_totals.append(total)
        page_local.append(c_sec + p_sec)
        session.pages.append(
            PageStageTiming(
                page_index=page_index,
                http_seconds=0.0,
                json_parse_seconds=0.0,
                projection_seconds=0.0,
                content_persist_seconds=c_sec,
                provenance_persist_seconds=p_sec,
                checkpoint_seconds=ck_s,
                total_seconds=total,
                works_count=works_per_page,
                content_new=page_new,
                content_reused=page_reused,
            )
        )
    steady_wall = time.perf_counter() - steady_t0
    first20 = page_totals[:20]
    last20 = page_totals[-20:] if len(page_totals) >= 20 else page_totals
    first_med = _median(first20)
    last_med = _median(last20)
    degradation = (last_med / first_med) if first_med and last_med and first_med > 0 else None
    return {
        "label": label,
        "use_p1": use_p1,
        "pages": pages,
        "works_per_page": works_per_page,
        "works": works,
        "content_new": content_new,
        "content_reused": content_reused,
        "median_sec_per_page": _median(page_totals),
        "p95_sec_per_page": _p95(page_totals),
        "local_persist_median": _median(page_local),
        "local_persist_p95": _p95(page_local),
        "first20_median": first_med,
        "last20_median": last_med,
        "degradation_ratio": degradation,
        "works_per_hour": (works / steady_wall * 3600.0) if steady_wall > 0 else None,
        "preload_seconds": preload_s,
        "preload_identities": preload.identity_count if preload else 0,
        "preload_memory_bytes": preload.memory_bytes if preload else 0,
        "steady_state_wall_excluding_preload": steady_wall,
        "total_wall_including_preload": steady_wall + preload_s,
        "stage_aggregate": session.aggregate(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=_REPO.parent / "MSPO-p1-bench-data",
        help="Isolated benchmark data root (default: sibling of worktree)",
    )
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES)
    parser.add_argument("--works-per-page", type=int, default=WORKS_PER_PAGE)
    parser.add_argument("--cardinality", type=int, default=DEFAULT_CARDINALITY)
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--only", choices=("A", "B", "both"), default="both")
    args = parser.parse_args()

    root = args.data_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    host_info = {
        "system": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        # Avoid private absolute host identifiers beyond drive letter.
        "data_root_drive": os.path.splitdrive(str(root))[0] or "unknown",
    }

    out: dict = {
        "host": host_info,
        "pages": args.pages,
        "works_per_page": args.works_per_page,
        "target_cardinality": args.cardinality,
        "filler_prefix": FILLER_PREFIX,
        "A": None,
        "B": None,
    }

    if args.only in ("A", "both"):
        raw_a = root / "A_flat" / "raw"
        if not args.skip_seed:
            print(f"[A] seeding flat filler cardinality~={args.cardinality} ...", flush=True)
            t_seed = time.perf_counter()
            _seed_flat_filler(raw_a / "content", args.cardinality)
            print(f"[A] seed done in {time.perf_counter() - t_seed:.1f}s", flush=True)
        print("[A] running flat baseline writer ...", flush=True)
        out["A"] = _run_writer(
            label="A",
            raw_dir=raw_a,
            pages=args.pages,
            works_per_page=args.works_per_page,
            use_p1=False,
        )
        print(json.dumps({k: out["A"][k] for k in (
            "median_sec_per_page", "p95_sec_per_page", "local_persist_median",
            "works_per_hour", "degradation_ratio", "total_wall_including_preload",
        )}, indent=2), flush=True)

    if args.only in ("B", "both"):
        raw_b = root / "B_p1" / "raw"
        if not args.skip_seed:
            print(f"[B] seeding flat filler cardinality~={args.cardinality} ...", flush=True)
            t_seed = time.perf_counter()
            _seed_flat_filler(raw_b / "content", args.cardinality)
            print(f"[B] seed done in {time.perf_counter() - t_seed:.1f}s", flush=True)
        print("[B] running P1 writer ...", flush=True)
        out["B"] = _run_writer(
            label="B",
            raw_dir=raw_b,
            pages=args.pages,
            works_per_page=args.works_per_page,
            use_p1=True,
        )
        print(json.dumps({k: out["B"][k] for k in (
            "median_sec_per_page", "p95_sec_per_page", "local_persist_median",
            "works_per_hour", "degradation_ratio", "preload_seconds",
            "total_wall_including_preload",
        )}, indent=2), flush=True)

    # Gate evaluation for B
    b = out.get("B")
    if b:
        hard = (
            (b["median_sec_per_page"] or 999) <= 30
            and (b["p95_sec_per_page"] or 999) <= 45
            and (b["local_persist_median"] or 999) <= 15
            and (b["local_persist_p95"] or 999) <= 30
            and (b["works_per_hour"] or 0) >= 24_000
            and (b["degradation_ratio"] or 999) <= 1.20
        )
        sufficient = (
            (b["median_sec_per_page"] or 999) <= 20
            and (b["p95_sec_per_page"] or 999) <= 30
            and (b["local_persist_median"] or 999) <= 10
            and (b["local_persist_p95"] or 999) <= 20
            and (b["works_per_hour"] or 0) >= 30_000
            and (b["degradation_ratio"] or 999) <= 1.15
        )
        out["gates"] = {
            "P1_HARD_GATE": "PASS" if hard else "FAIL",
            "P1_SUFFICIENT": "YES" if sufficient else "NO",
        }
    a = out.get("A")
    if a and b:
        # Live degradation reference ~95s/page; require A median meaningfully high.
        reproduces = "NO"
        if (a["median_sec_per_page"] or 0) >= 40:
            reproduces = "YES"
        elif (a["median_sec_per_page"] or 0) >= 15:
            reproduces = "PARTIAL"
        out["benchmark_reproduces_live_degradation"] = reproduces
        if reproduces == "NO":
            out["live_speedup_inference"] = "BENCHMARK_INCONCLUSIVE_FOR_LIVE_SPEEDUP"
        elif reproduces == "PARTIAL":
            out["live_speedup_inference"] = "PARTIALLY_SUPPORTED"
        else:
            out["live_speedup_inference"] = "SUPPORTED"

    stamp = uuid.uuid4().hex[:8]
    out_path = results_dir / f"p1_ab_result_{stamp}.json"
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    # Also write a stable latest pointer (relative names only).
    (results_dir / "latest.json").write_text(
        json.dumps({"result_file": out_path.name, **{k: out.get(k) for k in ("gates", "A", "B", "benchmark_reproduces_live_degradation", "live_speedup_inference")}}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
