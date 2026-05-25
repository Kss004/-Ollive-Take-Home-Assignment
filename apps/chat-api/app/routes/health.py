from __future__ import annotations

import os

from fastapi import APIRouter, Request

router = APIRouter(tags=["meta"])


@router.get("/healthz")
async def healthz():
    return {"ok": True}


@router.get("/providers")
async def providers(request: Request):
    # Show providers whose API key env vars are set. Models list is a sane default —
    # the UI can also override via free text.
    available = []
    if os.getenv("OPENAI_API_KEY"):
        available.append({
            "name": "openai",
            "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
        })
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append({
            "name": "anthropic",
            "models": [
                "claude-sonnet-4-5",
                "claude-haiku-4-5",
                "claude-opus-4-1",
                "claude-3-5-sonnet-latest",
            ],
        })
    if os.getenv("GOOGLE_API_KEY"):
        available.append({
            "name": "gemini",
            "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
        })
    return {
        "default": {
            "provider": os.getenv("DEFAULT_PROVIDER", "openai"),
            "model": os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),
        },
        "providers": available,
    }
