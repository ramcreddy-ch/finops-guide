"""Two forecasting methods, both standard FinOps practice:

- run-rate: month-to-date spend divided by days elapsed, projected across
  the full month. Dead simple, and it's what most billing dashboards show
  as "projected spend" because it's easy to explain to a VP.
- linear trend: fits a line through the last N days of daily totals and
  extrapolates forward. Reacts to trend direction (ramping up/down) in a
  way the run-rate method can't, at the cost of being noisier on short
  histories.
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import datetime

import numpy as np

from finops.analytics.aggregation import daily_trend, month_to_date_cost


def forecast_month_end_run_rate(conn: sqlite3.Connection, at: datetime | None = None) -> dict:
    at = at or datetime.utcnow()
    start_of_month = at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mtd = month_to_date_cost(conn, at)

    days_elapsed = max((at - start_of_month).total_seconds() / 86400, 1 / 24)
    days_in_month = calendar.monthrange(at.year, at.month)[1]
    daily_run_rate = mtd / days_elapsed
    projected = daily_run_rate * days_in_month

    return {
        "method": "run_rate",
        "month_to_date": mtd,
        "days_elapsed": round(days_elapsed, 2),
        "days_in_month": days_in_month,
        "daily_run_rate": round(daily_run_rate, 2),
        "projected_month_end": round(projected, 2),
    }


def forecast_trend(conn: sqlite3.Connection, history_days: int = 14, forecast_days: int = 7) -> dict:
    history = daily_trend(conn, history_days)
    if len(history) < 3:
        return {"method": "linear_trend", "error": "not enough history yet", "forecast": []}

    x = np.arange(len(history))
    y = np.array([h["cost"] for h in history], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)

    forecast = [
        {
            "days_ahead": i + 1,
            "projected_cost": round(float(slope * (len(history) - 1 + i + 1) + intercept), 2),
        }
        for i in range(forecast_days)
    ]

    return {
        "method": "linear_trend",
        "slope_per_day": round(float(slope), 2),
        "history_days_used": len(history),
        "forecast": forecast,
    }
