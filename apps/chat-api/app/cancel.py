"""Cancellation flag via Redis.

`/conversations/:id/cancel` sets `cancel:{id}` with a 60s TTL. The /chat stream
loop checks this key between yielded tokens and breaks early if it is set.
"""
from __future__ import annotations

import redis.asyncio as aioredis

CANCEL_TTL = 60


def key(conversation_id: str) -> str:
    return f"cancel:{conversation_id}"


async def signal(r: aioredis.Redis, conversation_id: str) -> None:
    await r.set(key(conversation_id), "1", ex=CANCEL_TTL)


async def is_cancelled(r: aioredis.Redis, conversation_id: str) -> bool:
    return bool(await r.get(key(conversation_id)))


async def clear(r: aioredis.Redis, conversation_id: str) -> None:
    await r.delete(key(conversation_id))
