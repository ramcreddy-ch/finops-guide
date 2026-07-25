"""Budget tracking against config/budgets.yaml (falls back to
config/budgets.example.yaml if you haven't copied it yet - see
docs/08-forecasting-and-budgets.md).

Each budget entry is scoped to one dimension (team, environment, provider,
or account_id) and matched against a single value. Month-to-date actual
spend for that scope is compared to the monthly amount, and we reuse the
run-rate method from forecast.py to project whether the scope will land
over budget by month end.
"""

from __future__ import annotations

import calendar
import os
import sqlite3
from datetime import datetime

import yaml

DEFAULT_BUDGETS_FILE = "config/budgets.yaml"
FALLBACK_BUDGETS_FILE = "config/budgets.example.yaml"
VALID_SCOPES = {"team", "environment", "provider", "account_id"}


def _default_budgets_file_path() -> str:
    """Only falls back to the example file when the caller hasn't pointed
    us at anything specific - an explicit path (env var or argument) that
    doesn't exist should return no budgets, not silently substitute a
    different file.
    """
    env_path = os.environ.get("FINOPS_BUDGETS_FILE")
    if env_path:
        return env_path
    if os.path.exists(DEFAULT_BUDGETS_FILE):
        return DEFAULT_BUDGETS_FILE
    return FALLBACK_BUDGETS_FILE


def load_budgets(path: str | None = None) -> list[dict]:
    path = path or _default_budgets_file_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("budgets", [])


def evaluate_budgets(conn: sqlite3.Connection, path: str | None = None, at: datetime | None = None) -> list[dict]:
    at = at or datetime.utcnow()
    start_of_month = at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_elapsed = max((at - start_of_month).total_seconds() / 86400, 1 / 24)
    days_in_month = calendar.monthrange(at.year, at.month)[1]

    results = []
    for budget in load_budgets(path):
        scope = budget["scope"]
        if scope not in VALID_SCOPES:
            raise ValueError(f"unsupported budget scope: {scope}")

        row = conn.execute(
            f"""
            SELECT COALESCE(SUM(cost_amount), 0) AS total
            FROM cost_records
            WHERE timestamp >= ? AND {scope} = ?
            """,
            (start_of_month.isoformat(), budget["match"]),
        ).fetchone()

        actual = round(row["total"], 2)
        monthly_amount = budget["monthly_amount"]
        pct_consumed = round((actual / monthly_amount * 100), 1) if monthly_amount else 0.0
        projected = round((actual / days_elapsed) * days_in_month, 2)
        alert_threshold = budget.get("alert_threshold_pct", 80)

        if pct_consumed >= 100:
            status = "over_budget"
        elif pct_consumed >= alert_threshold:
            status = "warning"
        else:
            status = "on_track"

        results.append(
            {
                "name": budget["name"],
                "scope": scope,
                "match": budget["match"],
                "monthly_amount": monthly_amount,
                "actual_month_to_date": actual,
                "pct_consumed": pct_consumed,
                "projected_month_end": projected,
                "status": status,
            }
        )

    return results
