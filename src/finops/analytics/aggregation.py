"""Basic cost aggregation queries. Nothing clever - group by a dimension,
sum the cost, sort descending. This is the "Inform" phase of FinOps: you
can't optimize or hold anyone accountable for spend you can't see broken
down by service/team/environment.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

VALID_DIMENSIONS = {"provider", "service", "team", "environment", "region", "account_id"}


def total_cost_since(conn: sqlite3.Connection, since: datetime) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_amount), 0) AS total FROM cost_records WHERE timestamp >= ?",
        (since.isoformat(),),
    ).fetchone()
    return round(row["total"], 2)


def cost_by_dimension(conn: sqlite3.Connection, dimension: str, since: datetime) -> list[dict]:
    if dimension not in VALID_DIMENSIONS:
        raise ValueError(f"unsupported dimension: {dimension}")

    rows = conn.execute(
        f"""
        SELECT {dimension} AS key, SUM(cost_amount) AS cost
        FROM cost_records
        WHERE timestamp >= ?
        GROUP BY {dimension}
        ORDER BY cost DESC
        """,
        (since.isoformat(),),
    ).fetchall()
    return [{"key": r["key"], "cost": round(r["cost"], 2)} for r in rows]


def daily_trend(conn: sqlite3.Connection, days: int) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=days)
    rows = conn.execute(
        """
        SELECT substr(timestamp, 1, 10) AS day, SUM(cost_amount) AS cost
        FROM cost_records
        WHERE timestamp >= ?
        GROUP BY day
        ORDER BY day ASC
        """,
        (since.isoformat(),),
    ).fetchall()
    return [{"day": r["day"], "cost": round(r["cost"], 2)} for r in rows]


def month_to_date_cost(conn: sqlite3.Connection, at: datetime | None = None) -> float:
    at = at or datetime.utcnow()
    start_of_month = at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return total_cost_since(conn, start_of_month)
