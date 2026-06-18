from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date


POLICY_VERSION_FINGERPRINT_VERSION = "policy_version_fingerprint.v1"
_WHITESPACE_RE = re.compile(r"\s+")


def build_policy_version_fingerprint(
    *,
    citation_text: str,
    title: str,
    doc_type: str,
    risk_level: str,
    effective_date: date,
) -> str:
    payload = {
        "version": POLICY_VERSION_FINGERPRINT_VERSION,
        "citation_text": _canonical_text(citation_text),
        "title": _canonical_metadata(title),
        "doc_type": _canonical_metadata(doc_type),
        "risk_level": _canonical_metadata(risk_level),
        "effective_date": effective_date.isoformat(),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_text(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.strip().split("\n"))


def _canonical_metadata(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return _WHITESPACE_RE.sub(" ", normalized).strip()
