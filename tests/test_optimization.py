from datetime import datetime, timedelta

from finops.analytics import optimization
from finops.models import CostRecord
from finops.storage import db


def record(resource_id, ts, cost, usage_type="on-demand", tags=None):
    return CostRecord(
        timestamp=ts,
        provider="aws",
        account_id="acct-1",
        service="EC2",
        resource_id=resource_id,
        region="us-east-1",
        environment="prod",
        team="platform",
        usage_type=usage_type,
        usage_quantity=24.0,
        usage_unit="hrs",
        unit_cost=cost / 24.0,
        cost_amount=cost,
        tags=tags or {},
    )


def test_finds_resource_with_low_utilization(conn):
    now = datetime.utcnow()
    records = [
        record("aws-ec2-idle-00", now - timedelta(days=d), 24.0, tags={"utilization_pct": "2.5"})
        for d in range(5)
    ]
    db.insert_records(conn, records)

    idle = optimization.find_idle_resources(conn, lookback_days=7, utilization_threshold_pct=10.0)

    assert len(idle) == 1
    assert idle[0]["resource_id"] == "aws-ec2-idle-00"
    assert idle[0]["projected_monthly_cost"] > 0


def test_ignores_healthy_utilization(conn):
    now = datetime.utcnow()
    records = [
        record("aws-ec2-busy-00", now - timedelta(days=d), 24.0, tags={"utilization_pct": "65.0"})
        for d in range(5)
    ]
    db.insert_records(conn, records)

    idle = optimization.find_idle_resources(conn, lookback_days=7)

    assert idle == []


def test_recommends_commitment_for_heavy_on_demand_usage(conn):
    now = datetime.utcnow()
    records = [
        record(f"aws-ec2-{i}", now - timedelta(days=1), 100.0, usage_type="on-demand")
        for i in range(3)
    ]
    db.insert_records(conn, records)

    recs = optimization.recommend_commitment_coverage(conn, lookback_days=14, min_on_demand_cost=50.0)

    assert len(recs) == 1
    assert recs[0]["service"] == "EC2"
    assert recs[0]["estimated_monthly_savings"] > 0


def test_no_recommendation_when_already_mostly_committed(conn):
    now = datetime.utcnow()
    db.insert_records(conn, [
        record("aws-ec2-reserved", now - timedelta(days=1), 100.0, usage_type="reserved"),
        record("aws-ec2-small-on-demand", now - timedelta(days=1), 5.0, usage_type="on-demand"),
    ])

    recs = optimization.recommend_commitment_coverage(conn, lookback_days=14, min_on_demand_cost=50.0)

    assert recs == []
