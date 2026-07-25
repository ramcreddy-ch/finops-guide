from datetime import datetime

from finops.models import COST_RECORD_COLUMNS, CostRecord


def make_record(**overrides):
    defaults = dict(
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        provider="aws",
        account_id="111122223333",
        service="EC2",
        resource_id="aws-ec2-prod-00",
        region="us-east-1",
        environment="prod",
        team="platform",
        usage_type="on-demand",
        usage_quantity=24.0,
        usage_unit="hrs",
        unit_cost=0.5,
        cost_amount=12.0,
    )
    defaults.update(overrides)
    return CostRecord(**defaults)


def test_record_gets_an_id_by_default():
    record = make_record()
    assert record.id
    assert len(record.id) == 32  # uuid4 hex


def test_as_row_matches_column_count():
    record = make_record(tags={"team": "platform"})
    row = record.as_row()
    assert len(row) == len(COST_RECORD_COLUMNS)


def test_as_row_serializes_tags_as_json():
    record = make_record(tags={"utilization_pct": "3.2"})
    row = record.as_row()
    tags_index = COST_RECORD_COLUMNS.index("tags_json")
    assert row[tags_index] == '{"utilization_pct": "3.2"}'


def test_rejects_unknown_provider():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_record(provider="oracle-cloud")
