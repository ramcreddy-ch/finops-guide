"""Provider adapter contract.

Anything that can produce a list of CostRecord objects for a time window is
a valid adapter - the simulator in finops.simulator implements this, and a
real adapter (hitting AWS Cost Explorer, Azure Cost Management, or GCP
Billing export) would implement the same interface. See
docs/10-multi-cloud-normalization.md for notes on wiring up a real one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from finops.models import CostRecord


class CostAdapter(ABC):
    provider: str

    @abstractmethod
    def fetch_historical(self, start: datetime, end: datetime) -> list[CostRecord]:
        """Return cost records for a fixed window. Used for backfills/seeding."""
        raise NotImplementedError

    @abstractmethod
    def next_tick(self, at: datetime) -> list[CostRecord]:
        """Return the records for a single simulated/real billing tick."""
        raise NotImplementedError
