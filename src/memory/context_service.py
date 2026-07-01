from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from src.memory.case_memory import CaseMemoryService
from src.memory.context_refs import (
    MemoryContextBundle,
    MemoryWriteDecisionV2,
    ReviewedMemoryContextBundle,
    ReviewedMemoryRef,
    ReviewedMemoryContextRetrieveStatusV1,
    SessionContextLoadStatusV1,
    SessionContextRef,
)
from src.memory.long_term import LongTermMemoryService
from src.memory.schemas import CaseMemorySearchRequest, SessionContextMemory, SessionMemoryView
from src.memory.session_bundle import SessionMemoryBundleService
from src.platform.trusted_context import MerchantScopeV1, TrustedContext, merchant_scope_allows

_UNSUPPORTED_SCOPE_TYPES = {"tenant", "global"}
_LONG_TERM_ITEM_KEYS = (
    "memory_id",
    "tenant_id",
    "scope_type",
    "scope_id",
    "memory_kind",
    "semantic_kind",
    "content",
    "source_type",
    "source_ref",
    "review_status",
    "version",
    "valid_from",
    "expires_at",
)
_CASE_ITEM_KEYS = (
    "case_memory_id",
    "excerpt",
    "applicability",
    "outcome",
    "caveats",
    "score",
    "source_refs",
    "policy_refs",
)


