# Going to production

This project is built to be readable and runnable on a laptop with zero
external dependencies - that shaped a lot of decisions that would need to
change if this were actually going to run a real FinOps practice at a real
company. This doc is an honest list of what those changes would be, in
roughly the order they'd start to matter.

## Storage

SQLite with a single writer thread is fine for a demo generating maybe a
few hundred thousand rows. Real cost data at real cloud scale (thousands
of resources, hourly-or-finer granularity, months to years of retention
for trend analysis) needs:

- A database built for time-series aggregation - Postgres with
  TimescaleDB, ClickHouse, or a columnar warehouse (BigQuery, Redshift,
  Snowflake) are all reasonable choices depending on what else your org
  already runs. The query patterns in `finops/analytics/` (sum/group by
  over a time-bounded window) map directly onto what these engines are
  built for.
- Partitioning by time (and probably provider), so old data can be rolled
  up/archived instead of every query scanning the full history.
- A real migration tool instead of `CREATE TABLE IF NOT EXISTS` in
  `storage/db.py`.

## Ingestion

Real cost data doesn't arrive as a convenient Python object stream - it
arrives as scheduled exports (AWS Cost and Usage Reports land in S3 as
Parquet/CSV on a schedule; GCP billing export lands in BigQuery
continuously; Azure has both push exports and a query API). A production
ingestion pipeline would be closer to: a scheduled job or event-driven
function that picks up new export files/rows, normalizes them into
`CostRecord`s (reusing the same normalization logic the adapters in
`finops/providers/` already sketch out), and writes them in batches - plus
retry/backoff, idempotency (so re-processing the same export file doesn't
double-count), and monitoring on the pipeline itself, since a FinOps
platform that silently stops ingesting data is worse than having no
FinOps platform at all - it creates false confidence.

## The API and background thread

`finops/api/app.py` runs the simulator on a background thread inside the
same process as the web server, with a `Broadcaster` holding
in-memory websocket connections. That doesn't survive multiple server
processes/replicas (each would run its own simulator and only know about
its own websocket clients) or a process restart (in-memory state is
gone). A real deployment would separate "thing that ingests cost data" from
"thing that serves the API/dashboard" into different processes, with the
websocket fan-out backed by something shared across replicas (Redis
pub/sub, a message queue) instead of an in-process Python set.

## Auth and multi-tenancy

There's none here - every endpoint is open, because it's a local demo.
Real cost data is sensitive (it reveals headcount-adjacent signals,
product roadmap signals from what's being provisioned, and straightforward
"how much money does this company have" signals) and a real deployment
needs authentication, and almost certainly per-team/per-account access
scoping so a given viewer only sees the cost data they're supposed to.

## Secrets and credentials

`.env.example` documents environment variables for real provider
credentials, but nothing in this codebase does secret management beyond
"read an environment variable." Production use needs a real secrets
manager (AWS Secrets Manager, Azure Key Vault, GCP Secret Manager,
Vault) and credentials scoped as tightly as each adapter's docstring
says it needs (read-only cost/billing access, nothing broader).

## Observability

There's no logging beyond FastAPI/uvicorn's defaults and no metrics on
the pipeline itself. A production version needs to know, independently of
the dashboard it feeds, whether ingestion is actually keeping up, whether
the anomaly detector is throwing exceptions on malformed data, and how
long analytics queries are taking as the table grows.

## What doesn't need to change

The `CostRecord` schema, the provider adapter interface, and the
analytics functions in `finops/analytics/` are all written to be storage-
and scale-agnostic - they take a connection/session and run
straightforward SQL. Moving to a bigger database means changing
`finops/storage/db.py`'s connection handling, not rewriting the queries
built on top of it. That separation was the main design goal worth
protecting; everything above is what accumulates around it as usage
scales up, not a rewrite of the core.

Next: [13-roadmap.md](13-roadmap.md).
