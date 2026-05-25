from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ConversationOut(BaseModel):
    id: str
    title: Optional[str] = None
    status: str
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sequence: int
    created_at: datetime
    metadata: dict[str, Any] = {}


class CreateConversation(BaseModel):
    title: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ChatRequest(BaseModel):
    conversation_id: str
    provider: str
    model: str
    message: str


class ConversationWithMessages(ConversationOut):
    messages: list[MessageOut]