class MemoryContextService:
    def __init__(
        self,
        *,
        session_bundle_service: SessionMemoryBundleService | None = None,
        long_term_memory_service: LongTermMemoryService | None = None,
        case_memory_service: CaseMemoryService | None = None,
    ) -> None:
        self.session_bundle_service = session_bundle_service
        self.long_term_memory_service = long_term_memory_service
        self.case_memory_service = case_memory_service

    async def load_session_context_for_intent(
        self,
        *,
        tenant_id: Any,
        user_id: Any,
        thread_id: str,
        run_id: Any,
        current_intent: str | None = None,
        max_recent_messages: int = 8,
    ) -> tuple[SessionContextMemory, SessionContextLoadStatusV1]:
        if self.session_bundle_service is None:
            context = _empty_session_context_memory(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                fallback_reason="missing_session_bundle_service",
            )
            return context, _session_context_status(
                context,
                status="skipped",
                source="memory_context_service",
                fallback_reason="missing_session_bundle_service",
            )

        try:
            bundle = await self.session_bundle_service.load_session_memory_bundle(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                current_intent=current_intent,
                max_recent_messages=max_recent_messages,
            )
        except Exception:
            context = _empty_session_context_memory(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                fallback_reason="session_bundle_unavailable",
            )
            return context, _session_context_status(
                context,
                status="unavailable",
                source="session_memory_bundle_service",
                fallback_reason="session_bundle_unavailable",
            )

        context = SessionContextMemory.model_validate(bundle)
        fallback_reason = ",".join(f"{key}:{value}" for key, value in sorted(bundle.fallback_reasons.items())) or None
        return context, _session_context_status(
            context,
            status="loaded",
            source="session_memory_bundle_service",
            fallback_reason=fallback_reason,
        )

    async def load_reviewed_memory_context(
        self,
        *,
        trusted_context: Any | None = None,
        current_slots: Mapping[str, Any] | None = None,
        trusted_business_context: Mapping[str, Any] | None = None,
        requested_scopes: list[dict[str, Any]] | None = None,
        query: str | None = None,
        case_type: str | None = None,
        now: datetime | None = None,
        limit: int = 5,
        **_: Any,
    ) -> ReviewedMemoryContextBundle:
        trusted = _parse_trusted_context(trusted_context)
        if trusted is None:
            return _empty_reviewed_memory_context(
                trusted_context=trusted_context,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
                fallback_reason="missing_trusted_context",
                filter_reasons=["missing_trusted_context"],
            )

        if not trusted.merchant_scope.merchant_ids:
            return _empty_reviewed_memory_context(
                trusted_context=trusted,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
                fallback_reason="missing_actor_merchant_scope",
                filter_reasons=["missing_actor_merchant_scope"],
            )

        if _requests_tenant_or_global_memory(requested_scopes):
            return _empty_reviewed_memory_context(
                trusted_context=trusted,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
                fallback_reason="tenant_global_memory_unsupported",
                filter_reasons=["tenant_global_memory_unsupported"],
                effective_scopes=_identity_effective_scopes(trusted),
            )

        scope_decision = _reviewed_memory_scopes(
            trusted,
            current_slots=current_slots,
            trusted_business_context=trusted_business_context,
        )
        if scope_decision.fallback_reason is not None:
            return _empty_reviewed_memory_context(
                trusted_context=trusted,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
                fallback_reason=scope_decision.fallback_reason,
                filter_reasons=scope_decision.filter_reasons,
                effective_scopes=scope_decision.effective_scopes,
            )

        if self.long_term_memory_service is None or self.case_memory_service is None:
            return _empty_reviewed_memory_context(
                trusted_context=trusted,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
                fallback_reason="missing_memory_context_services",
                filter_reasons=["missing_memory_context_services"],
                effective_scopes=scope_decision.effective_scopes,
                status="unavailable",
            )

        tenant_id = _uuid_or_value(trusted.tenant_id)
        service_scopes = scope_decision.retrieval_scopes
        long_term_raw = await self.long_term_memory_service.retrieve_profile_memory(
            tenant_id=tenant_id,
            scopes=service_scopes,
            now=now,
            limit=limit,
        )
        case_raw: list[Any] = []
        if query:
            case_result = await self.case_memory_service.retrieve_reviewed(
                CaseMemorySearchRequest(
                    tenant_id=tenant_id,
                    scopes=service_scopes,
                    case_type=case_type,
                    query=query,
                    now=now,
                    limit=limit,
                )
            )
            case_raw = list(getattr(case_result, "items", []))

        long_term_items, long_term_refs = _reviewed_long_term_items(
            long_term_raw,
            tenant_id=str(trusted.tenant_id),
            fallback_scope=scope_decision.primary_retrieval_scope,
        )
        case_items, case_refs = _reviewed_case_items(
            case_raw,
            tenant_id=str(trusted.tenant_id),
            fallback_scope=scope_decision.primary_retrieval_scope,
        )
        retrieved_refs = long_term_refs + case_refs
        status_ref = ReviewedMemoryContextRetrieveStatusV1(
            status="loaded" if retrieved_refs else "skipped",
            trusted_scope_inputs=_trusted_scope_inputs(
                trusted_context=trusted,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
            ),
            effective_scopes=scope_decision.effective_scopes,
            filter_reasons=scope_decision.filter_reasons,
            retrieved_refs=retrieved_refs,
            fallback_reason=None,
        )
        return ReviewedMemoryContextBundle(
            long_term_items=long_term_items,
            case_items=case_items,
            status_ref=status_ref,
        )

    async def load_memory_bundle_after_slot_resolution(
        self,
        *,
        session_context: SessionContextMemory,
        session_status_ref: SessionContextLoadStatusV1 | None = None,
        reviewed_memory_context: ReviewedMemoryContextBundle | None = None,
        trusted_context: Any | None = None,
        current_slots: Mapping[str, Any] | None = None,
        trusted_business_context: Mapping[str, Any] | None = None,
        requested_scopes: list[dict[str, Any]] | None = None,
        query: str | None = None,
        case_type: str | None = None,
        now: datetime | None = None,
        limit: int = 5,
    ) -> MemoryContextBundle:
        reviewed = reviewed_memory_context
        if reviewed is None:
            reviewed = await self.load_reviewed_memory_context(
                trusted_context=trusted_context,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
                query=query,
                case_type=case_type,
                now=now,
                limit=limit,
            )
        return MemoryContextBundle(
            session_context=session_context,
            long_term_items=list(reviewed.long_term_items),
            case_items=list(reviewed.case_items),
            session_status_ref=session_status_ref,
            reviewed_status_ref=reviewed.status_ref,
        )

    def project_memory_write_decision(
        self,
        legacy_result: Mapping[str, Any] | Any,
        *,
        memory_type: str,
        scope: Mapping[str, Any] | None = None,
        fallback_reason: str | None = None,
        authority_class: str = "contextual_only",
    ) -> MemoryWriteDecisionV2:
        result = _mapping(legacy_result)
        raw_decision = str(result.get("decision") or "skip")
        raw_status = str(
            result.get("status") or ("skipped" if raw_decision in {"delete", "skip", "tombstone"} else "written")
        )
        status = _memory_write_decision_status(raw_status)
        decision = _memory_write_decision_action(raw_decision, status)
        return MemoryWriteDecisionV2(
            status=status,
            decision=decision,
            authority_class=authority_class,
            memory_type=memory_type,
            memory_id=_optional_str(result.get("memory_id")),
            candidate_hash=_optional_str(result.get("candidate_hash")),
            source_identity_hash=_optional_str(result.get("source_identity_hash")),
            scope=dict(scope or {}),
            pii_classification=str(result.get("pii_classification") or "none"),
            review_status=str(result.get("review_status") or _review_status_for_status(status, decision)),
            reason_code=_memory_write_decision_reason_code(result),
            policy_version=str(result.get("policy_version") or "memory_write_policy.v1"),
            blocked_by=_string_list(result.get("blocked_by") or result.get("blocked_by_json")),
            fallback_reason=fallback_reason if fallback_reason is not None else _optional_str(result.get("fallback_reason")),
        )


