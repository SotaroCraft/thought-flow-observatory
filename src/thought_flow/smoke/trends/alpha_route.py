"""Official Google Trends API alpha — public-doc route assessment only.

M5 must not invent endpoints, scrape the UI, or use unofficial libraries.
Public Search Central docs describe alpha application and high-level
capabilities, but do not publish an implementable request schema / auth
flow for code without invitation materials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


ALPHA_PUBLIC_OVERVIEW_URL = "https://developers.google.com/search/apis/trends"
ALPHA_PUBLIC_ANNOUNCEMENT_URL = (
    "https://developers.google.com/search/blog/2025/07/trends-api"
)

# Env name only — never log values. Invitation materials may later define usage.
TRENDS_ALPHA_CREDENTIAL_ENV = "THOUGHT_FLOW_TRENDS_ALPHA_CREDENTIAL_PATH"


@dataclass(frozen=True)
class AlphaRouteAssessment:
    entitlement_human_confirmed: bool
    documented_auth_mechanism: str | None
    documented_api_route: str | None
    historical_range_public: str
    weekly_resolution_public: str
    geo_support_public: str
    multi_series_public: str
    quota_cost_public: str | None
    terms_storage_public: str | None
    route_verdict: str
    reason: str
    credential_env_present: bool

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "entitlement_human_confirmed": self.entitlement_human_confirmed,
            "documented_auth_mechanism": self.documented_auth_mechanism,
            "documented_api_route": self.documented_api_route,
            "historical_range_public": self.historical_range_public,
            "weekly_resolution_public": self.weekly_resolution_public,
            "geo_support_public": self.geo_support_public,
            "multi_series_public": self.multi_series_public,
            "quota_cost_public": self.quota_cost_public,
            "terms_storage_public": self.terms_storage_public,
            "route_verdict": self.route_verdict,
            "reason": self.reason,
            "credential_env_name": TRENDS_ALPHA_CREDENTIAL_ENV,
            "credential_env_present": self.credential_env_present,
            "public_doc_urls": [
                ALPHA_PUBLIC_OVERVIEW_URL,
                ALPHA_PUBLIC_ANNOUNCEMENT_URL,
            ],
            "fallback": "official_human_ui_csv_export",
        }


def assess_alpha_route(*, human_entitlement_confirmed: bool = True) -> AlphaRouteAssessment:
    """Assess whether Cursor can implement alpha from public documentation alone."""
    cred_path = (os.getenv(TRENDS_ALPHA_CREDENTIAL_ENV) or "").strip()
    return AlphaRouteAssessment(
        entitlement_human_confirmed=human_entitlement_confirmed,
        documented_auth_mechanism=None,
        documented_api_route=None,
        historical_range_public="rolling ~5 years / 1800 days (public overview)",
        weekly_resolution_public="daily/weekly/monthly/yearly intervals advertised",
        geo_support_public="countries and sub-regions advertised",
        multi_series_public="consistently scaled multi-request compare advertised",
        quota_cost_public=None,
        terms_storage_public=None,
        route_verdict="NOT_IMPLEMENTABLE_FROM_PUBLIC_DOCS",
        reason=(
            "Public Trends API alpha pages describe application and high-level "
            "capabilities only. They do not publish an implementable auth flow, "
            "endpoint/request schema, quota/cost table, or storage/publication "
            "terms for M5 smoke code. Cursor MUST NOT reverse-engineer UI "
            "endpoints or use unofficial libraries. Fall back to Human official "
            "UI CSV export + post-download import."
        ),
        credential_env_present=bool(cred_path),
    )


def refuse_alpha_live_call() -> None:
    """Hard stop for any attempted live alpha network acquisition in this milestone."""
    assessment = assess_alpha_route()
    raise RuntimeError(
        "Trends alpha live acquisition is blocked for M5 until Human supplies "
        "invitation-documented auth + API route + terms that can be recorded "
        f"public-safely. Verdict={assessment.route_verdict}. "
        f"Use official UI CSV import instead. Detail: {assessment.reason}"
    )
