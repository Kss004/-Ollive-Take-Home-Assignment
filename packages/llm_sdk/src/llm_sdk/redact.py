"""PII redaction.

Regex-based scrubber. Applied to previews before they leave the SDK (and again
defense-in-depth in the ingestion pipeline). The model still receives the
original message — only stored previews are redacted.
"""
from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# phone: digit (optional leading +) followed by 6-18 chars of digits/separators
# and a trailing digit. Loose by design; CC/SSN/IP run earlier so they win.
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,18}\d")
# credit card (digits with optional spaces/dashes, 13-19 digits)
CC_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _luhn(num: str) -> bool:
    digits = [int(c) for c in num if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _redact_cc(match: re.Match[str]) -> str:
    return "[REDACTED:CC]" if _luhn(match.group(0)) else match.group(0)


def _maybe_phone(match: re.Match[str]) -> str:
    """Only redact if the match has 7+ digits — avoids stripping incidental
    number runs (years, IDs) — and isn't a previously-redacted marker."""
    text = match.group(0)
    if text.startswith("[REDACTED"):
        return text
    return "[REDACTED:PHONE]" if sum(c.isdigit() for c in text) >= 7 else text


def redact(text: str) -> str:
    if not text:
        return text
    out = EMAIL_RE.sub("[REDACTED:EMAIL]", text)
    out = CC_RE.sub(_redact_cc, out)
    out = SSN_RE.sub("[REDACTED:SSN]", out)
    out = IPV4_RE.sub("[REDACTED:IP]", out)
    out = PHONE_RE.sub(_maybe_phone, out)
    return out


def preview(text: str, limit: int = 500) -> str:
    """Redact + truncate for storage."""
    if text is None:
        return ""
    redacted = redact(text)
    if len(redacted) > limit:
        return redacted[:limit] + "…"
    return redacted
