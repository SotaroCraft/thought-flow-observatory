"""Frozen Google Trends M5 smoke probes (acquisition mechanics only; not Gate D)."""

from __future__ import annotations

from thought_flow.smoke.periods import TRENDS_COUNTRIES, TRENDS_THEMES

# Country → theme → exact UI/API term probe from m5-smoke-spec §6.1
TRENDS_PROBES: dict[str, dict[str, str]] = {
    "US": {
        "generative_ai": "generative AI",
        "ai_agent": "AI agent",
    },
    "JP": {
        "generative_ai": "生成AI",
        "ai_agent": "AIエージェント",
    },
    "KR": {
        "generative_ai": "생성형 AI",
        "ai_agent": "AI 에이전트",
    },
    "CN": {
        "generative_ai": "生成式人工智能",
        "ai_agent": "AI智能体",
    },
}

ZERO_SEMANTICS_TRENDS = "low_or_insufficient_relative_interest"

TRENDS_CATEGORY = "all"
TRENDS_PROPERTY = "web_search"
TRENDS_MODE = "term"  # never silently substitute Topic


def probe_for(country: str, theme: str) -> str:
    if country not in TRENDS_COUNTRIES:
        raise ValueError(f"Unsupported Trends country: {country!r}")
    if theme not in TRENDS_THEMES:
        raise ValueError(f"Unsupported Trends theme: {theme!r}")
    return TRENDS_PROBES[country][theme]


def paired_probes(country: str) -> tuple[str, str]:
    """Both theme probes for one country comparison request."""
    return (
        probe_for(country, "generative_ai"),
        probe_for(country, "ai_agent"),
    )
