# FinOps basics

## What FinOps actually is

FinOps (financial operations, sometimes "cloud financial management") is
the practice of bringing engineering, finance, and business teams together
around cloud spend so that decisions about cost get made by the people
who understand both the bill and the workload. It's not a tool and it's
not a report you send out once a month - it's an operating model. The
[FinOps Foundation](https://www.finops.org/) organizes it around three
phases that repeat continuously:

- **Inform** - get everyone visibility into what's being spent, broken
  down in a way that maps to how the organization thinks (by team, by
  product, by environment), and make sure that visibility is trustworthy.
- **Optimize** - once people can see the spend, find and act on waste:
  rightsizing, commitment discounts, cleaning up orphaned resources,
  choosing cheaper storage tiers, etc.
- **Operate** - make the whole thing routine: budgets with real
  consequences, anomaly alerting, regular reviews, cost as a
  first-class input to architecture decisions rather than an
  afterthought discovered at the end of the month.

None of these phases are ever "done" - a healthy FinOps practice cycles
through all three continuously as the infrastructure and the org change.

## Why cloud cost is a different problem than on-prem cost

With on-prem infrastructure, most of the cost decisions get made once (at
purchase time) and then amortized. With cloud, every single API call that
provisions or scales something is a spending decision, made constantly, by
people (or autoscalers) who usually aren't looking at a price tag when they
make it. That's the whole reason this discipline exists: the friction
between spending money and knowing you're spending it that used to exist
with procurement is gone, which is great for velocity and bad for cost
control unless something fills that gap. FinOps is what fills the gap.

## The vocabulary you'll see throughout this repo

- **Showback vs chargeback** - showback means showing a team what their
  infrastructure costs without actually billing them for it internally;
  chargeback means actually moving budget between internal cost centers
  based on usage. Showback is the easier first step and is usually where
  organizations start.
- **Unit economics** - cost per some meaningful business unit (cost per
  customer, cost per request, cost per transaction) rather than raw
  dollars. Raw spend going up is only bad news if it's not tracking with
  growth; unit economics is how you tell the difference.
- **Committed use / reserved instances / savings plans** - discounts in
  exchange for committing to a baseline spend level over a term (usually
  1-3 years). The tradeoff is discount vs flexibility, and getting the mix
  right is one of the most mechanical, high-leverage things a FinOps
  practice does. See [09-optimization-recommendations.md](09-optimization-recommendations.md).
  for how this project estimates commitment coverage opportunities.
- **Rightsizing** - matching resource size to actual load. The classic
  case is a compute instance running at 4% CPU utilization 24/7 that was
  sized for a peak load that never happens, or that nobody has revisited
  since a workload changed.
- **Tagging / cost allocation** - attaching metadata (team, environment,
  cost center, product) to resources so cost can be sliced by anything
  other than "the whole AWS bill." Tagging discipline is the unglamorous
  foundation everything else in this doc is built on - see
  [06-cost-allocation-and-tagging.md](06-cost-allocation-and-tagging.md).

## Where this project fits

This repo is a working model of the "Inform" and "Optimize" phases end to
end, plus a chunk of "Operate" (budgets, anomaly alerting). It won't
replace an actual FinOps practice - that's a cross-team process, not
software - but it demonstrates the kind of tooling that practice runs on:

| FinOps concept | Where it lives in this repo |
|---|---|
| Inform / visibility | `finops/analytics/aggregation.py`, dashboard charts |
| Tagging / allocation | `team`, `environment`, `tags` fields on `CostRecord` |
| Anomaly detection | `finops/analytics/anomaly.py` |
| Forecasting | `finops/analytics/forecast.py` |
| Budgets / accountability | `finops/analytics/budgets.py`, `config/budgets.yaml` |
| Rightsizing | `finops/analytics/optimization.py::find_idle_resources` |
| Commitment coverage | `finops/analytics/optimization.py::recommend_commitment_coverage` |

Next: [02-architecture.md](02-architecture.md) for how these pieces are
actually wired together.
