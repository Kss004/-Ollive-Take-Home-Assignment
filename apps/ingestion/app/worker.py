"""Redis Stream consumer.

Reads from `inference:logs` via XREADGROUP, persists, ACKs on success, pushes to
DLQ on validation/persistence failure.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import asyncpg
import redis.asyncio as aioredis

from app import metrics
from app.pipeline import parse, persist

log = logging.getLogger("ingestion.worker")

STREAM = os.getenv("INFERENCE_STREAM", "inference:logs")
DLQ = os.getenv("INFERENCE_DLQ", "inference:logs:dlq")
GROUP = os.getenv("INFERENCE_GROUP", "ingest")
CONSUMER = os.getenv("INFERENCE_CONSUMER", "worker-1")


async def _ensure_group(r: aioredis.Redis) -> None:
    try:
        await r.xgroup_create(STREAM, GROUP, id="$", mkstream=True)
        log.info("created consumer group %s on %s", GROUP, STREAM)
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def run(pool: asyncpg.Pool, redis_url: str, stop_event: Optional[asyncio.Event] = None) -> None:
    r = aioredis.from_url(redis_url, decode_responses=True)
    await _ensure_group(r)
    log.info("worker starting: stream=%s group=%s consumer=%s", STREAM, GROUP, CONSUMER)

    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            resp = await r.xreadgroup(
                groupname=GROUP, consumername=CONSUMER,
                streams={STREAM: ">"}, count=100, block=5000,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("XREADGROUP failed: %s; sleeping 1s", exc)
            await asyncio.sleep(1)
            continue

        if not resp:
            continue
        for _stream, entries in resp:
            for entry_id, fields in entries:
                raw = fields.get("payload")
                if not raw:
                    await _dead_letter(r, entry_id, fields, reason="missing-payload")
                    continue
                try:
                    event = parse(raw)
                    await persist(pool, event)
                    await r.xack(STREAM, GROUP, entry_id)
                except Exception as exc:  # noqa: BLE001
                    log.exception("processing failed for %s: %s", entry_id, exc)
                    await _dead_letter(r, entry_id, fields, reason=type(exc).__name__)

    await r.aclose()


async def _dead_letter(r: aioredis.Redis, entry_id: str, fields: dict, reason: str) -> None:
    metrics.ingest_dlq.labels(reason=reason).inc()
    try:
        await r.xadd(DLQ, {**fields, "_reason": reason, "_orig_id": entry_id}, maxlen=10_000, approximate=True)
        await r.xack(STREAM, GROUP, entry_id)
    except Exception as exc:  # noqa: BLE001
        log.error("DLQ push failed for %s: %s", entry_id, exc)
