"""AWS cost data source.

Two things live here:

- SimulatedAWSAdapter: generates realistic-looking AWS spend for the demo,
  driven by the catalog in finops.simulator.catalog. This is what `finops
  serve` and `finops simulate` use by default, no AWS account needed.

- CostExplorerAdapter: a real adapter that pulls actual numbers out of the
  AWS Cost Explorer API. It's here so the swap from "demo" to "your real
  bill" is a one-line change (see docs/10-multi-cloud-normalization.md), but
  it needs boto3 and real credentials, so it's not wired up by default and
  isn't covered by the simulator's test suite.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from finops.models import CostRecord
from finops.providers.base import CostAdapter


class CostExplorerAdapter(CostAdapter):
    """Pulls real cost/usage data from AWS Cost Explorer.

    Requires `boto3` and credentials with ce:GetCostAndUsage. Cost Explorer
    reports at daily granularity at best (no true hourly stream), so
    `next_tick` here just re-fetches "yesterday" - if you want sub-day
    resolution from a real AWS bill you need to read the Cost and Usage
    Report (CUR) parquet/CSV exports from S3 instead, which is a bigger
    lift than this project takes on.
    """

    provider = "aws"

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id
        try:
            import boto3  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "CostExplorerAdapter needs boto3. Install it with "
                "`pip install boto3` if you want to use real AWS data."
            ) from exc
        import boto3

        self._client = boto3.client("ce")

    def fetch_historical(self, start: datetime, end: datetime) -> list[CostRecord]:
        resp = self._client.get_cost_and_usage(
            TimePeriod={
                "Start": start.strftime("%Y-%m-%d"),
                "End": end.strftime("%Y-%m-%d"),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost", "UsageQuantity"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
            ],
        )
        return self._parse_response(resp)

    def next_tick(self, at: datetime) -> list[CostRecord]:
        yesterday = at - timedelta(days=1)
        return self.fetch_historical(yesterday, at)

    def _parse_response(self, resp: dict) -> list[CostRecord]:
        records: list[CostRecord] = []
        for result in resp.get("ResultsByTime", []):
            ts = datetime.fromisoformat(result["TimePeriod"]["Start"])
            for group in result.get("Groups", []):
                service, region = group["Keys"]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                qty = float(group["Metrics"]["UsageQuantity"]["Amount"])
                if cost == 0 and qty == 0:
                    continue
                records.append(
                    CostRecord(
                        timestamp=ts,
                        provider="aws",
                        account_id=self.account_id,
                        service=service,
                        resource_id=f"{service}-aggregate",
                        region=region or "global",
                        environment="prod",
                        team="unassigned",
                        usage_type="on-demand",
                        usage_quantity=qty,
                        usage_unit="unit",
                        unit_cost=(cost / qty) if qty else 0.0,
                        cost_amount=cost,
                    )
                )
        return records
