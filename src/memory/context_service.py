from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.memory.case_memory import CaseMemoryService
from src.memory.context_refs import (
    MemoryWriteDecisionV2,
    ReviewedMemoryContextBundle,
    ReviewedMemoryContextRetrieveStatusV1,
    SessionContextLoadStatusV1,
    SessionContextRef,
)
from src.memory.long_term import LongTermMemoryService
from src.memory.schemas import SessionContextMemory, SessionMemoryView
from src.memory.session_bundle import SessionMemoryBundleService


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
        **_: Any,
    ) -> ReviewedMemoryContextBundle:
        status_ref = ReviewedMemoryContextRetrieveStatusV1(
            status="skipped",
            trusted_scope_inputs=_trusted_scope_inputs(
                trusted_context=trusted_context,
                current_slots=current_slots,
                trusted_business_context=trusted_business_context,
                requested_scopes=requested_scopes,
            ),
            effective_scopes=[],
            filter_reasons=["not_implemented_in_facade"],
            retrieved_refs=[],
            fallback_reason="not_implemented_in_facade",
        )
        return ReviewedMemoryContextBundle(long_term_items=[], case_items=[], status_ref=status_ref)

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
        decision = str(result.get("decision") or "skip")
        status = str(result.get("status") or ("skipped" if decision in {"delete", "skip", "tombstone"} else "written"))
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
            reason_code=str(result.get("reason_code") or "unspecified"),
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
            "fallback_reason",
        )
        if hasattr(value, key)
    }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _review_status_for_status(status: str, decision: str) -> str:
    if status == "needs_review" or decision == "needs_review":
        return "needs_review"
    if decision in {"delete", "tombstone"}:
        return "tombstoned"
    if status in {"skipped", "disabled", "fallback", "error"}:
        return "not_written"
    return "not_applicable"
