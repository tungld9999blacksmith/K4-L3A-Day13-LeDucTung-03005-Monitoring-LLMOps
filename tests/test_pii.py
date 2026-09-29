from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_passport() -> None:
    out = scrub_text("Passport: C1234567")
    assert "C1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_vietnamese_address() -> None:
    out = scrub_text("Tôi ở số nhà 12 Lê Lợi, phường Bến Nghé, quận 1, TP. Hồ Chí Minh")
    for fragment in ("12 Lê Lợi", "Bến Nghé", "quận 1", "Hồ Chí Minh"):
        assert fragment not in out
    assert "REDACTED_ADDRESS_VN" in out


def test_scrub_ids_and_secrets() -> None:
    cases = {
        "CCCD 079123456789": "REDACTED_CCCD",
        "CMND 123456789": "REDACTED_CMND",
        "card 4111 1111 1111 1111": "REDACTED_CREDIT_CARD",
        "ip 192.168.1.10": "REDACTED_IPV4",
        "key sk-lf-1234567890abcdef1234": "REDACTED_API_KEY",
        "Authorization: Bearer abcdefghijklmnop1234": "REDACTED_BEARER_TOKEN",
    }
    for text, token in cases.items():
        assert token in scrub_text(text), text
