# Getting started

## Requirements

- Python 3.10+
- Nothing else - SQLite ships with Python, and there's no cloud account or
  external service needed to run the demo.

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -e .
```

That last command installs the `finops` CLI entry point in editable mode.
If you'd rather not install it, every command below also works as
`python -m finops.cli <command>`.

## First run

```bash
finops init-db
finops seed --days 30
finops report --type summary
```

`init-db` creates `data/finops.db` (path configurable via
`FINOPS_DB_PATH`, see `.env.example`). `seed` backfills 30 days of hourly
simulated cost data - about 180 simulated resources across AWS, Azure, and
GCP, roughly 130k records - so the dashboard has history to show instead
of being empty. `report --type summary` gives you a quick sanity check
from the terminal:

```
month_to_date_cost  method    month_to_date  days_elapsed  days_in_month  daily_run_rate  projected_month_end
-------------------------------------------------------------------------------------------------------------
62348.68             run_rate  62348.68       24.71          31             2523.47         78227.45
```

## Running the dashboard

```bash
finops serve
```

Then open http://127.0.0.1:8000. This starts the FastAPI app *and* a
background thread that keeps advancing the simulator in real time (one
simulated hour every 5 real seconds by default), so the dashboard's live
feed and summary numbers keep moving while it's running. See
[05-real-time-pipeline.md](05-real-time-pipeline.md) for how that works.

Useful flags:

```bash
finops serve --port 8080          # different port
finops serve --reload             # auto-reload on code changes (dev only)
```

## Other CLI commands

```bash
finops report --type by-service --days 7 --format json
finops report --type anomalies
finops report --type budgets
finops report --type idle --days 7
finops report --type commitments --days 14

finops simulate --tick-seconds 1 --max-ticks 20   # run the simulator standalone, print each tick, no server
```

`finops report --type` accepts: `summary`, `by-provider`, `by-service`,
`by-team`, `by-environment`, `anomalies`, `budgets`, `idle`,
`commitments`. `--format` is `table` (default) or `json`.

## Setting your own budgets

Budgets live in `config/budgets.yaml`, which is gitignored - copy the
example to get started:

```bash
cp config/budgets.example.yaml config/budgets.yaml
```

Then edit the `monthly_amount` and `alert_threshold_pct` values. If you
don't copy it, the app falls back to reading `budgets.example.yaml`
directly so the demo still works out of the box - see
[08-forecasting-and-budgets.md](08-forecasting-and-budgets.md) for the
budget scope/matching format.

## Running the tests

```bash
pytest
```

24 tests, no external services or network access required - they use a
temporary SQLite file per test (see `tests/conftest.py`).

Next: [05-real-time-pipeline.md](05-real-time-pipeline.md).
