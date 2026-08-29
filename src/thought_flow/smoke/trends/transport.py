"""Trends transport layer — acquisition only; converges on CSV import boundary.

Transport B (Explore/widget) live calls remain DISABLED until the Decision
`docs/decisions/m5-trends-transport-exception-proposal.md` is Accepted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from thought_flow.smoke.trends.acquisition_contract import TrendsAcquisitionContract

# Soft gate: must remain False until SoT exception is Accepted on main.
EXPLORE_WIDGET_LIVE_AUTHORIZED = False

GOOGLE_JSON_ANTI_XSSI_PREFIX = ")]}'"


class TrendsTransportError(RuntimeError):
    """Acquisition failure — MUST NOT be coerced to Trends numeric zero."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class TransportCsvResult:
    contract: TrendsAcquisitionContract
    transport_id: str
    csv_bytes: bytes
    public_meta: dict[str, Any]


class TrendsCsvTransport(Protocol):
    transport_id: str

    def acquire_csv(self, contract: TrendsAcquisitionContract) -> TransportCsvResult: ...


def strip_google_json_prefix(raw: bytes | str) -> str:
    """Remove Google anti-XSSI prefix `)]}'` when present; no semantic alteration."""
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    stripped = text.lstrip()
    if stripped.startswith(GOOGLE_JSON_ANTI_XSSI_PREFIX):
        stripped = stripped[len(GOOGLE_JSON_ANTI_XSSI_PREFIX) :].lstrip("\n\r ")
    return stripped


def parse_explore_widgets(raw: bytes | str) -> list[dict[str, Any]]:
    text = strip_google_json_prefix(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TrendsTransportError("explore_parse_failure", str(exc)) from exc
    widgets = payload.get("widgets")
    if not isinstance(widgets, list):
        raise TrendsTransportError("explore_parse_failure", "widgets list missing")
    return [w for w in widgets if isinstance(w, dict)]


def select_timeseries_widget(widgets: list[dict[str, Any]]) -> dict[str, Any]:
    for widget in widgets:
        if widget.get("id") == "TIMESERIES":
            return widget
    raise TrendsTransportError(
        "missing_timeseries_widget",
        "Explore response lacked TIMESERIES widget",
    )


def extract_timeseries_request_token(
    widget: dict[str, Any],
) -> tuple[Any, str]:
    """Pass through widget request + token without semantic modification."""
    if "request" not in widget:
        raise TrendsTransportError("missing_widget_request", "TIMESERIES.request absent")
    token = widget.get("token")
    if not isinstance(token, str) or not token.strip():
        raise TrendsTransportError("missing_widget_token", "TIMESERIES.token absent")
    return widget["request"], token


def map_http_failure_to_transport_error(status_code: int) -> TrendsTransportError:
    if status_code == 429:
        return TrendsTransportError("http_429", "rate limited; not a valid Trends zero")
    if status_code >= 400:
        return TrendsTransportError(
            f"http_{status_code}",
            "HTTP acquisition failure; not a valid Trends zero",
        )
    return TrendsTransportError("http_unexpected", f"unexpected status {status_code}")


@dataclass
class HumanOfficialCsvTransport:
    """Transport A — Human already downloaded official UI CSV."""

    csv_path: Path
    transport_id: str = "human_official_csv"

    def acquire_csv(self, contract: TrendsAcquisitionContract) -> TransportCsvResult:
        if not self.csv_path.is_file():
            raise TrendsTransportError("csv_missing", f"file not found: {self.csv_path}")
        data = self.csv_path.read_bytes()
        if not data:
            raise TrendsTransportError("csv_empty", "empty CSV bytes")
        return TransportCsvResult(
            contract=contract,
            transport_id=self.transport_id,
            csv_bytes=data,
            public_meta={
                "source_filename": self.csv_path.name,
                "byte_length": len(data),
                "live_network": False,
            },
        )


@dataclass
class ExploreWidgetCsvTransport:
    """Transport B — Explore/widget CSV (LIVE DISABLED until SoT exception Accepted)."""

    host: str = "https://trends.google.co.jp"
    hl: str = "ja"
    tz: int = -540
    transport_id: str = "explore_widget_csv"

    def acquire_csv(self, contract: TrendsAcquisitionContract) -> TransportCsvResult:
        if not EXPLORE_WIDGET_LIVE_AUTHORIZED:
            raise TrendsTransportError(
                "transport_b_not_authorized",
                "Explore/widget live acquisition is disabled until "
                "docs/decisions/m5-trends-transport-exception-proposal.md is Accepted. "
                "Use Transport A (Human official CSV) or obtain Human/Codex approval.",
            )
        # Live path intentionally not implemented here: would violate frozen SoT
        # until the exception Decision is Accepted. Keep a hard stop.
        raise TrendsTransportError(
            "transport_b_live_not_enabled",
            "Live Explore/widget client is not enabled in this revision.",
        )

    def build_explore_body(self, contract: TrendsAcquisitionContract) -> dict[str, Any]:
        """Public-safe body builder for tests — values from TFO contract only."""
        return contract.explore_comparison_payload()
