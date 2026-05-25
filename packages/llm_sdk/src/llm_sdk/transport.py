"""Log transport.

Primary path: XADD to Redis Stream `inference:logs`.
Fallback: HTTP POST to the ingestion service `/ingest` endpoint.
All emissions are fire-and-forget — they must never block the chat request path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

import httpx

from llm_sdk.types import LogEvent

log = logging.getLogger("llm_sdk.transport")


class LogTransport:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        stream: str = "inference:logs",
        ingest_http_url: Optional[str] = None,
        http_timeout: float = 2.0,
    ) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.stream = stream or os.getenv("INFERENCE_STREAM", "inference:logs")
        self.ingest_http_url = ingest_http_url or os.getenv("INGESTION_URL")
        self.http_timeout = http_timeout
        self._redis = None
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        if not self.redis_url:
            return None
        try:
            import redis.asyncio as aioredis  # type: ignore

            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
            return self._redis
        except Exception as exc:  # noqa: BLE001
            log.warning("redis unavailable, falling back to HTTP: %s", exc)
            self._redis = None
            return None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.http_timeout)
        return self._http

    async def emit(self, event: LogEvent) -> None:
        payload = event.model_dump_json()
        r = await self._get_redis()
        if r is not None:
            try:
                await r.xadd(self.stream, {"payload": payload}, maxlen=100_000, approximate=True)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("XADD failed, falling back to HTTP: %s", exc)
        if not self.ingest_http_url:
            log.error("no ingestion URL configured; dropping log event")
            return
        try:
            http = await self._get_http()
            await http.post(f"{self.ingest_http_url.rstrip('/')}/ingest", content=payload,
                            headers={"content-type": "application/json"})
        except Exception as exc:  # noqa: BLE001
            log.error("HTTP ingest fallback failed: %s", exc)

    def emit_background(self, event: LogEvent) -> None:
        """Fire-and-forget. Safe to call from request handlers."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event))
        except RuntimeError:
            # no running loop — use a one-off
            asyncio.run(self.emit(event))

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass


_default_transport: Optional[LogTransport] = None


def default_transport() -> LogTransport:
    global _default_transport
    if _default_transport is None:
        _default_transport = LogTransport()
    return _default_transport
