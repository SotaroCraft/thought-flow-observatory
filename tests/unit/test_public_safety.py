"""Public-safety checks over git-tracked files and .env.example emptiness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_SCRIPT = REPO_ROOT / "scripts" / "public_safety_scan.py"


def _git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    if not result.stdout:
        return []
    return [p.decode("utf-8", errors="replace") for p in result.stdout.split(b"\0") if p]


def test_env_example_assignments_are_empty() -> None:
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "=" in stripped, f"Expected KEY= form, got {stripped!r}"
        _, _, value = stripped.partition("=")
        assert value == "", f"Non-empty .env.example assignment: {stripped!r}"


def test_tracked_inventory_comes_from_git_ls_files() -> None:
    tracked = _git_ls_files()
    assert tracked, "expected tracked files via git ls-files"
    assert ".env.example" in tracked
    assert "data/samples/m1_synthetic_raw.json" in tracked
    # Must not be a hand-curated 3-file list.
    assert len(tracked) >= 10


def test_public_safety_scan_tracked_and_history_clean() -> None:
    assert SCAN_SCRIPT.is_file()
    result = subprocess.run(
        [sys.executable, str(SCAN_SCRIPT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT=CLEAN" in result.stdout
    assert "tracked_files=" in result.stdout
    assert "reachable_commits=" in result.stdout


def test_config_defaults_when_env_flags_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_SHAREPOINT", "")
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_BIGQUERY", "")
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_AZURE", "")
    from thought_flow.config import load_settings

    settings = load_settings(dotenv_path=Path("/nonexistent/.env"))
    assert settings.external_integrations_enabled() is False
