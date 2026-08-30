"""Persistent UTC-day OpenAlex cost ledger and pre-request hard stop.

Program Control (TFO-M7-017-PC1 / R2): production OpenAlex must not issue a
billable HTTP attempt that would push the applicable UTC-day total above $1.00.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Iterator

from thought_flow.atomic_io import atomic_write_text
from thought_flow.smoke.http_client import OPENALEX_DOCUMENTED_DAILY_FREE_USD_WITH_KEY

# Authoritative billable-attempt hard-stop unit. Source-reported cost is telemetry
# only and must never reduce this reservation or silently raise the ledger total.
OPENALEX_BILLABLE_ATTEMPT_COST_USD = 0.0001
OPENALEX_DAILY_COST_CEILING_USD = OPENALEX_DOCUMENTED_DAILY_FREE_USD_WITH_KEY  # 1.0

LEDGER_SCHEMA_VERSION = "m7.openalex.daily_cost_ledger.v1"
OPENALEX_API_KEY_ENV = "THOUGHT_FLOW_OPENALEX_API_KEY"


class DailyCostCeilingExceeded(RuntimeError):
    """Raised before HTTP when the next attempt would exceed the UTC-day ceiling."""

    def __init__(self, message: str, *, accumulated_usd: float, projected_usd: float) -> None:
        super().__init__(message)
        self.accumulated_usd = accumulated_usd
        self.projected_usd = projected_usd


class DailyCostLedgerError(RuntimeError):
    """Fail-closed ledger / cost-model failures (never invent zero)."""


class CostModelMismatch(RuntimeError):
    """Source-reported cost exceeds the frozen hard-stop unit; block further HTTP."""

    def __init__(self, message: str, *, source_reported_cost_usd: float, unit_cost_usd: float) -> None:
        super().__init__(message)
        self.source_reported_cost_usd = source_reported_cost_usd
        self.unit_cost_usd = unit_cost_usd


def resolve_openalex_api_key(explicit: str | None = None) -> str | None:
    """Shared OpenAlex API key resolver for client, ledger, dry-run, and CLI."""
    if explicit is not None:
        stripped = str(explicit).strip()
        return stripped or None
    value = os.getenv(OPENALEX_API_KEY_ENV)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


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
    cost_model_mismatch: bool = False
    live_block_reason: str | None = None

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.ceiling_usd - self.accumulated_usd)

    @property
    def live_execution_permitted(self) -> bool:
        if self.live_block_reason:
            return False
        if self.cost_model_mismatch:
            return False
        return (self.accumulated_usd + self.unit_cost_usd) <= self.ceiling_usd

    def to_public_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "utc_date": self.utc_date.isoformat(),
            "credential_id": self.credential_id,
            "accumulated_usd": self.accumulated_usd,
            "attempt_count": self.attempt_count,
            "ceiling_usd": self.ceiling_usd,
            "billable_attempt_cost_usd": self.unit_cost_usd,
            "live_execution_permitted": self.live_execution_permitted,
            "remaining_usd": self.remaining_usd,
            "cost_model_mismatch": self.cost_model_mismatch,
        }
        if self.live_block_reason:
            out["reason"] = self.live_block_reason
        return out


@contextmanager
def _credential_day_lock(lock_path: Path) -> Iterator[None]:
    """Exclusive lock on a stable sidecar file (not the replaceable ledger JSON)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fh = open(lock_path, "a+b")
    except OSError as exc:
        raise DailyCostLedgerError(f"unable to open ledger lock {lock_path}: {exc}") from exc
    locked = False
    try:
        if sys.platform == "win32":
            import msvcrt

            deadline = time.monotonic() + 60.0
            while True:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise DailyCostLedgerError(
                            f"timed out acquiring ledger lock {lock_path}"
                        )
                    time.sleep(0.01)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        try:
            if locked:
                if sys.platform == "win32":
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


