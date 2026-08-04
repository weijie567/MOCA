"""Policy knowledge facade.

Tenant-over-global precedence is DEFERRED_WITH_OWNER to post-Phase 17
Policy Scope. It depends on a schema and query migration that introduces
global/default policy scope, with schema-and-query tenant-over-global tests as
the acceptance gate.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.agent.rag_context.builder import ContextBuilder
from src.agent.rag_context.claims import normalize_material_claim_v1
from src.agent.rag_context.schemas import MaterialClaim, MaterialClaimAuthorityClass
from src.agent.rag_context.verifier import (
    MaterialClaimVerificationResult,
    MaterialClaimVerifier,
    VerificationOutcome,
)
from src.knowledge.diagnostics import RankingExplanation, RetrievalDiagnostics
from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    RERANK_CONFIG_VERSION,
    RETRIEVAL_CONFIG_VERSION,
)
from src.knowledge.provenance import EvidenceProvenance
from src.knowledge.schemas import (
    ClaimVerificationBundleV1,
    ClaimVerificationResultV1,
    EvidenceItemV1,
    EvidenceRefV1,
    KnowledgeContext,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
    MaterialClaimV1,
    VerifiedEvidencePackageV1,
)
from src.knowledge.text_hash import evidence_text_hash
from src.tools.contracts import BusinessFactRefV1

_INTERNAL_DIAGNOSTIC_TYPES = (RetrievalDiagnostics, RankingExplanation)


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
        merchant_id = request.filters.merchant_id
        merchant_scope = context.merchant_scope
        if merchant_scope is None:
            return self._no_evidence_result()
        # Policy-only tenant public retrieval is authorized by trusted tenant
        # identity and knowledge permission; business merchant scope is checked
        # only when an explicit merchant/business policy filter is requested.
        if merchant_id is not None and "*" not in merchant_scope and merchant_id not in merchant_scope:
            return self._no_evidence_result()

        doc_type = request.filters.policy_types[0] if request.filters.policy_types else None
        query_rewrite_summary: str | None = None
        try:
            if hasattr(self.retriever, "retrieve_run"):
                run = await self.retriever.retrieve_run(
                    query=request.query,
                    context=context,
                    max_results=request.max_results,
                    doc_type=doc_type,
                )
                status = run.status
                evidence_refs = run.evidence_refs
                best_score = run.best_score
                query_rewrite_summary = run.query_rewrite_summary
            else:
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
            query_rewrite=query_rewrite_summary,
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
        effective_at_malformed = bool(effective_at) and effective_date is None
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
            if effective_at_malformed:
                reason_codes.extend(["freshness_invalid", "effective_date_invalid"])
            elif effective_date is not None and row_effective_date is not None and row_effective_date > effective_date:
                reason_codes.extend(["freshness_invalid", "effective_date_invalid"])
            elif effective_date is not None and row_expires_at is not None and row_expires_at < effective_date:
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

    async def build_verified_context(
        self,
        *,
        candidate_evidence_refs: Sequence[EvidenceRefV1 | Mapping[str, Any]],
        business_fact_refs: Sequence[BusinessFactRefV1 | Mapping[str, Any]] | None,
        knowledge_context: KnowledgeContext,
        evidence_policy: Mapping[str, Any] | None = None,
    ) -> VerifiedEvidencePackageV1:
        """Validate candidate evidence refs and expose the Phase 33 package contract."""
        policy = dict(evidence_policy or {})
        candidates = [_coerce_evidence_ref(ref) for ref in candidate_evidence_refs]
        business_refs = [_coerce_business_fact_ref(ref) for ref in business_fact_refs or []]
        retrieval_config_version = _package_retrieval_config_version(candidates, policy)
        evidence_required = bool(policy.get("evidence_required", True))
        if not evidence_required:
            return _empty_verified_package(
                status="not_required",
                knowledge_context=knowledge_context,
                retrieval_config_version=retrieval_config_version,
                reason_codes=["evidence_not_required"],
            )
        if not candidates:
            return _empty_verified_package(
                status="no_evidence",
                knowledge_context=knowledge_context,
                retrieval_config_version=retrieval_config_version,
                reason_codes=["candidate_evidence_required"],
            )

        trusted_context = _package_trusted_context(knowledge_context, policy)
        try:
            details = await self.get_verified_evidence_details(
                tenant_id=knowledge_context.tenant_id,
                evidence_refs=candidates,
                effective_at=knowledge_context.effective_at,
                merchant_scope=knowledge_context.merchant_scope,
                doc_type=_optional_str(policy.get("doc_type")),
                risk_level=_optional_str(policy.get("risk_level")),
            )
            bundle = await ContextBuilder(policy_service=self).build(
                candidate_evidence_refs=candidates,
                business_fact_refs=business_refs,
                trusted_context=trusted_context,
                risk_hints=_risk_hints(policy),
            )
        except Exception:
            return _empty_verified_package(
                status="build_error",
                knowledge_context=knowledge_context,
                retrieval_config_version=retrieval_config_version,
                reason_codes=["build_error"],
                rejected_candidate_refs=candidates,
            )

        included = dict(details.included)
        excluded = list(details.excluded)
        reason_codes = _unique(
            code for exclusion in excluded for code in (exclusion.reason_codes or [exclusion.reason_code])
        )
        status = _verified_package_status(
            included_count=len(included),
            excluded_reason_codes=set(reason_codes),
            total_candidates=len(candidates),
        )
        citation_map = {
            citation_id: list(entry.source_evidence_ids) for citation_id, entry in bundle.citation_map.items()
        }
        evidence_map = {evidence_id: detail.evidence_ref for evidence_id, detail in included.items()}
        policy_version = _package_policy_version(included, candidates, policy)
        stale_refs, conflict_refs, rejected_refs = _partition_rejected_refs(candidates, excluded)

        return VerifiedEvidencePackageV1(
            package_id=_package_id(knowledge_context, candidates),
            status=status,
            evidence_items=[_evidence_item_from_detail(detail, bundle=bundle) for detail in included.values()],
            citation_map=citation_map,
            evidence_map=evidence_map,
            prompt_projection=bundle.prompt_context.model_dump(mode="json"),
            verifier_projection=bundle.verifier_context.model_dump(mode="json"),
            replay_snapshot_refs=list(evidence_map),
            debug_projection=bundle.debug_context.model_dump(mode="json"),
            stale_refs=stale_refs,
            conflict_refs=conflict_refs,
            rejected_candidate_refs=rejected_refs,
            reason_codes=reason_codes,
            policy_version=policy_version,
            retrieval_config_version=retrieval_config_version,
        )

    async def verify_claims(
        self,
        *,
        material_claims: Sequence[MaterialClaimV1 | MaterialClaim | Mapping[str, Any]],
        verified_evidence_package: VerifiedEvidencePackageV1 | Mapping[str, Any] | None,
        business_context: Mapping[str, Any] | None,
        proposed_action: Mapping[str, Any] | None,
    ) -> ClaimVerificationBundleV1:
        """Aggregate material claim checks into the Phase 33 bundle contract."""
        try:
            claims = [normalize_material_claim_v1(claim) for claim in material_claims]
            package = (
                VerifiedEvidencePackageV1.model_validate(verified_evidence_package)
                if verified_evidence_package is not None
                else None
            )
        except Exception:
            return _claim_error_bundle("claim_input_malformed")

        if not claims:
            return ClaimVerificationBundleV1(
                overall_status="not_required",
                route="continue",
                claim_results=[],
                blocked_claims=[],
                safe_support_refs=[],
                reason_codes=["no_material_claims"],
                verifier_policy_version="material_claim_verifier.v1",
            )
        if package is None:
            return _blocked_package_bundle(claims, "verified_evidence_package_required")
        if package.status not in {"verified", "partial", "not_required"}:
            return _blocked_package_bundle(claims, f"rag_context_{package.status}", package.reason_codes)

        context_bundle = _claim_context_bundle(package, business_context or {})
        verifier = MaterialClaimVerifier()
        ordered_claims = list(claims)
        verification_order = [
            *[
                (index, claim)
                for index, claim in enumerate(ordered_claims)
                if claim.claim_type != "action_recommendation"
            ],
            *[
                (index, claim)
                for index, claim in enumerate(ordered_claims)
                if claim.claim_type == "action_recommendation"
            ],
        ]
        results_by_index: dict[int, MaterialClaimVerificationResult] = {}
        claim_results: list[ClaimVerificationResultV1] = []
        dependency_results: list[dict[str, Any]] = []
        blocked_claims: list[str] = []
        reason_codes: list[str] = []
        safe_support_refs: list[EvidenceRefV1] = []

        for index, claim in verification_order:
            legacy_claim = _legacy_claim_from_material_v1(claim, ordered_claims)
            result = await verifier.verify_claim(
                legacy_claim,
                context_bundle=context_bundle,
                dependency_results=dependency_results,
            )
            results_by_index[index] = result
            dependency_results.append(
                {
                    "claim_id": claim.claim_id,
                    "claim_type": claim.claim_type,
                    "outcome": _outcome_value(result.outcome),
                }
            )

        for index, claim in enumerate(ordered_claims):
            result = results_by_index[index]
            reason_codes.extend(result.reason_codes)
            claim_result = _claim_result_from_verifier_result(
                claim=claim,
                result=result,
                evidence_map=package.evidence_map,
            )
            claim_results.append(claim_result)
            safe_support_refs.extend(claim_result.supporting_evidence_refs)
            if _claim_is_blocked(claim, result, proposed_action):
                blocked_claims.append(claim.claim_id)

        bundle_reason_codes = _unique(reason_codes)
        if _needs_manual_review(bundle_reason_codes):
            overall_status = "manual_review"
            route = "manual_review"
        elif blocked_claims:
            overall_status = "blocked"
            route = "final_response"
        else:
            overall_status = "verified"
            route = "continue"

        return ClaimVerificationBundleV1(
            overall_status=overall_status,
            route=route,
            claim_results=claim_results,
            blocked_claims=blocked_claims,
            safe_support_refs=_unique_evidence_refs(safe_support_refs),
            reason_codes=bundle_reason_codes,
            verifier_policy_version="material_claim_verifier.v1",
        )

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


def _coerce_evidence_ref(value: EvidenceRefV1 | Mapping[str, Any]) -> EvidenceRefV1:
    return value if isinstance(value, EvidenceRefV1) else EvidenceRefV1.model_validate(value)


def _coerce_business_fact_ref(value: BusinessFactRefV1 | Mapping[str, Any]) -> BusinessFactRefV1:
    return value if isinstance(value, BusinessFactRefV1) else BusinessFactRefV1.model_validate(value)


def _package_trusted_context(context: KnowledgeContext, policy: Mapping[str, Any]) -> dict[str, Any]:
    doc_type = _optional_str(policy.get("doc_type"))
    risk_level = _optional_str(policy.get("risk_level"))
    trusted: dict[str, Any] = {
        "tenant_id": context.tenant_id,
        "user_id": context.user_id,
        "role": context.role,
        "merchant_scope": list(context.merchant_scope or []),
        "run_id": context.run_id,
        "trace_id": context.trace_id,
        "locale": context.locale,
        "effective_at": context.effective_at,
        "filters": {"doc_type": doc_type, "risk_level": risk_level},
        "scope": {
            "merchant_ids": list(context.merchant_scope or []),
            "doc_types": [doc_type] if doc_type else [],
            "risk_levels": [risk_level] if risk_level else [],
        },
    }
    return trusted


def _risk_hints(policy: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    hints = policy.get("risk_hints")
    return [dict(item) for item in hints] if isinstance(hints, list) else []


def _package_retrieval_config_version(
    refs: Sequence[EvidenceRefV1],
    policy: Mapping[str, Any],
) -> str:
    configured = _optional_str(policy.get("retrieval_config_version"))
    if configured:
        return configured
    if refs:
        return refs[0].retrieval_config_version
    return RETRIEVAL_CONFIG_VERSION


def _empty_verified_package(
    *,
    status: str,
    knowledge_context: KnowledgeContext,
    retrieval_config_version: str,
    reason_codes: list[str],
    rejected_candidate_refs: list[EvidenceRefV1] | None = None,
) -> VerifiedEvidencePackageV1:
    return VerifiedEvidencePackageV1(
        package_id=f"verified-evidence:{knowledge_context.run_id}:empty",
        status=status,
        evidence_items=[],
        citation_map={},
        evidence_map={},
        prompt_projection={},
        verifier_projection={"safe_refs": [], "evidence_snippets": [], "business_fact_refs": []},
        replay_snapshot_refs=[],
        debug_projection={"reason_codes": reason_codes},
        stale_refs=[],
        conflict_refs=[],
        rejected_candidate_refs=rejected_candidate_refs or [],
        reason_codes=reason_codes,
        policy_version="unknown",
        retrieval_config_version=retrieval_config_version,
    )


def _verified_package_status(
    *,
    included_count: int,
    excluded_reason_codes: set[str],
    total_candidates: int,
) -> str:
    if included_count == total_candidates and not excluded_reason_codes:
        return "verified"
    if "text_hash_mismatch" in excluded_reason_codes:
        return "invalid_hash"
    if excluded_reason_codes & {
        "scope_invalid",
        "merchant_scope_invalid",
        "doc_type_invalid",
        "risk_level_invalid",
        "tenant_mismatch",
        "tenant_id_malformed",
    }:
        return "invalid_scope"
    if excluded_reason_codes & {"unauthorized", "permission_denied", "acl_denied"}:
        return "unauthorized"
    if excluded_reason_codes & {
        "latest_version_invalid",
        "freshness_invalid",
        "effective_date_invalid",
    }:
        return "stale"
    if excluded_reason_codes & {"conflict", "policy_conflict", "source_conflict"}:
        return "conflict"
    if included_count and excluded_reason_codes:
        return "partial"
    return "no_evidence"


def _package_policy_version(
    included: Mapping[str, VerifiedEvidenceDetail],
    refs: Sequence[EvidenceRefV1],
    policy: Mapping[str, Any],
) -> str:
    configured = _optional_str(policy.get("policy_version"))
    if configured:
        return configured
    if included:
        return next(iter(included.values())).current_policy_version
    if refs:
        return refs[0].policy_version
    return "unknown"


def _package_id(context: KnowledgeContext, refs: Sequence[EvidenceRefV1]) -> str:
    first_ref = refs[0].evidence_id if refs else "none"
    return f"verified-evidence:{context.run_id}:{first_ref}"


def _evidence_item_from_detail(
    detail: VerifiedEvidenceDetail,
    *,
    bundle: Any,
) -> EvidenceItemV1:
    citation_entry = next(
        (
            entry
            for entry in bundle.citation_map.values()
            if detail.evidence_ref.evidence_id in entry.source_evidence_ids
        ),
        None,
    )
    snippet = citation_entry.snippet if citation_entry is not None else detail.content
    return EvidenceItemV1(
        ref=detail.evidence_ref,
        snippet=snippet,
        text_hash=detail.evidence_ref.text_hash,
        doc_version=f"v{detail.policy_document_version}",
        policy_version=detail.current_policy_version,
        effective_date_result="valid",
        tenant_scope_result="valid",
        authority_level="tenant_policy",
        source_locator={"doc_key": detail.evidence_ref.doc_key, "chunk_id": detail.evidence_ref.chunk_id},
        captured_at=_captured_at_from_ref(detail.evidence_ref),
    )


def _captured_at_from_ref(ref: EvidenceRefV1) -> datetime:
    try:
        return datetime.fromisoformat(ref.retrieved_at.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def _partition_rejected_refs(
    refs: Sequence[EvidenceRefV1],
    exclusions: Sequence[VerifiedEvidenceExclusion],
) -> tuple[list[EvidenceRefV1], list[EvidenceRefV1], list[EvidenceRefV1]]:
    by_id = {ref.evidence_id: ref for ref in refs}
    stale: list[EvidenceRefV1] = []
    conflict: list[EvidenceRefV1] = []
    rejected: list[EvidenceRefV1] = []
    for exclusion in exclusions:
        ref = by_id.get(exclusion.evidence_id)
        if ref is None:
            continue
        codes = set(exclusion.reason_codes or [exclusion.reason_code])
        if codes & {"latest_version_invalid", "freshness_invalid", "effective_date_invalid"}:
            stale.append(ref)
        elif codes & {"conflict", "policy_conflict", "source_conflict"}:
            conflict.append(ref)
        else:
            rejected.append(ref)
    return stale, conflict, rejected


def _claim_error_bundle(reason_code: str) -> ClaimVerificationBundleV1:
    return ClaimVerificationBundleV1(
        overall_status="error",
        route="final_response",
        claim_results=[],
        blocked_claims=[],
        safe_support_refs=[],
        reason_codes=[reason_code],
        verifier_policy_version="material_claim_verifier.v1",
    )


def _blocked_package_bundle(
    claims: Sequence[MaterialClaimV1],
    reason_code: str,
    package_reason_codes: Sequence[str] | None = None,
) -> ClaimVerificationBundleV1:
    reason_codes = _unique([reason_code, *(package_reason_codes or [])])
    return ClaimVerificationBundleV1(
        overall_status="error" if reason_code.endswith("build_error") else "blocked",
        route="final_response",
        claim_results=[
            ClaimVerificationResultV1(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                support_status="error" if reason_code.endswith("build_error") else "unsupported",
                supporting_evidence_refs=[],
                business_fact_refs=claim.business_fact_refs,
                rule_checks=[{"rule": reason_code, "passed": False}],
                semantic_review_status="not_needed",
                allows_user_visible_claim=False,
                allows_action_recommendation=False,
            )
            for claim in claims
        ],
        blocked_claims=[claim.claim_id for claim in claims],
        safe_support_refs=[],
        reason_codes=reason_codes,
        verifier_policy_version="material_claim_verifier.v1",
    )


def _claim_context_bundle(
    package: VerifiedEvidencePackageV1,
    business_context: Mapping[str, Any],
) -> dict[str, Any]:
    trusted_context = {"tenant_id": _package_tenant_id(package)}
    snippet_by_evidence_id = _snippet_by_evidence_id(package)
    citation_map: dict[str, dict[str, Any]] = {}
    for citation_id, evidence_ids in package.citation_map.items():
        if not evidence_ids:
            continue
        primary_id = evidence_ids[0]
        ref = package.evidence_map.get(primary_id)
        if ref is None:
            continue
        citation_map[citation_id] = {
            "citation_id": citation_id,
            "evidence_ref": ref.model_dump(mode="json"),
            "source_evidence_ids": list(evidence_ids),
            "snippet": snippet_by_evidence_id.get(primary_id, ""),
            "risk_labels": [],
        }

    verifier_projection = dict(package.verifier_projection)
    business_refs = _business_fact_refs_for_verifier(verifier_projection, business_context)
    verifier_projection["business_fact_refs"] = [ref.model_dump(mode="json") for ref in business_refs]
    verifier_projection.setdefault("evidence_snippets", _evidence_snippets_from_package(package))
    verifier_projection.setdefault("safe_refs", list(package.evidence_map))
    return {
        "trusted_context": trusted_context,
        "citation_map": citation_map,
        "verifier_context": verifier_projection,
        "business_context": dict(business_context),
    }


def _package_tenant_id(package: VerifiedEvidencePackageV1) -> str:
    if package.evidence_map:
        return next(iter(package.evidence_map.values())).tenant_id
    for ref in [*package.rejected_candidate_refs, *package.stale_refs, *package.conflict_refs]:
        return ref.tenant_id
    return ""


def _snippet_by_evidence_id(package: VerifiedEvidencePackageV1) -> dict[str, str]:
    snippets: dict[str, str] = {}
    for item in package.evidence_items:
        snippets[item.ref.evidence_id] = item.snippet
    raw_snippets = package.verifier_projection.get("evidence_snippets")
    if isinstance(raw_snippets, list):
        for raw in raw_snippets:
            if isinstance(raw, Mapping):
                evidence_id = _optional_str(raw.get("evidence_id"))
                text = _optional_str(raw.get("text"))
                if evidence_id and text:
                    snippets[evidence_id] = text
    return snippets


def _evidence_snippets_from_package(package: VerifiedEvidencePackageV1) -> list[dict[str, str]]:
    snippets = _snippet_by_evidence_id(package)
    result: list[dict[str, str]] = []
    for citation_id, evidence_ids in package.citation_map.items():
        for evidence_id in evidence_ids:
            result.append(
                {
                    "citation_id": citation_id,
                    "evidence_id": evidence_id,
                    "text": snippets.get(evidence_id, ""),
                }
            )
    return result


def _business_fact_refs_for_verifier(
    verifier_projection: Mapping[str, Any],
    business_context: Mapping[str, Any],
) -> list[BusinessFactRefV1]:
    refs: list[BusinessFactRefV1] = []
    for item in verifier_projection.get("business_fact_refs") or []:
        try:
            refs.append(_coerce_business_fact_ref(item))
        except Exception:
            continue
    for item in business_context.get("business_fact_refs") or []:
        try:
            refs.append(_coerce_business_fact_ref(item))
        except Exception:
            continue
    for item in business_context.get("business_fact_results") or []:
        if not isinstance(item, Mapping) or item.get("status") not in {"ok", "partial"}:
            continue
        for raw_ref in item.get("business_fact_refs") or []:
            try:
                refs.append(_coerce_business_fact_ref(raw_ref))
            except Exception:
                continue
    return _unique_business_fact_refs(refs)


def _unique_business_fact_refs(refs: Sequence[BusinessFactRefV1]) -> list[BusinessFactRefV1]:
    unique_refs: list[BusinessFactRefV1] = []
    seen: set[tuple[str, str, str, str, str | None]] = set()
    for ref in refs:
        key = (ref.tenant_id, ref.source_system, ref.resource_type, ref.resource_id, ref.resource_version)
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)
    return unique_refs


def _legacy_claim_from_material_v1(claim: MaterialClaimV1, all_claims: Sequence[MaterialClaimV1]) -> MaterialClaim:
    authority_class = {
        "policy": MaterialClaimAuthorityClass.POLICY_CLAIM,
        "business_fact": MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM,
        "action_recommendation": MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM,
    }[claim.claim_type]
    dependency_claim_ids = (
        [item.claim_id for item in all_claims if item.claim_type in {"policy", "business_fact"}]
        if claim.claim_type == "action_recommendation"
        else []
    )
    return MaterialClaim(
        claim_id=claim.claim_id,
        claim_text=claim.claim_text,
        authority_class=authority_class,
        source_node=claim.generated_from_step,
        risk_hints=list(claim.risk_hints),
        cited_evidence_ids=list(claim.cited_evidence_ids),
        business_fact_refs=list(claim.business_fact_refs),
        dependency_claim_ids=dependency_claim_ids,
    )


def _claim_result_from_verifier_result(
    *,
    claim: MaterialClaimV1,
    result: MaterialClaimVerificationResult,
    evidence_map: Mapping[str, EvidenceRefV1],
) -> ClaimVerificationResultV1:
    support_status = _support_status(result)
    supporting_refs = [evidence_map[ref_id] for ref_id in result.safe_support_refs if ref_id in evidence_map]
    return ClaimVerificationResultV1(
        claim_id=claim.claim_id,
        claim_type=claim.claim_type,
        support_status=support_status,
        supporting_evidence_refs=supporting_refs,
        business_fact_refs=claim.business_fact_refs,
        rule_checks=_claim_rule_checks(result, support_status),
        semantic_review_status=_semantic_review_status(result.reason_codes),
        allows_user_visible_claim=result.allows_claim,
        allows_action_recommendation=result.allows_action_recommendation,
    )


def _claim_rule_checks(result: MaterialClaimVerificationResult, support_status: str) -> list[dict[str, Any]]:
    if result.rule_checks:
        return [dict(check) for check in result.rule_checks]
    return [
        {
            "rule": "material_claim_verifier",
            "passed": support_status == "supported",
            "reason_codes": result.reason_codes,
        }
    ]


def _support_status(result: MaterialClaimVerificationResult) -> str:
    outcome = _outcome_value(result.outcome)
    if outcome == VerificationOutcome.SUPPORTED.value:
        return "supported"
    if outcome == VerificationOutcome.AMBIGUOUS.value:
        return "ambiguous"
    if outcome == VerificationOutcome.MANUAL_REVIEW.value:
        return "ambiguous"
    if outcome == VerificationOutcome.FAIL_CLOSED.value:
        return "error"
    if outcome == VerificationOutcome.INSUFFICIENT.value:
        return "partial"
    return "unsupported"


def _semantic_review_status(reason_codes: Sequence[str]) -> str:
    codes = set(reason_codes)
    if "semantic_provider_timeout" in codes:
        return "timeout"
    if codes & {"level2_semantic_trigger_hint", "level2_partial_overlap_ambiguous"}:
        return "ambiguous"
    return "not_needed"


def _claim_is_blocked(
    claim: MaterialClaimV1,
    result: MaterialClaimVerificationResult,
    proposed_action: Mapping[str, Any] | None,
) -> bool:
    if _outcome_value(result.outcome) != VerificationOutcome.SUPPORTED.value:
        return True
    if claim.claim_type == "action_recommendation":
        return not result.allows_action_recommendation
    if proposed_action is not None and claim.claim_type in {"policy", "business_fact"}:
        return not result.allows_claim
    return not result.allows_claim


def _needs_manual_review(reason_codes: Sequence[str]) -> bool:
    return any("manual_review" in code or "ambiguous" in code for code in reason_codes)


def _outcome_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _unique_evidence_refs(refs: Sequence[EvidenceRefV1]) -> list[EvidenceRefV1]:
    unique_refs: list[EvidenceRefV1] = []
    seen: set[str] = set()
    for ref in refs:
        if ref.evidence_id not in seen:
            seen.add(ref.evidence_id)
            unique_refs.append(ref)
    return unique_refs


def _unique(values: Sequence[str] | Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


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
