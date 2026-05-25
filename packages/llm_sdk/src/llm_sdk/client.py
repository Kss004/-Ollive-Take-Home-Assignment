"""Unified LLM client.

Wraps provider streams, captures inference metadata, and emits a LogEvent at
exit time (success, error, or cancellation).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from llm_sdk.providers import get_provider
from llm_sdk.providers.base import ProviderResult
from llm_sdk.redact import preview
from llm_sdk.transport import LogTransport, default_transport
from llm_sdk.types import LogEvent, LogStatus, Message, StreamChunk

log = logging.getLogger("llm_sdk")


class LLM:
    def __init__(
        self,
        provider: str,
        model: str,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        transport: Optional[LogTransport] = None,
        preview_limit: int = 500,
    ) -> None:
        self.provider_name = provider
        self.model = model
        self.session_id = session_id
        self.message_id = message_id
        self.provider = get_provider(provider)
        self.transport = transport or default_transport()
        self.preview_limit = preview_limit

    async def stream(
        self, messages: list[Message], **kwargs
    ) -> AsyncIterator[StreamChunk]:
        result = ProviderResult()
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        ttft_ms: Optional[int] = None
        assembled: list[str] = []
        status = LogStatus.success
        error_msg: Optional[str] = None
        user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")

        try:
            async for chunk in self.provider.stream(self.model, messages, result, **kwargs):
                if ttft_ms is None and chunk.delta:
                    ttft_ms = int((time.perf_counter() - t0) * 1000)
                assembled.append(chunk.delta)
                yield chunk
        except GeneratorExit:
            # downstream consumer cancelled iteration
            status = LogStatus.cancelled
            raise
        except TimeoutError as exc:
            status = LogStatus.timeout
            error_msg = str(exc)
            raise
        except Exception as exc:  # noqa: BLE001
            status = LogStatus.error
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            completed = datetime.now(timezone.utc)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            event = LogEvent(
                provider=self.provider_name,
                model=self.model,
                status=status,
                session_id=self.session_id,
                message_id=self.message_id,
                started_at=started,
                completed_at=completed,
                latency_ms=latency_ms,
                ttft_ms=ttft_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                error=error_msg,
                request_preview=preview(user_msg, self.preview_limit),
                response_preview=preview("".join(assembled), self.preview_limit),
                metadata={
                    "finish_reason": result.finish_reason,
                    **result.raw_meta,
                },
            )
            try:
                self.transport.emit_background(event)
            except Exception as exc:  # noqa: BLE001
                log.warning("log emission failed: %s", exc)
