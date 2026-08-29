"""Post-download Google Trends official CSV validation and local import.

Cursor never drives the Trends UI. Human downloads CSV; this module imports.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from thought_flow.smoke.artifacts import utc_now, write_json
from thought_flow.smoke.periods import TRENDS_FULL, TRENDS_COUNTRIES
from thought_flow.smoke.quality import QUALITY_STATES
from thought_flow.smoke.trends.probes import (
    ZERO_SEMANTICS_TRENDS,
    paired_probes,
    probe_for,
)

_SECRET_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "token",
        "password",
        "secret",
        "credential",
        "cookie",
    }
)


@dataclass
class TrendsSeriesPoint:
    week_start: str
    value: int | None
    quality_state: str
    zero_semantics: str | None = None


@dataclass
class ParsedTrendsCsv:
    country: str
    generative_ai_label: str
    ai_agent_label: str
    points_generative_ai: list[TrendsSeriesPoint]
    points_ai_agent: list[TrendsSeriesPoint]
    row_count: int
    first_week: str | None
    last_week: str | None
    missing_week_count: int
    warnings: list[str]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def redact_secrets(obj: Any) -> Any:
    """Ensure secrets never enter persisted public-safe metadata."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k).lower().replace("-", "_") in _SECRET_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(x) for x in obj]
    if isinstance(obj, str) and len(obj) > 8:
        lower = obj.lower()
        if any(s in lower for s in ("bearer ", "ya29.", "sk-", "api_key=")):
            return "[REDACTED]"
    return obj


def _parse_week_cell(raw: str) -> date | None:
    text = raw.strip()
    if not text:
        return None
    # Official exports use YYYY-MM-DD week starts.
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _interest_section(text: str) -> str:
    # Official multi-section CSV: find "Interest over time" block.
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "interest over time":
            start = i + 1
            break
    if start is None:
        # Some exports are already a single table.
        return text
    body: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            if body:
                break
            continue
        # Next section titles are typically title-case without commas as header-only.
        if "," not in line and body:
            break
        body.append(line)
    return "\n".join(body)


def _classify_value(raw: str) -> TrendsSeriesPoint:
    cell = raw.strip()
    if cell == "" or cell.upper() == "N/A" or cell == "<1":
        # Trends may emit blank / <1; treat blank as missing, <1 as low interest zero-ish.
        if cell == "<1":
            return TrendsSeriesPoint(
                week_start="",
                value=0,
                quality_state="zero",
                zero_semantics=ZERO_SEMANTICS_TRENDS,
            )
        return TrendsSeriesPoint(
            week_start="", value=None, quality_state="missing", zero_semantics=None
        )
    try:
        value = int(float(cell))
    except ValueError:
        return TrendsSeriesPoint(
            week_start="", value=None, quality_state="fetch_failure", zero_semantics=None
        )
    if value == 0:
        return TrendsSeriesPoint(
            week_start="",
            value=0,
            quality_state="zero",
            zero_semantics=ZERO_SEMANTICS_TRENDS,
        )
    if value < 0:
        return TrendsSeriesPoint(
            week_start="", value=None, quality_state="unknown", zero_semantics=None
        )
    return TrendsSeriesPoint(
        week_start="", value=value, quality_state="success", zero_semantics=None
    )


