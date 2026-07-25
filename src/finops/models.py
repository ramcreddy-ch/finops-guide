"""Shared cost record schema.

Every provider adapter (real or simulated) normalizes its billing data into
this shape before it hits the ingestion pipeline. That's the whole trick to
supporting AWS/Azure/GCP with one analytics layer - none of the aggregation,
anomaly detection, or budget code needs to know which cloud a record came
from.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["aws", "azure", "gcp"]
Environment = Literal["prod", "staging", "dev"]
UsageType = Literal["on-demand", "reserved", "spot", "savings-plan"]


class CostRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime
    provider: Provider
    account_id: str
    service: str
    resource_id: str
    region: str
    environment: Environment
    team: str
    usage_type: UsageType
    usage_quantity: float
    usage_unit: str
    unit_cost: float
    cost_amount: float
    currency: str = "USD"
    tags: dict[str, str] = Field(default_factory=dict)

    def as_row(self) -> tuple:
        """Flat tuple matching the cost_records table column order."""
        return (
            self.id,
            self.timestamp.isoformat(),
            self.provider,
            self.account_id,
            self.service,
            self.resource_id,
            self.region,
            self.environment,
            self.team,
            self.usage_type,
            self.usage_quantity,
            self.usage_unit,
            self.unit_cost,
            self.cost_amount,
            self.currency,
            json.dumps(self.tags),
        )


COST_RECORD_COLUMNS = (
    "id",
    "timestamp",
    "provider",
    "account_id",
    "service",
    "resource_id",
    "region",
    "environment",
    "team",
    "usage_type",
    "usage_quantity",
    "usage_unit",
    "unit_cost",
    "cost_amount",
    "currency",
    "tags_json",
)
