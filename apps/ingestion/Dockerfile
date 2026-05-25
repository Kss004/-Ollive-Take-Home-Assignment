FROM python:3.12-slim

# uv — fast Python package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /repo

# install llm_sdk first (editable)
COPY packages/llm_sdk /repo/packages/llm_sdk
COPY apps/ingestion /repo/apps/ingestion

WORKDIR /repo/apps/ingestion

RUN uv venv --clear && uv pip install -e /repo/packages/llm_sdk && uv pip install -e .

EXPOSE 8001

CMD ["/repo/apps/ingestion/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
