"""M5 Google Trends acquisition standardization tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_flow.smoke.periods import TRENDS_FULL, TRENDS_COUNTRIES, TRENDS_THEMES
from thought_flow.smoke.trends.alpha_route import (
    TRENDS_ALPHA_CREDENTIAL_ENV,
    assess_alpha_route,
    refuse_alpha_live_call,
)
from thought_flow.smoke.trends.csv_contract import DEFAULT_CSV_CONTRACT
from thought_flow.smoke.trends.csv_import import (
    import_human_csv,
    parse_official_trends_csv,
    redact_secrets,
)
from thought_flow.smoke.trends.probes import (
    ZERO_SEMANTICS_TRENDS,
    paired_probes,
    probe_for,
)


SAMPLE = Path("data/samples/m5_trends_ui_synthetic_us.csv")


def test_frozen_date_range_and_geos_themes() -> None:
    assert TRENDS_FULL.period_id == "TRENDS-FULL"
    assert TRENDS_FULL.inclusive_start.isoformat() == "2022-11-30"
    assert TRENDS_FULL.inclusive_end.isoformat() == "2026-08-16"
    assert TRENDS_FULL.half_open_form == "[2022-11-30, 2026-08-17)"
    assert TRENDS_COUNTRIES == ("JP", "US", "KR", "CN")
    assert TRENDS_THEMES == ("generative_ai", "ai_agent")
    assert probe_for("JP", "generative_ai") == "生成AI"
    assert paired_probes("US") == ("generative AI", "AI agent")


def test_alpha_route_not_implementable_from_public_docs() -> None:
    assessment = assess_alpha_route(human_entitlement_confirmed=True)
    assert assessment.route_verdict == "NOT_IMPLEMENTABLE_FROM_PUBLIC_DOCS"
    assert assessment.documented_api_route is None
    assert assessment.documented_auth_mechanism is None
    assert "unofficial" in assessment.reason.lower() or "reverse-engineer" in assessment.reason.lower()


def test_alpha_live_refuses_without_inventing_client() -> None:
    with pytest.raises(RuntimeError, match="blocked|CSV"):
        refuse_alpha_live_call()


def test_credential_env_absence_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TRENDS_ALPHA_CREDENTIAL_ENV, raising=False)
    assessment = assess_alpha_route()
    assert assessment.credential_env_present is False
    public = assessment.to_public_dict()
    assert public["credential_env_name"] == TRENDS_ALPHA_CREDENTIAL_ENV
    assert "secret" not in json.dumps(public).lower() or public["credential_env_present"] is False


def test_secret_redaction_never_persists_tokens() -> None:
    payload = {
        "authorization": "SENSITIVE_AUTH_HEADER_VALUE",
        "nested": {"api_key": "SENSITIVE_API_KEY_VALUE", "ok": 1},
        "note": "plain descriptive text without credential material",
    }
    red = redact_secrets(payload)
    assert red["authorization"] == "[REDACTED]"
    assert red["nested"]["api_key"] == "[REDACTED]"
    assert red["nested"]["ok"] == 1


def test_zero_semantics_and_fetch_failure_vs_zero() -> None:
    text = SAMPLE.read_text(encoding="utf-8")
    parsed = parse_official_trends_csv(text=text, country="US")
    zeros = [p for p in parsed.points_generative_ai if p.quality_state == "zero"]
    assert zeros
    assert all(p.zero_semantics == ZERO_SEMANTICS_TRENDS for p in zeros)
    assert all(
        p.zero_semantics != "absence_of_public_interest"
        for p in zeros
    )
    # Malformed numeric → fetch_failure distinguishable from zero
    bad = "Interest over time\nWeek,generative AI,AI agent\n2022-12-04,not-a-number,1\n"
    parsed_bad = parse_official_trends_csv(text=bad, country="US")
    assert parsed_bad.points_generative_ai[0].quality_state == "fetch_failure"
    assert parsed_bad.points_generative_ai[0].value is None


def test_malformed_import_rejected() -> None:
    with pytest.raises(ValueError, match="malformed"):
        parse_official_trends_csv(text="not a csv", country="US")


def test_jp_locale_official_ui_csv_shape() -> None:
    """Official JP-locale UI exports use 週 header, geo-suffixed labels, and 1 未満."""
    text = (
        "カテゴリ: すべてのカテゴリ\n"
        "\n"
        "週,生成AI: (日本),AIエージェント: (日本)\n"
        "2022-11-27,10,1 未満\n"
        "2022-12-04,8,0\n"
        "2023-01-01,6,2\n"
    )
    parsed = parse_official_trends_csv(text=text, country="JP")
    assert parsed.row_count == 3
    assert parsed.points_generative_ai[0].value == 10
    assert parsed.points_ai_agent[0].value == 0
    assert parsed.points_ai_agent[0].quality_state == "zero"
    assert parsed.points_ai_agent[0].zero_semantics == ZERO_SEMANTICS_TRENDS
    assert parsed.points_ai_agent[1].value == 0
    assert parsed.points_generative_ai[2].value == 6


def test_csv_import_append_only_and_no_ui_endpoint(tmp_path: Path) -> None:
    csv_path = tmp_path / "export.csv"
    csv_path.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    m1 = import_human_csv(
        csv_path=csv_path,
        country="US",
        data_root=tmp_path / "ws",
        code_revision="test",
        observation_index=1,
    )
    m2 = import_human_csv(
        csv_path=csv_path,
        country="US",
        data_root=tmp_path / "ws",
        code_revision="test",
        observation_index=1,
    )
    assert m1["run_id"] != m2["run_id"]
    assert m1["ui_automation"] is False
    assert m1["alpha_route_used"] is False
    assert m1["production_connector"] is False
    assert m1["second_observation_pending"] is True
    runs = list((tmp_path / "ws" / "m5-smoke" / "runs").iterdir())
    assert len(runs) == 2
    # Original run dirs untouched (append-only unique runs)
    assert (Path(m1["artifact_root"]) / "manifest.json").is_file()
    assert (Path(m2["artifact_root"]) / "manifest.json").is_file()
    blob = json.dumps(m1)
    assert "Bearer" not in blob
    assert "ya29" not in blob


def test_human_contract_forbids_ui_automation() -> None:
    checklist = DEFAULT_CSV_CONTRACT.human_checklist("KR")
    assert DEFAULT_CSV_CONTRACT.compare_both_themes_in_one_request is True
    assert "undocumented_ui_network_endpoints" in DEFAULT_CSV_CONTRACT.forbidden
    assert "생성형 AI" in checklist["steps"][1]
    assert "browser_login_automation" in DEFAULT_CSV_CONTRACT.forbidden


def test_no_production_connector_registration() -> None:
    # Trends must live under smoke/, not integrations/ production path.
    smoke_init = Path("src/thought_flow/smoke/trends/__init__.py")
    assert smoke_init.is_file()
    integrations = Path("src/thought_flow/integrations")
    if integrations.exists():
        names = [p.name for p in integrations.iterdir()]
        assert "trends" not in names
        assert "google_trends" not in names
