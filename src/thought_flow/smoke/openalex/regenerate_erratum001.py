"""Regenerate Erratum-001 derived evidence without refetch or Raw overwrite."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thought_flow.smoke.quality import (
    page_query_quality_state,
    remap_pre_erratum001_cell_quality,
)

ERRATUM_ID = "erratum-001"
DERIVED_DIRNAME = "derived"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_inventory(run_dir: Path) -> dict[str, str]:
    """Hash original immutable evidence files (not derived/)."""
    inventory: dict[str, str] = {}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        if rel.startswith(f"{DERIVED_DIRNAME}/"):
            continue
        inventory[rel] = _sha256_file(path)
    return inventory


def regenerate_erratum001(
    run_dir: Path,
    *,
    code_revision: str | None = None,
) -> dict[str, Any]:
    """Write versioned derived evidence under runs/<id>/derived/erratum-001/.

    Original Raw, queries.jsonl, coverage.csv, manifest.json, and HTTP-related
    provenance remain untouched. Only derived/ is written.
    """
    run_dir = run_dir.resolve()
    coverage_path = run_dir / "coverage.csv"
    manifest_path = run_dir / "manifest.json"
    queries_path = run_dir / "queries.jsonl"
    if not coverage_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(f"missing original coverage/manifest under {run_dir}")

    before = _file_inventory(run_dir)
    original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    out_dir = run_dir / DERIVED_DIRNAME / ERRATUM_ID
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- coverage ---
    with coverage_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    corrected_rows: list[dict[str, str]] = []
    for row in rows:
        new_state = remap_pre_erratum001_cell_quality(
            quality_state=row.get("quality_state") or "",
            stop_reason=row.get("stop_reason") or None,
        )
        out = dict(row)
        out["quality_state"] = new_state
        corrected_rows.append(out)

    derived_coverage = out_dir / "coverage.csv"
    with derived_coverage.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(corrected_rows)

    quality_dist = Counter(r["quality_state"] for r in corrected_rows)

    # --- queries (quality remap; cost stays null if unknown) ---
    derived_queries = out_dir / "queries.jsonl"
    query_dist: Counter[str] = Counter()
    with queries_path.open(encoding="utf-8") as src, derived_queries.open(
        "w", encoding="utf-8"
    ) as dst:
        for line in src:
            if not line.strip():
                continue
            obj = json.loads(line)
            status = obj.get("http_status")
            st = obj.get("source_total")
            new_q = page_query_quality_state(
                status_code=int(status) if status is not None else None,
                source_total=int(st) if st is not None else None,
                error=obj.get("error"),
            )
            obj["quality_state"] = new_q
            # Never coerce unknown cost to 0.0
            if obj.get("cost_usd") == 0.0 and "x-api-cost" not in str(
                (obj.get("rate") or {})
            ).lower():
                # Original already null; keep null. If somehow 0.0 without
                # reported header evidence, treat as unknown.
                rate = obj.get("rate") or {}
                headers = {str(k).lower(): v for k, v in dict(rate).items()}
                if "x-api-cost" not in headers and "cost" not in headers:
                    obj["cost_usd"] = None
            query_dist[new_q] += 1
            dst.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")

    # --- manifest ---
    reported = original_manifest.get("reported_cost_usd")
    # Unknown → null (never leave coerced 0.0)
    if reported == 0.0 or reported == 0:
        reported_cost: float | None = None
    else:
        reported_cost = reported

    derived_manifest = {
        "schema_version": "m5-smoke-manifest/v1+erratum-001",
        "erratum": ERRATUM_ID,
        "derived_from_run_id": original_manifest.get("run_id"),
        "original_manifest_sha256": before.get("manifest.json"),
        "original_coverage_sha256": before.get("coverage.csv"),
        "original_queries_sha256": before.get("queries.jsonl"),
        "regenerated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_revision": code_revision,
        "run_id": original_manifest.get("run_id"),
        "run_type": original_manifest.get("run_type"),
        "status": original_manifest.get("status"),
        "started_at": original_manifest.get("started_at"),
        "ended_at": original_manifest.get("ended_at"),
        "smoke_vocabulary_version": original_manifest.get("smoke_vocabulary_version"),
        "source": original_manifest.get("source"),
        "phase": original_manifest.get("phase"),
        "execution_mode": original_manifest.get("execution_mode"),
        "http_attempts_used": original_manifest.get("http_attempts_used"),
        "reported_cost_usd": reported_cost,
        "cost_ceiling_usd": original_manifest.get("cost_ceiling_usd"),
        "stop_reason": original_manifest.get("stop_reason"),
        "coverage_rows": len(corrected_rows),
        "quality_state_distribution": dict(quality_dist),
        "query_quality_state_distribution": dict(query_dist),
        "original_reported_cost_usd": original_manifest.get("reported_cost_usd"),
        "rf_recommendation": original_manifest.get("rf_recommendation"),
        "notes": (
            "Derived Erratum-001 evidence. Original Raw/query/HTTP artifacts "
            "were not refetched or overwritten."
        ),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(derived_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    after = _file_inventory(run_dir)
    if after != before:
        changed = sorted(set(before) | set(after))
        diffs = [p for p in changed if before.get(p) != after.get(p)]
        raise RuntimeError(
            f"immutable original evidence changed during regeneration: {diffs}"
        )

    report = {
        "erratum": ERRATUM_ID,
        "run_id": original_manifest.get("run_id"),
        "derived_dir": str(out_dir),
        "quality_state_distribution": dict(quality_dist),
        "query_quality_state_distribution": dict(query_dist),
        "reported_cost_usd": reported_cost,
        "original_file_count": len(before),
        "original_integrity_ok": True,
        "original_hashes": {
            "manifest.json": before.get("manifest.json"),
            "coverage.csv": before.get("coverage.csv"),
            "queries.jsonl": before.get("queries.jsonl"),
        },
    }
    (out_dir / "regeneration.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Path to runs/<run_id> containing original evidence",
    )
    parser.add_argument("--code-revision", default=None)
    args = parser.parse_args()
    rev = args.code_revision
    if rev is None:
        try:
            rev = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                text=True,
                cwd=str(Path(__file__).resolve().parents[4]),
            ).strip()
        except Exception:  # noqa: BLE001
            rev = None
    report = regenerate_erratum001(args.run_dir, code_revision=rev)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
