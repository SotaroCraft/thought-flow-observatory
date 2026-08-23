"""Erratum-001 quality-state and evidence-regeneration tests."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from thought_flow.smoke.openalex.regenerate_erratum001 import regenerate_erratum001
from thought_flow.smoke.quality import (
    classify_observation_quality,
    page_query_quality_state,
    remap_pre_erratum001_cell_quality,
)


def test_complete_nonzero_maps_to_success() -> None:
    assert (
        classify_observation_quality(
            observation_complete=True, qualifying_count=3
        )
        == "success"
    )


def test_complete_zero_maps_to_zero() -> None:
    assert (
        classify_observation_quality(
            observation_complete=True, qualifying_count=0
        )
        == "zero"
    )


def test_bounded_incomplete_maps_to_partial() -> None:
    assert (
        classify_observation_quality(
            has_unobserved_remainder=True, qualifying_count=5
        )
        == "partial"
    )


def test_missing_attribute_maps_to_missing() -> None:
    assert (
        classify_observation_quality(
            observation_complete=True,
            qualifying_count=1,
            attribute_absent=True,
        )
        == "missing"
    )


def test_unknown_attribute_maps_to_unknown() -> None:
    assert (
        classify_observation_quality(
            observation_complete=True,
            qualifying_count=1,
            attribute_unresolvable=True,
        )
        == "unknown"
    )


def test_fetch_failure_maps_to_fetch_failure() -> None:
    assert classify_observation_quality(acquisition_failed=True) == "fetch_failure"


def test_missing_is_not_generic_success() -> None:
    assert remap_pre_erratum001_cell_quality(
        quality_state="missing", stop_reason="complete_observation"
    ) == "success"
    assert remap_pre_erratum001_cell_quality(
        quality_state="missing", stop_reason="denominator_count_observed"
    ) == "success"
    # True attribute-level missing stays missing.
    assert (
        remap_pre_erratum001_cell_quality(
            quality_state="missing", stop_reason="attribute_absent"
        )
        == "missing"
    )


def test_page_query_quality_states() -> None:
    assert page_query_quality_state(status_code=200, source_total=12) == "success"
    assert page_query_quality_state(status_code=200, source_total=0) == "zero"
    assert page_query_quality_state(status_code=429, source_total=None) == "fetch_failure"
    assert page_query_quality_state(status_code=200, source_total=None) == "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_regeneration_corrects_quality_and_preserves_raw(tmp_path: Path) -> None:
    run_dir = tmp_path / "3422ccef-fake"
    raw_dir = run_dir / "raw" / "openalex"
    raw_dir.mkdir(parents=True)
    raw_file = raw_dir / "raw_abc.privacy-reduced.jsonl"
    raw_payload = {"run_id": "3422ccef-fake", "envelope": {"id": "W1"}}
    raw_file.write_text(json.dumps(raw_payload) + "\n", encoding="utf-8")
    raw_hash_before = _sha256(raw_file)

    coverage_path = run_dir / "coverage.csv"
    with coverage_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "cell_kind",
                "quality_state",
                "stop_reason",
                "matched_count",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "cell_kind": "country_theme",
                "quality_state": "missing",
                "stop_reason": "complete_observation",
                "matched_count": "3",
            }
        )
        writer.writerow(
            {
                "cell_kind": "country_theme",
                "quality_state": "zero",
                "stop_reason": "",
                "matched_count": "0",
            }
        )
        writer.writerow(
            {
                "cell_kind": "country_theme",
                "quality_state": "partial",
                "stop_reason": "bounded_ceiling",
                "matched_count": "1",
            }
        )
        writer.writerow(
            {
                "cell_kind": "country_period_denominator",
                "quality_state": "missing",
                "stop_reason": "denominator_count_observed",
                "matched_count": "",
            }
        )

    queries_path = run_dir / "queries.jsonl"
    queries_path.write_text(
        json.dumps(
            {
                "http_status": 200,
                "source_total": 5,
                "quality_state": "zero",
                "cost_usd": None,
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "3422ccef-fake",
                "run_type": "m5_smoke",
                "status": "succeeded",
                "reported_cost_usd": 0.0,
                "http_attempts_used": 1,
            }
        ),
        encoding="utf-8",
    )

    cov_hash_before = _sha256(coverage_path)
    man_hash_before = _sha256(manifest_path)
    q_hash_before = _sha256(queries_path)

    report = regenerate_erratum001(run_dir, code_revision="test")

    assert report["original_integrity_ok"] is True
    assert report["reported_cost_usd"] is None
    assert report["quality_state_distribution"] == {
        "success": 2,
        "zero": 1,
        "partial": 1,
    }

    derived = run_dir / "derived" / "erratum-001"
    assert (derived / "coverage.csv").is_file()
    assert (derived / "manifest.json").is_file()
    derived_manifest = json.loads((derived / "manifest.json").read_text(encoding="utf-8"))
    assert derived_manifest["reported_cost_usd"] is None
    assert derived_manifest["reported_cost_usd"] != 0.0
    assert derived_manifest["original_reported_cost_usd"] == 0.0

    # Original immutable evidence unchanged.
    assert _sha256(raw_file) == raw_hash_before
    assert _sha256(coverage_path) == cov_hash_before
    assert _sha256(manifest_path) == man_hash_before
    assert _sha256(queries_path) == q_hash_before
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["reported_cost_usd"] == 0.0