def parse_official_trends_csv(*, text: str, country: str) -> ParsedTrendsCsv:
    if country not in TRENDS_COUNTRIES:
        raise ValueError(f"Unsupported country: {country!r}")
    expected_gen, expected_agent = paired_probes(country)
    section = _interest_section(text)
    if not section.strip():
        raise ValueError("malformed_trends_csv: empty Interest over time section")

    reader = csv.reader(io.StringIO(section))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("malformed_trends_csv: no data rows")

    header = [c.strip() for c in rows[0]]
    if len(header) < 3:
        raise ValueError("malformed_trends_csv: expected Week + two series columns")

    # Column 0 is Week / Time; remaining are series labels.
    labels = header[1:]
    warnings: list[str] = []
    # Match labels case-insensitively / whitespace-normalized.
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().casefold())

    gen_idx = next((i for i, lab in enumerate(labels) if norm(lab) == norm(expected_gen)), None)
    agent_idx = next(
        (i for i, lab in enumerate(labels) if norm(lab) == norm(expected_agent)), None
    )
    if gen_idx is None or agent_idx is None:
        raise ValueError(
            "malformed_trends_csv: series labels do not match frozen probes "
            f"for {country}: expected {expected_gen!r} and {expected_agent!r}, got {labels!r}"
        )
    if gen_idx == agent_idx:
        raise ValueError("malformed_trends_csv: duplicate series columns")

    gen_points: list[TrendsSeriesPoint] = []
    agent_points: list[TrendsSeriesPoint] = []
    weeks: list[date] = []

    for row in rows[1:]:
        if len(row) < 3:
            warnings.append("short_row_skipped")
            continue
        week = _parse_week_cell(row[0])
        if week is None:
            warnings.append(f"unparseable_week:{row[0]!r}")
            continue
        weeks.append(week)
        g = _classify_value(row[1 + gen_idx])
        a = _classify_value(row[1 + agent_idx])
        g.week_start = week.isoformat()
        a.week_start = week.isoformat()
        # Re-assert quality states remain in frozen set.
        assert g.quality_state in QUALITY_STATES
        assert a.quality_state in QUALITY_STATES
        gen_points.append(g)
        agent_points.append(a)

    if not weeks:
        raise ValueError("malformed_trends_csv: no parseable weeks")

    first_week = min(weeks).isoformat()
    last_week = max(weeks).isoformat()
    # Expected coverage includes TRENDS-FULL start; week labels may precede inclusive start.
    if date.fromisoformat(last_week) < TRENDS_FULL.inclusive_start:
        raise ValueError("malformed_trends_csv: series ends before TRENDS-FULL start")

    missing = 0
    for p in gen_points + agent_points:
        if p.quality_state == "missing":
            missing += 1

    return ParsedTrendsCsv(
        country=country,
        generative_ai_label=expected_gen,
        ai_agent_label=expected_agent,
        points_generative_ai=gen_points,
        points_ai_agent=agent_points,
        row_count=len(gen_points),
        first_week=first_week,
        last_week=last_week,
        missing_week_count=missing,
        warnings=warnings,
    )


def suggested_filename(country: str, observation_index: int) -> str:
    return (
        f"trends-ui_{country}_TRENDS-FULL_obs{observation_index:02d}_"
        f"{TRENDS_FULL.inclusive_start.isoformat()}_"
        f"{TRENDS_FULL.inclusive_end.isoformat()}.csv"
    )


