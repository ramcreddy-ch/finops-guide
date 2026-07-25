"""Resource-level cost anomaly detection.

Approach: for every resource seen in the lookback window, treat its cost
history as a series, compute mean/stddev over everything except the most
recent point, and flag the most recent point if it's more than
`z_threshold` standard deviations above that baseline. It's a simple
z-score detector, not a real forecasting model, but it's exactly what
catches "someone left an autoscaling group misconfigured" or "a Lambda
started looping" style incidents, which is most of what FinOps anomaly
detection needs to catch in practice.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np


def detect_anomalies(
    conn: sqlite3.Connection,
    lookback_hours: int = 48,
    z_threshold: float = 3.0,
    min_history_points: int = 5,
) -> list[dict]:
    since = datetime.utcnow() - timedelta(hours=lookback_hours)
    rows = conn.execute(
        """
        SELECT resource_id, provider, service, team, environment, timestamp, cost_amount
        FROM cost_records
        WHERE timestamp >= ?
        ORDER BY resource_id, timestamp
        """,
        (since.isoformat(),),
    ).fetchall()

    series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    meta: dict[str, dict] = {}
    for row in rows:
        series[row["resource_id"]].append((row["timestamp"], row["cost_amount"]))
        meta[row["resource_id"]] = {
            "provider": row["provider"],
            "service": row["service"],
            "team": row["team"],
            "environment": row["environment"],
        }

    anomalies = []
    for resource_id, points in series.items():
        if len(points) < min_history_points:
            continue

        costs = np.array([p[1] for p in points], dtype=float)
        baseline, latest = costs[:-1], costs[-1]
        latest_ts = points[-1][0]

        mean = float(baseline.mean())
        std = float(baseline.std())

        if std == 0:
            if mean <= 0 or latest <= mean * 3:
                continue
            z_score = None
        else:
            z = (latest - mean) / std
            if z < z_threshold or latest <= mean:
                continue
            z_score = round(float(z), 2)

        anomalies.append(
            {
                "resource_id": resource_id,
                **meta[resource_id],
                "timestamp": latest_ts,
                "cost_amount": round(float(latest), 4),
                "baseline_mean": round(mean, 4),
                "z_score": z_score,
            }
        )

    anomalies.sort(key=lambda a: a["cost_amount"], reverse=True)
    return anomalies
