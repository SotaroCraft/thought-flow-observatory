"""Dual live gate for Trends Transport B (Erratum-002).

Both gates are required. Either absent → SMOKE-BLOCKED; no live request.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_TERMS_FIELDS = (
    "approved_at",
    "approver",
    "applicable_terms",
    "automated_access",
    "storage",
    "publication",
)


@dataclass(frozen=True)
class HumanTermsEvidence:
    approved_at: str
    approver: str
    applicable_terms: str
    automated_access: str
    storage: str
    publication: str

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> HumanTermsEvidence:
        missing = [k for k in REQUIRED_TERMS_FIELDS if not str(data.get(k, "")).strip()]
        if missing:
            raise ValueError(f"incomplete Human terms evidence; missing: {missing}")
        return cls(
            approved_at=str(data["approved_at"]).strip(),
            approver=str(data["approver"]).strip(),
            applicable_terms=str(data["applicable_terms"]).strip(),
            automated_access=str(data["automated_access"]).strip(),
            storage=str(data["storage"]).strip(),
            publication=str(data["publication"]).strip(),
        )


@dataclass(frozen=True)
class TransportBLiveGateResult:
    erratum_002_accepted_on_main: bool
    human_terms_evidence_present: bool
    live_authorized: bool
    smoke_state: str
    reason: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "erratum_002_accepted_on_main": self.erratum_002_accepted_on_main,
            "human_terms_evidence_present": self.human_terms_evidence_present,
            "live_authorized": self.live_authorized,
            "smoke_state": self.smoke_state,
            "reason": self.reason,
        }


def smoke_spec_contains_erratum_002(text: str) -> bool:
    return (
        "Erratum-002" in text
        and "M5 Trends Explore/widget Transport Exception" in text
    )


def erratum_002_accepted_on_main(
    *,
    repo_root: Path | None = None,
    main_ref: str = "origin/main",
    override: bool | None = None,
) -> bool:
    """True only when Erratum-002 normative text is present on main.

    `override` is for unit tests. Production callers MUST NOT pass True
    unless main actually contains the Accepted Erratum.
    """
    if override is not None:
        return override
    root = repo_root or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "show", f"{main_ref}:docs/decisions/m5-smoke-spec.md"],
            cwd=str(root),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if result.returncode != 0 or not result.stdout:
        return False
    return smoke_spec_contains_erratum_002(result.stdout)


def load_human_terms_evidence(path: Path | None) -> HumanTermsEvidence | None:
    if path is None or not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("terms evidence must be a JSON object")
    return HumanTermsEvidence.from_mapping(data)


def evaluate_transport_b_live_gates(
    *,
    erratum_002_accepted_on_main: bool,
    terms_evidence: HumanTermsEvidence | None,
) -> TransportBLiveGateResult:
    terms_ok = terms_evidence is not None
    if erratum_002_accepted_on_main and terms_ok:
        return TransportBLiveGateResult(
            erratum_002_accepted_on_main=True,
            human_terms_evidence_present=True,
            live_authorized=True,
            smoke_state="gates_satisfied",
            reason=(
                "Both Erratum-002 Accepted on main and dated Human terms/"
                "automated-access/storage/publication evidence are present."
            ),
        )
    parts: list[str] = []
    if not erratum_002_accepted_on_main:
        parts.append("Erratum-002 not Accepted on main")
    if not terms_ok:
        parts.append("Human terms/automated-access/storage/publication evidence absent")
    return TransportBLiveGateResult(
        erratum_002_accepted_on_main=erratum_002_accepted_on_main,
        human_terms_evidence_present=terms_ok,
        live_authorized=False,
        smoke_state="SMOKE-BLOCKED",
        reason=(
            "Transport B live request forbidden: "
            + "; ".join(parts)
            + ". Erratum acceptance alone does not authorize live use."
        ),
    )