def import_human_csv(
    *,
    csv_path: Path,
    country: str,
    data_root: Path,
    code_revision: str,
    observation_index: int,
    human_export_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate + import one Human-exported official CSV into an append-only run."""
    if country not in TRENDS_COUNTRIES:
        raise ValueError(f"Unsupported country: {country!r}")
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    text = csv_path.read_text(encoding="utf-8-sig")
    parsed = parse_official_trends_csv(text=text, country=country)
    file_hash = sha256_file(csv_path)

    run_id = str(uuid.uuid4())
    run_dir = data_root / "m5-smoke" / "runs" / run_id
    if run_dir.exists():
        raise RuntimeError("run_id collision; refuse overwrite")
    raw_dir = run_dir / "raw" / "google_trends"
    raw_dir.mkdir(parents=True, exist_ok=False)

    # Store a local copy under unique run (gitignored workspace); never overwrite.
    dest_name = suggested_filename(country, observation_index)
    dest = raw_dir / dest_name
    dest.write_bytes(csv_path.read_bytes())

    sidecar = redact_secrets(
        {
            "schema_version": "m5-trends-csv-sidecar/v1",
            "source": "google_trends_ui_csv",
            "acquisition_mode": "human_official_csv_download",
            "ui_automation": False,
            "undocumented_endpoint_used": False,
            "country": country,
            "period": TRENDS_FULL.to_manifest(),
            "observation_index": observation_index,
            "probes": {
                "generative_ai": probe_for(country, "generative_ai"),
                "ai_agent": probe_for(country, "ai_agent"),
            },
            "shared_scale": "within_request_0_100",
            "cross_country_level_comparable": False,
            "original_filename": csv_path.name,
            "stored_filename": dest_name,
            "file_sha256": file_hash,
            "row_count": parsed.row_count,
            "first_week": parsed.first_week,
            "last_week": parsed.last_week,
            "missing_week_count": parsed.missing_week_count,
            "warnings": parsed.warnings,
            "zero_semantics": ZERO_SEMANTICS_TRENDS,
            "human_export_meta": human_export_meta or {},
            "observed_at": utc_now(),
            "code_revision": code_revision,
            "run_id": run_id,
        }
    )
    write_json(raw_dir / f"{dest_name}.sidecar.json", sidecar)

    # Extracted weekly points (local only).
    extracted_path = run_dir / "extracted" / "google_trends.jsonl"
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    with extracted_path.open("w", encoding="utf-8") as fh:
        for theme, points in (
            ("generative_ai", parsed.points_generative_ai),
            ("ai_agent", parsed.points_ai_agent),
        ):
            for p in points:
                fh.write(
                    json.dumps(
                        {
                            "run_id": run_id,
                            "country": country,
                            "theme": theme,
                            "week_start": p.week_start,
                            "value": p.value,
                            "quality_state": p.quality_state,
                            "zero_semantics": p.zero_semantics,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )

    coverage_rows = []
    for theme, points in (
        ("generative_ai", parsed.points_generative_ai),
        ("ai_agent", parsed.points_ai_agent),
    ):
        zeros = sum(1 for p in points if p.quality_state == "zero")
        missing = sum(1 for p in points if p.quality_state == "missing")
        failures = sum(1 for p in points if p.quality_state == "fetch_failure")
        successes = sum(1 for p in points if p.quality_state == "success")
        if failures and not successes and not zeros:
            qstate = "fetch_failure"
        elif not points:
            qstate = "missing"
        else:
            qstate = "success"
        coverage_rows.append(
            {
                "cell_kind": "trends_country_theme",
                "country": country,
                "theme": theme,
                "period_id": TRENDS_FULL.period_id,
                "quality_state": qstate,
                "week_points": len(points),
                "success_points": successes,
                "zero_points": zeros,
                "missing_points": missing,
                "fetch_failure_points": failures,
                "zero_semantics": ZERO_SEMANTICS_TRENDS,
                "shared_scale": "within_request_0_100",
                "observation_index": observation_index,
            }
        )

    write_json(
        run_dir / "coverage.json",
        {"schema_version": "m5-trends-coverage/v1", "rows": coverage_rows},
    )

    manifest = redact_secrets(
        {
            "schema_version": "m5-smoke-manifest/v1",
            "run_id": run_id,
            "run_type": "m5_smoke",
            "source": "google_trends",
            "phase": "trends_ui_csv_import",
            "status": "succeeded",
            "started_at": utc_now(),
            "ended_at": utc_now(),
            "code_revision": code_revision,
            "execution_mode": "human_csv_import",
            "country": country,
            "observation_index": observation_index,
            "period": TRENDS_FULL.to_manifest(),
            "file_sha256": file_hash,
            "coverage_rows": len(coverage_rows),
            "repeat_observation_complete": False,
            "second_observation_pending": observation_index < 2,
            "alpha_route_used": False,
            "ui_automation": False,
            "production_connector": False,
            "artifact_root": str(run_dir),
            "rf_recommendation": "not_evaluated_trends_import_only",
        }
    )
    write_json(run_dir / "manifest.json", manifest)
    return manifest
