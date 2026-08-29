"""Unit tests for M4 Graph → SPO smoke (no live Microsoft access)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from thought_flow.integrations.sharepoint.auth import (
    AUTH_MODE,
    PUBLIC_CLIENT_REDIRECT_URI,
    acquire_delegated_token_interactive,
)
from thought_flow.integrations.sharepoint.client import GraphHttpResult, site_path_address
from thought_flow.integrations.sharepoint.config import GraphSmokeConfig, load_graph_smoke_config
from thought_flow.integrations.sharepoint.sanitize import public_safe_evidence, redact_secrets
from thought_flow.integrations.sharepoint.smoke import SmokeDependencies, preflight, run_graph_spo_smoke

HOSTILE = (
    "tenant=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee "
    "https://contoso.sharepoint.com/sites/SecretHub?code=AUTHCODE123 "
    "trace=ffffffff-1111-2222-3333-444444444444 "
    "correlation=zzzzzzzz-yyyy-xxxx-wwww-vvvvvvvvvvvv "
    "Bearer " + ("eyJ" + ("A" * 20) + "." + ("B" * 20) + "." + ("C" * 20)) + " "
    r"C:\Users\secret\apps\MSPO\workspace-data\leak.json"
)


def _ready_config() -> GraphSmokeConfig:
    return GraphSmokeConfig(
        enable_sharepoint=True,
        client_id="00000000-0000-0000-0000-000000000001",
        tenant_id="common-test-tenant",
        spo_hostname="example.sharepoint.com",
        spo_site_path="/sites/ThoughtFlowObservatory",
    )


def _assert_public_safe_clean(payload: dict[str, Any], *, evidence_text: str | None = None) -> None:
    dumped = json.dumps(payload, ensure_ascii=False)
    for fragment in (
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "contoso.sharepoint.com",
        "code=AUTHCODE123",
        "ffffffff-1111-2222-3333-444444444444",
        "C:\\Users\\secret",
        "eyJ" + ("A" * 20),
        "AUTHCODE123",
        "error_description",
        "Traceback",
    ):
        assert fragment not in dumped
        if evidence_text is not None:
            assert fragment not in evidence_text
    assert payload.get("public_safe") is True
    if payload.get("status") == "failed":
        assert "failure_message" not in payload
        assert set(payload.keys()) <= {
            "status",
            "live",
            "checked_at",
            "auth_mode",
            "permission_scope",
            "failure_category",
            "error_classification",
            "http_status",
            "completed_operations",
            "manual_fallback",
            "public_safe",
        }


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
    class FakeToken:
        ok = False
        access_token = None
        error_classification = "invalid_client"

    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(acquire_token=lambda **kwargs: FakeToken()),
    )
    assert result["status"] == "failed"
    assert result["failure_category"] == "authentication_failed"
    assert result["error_classification"] == "invalid_client"
    _assert_public_safe_clean(result)


def test_successful_smoke_sanitizes_ids(tmp_path: Path) -> None:
    fake_jwt = "eyJ" + ("A" * 20) + "." + ("B" * 20) + "." + ("C" * 20)

    class OkToken:
        ok = True
        access_token = fake_jwt
        error_classification = None

    def fake_get(*, path: str, access_token: str, query: dict[str, str] | None = None):
        assert access_token.startswith("eyJ")
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
            )
        if path.endswith("/lists"):
            return GraphHttpResult(
                ok=True,
                status_code=200,
                payload={
                    "value": [
                        {"id": "other-list", "displayName": "Other", "name": "Other"},
                        {
                            "id": "list-guid-should-not-persist",
                            "displayName": "Sources",
                            "name": "Sources",
                        },
                        {"id": "third", "displayName": "Archive", "name": "Archive"},
                    ]
                },
                error_category=None,
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
        )

    evidence = tmp_path / "m4-smoke"
    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(
            acquire_token=lambda **kwargs: OkToken(),
            graph_get=fake_get,
        ),
        evidence_dir=evidence,
    )
    assert result["status"] == "succeeded"
    assert result["auth_mode"] == AUTH_MODE
    assert "site_resolve" in result["graph_operation_categories"]
    assert "list_enumerate" in result["graph_operation_categories"]
    assert "metadata_read" in result["graph_operation_categories"]
    enumerate_op = next(op for op in result["operations"] if op["category"] == "list_enumerate")
    assert enumerate_op["returned_list_count"] == 3
    assert enumerate_op["preferred_found"] is True
    assert enumerate_op["preferred_display_name"] == "Sources"
    assert "count" not in enumerate_op
    assert result.get("evidence_locator") == "m4-smoke/m4_graph_spo_smoke_latest.json"
    text = (evidence / "m4_graph_spo_smoke_latest.json").read_text(encoding="utf-8")
    assert "site-guid-should-not-persist" not in text
    assert "list-guid-should-not-persist" not in text
    assert fake_jwt not in text
    assert str(tmp_path) not in json.dumps(result)
    _assert_public_safe_clean(result, evidence_text=text)


def test_unexpected_response_handled() -> None:
    class OkToken:
        ok = True
        access_token = "token-value-not-for-logs"
        error_classification = None

    def fake_get(*, path: str, access_token: str, query: dict[str, str] | None = None):
        return GraphHttpResult(
            ok=True,
            status_code=200,
            payload={"displayName": "MissingId"},
            error_category=None,
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
    _assert_public_safe_clean(result)


def test_sanitize_and_redact_helpers() -> None:
    cleaned = public_safe_evidence(
        {
            "status": "failed",
            "live": True,
            "checked_at": "2026-08-29T00:00:00Z",
            "auth_mode": AUTH_MODE,
            "permission_scope": "Sites.Read.All",
            "failure_category": "authentication_failed",
            "error_classification": "invalid_client",
            "failure_message": HOSTILE,
            "access_token": "secret",
            "manual_fallback": "fallback",
            "public_safe": True,
        }
    )
    assert "failure_message" not in cleaned
    assert "access_token" not in cleaned
    assert cleaned["error_classification"] == "invalid_client"
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


def test_interactive_auth_classifies_security_defaults(
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
                "error_description": HOSTILE,
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
    assert result.error_classification == "security_defaults_blocked"


@pytest.mark.parametrize(
    ("expected_class",),
    [
        ("invalid_client",),
        ("consent_or_access_denied",),
    ],
)
def test_auth_error_classifications_public_safe(expected_class: str) -> None:
    class FakeToken:
        ok = False
        access_token = None
        error_classification = expected_class

    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(acquire_token=lambda **kwargs: FakeToken()),
    )
    assert result["error_classification"] == expected_class
    _assert_public_safe_clean(result)


def test_graph_401_and_403_public_safe(tmp_path: Path) -> None:
    class OkToken:
        ok = True
        access_token = "tok"
        error_classification = None

    for status, expected in ((401, "graph_unauthorized"), (403, "graph_forbidden")):

        def fake_get(
            *,
            path: str,
            access_token: str,
            query: dict[str, str] | None = None,
            _status: int = status,
        ):
            return GraphHttpResult(
                ok=False,
                status_code=_status,
                payload=None,
                error_category="http_error",
            )

        result = run_graph_spo_smoke(
            live=True,
            config=_ready_config(),
            deps=SmokeDependencies(
                acquire_token=lambda **kwargs: OkToken(),
                graph_get=fake_get,
            ),
            evidence_dir=tmp_path / f"m4-{status}",
        )
        assert result["status"] == "failed"
        assert result["http_status"] == status
        assert result["error_classification"] == expected
        _assert_public_safe_clean(result)


def test_msal_constructor_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class BoomMsal:
        def PublicClientApplication(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(HOSTILE)

    monkeypatch.setattr(
        "thought_flow.integrations.sharepoint.auth._import_msal",
        lambda: BoomMsal(),
    )
    token = acquire_delegated_token_interactive(
        client_id="app",
        authority="https://login.microsoftonline.com/t",
        prompt=lambda _m: None,
    )
    assert token.ok is False
    assert token.error_classification == "msal_constructor_failed"
    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(acquire_token=lambda **kwargs: token),
    )
    _assert_public_safe_clean(result)


def test_msal_silent_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeApp:
        def get_accounts(self) -> list[Any]:
            return [{"home_account_id": "x"}]

        def acquire_token_silent(self, scopes: list[str], account: Any = None) -> dict[str, Any]:
            raise RuntimeError(HOSTILE)

        def acquire_token_interactive(self, scopes: list[str], **kwargs: Any) -> dict[str, Any]:
            raise AssertionError("should not reach interactive after silent failure")

    class FakeMsal:
        def PublicClientApplication(self, client_id: str, authority: str) -> FakeApp:
            return FakeApp()

    monkeypatch.setattr(
        "thought_flow.integrations.sharepoint.auth._import_msal",
        lambda: FakeMsal(),
    )
    token = acquire_delegated_token_interactive(
        client_id="app",
        authority="https://login.microsoftonline.com/t",
        prompt=lambda _m: None,
    )
    assert token.error_classification == "msal_silent_failed"
    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(acquire_token=lambda **kwargs: token),
    )
    assert result["error_classification"] == "msal_silent_failed"
    _assert_public_safe_clean(result)


def test_msal_interactive_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeApp:
        def get_accounts(self) -> list[Any]:
            return []

        def acquire_token_interactive(self, scopes: list[str], **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError(HOSTILE)

    class FakeMsal:
        def PublicClientApplication(self, client_id: str, authority: str) -> FakeApp:
            return FakeApp()

    monkeypatch.setattr(
        "thought_flow.integrations.sharepoint.auth._import_msal",
        lambda: FakeMsal(),
    )
    token = acquire_delegated_token_interactive(
        client_id="app",
        authority="https://login.microsoftonline.com/t",
        prompt=lambda _m: None,
    )
    assert token.error_classification == "msal_interactive_failed"
    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(acquire_token=lambda **kwargs: token),
    )
    _assert_public_safe_clean(result)


def test_unexpected_graph_exception_public_safe() -> None:
    class OkToken:
        ok = True
        access_token = "tok"
        error_classification = None

    def boom(*, path: str, access_token: str, query: dict[str, str] | None = None):
        raise RuntimeError(HOSTILE)

    result = run_graph_spo_smoke(
        live=True,
        config=_ready_config(),
        deps=SmokeDependencies(
            acquire_token=lambda **kwargs: OkToken(),
            graph_get=boom,
        ),
    )
    assert result["status"] == "failed"
    assert result["error_classification"] == "graph_client_exception"
    _assert_public_safe_clean(result)


def test_cli_stdout_failure_is_public_safe(capsys: pytest.CaptureFixture[str]) -> None:
    from thought_flow import cli

    class FakeToken:
        ok = False
        access_token = None
        error_classification = "consent_or_access_denied"

    def fake_run(*, live: bool = False, evidence_dir=None, **kwargs):
        return run_graph_spo_smoke(
            live=True,
            config=_ready_config(),
            deps=SmokeDependencies(acquire_token=lambda **kw: FakeToken()),
            evidence_dir=evidence_dir,
        )

    # Patch smoke entry used by CLI.
    import thought_flow.integrations.sharepoint.smoke as smoke_mod

    original = smoke_mod.run_graph_spo_smoke
    smoke_mod.run_graph_spo_smoke = fake_run  # type: ignore[assignment]
    try:
        code = cli.run_m4_graph_spo_smoke(live=True)
    finally:
        smoke_mod.run_graph_spo_smoke = original  # type: ignore[assignment]
    captured = capsys.readouterr()
    assert code == 1
    assert "contoso.sharepoint.com" not in captured.out
    assert "contoso.sharepoint.com" not in captured.err
    assert HOSTILE.split()[0] not in captured.out
    payload = json.loads(captured.out)
    _assert_public_safe_clean(payload)
