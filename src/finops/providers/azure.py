"""Azure cost data source.

Same split as finops.providers.aws: the simulator drives the demo, and
CostManagementAdapter is the real integration point for anyone who wants to
point this at an actual Azure subscription. It needs `azure-mgmt-costmanagement`
and `azure-identity`, neither of which are in requirements.txt since they're
only needed if you go down this path.
"""

from __future__ import annotations

from datetime import datetime

from finops.models import CostRecord
from finops.providers.base import CostAdapter


class CostManagementAdapter(CostAdapter):
    """Pulls real cost data from Azure Cost Management's query API.

    Needs AZURE_SUBSCRIPTION_ID plus a service principal
    (AZURE_TENANT_ID/AZURE_CLIENT_ID/AZURE_CLIENT_SECRET) with Cost
    Management Reader on the subscription.
    """

    provider = "azure"

    def __init__(self, subscription_id: str) -> None:
        self.subscription_id = subscription_id
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.costmanagement import CostManagementClient
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "CostManagementAdapter needs azure-identity and "
                "azure-mgmt-costmanagement. Install both if you want real "
                "Azure data."
            ) from exc

        credential = DefaultAzureCredential()
        self._client = CostManagementClient(credential)

    def fetch_historical(self, start: datetime, end: datetime) -> list[CostRecord]:
        scope = f"/subscriptions/{self.subscription_id}"
        query = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": start.isoformat(), "to": end.isoformat()},
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                "grouping": [
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "ResourceLocation"},
                ],
            },
        }
        result = self._client.query.usage(scope=scope, parameters=query)
        return self._parse_response(result)

    def next_tick(self, at: datetime) -> list[CostRecord]:
        from datetime import timedelta

        return self.fetch_historical(at - timedelta(days=1), at)

    def _parse_response(self, result) -> list[CostRecord]:
        records: list[CostRecord] = []
        columns = [c.name for c in result.columns]
        for row in result.rows:
            data = dict(zip(columns, row))
            records.append(
                CostRecord(
                    timestamp=datetime.fromisoformat(str(data.get("UsageDate"))),
                    provider="azure",
                    account_id=self.subscription_id,
                    service=data.get("ServiceName", "unknown"),
                    resource_id=f"{data.get('ServiceName', 'unknown')}-aggregate",
                    region=data.get("ResourceLocation", "global"),
                    environment="prod",
                    team="unassigned",
                    usage_type="on-demand",
                    usage_quantity=1.0,
                    usage_unit="unit",
                    unit_cost=float(data.get("Cost", 0.0)),
                    cost_amount=float(data.get("Cost", 0.0)),
                )
            )
        return records
