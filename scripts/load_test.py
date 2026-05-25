"""Fire N concurrent /chat requests at the chat-api and confirm the SSE stream
drains cleanly. Use to exercise dashboards and the DLQ.

Usage:
    uv run scripts/load_test.py --n 50 --concurrency 10
"""
from __future__ import annotations

import argparse
import asyncio
import time

import httpx


PROMPTS = [
    "summarise the theory of relativity in two sentences",
    "what is the airspeed velocity of an unladen swallow",
    "give me one obscure pandas trick",
    "explain consistent hashing to a 5 year old",
    "name three good observability metrics for an LLM service",
]


async def one(client: httpx.AsyncClient, base: str, provider: str, model: str, prompt: str) -> tuple[int, float]:
    t0 = time.perf_counter()
    conv = (await client.post(f"{base}/conversations", json={"provider": provider, "model": model})).json()
    async with client.stream(
        "POST", f"{base}/chat",
        json={"conversation_id": conv["id"], "provider": provider, "model": model, "message": prompt},
        timeout=60,
    ) as resp:
        async for _ in resp.aiter_bytes():
            pass
    return resp.status_code, time.perf_counter() - t0


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--provider", default="openai")
    p.add_argument("--model", default="gpt-4o-mini")
    args = p.parse_args()

    sem = asyncio.Semaphore(args.concurrency)
    timings: list[float] = []
    errors = 0

    async with httpx.AsyncClient() as client:
        async def runner(i: int) -> None:
            nonlocal errors
            prompt = PROMPTS[i % len(PROMPTS)]
            async with sem:
                try:
                    status, dt = await one(client, args.base, args.provider, args.model, prompt)
                    if status != 200:
                        errors += 1
                    timings.append(dt)
                    print(f"[{i:03d}] {status} {dt:.2f}s")
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    print(f"[{i:03d}] ERR {exc}")

        await asyncio.gather(*(runner(i) for i in range(args.n)))

    if timings:
        timings.sort()
        p50 = timings[len(timings) // 2]
        p95 = timings[int(len(timings) * 0.95)]
        print(f"\nn={args.n} errors={errors} p50={p50:.2f}s p95={p95:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
