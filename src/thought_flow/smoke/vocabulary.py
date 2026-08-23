"""PROVISIONAL-M5-SMOKE vocabulary loading and deterministic matching."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thought_flow.config.settings import REPO_ROOT

SMOKE_VOCABULARY_VERSION = "PROVISIONAL-M5-SMOKE/2026-08-23-r1"
DEFAULT_VOCAB_PATH = (
    REPO_ROOT / "config" / "smoke" / "provisional_m5_smoke_2026_08_23_r1.json"
)

_HYPHEN_CLASS = re.compile(r"[\u002D\u2010\u2011\u2012\u2013\u2014\u2212\uFE58\uFE63\uFF0D]")
_WS = re.compile(r"\s+")

# Standalone Latin "agent" / "agents" must never qualify alone (any case).
_STANDALONE_AGENT = re.compile(r"(?<![a-z0-9])agents?(?![a-z0-9])", re.IGNORECASE)


@dataclass(frozen=True)
class MatchEvidence:
    provisional_match: bool
    matched_term: str | None
    matched_field: str | None
    match_language: str | None
    status: str  # positive | ambiguous | excluded | none
    ambiguous_hits: tuple[str, ...]
    exclusion_hits: tuple[str, ...]
    smoke_vocabulary_version: str


def normalize_for_match(text: str) -> str:
    """NFKC, Latin case-fold, whitespace normalize, ASCII hyphen variants -> spaces."""
    if not text:
        return ""
    value = unicodedata.normalize("NFKC", text)
    value = value.casefold()
    value = _HYPHEN_CLASS.sub(" ", value)
    value = _WS.sub(" ", value).strip()
    return value


def _contains_phrase(haystack_norm: str, phrase: str) -> bool:
    needle = normalize_for_match(phrase)
    if not needle:
        return False
    # Prefer word-ish boundaries for short Latin tokens; CJK phrases use substring.
    if re.fullmatch(r"[a-z0-9 ]+", needle):
        pattern = r"(?<![a-z0-9])" + re.escape(needle).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        return re.search(pattern, haystack_norm) is not None
    return needle in haystack_norm


def load_provisional_vocabulary(path: Path | None = None) -> dict[str, Any]:
    vocab_path = path or DEFAULT_VOCAB_PATH
    data = json.loads(vocab_path.read_text(encoding="utf-8"))
    if data.get("version") != SMOKE_VOCABULARY_VERSION:
        raise ValueError(
            f"Vocabulary version mismatch: file={data.get('version')!r} "
            f"expected={SMOKE_VOCABULARY_VERSION!r}"
        )
    return data


def positive_phrases_for_country(
    vocab: dict[str, Any],
    *,
    theme: str,
    country: str | None,
    global_audit: bool = False,
) -> list[tuple[str, str]]:
    """
    Deterministic phrase queue: (language_row, phrase).

    Country cell: target-country language then English (US: English only).
    Global audit: English, Japanese, Korean, Chinese table order.
    """
    themes = vocab["themes"][theme]
    ordered_langs: list[str]
    if global_audit or country is None:
        ordered_langs = ["english", "japanese", "korean", "chinese"]
    elif country == "US":
        ordered_langs = ["english"]
    else:
        primary = vocab["country_language_rows"][country]
        ordered_langs = [primary]
        if primary != "english":
            ordered_langs.append("english")

    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for lang in ordered_langs:
        for phrase in themes[lang]["positive"]:
            key = normalize_for_match(phrase)
            if key in seen:
                continue
            seen.add(key)
            out.append((lang, phrase))
    return out


def classify_text(
    text: str,
    *,
    theme: str,
    vocab: dict[str, Any],
    field_name: str,
    language_preference: str | None = None,
) -> MatchEvidence:
    """Local provisional classification. No translation, stemming, synonym, or LLM."""
    version = vocab["version"]
    hay = normalize_for_match(text)
    if not hay:
        return MatchEvidence(
            provisional_match=False,
            matched_term=None,
            matched_field=field_name,
            match_language=None,
            status="none",
            ambiguous_hits=(),
            exclusion_hits=(),
            smoke_vocabulary_version=version,
        )

    theme_block = vocab["themes"][theme]
    lang_order = (
        [language_preference]
        if language_preference
        else ["english", "japanese", "korean", "chinese"]
    )
    # Always scan all language rows so multilingual titles are covered.
    for lang in ("english", "japanese", "korean", "chinese"):
        if lang not in lang_order:
            lang_order.append(lang)

    exclusion_hits: list[str] = []
    ambiguous_hits: list[str] = []
    positive_hit: tuple[str, str] | None = None

    for lang in lang_order:
        block = theme_block[lang]
        for excl in block["exclusions"]:
            if _contains_phrase(hay, excl):
                exclusion_hits.append(excl)
        for amb in block["ambiguous"]:
            if _contains_phrase(hay, amb):
                ambiguous_hits.append(amb)
        if positive_hit is None:
            for pos in block["positive"]:
                if _contains_phrase(hay, pos):
                    positive_hit = (lang, pos)
                    break

    # Standalone agent never qualifies (even if listed ambiguous).
    if theme == "ai_agent" and _STANDALONE_AGENT.search(hay):
        # still allow an explicit AI-positive phrase to qualify below
        pass

    if positive_hit is not None:
        lang, term = positive_hit
        # Exclusion alone contexts: if a GenAI exclusion is present and the only
        # generative signal is that exclusion family without a true positive, we
        # would not have a positive_hit. If positive exists, it remains valid even
        # when exclusions also appear elsewhere in the text (frozen rule 3).
        return MatchEvidence(
            provisional_match=True,
            matched_term=term,
            matched_field=field_name,
            match_language=lang,
            status="positive",
            ambiguous_hits=tuple(dict.fromkeys(ambiguous_hits)),
            exclusion_hits=tuple(dict.fromkeys(exclusion_hits)),
            smoke_vocabulary_version=version,
        )

    if exclusion_hits and not ambiguous_hits:
        return MatchEvidence(
            provisional_match=False,
            matched_term=None,
            matched_field=field_name,
            match_language=None,
            status="excluded",
            ambiguous_hits=(),
            exclusion_hits=tuple(dict.fromkeys(exclusion_hits)),
            smoke_vocabulary_version=version,
        )

    if ambiguous_hits:
        return MatchEvidence(
            provisional_match=False,
            matched_term=ambiguous_hits[0],
            matched_field=field_name,
            match_language=None,
            status="ambiguous",
            ambiguous_hits=tuple(dict.fromkeys(ambiguous_hits)),
            exclusion_hits=tuple(dict.fromkeys(exclusion_hits)),
            smoke_vocabulary_version=version,
        )

    if exclusion_hits:
        return MatchEvidence(
            provisional_match=False,
            matched_term=None,
            matched_field=field_name,
            match_language=None,
            status="excluded",
            ambiguous_hits=(),
            exclusion_hits=tuple(dict.fromkeys(exclusion_hits)),
            smoke_vocabulary_version=version,
        )

    return MatchEvidence(
        provisional_match=False,
        matched_term=None,
        matched_field=field_name,
        match_language=None,
        status="none",
        ambiguous_hits=(),
        exclusion_hits=(),
        smoke_vocabulary_version=version,
    )


def classify_title_and_abstract(
    *,
    title: str | None,
    abstract: str | None,
    theme: str,
    vocab: dict[str, Any],
) -> dict[str, Any]:
    title_ev = classify_text(title or "", theme=theme, vocab=vocab, field_name="title")
    abs_ev = classify_text(abstract or "", theme=theme, vocab=vocab, field_name="abstract")
    title_only = title_ev.provisional_match
    title_plus_abstract = title_only or abs_ev.provisional_match
    chosen = title_ev if title_ev.provisional_match else abs_ev
    return {
        "title_only_match": title_only,
        "title_plus_abstract_match": title_plus_abstract,
        "provisional_match": title_plus_abstract,
        "matched_term": chosen.matched_term if title_plus_abstract else None,
        "matched_field": chosen.matched_field if title_plus_abstract else None,
        "match_language": chosen.match_language if title_plus_abstract else None,
        "match_status": chosen.status if title_plus_abstract else (
            abs_ev.status if abs_ev.status != "none" else title_ev.status
        ),
        "title_evidence": title_ev.__dict__,
        "abstract_evidence": abs_ev.__dict__,
        "smoke_vocabulary_version": vocab["version"],
    }
