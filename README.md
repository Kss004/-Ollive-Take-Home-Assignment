# Ollive — LLM chat + inference logging

A small but production-shaped reference architecture for the Ollive Founding
Fullstack Engineer take-home. Build a multi-provider chatbot, log every inference
through a lightweight SDK, ship the logs through an event bus to an ingestion
pipeline, persist to Postgres, and visualise the result on a Grafana dashboard.
One command brings it all up.

## What's inside

| Concern | Implementation |
|---|---|
| Chatbot UI | Next.js 15 App Router + React 19 (bun) |
| Chat API | FastAPI (uv) — `/chat` SSE, conversations CRUD, cancel |
| LLM SDK | `packages/llm_sdk` — unified streaming client for OpenAI, Anthropic, Gemini |
| Event bus | Redis Streams (`inference:logs`) + DLQ (`inference:logs:dlq`) |
| Ingestion | FastAPI + `XREADGROUP` worker (uv) — validate, PII-redact, persist |
| Storage | Postgres 16 (single DB, JSONB metadata) |
| Observability | Prometheus + Grafana with a provisioned LLM dashboard |
| PII redaction | `llm_sdk/redact.py` — emails, phones, Luhn-validated CCs, SSNs, IPs |
| Frontend bonuses | Cancel mid-stream, list conversations, resume any conversation |
| Deploy | `docker compose up --build` + `infra/k8s/` manifests for kind/minikube |

## Quick start

```bash
cp .env.example .env       # then set at least one provider key
docker compose up --build  # boots everything; web at http://localhost:3000
```

Once up:

| URL | What |
|---|---|
| http://localhost:3000 | Chat UI |
| http://localhost:3000/conversations | History (list + resume) |
| http://localhost:8000/docs | Chat API (Swagger) |
| http://localhost:8001/metrics | Prometheus exposition |
| http://localhost:9090 | Prometheus |
| http://localhost:3001 | Grafana (admin / admin) → "LLM Observability" |

> Tip: seed dashboard data without burning provider tokens:
> ```bash
> PYTHONPATH=. uv run scripts/seed.py
> ```

## Architecture

```
┌──────────────┐  POST /chat (SSE)  ┌────────────┐  XADD inference:logs  ┌──────────┐
│  Next.js UI  │ ─────────────────▶ │  chat-api  │ ───────────────────▶ │  Redis   │
│ cancel/list  │                    │  (FastAPI) │                       │ Streams  │
│ resume       │ ◀───── tokens ──── │  llm_sdk   │                       └────┬─────┘
└──────────────┘                    └────────────┘                            │
       ▲                                                    XREADGROUP        │
       │                                                    consumer group    ▼
       │                                                    ┌──────────────────────┐
       │   POST /conversations/:id/cancel                   │   ingestion worker   │
       │   (Redis `cancel:{id}` flag)                       │   validate + redact  │
       └────────────────────────────────────────────────────│   + persist + ack    │
                                                            │   /metrics → Prom    │
                                                            └─────────┬────────────┘
                                                                      ▼
                                                              ┌───────────────┐
                                                              │  Postgres 16  │
                                                              └───────────────┘
                                                              ┌─────────────────┐
                                                              │ Prometheus +    │
                                                              │ Grafana board   │
                                                              └─────────────────┘
```

Two write paths converge on `inference_logs`:

1. **Hot path (default)** — SDK does `XADD inference:logs` directly from the
   chat process, fire-and-forget on a background task. The worker
   `XREADGROUP`s, validates, PII-redacts (defense in depth), inserts, and
   `XACK`s. Failures go to a DLQ stream.
2. **Fallback** — if Redis is unreachable from the SDK, it `POST`s the same
   payload to `ingestion:/ingest`, which re-publishes onto the stream so the
   worker stays the single writer.

The chat request path is never blocked by the logging path.

## Schema

`infra/postgres/init.sql`. Three tables: `conversations`, `messages`,
`inference_logs`. All carry a `metadata jsonb` column for forward-compat.

