# Multi-cloud normalization (and swapping in real data)

## The problem

AWS, Azure, and GCP each expose cost data through a completely different
API shape, with different granularity guarantees, different dimension
names for conceptually identical things, and different quirks:

| | AWS | Azure | GCP |
|---|---|---|---|
| API | Cost Explorer (`GetCostAndUsage`) | Cost Management query API | No direct query API - BigQuery billing export |
| Finest granularity | Daily | Daily | Whatever your export/query does, but source data is effectively daily-ish |
| "Which account" | Account ID | Subscription ID | Project ID |
| Grouping dimensions | `SERVICE`, `REGION`, tags, etc. | `ServiceName`, `ResourceLocation`, tags | Whatever columns you select from the export table |

None of the three give you a true sub-hourly cost stream over an API -
that's exactly why this project's "real-time" layer is a simulator rather
than a live feed from any of them (see
[00-overview.md](00-overview.md)). What they *do* give you, in different
shapes, is periodic (daily, sometimes hourly for some services) cost and
usage data that can be normalized into the same `CostRecord` schema this
project already uses everywhere downstream.

## The adapter interface

`finops.providers.base.CostAdapter` is the contract:

```python
class CostAdapter(ABC):
    provider: str

    @abstractmethod
    def fetch_historical(self, start: datetime, end: datetime) -> list[CostRecord]: ...

    @abstractmethod
    def next_tick(self, at: datetime) -> list[CostRecord]: ...
```

`finops.simulator.generator.FleetSimulator` doesn't literally implement
this interface (it has a slightly different method shape suited to
building/advancing a fake fleet), but the three real adapters do:

- `finops.providers.aws.CostExplorerAdapter` - wraps `boto3`'s
  `ce.get_cost_and_usage`, grouped by `SERVICE` and `REGION`.
- `finops.providers.azure.CostManagementAdapter` - wraps
  `azure.mgmt.costmanagement`'s `query.usage`, grouped by `ServiceName`
  and `ResourceLocation`.
- `finops.providers.gcp.BillingExportAdapter` - runs a parameterized
  BigQuery SQL query against your billing export dataset (GCP requires you
  to enable billing export to BigQuery yourself; there's no equivalent to
  "call an API and get your bill").

None of these are wired into `finops serve` by default, and none of them
are covered by the test suite (they need real credentials to run against
real services - see each module's docstring for exactly what SDK and
permissions they need). They exist so the swap from "demo mode" to "your
real AWS/Azure/GCP bill" is a matter of writing the wiring code, not
redesigning the schema.

## What it would take to wire one in for real

Using AWS as the example:

1. `pip install boto3` and set up credentials with `ce:GetCostAndUsage`
   (read-only, account- or org-level depending on what you want visibility
   into).
2. In `finops/api/app.py`'s lifespan function, replace the
   `FleetSimulator` + `run_live` background thread with something that
   periodically calls `CostExplorerAdapter(account_id).fetch_historical(...)`
   and inserts the results the same way `db.insert_records` already does.
   Since Cost Explorer only reports daily, "real-time" for a real AWS bill
   realistically means "refreshed every few hours," not every 5 seconds -
   there's no way around that with this API.
3. Everything else - `finops/analytics/*`, the REST API, the dashboard -
   needs zero changes, because they only ever operate on rows in
   `cost_records`, regardless of where those rows came from.

The same shape applies to Azure and GCP, swapping in
`CostManagementAdapter` or `BillingExportAdapter` respectively. If you want
all three running simultaneously against real accounts (genuinely
multi-cloud, not just multi-cloud-shaped), you'd run all three adapters on
independent schedules and let them all write into the same
`cost_records` table - which is exactly what the schema was designed for.

Next: [11-kubernetes-cost-visibility.md](11-kubernetes-cost-visibility.md).
