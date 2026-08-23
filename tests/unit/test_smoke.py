"""Local smoke execution with external integrations disabled."""

from __future__ import annotations

import json
from pathlib import Path

from thought_flow.cli import run_smoke
from thought_flow.observability.manifest import RunManifest


def test_local_smoke_succeeds_with_integrations_disabled(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "workspace-data"
    monkeypatch.setenv("THOUGHT_FLOW_DATA_ROOT", str(data_root))
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_SHAREPOINT", "false")
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_BIGQUERY", "false")
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_AZURE", "false")

    sample = Path(__file__).resolve().parents[2] / "data" / "samples" / "m1_synthetic_raw.json"
    assert run_smoke(sample_path=sample) == 0

    manifests = list((data_root / "manifests").glob("*.json"))
    assert len(manifests) == 1
    payload = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert payload["status"] == "succeeded"
    assert payload["run_type"] == "smoke"
    assert payload["duckdb_row_count"] == 1
    assert Path(payload["raw_artifact_path"]).exists()

    # Second run: different run/manifest identity, same record/content identity, no overwrite.
    assert run_smoke(sample_path=sample) == 0
    loaded = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (data_root / "manifests").glob("*.json")
    ]
    assert len(loaded) == 2
    by_new = {item["content_was_new"]: item for item in loaded}
    assert set(by_new) == {True, False}
    first = by_new[True]
    second = by_new[False]
    assert first["run_identity"] != second["run_identity"]
    assert first["record_identity"] == second["record_identity"]
    assert first["raw_content_identity"] == second["raw_content_identity"]
    assert Path(first["raw_artifact_path"]).exists()
    assert Path(second["raw_artifact_path"]).exists()
    assert first["raw_artifact_path"] != second["raw_artifact_path"]


def test_manifest_schema_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    manifest = RunManifest(
        run_identity="run-test",
        run_type="smoke",
        status="started",
        started_at="2026-08-23T00:00:00Z",
    )
    manifest.mark_succeeded(record_identity="rec_x", raw_content_identity="raw_y")
    manifest.write(path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["status"] == "succeeded"
    assert loaded["record_identity"] == "rec_x"
