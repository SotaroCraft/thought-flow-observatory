"""CodeX review corrections: dual gates, provenance, Transport B fixture E2E."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_flow.smoke.trends.live_gates import (
    HumanTermsEvidence,
    evaluate_transport_b_live_gates,
)
from thought_flow.smoke.trends.pipeline import acquire_and_import, human_csv_transport
from thought_flow.smoke.trends.provenance import (
    EXPLORE_WIDGET_CSV_PROVENANCE,
    HUMAN_OFFICIAL_CSV_PROVENANCE,
)
from thought_flow.smoke.trends.transport import ExploreWidgetCsvTransport

SAMPLE = Path("data/samples/m5_trends_ui_synthetic_us.csv")


def _terms() -> HumanTermsEvidence:
    return HumanTermsEvidence(
        approved_at="2026-08-29",
        approver="Human",
        applicable_terms="sample-terms-ref",
        automated_access="approved-for-m5-smoke-only",
        storage="local-gitignored-workspace",
        publication="not-authorized-for-public-raw",
    )


def test_dual_gate_both_absent_forbidden() -> None:
    r = evaluate_transport_b_live_gates(
        erratum_002_accepted_on_main=False,
        terms_evidence=None,
    )
    assert r.live_authorized is False
    assert r.smoke_state == "SMOKE-BLOCKED"


def test_dual_gate_erratum_without_terms_forbidden() -> None:
    r = evaluate_transport_b_live_gates(
        erratum_002_accepted_on_main=True,
        terms_evidence=None,
    )
    assert r.live_authorized is False
    assert r.smoke_state == "SMOKE-BLOCKED"
    assert "terms" in r.reason.lower() or "Human" in r.reason


def test_dual_gate_terms_without_erratum_forbidden() -> None:
    r = evaluate_transport_b_live_gates(
        erratum_002_accepted_on_main=False,
        terms_evidence=_terms(),
    )
    assert r.live_authorized is False
    assert r.smoke_state == "SMOKE-BLOCKED"
    assert "Erratum-002" in r.reason


def test_dual_gate_both_present_authorized_but_http_still_unimplemented(
    tmp_path: Path,
) -> None:
    r = evaluate_transport_b_live_gates(
        erratum_002_accepted_on_main=True,
        terms_evidence=_terms(),
    )
    assert r.live_authorized is True
    # Without fixture bytes, acquire still refuses live HTTP.
    from thought_flow.smoke.trends.acquisition_contract import build_acquisition_contract

    with pytest.raises(Exception) as ei:
        ExploreWidgetCsvTransport(
            erratum_002_accepted_on_main=True,
            terms_evidence=_terms(),
        ).acquire_csv(build_acquisition_contract(geo="US", observation_index=1))
    assert "unimplemented" in str(ei.value).lower() or "live" in str(ei.value).lower()


def test_transport_a_provenance(tmp_path: Path) -> None:
    csv_path = tmp_path / "a.csv"
    csv_path.write_bytes(SAMPLE.read_bytes())
    m = acquire_and_import(
        transport=human_csv_transport(csv_path),
        geo="US",
        observation_index=1,
        data_root=tmp_path / "ws",
        code_revision="test",
        staging_dir=tmp_path / "stage-a",
    )
    assert m["transport_id"] == HUMAN_OFFICIAL_CSV_PROVENANCE.transport_id
    assert m["acquisition_mode"] == "human_official_csv_download"
    assert m["undocumented_endpoint_used"] is False
    assert "Human official UI CSV" in m["provenance_description"]
    sidecar = next(Path(m["artifact_root"]).rglob("*.sidecar.json"))
    side = json.loads(sidecar.read_text(encoding="utf-8"))
    assert side["source"] == "google_trends_official_ui_csv"
    assert side["undocumented_endpoint_used"] is False


def test_transport_b_fixture_e2e_provenance_and_exact_bytes(tmp_path: Path) -> None:
    raw = SAMPLE.read_bytes()
    transport = ExploreWidgetCsvTransport(
        erratum_002_accepted_on_main=True,
        terms_evidence=_terms(),
        fixture_csv_bytes=raw,
    )
    m = acquire_and_import(
        transport=transport,
        geo="US",
        observation_index=1,
        data_root=tmp_path / "ws",
        code_revision="test",
        staging_dir=tmp_path / "stage-b",
    )
    assert m["status"] == "succeeded"
    assert m["transport_id"] == EXPLORE_WIDGET_CSV_PROVENANCE.transport_id
    assert m["acquisition_mode"] == "explore_widget_undocumented_endpoint"
    assert m["undocumented_endpoint_used"] is True
    assert "undocumented internal endpoint" in m["provenance_description"]
    sidecar = next(Path(m["artifact_root"]).rglob("*.sidecar.json"))
    side = json.loads(sidecar.read_text(encoding="utf-8"))
    assert side["source"] == "google_trends_explore_widget_csv"
    assert side["undocumented_endpoint_used"] is True
    stored = next(Path(m["artifact_root"]).rglob("*.csv"))
    assert stored.read_bytes() == raw
