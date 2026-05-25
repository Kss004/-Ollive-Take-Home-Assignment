"""Prometheus metrics emitted by the ingestion service.

Buckets cover sub-second to 30s for latency, and a tight grid under 5s for TTFT.
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

LATENCY_BUCKETS = (
    0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30,
)
TTFT_BUCKETS = (
    0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5,
)

inference_latency = Histogram(
    "llm_inference_latency_seconds",
    "End-to-end LLM inference latency in seconds",
    labelnames=("provider", "model", "status"),
    buckets=LATENCY_BUCKETS,
)
inference_ttft = Histogram(
    "llm_inference_ttft_seconds",
    "Time to first token in seconds",
    labelnames=("provider", "model"),
    buckets=TTFT_BUCKETS,
)
inference_total = Counter(
    "llm_inference_total",
    "Total inference calls processed",
    labelnames=("provider", "model", "status"),
)
inference_tokens = Counter(
    "llm_inference_tokens_total",
    "Tokens consumed/produced",
    labelnames=("provider", "model", "kind"),  # kind = prompt|completion
)
ingest_dlq = Counter(
    "llm_ingest_dlq_total",
    "Events sent to DLQ after failed processing",
    labelnames=("reason",),
)
ingest_processed = Counter(
    "llm_ingest_processed_total",
    "Events successfully persisted",
)
