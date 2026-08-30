"""Shared HTTP retry and OpenAlex smoke request budget."""

from __future__ import annotations

import math
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable


# Frozen OpenAlex smoke ceilings.
OPENALEX_MAX_HTTP_ATTEMPTS = 512
OPENALEX_MAX_COST_USD = 0.75
OPENALEX_DOCUMENTED_DAILY_FREE_USD_WITH_KEY = 1.0
OPENALEX_DOCUMENTED_DAILY_FREE_USD_KEYLESS = 0.1

# Operational bound for respecting Retry-After with a real wait.
# Larger values (e.g. ~12h) must not be shortened into a retry; they terminate.
MAX_OPERATIONAL_RETRY_AFTER_SECONDS = 300.0

MAX_RETRIES = 2  # in addition to the initial attempt; not mandatory to use all
BACKOFF_SECONDS = (2.0, 8.0)


def openalex_cost_ceiling_usd(*, has_api_key: bool) -> float:
    daily = (
        OPENALEX_DOCUMENTED_DAILY_FREE_USD_WITH_KEY
        if has_api_key
        else OPENALEX_DOCUMENTED_DAILY_FREE_USD_KEYLESS
    )
    return min(OPENALEX_MAX_COST_USD, 0.75 * daily)


OPENALEX_COST_CEILING_USD = openalex_cost_ceiling_usd(has_api_key=True)


@dataclass
class HttpAttemptRecord:
    attempt: int
    status_code: int | None
    error_category: str | None
    elapsed_ms: int
    retry_after: str | None = None
    retry_skipped_reason: str | None = None


@dataclass
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    url: str
    attempts: list[HttpAttemptRecord]
    cost_usd: float | None
    terminal_blocker: str | None = None


@dataclass
class RequestBudget:
    max_attempts: int = OPENALEX_MAX_HTTP_ATTEMPTS
    max_cost_usd: float = OPENALEX_COST_CEILING_USD
    attempts_used: int = 0
    # Sum of source-reported costs only; None until at least one cost is observed.
    cost_usd: float | None = None
    cost_report_count: int = 0
    stop_reason: str | None = None

    @property
    def reported_cost_usd(self) -> float | None:
        """Null when the source never reported cost; never coerce unknown to 0.0."""
        if self.cost_report_count <= 0:
            return None
        return self.cost_usd if self.cost_usd is not None else None

    def can_request(self) -> bool:
        if self.stop_reason:
            return False
        if self.attempts_used >= self.max_attempts:
            self.stop_reason = "http_attempt_ceiling"
            return False
        if (
            self.cost_report_count > 0
            and self.cost_usd is not None
            and self.cost_usd >= self.max_cost_usd
        ):
            self.stop_reason = "cost_ceiling"
            return False
        return True

    def register(self, *, attempts: int, cost_usd: float | None) -> None:
        self.attempts_used += attempts
        if cost_usd is not None:
            if self.cost_usd is None:
                self.cost_usd = 0.0
            self.cost_usd += cost_usd
            self.cost_report_count += 1
        if self.attempts_used >= self.max_attempts:
            self.stop_reason = self.stop_reason or "http_attempt_ceiling"
        if (
            self.cost_report_count > 0
            and self.cost_usd is not None
            and self.cost_usd >= self.max_cost_usd
        ):
            self.stop_reason = self.stop_reason or "cost_ceiling"


