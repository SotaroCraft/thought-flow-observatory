"""Public-safety checks for samples and env templates."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Patterns that must not appear as real secrets / user-specific IDs in tracked samples.
FORBIDDEN_PATTERNS = [
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-z0-9_\-]{16,}"),
    re.compile(r"(?i)secret\s*[:=]\s*['\"]?[a-z0-9_\-]{8,}"),
    re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)client_secret"),
    re.compile(r"(?i)tenant[_-]?id\s*[:=]\s*['\"]?[0-9a-f\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def _tracked_safety_files() -> list[Path]:
    paths = [
        REPO_ROOT / ".env.example",
        REPO_ROOT / "data" / "samples" / "m1_synthetic_raw.json",
        REPO_ROOT / "data" / "README.md",
    ]
    return [p for p in paths if p.exists()]


def test_samples_and_env_example_have_no_real_secrets() -> None:
    findings: list[str] = []
    for path in _tracked_safety_files():
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                findings.append(f"{path.relative_to(REPO_ROOT)}: matched {pattern.pattern}")
    assert findings == [], "Public-safety findings:\n" + "\n".join(findings)


def test_env_example_has_names_only_no_assigned_secrets() -> None:
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        # Allow explicit false defaults for feature flags; forbid opaque secret values.
        assert value in {"", "false", "true"}, f"Unexpected value for {key}: {value!r}"
