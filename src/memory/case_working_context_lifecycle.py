from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import json
import re
import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.repository import ConversationRepository
from src.db.models import ThreadCaseLink
from src.memory.case_identity import CaseIdentityResult, resolve_case_id
from src.memory.case_working_context import CaseWorkingContextRepository, hydrate_content
from src.memory.case_working_context_service import CaseWorkingContextService
from src.memory.case_working_context_schemas import (
    CaseWorkingContextContentV1,
    CaseWorkingContextNextActionV1,
    CaseWorkingContextObservationV1,
    CaseWorkingContextRecommendationV1,
    CaseWorkingContextVerifiedFactV1,
    CaseWorkingContextWriteCandidate,
)
from src.memory.context_refs import CaseWorkingContextLifecycleStatusV1, CaseWorkingContextRef
from src.memory.fact_promotion import FactPromotionCandidateV1, FactPromotionResultV1, promote_verified_fact
from src.memory.schemas import MemorySourceRefV1
from src.knowledge.evidence_identity import EvidenceIdentityResolutionStatus
from src.knowledge.schemas import EvidenceRefV1
from src.repositories.evidence_version_repo import EvidenceVersionRepository
from src.tools.contracts import BusinessFactRefV1

if TYPE_CHECKING:
    from src.db.models import CaseWorkingContext


CaseResolver = Callable[..., Awaitable[CaseIdentityResult]]
PolicyEvidenceResolver = Callable[..., Awaitable[bool]]

_TERMINAL_PROHIBITED_PII_MARKERS = {"身份证", "手机号", "password", "secret"}
_TERMINAL_SENSITIVE_PII_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)"),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|credential|passwd|pwd)\b\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
)
_DEFAULT_OBSERVED_AT = datetime(1970, 1, 1, tzinfo=UTC)


async def resolve_policy_evidence_ref_exact(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    evidence_ref: EvidenceRefV1,
) -> bool:
    """Resolve one policy ref against the trusted tenant's retained row."""

    try:
        identity = evidence_ref.to_canonical_identity()
        if (
            identity is None
            or evidence_ref.tenant_id != str(tenant_id)
            or identity.scope_type != "tenant_policy"
            or identity.scope_id != str(tenant_id)
        ):
            return False
        resolution = await EvidenceVersionRepository(session).resolve_immutable_evidence(
            evidence_ref,
            expected_tenant_id=tenant_id,
            expected_scope_type="tenant_policy",
            expected_scope_id=str(tenant_id),
        )
    except Exception:
        return False
    return resolution.status is EvidenceIdentityResolutionStatus.CANONICAL and resolution.identity == identity


@dataclass(frozen=True)
class CaseWorkingContextLifecycleResult:
    case_id: uuid.UUID | None
    case_working_context: dict[str, Any] | None
    status_ref: CaseWorkingContextLifecycleStatusV1
    write_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class TerminalProjectionResult:
    candidate: CaseWorkingContextWriteCandidate | None
    status_ref: CaseWorkingContextLifecycleStatusV1


