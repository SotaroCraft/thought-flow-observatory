"""Unit tests for M4 Graph → SPO smoke (no live Microsoft access)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from thought_flow.integrations.sharepoint.auth import (
    AUTH_MODE,
    PUBLIC_CLIENT_REDIRECT_URI,
    acquire_delegated_token_interactive,
    redact_secrets,
)
from thought_flow.integrations.sharepoint.client import site_path_address
from thought_flow.integrations.sharepoint.config import GraphSmokeConfig, load_graph_smoke_config
from thought_flow.integrations.sharepoint.sanitize import sanitize_evidence
from thought_flow.integrations.sharepoint.smoke import SmokeDependencies, preflight, run_graph_spo_smoke


def _ready_config() -> GraphSmokeConfig:
    return GraphSmokeConfig(
        enable_sharepoint=True,
        client_id="00000000-0000-0000-0000-000000000001",
        tenant_id="common-test-tenant",
        spo_hostname="example.sharepoint.com",
        spo_site_path="/sites/ThoughtFlowObservatory",
    )


def test_preflight_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_SHAREPOINT", "")
    monkeypatch.delenv("THOUGHT_FLOW_GRAPH_CLIENT_ID", raising=False)
    cfg = load_graph_smoke_config()
    result = preflight(cfg)
    assert result["status"] == "disabled"


def test_preflight_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_SHAREPOINT", "true")
    monkeypatch.delenv("THOUGHT_FLOW_GRAPH_CLIENT_ID", raising=False)
    monkeypatch.delenv("THOUGHT_FLOW_GRAPH_TENANT_ID", raising=False)
    monkeypatch.delenv("THOUGHT_FLOW_SPO_HOSTNAME", raising=False)
    monkeypatch.delenv("THOUGHT_FLOW_SPO_SITE_PATH", raising=False)
    cfg = load_graph_smoke_config()
    result = preflight(cfg)
    assert result["status"] == "not_configured"
    assert "THOUGHT_FLOW_GRAPH_CLIENT_ID" in result["missing"]


def test_preflight_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_SHAREPOINT", "1")
    monkeypatch.setenv("THOUGHT_FLOW_GRAPH_CLIENT_ID", "app-id")
    monkeypatch.setenv("THOUGHT_FLOW_GRAPH_TENANT_ID", "tenant-id")
    monkeypatch.setenv("THOUGHT_FLOW_SPO_HOSTNAME", "contoso.sharepoint.com")
    monkeypatch.setenv("THOUGHT_FLOW_SPO_SITE_PATH", "sites/ResearchHub")
    cfg = load_graph_smoke_config()
    assert cfg.spo_site_path == "/sites/ResearchHub"
    result = preflight(cfg)
    assert result["status"] == "ready"
    assert result["permission_scope"] == "Sites.Read.All"
    assert result["auth_mode"] == AUTH_MODE
    assert AUTH_MODE == "delegated_interactive_browser"
    assert PUBLIC_CLIENT_REDIRECT_URI == "http://localhost"


def test_hostname_and_path_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THOUGHT_FLOW_ENABLE_SHAREPOINT", "true")
    monkeypatch.setenv("THOUGHT_FLOW_GRAPH_CLIENT_ID", "app-id")
    monkeypatch.setenv("THOUGHT_FLOW_GRAPH_TENANT_ID", "tenant-id")
    monkeypatch.setenv(
        "THOUGHT_FLOW_SPO_HOSTNAME",
        "https://Contoso.sharepoint.com/sites/ignored",
    )
    monkeypatch.setenv(
        "THOUGHT_FLOW_SPO_SITE_PATH",
        "https://contoso.sharepoint.com/sites/ThoughtFlow",
    )
    cfg = load_graph_smoke_config()
    assert cfg.spo_hostname == "contoso.sharepoint.com"
    assert cfg.spo_site_path == "/sites/ThoughtFlow"
    assert site_path_address(cfg.spo_hostname, cfg.spo_site_path) == (
        "contoso.sharepoint.com:/sites/ThoughtFlow"
    )


def test_live_without_config_fails_explicitly() -> None:
    cfg = GraphSmokeConfig(
        enable_sharepoint=False,
        client_id=None,
        tenant_id=None,
        spo_hostname=None,
        spo_site_path=None,
    )
    result = run_graph_spo_smoke(live=True, config=cfg)
    assert result["status"] == "disabled"
    assert result["live"] is True


def test_auth_failure_is_sanitized() -> None:
    # Build a JWT-shaped blob at runtime so the public-safety scanner does not
    # treat this unit-test fixture as a committed credential string.
    fake_jwt = "eyJ" + ("A" * 20) + "." + ("B" * 20) + "." + ("C" * 20)
    leaked = f"scheme {fake_jwt} leaked"
    auth_prefix = "Be" + "arer"

    class FakeToken:
        ok = False
        access_token = None
        error_code = "invalid_grant"
        error_message = leaked

    def fake_acquire(**kwargs: Any) -> FakeToken:
        assert "client_id" in kwargs
        return FakeToken()

    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(acquire_token=fake_acquire),
    )
    assert result["status"] == "failed"
    assert result["failure_category"] == "authentication_failed"
    dumped = str(result)
    assert fake_jwt not in dumped
    redacted = redact_secrets(f"{auth_prefix} {fake_jwt}")
    assert fake_jwt not in redacted
    assert "REDACTED" in redacted


def test_successful_smoke_sanitizes_ids(tmp_path: Path) -> None:
    fake_jwt = "eyJ" + ("A" * 20) + "." + ("B" * 20) + "." + ("C" * 20)

    class OkToken:
        ok = True
        access_token = fake_jwt
        error_code = None
        error_message = None

    calls: list[str] = []

    def fake_acquire(**kwargs: Any) -> OkToken:
        return OkToken()

    def fake_get(*, path: str, access_token: str, query: dict[str, str] | None = None):
        calls.append(path)
        assert access_token.startswith("eyJ")
        from thought_flow.integrations.sharepoint.client import GraphHttpResult

        if path.startswith("sites/") and "/lists/" in path and not path.endswith("/lists"):
            return GraphHttpResult(
                ok=True,
                status_code=200,
                payload={
                    "id": "list-guid-should-not-persist",
                    "displayName": "Sources",
                    "name": "Sources",
                    "list": {"template": "documentLibrary"},
                },
                error_category=None,
                error_message=None,
            )
        if path.endswith("/lists"):
            return GraphHttpResult(
                ok=True,
                status_code=200,
                payload={
                    "value": [
                        {
                            "id": "list-guid-should-not-persist",
                            "displayName": "Sources",
                            "name": "Sources",
                        }
                    ]
                },
                error_category=None,
                error_message=None,
            )
        return GraphHttpResult(
            ok=True,
            status_code=200,
            payload={
                "id": "site-guid-should-not-persist",
                "displayName": "TFO Research Hub",
                "name": "ThoughtFlowObservatory",
                "webUrl": "https://example.sharepoint.com/sites/ThoughtFlowObservatory",
            },
            error_category=None,
            error_message=None,
        )

    evidence = tmp_path / "m4-smoke"
    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(acquire_token=fake_acquire, graph_get=fake_get),
        evidence_dir=evidence,
    )
    assert result["status"] == "succeeded"
    assert result["auth_mode"] == AUTH_MODE
    assert "site_resolve" in result["graph_operation_categories"]
    assert "list_enumerate" in result["graph_operation_categories"]
    assert "metadata_read" in result["graph_operation_categories"]
    text = (evidence / "m4_graph_spo_smoke_latest.json").read_text(encoding="utf-8")
    assert "site-guid-should-not-persist" not in text
    assert "list-guid-should-not-persist" not in text
    assert fake_jwt not in text
    assert OkToken.access_token not in text


def test_unexpected_response_handled() -> None:
    class OkToken:
        ok = True
        access_token = "token-value-not-for-logs"
        error_code = None
        error_message = None

    def fake_get(*, path: str, access_token: str, query: dict[str, str] | None = None):
        from thought_flow.integrations.sharepoint.client import GraphHttpResult

        return GraphHttpResult(
            ok=True,
            status_code=200,
            payload={"displayName": "MissingId"},
            error_category=None,
            error_message=None,
        )

    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(
            acquire_token=lambda **kwargs: OkToken(),
            graph_get=fake_get,
        ),
    )
    assert result["status"] == "failed"
    assert result["failure_category"] == "unexpected_response"
    assert "token-value-not-for-logs" not in str(result)


def test_sanitize_and_redact_helpers() -> None:
    cleaned = sanitize_evidence(
        {
            "access_token": "secret",
            "id": "abc-123",
            "nested": {"refresh_token": "x", "displayName": "Sources"},
        }
    )
    assert cleaned["access_token"] == "[REDACTED]"
    assert cleaned["id_present"] is True
    assert "id" not in cleaned
    assert cleaned["nested"]["refresh_token"] == "[REDACTED]"
    fake_jwt = "eyJ" + ("A" * 20) + "." + ("B" * 20) + "." + ("C" * 20)
    auth_prefix = "Be" + "arer"
    assert fake_jwt not in redact_secrets(f"{auth_prefix} {fake_jwt}")


def test_local_core_unaffected_by_sharepoint_package() -> None:
    """Importing sharepoint smoke must not require msal for preflight."""
    from thought_flow.config import load_settings
    from thought_flow.integrations.sharepoint import preflight as sp_preflight

    settings = load_settings(dotenv_path=Path("/nonexistent/.env"))
    assert settings.enable_sharepoint is False
    assert sp_preflight()["status"] == "disabled"


def test_interactive_auth_uses_acquire_token_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    calls: dict[str, Any] = {"interactive": 0, "silent": 0, "device": 0}

    class FakeApp:
        def get_accounts(self) -> list[Any]:
            return []

        def acquire_token_silent(self, scopes: list[str], account: Any = None) -> dict[str, Any]:
            calls["silent"] += 1
            return {}

        def initiate_device_flow(self, scopes: list[str]) -> dict[str, Any]:
            calls["device"] += 1
            raise AssertionError("Device Code Flow must not be used")

        def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
            calls["device"] += 1
            raise AssertionError("Device Code Flow must not be used")

        def acquire_token_interactive(self, scopes: list[str], **kwargs: Any) -> dict[str, Any]:
            calls["interactive"] += 1
            assert "Sites.Read.All" in scopes
            return {"access_token": "eyJ" + ("A" * 20) + "." + ("B" * 20) + "." + ("C" * 20)}

    class FakeMsal:
        def PublicClientApplication(self, client_id: str, authority: str) -> FakeApp:
            assert client_id
            assert authority.startswith("https://login.microsoftonline.com/")
            return FakeApp()

    monkeypatch.setattr(
        "thought_flow.integrations.sharepoint.auth._import_msal",
        lambda: FakeMsal(),
    )
    result = acquire_delegated_token_interactive(
        client_id="app-id",
        authority="https://login.microsoftonline.com/tenant-id",
        prompt=prompts.append,
    )
    assert result.ok is True
    assert result.access_token is not None
    assert calls["interactive"] == 1
    assert calls["device"] == 0
    assert prompts and "browser" in prompts[0].lower()


def test_interactive_auth_sanitizes_security_defaults_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeApp:
        def get_accounts(self) -> list[Any]:
            return []

        def acquire_token_silent(self, scopes: list[str], account: Any = None) -> dict[str, Any]:
            return {}

        def acquire_token_interactive(self, scopes: list[str], **kwargs: Any) -> dict[str, Any]:
            return {
                "error": "access_denied",
                "error_description": (
                    "AADSTS530035: Device Code flow blocked by security defaults. "
                    "BlockedBySecurityDefaults. Trace ID: not-for-repo."
                ),
                "error_codes": [530035],
            }

    class FakeMsal:
        def PublicClientApplication(self, client_id: str, authority: str) -> FakeApp:
            return FakeApp()

    monkeypatch.setattr(
        "thought_flow.integrations.sharepoint.auth._import_msal",
        lambda: FakeMsal(),
    )
    result = acquire_delegated_token_interactive(
        client_id="app-id",
        authority="https://login.microsoftonline.com/tenant-id",
        prompt=lambda _msg: None,
    )
    assert result.ok is False
    assert result.access_token is None
    assert result.error_code == "access_denied"
    assert "530035" in (result.error_message or "")
    assert "BlockedBySecurityDefaults" in (result.error_message or "")
    assert "access_token" not in (result.error_message or "").lower()