def _session_context_status(
    context: SessionContextMemory,
    *,
    status: str,
    source: str,
    fallback_reason: str | None,
) -> SessionContextLoadStatusV1:
    return SessionContextLoadStatusV1(
        status=status,
        source=source,
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        thread_id=context.thread_id,
        run_id=context.run_id,
        loaded_refs=_session_context_refs(context),
        fallback_reason=fallback_reason,
        slot_count=len(context.slot_continuity.active_slots),
        recent_message_count=len(context.recent_messages),
        tool_summary_count=len(context.tool_summaries),
    )


def _session_context_refs(context: SessionContextMemory) -> list[SessionContextRef]:
    refs: list[SessionContextRef] = []
    if context.rolling_summary is not None:
        refs.append(
            _session_context_ref(
                context,
                source="conversation_log",
                ref_id=f"rolling_summary:{context.rolling_summary.summary_id}",
            )
        )
    refs.extend(
        _session_context_ref(context, source="conversation_log", ref_id=f"message:{message.message_id}")
        for message in context.recent_messages
    )
    refs.extend(
        _session_context_ref(context, source="tool_summary", ref_id=f"tool_summary:{summary.tool_result_record_id}")
        for summary in context.tool_summaries
    )
    if context.slot_continuity.continuity_claimed or context.slot_continuity.active_slots:
        refs.append(
            _session_context_ref(
                context,
                source="session_continuity_store",
                ref_id=f"slot_continuity:{context.slot_continuity.version or 'current'}",
            )
        )
    return refs


def _session_context_ref(context: SessionContextMemory, *, source: str, ref_id: str) -> SessionContextRef:
    return SessionContextRef(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        thread_id=context.thread_id,
        run_id=context.run_id,
        source=source,
        ref_id=ref_id,
    )


def _empty_session_context_memory(
    *,
    tenant_id: Any,
    user_id: Any,
    thread_id: str,
    run_id: Any,
    fallback_reason: str,
) -> SessionContextMemory:
    return SessionContextMemory(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        thread_id=thread_id,
        run_id=str(run_id),
        slot_continuity=SessionMemoryView(
            source="empty_adapter",
            continuity_claimed=False,
            active_slots={},
            slot_metadata={},
            fallback_reason=fallback_reason,
        ),
        fallback_reasons={"session_context": fallback_reason},
    )


