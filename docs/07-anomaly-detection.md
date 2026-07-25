# Anomaly detection

## The method

`finops.analytics.anomaly.detect_anomalies` is a per-resource z-score
detector. For every `resource_id` seen within the lookback window
(48 hours by default):

1. Pull its cost history, ordered by time.
2. Split off the most recent point; treat everything before it as the
   baseline.
3. Compute the baseline's mean and standard deviation.
4. Flag the most recent point if it's more than `z_threshold` (3.0 by
   default) standard deviations above that mean.

```python
mean = baseline.mean()
std = baseline.std()
z = (latest - mean) / std
if z >= z_threshold and latest > mean:
    # flag it
```

There's a fallback for the case where `std == 0` (a resource with
perfectly flat historical cost, which happens easily in a simulator, less
often in real billing data): if the baseline had zero variance, a z-score
is undefined, so instead it just flags anything more than 3x the flat
baseline.

A resource needs at least `min_history_points` (5) observations before
it's eligible to be flagged at all - otherwise you get false positives
from resources that are brand new and simply don't have a "normal" yet
established.

## Why per-resource instead of per-service or per-account

The alternative design - compare today's total service cost to its
historical daily total - is simpler to compute but far less useful in
practice: it only catches anomalies large enough to move a whole service's
aggregate, which means a single misconfigured resource has to be a
meaningful fraction of that service's entire spend before it's visible.
Per-resource detection catches the actual failure mode FinOps anomaly
detection exists for: one thing going wrong, not the whole account.

The tradeoff is more noise surface (many more time series to evaluate) and
the cold-start problem above. Both are manageable at the scale this
project runs at; at real fleet scale (thousands to tens of thousands of
resources) you'd want to pre-aggregate or sample rather than run this
exact query - see [12-going-to-production.md](12-going-to-production.md).

## Why z-score instead of something fancier

A z-score threshold is crude compared to, say, a seasonal decomposition
model or an actual forecasting model with confidence intervals (Prophet,
ARIMA, or a hand-rolled EWMA with seasonal adjustment). It was the right
choice here for one reason: it's *explainable*. When this flags something,
you can say exactly why in one sentence - "this resource's cost is 6.2
standard deviations above what it normally costs" - and a human can verify
that in about five seconds by looking at the same numbers. Anomaly
detection that nobody trusts doesn't get acted on, and trust starts with
being able to explain a flag without hand-waving at a model. If you're
extending this for a real deployment with strong daily/weekly seasonality
(most consumer-facing services have both), you'd want to detrend/deseasonalize
before applying z-scores, or you'll get false positives every Monday
morning and false negatives during a slow weekend cost spike.

## How to see it work

```bash
finops seed --days 30      # historical data, anomalies get injected throughout
finops report --type anomalies
```

or, to watch one happen live:

```bash
finops simulate --tick-seconds 1 --max-ticks 60
```

and watch for a tick where one resource's cost jumps 5-18x - then run
`finops report --type anomalies` (against a server with `finops serve`
running, or after that simulate run has written to the DB) to see it
picked up.

Next: [08-forecasting-and-budgets.md](08-forecasting-and-budgets.md).
