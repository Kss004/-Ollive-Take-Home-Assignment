from llm_sdk.redact import preview, redact


def test_email_redacted():
    assert "[REDACTED:EMAIL]" in redact("contact me at foo@bar.com please")


def test_phone_redacted():
    out = redact("call +91 90000 11111 today")
    assert "[REDACTED:PHONE]" in out


def test_credit_card_redacted_with_luhn():
    # 4111 1111 1111 1111 is a known valid test CC
    assert "[REDACTED:CC]" in redact("card 4111 1111 1111 1111 expires 12/30")


def test_invalid_credit_card_not_redacted():
    # 1234 5678 9012 3456 fails Luhn
    out = redact("bogus 1234 5678 9012 3456")
    assert "[REDACTED:CC]" not in out


def test_ssn_redacted():
    assert "[REDACTED:SSN]" in redact("ssn 123-45-6789")


def test_ip_redacted():
    assert "[REDACTED:IP]" in redact("server is 192.168.0.1 on the lan")


def test_preview_truncates():
    s = "x" * 1000
    out = preview(s, limit=100)
    assert len(out) <= 101  # +1 for ellipsis
    assert out.endswith("…")


def test_preview_handles_empty():
    assert preview("", 100) == ""
    assert preview(None, 100) == ""  # type: ignore[arg-type]
