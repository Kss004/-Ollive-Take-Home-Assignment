from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app import cancel
from app.models import ChatRequest
from llm_sdk import LLM, Message

log = logging.getLogger("chat")

router = APIRouter(tags=["chat"])  # exported as router; mounted at root


async def _next_sequence(conn, conversation_id: str) -> int:
    row = await conn.fetchrow(
        "SELECT COALESCE(MAX(sequence), -1) + 1 AS seq FROM messages WHERE conversation_id = $1::uuid",
        conversation_id,
    )
    return int(row["seq"])


async def _persist_user_message(conn, conversation_id: str, content: str) -> tuple[str, int]:
    seq = await _next_sequence(conn, conversation_id)
    row = await conn.fetchrow(
        """
        INSERT INTO messages (conversation_id, role, content, sequence)
        VALUES ($1::uuid, 'user', $2, $3)
        RETURNING id
        """,
        conversation_id, content, seq,
    )
    return str(row["id"]), seq


async def _create_assistant_placeholder(
    conn, conversation_id: str, sequence: int, msg_id: str,
) -> None:
    """Insert an empty assistant row so the message_id exists for FK references
    in inference_logs before the stream completes."""
    await conn.execute(
        """
        INSERT INTO messages (id, conversation_id, role, content, sequence, metadata)
        VALUES ($1::uuid, $2::uuid, 'assistant', '', $3, '{}'::jsonb)
        """,
        msg_id, conversation_id, sequence,
    )


async def _finalize_assistant_message(
    conn, msg_id: str, content: str, metadata: dict,
) -> None:
    await conn.execute(
        """
        UPDATE messages SET content = $1, metadata = $2::jsonb
        WHERE id = $3::uuid
        """,
        content, metadata, msg_id,
    )


async def _load_history(conn, conversation_id: str) -> list[Message]:
    rows = await conn.fetch(
        "SELECT role, content FROM messages WHERE conversation_id = $1::uuid ORDER BY sequence ASC",
        conversation_id,
    )
    return [Message(role=r["role"], content=r["content"]) for r in rows]


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    pool = request.app.state.pool
    r = request.app.state.redis

    # validate conversation
    async with pool.acquire() as conn:
        conv = await conn.fetchrow(
            "SELECT id, status FROM conversations WHERE id = $1::uuid", body.conversation_id,
        )
        if not conv:
            raise HTTPException(404, "conversation not found")
        if conv["status"] == "archived":
            raise HTTPException(400, "conversation archived")

        # clear any stale cancel flag at the start of a new turn
        await cancel.clear(r, body.conversation_id)

        # persist user message + load full history
        user_msg_id, user_seq = await _persist_user_message(conn, body.conversation_id, body.message)
        history = await _load_history(conn, body.conversation_id)
        # pre-allocate assistant message id so inference_logs FK is satisfied
        assistant_seq = await _next_sequence(conn, body.conversation_id)
        assistant_msg_id = str(uuid.uuid4())
        await _create_assistant_placeholder(
            conn, body.conversation_id, assistant_seq, assistant_msg_id,
        )
        # update conv provider/model + touch
        await conn.execute(
            "UPDATE conversations SET provider = $1, model = $2, status = 'active' "
            "WHERE id = $3::uuid",
            body.provider, body.model, body.conversation_id,
        )

    llm = LLM(
        provider=body.provider,
        model=body.model,
        session_id=body.conversation_id,
        message_id=assistant_msg_id,
    )

    async def event_gen():
        assembled: list[str] = []
        cancelled = False
        meta: dict = {"user_message_id": user_msg_id}
        try:
            yield {"event": "ready", "data": json.dumps({"user_message_id": user_msg_id})}
            stream = llm.stream(history)
            async for chunk in stream:
                if await cancel.is_cancelled(r, body.conversation_id):
                    cancelled = True
                    await stream.aclose()
                    break
                if chunk.delta:
                    assembled.append(chunk.delta)
                    yield {"event": "token", "data": chunk.delta}
        except Exception as exc:  # noqa: BLE001
            log.exception("stream error: %s", exc)
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}
            meta["error"] = str(exc)
        finally:
            content = "".join(assembled)
            if cancelled:
                meta["cancelled"] = True
                # mark conversation cancelled for visibility but keep it usable
                try:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE conversations SET status = 'cancelled' "
                            "WHERE id = $1::uuid AND status = 'active'",
                            body.conversation_id,
                        )
                except Exception:
                    pass
            try:
                async with pool.acquire() as conn:
                    await _finalize_assistant_message(
                        conn, assistant_msg_id, content, meta,
                    )
            except Exception as exc:  # noqa: BLE001
                log.exception("failed to finalize assistant message: %s", exc)

            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": assistant_msg_id,
                    "cancelled": cancelled,
                }),
            }

    return EventSourceResponse(event_gen())
