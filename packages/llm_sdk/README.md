# llm_sdk

Unified async streaming client for OpenAI, Anthropic, Gemini.
Captures inference metadata (latency, tokens, status, previews) and emits to Redis Streams
(falls back to HTTP POST `/ingest` when Redis is unavailable). PII redaction applied before
previews leave the SDK.

```python
from llm_sdk import LLM, Message

llm = LLM(provider="anthropic", model="claude-sonnet-4-5",
          session_id=conversation_id, message_id=message_id)

async for chunk in llm.stream([Message(role="user", content="hi")]):
    print(chunk.delta, end="", flush=True)
# On exit a LogEvent is emitted asynchronously to the ingestion pipeline.
```
