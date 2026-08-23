"""Unit tests for configuration loading."""

from __future__ import annotations

import os
from pathlib import Path

from thought_flow.config import load_settings
from thought_flow.config.settings import REPO_ROOT


def test_config_loads_without_external_credentials(monkeypatch) -> None:
    monkeypatch.delenv("THOUGHT_FLOW_DATA_ROOT", raising=False)
    monkeypatch.delenv("THOUGHT_FLOW_ENABLE_SHAREPOINT", raising=False)
    monkeypatch.delenv("THOUGHT_FLOW_ENABLE_BIGQUERY", raising=False)
    monkeypatch.delenv("THOUGHT_FLOW_ENABLE_AZURE", raising=False)
    # Ensure no accidental credential requirement.
    for key in list(os.environ):
        if any(token in key.upper() for token in ("SECRET", "TOKEN", "PASSWORD", "API_KEY")):
            monkeypatch.delenv(key, raising=False)

    settings = load_settings(dotenv_path=Path("/nonexistent/.env"))
    assert settings.repo_root == REPO_ROOT
    assert settings.data_root == REPO_ROOT / "workspace-data"
    assert settings.samples_dir == REPO_ROOT / "data" / "samples"
    assert settings.enable_sharepoint is False
    assert settings.enable_bigquery is False
    assert settings.enable_azure is False
    assert settings.external_integrations_enabled() is False


def test_config_respects_data_root_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_DATA_ROOT", str(tmp_path / "local-data"))
    settings = load_settings(dotenv_path=Path("/nonexistent/.env"))
    assert settings.data_root == tmp_path / "local-data"
    assert settings.raw_dir == tmp_path / "local-data" / "raw"