def coerce_source_reported_cost_usd(value: Any) -> float | None:
    """Accept finite non-negative source costs; keep unknown as null (never invent 0).

    Numeric 0 from the source is preserved as 0.0. Bool, NaN, Inf, negatives,
    and non-numeric values are rejected.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0.0:
        return None
    return parsed


def _parse_cost(headers: dict[str, str]) -> float | None:
    """Read X-API-Cost header when present and valid."""
    for k, v in headers.items():
        if k.lower() == "x-api-cost":
            return coerce_source_reported_cost_usd(v)
    return None


def resolve_openalex_cost_usd(
    *,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> float | None:
    """Prefer X-API-Cost; fall back to payload meta.cost_usd; never double-count.

    Precedence:
    1. Valid X-API-Cost header
    2. Else valid payload['meta']['cost_usd'] when payload is provided
    3. Else null (source did not report a usable cost)
    """
    header_cost = _parse_cost(headers)
    if header_cost is not None:
        return header_cost
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    return coerce_source_reported_cost_usd(meta.get("cost_usd"))


def parse_retry_after_seconds(retry_after: str | None) -> float | None:
    if retry_after is None or str(retry_after).strip() == "":
        return None
    try:
        return float(retry_after)
    except ValueError:
        return None


def retry_after_is_operable(retry_after: str | None) -> bool:
    """True when Retry-After can be waited in full for a smoke retry."""
    seconds = parse_retry_after_seconds(retry_after)
    if seconds is None:
        # No header: frozen fallback 2s / 8s applies for 429/5xx.
        return True
    return 0.0 <= seconds <= MAX_OPERATIONAL_RETRY_AFTER_SECONDS


def _should_retry_status(status: int | None, exc: BaseException | None) -> bool:
    if exc is not None:
        return isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError))
    if status is None:
        return False
    return status == 429 or status >= 500


def _sleep_for_retry(*, attempt_index: int, retry_after: str | None) -> None:
    """Wait using full Retry-After when operable; otherwise frozen 2s/8s (+jitter)."""
    seconds = parse_retry_after_seconds(retry_after)
    if seconds is not None:
        time.sleep(max(0.0, seconds) + random.uniform(0.0, 0.25))
        return
    base = BACKOFF_SECONDS[min(attempt_index, len(BACKOFF_SECONDS) - 1)]
    time.sleep(base + random.uniform(0.0, 0.25))


Transport = Callable[[str, dict[str, str], float], tuple[int, dict[str, str], bytes]]


def default_transport(
    url: str, headers: dict[str, str], timeout: float
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            hdrs = {k: v for k, v in resp.headers.items()}
            return int(status), hdrs, resp.read()
    except urllib.error.HTTPError as err:
        hdrs = {k: v for k, v in err.headers.items()} if err.headers else {}
        body = err.read() if hasattr(err, "read") else b""
        return int(err.code), hdrs, body


@dataclass
class SmokeHttpClient:
    budget: RequestBudget = field(default_factory=RequestBudget)
    transport: Transport = default_transport
    user_agent: str = "thought-flow-observatory-m5-smoke (research; local)"
    timeout_seconds: float = 30.0
    sleep_fn: Callable[..., None] = _sleep_for_retry
    # Optional production UTC-day hard stop (TFO-M7-017-PC1). Smoke leaves this None.
    daily_cost_guard: Any | None = None

    def get(self, url: str, *, extra_headers: dict[str, str] | None = None) -> HttpResponse:
        from thought_flow.smoke.progress import progress

        if not self.budget.can_request():
            raise RuntimeError(f"Request blocked by budget: {self.budget.stop_reason}")

        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if extra_headers:
            for k, v in extra_headers.items():
                if k.lower() in {"authorization", "proxy-authorization"}:
                    continue
                headers[k] = v

        attempts: list[HttpAttemptRecord] = []
        last_status: int | None = None
        last_headers: dict[str, str] = {}
        last_body = b""
        sanitized = _sanitize_url(url)
        terminal_blocker: str | None = None

        max_attempts = MAX_RETRIES + 1
        for attempt in range(1, max_attempts + 1):
            if self.budget.attempts_used + 1 > self.budget.max_attempts:
                self.budget.stop_reason = "http_attempt_ceiling"
                raise RuntimeError("HTTP attempt ceiling reached")

            # Pre-request hard stop — before any network I/O for this attempt.
            reservation_id: str | None = None
            if self.daily_cost_guard is not None:
                reservation_id = self.daily_cost_guard.authorize_next_attempt()

            progress(
                "HTTP request start",
                f"attempt={attempt}/{max_attempts} timeout_s={self.timeout_seconds} url={sanitized}",
            )
            started = time.perf_counter()
            try:
                status, hdrs, body = self.transport(url, headers, self.timeout_seconds)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                retry_after = hdrs.get("Retry-After") or hdrs.get("retry-after")
                attempts.append(
                    HttpAttemptRecord(
                        attempt=attempt,
                        status_code=status,
                        error_category=None if status < 400 else f"http_{status}",
                        elapsed_ms=elapsed_ms,
                        retry_after=retry_after,
                    )
                )
                # Count attempts per try; register header cost once for the
                # terminal response (not on intermediate retries).
                self.budget.register(attempts=1, cost_usd=None)
                attempt_header_cost = _parse_cost(hdrs)
                if self.daily_cost_guard is not None:
                    # Every billable attempt (including retries) hits the daily ledger.
                    self.daily_cost_guard.record_billable_attempt(
                        source_reported_cost_usd=attempt_header_cost,
                        reservation_id=reservation_id,
                    )
                last_status, last_headers, last_body = status, hdrs, body
                progress(
                    "HTTP response received",
                    f"attempt={attempt} status={status} elapsed_ms={elapsed_ms} "
                    f"bytes={len(body)} retry_after={retry_after!r}",
                )
                if not (_should_retry_status(status, None) and attempt < max_attempts):
                    break
                # 429/5xx may retry at most twice total — only when wait is operable.
                if status == 429 and not retry_after_is_operable(retry_after):
                    reason = "retry_after_not_operable"
                    attempts[-1].retry_skipped_reason = reason
                    terminal_blocker = reason
                    progress(
                        "HTTP retry skipped",
                        f"status=429 retry_after={retry_after!r} reason={reason}",
                    )
                    break
                progress("HTTP retry scheduled", f"status={status} retry_after={retry_after!r}")
                self.sleep_fn(attempt_index=attempt - 1, retry_after=retry_after)
                continue
            except Exception as exc:  # noqa: BLE001 — classified for retry policy
                # Cost-ceiling / ledger failures must not be swallowed as transport errors.
                if type(exc).__name__ in {
                    "DailyCostCeilingExceeded",
                    "DailyCostLedgerError",
                    "CostModelMismatch",
                }:
                    raise
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                attempts.append(
                    HttpAttemptRecord(
                        attempt=attempt,
                        status_code=None,
                        error_category=type(exc).__name__,
                        elapsed_ms=elapsed_ms,
                    )
                )
                self.budget.register(attempts=1, cost_usd=None)
                # Network exception after authorize: still a billable attempt risk;
                # record unit cost via guard when present (fail-closed accounting).
                if self.daily_cost_guard is not None:
                    self.daily_cost_guard.record_billable_attempt(
                        source_reported_cost_usd=None,
                        reservation_id=reservation_id,
                    )
                progress(
                    "HTTP request error",
                    f"attempt={attempt} category={type(exc).__name__} elapsed_ms={elapsed_ms}",
                )
                if _should_retry_status(None, exc) and attempt < max_attempts:
                    progress("HTTP retry scheduled", f"category={type(exc).__name__}")
                    self.sleep_fn(attempt_index=attempt - 1, retry_after=None)
                    continue
                raise

        assert last_status is not None
        # One logical response → at most one header-cost registration on in-process budget.
        header_cost = _parse_cost(last_headers)
        if header_cost is not None:
            self.budget.register(attempts=0, cost_usd=header_cost)
        return HttpResponse(
            status_code=last_status,
            headers={k.lower(): v for k, v in last_headers.items()},
            body=last_body,
            url=sanitized,
            attempts=attempts,
            cost_usd=header_cost,
            terminal_blocker=terminal_blocker,
        )


def _sanitize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    cleaned = [
        (k, v) for k, v in query if k.lower() not in {"api_key", "api-key", "mailto"}
    ]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(cleaned), parts.fragment)
    )


def build_url(base: str, params: dict[str, Any]) -> str:
    filtered = {k: v for k, v in params.items() if v is not None}
    return f"{base}?{urllib.parse.urlencode(filtered, doseq=True)}"
