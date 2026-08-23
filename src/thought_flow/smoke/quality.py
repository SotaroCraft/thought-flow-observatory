"""Frozen M5 primary quality states."""

from __future__ import annotations

from typing import Literal

QualityState = Literal["zero", "missing", "unknown", "fetch_failure", "partial"]

QUALITY_STATES: frozenset[str] = frozenset(
    {"zero", "missing", "unknown", "fetch_failure", "partial"}
)


def require_quality_state(value: str) -> QualityState:
    if value not in QUALITY_STATES:
        raise ValueError(f"Unknown M5 quality state: {value!r}")
    return value  # type: ignore[return-value]
