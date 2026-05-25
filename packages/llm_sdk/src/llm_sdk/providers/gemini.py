from __future__ import annotations

import os
from typing import AsyncIterator

from llm_sdk.providers.base import BaseProvider, ProviderResult
from llm_sdk.types import Message, StreamChunk


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None) -> None:
        from google import genai

        self.genai = genai
        self.client = genai.Client(api_key=api_key or os.getenv("GOOGLE_API_KEY"))

    @staticmethod
    def _to_contents(messages: list[Message]) -> tuple[list[dict], str | None]:
        system_text = "\n\n".join(m.content for m in messages if m.role == "system") or None
        contents = []
        for m in messages:
            if m.role == "system":
                continue
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        return contents, system_text

    async def stream(
        self, model: str, messages: list[Message], result: ProviderResult, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        from google.genai import types as gtypes  # type: ignore

        contents, system_text = self._to_contents(messages)
        config = None
        if system_text:
            config = gtypes.GenerateContentConfig(system_instruction=system_text)

        stream = await self.client.aio.models.generate_content_stream(
            model=model, contents=contents, config=config
        )
        async for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield StreamChunk(delta=text)
            usage = getattr(chunk, "usage_metadata", None)
            if usage:
                result.prompt_tokens = getattr(usage, "prompt_token_count", None) or result.prompt_tokens
                result.completion_tokens = (
                    getattr(usage, "candidates_token_count", None) or result.completion_tokens
                )
                result.total_tokens = (
                    getattr(usage, "total_token_count", None) or result.total_tokens
                )
            candidates = getattr(chunk, "candidates", None) or []
            for cand in candidates:
                if getattr(cand, "finish_reason", None):
                    result.finish_reason = str(cand.finish_reason)
