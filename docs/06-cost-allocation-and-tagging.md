# Cost allocation and tagging

This is the least glamorous part of FinOps and also the part that
determines whether everything else in this repo is useful. Anomaly
detection, budgets, and optimization recommendations are only as good as
the labels attached to the underlying resources - if half your fleet has
no `team` tag, half your budget report is a bucket labeled "unassigned"
that nobody is accountable for.

## What this project tags every record with

Every `CostRecord` carries, as real columns rather than optional
metadata:

- `team` - which team owns the resource (`platform`, `data`, `ml`,
  `frontend` in the simulator)
- `environment` - `prod`, `staging`, or `dev`
- `provider`, `account_id`, `region` - where it runs
- `tags` - a freeform dict for anything else (`utilization_pct`,
  `anomaly` in this project; in a real system this is where you'd put
  cost-center codes, product lines, whatever your org's chargeback model
  needs)

Promoting `team` and `environment` to real columns (instead of leaving
them buried in a generic tags map) was a deliberate tradeoff: it makes the
schema less flexible but every budget/aggregation query in this repo
faster and easier to write correctly, since SQLite can index and filter on
them directly. See [03-data-model.md](03-data-model.md) for the reasoning.

## Why tagging is hard in the real world (and how this project sidesteps it)

In a real cloud account, tags are optional, inconsistently applied,
sometimes overwritten by IaC tooling that doesn't know about your tagging
convention, and often missing entirely on resources created through the
console by someone in a hurry. A real FinOps practice spends a lot of its
early effort just getting tag coverage up - tagging policies, automated
tag enforcement (AWS Config rules, Azure Policy, GCP Organization
Policies), and just-in-time nudges when someone creates something
untagged.

The simulator here doesn't model that problem - every simulated resource
is tagged from the moment it's created, because the point of this project
is to demonstrate what you do *with* well-tagged cost data, not to
simulate the (very real, very tedious) process of getting there. If you're
adapting this for an actual cost pipeline, budget real time for tag
enforcement before your `cost_by_dimension("team", ...)` numbers mean
anything.

## Showback with what's here

`aggregation.cost_by_dimension(conn, "team", since)` and the equivalent
for `environment`/`provider`/`region`/`account_id` are the showback
primitive - "here's what each team is actually spending," with no money
moving between budgets. The dashboard's provider/service charts and the
CLI's `finops report --type by-team` are both just this function with
different dimensions. Chargeback (actually debiting internal budgets)
isn't implemented here since it's an accounting/billing-system
integration problem, not an analytics one - see
[13-roadmap.md](13-roadmap.md).

Next: [07-anomaly-detection.md](07-anomaly-detection.md).
