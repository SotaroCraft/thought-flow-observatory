"""M5 smoke local artifact layout under workspace-data/m5-smoke/."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class M5RunPaths:
    run_dir: Path
    manifest_path: Path
    queries_path: Path
    raw_openalex_dir: Path
    extracted_openalex_path: Path
    coverage_path: Path
    privacy_licensing_path: Path

    @classmethod
    def create(cls, root: Path, run_id: str) -> M5RunPaths:
        run_dir = root / "runs" / run_id
        raw_dir = run_dir / "raw" / "openalex"
        extracted_dir = run_dir / "extracted"
        raw_dir.mkdir(parents=True, exist_ok=True)
        extracted_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            run_dir=run_dir,
            manifest_path=run_dir / "manifest.json",
            queries_path=run_dir / "queries.jsonl",
            raw_openalex_dir=raw_dir,
            extracted_openalex_path=extracted_dir / "openalex.jsonl",
            coverage_path=run_dir / "coverage.csv",
            privacy_licensing_path=run_dir / "privacy-licensing.json",
        )


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_coverage_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    fieldnames = [
        "cell_kind",
        "country",
        "theme",
        "period_id",
        "quality_state",
        "source_total",
        "inspected_count",
        "retained_count",
        "matched_count",
        "missing_country_count",
        "multi_country_count",
        "unknown_country_count",
        "title_only_match_count",
        "title_plus_abstract_match_count",
        "abstract_present_count",
        "pages_used",
        "truncation",
        "observation_complete",
        "stop_reason",
        "phrase_source_counts",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in fieldnames}
            if isinstance(out.get("phrase_source_counts"), dict):
                out["phrase_source_counts"] = json.dumps(
                    out["phrase_source_counts"], ensure_ascii=False, sort_keys=True
                )
            writer.writerow(out)
