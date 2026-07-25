# Roadmap / not yet covered

Things this project deliberately doesn't cover, roughly in order of how
likely I am to actually get to them:

- **Kubernetes cost allocation.** Discussed at length in
  [11-kubernetes-cost-visibility.md](11-kubernetes-cost-visibility.md) -
  the schema is designed to accommodate it but there's no allocation logic
  yet.
- **Storage lifecycle recommendations.** Flagging objects that should move
  from S3 Standard to Infrequent Access/Glacier (or the Azure/GCP
  equivalents) based on access patterns. Needs access-frequency data this
  project's cost-only model doesn't have.
- **Orphaned resource detection.** Unattached EBS volumes, unused Elastic
  IPs, old snapshots nobody's looked at in a year, load balancers with no
  registered targets. These usually show up as small individual costs that
  only become obviously wasteful in aggregate - worth a dedicated
  detector, distinct from the utilization-based idle-resource check that
  exists today.
- **Spot/preemptible recommendations.** Flagging on-demand workloads that
  tolerate interruption well (batch jobs, some CI runners, stateless
  horizontally-scaled services) as spot/preemptible candidates. Needs some
  signal about interruption tolerance that isn't in cost data alone.
- **Real multi-currency support.** Everything currently assumes USD. Real
  support means FX rate handling and deciding when a rate gets locked in
  for a given cost record - not hard, just not needed for the demo.
- **Chargeback (vs showback).** This project shows what each team/scope is
  spending; it doesn't move budget between internal cost centers or
  integrate with an actual accounting system. That's deliberately out of
  scope - see [06-cost-allocation-and-tagging.md](06-cost-allocation-and-tagging.md).
- **A second forecasting method with confidence intervals.** Both current
  methods (run-rate, linear trend) return a point estimate. A model that
  also returns a plausible range (even something simple like a
  bootstrapped confidence band) would make the "how sure are we" question
  answerable instead of implicit.
- **Wiring a real provider adapter into `finops serve` behind a flag**, so
  someone with actual AWS/Azure/GCP credentials could point this at a real
  account instead of the simulator without writing the glue code
  themselves. The adapters exist (see
  [10-multi-cloud-normalization.md](10-multi-cloud-normalization.md)); the
  CLI flag to select real vs simulated doesn't yet.

If you build any of these on top of this project, the design intent is
that they should mostly be new modules under `finops/analytics/` or
`finops/providers/` plus a new API endpoint and dashboard card - not
changes to the core schema or pipeline. If you find yourself needing to
change `CostRecord` itself, that's a sign the thing you're adding is
different enough in kind that it probably deserves its own table rather
than being squeezed into this one.
