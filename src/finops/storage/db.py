"""SQLite storage for cost records.

Plain sqlite3, no ORM. This is a single-node demo project, not a production
FinOps platform serving a real enterprise - if you're adapting this for
something that actually needs to scale, swap this module for a Postgres/
Timescale connection and keep the same function signatures, everything
upstream (ingestion, analytics, api) only talks to this module.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from finops.models import COST_RECORD_COLUMNS, CostRecord

DEFAULT_DB_PATH = "data/finops.db"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS cost_records (
    {", ".join(f"{col} TEXT" if col not in ("usage_quantity", "unit_cost", "cost_amount") else f"{col} REAL" for col in COST_RECORD_COLUMNS)},
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_cost_records_timestamp ON cost_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_cost_records_service ON cost_records(service);
CREATE INDEX IF NOT EXISTS idx_cost_records_team ON cost_records(team);
CREATE INDEX IF NOT EXISTS idx_cost_records_provider ON cost_records(provider);
CREATE INDEX IF NOT EXISTS idx_cost_records_environment ON cost_records(environment);
"""


def db_path() -> str:
    return os.environ.get("FINOPS_DB_PATH", DEFAULT_DB_PATH)


def get_connection(path: str | None = None) -> sqlite3.Connection:
    path = path or db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(path: str | None = None) -> None:
    conn = get_connection(path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_records(conn: sqlite3.Connection, records: list[CostRecord]) -> None:
    if not records:
        return
    placeholders = ", ".join("?" for _ in COST_RECORD_COLUMNS)
    columns = ", ".join(COST_RECORD_COLUMNS)
    conn.executemany(
        f"INSERT OR REPLACE INTO cost_records ({columns}) VALUES ({placeholders})",
        [r.as_row() for r in records],
    )
    conn.commit()


def total_record_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM cost_records").fetchone()
    return row["n"]


def latest_timestamp(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(timestamp) AS ts FROM cost_records").fetchone()
    return row["ts"]
