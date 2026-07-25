# Data model

Everything in this project is built on one schema: `CostRecord`, defined
in `src/finops/models.py`. Every provider adapter (simulated or real)
produces these, the SQLite table stores them, and every analytics function
reads them.

```python
class CostRecord(BaseModel):
    id: str                 # uuid4 hex, generated if not supplied
    timestamp: datetime      # when this cost was incurred (hourly granularity in this project)
    provider: Literal["aws", "azure", "gcp"]
    account_id: str          # AWS account / Azure subscription / GCP project
    service: str              # "EC2", "S3", "Virtual Machines", "BigQuery", etc.
    resource_id: str
    region: str
    environment: Literal["prod", "staging", "dev"]
    team: str                 # cost allocation tag - see 06-cost-allocation-and-tagging.md
    usage_type: Literal["on-demand", "reserved", "spot", "savings-plan"]
    usage_quantity: float
    usage_unit: str            # "hrs", "GB-month", "1M-invocations", etc.
    unit_cost: float
    cost_amount: float         # what actually gets summed everywhere
    currency: str = "USD"
    tags: dict[str, str]       # freeform, e.g. utilization_pct, anomaly
```

## Why this shape

The design goal was: one record type that AWS Cost Explorer, Azure Cost
Management, and GCP's BigQuery billing export can all be flattened into
without losing anything downstream analytics needs. A few choices that
fell out of that:

- **`provider` + `account_id` instead of provider-specific ID fields.**
  AWS has account IDs, Azure has subscription IDs, GCP has project IDs -
  they're conceptually the same "which bucket of the bill is this" field,
  so they share one column. If you need the original provider-native ID
  somewhere, put it in `tags`.
- **`team` is a first-class column, not just a tag.** In practice, "which
  team owns this cost" is the single most common way people slice a bill,
  so it gets to be a real column with a real index rather than something
  you have to parse out of a tags blob on every query. `environment` gets
  the same treatment for the same reason.
- **`tags` is a genuinely freeform escape hatch.** Stored as a JSON blob
  (`tags_json` in SQLite) rather than a separate key-value table, because
  at this project's scale a normalized tags table buys nothing but joins.
  The simulator uses it for `utilization_pct` (used by
  `optimization.find_idle_resources`) and `anomaly` (a debug marker, not
  what the actual anomaly detector relies on - see
  [07-anomaly-detection.md](07-anomaly-detection.md)).
- **`cost_amount` is always in USD.** Real multi-currency billing is a
  whole additional problem (FX rates, when they're locked in, rounding)
  that's out of scope here - see [13-roadmap.md](13-roadmap.md).

## Storage

SQLite, one table, defined in `finops/storage/db.py`:

```sql
CREATE TABLE cost_records (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    provider TEXT,
    account_id TEXT,
    service TEXT,
    resource_id TEXT,
    region TEXT,
    environment TEXT,
    team TEXT,
    usage_type TEXT,
    usage_quantity REAL,
    usage_unit TEXT,
    unit_cost REAL,
    cost_amount REAL,
    currency TEXT,
    tags_json TEXT
);
```

with indexes on `timestamp`, `service`, `team`, `provider`, and
`environment` - those are the columns every query in `analytics/` filters
or groups on. `timestamp` is stored as an ISO-8601 string rather than a
SQLite native datetime (SQLite doesn't have one) - `substr(timestamp, 1,
10)` is used in `aggregation.daily_trend` to bucket by day, which works
because ISO-8601 sorts and truncates lexicographically the same way it
sorts chronologically.

This is a demo-scale choice; a production version of this would very
likely want columnar storage (see
[12-going-to-production.md](12-going-to-production.md)) since cost
analytics workloads are almost entirely "sum/group by over a large
time-partitioned table," which is exactly what columnar engines are built
for.

Next: [04-getting-started.md](04-getting-started.md) to actually run this.
