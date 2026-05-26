from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app import cancel
from app.models import (
    ConversationOut,
    ConversationWithMessages,
    CreateConversation,
    MessageOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _row_to_conv(row) -> ConversationOut:
    return ConversationOut(
        id=str(row["id"]),
        title=row["title"],
        status=row["status"],
        provider=row["provider"],
        model=row["model"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_msg(row) -> MessageOut:
    return MessageOut(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        role=row["role"],
        content=row["content"],
        sequence=row["sequence"],
        created_at=row["created_at"],
        metadata=row["metadata"] or {},
    )


@router.post("", response_model=ConversationOut)
async def create_conversation(body: CreateConversation, request: Request) -> ConversationOut:
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations (title, provider, model)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            body.title, body.provider, body.model,
        )
    return _row_to_conv(row)


_VALID_STATUSES = {"active", "cancelled", "archived"}


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
) -> list[ConversationOut]:
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(_VALID_STATUSES)}")
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM conversations WHERE status = $1::conv_status "
                "ORDER BY updated_at DESC LIMIT $2",
                status, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT $1",
                limit,
            )
    return [_row_to_conv(r) for r in rows]


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(conversation_id: str, request: Request) -> ConversationWithMessages:
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT * FROM conversations WHERE id = $1::uuid", conversation_id,
        )
        if not conv:
            raise HTTPException(404, "conversation not found")
        msgs = await conn.fetch(
            "SELECT * FROM messages WHERE conversation_id = $1::uuid ORDER BY sequence ASC",
            conversation_id,
        )
    return ConversationWithMessages(
        **_row_to_conv(conv).model_dump(),
        messages=[_row_to_msg(m) for m in msgs],
    )


@router.post("/{conversation_id}/cancel")
async def cancel_conversation(conversation_id: str, request: Request):
    r = request.app.state.redis
    await cancel.signal(r, conversation_id)
    return {"cancelled": True}


@router.post("/{conversation_id}/archive")
async def archive_conversation(conversation_id: str, request: Request):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE conversations SET status = 'archived' WHERE id = $1::uuid RETURNING *",
            conversation_id,
        )
        if not row:
            raise HTTPException(404, "conversation not found")
    return _row_to_conv(row)
