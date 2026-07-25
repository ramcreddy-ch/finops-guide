# Optimization recommendations

This is the "Optimize" phase of FinOps: once you can see spend clearly
(Inform) and you've got budgets and anomaly alerts running (Operate), the
actual savings come from acting on two categories of finding.
`finops.analytics.optimization` implements both.

## Idle / underutilized resources

`find_idle_resources(conn, lookback_days=7, utilization_threshold_pct=10.0)`
looks at every resource that has a `utilization_pct` tag (in this project,
that's anything billed by the hour - EC2, RDS, VMs, managed Kubernetes
control planes, cache instances), averages that utilization over the
lookback window, and flags anything averaging below the threshold. For
each flagged resource it projects a monthly cost
(`observed_cost / lookback_days * 30`) so the finding comes with a dollar
figure attached, not just a percentage.

This is deliberately the single most common real-world FinOps finding:
someone provisioned a compute resource sized for peak load, or for a
launch that didn't happen, or for a service that was later decommissioned
without decommissioning its infrastructure - and it's been sitting there
running (and billing) at 2-4% utilization ever since. Cloud providers will
never proactively tell you this; nothing about a running-but-idle instance
looks different in the billing API from a busy one. Finding it requires
looking at utilization alongside cost, which is exactly what this function
does.

The recommendation text is intentionally generic ("rightsize or terminate
- sustained low utilization") rather than prescribing a specific instance
size, because picking the right target size needs information this
project doesn't model (actual CPU/memory profiles, peak-vs-average load,
whether the workload is latency-sensitive). A real implementation would
pull that from CloudWatch/Azure Monitor/Cloud Monitoring metrics, not from
the billing data alone.

## Commitment coverage

`recommend_commitment_coverage(conn, lookback_days=14, min_on_demand_cost=50.0)`
groups spend by `(provider, service, usage_type)` and looks for services
where on-demand usage is both a meaningful dollar amount
(`min_on_demand_cost`) and a large share (>40%) of that service's total
spend. Steady, predictable on-demand usage is exactly what reserved
instances, savings plans, and committed use discounts are priced to
reward - if a service is running mostly on-demand at steady volume, that's
money being left on the table every month.

The estimated savings use a flat assumed 30% discount
(`ASSUMED_COMMITMENT_DISCOUNT`). Real discounts vary by term length (1 vs
3 years), payment option (all upfront vs partial vs no upfront), and
provider/instance family - anywhere from roughly 20% to 60%+ for
longer-term, more restrictive commitments. 30% is a reasonable
middle-of-the-road planning number, not a quote. The point of this
function is to flag *where* to go get a real quote, not to be one.

## Why these two checks and not more

Real FinOps optimization work covers a lot more ground: storage tier
transitions (S3 Standard -> Infrequent Access -> Glacier), orphaned
snapshots and unattached volumes, oversized load balancers, data transfer
cost between regions/AZs, spot instance opportunities for
interruption-tolerant workloads, license optimization (BYOL vs
included licensing), and more. This project covers idle resources and
commitment coverage because they're the two findings that (a) apply
almost universally regardless of what the workload actually does, and
(b) are cleanly derivable from cost + a utilization tag, without needing
provider-specific APIs for volumes, snapshots, or storage class metadata.
See [13-roadmap.md](13-roadmap.md) for what's not covered.

Next: [10-multi-cloud-normalization.md](10-multi-cloud-normalization.md).
