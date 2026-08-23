"""Configuration loading with a hard boundary between public paths and secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Repo root: src/thought_flow/config/settings.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = REPO_ROOT / "workspace-data"
DEFAULT_SAMPLES_DIR = REPO_ROOT / "data" / "samples"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(raw: str | None, default: Path) -> Path:
    if raw is None or raw.strip() == "":
        return default
    path = Path(raw.strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


@dataclass(frozen=True)
class Settings:
    """Local-run settings. External integrations stay off unless explicitly enabled."""

    repo_root: Path
    data_root: Path
    samples_dir: Path
    enable_sharepoint: bool
    enable_bigquery: bool
    enable_azure: bool

    @property
    def raw_dir(self) -> Path:
        return self.data_root / "raw"

    @property
    def canonical_dir(self) -> Path:
        return self.data_root / "canonical"

    @property
    def results_dir(self) -> Path:
        return self.data_root / "results"

    @property
    def manifests_dir(self) -> Path:
        return self.data_root / "manifests"

    @property
    def duckdb_path(self) -> Path:
        return self.data_root / "catalog.duckdb"

    def ensure_directories(self) -> None:
        for path in (
            self.raw_dir,
            self.canonical_dir,
            self.results_dir,
            self.manifests_dir,
            self.samples_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def external_integrations_enabled(self) -> bool:
        return self.enable_sharepoint or self.enable_bigquery or self.enable_azure


def load_settings(*, dotenv_path: Path | None = None) -> Settings:
    """Load settings from environment. Missing credentials must not block local runs."""
    env_file = dotenv_path if dotenv_path is not None else REPO_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

    return Settings(
        repo_root=REPO_ROOT,
        data_root=_resolve_path(os.getenv("THOUGHT_FLOW_DATA_ROOT"), DEFAULT_DATA_ROOT),
        samples_dir=_resolve_path(os.getenv("THOUGHT_FLOW_SAMPLES_DIR"), DEFAULT_SAMPLES_DIR),
        enable_sharepoint=_as_bool(os.getenv("THOUGHT_FLOW_ENABLE_SHAREPOINT"), False),
        enable_bigquery=_as_bool(os.getenv("THOUGHT_FLOW_ENABLE_BIGQUERY"), False),
        enable_azure=_as_bool(os.getenv("THOUGHT_FLOW_ENABLE_AZURE"), False),
    )
