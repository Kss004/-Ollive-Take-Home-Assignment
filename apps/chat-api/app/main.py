from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import chat, conversations, health


async def _init_conn(conn: asyncpg.Connection) -> None:
    # decode jsonb columns as Python dicts/lists, not strings
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("chat-api")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ollive:ollive@postgres:5432/ollive")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, init=_init_conn)
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    app.state.pool = pool
    app.state.redis = r
    log.info("chat-api ready")
    try:
        yield
    finally:
        await r.aclose()
        await pool.close()


app = FastAPI(title="Ollive Chat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(conversations.router)
app.include_router(chat.router)
