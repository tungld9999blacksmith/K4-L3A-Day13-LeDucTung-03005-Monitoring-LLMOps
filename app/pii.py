from __future__ import annotations

import hashlib
import re

# Order matters: patterns are applied top to bottom, so secrets and long
# numbers are scrubbed before shorter, more generic number patterns.
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    # API keys / tokens (OpenAI, Langfuse sk-lf-/pk-lf-, Bearer headers)
    "api_key": r"\b(?:sk|pk)-[A-Za-z0-9_-]{16,}",
    "bearer_token": r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*",
    "cccd": re.compile(r"\b\d{12}\b"),
    "credit_card": re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    # Old 9-digit CMND
    "cmnd": r"\b\d{9}\b",
    # Vietnamese passport: 1 uppercase letter + 7 digits (e.g. C1234567)
    "passport": r"\b[A-Z]\d{7}\b",
    "ipv4": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
    # Address keyword + the following segment up to a separator
    "address_vn": (
        r"(?i)\b(?:số\s+nhà|đường|phố|ngõ|ngách|hẻm|kiệt|thôn|xóm|ấp|khu\s+phố|"
        r"phường|xã|thị\s+trấn|quận|huyện|thị\s+xã|tỉnh|thành\s+phố|tp\.?)"
        r"\s+[^\n,;.]{1,40}"
    ),
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
