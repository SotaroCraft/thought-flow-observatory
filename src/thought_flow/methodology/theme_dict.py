"""THEME-DICT/v1 loader — seed of PROVISIONAL-M5-SMOKE/2026-08-23-r1 unchanged."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thought_flow.config.settings import REPO_ROOT
from thought_flow.methodology.contracts import THEME_DICT_VERSION
from thought_flow.smoke.vocabulary import (
    SMOKE_VOCABULARY_VERSION,
    classify_text,
    classify_title_and_abstract,
    load_provisional_vocabulary,
)

DEFAULT_THEME_DICT_PATH = REPO_ROOT / "config" / "themes" / "theme_dict_v1.json"
M5_SEED_PATH = REPO_ROOT / "config" / "smoke" / "provisional_m5_smoke_2026_08_23_r1.json"


def load_theme_dict_v1(path: Path | None = None) -> dict[str, Any]:
    dict_path = path or DEFAULT_THEME_DICT_PATH
    data = json.loads(dict_path.read_text(encoding="utf-8"))
    if data.get("version") != THEME_DICT_VERSION:
        raise ValueError(
            f"Theme dictionary version mismatch: file={data.get('version')!r} "
            f"expected={THEME_DICT_VERSION!r}"
        )
    if data.get("seed_from") != SMOKE_VOCABULARY_VERSION:
        raise ValueError(
            f"Theme dictionary seed_from mismatch: {data.get('seed_from')!r} "
            f"expected={SMOKE_VOCABULARY_VERSION!r}"
        )
    if data.get("vocabulary_modified_after_m5") is not False:
        raise ValueError("THEME-DICT/v1 must record vocabulary_modified_after_m5=false")
    return data


def theme_terms_unchanged_from_m5_seed(
    theme_dict: dict[str, Any] | None = None,
    seed: dict[str, Any] | None = None,
) -> bool:
    """True iff theme term tables are identical to the M5 provisional seed."""
    td = theme_dict if theme_dict is not None else load_theme_dict_v1()
    sm = seed if seed is not None else load_provisional_vocabulary()
    return td["themes"] == sm["themes"] and td.get("country_language_rows") == sm.get(
        "country_language_rows"
    )


def classify_with_theme_dict_v1(
    text: str,
    *,
    theme: str,
    field_name: str = "title",
    vocab: dict[str, Any] | None = None,
) -> Any:
    """Deterministic classification under THEME-DICT/v1 (reuses M5 matching mechanics)."""
    dictionary = vocab if vocab is not None else load_theme_dict_v1()
    return classify_text(text, theme=theme, vocab=dictionary, field_name=field_name)


def classify_work_title_abstract_v1(
    *,
    title: str | None,
    abstract: str | None,
    theme: str,
    vocab: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dictionary = vocab if vocab is not None else load_theme_dict_v1()
    result = classify_title_and_abstract(
        title=title, abstract=abstract, theme=theme, vocab=dictionary
    )
    # Preserve field name for smoke compatibility; value is THEME-DICT/v1.
    result["dictionary_version"] = dictionary["version"]
    return result
