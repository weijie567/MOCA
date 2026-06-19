"""Policy knowledge facade.

Tenant-over-global precedence is DEFERRED_WITH_OWNER to post-Phase 17
Policy Scope. It depends on a schema and query migration that introduces
global/default policy scope, with schema-and-query tenant-over-global tests as
the acceptance gate.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    RERANK_CONFIG_VERSION,
    RETRIEVAL_CONFIG_VERSION,
)
from src.knowledge.provenance import EvidenceProvenance
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, KnowledgeSearchRequest, KnowledgeSearchResult
from src.knowledge.text_hash import evidence_text_hash


class PolicyRetriever(Protocol):
    async def retrieve(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[str, list[EvidenceRefV1], float]: ...

    async def get_contents_by_evidence_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], str]: ...

    async def get_provenance_by_evidence_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], EvidenceProvenance]: ...

    async def get_canonical_evidence_rows_by_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, Any]]: ...


class VerifiedEvidenceDetail(BaseModel):
    """Canonical Phase 22 evidence row after service-level validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_ref: EvidenceRefV1
    content: str
    policy_document_version: int
    current_policy_version: str
    effective_date: date | None = None
    expires_at: date | None = None
    doc_type: str | None = None
    risk_level: str | None = None
    merchant_ids: list[str] = Field(default_factory=list)


class VerifiedEvidenceExclusion(BaseModel):
    """Typed fail-closed exclusion for an invalid Phase 22 evidence ref."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    reason_code: str
    reason_codes: list[str]
    doc_key: str | None = None
    chunk_id: str | None = None


class VerifiedEvidenceDetailsResult(BaseModel):
    """Batch result for Phase 22 canonical evidence validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    included: dict[str, VerifiedEvidenceDetail] = Field(default_factory=dict)
    excluded: list[VerifiedEvidenceExclusion] = Field(default_factory=list)


