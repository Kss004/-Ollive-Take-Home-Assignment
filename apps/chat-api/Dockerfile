FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /repo

COPY packages/llm_sdk /repo/packages/llm_sdk
COPY apps/chat-api /repo/apps/chat-api

WORKDIR /repo/apps/chat-api

RUN uv venv --clear && uv pip install -e /repo/packages/llm_sdk && uv pip install -e .

EXPOSE 8000

CMD ["/repo/apps/chat-api/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
