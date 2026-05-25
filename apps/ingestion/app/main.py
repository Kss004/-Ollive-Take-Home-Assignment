"""Ingestion service.

Runs three concerns in one process:
  - POST /ingest    — HTTP fallback for SDK when Redis is down.
                      Publishes onto the stream so the worker remains the single writer.
  - Worker          — XREADGROUP loop persisting events to Postgres.
  - GET  /metrics   — Prometheus scrape endpoint.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import worker
from app.pipeline import parse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("ingestion")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ollive:ollive@postgres:5432/ollive")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STREAM = os.getenv("INFERENCE_STREAM", "inference:logs")


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, init=_init_conn)
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    stop = asyncio.Event()
    worker_task = asyncio.create_task(worker.run(pool, REDIS_URL, stop))
    app.state.pool = pool
    app.state.redis = r
    app.state.stop = stop
    app.state.worker_task = worker_task
    log.info("ingestion ready")
    try:
        yield
    finally:
        stop.set()
        worker_task.cancel()
        try:
            await worker_task
        except (asyncio.CancelledError, Exception):
            pass
        await r.aclose()
        await pool.close()


app = FastAPI(title="Ollive Ingestion", lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/metrics")
async def metrics_endpoint():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/ingest")
async def ingest(request: Request):
    body = await request.body()
    try:
        event = parse(body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid payload: {exc}") from exc
    r: aioredis.Redis = request.app.state.redis
    try:
        await r.xadd(STREAM, {"payload": event.model_dump_json()}, maxlen=100_000, approximate=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("redis publish failed in /ingest, falling back to direct persist: %s", exc)
        from app.pipeline import persist as _persist
        await _persist(request.app.state.pool, event)
    return {"accepted": True}
