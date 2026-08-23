"""Privacy-reduced envelope checksum helpers.

persisted_envelope_checksum is always over the privacy-reduced envelope,
never over a discarded upstream_response.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def canonical_envelope_bytes(envelope: Mapping[str, Any]) -> bytes:
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def persisted_envelope_checksum(envelope: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_envelope_bytes(envelope)).hexdigest()
    return f"sha256:{digest}"
