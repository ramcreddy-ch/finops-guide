# The real-time pipeline

## The fleet

`finops.simulator.generator.FleetSimulator` builds a fixed set of simulated
resources once, at startup (`_build_fleet`), then advances all of them by
one "tick" at a time. A tick represents one simulated hour, regardless of
how much real wall-clock time passes between ticks - that separation
(simulated time vs real time) is what lets `finops seed --days 30` produce
30 days of hourly history in a couple of seconds, while `finops serve`
advances at a human-watchable pace (one tick per 5 real seconds by
default, via `tick_seconds`).

The fleet isn't evenly distributed - production environments get 3-6
resources per service per provider, staging and dev get 1-2. That's
deliberate: a fleet where dev and prod have exactly the same footprint
doesn't look like any real company's cloud bill, and it made every
environment-scoped budget in the demo either meaninglessly slack or
meaninglessly tight.

## What makes a tick interesting

Three things happen every tick that make this more than a random number
generator:

1. **Idle resources stay idle.** About 8% of resources are marked
   `is_idle` at fleet-build time. They get billed at essentially the
   normal rate every tick (real cloud providers don't discount you for
   under-utilizing something you provisioned) but their `utilization_pct`
   tag stays in the low single digits. That's what
   `optimization.find_idle_resources` looks for - see
   [09-optimization-recommendations.md](09-optimization-recommendations.md).
2. **Non-prod usage drops outside business hours.** For staging/dev
   resources, cost gets scaled down to 15-35% of normal outside
   08:00-19:00. This is meant to mirror the (very common, very sensible)
   practice of scaling down or stopping non-prod environments overnight
   and on weekends - and it's also what gives the daily trend chart a
   visible wave shape instead of a flat line.
3. **Anomalies get injected.** Each tick has a small chance
   (`anomaly_probability_per_tick`, 1% by default) of picking a random
   resource and multiplying its cost by 5-18x for 2-6 ticks - simulating
   something like a runaway autoscaling group, an infinite retry loop
   hammering a paid API, or a misconfigured batch job. This is what
   `anomaly.detect_anomalies` is meant to catch (and it catches it based
   on the cost data itself via z-scores, not by reading the `anomaly` tag
   the simulator happens to set - that tag exists for debugging, not as a
   shortcut for the detector).

## Backfill vs live

`finops.ingestion.pipeline` has two entry points:

- **`backfill(conn, simulator, start, end, tick_delta)`** - walks the
  entire window in a tight loop, no sleeping. Used by `finops seed`.
- **`run_live(conn, simulator, tick_seconds, tick_delta, on_tick,
  stop_event)`** - same tick-generation logic, but sleeps `tick_seconds`
  between ticks and calls `on_tick` with each batch. Used by `finops
  serve` (with `on_tick` wired to the websocket broadcaster) and `finops
  simulate` (with `on_tick` wired to a print statement).

Both call the exact same `simulator.tick(at)` method - there's no separate
"backfill mode" logic to keep in sync with "live mode" logic, they're the
same code path at different speeds.

`run_live` picks up where the database left off: it reads
`MAX(timestamp)` from `cost_records` and continues from there, so running
`finops seed --days 30` and then `finops serve` gives you a continuous
timeline instead of a gap or an overlap.

## The websocket

`finops/api/app.py` has a `Broadcaster` class that holds the set of
connected websocket clients. The tricky part is that `run_live` executes
on a plain background thread (see [02-architecture.md](02-architecture.md)
for why), but sending over a websocket is an async operation that has to
run on FastAPI's event loop. `Broadcaster.publish` bridges that gap with
`asyncio.run_coroutine_threadsafe`, which schedules the actual send
coroutine onto the loop from a non-async thread. If a client disconnects
mid-broadcast, `_broadcast` just drops it from the client set rather than
propagating the exception - a live dashboard closing its tab shouldn't
crash the tick loop for everyone else.

Next: [06-cost-allocation-and-tagging.md](06-cost-allocation-and-tagging.md).
