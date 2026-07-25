# Forecasting and budgets

## Two forecasting methods

`finops.analytics.forecast` has both, because they answer slightly
different questions and disagree in informative ways.

**Run-rate** (`forecast_month_end_run_rate`): take month-to-date spend,
divide by days elapsed in the month, multiply by days in the month.

```python
daily_run_rate = month_to_date / days_elapsed
projected_month_end = daily_run_rate * days_in_month
```

This is what almost every cloud provider's own billing console shows you
as "projected spend," because it's trivial to compute and trivial to
explain. Its weakness: it assumes the rest of the month looks like the
average of the days so far, so it reacts slowly to a spend trend that's
actively accelerating or decelerating, and it can be thrown off early in
the month when `days_elapsed` is small and noisy (day 2 of a 31-day month
is a bad sample size).

**Linear trend** (`forecast_trend`): fits a straight line (`numpy.polyfit`,
degree 1) through the last `history_days` of daily totals and
extrapolates it forward `forecast_days`. This reacts to direction - a
fleet that's ramping up week over week will show a rising forecast, which
run-rate can't do until that ramp is already baked into the month-to-date
average. It needs at least 3 days of history or it returns an explicit
`{"error": "not enough history yet"}` rather than a number computed from
too little data (a 2-point "trend" is just the average of two arbitrary
values, not a trend).

Both are exposed on `GET /api/forecast` and in `finops report --type
summary` (which currently surfaces run-rate; trend is available via the
API and worth wiring into a report type if you extend this).

## Budgets

Budgets are declarative, in `config/budgets.yaml` (see
`config/budgets.example.yaml` for the format, which is what's used if you
haven't copied your own):

```yaml
budgets:
  - name: platform-team
    scope: team           # team | environment | provider | account_id
    match: platform         # the value to match within that scope
    monthly_amount: 18000
    alert_threshold_pct: 80
```

`budgets.evaluate_budgets` runs each entry as `SUM(cost_amount) WHERE
{scope} = {match} AND timestamp >= start_of_month`, then compares actual
month-to-date spend against `monthly_amount` and reuses the run-rate
method to project whether that scope will land over budget:

- `status: on_track` - under the alert threshold
- `status: warning` - at or above `alert_threshold_pct` but under 100%
- `status: over_budget` - at or above 100% of the monthly amount already

`scope` is validated against a fixed whitelist (`team`, `environment`,
`provider`, `account_id`) before it's interpolated into the SQL query -
not because budget config is untrusted input in any adversarial sense
(it's your own file), but because a typo'd scope value should raise a
clear error immediately rather than either silently produce nonsense or,
worse, get accepted as a raw column name from a config file with no
validation at all.

## Why budgets are scoped, not global

A single company-wide "don't spend more than $X" budget is close to
useless for actually changing behavior, because no individual team can see
their own contribution to it or do anything about it. Scoping budgets to
team/environment/provider/account means each one maps to a group of
people who can actually act on a warning - which is the entire point of
the "Operate" phase of FinOps (see
[01-finops-basics.md](01-finops-basics.md)): a budget alert should always
have an owner.

Next: [09-optimization-recommendations.md](09-optimization-recommendations.md).
