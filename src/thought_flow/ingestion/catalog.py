"""Minimal DuckDB catalog for local Raw Parquet smoke queries."""

from __future__ import annotations

from pathlib import Path

import duckdb


def open_catalog(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def register_raw_parquet(conn: duckdb.DuckDBPyConnection, parquet_path: Path, view_name: str = "raw_smoke") -> None:
    # path as SQL string; paths are local and controlled by this package
    escaped = str(parquet_path).replace("'", "''")
    conn.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM read_parquet('{escaped}')")


def count_rows(conn: duckdb.DuckDBPyConnection, view_name: str = "raw_smoke") -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()
    return int(row[0]) if row else 0


def fetch_identities(conn: duckdb.DuckDBPyConnection, view_name: str = "raw_smoke") -> list[dict[str, str]]:
    rows = conn.execute(
        f"SELECT record_identity, raw_content_identity, run_identity FROM {view_name}"
    ).fetchall()
    return [
        {
            "record_identity": r[0],
            "raw_content_identity": r[1],
            "run_identity": r[2],
        }
        for r in rows
    ]