class CaseWorkingContextLifecycleAdapter:
    def __init__(
        self,
        *,
        case_resolver: CaseResolver = resolve_case_id,
        repository_cls: type[Any] = CaseWorkingContextRepository,
        conversation_repository_cls: type[Any] = ConversationRepository,
        case_working_context_service_cls: type[Any] = CaseWorkingContextService,
        policy_evidence_resolver: PolicyEvidenceResolver = resolve_policy_evidence_ref_exact,
    ) -> None:
        self._case_resolver = case_resolver
        self._repository_cls = repository_cls
        self._conversation_repository_cls = conversation_repository_cls
        self._case_working_context_service_cls = case_working_context_service_cls
        self._policy_evidence_resolver = policy_evidence_resolver

    async def resolve_case(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        raw_case_ref: str | None,
    ) -> CaseIdentityResult:
        return await self._case_resolver(session, tenant_id=tenant_id, raw_case_ref=raw_case_ref)

    async def read_active_payload(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        case_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        row = await self._repository_cls(session).read_active(tenant_id=tenant_id, case_id=case_id)
        if row is None:
            return None
        return build_active_cwc_payload(row)

    async def link_and_load_active(
        self,
        *,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID | None,
        state: Mapping[str, Any],
    ) -> CaseWorkingContextLifecycleResult:
        raw_case_ref = trusted_case_ref_from_state(state, include_business_context=False)
        if raw_case_ref is None:
            return CaseWorkingContextLifecycleResult(
                case_id=None,
                case_working_context=None,
                status_ref=skipped_status(
                    reason_code="skipped_no_case",
                    tenant_id=tenant_id,
                    run_id=run_id,
                ),
            )

        case_identity = await self.resolve_case(session, tenant_id=tenant_id, raw_case_ref=raw_case_ref)
        if case_identity.status != "resolved" or case_identity.case_id is None:
            return CaseWorkingContextLifecycleResult(
                case_id=None,
                case_working_context=None,
                status_ref=skipped_status(
                    reason_code="skipped_unresolved_case",
                    resolve_status=case_identity.status,
                    tenant_id=tenant_id,
                    run_id=run_id,
                    raw_case_ref=raw_case_ref,
                ),
            )

        case_id = case_identity.case_id
        link_status = "skipped_missing_run_id"
        if run_id is not None:
            try:
                conversation_repository = self._conversation_repository_cls(session)
                was_already_linked = await _has_active_thread_case_link(
                    session,
                    conversation_repository=conversation_repository,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    thread_id=thread_id,
                    case_id=case_id,
                )
                async with session.begin_nested():
                    await conversation_repository.link_case(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        thread_id=thread_id,
                        case_id=case_id,
                        link_source="run_auto",
                        linked_by_run_id=run_id,
                    )
                link_status = "deduped" if was_already_linked else "linked"
            except Exception:
                return CaseWorkingContextLifecycleResult(
                    case_id=case_id,
                    case_working_context=None,
                    status_ref=error_status(
                        reason_code="link_failed",
                        resolve_status=case_identity.status,
                        link_status="error",
                        read_status="skipped_link_failed",
                        tenant_id=tenant_id,
                        case_id=case_id,
                        run_id=run_id,
                        raw_case_ref=raw_case_ref,
                    ),
                )

        row = await self._repository_cls(session).read_active(tenant_id=tenant_id, case_id=case_id)
        case_working_context = build_active_cwc_payload(row) if row is not None else None
        read_status = "loaded" if case_working_context is not None else "missing"
        return CaseWorkingContextLifecycleResult(
            case_id=case_id,
            case_working_context=case_working_context,
            status_ref=lifecycle_status(
                status="completed",
                resolve_status=case_identity.status,
                link_status=link_status,
                read_status=read_status,
                tenant_id=tenant_id,
                case_id=case_id,
                run_id=run_id,
                raw_case_ref=raw_case_ref,
            ),
        )

    async def write_after_terminal_success(
        self,
        *,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        run_id: uuid.UUID,
        final_state: Mapping[str, Any],
        final_response: str,
    ) -> CaseWorkingContextLifecycleResult:
        raw_case_ref = trusted_case_ref_from_state(final_state, include_business_context=True)
        if raw_case_ref is None:
            return CaseWorkingContextLifecycleResult(
                case_id=None,
                case_working_context=None,
                status_ref=skipped_status(
                    reason_code="skipped_no_case",
                    write_status="skipped",
                    tenant_id=tenant_id,
                    run_id=run_id,
                ),
            )

        case_identity = await self.resolve_case(session, tenant_id=tenant_id, raw_case_ref=raw_case_ref)
        if case_identity.status != "resolved" or case_identity.case_id is None:
            return CaseWorkingContextLifecycleResult(
                case_id=None,
                case_working_context=None,
                status_ref=skipped_status(
                    reason_code="skipped_unresolved_case",
                    resolve_status=case_identity.status,
                    write_status="skipped",
                    tenant_id=tenant_id,
                    run_id=run_id,
                    raw_case_ref=raw_case_ref,
                ),
            )

        case_id = case_identity.case_id
        link_status = await self._link_terminal_thread_case(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            case_id=case_id,
            run_id=run_id,
        )
        if link_status == "error":
            return CaseWorkingContextLifecycleResult(
                case_id=case_id,
                case_working_context=None,
                status_ref=lifecycle_status(
                    status="skipped",
                    resolve_status=case_identity.status,
                    link_status="error",
                    read_status="skipped_link_failed",
                    write_status="skipped",
                    reason_code="link_failed",
                    tenant_id=tenant_id,
                    case_id=case_id,
                    run_id=run_id,
                    raw_case_ref=raw_case_ref,
                ),
            )

        try:
            row = await self._repository_cls(session).read_active(tenant_id=tenant_id, case_id=case_id)
            expected_version = row.version if row is not None else None
            read_status = "loaded" if row is not None else "missing"
        except Exception:
            return CaseWorkingContextLifecycleResult(
                case_id=case_id,
                case_working_context=None,
                status_ref=lifecycle_status(
                    status="error",
                    resolve_status=case_identity.status,
                    link_status=link_status,
                    read_status="error",
                    write_status="error",
                    reason_code="active_cwc_read_failed",
                    tenant_id=tenant_id,
                    case_id=case_id,
                    run_id=run_id,
                    raw_case_ref=raw_case_ref,
                ),
            )

        validated_policy_evidence_ids = await _validated_policy_evidence_ids(
            final_state,
            session=session,
            tenant_id=tenant_id,
            resolver=self._policy_evidence_resolver,
        )
        projection = project_terminal_write_candidate(
            state=final_state,
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            expected_version=expected_version,
            final_response=final_response,
            _validated_policy_evidence_ids=validated_policy_evidence_ids,
        )
        if projection.candidate is None:
            return CaseWorkingContextLifecycleResult(
                case_id=case_id,
                case_working_context=None,
                status_ref=_terminal_status_with_context(
                    projection.status_ref,
                    resolve_status=case_identity.status,
                    link_status=link_status,
                    read_status=read_status,
                    tenant_id=tenant_id,
                    case_id=case_id,
                    run_id=run_id,
                    raw_case_ref=raw_case_ref,
                ),
            )

        try:
            service_result = await self._case_working_context_service_cls().write_case_working_context(
                session,
                projection.candidate,
                run_id=run_id,
            )
        except Exception:
            return CaseWorkingContextLifecycleResult(
                case_id=case_id,
                case_working_context=None,
                status_ref=lifecycle_status(
                    status="error",
                    resolve_status=case_identity.status,
                    link_status=link_status,
                    read_status=read_status,
                    write_status="error",
                    reason_code="case_working_context_write_failed",
                    tenant_id=tenant_id,
                    case_id=case_id,
                    run_id=run_id,
                    raw_case_ref=raw_case_ref,
                ),
            )

        write_status = str(service_result.status)
        write_result = _service_write_result_dict(service_result)
        return CaseWorkingContextLifecycleResult(
            case_id=case_id,
            case_working_context=None,
            write_result=write_result,
            status_ref=lifecycle_status(
                status="completed" if write_status == "written" else "skipped",
                resolve_status=case_identity.status,
                link_status=link_status,
                read_status=read_status,
                write_status=write_status,
                reason_code=str(service_result.reason_code),
                tenant_id=tenant_id,
                case_id=case_id,
                run_id=run_id,
                raw_case_ref=raw_case_ref,
            ),
        )

    async def _link_terminal_thread_case(
        self,
        *,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        case_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> str:
        try:
            conversation_repository = self._conversation_repository_cls(session)
            was_already_linked = await _has_active_thread_case_link(
                session,
                conversation_repository=conversation_repository,
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                case_id=case_id,
            )
            if was_already_linked:
                return "deduped"
            if hasattr(session, "begin_nested"):
                async with session.begin_nested():
                    await conversation_repository.link_case(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        thread_id=thread_id,
                        case_id=case_id,
                        link_source="run_auto",
                        linked_by_run_id=run_id,
                    )
            else:
                await conversation_repository.link_case(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    thread_id=thread_id,
                    case_id=case_id,
                    link_source="run_auto",
                    linked_by_run_id=run_id,
                )
            return "linked"
        except Exception:
            return "error"

    @staticmethod
    def trusted_case_ref_from_state(
        state: Mapping[str, Any],
        *,
        include_business_context: bool = False,
    ) -> str | None:
        return trusted_case_ref_from_state(state, include_business_context=include_business_context)

    @staticmethod
    def build_active_cwc_payload(row: CaseWorkingContext) -> dict[str, Any]:
        return build_active_cwc_payload(row)

    @staticmethod
    def skipped_status(reason_code: str, **overrides: Any) -> CaseWorkingContextLifecycleStatusV1:
        return skipped_status(reason_code=reason_code, **overrides)


def project_terminal_write_candidate(
    *,
    state: Mapping[str, Any],
    tenant_id: uuid.UUID,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    expected_version: int | None,
    final_response: str,
    _validated_policy_evidence_ids: frozenset[str] | None = None,
) -> TerminalProjectionResult:
    try:
        return _project_terminal_write_candidate(
            state=state,
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            expected_version=expected_version,
            final_response=final_response,
            validated_policy_evidence_ids=_validated_policy_evidence_ids or frozenset(),
        )
    except Exception:
        return TerminalProjectionResult(
            candidate=None,
            status_ref=lifecycle_status(
                status="error",
                write_status="error",
                reason_code="projection_failed",
                tenant_id=tenant_id,
                case_id=case_id,
                run_id=run_id,
            ),
        )


def _project_terminal_write_candidate(
    *,
    state: Mapping[str, Any],
    tenant_id: uuid.UUID,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    expected_version: int | None,
    final_response: str,
    validated_policy_evidence_ids: frozenset[str],
) -> TerminalProjectionResult:
    if _is_clarification_only_state(state):
        return TerminalProjectionResult(
            candidate=None,
            status_ref=lifecycle_status(
                status="skipped",
                write_status="skipped",
                reason_code="clarification_only",
                tenant_id=tenant_id,
                case_id=case_id,
                run_id=run_id,
            ),
        )

    source_ref = _terminal_source_ref(run_id=run_id, case_id=case_id)
    recommendations, next_action = _project_recommendations_and_next_action(state)
    verified_facts, observations, policy_refs = _project_promoted_content(
        state,
        tenant_id=tenant_id,
        source_ref=source_ref,
        validated_policy_evidence_ids=validated_policy_evidence_ids,
    )
    content = CaseWorkingContextContentV1(
        customer_request=_truncate(_non_empty_str(state.get("user_query")), 500),
        issue_type=_project_issue_type(state),
        verified_facts=verified_facts,
        evidence_refs=observations,
        policy_refs=policy_refs,
        agent_recommendations=recommendations,
        next_action=next_action,
    )
    if not _has_projectable_content(content):
        return TerminalProjectionResult(
            candidate=None,
            status_ref=lifecycle_status(
                status="skipped",
                write_status="skipped",
                reason_code="skipped_no_projectable_content",
                tenant_id=tenant_id,
                case_id=case_id,
                run_id=run_id,
            ),
        )

    candidate = CaseWorkingContextWriteCandidate(
        tenant_id=tenant_id,
        case_id=case_id,
        updated_by_run_id=run_id,
        source_ref=source_ref,
        expected_version=expected_version,
        content=content,
        pii_classification=_classify_terminal_projection_pii(content, final_response=final_response),
    )
    return TerminalProjectionResult(
        candidate=candidate,
        status_ref=lifecycle_status(
            status="eligible",
            write_status="candidate_projected",
            reason_code="eligible",
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
        ),
    )


def _terminal_source_ref(*, run_id: uuid.UUID, case_id: uuid.UUID) -> MemorySourceRefV1:
    return MemorySourceRefV1(
        source_type="run_auto_terminal",
        run_id=str(run_id),
        agent_run_id=str(run_id),
        business_object_type="refund_case",
        business_object_id=str(case_id),
    )


def _is_clarification_only_state(state: Mapping[str, Any]) -> bool:
    if state.get("clarification_request") is None:
        return False
    return not any(
        (
            _non_empty_mapping(state.get("business_context")),
            list(_iter_mappings(state.get("tool_results"))),
            _non_empty_mapping(state.get("recommendation_draft")),
            _non_empty_mapping(state.get("proposed_action")),
        )
    )


def _project_issue_type(state: Mapping[str, Any]) -> str | None:
    active_slots_issue_type = _mapping_value(state.get("active_slots"), "issue_type")
    issue_type = _non_empty_str(active_slots_issue_type)
    if issue_type is None:
        issue_type = _non_empty_str(state.get("primary_intent"))
    return _truncate(issue_type, 64)


async def _validated_policy_evidence_ids(
    state: Mapping[str, Any],
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    resolver: PolicyEvidenceResolver,
) -> frozenset[str]:
    """Return only complete per-result ref sets proven by the exact resolver."""

    validated: set[str] = set()
    for item in _iter_mappings(state.get("tool_results")):
        refs, refs_invalid, compatibility_only = _parse_policy_refs(item.get("policy_evidence_refs"))
        if refs_invalid or compatibility_only or not refs:
            continue
        item_is_valid = True
        for ref in refs:
            try:
                if not await resolver(
                    session,
                    tenant_id=tenant_id,
                    evidence_ref=ref,
                ):
                    item_is_valid = False
                    break
            except Exception:
                item_is_valid = False
                break
        if item_is_valid:
            validated.update(ref.evidence_id for ref in refs)
    return frozenset(validated)


def _project_promoted_content(
    state: Mapping[str, Any],
    *,
    tenant_id: uuid.UUID,
    source_ref: MemorySourceRefV1,
    validated_policy_evidence_ids: frozenset[str],
) -> tuple[
    list[CaseWorkingContextVerifiedFactV1],
    list[CaseWorkingContextObservationV1],
    list[EvidenceRefV1],
]:
    facts: list[CaseWorkingContextVerifiedFactV1] = []
    observations: list[CaseWorkingContextObservationV1] = []
    policy_refs: list[EvidenceRefV1] = []
    seen_facts: set[str] = set()
    seen_policy_refs: set[str] = set()
    for item in _iter_mappings(state.get("tool_results")):
        candidate = _promotion_candidate_from_item(
            item,
            tenant_id=tenant_id,
            validated_policy_evidence_ids=validated_policy_evidence_ids,
        )
        if candidate is None:
            continue
        fact_source_ref = _source_ref_with_tool_result(source_ref, item)
        result = promote_verified_fact(candidate)
        if result.decision == "promote":
            key = _promotion_source_key(result)
            if key in seen_facts:
                continue
            seen_facts.add(key)
            facts.append(result.to_verified_fact(source_ref=fact_source_ref))
            for ref in result.policy_evidence_refs:
                ref_key = _canonical_policy_source_key(ref)
                if ref_key in seen_policy_refs:
                    continue
                seen_policy_refs.add(ref_key)
                policy_refs.append(ref)
            continue
        observations.append(
            CaseWorkingContextObservationV1(
                summary=result.summary,
                decision=result.decision,
                authority_class=result.authority_class,
                status=result.status,
                reason_code=result.reason_code,
                internal_reason_code=result.internal_reason_code,
                completeness=result.completeness,
                scope_result=result.scope_result,
                freshness_result=result.freshness_result,
                reference_validation=result.reference_validation,
                source_ref=fact_source_ref,
                observed_at=result.observed_at,
                business_fact_refs=result.business_fact_refs,
                policy_evidence_refs=result.policy_evidence_refs,
            )
        )
    return facts, observations, policy_refs


def _promotion_candidate_from_item(
    item: Mapping[str, Any],
    *,
    tenant_id: uuid.UUID,
    validated_policy_evidence_ids: frozenset[str],
) -> FactPromotionCandidateV1 | None:
    summary = _first_non_empty_str(item, ("summary", "prompt_summary", "tool_summary"))
    if summary is None:
        return None
    observed_at = _item_observed_at(item)
    business_refs, business_invalid = _parse_business_refs(item.get("business_fact_refs"))
    policy_refs, policy_invalid, compatibility_only = _parse_policy_refs(item.get("policy_evidence_refs"))
    authority_class = _promotion_authority(item, business_refs=business_refs, policy_refs=policy_refs)
    status = _promotion_status(item.get("status"))
    completeness = _promotion_completeness(
        item.get("completeness"),
        status=status,
        has_refs=bool(business_refs or policy_refs),
    )
    scope_result, scope_internal_reason = _promotion_scope(
        item,
        tenant_id=tenant_id,
        authority_class=authority_class,
        business_refs=business_refs,
        policy_refs=policy_refs,
        refs_invalid=business_invalid or policy_invalid,
    )
    reference_validation = _promotion_ref_validation(
        item.get("reference_validation"),
        refs_invalid=business_invalid or policy_invalid,
        compatibility_only=compatibility_only,
    )
    if (
        authority_class == "policy_evidence"
        and policy_refs
        and reference_validation == "valid"
        and any(ref.evidence_id not in validated_policy_evidence_ids for ref in policy_refs)
    ):
        reference_validation = "invalid"
    freshness_result = _promotion_freshness(
        item.get("freshness_result"),
        observed_at=observed_at,
        business_refs=business_refs,
        policy_refs=policy_refs,
    )
    return FactPromotionCandidateV1(
        tenant_id=str(tenant_id),
        summary=_truncate(summary, 500) or summary,
        authority_class=authority_class,
        status=status,
        completeness=completeness,
        scope_result=scope_result,
        freshness_result=freshness_result,
        reference_validation=reference_validation,
        observed_at=observed_at,
        business_fact_refs=business_refs,
        policy_evidence_refs=policy_refs,
        scope_internal_reason=scope_internal_reason,
    )


def _source_ref_with_tool_result(
    source_ref: MemorySourceRefV1,
    item: Mapping[str, Any],
) -> MemorySourceRefV1:
    tool_result_id = _first_non_empty_str(item, ("tool_result_id", "tool_call_id", "id"))
    if tool_result_id is None:
        return source_ref
    payload = source_ref.model_dump(mode="json", exclude_none=True)
    payload["tool_result_id"] = tool_result_id
    return MemorySourceRefV1.model_validate(payload)


def _parse_business_refs(value: Any) -> tuple[list[BusinessFactRefV1], bool]:
    refs: list[BusinessFactRefV1] = []
    members, invalid = _raw_ref_members(value)
    for item in members:
        try:
            refs.append(BusinessFactRefV1.model_validate(item))
        except ValidationError:
            invalid = True
    return refs, invalid


def _parse_policy_refs(value: Any) -> tuple[list[EvidenceRefV1], bool, bool]:
    refs: list[EvidenceRefV1] = []
    members, invalid = _raw_ref_members(value)
    compatibility_only = False
    for item in members:
        try:
            ref = EvidenceRefV1.model_validate(item)
        except ValidationError:
            invalid = True
            continue
        refs.append(ref)
        if ref.to_canonical_identity() is None:
            compatibility_only = True
    return refs, invalid, compatibility_only


def _promotion_authority(
    item: Mapping[str, Any],
    *,
    business_refs: list[BusinessFactRefV1],
    policy_refs: list[EvidenceRefV1],
) -> str:
    explicit = item.get("authority_class")
    if explicit in {"business_fact", "policy_evidence", "contextual_only", "unknown"}:
        return str(explicit)
    if business_refs and not policy_refs:
        return "business_fact"
    if policy_refs and not business_refs:
        return "policy_evidence"
    tool_name = _non_empty_str(item.get("tool_name"))
    if tool_name == "search_case_memory":
        return "contextual_only"
    if tool_name in {"search_policy", "search_sop"}:
        return "policy_evidence"
    if tool_name in {
        "get_order",
        "get_refund_case",
        "get_ticket",
        "get_logistics",
        "get_merchant_risk",
        "business_metric_query",
        "query_business_metric",
        "query_business",
    }:
        return "business_fact"
    return "unknown"


def _promotion_status(value: Any) -> str:
    status = _non_empty_str(value) or "malformed"
    aliases = {
        "permission_denied": "denied",
        "unauthorized": "denied",
        "strong_evidence": "success",
        "verified": "success",
        "partial_evidence": "partial",
        "no_evidence": "not_found",
        "invalid_hash": "invalid_response",
        "invalid_scope": "invalid_response",
        "build_error": "error",
    }
    normalized = aliases.get(status, status)
    allowed = {
        "success",
        "denied",
        "unavailable",
        "stale",
        "malformed",
        "partial",
        "partial_success",
        "timeout",
        "error",
        "invalid_request",
        "invalid_response",
        "not_found",
        "legacy_unresolved",
        "conflict",
    }
    return normalized if normalized in allowed else "malformed"


def _promotion_completeness(value: Any, *, status: str, has_refs: bool) -> str:
    if value in {"complete", "partial", "unknown"}:
        return str(value)
    if status in {"partial", "partial_success"}:
        return "partial"
    if status == "success" and has_refs:
        return "complete"
    return "unknown"


def _promotion_scope(
    item: Mapping[str, Any],
    *,
    tenant_id: uuid.UUID,
    authority_class: str,
    business_refs: list[BusinessFactRefV1],
    policy_refs: list[EvidenceRefV1],
    refs_invalid: bool,
) -> tuple[str, str | None]:
    tenant = str(tenant_id)
    raw_policy_refs = _iter_mappings(item.get("policy_evidence_refs"))
    if authority_class == "business_fact" and business_refs:
        if any(ref.tenant_id != tenant for ref in business_refs):
            return "invalid", "tenant_mismatch"
        return "valid", None
    if authority_class == "policy_evidence" and raw_policy_refs:
        for raw in raw_policy_refs:
            if _non_empty_str(raw.get("tenant_id")) != tenant:
                return "invalid", "tenant_mismatch"
            if raw.get("scope_type") != "tenant_policy":
                return "invalid", "unsupported_scope"
            if _non_empty_str(raw.get("scope_id")) != tenant:
                return "invalid", "scope_mismatch"
        if refs_invalid:
            return "invalid", "scope_mismatch"
        if any(ref.to_canonical_identity() is None for ref in policy_refs):
            return "unknown", None
        return "valid", None
    explicit = item.get("scope_result")
    if explicit in {"valid", "invalid", "unknown"}:
        return str(explicit), "scope_mismatch" if explicit == "invalid" else None
    return "unknown", None


def _promotion_ref_validation(value: Any, *, refs_invalid: bool, compatibility_only: bool) -> str:
    if compatibility_only or value == "compatibility_only":
        return "compatibility_only"
    if refs_invalid:
        return "invalid"
    if value in {"valid", "invalid", "unknown"}:
        return str(value)
    return "valid"


def _promotion_freshness(
    value: Any,
    *,
    observed_at: datetime,
    business_refs: list[BusinessFactRefV1],
    policy_refs: list[EvidenceRefV1],
) -> str:
    if value in {"stale", "invalid", "unknown"}:
        return str(value)
    if business_refs:
        if any(ref.data_freshness_at is None for ref in business_refs):
            return "unknown"
        if any(
            ref.data_freshness_at > observed_at or ref.retrieved_at > observed_at
            for ref in business_refs
            if ref.data_freshness_at is not None
        ):
            return "invalid"
        return "valid"
    if policy_refs:
        for ref in policy_refs:
            retrieved_at = _coerce_datetime(ref.retrieved_at)
            if retrieved_at == _DEFAULT_OBSERVED_AT or retrieved_at > observed_at:
                return "invalid"
        return "valid"
    return "valid" if value == "valid" else "unknown"


def _item_observed_at(item: Mapping[str, Any]) -> datetime:
    explicit = item.get("observed_at") or item.get("created_at") or item.get("completed_at") or item.get("updated_at")
    if explicit is not None:
        return _coerce_datetime(explicit)
    reference_times: list[datetime] = []
    for ref in _iter_mappings(item.get("business_fact_refs")):
        reference_times.append(_coerce_datetime(ref.get("retrieved_at")))
    for ref in _iter_mappings(item.get("policy_evidence_refs")):
        reference_times.append(_coerce_datetime(ref.get("retrieved_at")))
    valid_times = [value for value in reference_times if value != _DEFAULT_OBSERVED_AT]
    return max(valid_times, default=_DEFAULT_OBSERVED_AT)


def _promotion_source_key(result: FactPromotionResultV1) -> str:
    if result.authority_class == "business_fact":
        sources = [ref.model_dump(mode="json") for ref in result.business_fact_refs]
    else:
        sources = [ref.to_canonical_identity().model_dump(mode="json") for ref in result.policy_evidence_refs]
    sources.sort(key=lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return f"{result.authority_class}:{json.dumps(sources, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"


def _canonical_policy_source_key(ref: EvidenceRefV1) -> str:
    identity = ref.to_canonical_identity()
    if identity is None:  # pragma: no cover - only promoted canonical refs reach this helper
        raise ValueError("promoted policy refs require canonical identity")
    return identity.model_dump_json()


def _project_recommendations_and_next_action(
    state: Mapping[str, Any],
) -> tuple[list[CaseWorkingContextRecommendationV1], CaseWorkingContextNextActionV1]:
    recommendation_draft = state.get("recommendation_draft")
    proposed_action = state.get("proposed_action")
    recommendation_text: str | None = None
    next_step: str | None = None

    if isinstance(recommendation_draft, Mapping):
        recommendation_text = _first_non_empty_str(recommendation_draft, ("recommended_action", "recommendation"))
        next_step = recommendation_text
    if isinstance(proposed_action, Mapping):
        proposed_step = _non_empty_str(proposed_action.get("action_type"))
        if recommendation_text is None:
            recommendation_text = proposed_step
        if next_step is None:
            next_step = proposed_step

    recommendations = (
        [CaseWorkingContextRecommendationV1(recommended_step=recommendation_text)]
        if recommendation_text is not None
        else []
    )
    return recommendations, CaseWorkingContextNextActionV1(recommended_step=next_step)


def _has_projectable_content(content: CaseWorkingContextContentV1) -> bool:
    return any(
        (
            content.customer_request,
            content.issue_type,
            content.verified_facts,
            content.policy_refs,
            content.agent_recommendations,
            content.next_action.recommended_step,
            content.next_action.blocked_by,
        )
    )


def _classify_terminal_projection_pii(
    content: CaseWorkingContextContentV1,
    *,
    final_response: str,
) -> str:
    values = _collect_strings(content.model_dump(mode="json"))
    values.append(final_response)
    text = " ".join(values).lower()
    if any(marker.lower() in text for marker in _TERMINAL_PROHIBITED_PII_MARKERS):
        return "prohibited"
    if any(pattern.search(text) for pattern in _TERMINAL_SENSITIVE_PII_PATTERNS):
        return "sensitive"
    return "none"


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        strings: list[str] = []
        for nested in value.values():
            strings.extend(_collect_strings(nested))
        return strings
    if isinstance(value, list | tuple):
        strings = []
        for item in value:
            strings.extend(_collect_strings(item))
        return strings
    return []


def _iter_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _raw_ref_members(value: Any) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    if isinstance(value, Mapping):
        return (value,), False
    if not isinstance(value, list | tuple):
        return (), value is not None
    members = tuple(value)
    return tuple(item for item in members if isinstance(item, Mapping)), any(
        not isinstance(item, Mapping) for item in members
    )


def _non_empty_mapping(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value)


def _first_non_empty_str(container: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _non_empty_str(container.get(key))
        if value is not None:
            return value
    return None


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return _DEFAULT_OBSERVED_AT
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return _DEFAULT_OBSERVED_AT


def trusted_case_ref_from_state(
    state: Mapping[str, Any],
    *,
    include_business_context: bool = False,
) -> str | None:
    active_slots_ref = _mapping_value(state.get("active_slots"), "refund_case_id")
    if active_slots_ref is not None:
        return active_slots_ref

    extracted_slots_ref = _mapping_value(state.get("extracted_slots"), "refund_case_id")
    if extracted_slots_ref is not None:
        return extracted_slots_ref

    if not include_business_context:
        return None

    refund_case = _mapping_value(state.get("business_context"), "refund_case")
    if not isinstance(refund_case, Mapping):
        return None

    for key in ("refund_case_no", "refund_case_id", "id"):
        value = _non_empty_str(refund_case.get(key))
        if value is not None:
            return value
    return None


async def _has_active_thread_case_link(
    session: AsyncSession,
    *,
    conversation_repository: ConversationRepository,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    thread_id: str,
    case_id: uuid.UUID,
    link_source: str | None = None,
    linked_by_run_id: uuid.UUID | None = None,
) -> bool:
    thread = await conversation_repository.get_thread(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
    )
    if thread is None:
        return False
    stmt = select(ThreadCaseLink.id).where(
        ThreadCaseLink.tenant_id == tenant_id,
        ThreadCaseLink.conversation_thread_id == thread.id,
        ThreadCaseLink.case_id == case_id,
        ThreadCaseLink.deleted_at.is_(None),
    )
    if link_source is not None:
        stmt = stmt.where(ThreadCaseLink.link_source == link_source)
    if linked_by_run_id is not None:
        stmt = stmt.where(ThreadCaseLink.linked_by_run_id == linked_by_run_id)
    result = await session.execute(stmt.limit(1))
    return result.scalar_one_or_none() is not None


def build_active_cwc_payload(row: CaseWorkingContext) -> dict[str, Any]:
    content = hydrate_content(row).model_dump(mode="json")
    for observation in content.get("evidence_refs", []):
        if isinstance(observation, dict):
            observation.pop("internal_reason_code", None)
    ref = CaseWorkingContextRef(
        tenant_id=str(row.tenant_id),
        case_id=str(row.case_id),
        memory_id=str(row.id),
        version=row.version,
        source_ref=dict(row.source_ref_json or {}),
        updated_by_run_id=str(row.updated_by_run_id) if row.updated_by_run_id is not None else None,
    )
    return {
        "content": content,
        "ref": ref.model_dump(mode="json"),
    }


def skipped_status(reason_code: str, **overrides: Any) -> CaseWorkingContextLifecycleStatusV1:
    return lifecycle_status(status="skipped", reason_code=reason_code, **overrides)


def error_status(reason_code: str, **overrides: Any) -> CaseWorkingContextLifecycleStatusV1:
    return lifecycle_status(status="error", reason_code=reason_code, **overrides)


def _terminal_status_with_context(
    status_ref: CaseWorkingContextLifecycleStatusV1,
    *,
    resolve_status: str,
    link_status: str,
    read_status: str,
    tenant_id: uuid.UUID,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    raw_case_ref: str,
) -> CaseWorkingContextLifecycleStatusV1:
    return lifecycle_status(
        status=status_ref.status,
        resolve_status=resolve_status,
        link_status=link_status,
        read_status=read_status,
        write_status=status_ref.write_status,
        reason_code=status_ref.reason_code,
        filter_reasons=status_ref.filter_reasons,
        tenant_id=tenant_id,
        case_id=case_id,
        run_id=run_id,
        raw_case_ref=raw_case_ref,
    )


def _service_write_result_dict(service_result: Any) -> dict[str, Any]:
    memory_id = getattr(service_result, "memory_id", None)
    event_id = getattr(service_result, "event_id", None)
    return {
        "status": str(getattr(service_result, "status", "")),
        "reason_code": str(getattr(service_result, "reason_code", "")),
        "memory_id": str(memory_id) if memory_id is not None else None,
        "version": getattr(service_result, "version", None),
        "event_id": str(event_id) if event_id is not None else None,
    }


def lifecycle_status(
    *,
    status: str,
    resolve_status: str | None = None,
    link_status: str | None = None,
    read_status: str | None = None,
    write_status: str | None = None,
    reason_code: str | None = None,
    filter_reasons: list[str] | None = None,
    tenant_id: uuid.UUID | str | None = None,
    case_id: uuid.UUID | str | None = None,
    run_id: uuid.UUID | str | None = None,
    raw_case_ref: str | None = None,
) -> CaseWorkingContextLifecycleStatusV1:
    return CaseWorkingContextLifecycleStatusV1(
        status=status,
        resolve_status=resolve_status,
        link_status=link_status,
        read_status=read_status,
        write_status=write_status,
        reason_code=reason_code,
        filter_reasons=list(filter_reasons or []),
        tenant_id=str(tenant_id) if tenant_id is not None else None,
        case_id=str(case_id) if case_id is not None else None,
        run_id=str(run_id) if run_id is not None else None,
        raw_case_ref=raw_case_ref,
    )


def _mapping_value(container: Any, key: str) -> Any:
    if not isinstance(container, Mapping):
        return None
    return container.get(key)


def _non_empty_str(value: Any) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
