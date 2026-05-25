"""Seed a few fake inference_logs rows so the dashboard has something to draw.

Usage:
    uv run scripts/seed.py
or  python scripts/seed.py
"""
from __future__ import annotations

import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg


PROVIDERS = [
    ("openai", "gpt-4o-mini"),
    ("openai", "gpt-4o"),
    ("anthropic", "claude-sonnet-4-5"),
    ("gemini", "gemini-2.5-flash"),
]
STATUSES = ["success", "success", "success", "success", "error", "cancelled"]


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "postgresql://ollive:ollive@localhost:5432/ollive")
    conn = await asyncpg.connect(url)
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(200):
        provider, model = random.choice(PROVIDERS)
        status = random.choice(STATUSES)
        latency = random.randint(120, 6_000)
        ttft = random.randint(40, min(1_200, latency))
        prompt_t = random.randint(20, 1_500)
        comp_t = random.randint(20, 1_500) if status == "success" else 0
        started = now - timedelta(seconds=random.randint(0, 1800))
        rows.append((
            None, None, provider, model, status,
            latency, ttft, prompt_t, comp_t, prompt_t + comp_t,
            None if status != "error" else "fake provider blew up",
            "[seed]", "[seed]",
            started, started + timedelta(milliseconds=latency),
            "{}",
        ))
    await conn.executemany(
        """
        INSERT INTO inference_logs (
          conversation_id, message_id, provider, model, status,
          latency_ms, ttft_ms, prompt_tokens, completion_tokens, total_tokens,
          error, request_preview, response_preview, started_at, completed_at, metadata
        ) VALUES (
          $1, $2, $3, $4, $5::log_status,
          $6, $7, $8, $9, $10,
          $11, $12, $13, $14, $15, $16::jsonb
        )
        """,
        rows,
    )
    print(f"inserted {len(rows)} seed rows")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
