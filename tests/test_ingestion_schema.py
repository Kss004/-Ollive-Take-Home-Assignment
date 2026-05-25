import json
from datetime import datetime, timezone

import pytest

from app.schema import LogEventIn
from app.pipeline import parse


def _payload(**overrides):
    base = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "latency_ms": 1234,
    }
    base.update(overrides)
    return base


def test_parse_accepts_valid_payload():
    raw = json.dumps(_payload())
    ev = parse(raw)
    assert isinstance(ev, LogEventIn)
    assert ev.provider == "openai"


def test_parse_rejects_unknown_status():
    raw = json.dumps(_payload(status="bogus"))
    with pytest.raises(Exception):
        parse(raw)


def test_parse_accepts_dict():
    ev = parse(_payload(status="cancelled"))
    assert ev.status == "cancelled"
