from __future__ import annotations

import os
from typing import AsyncIterator

from llm_sdk.providers.base import BaseProvider, ProviderResult
from llm_sdk.types import Message, StreamChunk


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    async def stream(
        self, model: str, messages: list[Message], result: ProviderResult, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        oai_messages = [{"role": m.role, "content": m.content} for m in messages]
        stream = await self.client.chat.completions.create(
            model=model,
            messages=oai_messages,
            stream=True,
            stream_options={"include_usage": True},
            **kwargs,
        )
        async for chunk in stream:
            if chunk.usage:
                result.prompt_tokens = chunk.usage.prompt_tokens
                result.completion_tokens = chunk.usage.completion_tokens
                result.total_tokens = chunk.usage.total_tokens
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta.content if choice.delta else None
            if choice.finish_reason:
                result.finish_reason = choice.finish_reason
            if delta:
                yield StreamChunk(delta=delta, finish_reason=choice.finish_reason)
