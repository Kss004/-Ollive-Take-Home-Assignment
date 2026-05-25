"""Validate → redact → persist pipeline shared by HTTP and stream consumer paths."""
from __future__ import annotations

import json
import logging

import asyncpg

from llm_sdk.redact import preview
from app import metrics
from app.schema import LogEventIn

log = logging.getLogger("ingestion.pipeline")


async def persist(pool: asyncpg.Pool, event: LogEventIn) -> None:
    # defense-in-depth redaction
    req_prev = preview(event.request_preview or "", 500) if event.request_preview else None
    res_prev = preview(event.response_preview or "", 500) if event.response_preview else None

    async with pool.acquire() as conn:
        # `message_id` is informational. If the chat-api hasn't persisted the
        # assistant message yet (race) or the row got deleted, fall back to NULL
        # so the FK doesn't reject the whole event — we still want the log row.
        msg_id = event.message_id
        if msg_id:
            exists = await conn.fetchval(
                "SELECT 1 FROM messages WHERE id = $1::uuid", msg_id,
            )
            if not exists:
                msg_id = None
        await conn.execute(
            """
            INSERT INTO inference_logs (
              conversation_id, message_id, provider, model, status,
              latency_ms, ttft_ms, prompt_tokens, completion_tokens, total_tokens,
              error, request_preview, response_preview, started_at, completed_at, metadata
            ) VALUES (
              $1::uuid, $2::uuid, $3, $4, $5::log_status,
              $6, $7, $8, $9, $10,
              $11, $12, $13, $14, $15, $16::jsonb
            )
            """,
            event.session_id, msg_id, event.provider, event.model, event.status,
            event.latency_ms, event.ttft_ms, event.prompt_tokens, event.completion_tokens,
            event.total_tokens, event.error, req_prev, res_prev,
            event.started_at, event.completed_at, event.metadata or {},
        )

    # metrics
    labels = (event.provider, event.model, event.status)
    if event.latency_ms is not None:
        metrics.inference_latency.labels(*labels).observe(event.latency_ms / 1000.0)
    if event.ttft_ms is not None:
        metrics.inference_ttft.labels(event.provider, event.model).observe(event.ttft_ms / 1000.0)
    metrics.inference_total.labels(*labels).inc()
    if event.prompt_tokens:
        metrics.inference_tokens.labels(event.provider, event.model, "prompt").inc(event.prompt_tokens)
    if event.completion_tokens:
        metrics.inference_tokens.labels(event.provider, event.model, "completion").inc(event.completion_tokens)
    metrics.ingest_processed.inc()


def parse(raw: str | bytes | dict) -> LogEventIn:
    if isinstance(raw, (str, bytes)):
        data = json.loads(raw)
    else:
        data = raw
    return LogEventIn.model_validate(data)