class _ReviewedMemoryScopeDecision:
    def __init__(
        self,
        *,
        retrieval_scopes: list[tuple[str, str]],
        effective_scopes: list[dict[str, Any]],
        filter_reasons: list[str],
        fallback_reason: str | None,
    ) -> None:
        self.retrieval_scopes = retrieval_scopes
        self.effective_scopes = effective_scopes
        self.filter_reasons = filter_reasons
        self.fallback_reason = fallback_reason

    @property
    def primary_retrieval_scope(self) -> tuple[str, str]:
        return self.retrieval_scopes[0] if self.retrieval_scopes else ("merchant", "unknown")


def _parse_trusted_context(value: Any | None) -> TrustedContext | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, TrustedContext) else TrustedContext.model_validate(value)
    except ValidationError:
        return None


def _reviewed_memory_scopes(
    trusted: TrustedContext,
    *,
    current_slots: Mapping[str, Any] | None,
    trusted_business_context: Mapping[str, Any] | None,
) -> _ReviewedMemoryScopeDecision:
    filter_reasons: list[str] = []
    effective_scopes = _identity_effective_scopes(trusted)
    retrieval_scopes: list[tuple[str, str]] = []
    explicit_merchant_id = _first_string(current_slots, ("merchant_id",))
    business_merchant_id = _trusted_business_merchant_id(trusted_business_context)
    denied_merchant_id = _first_denied_merchant(
        trusted.merchant_scope,
        [explicit_merchant_id, business_merchant_id],
    )
    if denied_merchant_id is not None:
        filter_reasons.append(f"merchant_scope_denied:{denied_merchant_id}")
        return _ReviewedMemoryScopeDecision(
            retrieval_scopes=[],
            effective_scopes=effective_scopes,
            filter_reasons=filter_reasons,
            fallback_reason="merchant_scope_denied",
        )

    merchant_id = explicit_merchant_id or business_merchant_id
    if merchant_id is not None:
        _append_scope(
            retrieval_scopes,
            effective_scopes,
            "merchant",
            merchant_id,
            source="current_slots" if explicit_merchant_id is not None else "trusted_business_context",
            usage="retrieval",
        )

    case_id = _first_string(current_slots, ("case_id", "refund_case_id")) or _trusted_business_case_id(
        trusted_business_context
    )
    if case_id is not None:
        case_merchant_id = business_merchant_id or explicit_merchant_id
        if case_merchant_id is None or not merchant_scope_allows(trusted.merchant_scope, merchant_id=case_merchant_id):
            filter_reasons.append("case_scope_unverified")
        else:
            _append_scope(
                retrieval_scopes,
                effective_scopes,
                "case",
                case_id,
                source="trusted_business_context" if business_merchant_id is not None else "current_slots",
                usage="retrieval",
            )

    if not retrieval_scopes:
        filter_reasons.append("memory_scope_not_authority")
        return _ReviewedMemoryScopeDecision(
            retrieval_scopes=[],
            effective_scopes=effective_scopes,
            filter_reasons=filter_reasons,
            fallback_reason="memory_scope_not_authority",
        )

    return _ReviewedMemoryScopeDecision(
        retrieval_scopes=retrieval_scopes,
        effective_scopes=effective_scopes,
        filter_reasons=filter_reasons,
        fallback_reason=None,
    )


def _identity_effective_scopes(trusted: TrustedContext) -> list[dict[str, Any]]:
    return [
        {"scope_type": "tenant", "scope_id": trusted.tenant_id, "source": "trusted_context", "usage": "identity_filter"},
        {"scope_type": "user", "scope_id": trusted.user_id, "source": "trusted_context", "usage": "identity_filter"},
        {"scope_type": "thread", "scope_id": trusted.thread_id, "source": "trusted_context", "usage": "identity_filter"},
    ]


def _append_scope(
    retrieval_scopes: list[tuple[str, str]],
    effective_scopes: list[dict[str, Any]],
    scope_type: str,
    scope_id: str,
    *,
    source: str,
    usage: str,
) -> None:
    scope = (scope_type, scope_id)
    if scope in retrieval_scopes:
        return
    retrieval_scopes.append(scope)
    effective_scopes.append(
        {"scope_type": scope_type, "scope_id": scope_id, "source": source, "usage": usage}
    )


