"""OpenAlex Works list/search client for bounded M5 smoke."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from thought_flow.smoke.http_client import (
    RequestBudget,
    SmokeHttpClient,
    build_url,
    openalex_cost_ceiling_usd,
    resolve_openalex_cost_usd,
)
from thought_flow.smoke.periods import SmokePeriod

OPENALEX_WORKS_URL = "https://api.openalex.org/works"

# Per-cell ceilings from frozen smoke spec.
PER_PAGE = 25
MAX_RETAINED_PER_CELL = 100
MAX_INSPECTED_PER_CELL = 300
MAX_PAGES_PER_CELL = 12


@dataclass(frozen=True)
class OpenAlexQuery:
    cell_kind: str
    country: str | None
    theme: str | None
    period: SmokePeriod
    search_phrase: str | None
    page_index: int
    cursor: str | None
    filter_expr: str
    sanitized_url: str
    query_hash: str


def _query_hash(parts: dict[str, Any]) -> str:
    from thought_flow.observability.identity import raw_content_identity

    # Reuse content hashing helper for sanitized query identity (not upstream body).
    return raw_content_identity(parts).replace("raw_", "q_", 1)


def build_filter(
    *,
    period: SmokePeriod,
    country: str | None,
    denominator: bool = False,
) -> str:
    parts = [
        f"from_publication_date:{period.inclusive_start.isoformat()}",
        f"to_publication_date:{period.inclusive_end.isoformat()}",
    ]
    if country:
        # Retrieval aid only; multi-country evidence retained after projection.
        parts.append(f"authorships.countries:{country.lower()}")
    if denominator:
        # Denominator: country-period works; no search phrase.
        pass
    return ",".join(parts)


def make_works_url(
    *,
    filter_expr: str,
    search: str | None,
    cursor: str | None,
    api_key: str | None,
    select: str | None = None,
    per_page: int | None = None,
) -> str:
    params: dict[str, Any] = {
        "filter": filter_expr,
        "per-page": PER_PAGE if per_page is None else per_page,
    }
    if search:
        params["search"] = search
    if cursor:
        params["cursor"] = cursor
    else:
        # First page of a search/list; cursor=* enables cursor paging when needed.
        params["cursor"] = "*"
    if select:
        params["select"] = select
    if api_key:
        params["api_key"] = api_key
    return build_url(OPENALEX_WORKS_URL, params)


class OpenAlexClient:
    def __init__(
        self,
        *,
        http: SmokeHttpClient | None = None,
        api_key: str | None = None,
    ) -> None:
        self.http = http or SmokeHttpClient()
        self.api_key = api_key if api_key is not None else os.getenv("THOUGHT_FLOW_OPENALEX_API_KEY")
        if self.api_key is not None and not str(self.api_key).strip():
            self.api_key = None
        # Apply frozen cost ceiling for the active access mode (key vs keyless).
        self.http.budget.max_cost_usd = openalex_cost_ceiling_usd(has_api_key=bool(self.api_key))

    @property
    def budget(self) -> RequestBudget:
        return self.http.budget

    def fetch_works_page(
        self,
        *,
        filter_expr: str,
        search: str | None,
        cursor: str | None,
        per_page: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        url = make_works_url(
            filter_expr=filter_expr,
            search=search,
            cursor=cursor,
            api_key=self.api_key,
            per_page=per_page,
        )
        response = self.http.get(url)
        meta = {
            "sanitized_url": response.url,
            "status_code": response.status_code,
            "attempts": [a.__dict__ for a in response.attempts],
            "retry_count": max(0, len(response.attempts) - 1),
            "cost_usd": response.cost_usd,
            "terminal_blocker": response.terminal_blocker,
            "rate_limit_remaining": response.headers.get("x-ratelimit-remaining"),
            "rate_limit_retry_after": response.headers.get("retry-after"),
            "observed_headers": {
                k: response.headers.get(k)
                for k in (
                    "x-api-cost",
                    "x-ratelimit-remaining",
                    "x-ratelimit-limit",
                    "retry-after",
                )
                if response.headers.get(k) is not None
            },
        }
        if response.status_code >= 400:
            return {
                "error": True,
                "status_code": response.status_code,
                "meta": {},
                "results": [],
            }, meta
        from thought_flow.smoke.progress import progress

        progress("response parsing", f"status={response.status_code} bytes={len(response.body)}")
        payload = json.loads(response.body.decode("utf-8"))
        # Prefer header cost (already budgeted); else fall back to meta.cost_usd once.
        effective_cost = resolve_openalex_cost_usd(headers=response.headers, payload=payload)
        if response.cost_usd is None and effective_cost is not None:
            self.http.budget.register(attempts=0, cost_usd=effective_cost)
        meta["cost_usd"] = effective_cost
        return payload, meta
