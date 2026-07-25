"""Turns simulator ticks into rows in the database (and optionally a
callback, which is how the FastAPI app pushes new records to websocket
clients as they're generated).

Two modes:
- backfill(): walk a fixed historical window all at once. Used by
  `finops seed` to populate a few weeks of history so the dashboard isn't
  empty on first run.
- run_live(): advance one tick at a time in real time, sleeping between
  ticks. Used by `finops serve` and `finops simulate --live`.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Callable

from finops.models import CostRecord
from finops.simulator.generator import FleetSimulator
from finops.storage import db

OnTick = Callable[[list[CostRecord]], None]


def backfill(
    conn: sqlite3.Connection,
    simulator: FleetSimulator,
    start: datetime,
    end: datetime,
    tick_delta: timedelta = timedelta(hours=1),
) -> int:
    total = 0
    current = start
    while current <= end:
        records = simulator.tick(current)
        db.insert_records(conn, records)
        total += len(records)
        current += tick_delta
    return total


def run_live(
    conn: sqlite3.Connection,
    simulator: FleetSimulator,
    tick_seconds: float = 5.0,
    tick_delta: timedelta = timedelta(hours=1),
    on_tick: OnTick | None = None,
    stop_event: threading.Event | None = None,
    max_ticks: int | None = None,
) -> None:
    latest = db.latest_timestamp(conn)
    current = datetime.fromisoformat(latest) + tick_delta if latest else datetime.utcnow()

    ticks_run = 0
    while stop_event is None or not stop_event.is_set():
        records = simulator.tick(current)
        db.insert_records(conn, records)
        if on_tick:
            on_tick(records)

        current += tick_delta
        ticks_run += 1
        if max_ticks is not None and ticks_run >= max_ticks:
            break
        time.sleep(tick_seconds)