class DailyCostGuard:
    """Pre-request UTC-day cost guard with durable, locked ledger reservations."""

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

    def lock_path(self, day: date | None = None) -> Path:
        d = day or utc_billing_day(self._clock)
        return self.ledger_root / self.credential_id / f"{d.isoformat()}.lock"

    def snapshot(self) -> DailyCostSnapshot:
        day = utc_billing_day(self._clock)
        with _credential_day_lock(self.lock_path(day)):
            data = self._read_ledger(day)
        return self._snapshot_from_data(day, data)

    def would_allow_next_attempt(self) -> bool:
        return self.snapshot().live_execution_permitted

    def raise_if_next_attempt_blocked(self) -> None:
        """Peek-only ceiling / mismatch check for between-date stops (no reservation)."""
        snap = self.snapshot()
        if snap.cost_model_mismatch:
            raise CostModelMismatch(
                "OpenAlex cost model mismatch blocks further HTTP on this UTC day",
                source_reported_cost_usd=self.unit_cost_usd,
                unit_cost_usd=self.unit_cost_usd,
            )
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

    def authorize_next_attempt(self) -> str:
        """Atomically reserve unit cost before HTTP. Returns reservation_id."""
        day = utc_billing_day(self._clock)
        with _credential_day_lock(self.lock_path(day)):
            path = self.ledger_path(day)
            data = self._read_ledger(day)
            if data.get("cost_model_mismatch"):
                raise CostModelMismatch(
                    "OpenAlex cost model mismatch blocks further HTTP on this UTC day",
                    source_reported_cost_usd=self.unit_cost_usd,
                    unit_cost_usd=self.unit_cost_usd,
                )
            accumulated = float(data["accumulated_usd"])
            projected = accumulated + self.unit_cost_usd
            if projected > self.ceiling_usd + 1e-15:
                raise DailyCostCeilingExceeded(
                    (
                        f"OpenAlex daily cost ceiling would be exceeded: "
                        f"accumulated={accumulated:.6f} "
                        f"next={self.unit_cost_usd:.6f} "
                        f"projected={projected:.6f} "
                        f"ceiling={self.ceiling_usd:.6f} "
                        f"utc_date={day.isoformat()}"
                    ),
                    accumulated_usd=accumulated,
                    projected_usd=projected,
                )
            reservation_id = f"rsv_{uuid.uuid4().hex}"
            data["accumulated_usd"] = projected
            data["attempt_count"] = int(data["attempt_count"]) + 1
            data["entries"].append(
                {
                    "reservation_id": reservation_id,
                    "recorded_at": _utc_now_iso(self._clock),
                    "cost_usd": self.unit_cost_usd,
                    "source_reported_cost_usd": None,
                    "reserved": True,
                }
            )
            try:
                self._write_ledger(path, data)
            except OSError as exc:
                raise DailyCostLedgerError(f"unable to write ledger {path}: {exc}") from exc
            return reservation_id

    def record_billable_attempt(
        self,
        *,
        source_reported_cost_usd: float | None,
        reservation_id: str | None = None,
    ) -> None:
        """Annotate a reservation; never reduce it or raise hard-stop accumulated above unit.

        Larger-than-unit source costs set ``cost_model_mismatch`` and raise without
        overflowing the ``$1.00`` hard-stop total.
        """
        if source_reported_cost_usd is not None and not _finite_nonneg(source_reported_cost_usd):
            raise DailyCostLedgerError(
                f"unusable source-reported cost {source_reported_cost_usd!r}; fail closed"
            )
        day = utc_billing_day(self._clock)
        with _credential_day_lock(self.lock_path(day)):
            path = self.ledger_path(day)
            data = self._read_ledger(day)
            entry = self._find_reservation(data, reservation_id)
            if entry is None:
                # Standalone / recovery path: append a full unit reservation only.
                if float(data["accumulated_usd"]) + self.unit_cost_usd > self.ceiling_usd + 1e-15:
                    raise DailyCostCeilingExceeded(
                        "cannot record standalone attempt above daily ceiling",
                        accumulated_usd=float(data["accumulated_usd"]),
                        projected_usd=float(data["accumulated_usd"]) + self.unit_cost_usd,
                    )
                rid = reservation_id or f"rsv_{uuid.uuid4().hex}"
                entry = {
                    "reservation_id": rid,
                    "recorded_at": _utc_now_iso(self._clock),
                    "cost_usd": self.unit_cost_usd,
                    "source_reported_cost_usd": None,
                    "reserved": True,
                }
                data["accumulated_usd"] = float(data["accumulated_usd"]) + self.unit_cost_usd
                data["attempt_count"] = int(data["attempt_count"]) + 1
                data["entries"].append(entry)

            if source_reported_cost_usd is not None:
                source = float(source_reported_cost_usd)
                entry["source_reported_cost_usd"] = source
                entry["reserved"] = False
                if source > self.unit_cost_usd + 1e-15:
                    data["cost_model_mismatch"] = True
                    entry["cost_model_mismatch"] = True
                    try:
                        self._write_ledger(path, data)
                    except OSError as exc:
                        raise DailyCostLedgerError(
                            f"unable to write ledger {path}: {exc}"
                        ) from exc
                    raise CostModelMismatch(
                        (
                            f"source-reported cost {source:.6f} exceeds hard-stop unit "
                            f"{self.unit_cost_usd:.6f}; further HTTP prohibited"
                        ),
                        source_reported_cost_usd=source,
                        unit_cost_usd=self.unit_cost_usd,
                    )
            else:
                entry["reserved"] = False

            # Hard-stop accumulated stays at reserved unit forever (never reduce).
            entry["cost_usd"] = self.unit_cost_usd
            try:
                self._write_ledger(path, data)
            except OSError as exc:
                raise DailyCostLedgerError(f"unable to write ledger {path}: {exc}") from exc

    def _find_reservation(
        self, data: dict[str, Any], reservation_id: str | None
    ) -> dict[str, Any] | None:
        entries = data.get("entries")
        if not isinstance(entries, list):
            return None
        if reservation_id is not None:
            for entry in reversed(entries):
                if isinstance(entry, dict) and entry.get("reservation_id") == reservation_id:
                    return entry
            return None
        for entry in reversed(entries):
            if isinstance(entry, dict) and entry.get("reserved") is True:
                return entry
        return None

    def _snapshot_from_data(self, day: date, data: dict[str, Any]) -> DailyCostSnapshot:
        return DailyCostSnapshot(
            utc_date=day,
            credential_id=self.credential_id,
            accumulated_usd=float(data["accumulated_usd"]),
            attempt_count=int(data["attempt_count"]),
            ceiling_usd=self.ceiling_usd,
            unit_cost_usd=self.unit_cost_usd,
            cost_model_mismatch=bool(data.get("cost_model_mismatch")),
        )

    def _read_ledger(self, day: date) -> dict[str, Any]:
        path = self.ledger_path(day)
        if not path.exists():
            return {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "utc_date": day.isoformat(),
                "credential_id": self.credential_id,
                "accumulated_usd": 0.0,
                "attempt_count": 0,
                "cost_model_mismatch": False,
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
        if float(acc) > self.ceiling_usd + 1e-9:
            raise DailyCostLedgerError(
                f"ledger accumulated_usd {acc} exceeds ceiling {self.ceiling_usd} in {path}"
            )
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
            "cost_model_mismatch": bool(data.get("cost_model_mismatch")),
            "entries": entries,
        }

    def _write_ledger(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        atomic_write_text(path, payload)


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
