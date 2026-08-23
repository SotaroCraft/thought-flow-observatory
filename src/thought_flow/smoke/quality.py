"""Frozen M5 primary quality states (including Erratum-001 `success`)."""

from __future__ import annotations

from typing import Any, Literal

QualityState = Literal[
    "success", "zero", "missing", "unknown", "fetch_failure", "partial"
]

QUALITY_STATES: frozenset[str] = frozenset(
    {"success", "zero", "missing", "unknown", "fetch_failure", "partial"}
)


def require_quality_state(value: str) -> QualityState:
    if value not in QUALITY_STATES:
        raise ValueError(f"Unknown M5 quality state: {value!r}")
    return value  # type: ignore[return-value]


def classify_observation_quality(
    *,
    acquisition_failed: bool = False,
    has_unobserved_remainder: bool = False,
    observation_complete: bool = False,
    qualifying_count: int = 0,
    attribute_absent: bool = False,
    attribute_unresolvable: bool = False,
) -> QualityState:
    """Map observation outcomes to Erratum-001 primary quality states.

    Priority: acquisition failure → attribute missing → attribute unknown →
    partial (bounded remainder) → complete zero → complete nonzero success.
    """
    if acquisition_failed:
        return "fetch_failure"
    if attribute_absent:
        return "missing"
    if attribute_unresolvable:
        return "unknown"
    if has_unobserved_remainder or not observation_complete:
        return "partial"
    if qualifying_count <= 0:
        return "zero"
    return "success"


def page_query_quality_state(
    *,
    status_code: int | None,
    source_total: int | None = None,
    result_count: int | None = None,
    error: Any = None,
) -> QualityState:
    """Quality state for a single HTTP query/page observation."""
    if error or status_code is None or status_code >= 400:
        return "fetch_failure"
    qualifying = source_total if source_total is not None else result_count
    if qualifying is None:
        return "unknown"
    if int(qualifying) <= 0:
        return "zero"
    return "success"


def remap_pre_erratum001_cell_quality(
    *,
    quality_state: str,
    stop_reason: str | None = None,
) -> QualityState:
    """Correct pre-Erratum-001 cell rows that overloaded `missing` as success."""
    stop = stop_reason or ""
    if quality_state == "missing" and stop in {
        "complete_observation",
        "denominator_count_observed",
    }:
        return "success"
    return require_quality_state(quality_state)
