"""Gate E country helpers — structured evidence only; inclusion counting (TBD-008)."""

from __future__ import annotations

from collections.abc import Iterable

TARGET_COUNTRIES: frozenset[str] = frozenset({"JP", "US", "KR", "CN"})


def _normalize_code(code: str | None) -> str | None:
    """Normalize an already-structured country code. No name/language/LLM inference."""
    if code is None:
        return None
    value = str(code).strip().upper()
    if not value:
        return None
    return value


def structured_country_codes(codes: Iterable[str | None]) -> frozenset[str]:
    """
    Distinct structured country codes present on the Work (any country).

    `unknown` is defined over this set: empty ⇒ unknown.
    Non-target codes (e.g. DE) remain structured evidence and are NOT unknown.
    """
    out: set[str] = set()
    for raw in codes:
        code = _normalize_code(raw)
        if code is None:
            continue
        out.add(code)
    return frozenset(out)


def structured_target_countries(codes: Iterable[str | None]) -> frozenset[str]:
    """Distinct target-country codes (JP/US/KR/CN) present in structured evidence."""
    return frozenset(c for c in structured_country_codes(codes) if c in TARGET_COUNTRIES)


def is_unknown_country(codes: Iterable[str | None]) -> bool:
    """True when no structured country code is present at all (unknown ≠ zero)."""
    return len(structured_country_codes(codes)) == 0


def is_multi_country(codes: Iterable[str | None]) -> bool:
    """Multi-country among target countries (inclusion-counting scope)."""
    return len(structured_target_countries(codes)) >= 2


def inclusion_country_hits(codes: Iterable[str | None]) -> frozenset[str]:
    """
    Inclusion counting (TBD-008): count once in each distinct target country.

    Denominator construction for a country C must use the same predicate:
    Work has structured evidence for C (theme filter MUST NOT apply to denominator).
    """
    return structured_target_countries(codes)


def work_counts_in_country(codes: Iterable[str | None], country: str) -> bool:
    target = _normalize_code(country)
    if target is None or target not in TARGET_COUNTRIES:
        raise ValueError(f"country must be one of {sorted(TARGET_COUNTRIES)}, got {country!r}")
    return target in inclusion_country_hits(codes)


def matched_share(*, matched_works: int, denominator_works: int) -> float | None:
    """Primary Gate A derived measure. None when denominator is zero (do not fabricate)."""
    if denominator_works < 0 or matched_works < 0:
        raise ValueError("counts must be non-negative")
    if matched_works > denominator_works:
        raise ValueError("matched_works cannot exceed denominator_works under compatible filters")
    if denominator_works == 0:
        return None
    return matched_works / denominator_works


def assert_denominator_query_theme_independent(query_params: dict[str, object]) -> None:
    """
    Guard for Gate A: denominator requests must not carry theme phrase filters.

    Accepts a sanitized param dict (as would be logged for OpenAlex). Raises if a
    theme/search phrase key is present for a denominator-classified query.
    """
    kind = str(query_params.get("query_kind", "")).lower()
    if kind not in {"denominator", "country_period_denominator", "country_week_denominator"}:
        raise ValueError(f"not a denominator query_kind: {kind!r}")
    forbidden_keys = {"search", "theme", "theme_phrase", "provisional_phrase", "dictionary_phrase"}
    present = forbidden_keys.intersection(query_params)
    if present:
        raise ValueError(f"denominator must not include theme filters: {sorted(present)}")
    search_val = query_params.get("filter_search") or query_params.get("q")
    if search_val not in (None, "", []):
        raise ValueError("denominator must not include search/theme phrase values")
