from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from llm_sdk.types import Message, StreamChunk


@dataclass
class ProviderResult:
    """Side-channel state collected during streaming (read after iteration)."""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    raw_meta: dict = field(default_factory=dict)


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    def stream(self, model: str, messages: list[Message], result: ProviderResult,
               **kwargs) -> AsyncIterator[StreamChunk]:
        """Yield StreamChunk(delta=...) until exhausted.
        Implementations write token counts/meta into `result` as they become available."""
        ...