def _requests_tenant_or_global_memory(requested_scopes: list[dict[str, Any]] | None) -> bool:
    for requested_scope in requested_scopes or []:
        scope_type = str(requested_scope.get("scope_type") or requested_scope.get("type") or "").strip().lower()
        if scope_type in _UNSUPPORTED_SCOPE_TYPES:
            return True
    return False


def _first_denied_merchant(scope: MerchantScopeV1, merchant_ids: list[str | None]) -> str | None:
    for merchant_id in merchant_ids:
        if merchant_id is None:
            continue
        if not merchant_scope_allows(scope, merchant_id=merchant_id):
            return merchant_id
    return None


def _trusted_business_merchant_id(value: Mapping[str, Any] | None) -> str | None:
    return _first_string_deep(value, ("merchant_id", "merchant_no"))


def _trusted_business_case_id(value: Mapping[str, Any] | None) -> str | None:
    return _first_string_deep(value, ("case_id", "refund_case_id", "refund_case_no"))


def _first_string(value: Mapping[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, int | float) and str(raw).strip():
            return str(raw).strip()
    return None


def _first_string_deep(value: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, Mapping):
        direct = _first_string(value, keys)
        if direct is not None:
            return direct
        for nested in value.values():
            found = _first_string_deep(nested, keys)
            if found is not None:
                return found
    if isinstance(value, list | tuple):
        for nested in value:
            found = _first_string_deep(nested, keys)
            if found is not None:
                return found
    return None


def _empty_reviewed_memory_context(
    *,
    trusted_context: Any | None,
    current_slots: Mapping[str, Any] | None,
    trusted_business_context: Mapping[str, Any] | None,
    requested_scopes: list[dict[str, Any]] | None,
    fallback_reason: str,
    filter_reasons: list[str],
    effective_scopes: list[dict[str, Any]] | None = None,
    status: str = "skipped",
) -> ReviewedMemoryContextBundle:
    status_ref = ReviewedMemoryContextRetrieveStatusV1(
        status=status,
        trusted_scope_inputs=_trusted_scope_inputs(
            trusted_context=trusted_context,
            current_slots=current_slots,
            trusted_business_context=trusted_business_context,
            requested_scopes=requested_scopes,
        ),
        effective_scopes=effective_scopes or [],
        filter_reasons=list(dict.fromkeys(filter_reasons)),
        retrieved_refs=[],
        fallback_reason=fallback_reason,
    )
    return ReviewedMemoryContextBundle(long_term_items=[], case_items=[], status_ref=status_ref)


def _reviewed_long_term_items(
    items: list[Any],
    *,
    tenant_id: str,
    fallback_scope: tuple[str, str],
) -> tuple[list[dict[str, Any]], list[ReviewedMemoryRef]]:
    projected_items: list[dict[str, Any]] = []
    refs: list[ReviewedMemoryRef] = []
    for item in items:
        raw = _mapping(item)
        projected = _select_item_keys(raw, _LONG_TERM_ITEM_KEYS)
        memory_id = _optional_str(projected.get("memory_id"))
        scope_type = _optional_str(projected.get("scope_type")) or fallback_scope[0]
        scope_id = _optional_str(projected.get("scope_id")) or fallback_scope[1]
        review_status = _optional_str(projected.get("review_status")) or "approved"
        if memory_id is None:
            continue
        projected["scope_type"] = scope_type
        projected["scope_id"] = scope_id
        projected["review_status"] = review_status
        ref = ReviewedMemoryRef(
            tenant_id=tenant_id,
            memory_type="long_term",
            scope_type=scope_type,
            scope_id=scope_id,
            memory_id=memory_id,
            review_status=review_status,
            source_identity_hash=_optional_str(projected.get("source_identity_hash")),
            prompt_safe=True,
        )
        projected["ref"] = ref.model_dump(mode="json")
        projected_items.append(projected)
        refs.append(ref)
    return projected_items, refs


def _reviewed_case_items(
    items: list[Any],
    *,
    tenant_id: str,
    fallback_scope: tuple[str, str],
) -> tuple[list[dict[str, Any]], list[ReviewedMemoryRef]]:
    projected_items: list[dict[str, Any]] = []
    refs: list[ReviewedMemoryRef] = []
    for item in items:
        raw = _mapping(item)
        projected = _select_item_keys(raw, _CASE_ITEM_KEYS)
        memory_id = _optional_str(
            projected.get("case_memory_id") or projected.get("memory_id") or projected.get("id")
        )
        if memory_id is None:
            continue
        scope_type, scope_id = fallback_scope
        ref = ReviewedMemoryRef(
            tenant_id=tenant_id,
            memory_type="case",
            scope_type=scope_type,
            scope_id=scope_id,
            memory_id=memory_id,
            review_status="approved",
            source_identity_hash=_optional_str(projected.get("source_identity_hash")),
            prompt_safe=True,
        )
        projected["ref"] = ref.model_dump(mode="json")
        projected_items.append(projected)
        refs.append(ref)
    return projected_items, refs


def _select_item_keys(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key in keys:
        if key in mapping and mapping[key] is not None:
            selected[key] = _json_safe(mapping[key])
    return selected


def _uuid_or_value(value: str) -> UUID | str:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return str(value)


def _trusted_scope_inputs(
    *,
    trusted_context: Any | None,
    current_slots: Mapping[str, Any] | None,
    trusted_business_context: Mapping[str, Any] | None,
    requested_scopes: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    if trusted_context is not None:
        for key in ("tenant_id", "user_id", "thread_id", "run_id", "trace_id", "role"):
            value = getattr(trusted_context, key, None)
            if value is not None:
                inputs[key] = value
        merchant_scope = getattr(trusted_context, "merchant_scope", None)
        if merchant_scope is not None:
            merchant_ids = getattr(merchant_scope, "merchant_ids", None)
            inputs["merchant_scope"] = list(merchant_ids or [])
    if current_slots:
        inputs["current_slots"] = dict(current_slots)
    if trusted_business_context:
        inputs["trusted_business_context"] = dict(trusted_business_context)
    if requested_scopes:
        inputs["requested_scopes"] = [dict(scope) for scope in requested_scopes]
    return inputs


def _mapping(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {
        key: getattr(value, key)
        for key in (
            "status",
            "decision",
            "memory_id",
            "candidate_hash",
            "source_identity_hash",
            "pii_classification",
            "review_status",
            "reason_code",
            "policy_version",
            "blocked_by",
            "blocked_by_json",
            "fallback_reason",
        )
        if hasattr(value, key)
    }


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [str(item) for item in value if item is not None]


def _review_status_for_status(status: str, decision: str) -> str:
    if status == "needs_review" or decision == "needs_review":
        return "needs_review"
    if decision in {"delete", "tombstone"}:
        return "tombstoned"
    if status in {"skipped", "disabled", "fallback", "error"}:
        return "not_written"
    return "not_applicable"


def _memory_write_decision_status(status: str) -> str:
    if status in {"written", "merged_after_conflict"}:
        return "written"
    if status in {"skipped", "disabled", "fallback", "conflict"}:
        return "skipped"
    if status == "error":
        return "error"
    return status


def _memory_write_decision_action(decision: str, status: str) -> str:
    if decision in {"delete", "needs_review", "supersede", "tombstone", "write_blocked"}:
        return decision
    if status in {"skipped", "error"} or decision == "skip":
        return "skip"
    return "write"


def _memory_write_decision_reason_code(result: Mapping[str, Any]) -> str:
    reason_code = str(result.get("reason_code") or "unspecified")
    if result.get("status") == "error" and reason_code in {"write_failed", "unavailable"}:
        return "write_error"
    return reason_code