| Decision | Rationale |
|---|---|
| Single Postgres for chats and logs | Demo simplicity. Logs are append-only and indexed for time/provider/model lookups — fine for assignment scale. Production would split logs to ClickHouse for cheaper aggregates. |
| `jsonb metadata` columns | Add provider-specific fields (finish_reason, raw response id, region) without migrations. |
| Enums (`conv_status`, `msg_role`, `log_status`) | Constraint at the DB layer; cheap to extend. |
| Nullable token counts | Some providers don't return usage on streaming; we record what we have. |
| Cascading FK on `messages` | Deleting a conversation cleans its messages. `inference_logs.conversation_id` is `ON DELETE SET NULL` — logs outlive conversations. |
| Previews stored already redacted | Raw user content never persists to the logs table. |
| `(conversation_id, sequence)` unique | Sequential order is the index used to render a conversation. |

## Tradeoffs

- Streams vs Kafka: Redis Streams keeps the demo cheap (one container) and is
  fine for the workload. Throughput ceiling is lower; a real deployment would
  move to Kafka or NATS JetStream for stronger ordering / replay guarantees.
- Postgres vs ClickHouse for logs: see above. Postgres is the single source of
  truth here; the panels query Prometheus, not Postgres, so the choice doesn't
  affect dashboards.
- Cancel via Redis flag (not WebSocket): the chat endpoint is a regular HTTP
  SSE stream, so the cancel signal is a small Redis `SET` with a TTL. The
  stream loop polls the flag between yielded tokens. Adds at most one round
  trip per token but is trivially simple to reason about.
- PII redaction is regex-based: high precision for emails/SSNs, looser for
  phones. Production should add Microsoft Presidio or a named-entity model on
  top.

## What I'd improve with more time

- Per-provider rate limiting and retries via `tenacity` (skeleton already
  imported) — currently the SDK does not retry on transient 5xx.
- Token streaming via Server-Sent Events works, but a WebSocket would carry
  bidirectional events (think: tool calls, partial cancellations).
- A second store (ClickHouse / Postgres TimescaleDB) for high-cardinality log
  analytics. Today the Grafana panels go through Prometheus, which loses
  per-conversation drill-down.
- Auth: there is none. A real product gates everything behind an org and a
  user model.
- Tests cover redact + ingestion schema. The chat endpoint and SDK provider
  integrations are tested by hand; a fake provider would let us cover the
  stream lifecycle (cancel, error, partial).
- Workflow-style durable execution for ingestion (retries, replay) — Redis
  Streams + DLQ does the bare minimum; a real platform would use Temporal,
  Vercel Workflow, or similar.
- Multi-region: today a single Postgres + Redis. Logs would naturally fan out
  per-region.

## Architecture notes — ingestion flow, logging strategy, scaling, failure handling

See [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Layout

```
apps/chat-api    # FastAPI: /chat (SSE), conversations, cancel
apps/ingestion   # FastAPI + worker: /ingest, /metrics, XREADGROUP loop
apps/web         # Next.js 15 + bun
packages/llm_sdk # Unified streaming SDK + redaction + transport
infra/postgres   # init.sql
infra/prometheus # prometheus.yml
infra/grafana    # provisioning + dashboard JSON
infra/k8s        # deployments, services, configmaps, secrets, statefulset, RBAC
scripts/seed.py        # populate logs without burning provider tokens
scripts/load_test.py   # fire concurrent chats
tests/                 # redact + ingestion schema
docker-compose.yml
.env.example
```

## Tests

```bash
# Unit (redact + ingestion schema)
PYTHONPATH=apps/ingestion uv --directory apps/ingestion run \
    --with pytest --with pytest-asyncio \
    --with-editable packages/llm_sdk \
    pytest tests/test_redact.py tests/test_ingestion_schema.py -v

# End-to-end against a running stack (skips automatically if stack is down)
docker compose run --rm \
    -v "$PWD/tests:/repo/tests:ro" \
    -e CHAT_API_URL_E2E=http://chat-api:8000 \
    -e INGEST_API_URL_E2E=http://ingestion:8001 \
    -e DATABASE_URL_E2E=postgresql://ollive:ollive@postgres:5432/ollive \
    --entrypoint sh ingestion -c "uv pip install -q pytest pytest-asyncio && \
        PYTHONPATH=/repo/apps/ingestion uv run pytest /repo/tests/test_e2e_flow.py -v"
```

The E2E suite covers: health, providers, conversation CRUD, OpenAI + Gemini
streaming, mid-stream cancel, PII redaction roundtrip, DLQ on bad payload,
archived conversation rejection, and unknown-provider fast-fail.

## Demo walkthrough

Step-by-step walkthrough lives in [`ARCHITECTURE.md`](./ARCHITECTURE.md) § Demo walkthrough.
