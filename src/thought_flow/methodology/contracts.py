"""Load frozen M6 gate contracts JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thought_flow.config.settings import REPO_ROOT

CONTRACT_VERSION = "M6-GATE-CONTRACTS/v1"
THEME_DICT_VERSION = "THEME-DICT/v1"
DEFAULT_CONTRACT_PATH = REPO_ROOT / "config" / "rules" / "m6_gate_contracts_v1.json"


def load_gate_contracts(path: Path | None = None) -> dict[str, Any]:
    contract_path = path or DEFAULT_CONTRACT_PATH
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    if data.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(
            f"Gate contract version mismatch: file={data.get('contract_version')!r} "
            f"expected={CONTRACT_VERSION!r}"
        )
    return data
