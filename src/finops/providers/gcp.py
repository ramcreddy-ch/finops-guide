"""GCP cost data source.

Google doesn't expose a clean "get me cost by service" REST API the way AWS
and Azure do - the recommended path is enabling BigQuery billing export and
querying it. That's what BillingExportAdapter does below. Needs
`google-cloud-bigquery` and a service account with BigQuery Data Viewer on
the billing export dataset.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from finops.models import CostRecord
from finops.providers.base import CostAdapter

_QUERY_TEMPLATE = """
SELECT
  service.description AS service,
  location.region AS region,
  project.id AS project_id,
  SUM(cost) AS cost,
  SUM(usage.amount) AS usage_amount,
  usage.unit AS usage_unit,
  DATE(usage_start_time) AS usage_date
FROM `{table}`
WHERE DATE(usage_start_time) BETWEEN @start AND @end
GROUP BY service, region, project_id, usage_unit, usage_date
"""


class BillingExportAdapter(CostAdapter):
    provider = "gcp"

    def __init__(self, project_id: str, billing_export_table: str) -> None:
        self.project_id = project_id
        self.table = billing_export_table
        try:
            from google.cloud import bigquery
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "BillingExportAdapter needs google-cloud-bigquery. Install "
                "it if you want real GCP billing export data."
            ) from exc

        self._client = bigquery.Client(project=project_id)
        self._bigquery = bigquery

    def fetch_historical(self, start: datetime, end: datetime) -> list[CostRecord]:
        job_config = self._bigquery.QueryJobConfig(
            query_parameters=[
                self._bigquery.ScalarQueryParameter("start", "DATE", start.date()),
                self._bigquery.ScalarQueryParameter("end", "DATE", end.date()),
            ]
        )
        query = _QUERY_TEMPLATE.format(table=self.table)
        rows = self._client.query(query, job_config=job_config).result()
        return self._parse_rows(rows)

    def next_tick(self, at: datetime) -> list[CostRecord]:
        return self.fetch_historical(at - timedelta(days=1), at)

    def _parse_rows(self, rows) -> list[CostRecord]:
        records: list[CostRecord] = []
        for row in rows:
            qty = float(row.usage_amount or 0)
            cost = float(row.cost or 0)
            records.append(
                CostRecord(
                    timestamp=datetime.combine(row.usage_date, datetime.min.time()),
                    provider="gcp",
                    account_id=row.project_id or self.project_id,
                    service=row.service or "unknown",
                    resource_id=f"{row.service}-aggregate",
                    region=row.region or "global",
                    environment="prod",
                    team="unassigned",
                    usage_type="on-demand",
                    usage_quantity=qty,
                    usage_unit=row.usage_unit or "unit",
                    unit_cost=(cost / qty) if qty else 0.0,
                    cost_amount=cost,
                )
            )
        return records
