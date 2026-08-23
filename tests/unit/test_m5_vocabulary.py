"""Tests for PROVISIONAL-M5-SMOKE vocabulary matching."""

from __future__ import annotations

from thought_flow.smoke.vocabulary import (
    SMOKE_VOCABULARY_VERSION,
    classify_text,
    load_provisional_vocabulary,
    normalize_for_match,
    positive_phrases_for_country,
)


def test_vocabulary_version_loads() -> None:
    vocab = load_provisional_vocabulary()
    assert vocab["version"] == SMOKE_VOCABULARY_VERSION
    assert vocab["label"] == "PROVISIONAL-M5-SMOKE"


def test_normalize_nfkc_casefold_hyphen_whitespace() -> None:
    assert normalize_for_match("  Gen-AI\tModel  ") == "gen ai model"
    assert normalize_for_match("ＡＩ") == "ai"


def test_english_positive_generative_ai() -> None:
    vocab = load_provisional_vocabulary()
    ev = classify_text(
        "Advances in generative AI systems",
        theme="generative_ai",
        vocab=vocab,
        field_name="title",
    )
    assert ev.provisional_match is True
    assert ev.status == "positive"
    assert ev.matched_term is not None


def test_ambiguous_alone_does_not_qualify() -> None:
    vocab = load_provisional_vocabulary()
    ev = classify_text(
        "A foundation model for vision",
        theme="generative_ai",
        vocab=vocab,
        field_name="title",
    )
    assert ev.provisional_match is False
    assert ev.status == "ambiguous"


def test_exclusion_gan_alone() -> None:
    vocab = load_provisional_vocabulary()
    ev = classify_text(
        "Training a GAN for images",
        theme="generative_ai",
        vocab=vocab,
        field_name="title",
    )
    assert ev.provisional_match is False
    assert ev.status in {"excluded", "ambiguous", "none"}


def test_standalone_agent_never_qualifies() -> None:
    vocab = load_provisional_vocabulary()
    for text in ("An agent for booking", "software Agents in the field", "Agent"):
        ev = classify_text(text, theme="ai_agent", vocab=vocab, field_name="title")
        assert ev.provisional_match is False, text


def test_ai_agent_positive() -> None:
    vocab = load_provisional_vocabulary()
    ev = classify_text(
        "Building an AI agent with tools",
        theme="ai_agent",
        vocab=vocab,
        field_name="title",
    )
    assert ev.provisional_match is True
    assert ev.matched_term is not None


def test_japanese_korean_chinese_examples() -> None:
    vocab = load_provisional_vocabulary()
    jp = classify_text("生成AIの応用", theme="generative_ai", vocab=vocab, field_name="title")
    kr = classify_text("생성형 AI 연구", theme="generative_ai", vocab=vocab, field_name="title")
    zh = classify_text("生成式人工智能综述", theme="generative_ai", vocab=vocab, field_name="title")
    assert jp.provisional_match and kr.provisional_match and zh.provisional_match

    jp_agent = classify_text(
        "LLMエージェントの設計", theme="ai_agent", vocab=vocab, field_name="title"
    )
    kr_agent = classify_text(
        "AI 에이전트 프레임워크", theme="ai_agent", vocab=vocab, field_name="title"
    )
    zh_agent = classify_text("AI智能体研究", theme="ai_agent", vocab=vocab, field_name="title")
    assert jp_agent.provisional_match and kr_agent.provisional_match and zh_agent.provisional_match


def test_us_phrase_order_english_only() -> None:
    vocab = load_provisional_vocabulary()
    phrases = positive_phrases_for_country(vocab, theme="generative_ai", country="US")
    assert all(lang == "english" for lang, _ in phrases)


def test_jp_phrase_order_japanese_then_english() -> None:
    vocab = load_provisional_vocabulary()
    phrases = positive_phrases_for_country(vocab, theme="generative_ai", country="JP")
    langs = [lang for lang, _ in phrases]
    assert langs[0] == "japanese"
    assert "english" in langs
