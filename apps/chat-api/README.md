# chat-api

FastAPI service for the chatbot.

Endpoints:

| Method | Path                                  | Notes                                                            |
|--------|---------------------------------------|------------------------------------------------------------------|
| POST   | `/conversations`                      | create a conversation                                            |
| GET    | `/conversations`                      | list conversations (most recent first)                           |
| GET    | `/conversations/{id}`                 | conversation + full message history (used for **resume**)         |
| POST   | `/conversations/{id}/cancel`          | set a Redis cancel flag; the active stream halts on next token   |
| POST   | `/conversations/{id}/archive`         | hide conversation from default list                              |
| POST   | `/chat`                               | SSE stream of `token`, `error`, `done` events                     |
| GET    | `/providers`                          | which providers/models are usable in this deployment              |
| GET    | `/healthz`                            | liveness                                                         |

Inference logging is handled by the `llm_sdk` package — the chat API does not
touch the ingestion path directly. The SDK emits `LogEvent` to Redis Streams
(or HTTP `/ingest` as fallback) at the end of every stream, including cancelled
ones.

```bash
uv venv && uv pip install -e ../../packages/llm_sdk && uv pip install -e .
uv run uvicorn app.main:app --reload --port 8000
```
