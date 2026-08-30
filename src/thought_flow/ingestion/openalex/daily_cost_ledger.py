"""Persistent UTC-day OpenAlex cost ledger and pre-request hard stop.

Program Control (TFO-M7-017-PC1): production OpenAlex must not issue a billable
HTTP attempt that would push the applicable UTC-day total above $1.00.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from thought_flow.smoke.http_client import OPENALEX_DOCUMENTED_DAILY_FREE_USD_WITH_KEY

# Authoritative billable-attempt projection / accounting unit used when a source
# cost is not yet known for the next attempt. Matches observed X-API-Cost scale
# used in M7 campaign telemetry (never coerce unknown to 0).
OPENALEX_BILLABLE_ATTEMPT_COST_USD = 0.0001
OPENALEX_DAILY_COST_CEILING_USD = OPENALEX_DOCUMENTED_DAILY_FREE_USD_WITH_KEY  # 1.0

LEDGER_SCHEMA_VERSION = "m7.openalex.daily_cost_ledger.v1"


class DailyCostCeilingExceeded(RuntimeError):
    """Raised before HTTP when the next attempt would exceed the UTC-day ceiling."""

    def __init__(self, message: str, *, accumulated_usd: float, projected_usd: float) -> None:
        super().__init__(message)
        self.accumulated_usd = accumulated_usd
        self.projected_usd = projected_usd


class DailyCostLedgerError(RuntimeError):
    """Fail-closed ledger / cost-model failures (never invent zero)."""


def credential_ledger_id(api_key: str | None) -> str:
    """Stable non-secret id for ledger partitioning by credential."""
    if api_key is None or str(api_key).strip() == "":
        return "keyless"
    digest = hashlib.sha256(str(api_key).encode("utf-8")).hexdigest()
    return f"key_{digest[:24]}"


def utc_billing_day(clock: Callable[[], datetime] | None = None) -> date:
    now = clock() if clock is not None else datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(UTC).date()


@dataclass
class DailyCostSnapshot:
    utc_date: date
    credential_id: str
    accumulated_usd: float
    attempt_count: int
    ceiling_usd: float
    unit_cost_usd: float

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.ceiling_usd - self.accumulated_usd)

    @property
    def live_execution_permitted(self) -> bool:
        return (self.accumulated_usd + self.unit_cost_usd) <= self.ceiling_usd

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "utc_date": self.utc_date.isoformat(),
            "credential_id": self.credential_id,
            "accumulated_usd": self.accumulated_usd,
            "attempt_count": self.attempt_count,
            "ceiling_usd": self.ceiling_usd,
            "billable_attempt_cost_usd": self.unit_cost_usd,
            "live_execution_permitted": self.live_execution_permitted,
            "remaining_usd": self.remaining_usd,
        }


class DailyCostGuard:
    """Pre-request UTC-day cost guard with durable ledger."""

    def __init__(
        self,
        *,
        ledger_root: Path,
        credential_id: str,
        ceiling_usd: float = OPENALEX_DAILY_COST_CEILING_USD,
        unit_cost_usd: float = OPENALEX_BILLABLE_ATTEMPT_COST_USD,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ceiling_usd <= 0 or not _finite_nonneg(ceiling_usd):
            raise DailyCostLedgerError("daily cost ceiling must be a finite positive number")
        if unit_cost_usd <= 0 or not _finite_nonneg(unit_cost_usd):
            raise DailyCostLedgerError(
                "billable attempt cost must be a finite positive number (unknown is not zero)"
            )
        self.ledger_root = Path(ledger_root)
        self.credential_id = credential_id
        self.ceiling_usd = float(ceiling_usd)
        self.unit_cost_usd = float(unit_cost_usd)
        self._clock = clock

    def ledger_path(self, day: date | None = None) -> Path:
        d = day or utc_billing_day(self._clock)
        return self.ledger_root / self.credential_id / f"{d.isoformat()}.json"

    def snapshot(self) -> DailyCostSnapshot:
        day = utc_billing_day(self._clock)
        data = self._read_ledger(day)
        return DailyCostSnapshot(
            utc_date=day,
            credential_id=self.credential_id,
            accumulated_usd=float(data["accumulated_usd"]),
            attempt_count=int(data["attempt_count"]),
            ceiling_usd=self.ceiling_usd,
            unit_cost_usd=self.unit_cost_usd,
        )

    def authorize_next_attempt(self) -> None:
        """Fail closed before HTTP if the next billable attempt would exceed the ceiling."""
        snap = self.snapshot()
        projected = snap.accumulated_usd + self.unit_cost_usd
        if projected > self.ceiling_usd + 1e-15:
            raise DailyCostCeilingExceeded(
                (
                    f"OpenAlex daily cost ceiling would be exceeded: "
                    f"accumulated={snap.accumulated_usd:.6f} "
                    f"next={self.unit_cost_usd:.6f} "
                    f"projected={projected:.6f} "
                    f"ceiling={self.ceiling_usd:.6f} "
                    f"utc_date={snap.utc_date.isoformat()}"
                ),
                accumulated_usd=snap.accumulated_usd,
                projected_usd=projected,
            )

    def record_billable_attempt(self, *, source_reported_cost_usd: float | None) -> None:
        """Persist spend for one billable attempt (including retries)."""
        if source_reported_cost_usd is None:
            cost = self.unit_cost_usd
        else:
            if not _finite_nonneg(source_reported_cost_usd):
                raise DailyCostLedgerError(
                    f"unusable source-reported cost {source_reported_cost_usd!r}; fail closed"
                )
            cost = float(source_reported_cost_usd)
        day = utc_billing_day(self._clock)
        path = self.ledger_path(day)
        data = self._read_ledger(day)
        data["accumulated_usd"] = float(data["accumulated_usd"]) + cost
        data["attempt_count"] = int(data["attempt_count"]) + 1
        data["entries"].append(
            {
                "recorded_at": _utc_now_iso(self._clock),
                "cost_usd": cost,
                "source_reported": source_reported_cost_usd is not None,
            }
        )
        self._write_ledger(path, data)

    def _read_ledger(self, day: date) -> dict[str, Any]:
        path = self.ledger_path(day)
        if not path.exists():
            return {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "utc_date": day.isoformat(),
                "credential_id": self.credential_id,
                "accumulated_usd": 0.0,
                "attempt_count": 0,
                "entries": [],
            }
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise DailyCostLedgerError(f"unreadable daily cost ledger {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise DailyCostLedgerError(f"invalid daily cost ledger shape in {path}")
        if data.get("schema_version") != LEDGER_SCHEMA_VERSION:
            raise DailyCostLedgerError(
                f"unsupported ledger schema {data.get('schema_version')!r} in {path}"
            )
        if data.get("utc_date") != day.isoformat():
            raise DailyCostLedgerError(f"ledger date mismatch in {path}")
        if data.get("credential_id") != self.credential_id:
            raise DailyCostLedgerError(f"ledger credential mismatch in {path}")
        acc = data.get("accumulated_usd")
        if not _finite_nonneg(acc):
            raise DailyCostLedgerError(f"invalid accumulated_usd in {path}")
        attempts = data.get("attempt_count")
        if not isinstance(attempts, int) or attempts < 0:
            raise DailyCostLedgerError(f"invalid attempt_count in {path}")
        entries = data.get("entries")
        if not isinstance(entries, list):
            raise DailyCostLedgerError(f"invalid entries in {path}")
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "utc_date": day.isoformat(),
            "credential_id": self.credential_id,
            "accumulated_usd": float(acc),
            "attempt_count": attempts,
            "entries": entries,
        }

    def _write_ledger(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)


def default_ledger_root(data_root: Path) -> Path:
    return Path(data_root) / "manifests" / "openalex_backfill" / "daily_cost_ledger"


def _finite_nonneg(value: Any) -> bool:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return parsed >= 0.0 and parsed == parsed and parsed != float("inf")


def _utc_now_iso(clock: Callable[[], datetime] | None = None) -> str:
    now = clock() if clock is not None else datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
