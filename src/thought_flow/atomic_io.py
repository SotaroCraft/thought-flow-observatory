"""Atomic JSON/text writes safe on Windows (temp file in same directory + os.replace)."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


def is_temporary_sidecar(path: Path) -> bool:
    """True for write sidecars that must never be treated as final artifacts."""
    name = path.name
    return name.endswith(".tmp") or name.startswith(".")


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    """
    Write text via a same-directory temporary file, then atomically replace.

    On Windows, ``os.replace`` replaces the destination when source and destination
    are on the same volume (guaranteed here by using ``path.parent`` for the temp).
    A failure before replace leaves the existing destination intact.

    Brief PermissionError retries absorb transient Windows locks (AV / indexer)
    without rewriting the destination in place.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        last_error: OSError | None = None
        for attempt in range(8):
            try:
                os.replace(tmp_path, path)
                return path
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.025 * (attempt + 1))
        assert last_error is not None
        raise last_error
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise
