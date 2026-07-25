"""Cost optimization recommendations - the "Optimize" phase of FinOps.

Two checks, both deliberately simple and explainable (a recommendation
nobody trusts doesn't get acted on):

- idle resources: anything running with sustained low utilization is
  either oversized or should be shut down entirely.
- commitment coverage: services running mostly on-demand at steady volume
  are candidates for reserved instances / savings plans / committed use
  discounts. We assume a flat 30% average discount for the estimate since
  actual discount depends on term length and provider - this is meant to
  flag the opportunity, not to be a quote.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

ASSUMED_COMMITMENT_DISCOUNT = 0.30


def find_idle_resources(
    conn: sqlite3.Connection,
    lookback_days: int = 7,
    utilization_threshold_pct: float = 10.0,
) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=lookback_days)
    rows = conn.execute(
        """
        SELECT resource_id, provider, service, team, environment, cost_amount, tags_json
        FROM cost_records
        WHERE timestamp >= ?
        """,
        (since.isoformat(),),
    ).fetchall()

    by_resource: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "utilizations": [], "meta": {}})
    for row in rows:
        tags = json.loads(row["tags_json"] or "{}")
        util = tags.get("utilization_pct")
        if util is None:
            continue
        entry = by_resource[row["resource_id"]]
        entry["cost"] += row["cost_amount"]
        entry["utilizations"].append(float(util))
        entry["meta"] = {
            "provider": row["provider"],
            "service": row["service"],
            "team": row["team"],
            "environment": row["environment"],
        }

    recommendations = []
    for resource_id, data in by_resource.items():
        avg_util = sum(data["utilizations"]) / len(data["utilizations"])
        if avg_util > utilization_threshold_pct:
            continue
        projected_monthly_cost = data["cost"] / lookback_days * 30
        recommendations.append(
            {
                "resource_id": resource_id,
                **data["meta"],
                "avg_utilization_pct": round(avg_util, 1),
                "observed_cost_lookback": round(data["cost"], 2),
                "lookback_days": lookback_days,
                "projected_monthly_cost": round(projected_monthly_cost, 2),
                "recommendation": "rightsize or terminate - sustained low utilization",
            }
        )

    recommendations.sort(key=lambda r: r["projected_monthly_cost"], reverse=True)
    return recommendations


def recommend_commitment_coverage(
    conn: sqlite3.Connection,
    lookback_days: int = 14,
    min_on_demand_cost: float = 50.0,
) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=lookback_days)
    rows = conn.execute(
        """
        SELECT provider, service, usage_type, SUM(cost_amount) AS total
        FROM cost_records
        WHERE timestamp >= ?
        GROUP BY provider, service, usage_type
        """,
        (since.isoformat(),),
    ).fetchall()

    totals: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in rows:
        totals[(row["provider"], row["service"])][row["usage_type"]] = row["total"]

    recommendations = []
    for (provider, service), by_usage_type in totals.items():
        on_demand_cost = by_usage_type.get("on-demand", 0.0)
        total_cost = sum(by_usage_type.values())
        if on_demand_cost < min_on_demand_cost or total_cost == 0:
            continue

        on_demand_share = on_demand_cost / total_cost
        if on_demand_share < 0.4:
            continue

        estimated_monthly_on_demand = on_demand_cost / lookback_days * 30
        estimated_savings = estimated_monthly_on_demand * ASSUMED_COMMITMENT_DISCOUNT

        recommendations.append(
            {
                "provider": provider,
                "service": service,
                "on_demand_share_pct": round(on_demand_share * 100, 1),
                "estimated_monthly_on_demand_cost": round(estimated_monthly_on_demand, 2),
                "estimated_monthly_savings": round(estimated_savings, 2),
                "recommendation": "commit to a reserved instance / savings plan for steady baseline usage",
            }
        )

    recommendations.sort(key=lambda r: r["estimated_monthly_savings"], reverse=True)
    return recommendations
