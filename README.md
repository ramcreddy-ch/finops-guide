# finops-guide

A real-time-ish FinOps cost management platform for multi-cloud
environments (AWS, Azure, GCP), built to demonstrate the whole loop a
FinOps/platform team actually runs: continuous cost ingestion, live
dashboards, anomaly detection, month-end forecasting, budget tracking, and
optimization recommendations (idle resources, commitment coverage).

It runs entirely locally with no cloud account required - a built-in
multi-cloud simulator generates realistic, continuously-streaming cost
data (with deliberately injected waste and anomalies) so every piece of
analytics has real data to work against. The provider adapter layer for
wiring in an actual AWS/Azure/GCP bill is there too, just not switched on
by default - see [docs/10-multi-cloud-normalization.md](docs/10-multi-cloud-normalization.md).

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -e .

finops init-db
finops seed --days 30
finops serve
```

Then open http://127.0.0.1:8000. The dashboard updates live - a
background simulator keeps producing new cost events every few seconds and
pushes them over a websocket while you watch.

```bash
pytest                                   # 24 tests, no external deps
finops report --type summary             # quick terminal check
finops report --type anomalies
finops report --type idle --days 7
```

## What's in the dashboard

- Today's spend, month-to-date, projected month-end (run-rate forecast),
  active anomaly count
- Cost broken down by provider and by service (7-day window)
- 30-day daily spend trend
- Live-detected anomalies (z-score based, per-resource)
- Budget status per team/environment against `config/budgets.yaml`
- Idle/underutilized resources with projected monthly waste
- Reserved instance / savings plan opportunities with estimated savings
- A live feed of raw cost ticks as they're generated

## Why this exists

Most FinOps demos are a static chart of last month's bill. This tries to
model the actual operating loop - continuous ingestion, live alerting,
budget accountability, and concrete optimization findings - because that
loop, not the dashboard, is what a real FinOps practice is. See
[docs/01-finops-basics.md](docs/01-finops-basics.md) if you want the
FinOps background this project is built around, or
[docs/00-overview.md](docs/00-overview.md) for what's simulated vs real
and where to start reading.

## Documentation

Full docs, ordered basics to advanced, live in [docs/](docs/00-overview.md):

| Doc | Covers |
|---|---|
| [00-overview.md](docs/00-overview.md) | What's real vs simulated, reading order |
| [01-finops-basics.md](docs/01-finops-basics.md) | FinOps concepts, vocabulary |
| [02-architecture.md](docs/02-architecture.md) | How the pieces fit together |
| [03-data-model.md](docs/03-data-model.md) | The `CostRecord` schema |
| [04-getting-started.md](docs/04-getting-started.md) | Full setup + CLI reference |
| [05-real-time-pipeline.md](docs/05-real-time-pipeline.md) | The simulator + streaming/websocket internals |
| [06-cost-allocation-and-tagging.md](docs/06-cost-allocation-and-tagging.md) | Showback, tagging |
| [07-anomaly-detection.md](docs/07-anomaly-detection.md) | The z-score detector |
| [08-forecasting-and-budgets.md](docs/08-forecasting-and-budgets.md) | Forecast methods, budget config |
| [09-optimization-recommendations.md](docs/09-optimization-recommendations.md) | Idle resources, commitment coverage |
| [10-multi-cloud-normalization.md](docs/10-multi-cloud-normalization.md) | Swapping in real AWS/Azure/GCP data |
| [11-kubernetes-cost-visibility.md](docs/11-kubernetes-cost-visibility.md) | Advanced topic, not implemented - why it's hard |
| [12-going-to-production.md](docs/12-going-to-production.md) | What changes at real scale |
| [13-roadmap.md](docs/13-roadmap.md) | What's not covered yet |

## Project layout

```
src/finops/
  models.py         CostRecord - the shared schema
  providers/        AWS/Azure/GCP adapters (simulated + real)
  simulator/         Multi-cloud cost/usage generator
  storage/           SQLite schema + connection helpers
  ingestion/         Backfill + live streaming pipeline
  analytics/         Aggregation, anomaly detection, forecasting, budgets, optimization
  api/               FastAPI app - REST + /ws/live websocket
  web/               Dashboard (Jinja2 + Chart.js)
  cli.py             `finops` command line entry point
tests/               pytest suite, no external services needed
config/              budgets.example.yaml
docs/                basics-to-advanced documentation
```

## License

MIT - see [LICENSE](LICENSE).
