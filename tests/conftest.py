"""Shared pytest setup.

We use the monorepo layout, so tests import from the installed packages:
  - `llm_sdk` (packages/llm_sdk)
  - `app`     (apps/ingestion / apps/chat-api — each has its own `app` package
                so tests should be run from the relevant working dir, or with
                PYTHONPATH set, e.g.  `PYTHONPATH=apps/ingestion uv run pytest tests/`).
"""
