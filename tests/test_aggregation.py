from datetime import datetime, timedelta

from finops.analytics import aggregation
from finops.models import CostRecord
from finops.storage import db


def record(ts, cost, provider="aws", service="EC2", team="platform", environment="prod"):
    return CostRecord(
        timestamp=ts,
        provider=provider,
        account_id="acct-1",
        service=service,
        resource_id=f"{provider}-{service}-r1",
        region="us-east-1",
        environment=environment,
        team=team,
        usage_type="on-demand",
        usage_quantity=1.0,
        usage_unit="hrs",
        unit_cost=cost,
        cost_amount=cost,
    )


def test_total_cost_since(conn):
    now = datetime.utcnow()
    db.insert_records(conn, [
        record(now - timedelta(hours=1), 10.0),
        record(now - timedelta(days=5), 20.0),
    ])

    total_last_day = aggregation.total_cost_since(conn, now - timedelta(days=1))
    assert total_last_day == 10.0

    total_last_week = aggregation.total_cost_since(conn, now - timedelta(days=7))
    assert total_last_week == 30.0


def test_cost_by_dimension_groups_and_sorts(conn):
    now = datetime.utcnow()
    db.insert_records(conn, [
        record(now, 5.0, provider="aws"),
        record(now, 15.0, provider="azure"),
        record(now, 1.0, provider="gcp"),
    ])

    rows = aggregation.cost_by_dimension(conn, "provider", now - timedelta(hours=1))
    assert [r["key"] for r in rows] == ["azure", "aws", "gcp"]
    assert rows[0]["cost"] == 15.0


def test_cost_by_dimension_rejects_bad_dimension(conn):
    import pytest

    with pytest.raises(ValueError):
        aggregation.cost_by_dimension(conn, "not_a_real_column", datetime.utcnow())


def test_daily_trend_buckets_by_day(conn):
    day1 = datetime.utcnow() - timedelta(days=2)
    day2 = datetime.utcnow() - timedelta(days=1)
    db.insert_records(conn, [
        record(day1, 10.0),
        record(day1.replace(hour=23), 5.0),
        record(day2, 7.0),
    ])

    trend = aggregation.daily_trend(conn, days=5)
    by_day = {t["day"]: t["cost"] for t in trend}
    assert by_day[day1.strftime("%Y-%m-%d")] == 15.0
    assert by_day[day2.strftime("%Y-%m-%d")] == 7.0


def test_month_to_date_cost_excludes_previous_month(conn):
    at = datetime(2026, 3, 15, 12, 0, 0)
    db.insert_records(conn, [
        record(datetime(2026, 3, 1, 0, 0, 0), 100.0),
        record(datetime(2026, 2, 28, 23, 0, 0), 999.0),
    ])

    assert aggregation.month_to_date_cost(conn, at) == 100.0
