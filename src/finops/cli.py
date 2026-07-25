"""Command-line entry point. Run `finops --help` (or `python -m finops.cli
--help` if you haven't installed the package) to see everything below.

Typical first run:

    finops init-db
    finops seed --days 30
    finops report --type summary
    finops serve
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from finops.analytics import aggregation, anomaly, budgets, forecast, optimization
from finops.ingestion.pipeline import backfill, run_live
from finops.simulator.generator import FleetSimulator
from finops.storage import db


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("(no rows)")
        return
    columns = list(rows[0].keys())
    widths = [max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in columns]
    header = "  ".join(c.ljust(w) for c, w in zip(columns, widths))
    print(header)
    print("-" * len(header))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(w) for c, w in zip(columns, widths)))


def cmd_init_db(args: argparse.Namespace) -> None:
    db.init_db()
    print(f"initialized database at {db.db_path()}")


def cmd_seed(args: argparse.Namespace) -> None:
    db.init_db()
    conn = db.get_connection()
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=args.days)
        simulator = FleetSimulator(seed=args.seed)
        print(f"seeding ~{args.days} days of hourly data across {simulator.fleet_size()} simulated resources...")
        count = backfill(conn, simulator, start, end, tick_delta=timedelta(hours=args.tick_hours))
        print(f"inserted {count} cost records")
    finally:
        conn.close()


def cmd_simulate(args: argparse.Namespace) -> None:
    db.init_db()
    conn = db.get_connection()
    try:
        simulator = FleetSimulator(seed=args.seed)

        def on_tick(records):
            total = sum(r.cost_amount for r in records)
            ts = records[0].timestamp if records else "?"
            print(f"[{ts}] {len(records)} records, ${total:,.2f}")

        run_live(
            conn,
            simulator,
            tick_seconds=args.tick_seconds,
            tick_delta=timedelta(hours=args.tick_hours),
            on_tick=on_tick,
            max_ticks=args.max_ticks,
        )
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        conn.close()


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("finops.api.app:app", host=args.host, port=args.port, reload=args.reload)


def cmd_report(args: argparse.Namespace) -> None:
    db.init_db()
    conn = db.get_connection()
    try:
        since = datetime.utcnow() - timedelta(days=args.days)

        if args.type == "summary":
            data = {
                "month_to_date_cost": aggregation.month_to_date_cost(conn),
                **forecast.forecast_month_end_run_rate(conn),
            }
            rows = [data]
        elif args.type in ("by-provider", "by-service", "by-team", "by-environment"):
            dimension = args.type.split("-")[1]
            rows = aggregation.cost_by_dimension(conn, dimension, since)
        elif args.type == "anomalies":
            rows = anomaly.detect_anomalies(conn)
        elif args.type == "budgets":
            rows = budgets.evaluate_budgets(conn)
        elif args.type == "idle":
            rows = optimization.find_idle_resources(conn, lookback_days=args.days)
        elif args.type == "commitments":
            rows = optimization.recommend_commitment_coverage(conn, lookback_days=args.days)
        else:
            print(f"unknown report type: {args.type}", file=sys.stderr)
            sys.exit(1)

        if args.format == "json":
            print(json.dumps(rows, indent=2, default=str))
        else:
            _print_table(rows)
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finops", description="Real-time FinOps cost management demo")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="create the sqlite schema")
    p_init.set_defaults(func=cmd_init_db)

    p_seed = sub.add_parser("seed", help="backfill historical cost data so the dashboard isn't empty")
    p_seed.add_argument("--days", type=int, default=30)
    p_seed.add_argument("--tick-hours", type=float, default=1.0)
    p_seed.add_argument("--seed", type=int, default=42)
    p_seed.set_defaults(func=cmd_seed)

    p_sim = sub.add_parser("simulate", help="run the simulator standalone, printing each tick")
    p_sim.add_argument("--tick-seconds", type=float, default=5.0)
    p_sim.add_argument("--tick-hours", type=float, default=1.0)
    p_sim.add_argument("--max-ticks", type=int, default=None)
    p_sim.add_argument("--seed", type=int, default=None)
    p_sim.set_defaults(func=cmd_simulate)

    p_serve = sub.add_parser("serve", help="run the API + dashboard (also runs the live simulator)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_report = sub.add_parser("report", help="print a report to the terminal")
    p_report.add_argument(
        "--type",
        default="summary",
        choices=["summary", "by-provider", "by-service", "by-team", "by-environment", "anomalies", "budgets", "idle", "commitments"],
    )
    p_report.add_argument("--format", default="table", choices=["table", "json"])
    p_report.add_argument("--days", type=int, default=7)
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
