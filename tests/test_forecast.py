from datetime import datetime, timedelta

from finops.analytics import forecast
from finops.models import CostRecord
from finops.storage import db


def record(ts, cost):
    return CostRecord(
        timestamp=ts,
        provider="aws",
        account_id="acct-1",
        service="EC2",
        resource_id="aws-ec2-prod-00",
        region="us-east-1",
        environment="prod",
        team="platform",
        usage_type="on-demand",
        usage_quantity=1.0,
        usage_unit="hrs",
        unit_cost=cost,
        cost_amount=cost,
    )


def test_run_rate_projects_forward_from_month_to_date_spend(conn):
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db.insert_records(conn, [record(start_of_month + timedelta(hours=1), 100.0)])

    result = forecast.forecast_month_end_run_rate(conn, at=now)

    assert result["month_to_date"] == 100.0
    assert result["daily_run_rate"] > 0
    assert result["projected_month_end"] >= result["month_to_date"]


def test_trend_forecast_needs_minimum_history(conn):
    now = datetime.utcnow()
    db.insert_records(conn, [record(now, 10.0), record(now - timedelta(days=1), 8.0)])

    result = forecast.forecast_trend(conn, history_days=14, forecast_days=7)

    assert "error" in result
    assert result["forecast"] == []


def test_trend_forecast_slopes_upward_on_rising_costs(conn):
    now = datetime.utcnow()
    records = [record(now - timedelta(days=d), 10.0 * (10 - d)) for d in range(9, -1, -1)]
    db.insert_records(conn, records)

    result = forecast.forecast_trend(conn, history_days=14, forecast_days=7)

    assert result["method"] == "linear_trend"
    assert result["slope_per_day"] > 0
    assert len(result["forecast"]) == 7
