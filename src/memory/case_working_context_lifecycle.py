from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import re
import uuid

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
    CaseWorkingContextPolicyRefV1,
    CaseWorkingContextRecommendationV1,
    CaseWorkingContextVerifiedFactV1,
    CaseWorkingContextWriteCandidate,
)
from src.memory.context_refs import CaseWorkingContextLifecycleStatusV1, CaseWorkingContextRef
from src.memory.schemas import MemorySourceRefV1

if TYPE_CHECKING:
    from src.db.models import CaseWorkingContext


CaseResolver = Callable[..., Awaitable[CaseIdentityResult]]

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
    ) -> None:
        self._case_resolver = case_resolver
        self._repository_cls = repository_cls
        self._conversation_repository_cls = conversation_repository_cls
        self._case_working_context_service_cls = case_working_context_service_cls

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

        projection = project_terminal_write_candidate(
            state=final_state,
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            expected_version=expected_version,
            final_response=final_response,
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
) -> TerminalProjectionResult:
    try:
        return _project_terminal_write_candidate(
            state=state,
            tenant_id=tenant_id,
            case_id=case_id,
            run_id=run_id,
            expected_version=expected_version,
            final_response=final_response,
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
    content = CaseWorkingContextContentV1(
        customer_request=_truncate(_non_empty_str(state.get("user_query")), 500),
        issue_type=_project_issue_type(state),
        verified_facts=_project_verified_facts(state, source_ref=source_ref),
        policy_refs=_project_policy_refs(state),
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


def _project_verified_facts(
    state: Mapping[str, Any],
    *,
    source_ref: MemorySourceRefV1,
) -> list[CaseWorkingContextVerifiedFactV1]:
    facts: list[CaseWorkingContextVerifiedFactV1] = []
    seen: set[str] = set()
    for item in _iter_mappings(state.get("tool_results")):
        text = _first_non_empty_str(item, ("summary", "prompt_summary", "tool_summary"))
        if text is None or text in seen:
            continue
        seen.add(text)
        fact_source_ref = _source_ref_with_tool_result(source_ref, item)
        facts.append(
            CaseWorkingContextVerifiedFactV1(
                text=text,
                source_ref=fact_source_ref,
                observed_at=_coerce_datetime(
                    item.get("observed_at")
                    or item.get("created_at")
                    or item.get("completed_at")
                    or item.get("updated_at")
                ),
            )
        )
    return facts


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


def _project_policy_refs(state: Mapping[str, Any]) -> list[CaseWorkingContextPolicyRefV1]:
    refs: list[CaseWorkingContextPolicyRefV1] = []
    seen: set[tuple[str, str, str]] = set()
    for item in _iter_potential_policy_ref_mappings(state):
        doc_id = _first_non_empty_str(item, ("doc_key", "doc_id"))
        chunk_id = _non_empty_str(item.get("chunk_id"))
        version = _first_non_empty_str(item, ("policy_version", "version"))
        if doc_id is None or chunk_id is None or version is None:
            continue
        key = (doc_id, chunk_id, version)
        if key in seen:
            continue
        seen.add(key)
        refs.append(CaseWorkingContextPolicyRefV1(doc_id=doc_id, chunk_id=chunk_id, version=version))
    return refs


def _iter_potential_policy_ref_mappings(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    roots = (
        state.get("rag_context_bundle"),
        state.get("claim_verification_bundle"),
        state.get("policy_refs"),
    )
    items: list[Mapping[str, Any]] = []
    for root in roots:
        items.extend(_collect_policy_ref_mappings(root))
    return items


def _collect_policy_ref_mappings(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        collected: list[Mapping[str, Any]] = []
        if ("doc_key" in value or "doc_id" in value) and "chunk_id" in value:
            collected.append(value)
        for nested in value.values():
            collected.extend(_collect_policy_ref_mappings(nested))
        return collected
    if isinstance(value, list | tuple):
        collected = []
        for item in value:
            collected.extend(_collect_policy_ref_mappings(item))
        return collected
    return []


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
