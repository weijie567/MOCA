"""Safe RAG/claim summary projection helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


RAG_CLAIM_SUMMARY_SCHEMA_VERSION = "rag_claim_summary.v1"
_RAG_CLAIM_RAW_PAYLOAD_KEYS = frozenset(
    {
        "verified_evidence_package",
        "claim_verification_bundle",
        "debug_projection",
        "verifier_projection",
        "prompt_projection",
        "raw_semantic",
        "source_block",
        "source_block_id",
        "source_block_ids",
        "ocr",
        "ocr_metadata_json",
        "candidate_refs",
        "rejected_candidate_refs",
        "stale_refs",
        "conflict_refs",
        "safe_support_refs",
        "blocked_claims",
        "evidence_map",
    }
)
_RAG_CLAIM_SIGNAL_KEYS = frozenset(
    {
        "rag_claim_summary",
        "rag_context_status",
        "verified_evidence_count",
        "rejected_candidate_count",
        "stale_ref_count",
        "conflict_ref_count",
        "claim_verification_status",
        "blocked_claim_count",
        "safe_support_ref_count",
        "verified_evidence_package",
        "claim_verification_bundle",
        "safe_support_refs",
        "blocked_claims",
    }
)


def build_rag_claim_summary(source: Any) -> dict[str, Any] | None:
    """Project a single state/metrics payload into the public RAG/claim summary."""
    return build_rag_claim_summary_from_sources([source])


def build_rag_claim_summary_from_sources(sources: list[Any]) -> dict[str, Any] | None:
    """Merge state, step metrics, or replay payloads into the allowlisted summary."""
    rag_context_status: str | None = None
    claim_verification_status: str | None = None
    verified_evidence_ids: set[str] = set()
    safe_support_refs: list[Any] = []
    counts = {
        "verified_evidence_count": 0,
        "rejected_candidate_count": 0,
        "stale_ref_count": 0,
        "conflict_ref_count": 0,
        "blocked_claim_count": 0,
        "safe_support_ref_count": 0,
    }
    safe_support_metric: int | None = None
    saw_phase33_payload = False

    for source in sources:
        source_mapping = _mapping(source)
        if not source_mapping:
            continue

        existing_summary = _mapping(source_mapping.get("rag_claim_summary"))
        if existing_summary:
            saw_phase33_payload = True
            rag_context_status = rag_context_status or _string_value(existing_summary.get("rag_context_status"))
            claim_verification_status = claim_verification_status or _string_value(
                existing_summary.get("claim_verification_status")
            )
            for count_key in counts:
                counts[count_key] = max(counts[count_key], _non_negative_int(existing_summary.get(count_key)) or 0)
            safe_support_metric = counts["safe_support_ref_count"]

        if _has_rag_claim_signal(source_mapping):
            saw_phase33_payload = True

        package = _mapping(source_mapping.get("verified_evidence_package"))
        bundle = _mapping(source_mapping.get("claim_verification_bundle"))

        rag_context_status = (
            rag_context_status
            or _string_value(source_mapping.get("rag_context_status"))
            or _string_value(package.get("status"))
        )
        claim_verification_status = (
            claim_verification_status
            or _string_value(source_mapping.get("claim_verification_status"))
            or _string_value(bundle.get("overall_status"))
        )

        source_verified_ids = _verified_evidence_ids(package)
        verified_evidence_ids.update(source_verified_ids)
        counts["verified_evidence_count"] = max(
            counts["verified_evidence_count"],
            _non_negative_int(source_mapping.get("verified_evidence_count")) or len(source_verified_ids),
        )
        counts["rejected_candidate_count"] = max(
            counts["rejected_candidate_count"],
            _non_negative_int(source_mapping.get("rejected_candidate_count"))
            or _sequence_count(package.get("rejected_candidate_refs")),
        )
        counts["stale_ref_count"] = max(
            counts["stale_ref_count"],
            _non_negative_int(source_mapping.get("stale_ref_count")) or _sequence_count(package.get("stale_refs")),
        )
        counts["conflict_ref_count"] = max(
            counts["conflict_ref_count"],
            _non_negative_int(source_mapping.get("conflict_ref_count"))
            or _sequence_count(package.get("conflict_refs")),
        )
        counts["blocked_claim_count"] = max(
            counts["blocked_claim_count"],
            _non_negative_int(source_mapping.get("blocked_claim_count"))
            or _sequence_count(bundle.get("blocked_claims") or source_mapping.get("blocked_claims")),
        )

        metric_safe_count = _non_negative_int(source_mapping.get("safe_support_ref_count"))
        if metric_safe_count is not None:
            safe_support_metric = max(safe_support_metric or 0, metric_safe_count)
        safe_support_refs.extend(
            _sequence_items(bundle.get("safe_support_refs") or source_mapping.get("safe_support_refs"))
        )

    if not saw_phase33_payload:
        return None

    safe_support_ref_count = _safe_support_ref_count(safe_support_refs, verified_evidence_ids)
    if safe_support_ref_count is None or (not verified_evidence_ids and safe_support_metric is not None):
        safe_support_ref_count = safe_support_metric or counts["safe_support_ref_count"]

    return {
        "schema_version": RAG_CLAIM_SUMMARY_SCHEMA_VERSION,
        "rag_context_status": rag_context_status or "unknown",
        "verified_evidence_count": counts["verified_evidence_count"],
        "rejected_candidate_count": counts["rejected_candidate_count"],
        "stale_ref_count": counts["stale_ref_count"],
        "conflict_ref_count": counts["conflict_ref_count"],
        "claim_verification_status": claim_verification_status or "unknown",
        "blocked_claim_count": counts["blocked_claim_count"],
        "safe_support_ref_count": safe_support_ref_count,
    }


def sanitize_rag_claim_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove raw RAG/claim internals and attach the safe summary when present."""
    summary = build_rag_claim_summary(payload)
    sanitized = {key: value for key, value in payload.items() if key not in _RAG_CLAIM_RAW_PAYLOAD_KEYS}
    sanitized.pop("rag_claim_summary", None)
    if summary is not None:
        sanitized["rag_claim_summary"] = summary
    return sanitized


def _has_rag_claim_signal(source: Mapping[str, Any]) -> bool:
    for key in _RAG_CLAIM_SIGNAL_KEYS.intersection(source):
        value = source.get(key)
        if value not in (None, "", [], {}):
            return True
    return False


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _string_value(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _sequence_items(value: Any) -> list[Any]:
    if isinstance(value, list | tuple):
        return list(value)
    return []


def _sequence_count(value: Any) -> int:
    return len(_sequence_items(value))


def _verified_evidence_ids(package: Mapping[str, Any]) -> set[str]:
    evidence_map = package.get("evidence_map")
    if isinstance(evidence_map, dict):
        return {str(key) for key in evidence_map if key}
    ids: set[str] = set()
    for key in ("evidence_refs", "evidence_items"):
        for item in _sequence_items(package.get(key)):
            evidence_id = _evidence_id(item)
            if evidence_id:
                ids.add(evidence_id)
    return ids


def _safe_support_ref_count(refs: list[Any], verified_evidence_ids: set[str]) -> int | None:
    if not refs:
        return None
    if not verified_evidence_ids:
        return 0
    safe_ids = {_evidence_id(ref) for ref in refs}
    safe_ids.discard(None)
    return len(safe_ids.intersection(verified_evidence_ids))


def _evidence_id(ref: Any) -> str | None:
    ref_mapping = _mapping(ref)
    if ref_mapping:
        return _string_value(ref_mapping.get("evidence_id"))
    if isinstance(ref, str) and ref:
        return ref
    return None
