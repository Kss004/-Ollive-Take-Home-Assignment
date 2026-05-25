# ingestion

Two roles in one FastAPI process:

1. **Worker** — `XREADGROUP inference:logs` → validate → defense-in-depth PII redact → insert into `inference_logs`. Failures push to `inference:logs:dlq`.
2. **HTTP** — `POST /ingest` is the fallback path the SDK uses when Redis is unreachable. It re-publishes to the stream so the worker stays the single writer (or persists directly if Redis is also unreachable from here).
3. **Metrics** — `GET /metrics` exposes Prometheus histograms/counters.

```bash
uv venv && uv pip install -e ../../packages/llm_sdk && uv pip install -e .
uv run uvicorn app.main:app --port 8001
```
