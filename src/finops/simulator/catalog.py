"""Reference data the simulator uses to build a fake-but-plausible fleet.

`cost_low`/`cost_high` are the per-resource, per-hour dollar cost range -
that's what actually drives cost_amount in the generator. `usage_low`/
`usage_high` are just for the usage_quantity/usage_unit fields on the
record (so the dashboard shows something like "1,200 GB" instead of a
meaningless number); they don't feed back into the cost math. Trying to
derive realistic cost from usage * a real per-unit list price gets messy
fast once you mix hourly-billed things (compute) with monthly-billed
things (storage) in the same per-hour tick loop, so we don't bother - the
hourly cost ranges below are picked to land in the right ballpark instead.
"""

from __future__ import annotations

from dataclasses import dataclass

TEAMS = ["platform", "data", "ml", "frontend"]
ENVIRONMENTS = ["prod", "staging", "dev"]


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    unit: str
    cost_low: float
    cost_high: float
    usage_low: float
    usage_high: float


PROVIDER_CATALOG: dict[str, dict] = {
    "aws": {
        "regions": ["us-east-1", "us-west-2", "eu-west-1"],
        "accounts": {
            "prod": "111122223333",
            "staging": "111122224444",
            "dev": "111122225555",
        },
        "services": [
            ServiceSpec("EC2", "hrs", 0.02, 0.60, 1, 1),
            ServiceSpec("S3", "GB-month", 0.05, 3.00, 50, 3000),
            ServiceSpec("RDS", "hrs", 0.05, 1.00, 1, 1),
            ServiceSpec("Lambda", "1M-invocations", 0.05, 2.00, 0.5, 20),
            ServiceSpec("EKS", "hrs", 0.10, 0.10, 1, 1),
            ServiceSpec("CloudFront", "GB", 0.05, 2.00, 10, 300),
            ServiceSpec("DynamoDB", "hrs", 0.03, 0.60, 1, 1),
            ServiceSpec("ElastiCache", "hrs", 0.03, 0.50, 1, 1),
        ],
    },
    "azure": {
        "regions": ["eastus", "westeurope", "southeastasia"],
        "accounts": {
            "prod": "sub-prod-2f88",
            "staging": "sub-stg-7ac1",
            "dev": "sub-dev-4e02",
        },
        "services": [
            ServiceSpec("Virtual Machines", "hrs", 0.02, 0.55, 1, 1),
            ServiceSpec("Blob Storage", "GB-month", 0.04, 2.50, 50, 3000),
            ServiceSpec("SQL Database", "hrs", 0.08, 1.10, 1, 1),
            ServiceSpec("Functions", "1M-executions", 0.05, 2.00, 0.5, 20),
            ServiceSpec("AKS", "hrs", 0.10, 0.10, 1, 1),
            ServiceSpec("CDN", "GB", 0.04, 1.80, 10, 300),
            ServiceSpec("Cosmos DB", "hrs", 0.04, 0.70, 1, 1),
            ServiceSpec("Redis Cache", "hrs", 0.03, 0.55, 1, 1),
        ],
    },
    "gcp": {
        "regions": ["us-central1", "europe-west1", "asia-southeast1"],
        "accounts": {
            "prod": "proj-prod-a91f",
            "staging": "proj-staging-b12c",
            "dev": "proj-dev-c34d",
        },
        "services": [
            ServiceSpec("Compute Engine", "hrs", 0.02, 0.50, 1, 1),
            ServiceSpec("Cloud Storage", "GB-month", 0.04, 2.80, 50, 3000),
            ServiceSpec("Cloud SQL", "hrs", 0.06, 1.05, 1, 1),
            ServiceSpec("Cloud Functions", "1M-invocations", 0.05, 2.00, 0.5, 20),
            ServiceSpec("GKE", "hrs", 0.10, 0.10, 1, 1),
            ServiceSpec("Cloud CDN", "GB", 0.04, 1.80, 10, 300),
            ServiceSpec("BigQuery", "TB-scanned", 0.10, 3.00, 0.1, 4),
            ServiceSpec("Memorystore", "hrs", 0.03, 0.60, 1, 1),
        ],
    },
}
