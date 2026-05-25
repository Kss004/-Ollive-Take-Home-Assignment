"""Validated wire-format for log events arriving from the SDK."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class LogStatus(str):
    pass


class LogEventIn(BaseModel):
    provider: str
    model: str
    status: str
    session_id: Optional[str] = None
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

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        allowed = {"success", "error", "cancelled", "timeout"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v
