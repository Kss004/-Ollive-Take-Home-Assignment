# Architecture Notes

## Ingestion flow

1. The browser hits `POST /chat` on the chat API with `{conversation_id, provider, model, message}`.
2. Chat API persists the user message, loads the conversation history, and starts an `llm_sdk.LLM(...).stream(history)` async iterator.
3. The SDK wraps the provider stream and tracks: `started_at`, `ttft_ms` (set on first non-empty delta), `latency_ms` on exit, token counts pulled from provider final-chunk usage, the redacted previews of the last user message and the assembled assistant reply, and `status ∈ {success, error, cancelled, timeout}`.
4. Tokens flow back to the browser as SSE `event: token` frames.
5. Between each yielded token, the chat API checks Redis key `cancel:{conversation_id}`. If set, it calls `stream.aclose()`, which surfaces as `GeneratorExit` inside the SDK — the SDK marks `status=cancelled`, still emits the log event with the partial response, and re-raises.
6. On normal completion, error, or cancellation, the SDK builds a `LogEvent` and fires it through `LogTransport`:
   - Primary: `XADD inference:logs * payload <json>` with `MAXLEN ~ 100_000`.
   - Fallback: HTTP `POST /ingest` (re-publishes onto the stream from inside the ingestion service).
   - This emission runs as `asyncio.create_task(...)` — the chat path never waits on it.
7. The ingestion worker reads via `XREADGROUP GROUP ingest workers > inference:logs COUNT 100 BLOCK 5000`, validates with Pydantic, redacts previews again (defense in depth), inserts into `inference_logs`, observes Prometheus metrics, and `XACK`s. Failures push the original entry to `inference:logs:dlq` with a `_reason` tag.

## Logging strategy

- **What we capture per call**: `provider`, `model`, `session_id` (conversation_id), `message_id`, `started_at`, `completed_at`, `latency_ms`, `ttft_ms`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `status`, `error`, `request_preview` (≤500 chars, PII-redacted), `response_preview` (≤500 chars, PII-redacted), `metadata` (raw provider id, finish_reason, free-form).
- **Where**:
  - Real-time → Redis Streams (durable, capped).
  - Persisted → Postgres `inference_logs` (indexed on `started_at`, `(model, started_at)`, `status`, `conversation_id`).
  - Aggregates → Prometheus (histograms for latency + ttft, counters for total / by-status / tokens / DLQ).
- **PII**: emails, phones, Luhn-validated credit cards, SSNs, IPv4 addresses are stripped from previews before they leave the SDK process. The model itself still sees the original message — only stored/observed previews are redacted.

## Scaling considerations

- **Stateless services** (`chat-api`, `ingestion`, `web`) scale horizontally. Worker pods share a single consumer group, so adding replicas linearly increases ingestion throughput without duplicate processing.
- **Redis Streams** is the natural bottleneck. The stream is capped at ~100k entries (`MAXLEN ~`) — sustained burst rate ≫ persistence rate would shed the oldest entries. To grow past one Redis: shard on `session_id` across multiple streams, or replace with Kafka.
- **Postgres** writes are the next bottleneck. `inference_logs` is append-only; switching to partitioning by day (`PARTITION BY RANGE (started_at)`) makes retention cheap and keeps indexes small. For high-cardinality analytics, sink into ClickHouse asynchronously.
- **Prometheus** scrapes ingestion every 5s; cardinality is bounded by `(provider, model, status)`. Adding tenant/org dimensions would inflate series count — push to a remote write target (Mimir / VictoriaMetrics) for high-cardinality cases.
- **Hot path latency**: the chat request only does a few small Postgres writes and one async Redis `XADD`. The chat → tokens path is bound by provider TTFT, not by us.

## Failure handling assumptions

| Failure | Behavior |
|---|---|
| Provider 5xx / timeout | SDK catches, marks `status=error|timeout`, emits log event, re-raises so chat-api yields `event: error` and persists an assistant message with empty content + `metadata.error`. |
| User cancels mid-stream | UI calls `/conversations/:id/cancel` (Redis SET) **and** aborts the local `fetch`. Backend detects the flag, closes the SDK generator → SDK emits `status=cancelled` with the partial response. Assistant message persists with `metadata.cancelled=true` and a truncated content body. |
| Redis down | SDK falls back to `POST /ingest`. Ingestion still attempts to publish to the stream first; if Redis is also unreachable from ingestion, it persists directly to Postgres (skipping the queue but not dropping the event). |
| Worker crashes between read and ack | Pending Entries List (PEL) keeps the entry assigned. On restart the new consumer reclaims it (via `XAUTOCLAIM` — added at production-ready time; currently relies on consumer restart with the same name). |
| Validation failure | Event is XADDed to `inference:logs:dlq` with `_reason=ValidationError`; `llm_ingest_dlq_total` counter goes up. The original stream entry is ACKed so it does not stall the group. |
| Postgres down | Worker logs the error, sends to DLQ. Chat API itself fails fast on `/chat` (cannot persist messages) — by design; logs being durable in Redis means we can replay once Postgres recovers. |
| Provider key missing | `/providers` only advertises providers whose key is set. The UI dropdown reflects this and disables Send if no provider exists. |

## Demo script (Loom outline, ~5 min)

1. `docker compose up --build` — point out: postgres, redis, ingestion (workers), chat-api, web, prometheus, grafana boot together with healthchecks; one command.
2. Open http://localhost:3000 — show provider picker pulling from `/providers`. Pick OpenAI, send "what is consistent hashing in two sentences". Tokens stream in. Click cancel mid-stream → response halts; "cancelled" badge appears.
3. Reload `/conversations` — see the conversation with status `cancelled`. Click into it → message history loads (resume).
4. Switch provider to Anthropic, send another message → tokens stream from the new provider.
5. PII demo: send "my email is foo@bar.com, phone +91 90000 11111" → open Postgres (`docker compose exec postgres psql -U ollive -d ollive`) and `SELECT request_preview FROM inference_logs ORDER BY started_at DESC LIMIT 1;` — shows `[REDACTED:EMAIL]`, `[REDACTED:PHONE]`.
6. Run `uv run scripts/load_test.py --n 50 --concurrency 10` against an installed provider key. Open Grafana → "LLM Observability" → panels show requests/sec climb, latency p95/p99 by provider, TTFT, throughput by status, token rate.
7. Kill the ingestion container — send a new chat → mention SDK falls back to HTTP `/ingest`. Restart ingestion — old stream entries drain via the consumer group from the last ack.
8. `kubectl apply -f infra/k8s` against a `kind` cluster — show pods come up, port-forward web, send a chat. Same flow runs unchanged in k8s.

## Submission email (draft)

> Subject: Ollive Founding Fullstack — assignment submission
>
> Hi,
>
> Here is my submission for the Founding Fullstack take-home.
>
> - Repo: <https://github.com/$you/OliveAssign>
> - Demo: <Loom link>
> - Architecture notes: in `ARCHITECTURE.md` (ingestion flow, logging strategy, scaling, failure handling).
>
> Implemented all of: multi-provider streaming (OpenAI, Anthropic, Gemini), event-based logging via Redis Streams with a DLQ, Postgres storage with sensible schema/indexes, PII redaction, latency / throughput / errors dashboards in Grafana, Docker Compose one-command boot, k8s manifests for kind/minikube, and the frontend bonuses (cancel mid-stream, list conversations, resume any conversation).
>
> Happy to walk through tradeoffs over a call.
>
> — <name>
