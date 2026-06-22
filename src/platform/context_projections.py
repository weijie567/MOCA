"""Service-safe projections derived from canonical TrustedContext."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.knowledge.schemas import KnowledgeContext
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.contracts import ToolCallContext


class ProjectionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str | None = None
    model_version: str | None = None
    tool_version: str | None = None
    artifact_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)


class MemoryContext(ProjectionMetadata):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["memory_context.v1"] = "memory_context.v1"
    tenant_id: str
    user_id: str
    role: str
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None


class ApprovalContext(ProjectionMetadata):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["approval_context.v1"] = "approval_context.v1"
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    merchant_scope: dict[str, Any]
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None


class ReplayContext(ProjectionMetadata):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_context.v1"] = "replay_context.v1"
    tenant_id: str
    user_id: str
    role: str
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None


class IntentPolicyContext(ProjectionMetadata):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["intent_policy_context.v1"] = "intent_policy_context.v1"
    tenant_id: str
    user_id: str
    role: str
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None
    channel: str


def project_to_tool_context(
    trusted: TrustedContext,
    *,
    request_id: str,
    tool_call_id: str,
    caller_node: str,
    deadline_at: datetime | None = None,
    effective_at: str | None = None,
    attempt: int = 1,
    max_attempts: int = 1,
    idempotency_key: str | None = None,
    approval_ref: str | None = None,
    safety_snapshot_ref: str | None = None,
    policy_snapshot_ref: str | None = None,
) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=trusted.tenant_id,
        user_id=trusted.user_id,
        role=trusted.role,
        permissions=list(trusted.permissions),
        merchant_scope=trusted.merchant_scope.model_dump(),
        session_id=trusted.session_id,
        thread_id=trusted.thread_id,
        run_id=trusted.run_id,
        trace_id=trusted.trace_id or "",
        request_id=request_id,
        tool_call_id=tool_call_id,
        caller_node=caller_node,
        deadline_at=deadline_at,
        effective_at=effective_at,
        attempt=attempt,
        max_attempts=max_attempts,
        idempotency_key=idempotency_key,
        approval_ref=approval_ref,
        safety_snapshot_ref=safety_snapshot_ref,
        policy_snapshot_ref=policy_snapshot_ref,
    )


def project_merchant_scope_for_knowledge(
    value: MerchantScopeV1 | dict[str, Any] | list[str] | None,
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, MerchantScopeV1):
        return list(value.merchant_ids) if value.merchant_ids else []
    if isinstance(value, dict):
        raw_ids = value.get("merchant_ids")
    else:
        raw_ids = value
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    if not all(isinstance(item, str) and item for item in raw_ids):
        return []
    return list(raw_ids)


def project_to_knowledge_context(trusted: TrustedContext, *, effective_at: str) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=trusted.tenant_id,
        user_id=trusted.user_id,
        role=trusted.role,
        merchant_scope=project_merchant_scope_for_knowledge(trusted.merchant_scope),
        run_id=trusted.run_id,
        trace_id=trusted.trace_id or "",
        locale=trusted.locale,
        effective_at=effective_at,
    )


def project_tool_context_to_knowledge_context(
    ctx: ToolCallContext,
    *,
    effective_at: str,
) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        role=ctx.role,
        merchant_scope=project_merchant_scope_for_knowledge(ctx.merchant_scope),
        run_id=ctx.run_id,
        trace_id=ctx.trace_id,
        locale=None,
        effective_at=effective_at,
    )


def project_to_memory_context(
    trusted: TrustedContext,
    *,
    policy_version: str | None = None,
    model_version: str | None = None,
    tool_version: str | None = None,
    artifact_ref: str | None = None,
    artifact_refs: list[str] | None = None,
) -> MemoryContext:
    return MemoryContext(
        tenant_id=trusted.tenant_id,
        user_id=trusted.user_id,
        role=trusted.role,
        session_id=trusted.session_id,
        thread_id=trusted.thread_id,
        run_id=trusted.run_id,
        trace_id=trusted.trace_id,
        locale=trusted.locale,
        **_metadata_kwargs(
            policy_version=policy_version,
            model_version=model_version,
            tool_version=tool_version,
            artifact_ref=artifact_ref,
            artifact_refs=artifact_refs,
        ),
    )


def project_to_approval_context(
    trusted: TrustedContext,
    *,
    approval_ref: str | None = None,
    safety_snapshot_ref: str | None = None,
    policy_version: str | None = None,
    model_version: str | None = None,
    tool_version: str | None = None,
    artifact_ref: str | None = None,
    artifact_refs: list[str] | None = None,
) -> ApprovalContext:
    return ApprovalContext(
        tenant_id=trusted.tenant_id,
        user_id=trusted.user_id,
        role=trusted.role,
        permissions=list(trusted.permissions),
        merchant_scope=trusted.merchant_scope.model_dump(),
        session_id=trusted.session_id,
        thread_id=trusted.thread_id,
        run_id=trusted.run_id,
        trace_id=trusted.trace_id,
        locale=trusted.locale,
        approval_ref=approval_ref,
        safety_snapshot_ref=safety_snapshot_ref,
        **_metadata_kwargs(
            policy_version=policy_version,
            model_version=model_version,
            tool_version=tool_version,
            artifact_ref=artifact_ref,
            artifact_refs=artifact_refs,
        ),
    )


def project_to_replay_context(
    trusted: TrustedContext,
    *,
    policy_version: str | None = None,
    model_version: str | None = None,
    tool_version: str | None = None,
    artifact_ref: str | None = None,
    artifact_refs: list[str] | None = None,
) -> ReplayContext:
    return ReplayContext(
        tenant_id=trusted.tenant_id,
        user_id=trusted.user_id,
        role=trusted.role,
        session_id=trusted.session_id,
        thread_id=trusted.thread_id,
        run_id=trusted.run_id,
        trace_id=trusted.trace_id,
        locale=trusted.locale,
        **_metadata_kwargs(
            policy_version=policy_version,
            model_version=model_version,
            tool_version=tool_version,
            artifact_ref=artifact_ref,
            artifact_refs=artifact_refs,
        ),
    )


def project_to_intent_policy_context(
    trusted: TrustedContext,
    *,
    channel: str,
    policy_version: str | None = None,
    model_version: str | None = None,
    tool_version: str | None = None,
    artifact_ref: str | None = None,
    artifact_refs: list[str] | None = None,
) -> IntentPolicyContext:
    return IntentPolicyContext(
        tenant_id=trusted.tenant_id,
        user_id=trusted.user_id,
        role=trusted.role,
        session_id=trusted.session_id,
        thread_id=trusted.thread_id,
        run_id=trusted.run_id,
        trace_id=trusted.trace_id,
        locale=trusted.locale,
        channel=channel,
        **_metadata_kwargs(
            policy_version=policy_version,
            model_version=model_version,
            tool_version=tool_version,
            artifact_ref=artifact_ref,
            artifact_refs=artifact_refs,
        ),
    )


def project_to_agent_state_identity(trusted: TrustedContext) -> dict[str, str | None]:
    return {
        "tenant_id": trusted.tenant_id,
        "user_id": trusted.user_id,
        "role": trusted.role,
        "session_id": trusted.session_id,
        "thread_id": trusted.thread_id,
        "run_id": trusted.run_id,
        "trace_id": trusted.trace_id,
    }


def project_to_legacy_agent_state_identity(trusted: TrustedContext) -> dict[str, str | None]:
    """Compatibility-only adapter for legacy AgentState.current_run_id."""

    identity = project_to_agent_state_identity(trusted)
    return identity | {"current_run_id": trusted.run_id}


def _metadata_kwargs(
    *,
    policy_version: str | None,
    model_version: str | None,
    tool_version: str | None,
    artifact_ref: str | None,
    artifact_refs: list[str] | None,
) -> dict[str, Any]:
    return {
        "policy_version": policy_version,
        "model_version": model_version,
        "tool_version": tool_version,
        "artifact_ref": artifact_ref,
        "artifact_refs": list(artifact_refs or []),
    }
