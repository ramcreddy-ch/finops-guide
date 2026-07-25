from datetime import datetime, timedelta

from finops.analytics.anomaly import detect_anomalies
from finops.models import CostRecord
from finops.storage import db


def record(resource_id, ts, cost, service="EC2"):
    return CostRecord(
        timestamp=ts,
        provider="aws",
        account_id="acct-1",
        service=service,
        resource_id=resource_id,
        region="us-east-1",
        environment="prod",
        team="platform",
        usage_type="on-demand",
        usage_quantity=1.0,
        usage_unit="hrs",
        unit_cost=cost,
        cost_amount=cost,
    )


def test_flags_a_resource_that_spikes(conn):
    now = datetime.utcnow()
    records = []
    # 10 hours of stable cost around $10, then a spike to $150
    for i in range(10, 0, -1):
        records.append(record("aws-ec2-prod-00", now - timedelta(hours=i), 10.0 + (i % 2)))
    records.append(record("aws-ec2-prod-00", now, 150.0))
    db.insert_records(conn, records)

    anomalies = detect_anomalies(conn, lookback_hours=48, z_threshold=3.0)

    assert len(anomalies) == 1
    assert anomalies[0]["resource_id"] == "aws-ec2-prod-00"
    assert anomalies[0]["cost_amount"] == 150.0


def test_stable_resource_is_not_flagged(conn):
    now = datetime.utcnow()
    records = [
        record("aws-ec2-prod-01", now - timedelta(hours=i), 10.0 + (i % 3) * 0.1)
        for i in range(10, -1, -1)
    ]
    db.insert_records(conn, records)

    anomalies = detect_anomalies(conn)

    assert anomalies == []


def test_resource_with_too_little_history_is_ignored(conn):
    now = datetime.utcnow()
    db.insert_records(conn, [
        record("aws-ec2-prod-02", now - timedelta(hours=1), 10.0),
        record("aws-ec2-prod-02", now, 200.0),
    ])

    anomalies = detect_anomalies(conn, min_history_points=5)

    assert anomalies == []
