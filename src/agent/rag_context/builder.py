"""Build prompt-safe RAG context bundles from already-retrieved evidence."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from src.agent.rag_context.schemas import (
    CitationMapEntry,
    EvidenceTraceEntry,
    PromptCitation,
    RagContextBudget,
    RagContextBudgetTrace,
    RagContextBuildInput,
    RagContextBundle,
    RagDebugContext,
    RagPromptContext,
    RagSafeContext,
    RagVerifierContext,
)
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


_TRUNCATION_MARKER = " [truncated]"
_SAFE_RISK_LABELS = frozenset(
    {
        "authority_checked",
        "conflict",
        "freshness_risk",
        "high_risk",
        "latest_version_checked",
        "ocr_low_confidence",
        "provenance_available",
        "source_locator_available",
        "stale_evidence",
    }
)
_SAFE_TRUSTED_CONTEXT_KEYS = ("tenant_id", "run_id", "thread_id", "effective_at")
_LEAKAGE_SENTINEL_RE = re.compile(r"\bSHOULD_NOT_[A-Z0-9_]+")


class ContextBuilder:
    """Validate evidence refs and project them into safe context surfaces."""

    def __init__(
        self,
        *,
        policy_service: Any,
        budget: RagContextBudget | None = None,
        max_snippet_chars: int | None = None,
        merge_adjacent_chunks: bool = False,
    ) -> None:
        self.policy_service = policy_service
        if budget is None:
            budget = RagContextBudget()
        if max_snippet_chars is not None:
            budget = budget.model_copy(update={"max_snippet_chars": max_snippet_chars})
        self.budget = budget
        self.merge_adjacent_chunks = merge_adjacent_chunks

    async def build(
        self,
        *,
        candidate_evidence_refs: Sequence[EvidenceRefV1],
        business_fact_refs: Sequence[BusinessFactRefV1],
        trusted_context: Mapping[str, Any],
        risk_hints: Sequence[Mapping[str, Any]] | None = None,
    ) -> RagContextBundle:
        build_input = RagContextBuildInput(
            candidate_evidence_refs=list(candidate_evidence_refs),
            business_fact_refs=list(business_fact_refs),
            trusted_context=dict(trusted_context),
            risk_hints=[dict(hint) for hint in risk_hints or []],
        )
        tenant_id = str(build_input.trusted_context.get("tenant_id") or "")
        risk_labels_by_id = _risk_labels_by_evidence_id(build_input.risk_hints)

        retained_refs, initial_exclusions = _dedupe_candidates(build_input.candidate_evidence_refs)
        contents = await self._verified_contents(tenant_id=tenant_id, refs=retained_refs)

        included: list[_IncludedEvidence] = []
        exclusions = list(initial_exclusions)
        for ref in retained_refs:
            if not _valid_uuid(ref.tenant_id):
                exclusions.append(_trace(ref, "tenant_id_malformed"))
                continue
            if ref.tenant_id != tenant_id:
                exclusions.append(_trace(ref, "tenant_mismatch"))
                continue
            content = contents.get(ref.evidence_id)
            if content is None:
                exclusions.append(_trace(ref, self._missing_content_reason(ref)))
                continue
            included.append(
                _IncludedEvidence(
                    evidence_ref=ref,
                    content=content,
                    risk_labels=risk_labels_by_id.get(ref.evidence_id, []),
                )
            )

        included.sort(key=lambda item: (item.evidence_ref.rank or 10_000, item.evidence_ref.evidence_id))
        budget_included, budget_excluded = _apply_evidence_item_budget(included, self.budget.max_evidence_items)
        exclusions.extend(budget_excluded)

        citation_items = _merge_adjacent(budget_included) if self.merge_adjacent_chunks else [[item] for item in budget_included]
        prompt_citations: list[PromptCitation] = []
        citation_map: dict[str, CitationMapEntry] = {}
        budget_truncated: list[EvidenceTraceEntry] = []
        debug_included: list[EvidenceTraceEntry] = []

        for index, group in enumerate(citation_items, start=1):
            citation_id = f"C{index}"
            primary = group[0]
            source_ids = [item.evidence_ref.evidence_id for item in group]
            merged_chunk_ids = [item.evidence_ref.chunk_id for item in group[1:]]
            content = "\n".join(item.content for item in group)
            snippet, truncated = _bounded_snippet(content, self.budget.max_snippet_chars)
            labels = _unique_label_list(label for item in group for label in item.risk_labels)
            metadata = {
                "doc_key": primary.evidence_ref.doc_key,
                "chunk_id": primary.evidence_ref.chunk_id,
                "policy_version": primary.evidence_ref.policy_version,
            }
            citation = PromptCitation(
                citation_id=citation_id,
                display_label=_display_label(group),
                snippet=snippet,
                risk_labels=labels,
                metadata=metadata,
                merged_from_chunk_ids=merged_chunk_ids,
            )
            prompt_citations.append(citation)
            citation_map[citation_id] = CitationMapEntry(
                citation_id=citation_id,
                evidence_ref=primary.evidence_ref,
                source_evidence_ids=source_ids,
                snippet=snippet,
                risk_labels=labels,
                metadata=metadata,
                merged_from_chunk_ids=merged_chunk_ids,
            )
            debug_included.append(_trace(primary.evidence_ref, "included", citation_id=citation_id))
            if truncated:
                for item in group:
                    budget_truncated.append(_trace(item.evidence_ref, "snippet_truncated", citation_id=citation_id))

        safe_risk_labels = _unique_label_list(label for citation in prompt_citations for label in citation.risk_labels)
        safe_context = RagSafeContext(citations=prompt_citations, risk_labels=safe_risk_labels)
        budget_trace = RagContextBudgetTrace(
            max_prompt_chars=self.budget.max_prompt_chars,
            protected_metadata_preserved=True,
            included=debug_included,
            truncated=budget_truncated,
            excluded=exclusions,
        )

        return RagContextBundle(
            tenant_id=tenant_id,
            trusted_context=dict(build_input.trusted_context),
            citation_map=citation_map,
            prompt_context=RagPromptContext(
                citations=prompt_citations,
                risk_labels=safe_risk_labels,
                trusted_context=_safe_trusted_context(build_input.trusted_context),
            ),
            verifier_context=RagVerifierContext(
                evidence_snippets=[
                    {
                        "citation_id": citation_id,
                        "evidence_id": entry.evidence_ref.evidence_id,
                        "text": entry.snippet,
                    }
                    for citation_id, entry in citation_map.items()
                ],
                business_fact_refs=build_input.business_fact_refs,
                safe_refs=[entry.evidence_ref.evidence_id for entry in citation_map.values()],
            ),
            debug_context=RagDebugContext(
                included_evidence=debug_included,
                truncated_or_excluded_evidence=[*exclusions, *budget_truncated],
                raw_risk_hints=build_input.risk_hints,
            ),
            final_response_context=safe_context,
            memory_context=safe_context,
            replay_context=safe_context,
            business_fact_context=safe_context,
            action_snapshot_context=safe_context,
            budget_trace=budget_trace,
        )

    async def _verified_contents(self, *, tenant_id: str, refs: list[EvidenceRefV1]) -> dict[str, str]:
        if not refs or not hasattr(self.policy_service, "get_verified_evidence_contents"):
            return {}
        try:
            result = await self.policy_service.get_verified_evidence_contents(
                tenant_id=tenant_id,
                evidence_refs=refs,
            )
        except Exception:
            return {}
        return result if isinstance(result, dict) else {}

    def _missing_content_reason(self, ref: EvidenceRefV1) -> str:
        authorized = getattr(self.policy_service, "authorized_evidence_ids", None)
        if authorized is not None and ref.evidence_id not in authorized:
            return "scope_invalid"
        latest_versions = getattr(self.policy_service, "latest_versions", None)
        if isinstance(latest_versions, Mapping) and latest_versions.get(ref.doc_key, ref.policy_version) != ref.policy_version:
            return "latest_version_invalid"
        return "canonical_content_missing"


class _IncludedEvidence:
    def __init__(self, *, evidence_ref: EvidenceRefV1, content: str, risk_labels: list[str]) -> None:
        self.evidence_ref = evidence_ref
        self.content = content
        self.risk_labels = risk_labels


def _dedupe_candidates(refs: list[EvidenceRefV1]) -> tuple[list[EvidenceRefV1], list[EvidenceTraceEntry]]:
    grouped: dict[tuple[str, str], list[EvidenceRefV1]] = defaultdict(list)
    for ref in refs:
        grouped[(ref.doc_key, ref.chunk_id)].append(ref)

    retained: list[EvidenceRefV1] = []
    excluded: list[EvidenceTraceEntry] = []
    for group in grouped.values():
        if len(group) == 1:
            retained.append(group[0])
            continue
        identities = {(ref.evidence_id, ref.text_hash, ref.policy_version) for ref in group}
        if len(identities) == 1:
            retained.append(group[0])
            excluded.extend(_trace(ref, "duplicate_evidence_key") for ref in group[1:])
        else:
            excluded.extend(_trace(ref, "duplicate_evidence_key") for ref in group)
    return retained, excluded


def _apply_evidence_item_budget(
    included: list[_IncludedEvidence],
    max_items: int,
) -> tuple[list[_IncludedEvidence], list[EvidenceTraceEntry]]:
    kept = included[:max_items]
    excluded = [_trace(item.evidence_ref, "budget_evidence_item_limit") for item in included[max_items:]]
    return kept, excluded


def _merge_adjacent(items: list[_IncludedEvidence]) -> list[list[_IncludedEvidence]]:
    groups: list[list[_IncludedEvidence]] = []
    for item in items:
        if not groups:
            groups.append([item])
            continue
        previous = groups[-1][-1].evidence_ref
        current = item.evidence_ref
        if previous.doc_key == current.doc_key and _chunk_number(current.chunk_id) == _chunk_number(previous.chunk_id) + 1:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def _chunk_number(chunk_id: str) -> int:
    match = re.search(r"(\d+)$", chunk_id)
    return int(match.group(1)) if match else -10_000


def _display_label(group: list[_IncludedEvidence]) -> str:
    primary = group[0].evidence_ref
    if len(group) == 1:
        return f"{primary.doc_key} / {primary.chunk_id}"
    return f"{primary.doc_key} / {primary.chunk_id}-{group[-1].evidence_ref.chunk_id}"


def _bounded_snippet(content: str, max_chars: int) -> tuple[str, bool]:
    safe = _sanitize_ordinary_text(" ".join(content.split()))
    if len(safe) <= max_chars:
        return safe, False
    limit = max(0, max_chars - len(_TRUNCATION_MARKER))
    return safe[:limit].rstrip() + _TRUNCATION_MARKER, True


def _sanitize_ordinary_text(value: str) -> str:
    return _LEAKAGE_SENTINEL_RE.sub("", value).strip()


def _trace(ref: EvidenceRefV1, reason_code: str, *, citation_id: str | None = None) -> EvidenceTraceEntry:
    return EvidenceTraceEntry(
        evidence_id=ref.evidence_id,
        reason_code=reason_code,
        reason_codes=[reason_code],
        citation_id=citation_id,
        doc_key=ref.doc_key,
        chunk_id=ref.chunk_id,
    )


def _risk_labels_by_evidence_id(hints: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    for hint in hints:
        evidence_id = str(hint.get("evidence_id") or "")
        if not evidence_id:
            continue
        labels[evidence_id] = _unique_label_list(
            str(label) for label in hint.get("labels") or [] if str(label) in _SAFE_RISK_LABELS
        )
    return labels


def _unique_label_list(labels: Any) -> list[str]:
    result: list[str] = []
    for label in labels:
        if label and label not in result:
            result.append(label)
    return result


def _safe_trusted_context(context: Mapping[str, Any]) -> dict[str, str]:
    return {key: str(context[key]) for key in _SAFE_TRUSTED_CONTEXT_KEYS if context.get(key) is not None}


def _valid_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True
