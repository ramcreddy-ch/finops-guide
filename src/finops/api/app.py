"""FastAPI app: REST endpoints for the dashboard plus a websocket that
pushes newly-generated cost records out as they're ingested.

The "real-time" part of this project is intentionally modest: a background
thread runs the simulator on a tick, writes to SQLite, and then hands the
new batch of records to a broadcaster that fans it out to whatever
websocket clients are connected. It's a demo-scale version of what a real
streaming cost pipeline (Kinesis/Kafka -> stream processor -> dashboard)
would do.
"""

from __future__ import annotations

import asyncio
import json
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from finops.analytics import aggregation, anomaly, budgets, forecast, optimization
from finops.ingestion.pipeline import run_live
from finops.models import CostRecord
from finops.simulator.generator import FleetSimulator
from finops.storage import db

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class Broadcaster:
    """Fans out cost record batches to connected websocket clients.

    The simulator runs on a plain background thread (not asyncio), so
    `publish` is called from that thread and hops onto the FastAPI event
    loop via `run_coroutine_threadsafe`.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    def publish(self, records: list[CostRecord]) -> None:
        if not self._clients or self._loop is None:
            return
        payload = json.dumps(
            {
                "type": "cost_tick",
                "tick_total": round(sum(r.cost_amount for r in records), 2),
                "record_count": len(records),
                "timestamp": records[0].timestamp.isoformat() if records else None,
                "top_services": _top_services(records),
            }
        )
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)

    async def _broadcast(self, payload: str) -> None:
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


def _top_services(records: list[CostRecord], limit: int = 5) -> list[dict]:
    totals: dict[str, float] = {}
    for r in records:
        totals[r.service] = totals.get(r.service, 0.0) + r.cost_amount
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"service": name, "cost": round(cost, 2)} for name, cost in ranked]


broadcaster = Broadcaster()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    broadcaster.bind_loop(asyncio.get_running_loop())

    stop_event = threading.Event()
    simulator = FleetSimulator(seed=None)

    def _run_simulator() -> None:
        # sqlite3 connections are only usable on the thread that created
        # them, so this thread needs its own - it can't reuse one opened
        # on the event loop thread.
        conn = db.get_connection()
        try:
            run_live(
                conn=conn,
                simulator=simulator,
                tick_seconds=5.0,
                tick_delta=timedelta(hours=1),
                on_tick=broadcaster.publish,
                stop_event=stop_event,
            )
        finally:
            conn.close()

    thread = threading.Thread(target=_run_simulator, daemon=True)
    thread.start()

    yield

    stop_event.set()
    thread.join(timeout=2)


app = FastAPI(title="finops-guide", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/summary")
def summary():
    conn = db.get_connection()
    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            "today_cost": aggregation.total_cost_since(conn, today_start),
            "month_to_date_cost": aggregation.month_to_date_cost(conn),
            "forecast": forecast.forecast_month_end_run_rate(conn),
            "active_anomalies": len(anomaly.detect_anomalies(conn)),
            "record_count": db.total_record_count(conn),
            "latest_timestamp": db.latest_timestamp(conn),
        }
    finally:
        conn.close()


@app.get("/api/costs/by/{dimension}")
def costs_by_dimension(dimension: str, days: int = 7):
    conn = db.get_connection()
    since = datetime.utcnow() - timedelta(days=days)
    try:
        return aggregation.cost_by_dimension(conn, dimension, since)
    finally:
        conn.close()


@app.get("/api/costs/trend")
def costs_trend(days: int = 30):
    conn = db.get_connection()
    try:
        return aggregation.daily_trend(conn, days)
    finally:
        conn.close()


@app.get("/api/forecast")
def forecast_endpoint():
    conn = db.get_connection()
    try:
        return {
            "run_rate": forecast.forecast_month_end_run_rate(conn),
            "trend": forecast.forecast_trend(conn),
        }
    finally:
        conn.close()


@app.get("/api/anomalies")
def anomalies_endpoint(lookback_hours: int = 48, z_threshold: float = 3.0):
    conn = db.get_connection()
    try:
        return anomaly.detect_anomalies(conn, lookback_hours=lookback_hours, z_threshold=z_threshold)
    finally:
        conn.close()


@app.get("/api/budgets")
def budgets_endpoint():
    conn = db.get_connection()
    try:
        return budgets.evaluate_budgets(conn)
    finally:
        conn.close()


@app.get("/api/optimization/idle")
def idle_resources_endpoint(lookback_days: int = 7):
    conn = db.get_connection()
    try:
        return optimization.find_idle_resources(conn, lookback_days=lookback_days)
    finally:
        conn.close()


@app.get("/api/optimization/commitments")
def commitment_recommendations_endpoint(lookback_days: int = 14):
    conn = db.get_connection()
    try:
        return optimization.recommend_commitment_coverage(conn, lookback_days=lookback_days)
    finally:
        conn.close()


@app.websocket("/ws/live")
async def live_feed(ws: WebSocket):
    await broadcaster.connect(ws)
    try:
        while True:
            # we don't expect client messages, this just keeps the socket
            # open and lets us notice disconnects
            await ws.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(ws)