class PolicyKnowledgeService:
    def __init__(self, retriever: PolicyRetriever):
        self.retriever = retriever

    async def search(
        self,
        request: KnowledgeSearchRequest,
        context: KnowledgeContext,
    ) -> KnowledgeSearchResult:
        # Merchant filters are authorization inputs only until policy rows gain
        # merchant scope. Deny before adapter execution rather than widening an
        # unauthorized request into an unfiltered tenant search.
        merchant_id = request.filters.merchant_id
        merchant_scope = context.merchant_scope
        if not merchant_scope:
            return self._no_evidence_result()
        if merchant_id is not None and "*" not in merchant_scope and merchant_id not in merchant_scope:
            return self._no_evidence_result()

        doc_type = request.filters.policy_types[0] if request.filters.policy_types else None
        try:
            status, evidence_refs, best_score = await self.retriever.retrieve(
                query=request.query,
                context=context,
                max_results=request.max_results,
                doc_type=doc_type,
            )
        except asyncio.TimeoutError:
            return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
        except Exception:
            return self._error_result(
                "SEARCH_ERROR",
                "Failed to search policy evidence",
                retryable=False,
            )

        if status == "partial_evidence" and not request.allow_partial_evidence:
            return KnowledgeSearchResult(
                status="no_evidence",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                rerank_config_version=RERANK_CONFIG_VERSION,
                best_score=best_score,
                threshold=MIN_SIMILARITY_THRESHOLD,
                evidence_refs=[],
            )

        if status == "error":
            return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
        return KnowledgeSearchResult(
            status=status,
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            best_score=best_score,
            threshold=MIN_SIMILARITY_THRESHOLD,
            evidence_refs=evidence_refs,
        )

    async def get_verified_evidence_contents(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, str]:
        try:
            tenant_uuid = UUID(tenant_id)
        except ValueError:
            return {}

        key_counts = Counter((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
        keys = [key for key, count in key_counts.items() if count == 1 and all(key)]
        if not keys:
            return {}

        try:
            contents = await self.retriever.get_contents_by_evidence_keys(
                tenant_id=tenant_uuid,
                keys=keys,
            )
        except Exception:
            return {}

        verified: dict[str, str] = {}
        for ref in evidence_refs:
            key = (ref.doc_key, ref.chunk_id)
            content = contents.get(key)
            if (
                key_counts.get(key) == 1
                and ref.tenant_id == tenant_id
                and content is not None
                and evidence_text_hash(content) == ref.text_hash
            ):
                verified[ref.evidence_id] = content
        return verified

    async def get_verified_evidence_provenance(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, EvidenceProvenance]:
        try:
            tenant_uuid = UUID(tenant_id)
        except ValueError:
            return {}

        key_counts = Counter((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
        keys = [key for key, count in key_counts.items() if count == 1 and all(key)]
        if not keys:
            return {}

        try:
            contents = await self.retriever.get_contents_by_evidence_keys(
                tenant_id=tenant_uuid,
                keys=keys,
            )
        except Exception:
            return {}

        verified_refs: list[EvidenceRefV1] = []
        for ref in evidence_refs:
            key = (ref.doc_key, ref.chunk_id)
            content = contents.get(key)
            if (
                key_counts.get(key) == 1
                and ref.tenant_id == tenant_id
                and content is not None
                and evidence_text_hash(content) == ref.text_hash
            ):
                verified_refs.append(ref)
        if not verified_refs:
            return {}

        verified_keys = [(ref.doc_key, ref.chunk_id) for ref in verified_refs]
        try:
            provenance_by_key = await self.retriever.get_provenance_by_evidence_keys(
                tenant_id=tenant_uuid,
                keys=verified_keys,
            )
        except Exception:
            return {}

        result: dict[str, EvidenceProvenance] = {}
        for ref in verified_refs:
            key = (ref.doc_key, ref.chunk_id)
            provenance = provenance_by_key.get(key)
            if (
                provenance is None
                or provenance.evidence_id != ref.evidence_id
                or provenance.doc_key != ref.doc_key
                or provenance.chunk_id != ref.chunk_id
                or not provenance.source_locators
            ):
                return {}
            result[ref.evidence_id] = provenance
        return result

    async def get_canonical_evidence_rows(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """Return canonical document/chunk metadata under tenant predicates."""
        try:
            tenant_uuid = UUID(tenant_id)
        except ValueError:
            return {}

        key_counts = Counter((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
        keys = [key for key, count in key_counts.items() if count == 1 and all(key)]
        if not keys or not hasattr(self.retriever, "get_canonical_evidence_rows_by_keys"):
            return {}

        try:
            rows = await self.retriever.get_canonical_evidence_rows_by_keys(
                tenant_id=tenant_uuid,
                keys=keys,
            )
        except Exception:
            return {}
        return rows if isinstance(rows, dict) else {}

    async def get_verified_evidence_details(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
        effective_at: str | None = None,
        merchant_scope: list[str] | None = None,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> VerifiedEvidenceDetailsResult:
        """Validate Phase 22 evidence refs with typed current-row reason codes."""
        effective_date = _effective_date(effective_at)
        try:
            UUID(tenant_id)
        except ValueError:
            return VerifiedEvidenceDetailsResult(
                excluded=[_detail_exclusion(ref, ["tenant_id_malformed"]) for ref in evidence_refs]
            )

        key_counts = Counter((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
        query_refs = [
            ref
            for ref in evidence_refs
            if key_counts[(ref.doc_key, ref.chunk_id)] == 1 and ref.doc_key and ref.chunk_id
        ]
        rows = await self.get_canonical_evidence_rows(tenant_id=tenant_id, evidence_refs=query_refs)

        included: dict[str, VerifiedEvidenceDetail] = {}
        excluded: list[VerifiedEvidenceExclusion] = []
        for ref in evidence_refs:
            reason_codes: list[str] = []
            key = (ref.doc_key, ref.chunk_id)
            if not _valid_uuid(ref.tenant_id):
                reason_codes.append("tenant_id_malformed")
            elif ref.tenant_id != tenant_id:
                reason_codes.append("tenant_mismatch")
            if key_counts[key] > 1:
                reason_codes.append("duplicate_evidence_key")

            row = rows.get(key) if not reason_codes else None
            if row is None and not reason_codes:
                reason_codes.append("canonical_content_missing")
            if reason_codes:
                excluded.append(_detail_exclusion(ref, reason_codes))
                continue

            row_content = str(row.get("content") or "")
            current_policy_version = str(
                row.get("current_policy_version") or f"v{int(row.get('policy_document_version') or 1)}"
            )
            row_effective_date = _row_date(row.get("effective_date"))
            row_expires_at = _row_date(row.get("expires_at"))
            row_doc_type = _optional_str(row.get("doc_type"))
            row_risk_level = _optional_str(row.get("risk_level"))
            row_merchant_ids = [str(item) for item in row.get("merchant_ids") or [] if str(item)]

            if not row_content:
                reason_codes.append("canonical_content_missing")
            elif evidence_text_hash(row_content) != ref.text_hash:
                reason_codes.append("text_hash_mismatch")
            if current_policy_version != ref.policy_version:
                reason_codes.append("latest_version_invalid")
            if effective_date is not None and row_effective_date is not None and row_effective_date > effective_date:
                reason_codes.extend(["freshness_invalid", "effective_date_invalid"])
            if effective_date is not None and row_expires_at is not None and row_expires_at < effective_date:
                reason_codes.extend(["freshness_invalid", "effective_date_invalid"])
            reason_codes.extend(
                _scope_reason_codes(
                    merchant_scope=merchant_scope,
                    row_merchant_ids=row_merchant_ids,
                    expected_doc_type=doc_type,
                    row_doc_type=row_doc_type,
                    expected_risk_level=risk_level,
                    row_risk_level=row_risk_level,
                )
            )

            if reason_codes:
                excluded.append(_detail_exclusion(ref, reason_codes))
                continue

            included[ref.evidence_id] = VerifiedEvidenceDetail(
                evidence_ref=ref,
                content=row_content,
                policy_document_version=int(row.get("policy_document_version") or 1),
                current_policy_version=current_policy_version,
                effective_date=row_effective_date,
                expires_at=row_expires_at,
                doc_type=row_doc_type,
                risk_level=row_risk_level,
                merchant_ids=row_merchant_ids,
            )
        return VerifiedEvidenceDetailsResult(included=included, excluded=excluded)

    @staticmethod
    def _no_evidence_result() -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            status="no_evidence",
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            best_score=0.0,
            threshold=MIN_SIMILARITY_THRESHOLD,
            evidence_refs=[],
        )

    @staticmethod
    def _error_result(error_code: str, message: str, *, retryable: bool) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            status="error",
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            best_score=0.0,
            threshold=MIN_SIMILARITY_THRESHOLD,
            evidence_refs=[],
            error={
                "error_code": error_code,
                "message": message,
                "retryable": retryable,
            },
        )


def _detail_exclusion(ref: EvidenceRefV1, reason_codes: list[str]) -> VerifiedEvidenceExclusion:
    ordered = list(dict.fromkeys(reason_codes))
    return VerifiedEvidenceExclusion(
        evidence_id=ref.evidence_id,
        reason_code=ordered[0],
        reason_codes=ordered,
        doc_key=ref.doc_key,
        chunk_id=ref.chunk_id,
    )


def _effective_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _row_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _valid_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _scope_reason_codes(
    *,
    merchant_scope: list[str] | None,
    row_merchant_ids: list[str],
    expected_doc_type: str | None,
    row_doc_type: str | None,
    expected_risk_level: str | None,
    row_risk_level: str | None,
) -> list[str]:
    reason_codes: list[str] = []
    if (
        row_merchant_ids
        and "*" not in (merchant_scope or [])
        and not set(row_merchant_ids).intersection(merchant_scope or [])
    ):
        reason_codes.extend(["scope_invalid", "merchant_scope_invalid"])
    if expected_doc_type and row_doc_type and row_doc_type != expected_doc_type:
        reason_codes.extend(["scope_invalid", "doc_type_invalid"])
    if expected_risk_level and row_risk_level and row_risk_level != expected_risk_level:
        reason_codes.extend(["scope_invalid", "risk_level_invalid"])
    return reason_codes
