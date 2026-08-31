"""Atomic JSON/text writes safe on Windows (temp file in same directory + os.replace)."""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path


def is_temporary_sidecar(path: Path) -> bool:
    """True for write sidecars that must never be treated as final artifacts."""
    name = path.name
    return name.endswith(".tmp") or name.startswith(".")


def publish_file_no_clobber(tmp_path: Path, final_path: Path) -> None:
    """
    Publish a completed temp file to ``final_path`` without overwriting.

    Windows: ``os.rename`` fails with FileExistsError when the destination exists.
    POSIX: ``os.link`` fails when the destination exists (rename would overwrite).

    Raises FileExistsError if ``final_path`` already exists.
    Leaves ``tmp_path`` in place on failure (caller may clean up).
    """
    tmp_path = Path(tmp_path)
    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    last_error: OSError | None = None
    for attempt in range(8):
        try:
            if os.name == "nt":
                os.rename(tmp_path, final_path)
            else:
                os.link(tmp_path, final_path)
                os.unlink(tmp_path)
            return
        except FileExistsError:
            raise
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.025 * (attempt + 1))
    assert last_error is not None
    raise last_error


def write_parquet_via_temp_no_clobber(table: object, final_path: Path) -> None:
    """
    Write a complete Parquet table to a non-discoverable temp, then no-clobber publish.

    Temp names end with ``.tmp`` and start with ``.`` so they are never treated as Raw.
    On FileExistsError the temp is removed and the error is re-raised.
    """
    import pyarrow.parquet as pq

    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{final_path.name}.publish-",
        suffix=f".{token}.tmp",
        dir=str(final_path.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        pq.write_table(table, tmp_path)
        # Durability before visibility. Use r+b — Windows rejects fsync on read-only fds.
        with open(tmp_path, "r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
        publish_file_no_clobber(tmp_path, final_path)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


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
