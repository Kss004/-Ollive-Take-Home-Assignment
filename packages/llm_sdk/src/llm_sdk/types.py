from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Role = Literal["user", "assistant", "system"]


class Message(BaseModel):
    role: Role
    content: str


class StreamChunk(BaseModel):
    delta: str = ""
    finish_reason: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


class LogStatus(str, Enum):
    success = "success"
    error = "error"
    cancelled = "cancelled"
    timeout = "timeout"


class LogEvent(BaseModel):
    """Inference log emitted by the SDK to the ingestion pipeline."""

    provider: str
    model: str
    status: LogStatus
    session_id: Optional[str] = None      # conversation_id
    message_id: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    ttft_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error: Optional[str] = None
    request_preview: Optional[str] = None
    response_preview: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
