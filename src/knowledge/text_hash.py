from __future__ import annotations

import hashlib
import unicodedata

EVIDENCE_TEXT_HASH_VERSION = "evidence_text_hash.v1"


def normalize_evidence_text(text: str) -> str:
    """Normalize text according to evidence_text_hash.v1."""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def evidence_text_hash(text: str) -> str:
    """Return sha256:<lowercase hex> of the normalized UTF-8 bytes."""
    digest = hashlib.sha256(normalize_evidence_text(text).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
