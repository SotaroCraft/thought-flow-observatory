"""Converge any authorized Trends CSV transport onto the PR #7 import boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thought_flow.smoke.trends.acquisition_contract import (
    TrendsAcquisitionContract,
    assert_contract_matches_tfo_sot,
    build_acquisition_contract,
)
from thought_flow.smoke.trends.csv_import import import_human_csv
from thought_flow.smoke.trends.transport import (
    ExploreWidgetCsvTransport,
    HumanOfficialCsvTransport,
    TrendsCsvTransport,
    TrendsTransportError,
    TransportCsvResult,
)


def acquire_and_import(
    *,
    transport: TrendsCsvTransport,
    geo: str,
    observation_index: int,
    data_root: Path,
    code_revision: str,
    staging_dir: Path | None = None,
) -> dict[str, Any]:
    """Run Layer B then PR #7 CSV validate/import. Failed GEO must not overwrite priors."""
    contract = build_acquisition_contract(geo=geo, observation_index=observation_index)
    assert_contract_matches_tfo_sot(contract)
    try:
        result = transport.acquire_csv(contract)
    except TrendsTransportError as exc:
        return {
            "status": "fetch_failure",
            "quality_state": "fetch_failure",
            "transport_error_code": exc.code,
            "failure_message": str(exc)[:500],
            "geo": contract.geo,
            "observation_index": observation_index,
            "zero_coerced": False,
            "transport_id": getattr(transport, "transport_id", "unknown"),
        }

    return _import_exact_bytes(
        result=result,
        data_root=data_root,
        code_revision=code_revision,
        staging_dir=staging_dir,
    )


def _import_exact_bytes(
    *,
    result: TransportCsvResult,
    data_root: Path,
    code_revision: str,
    staging_dir: Path | None,
) -> dict[str, Any]:
    stage = staging_dir or (data_root / "m5-smoke" / "_staging")
    stage.mkdir(parents=True, exist_ok=True)
    # Unique staging file per contract; never overwrite another GEO's success artifact.
    staged = stage / (
        f"{result.contract.obs_id}__{result.transport_id}__obs"
        f"{result.contract.observation_index:02d}.csv"
    )
    if staged.exists():
        raise RuntimeError(f"refuse overwrite of staged CSV: {staged.name}")
    staged.write_bytes(result.csv_bytes)  # exact bytes, no numeric transform

    manifest = import_human_csv(
        csv_path=staged,
        country=result.contract.geo,
        data_root=data_root,
        code_revision=code_revision,
        observation_index=result.contract.observation_index,
        human_export_meta={
            "transport_id": result.transport_id,
            "obs_id": result.contract.obs_id,
            "transport_public_meta": result.public_meta,
            "byte_preservation": "exact_source_csv_bytes",
        },
    )
    manifest["transport_id"] = result.transport_id
    manifest["obs_id"] = result.contract.obs_id
    return manifest


def human_csv_transport(csv_path: Path) -> HumanOfficialCsvTransport:
    return HumanOfficialCsvTransport(csv_path=csv_path)


def explore_widget_transport() -> ExploreWidgetCsvTransport:
    return ExploreWidgetCsvTransport()
