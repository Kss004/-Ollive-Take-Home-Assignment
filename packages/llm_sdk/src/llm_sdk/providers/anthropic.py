from __future__ import annotations

import os
from typing import AsyncIterator

from llm_sdk.providers.base import BaseProvider, ProviderResult
from llm_sdk.types import Message, StreamChunk


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    async def stream(
        self, model: str, messages: list[Message], result: ProviderResult, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        system_msgs = [m.content for m in messages if m.role == "system"]
        chat = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        max_tokens = kwargs.pop("max_tokens", 1024)
        create_kwargs: dict = {
            "model": model,
            "messages": chat,
            "max_tokens": max_tokens,
        }
        if system_msgs:
            create_kwargs["system"] = "\n\n".join(system_msgs)
        create_kwargs.update(kwargs)

        async with self.client.messages.stream(**create_kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield StreamChunk(delta=text)
            final = await stream.get_final_message()
        if final.usage:
            result.prompt_tokens = final.usage.input_tokens
            result.completion_tokens = final.usage.output_tokens
            result.total_tokens = (final.usage.input_tokens or 0) + (final.usage.output_tokens or 0)
        if final.stop_reason:
            result.finish_reason = final.stop_reason
        result.raw_meta["id"] = final.id
