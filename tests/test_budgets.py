from datetime import datetime, timedelta

import pytest

from finops.analytics import budgets
from finops.models import CostRecord
from finops.storage import db


def record(ts, cost, team="platform"):
    return CostRecord(
        timestamp=ts,
        provider="aws",
        account_id="acct-1",
        service="EC2",
        resource_id="aws-ec2-prod-00",
        region="us-east-1",
        environment="prod",
        team=team,
        usage_type="on-demand",
        usage_quantity=1.0,
        usage_unit="hrs",
        unit_cost=cost,
        cost_amount=cost,
    )


def write_budgets_file(tmp_path, monthly_amount, alert_threshold_pct=80):
    budgets_file = tmp_path / "budgets.yaml"
    budgets_file.write_text(
        f"""
budgets:
  - name: platform-team
    scope: team
    match: platform
    monthly_amount: {monthly_amount}
    alert_threshold_pct: {alert_threshold_pct}
"""
    )
    return budgets_file


def test_on_track_below_threshold(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_BUDGETS_FILE", str(write_budgets_file(tmp_path, monthly_amount=1000)))
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db.insert_records(conn, [record(start_of_month + timedelta(hours=1), 100.0)])

    results = budgets.evaluate_budgets(conn, at=now)

    assert results[0]["status"] == "on_track"
    assert results[0]["pct_consumed"] == 10.0


def test_warning_above_threshold(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_BUDGETS_FILE", str(write_budgets_file(tmp_path, monthly_amount=100, alert_threshold_pct=80)))
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db.insert_records(conn, [record(start_of_month + timedelta(hours=1), 90.0)])

    results = budgets.evaluate_budgets(conn, at=now)

    assert results[0]["status"] == "warning"


def test_over_budget(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_BUDGETS_FILE", str(write_budgets_file(tmp_path, monthly_amount=100)))
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    db.insert_records(conn, [record(start_of_month + timedelta(hours=1), 150.0)])

    results = budgets.evaluate_budgets(conn, at=now)

    assert results[0]["status"] == "over_budget"


def test_rejects_unsupported_scope(conn, tmp_path, monkeypatch):
    budgets_file = tmp_path / "budgets.yaml"
    budgets_file.write_text(
        """
budgets:
  - name: bad-scope
    scope: resource_id
    match: whatever
    monthly_amount: 100
"""
    )
    monkeypatch.setenv("FINOPS_BUDGETS_FILE", str(budgets_file))

    with pytest.raises(ValueError):
        budgets.evaluate_budgets(conn)


def test_missing_budgets_file_returns_empty(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("FINOPS_BUDGETS_FILE", str(tmp_path / "does-not-exist.yaml"))

    assert budgets.evaluate_budgets(conn) == []
