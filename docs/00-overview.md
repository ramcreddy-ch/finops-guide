# finops-guide

This is a self-contained FinOps cost management platform: a multi-cloud cost
simulator, a SQLite-backed ingestion pipeline, analytics (aggregation,
anomaly detection, forecasting, budgets, optimization recommendations), a
REST + websocket API, and a live dashboard - all in Python, all runnable on
a laptop with no cloud account required.

I built this to put together, end to end, the kind of tooling a FinOps or
platform team actually maintains: something that ingests cost data
continuously, tells you what you're spending right now, flags when
something's gone wrong, projects where you'll land at month end, and points
at concrete waste. Most FinOps write-ups stop at "here's a dashboard
showing last month's AWS bill." This tries to cover the whole loop,
including the parts that are less about dashboards and more about process
(budgets, tagging discipline, chargeback) - because that's most of what
FinOps actually is in practice.

## What's actually here vs what's illustrative

To be upfront about scope: the "real-time" data is a simulator
(`finops/simulator/`), not a live AWS/Azure/GCP bill. Real billing data
doesn't stream at sub-hourly granularity from any provider's API, and
requiring real cloud credentials would make this unrunnable for anyone
without three cloud accounts sitting around. The simulator produces
plausible multi-cloud spend - realistic service names, regions, cost
ranges, and (deliberately) injected waste and anomalies - so every piece of
analytics downstream has real data to chew on and the numbers you see are
internally consistent, not random.

The provider adapter interface (`finops/providers/`) is real, though: the
`CostExplorerAdapter`, `CostManagementAdapter`, and `BillingExportAdapter`
classes call actual AWS Cost Explorer, Azure Cost Management, and GCP
BigQuery billing export APIs. They're just not wired into the running
system by default, since that would need your credentials. See
[10-multi-cloud-normalization.md](10-multi-cloud-normalization.md) for how
to switch from simulated to real.

## Reading order

If you're new to FinOps as a discipline, start at
[01-finops-basics.md](01-finops-basics.md) and read forward - each doc
builds on the last, roughly basics to advanced:

1. [FinOps basics](01-finops-basics.md) - what FinOps is and isn't
2. [Architecture](02-architecture.md) - how the pieces fit together
3. [Data model](03-data-model.md) - the CostRecord schema everything else builds on
4. [Getting started](04-getting-started.md) - running it locally
5. [Real-time pipeline](05-real-time-pipeline.md) - how the streaming/ingestion works
6. [Cost allocation and tagging](06-cost-allocation-and-tagging.md)
7. [Anomaly detection](07-anomaly-detection.md)
8. [Forecasting and budgets](08-forecasting-and-budgets.md)
9. [Optimization recommendations](09-optimization-recommendations.md)
10. [Multi-cloud normalization](10-multi-cloud-normalization.md) - and swapping in real provider data
11. [Kubernetes cost visibility](11-kubernetes-cost-visibility.md) - advanced topic, not implemented here
12. [Going to production](12-going-to-production.md) - what would need to change to run this for real
13. [Roadmap](13-roadmap.md)

If you just want to run it, skip to
[04-getting-started.md](04-getting-started.md).
