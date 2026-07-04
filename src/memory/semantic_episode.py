"""Prompt-safe semantic episode candidate projection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.memory.schemas import (
    LongTermMemoryWriteCandidate,
    LongTermPiiClassification,
    LongTermScopeType,
    MemorySourceRefV1,
)


SEMANTIC_EPISODE_SOURCE_TYPE = "semantic_episode_candidate"

SemanticEpisodeKind = Literal["preference_candidate"]

_SOURCE_SUMMARY_LIMIT = 3
_SOURCE_SUMMARY_CHAR_LIMIT = 280
_CANDIDATE_CONTENT_LIMIT = 600
_WHITESPACE_RE = re.compile(r"\s+")
_FORBIDDEN_KEY_MARKERS = (
    "raw",
    "payload",
    "policy_text",
    "authority_body",
    "debug_blob",
    "trace_blob",
    "replay_blob",
    "evidence_ref",
    "snapshot",
)
_KIND_FIELDS: dict[SemanticEpisodeKind, tuple[str, ...]] = {
    "preference_candidate": ("preference", "text", "content"),
}
_SUMMARY_KEYS: dict[SemanticEpisodeKind, tuple[str, ...]] = {
    "preference_candidate": ("preference_candidates", "preferences", "user_behavior_patterns"),
}
_CONTENT_PREFIX: dict[SemanticEpisodeKind, str] = {
    "preference_candidate": "Preference candidate",
}


class SemanticEpisodeCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    run_id: uuid.UUID
    scope_type: LongTermScopeType
    scope_id: str = Field(min_length=1, max_length=128)
    kind: SemanticEpisodeKind
    content: str = Field(min_length=1, max_length=_CANDIDATE_CONTENT_LIMIT)
    source_type: Literal["semantic_episode_candidate"] = SEMANTIC_EPISODE_SOURCE_TYPE
    review_status: Literal["needs_review"] = "needs_review"
    source_ref: MemorySourceRefV1
    source_summaries: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    pii_classification: LongTermPiiClassification = "none"

    def to_long_term_memory_candidate(self) -> LongTermMemoryWriteCandidate:
        return LongTermMemoryWriteCandidate(
            tenant_id=self.tenant_id,
            run_id=self.run_id,
            scope_type=self.scope_type,
            scope_id=self.scope_id,
            memory_kind="preference",
            content=self.content,
            source_type=self.source_type,
            source_ref=self.source_ref,
            confidence=self.confidence,
            pii_classification=self.pii_classification,
        )


def project_semantic_episode_candidates(
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_type: LongTermScopeType,
    scope_id: str,
    summaries: Sequence[Any] = (),
    tool_prompt_summaries: Sequence[Any] = (),
    case_outcome_summaries: Sequence[Any] = (),
    limit_per_kind: int = 3,
) -> list[SemanticEpisodeCandidate]:
    source_summaries = _source_summaries(
        summaries=summaries,
        tool_prompt_summaries=tool_prompt_summaries,
        case_outcome_summaries=case_outcome_summaries,
    )
    source_ref = MemorySourceRefV1(
        source_type=SEMANTIC_EPISODE_SOURCE_TYPE,
        run_id=str(run_id),
        agent_run_id=str(run_id),
    )
    candidates: list[SemanticEpisodeCandidate] = []
    seen: set[tuple[str, str]] = set()

    for summary in summaries:
        payload = _semantic_payload(summary)
        for kind, keys in _SUMMARY_KEYS.items():
            emitted_for_kind = 0
            for item in _items_for_keys(payload, keys):
                text = _candidate_text(item, kind)
                if not text:
                    continue
                content = _bounded_text(f"{_CONTENT_PREFIX[kind]}: {text}", _CANDIDATE_CONTENT_LIMIT)
                dedupe_key = (kind, content.casefold())
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                candidates.append(
                    SemanticEpisodeCandidate(
                        tenant_id=tenant_id,
                        run_id=run_id,
                        scope_type=scope_type,
                        scope_id=scope_id,
                        kind=kind,
                        content=content,
                        source_ref=source_ref,
                        source_summaries=source_summaries,
                        confidence=_confidence(item),
                        pii_classification=_pii_classification(item),
                    )
                )
                emitted_for_kind += 1
                if emitted_for_kind >= max(limit_per_kind, 1):
                    break

    return candidates


def _semantic_payload(summary: Any) -> Mapping[str, Any]:
    summary_json = getattr(summary, "summary_json", None)
    if not isinstance(summary_json, Mapping):
        return {}
    semantic = summary_json.get("semantic_episode")
    if isinstance(semantic, Mapping):
        return semantic
    return summary_json


def _items_for_keys(payload: Mapping[str, Any], keys: tuple[str, ...]) -> list[Any]:
    items: list[Any] = []
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, list | tuple):
            items.extend(value)
        else:
            items.append(value)
    return items


def _candidate_text(item: Any, kind: SemanticEpisodeKind) -> str:
    if isinstance(item, str):
        return _safe_text(item)
    if not isinstance(item, Mapping):
        return ""
    for field in _KIND_FIELDS[kind]:
        value = item.get(field)
        if isinstance(value, str):
            text = _safe_text(value)
            if text:
                return text
    return ""


def _confidence(item: Any) -> float:
    if not isinstance(item, Mapping):
        return 0.5
    value = item.get("confidence")
    if not isinstance(value, int | float):
        return 0.5
    return max(0.0, min(float(value), 1.0))


def _pii_classification(item: Any) -> LongTermPiiClassification:
    if not isinstance(item, Mapping):
        return "none"
    value = item.get("pii_classification")
    if value in {"none", "low", "sensitive", "prohibited"}:
        return value
    return "none"


def _source_summaries(
    *,
    summaries: Sequence[Any],
    tool_prompt_summaries: Sequence[Any],
    case_outcome_summaries: Sequence[Any],
) -> list[str]:
    source_texts: list[str] = []
    for summary in summaries:
        source_texts.append(getattr(summary, "summary_text", "") or "")
    for tool_summary in tool_prompt_summaries:
        source_texts.append(_prompt_summary_text(tool_summary))
    for outcome_summary in case_outcome_summaries:
        source_texts.append(_prompt_summary_text(outcome_summary))

    cleaned: list[str] = []
    seen: set[str] = set()
    for text in source_texts:
        safe = _bounded_text(_safe_text(text), _SOURCE_SUMMARY_CHAR_LIMIT)
        if not safe:
            continue
        key = safe.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(safe)
        if len(cleaned) >= _SOURCE_SUMMARY_LIMIT:
            break
    return cleaned


def _prompt_summary_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("prompt_summary", "summary", "text"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
        return ""
    for attr in ("prompt_summary", "summary", "summary_text"):
        candidate = getattr(value, attr, None)
        if isinstance(candidate, str):
            return candidate
    return ""


def _safe_text(value: str) -> str:
    compact = _WHITESPACE_RE.sub(" ", value).strip()
    if not compact:
        return ""
    segments = [segment.strip() for segment in compact.split(" | ") if segment.strip()]
    kept = [segment for segment in segments if not _looks_forbidden(segment)]
    return " | ".join(kept) if kept else ""


def _looks_forbidden(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _FORBIDDEN_KEY_MARKERS)


def _bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 20].rstrip() + "\n[truncated]"
