"""Safe diagnostic progress lines for M5 live path (not evidence contract)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime


def progress(stage: str, detail: str = "") -> None:
    """Emit one flushed progress line. Never log secrets or upstream bodies."""
    ts = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    msg = f"[m5-progress] {ts} | {stage}"
    if detail:
        msg = f"{msg} | {detail}"
    print(msg, flush=True, file=sys.stderr)
