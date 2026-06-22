from __future__ import annotations

from datetime import UTC, datetime

from src.knowledge.schemas import KnowledgeContext
from src.platform.context_projections import (
    project_to_agent_state_identity,
    project_to_approval_context,
    project_to_intent_policy_context,
    project_to_knowledge_context,
    project_to_legacy_agent_state_identity,
    project_to_memory_context,
    project_to_replay_context,
    project_to_tool_context,
)
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.contracts import ToolCallContext


def _trusted_context() -> TrustedContext:
    return TrustedContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support",
        permissions=["tool:get_order", "knowledge:search"],
        merchant_scope=MerchantScopeV1(merchant_ids=["merchant-1"]),
        session_id="session-1",
        thread_id="thread-1",
        run_id="run-1",
        trace_id="trace-1",
        locale="zh-CN",
    )


def test_tool_projection_preserves_tool_context_v2_and_local_fields() -> None:
    trusted = _trusted_context()
    deadline = datetime(2026, 6, 22, 12, 0, tzinfo=UTC)

    tool_context = project_to_tool_context(
        trusted,
        request_id="request-1",
        tool_call_id="tool-call-1",
        caller_node="investigate",
        deadline_at=deadline,
        effective_at="2026-06-22T12:00:00Z",
        attempt=2,
        max_attempts=3,
        idempotency_key="run-1:search_policy:1",
        safety_snapshot_ref="safety-snapshot-1",
        policy_snapshot_ref="policy-snapshot-1",
    )

    assert isinstance(tool_context, ToolCallContext)
    assert tool_context.schema_version == "tool_context.v2"
    assert tool_context.tenant_id == trusted.tenant_id
    assert tool_context.permissions == trusted.permissions
    assert tool_context.merchant_scope == trusted.merchant_scope.model_dump()
    assert tool_context.request_id == "request-1"
    assert tool_context.tool_call_id == "tool-call-1"
    assert tool_context.caller_node == "investigate"
    assert tool_context.deadline_at == deadline
    assert tool_context.safety_snapshot_ref == "safety-snapshot-1"
    assert tool_context.policy_snapshot_ref == "policy-snapshot-1"
    assert "policy_version" not in tool_context.model_dump()
    assert "model_version" not in tool_context.model_dump()
    assert "tool_version" not in tool_context.model_dump()
    assert "request_id" not in trusted.model_dump()


def test_knowledge_projection_keeps_effective_at_local_and_scope_list_compatible() -> None:
    trusted = _trusted_context()
    knowledge_context = project_to_knowledge_context(
        trusted,
        effective_at="2026-06-22T12:00:00Z",
    )

    assert isinstance(knowledge_context, KnowledgeContext)
    assert knowledge_context.tenant_id == trusted.tenant_id
    assert knowledge_context.user_id == trusted.user_id
    assert knowledge_context.role == trusted.role
    assert knowledge_context.merchant_scope == ["merchant-1"]
    assert knowledge_context.run_id == trusted.run_id
    assert knowledge_context.trace_id == trusted.trace_id
    assert knowledge_context.locale == trusted.locale
    assert knowledge_context.effective_at == "2026-06-22T12:00:00Z"
    assert "effective_at" not in trusted.model_dump()


def test_memory_approval_replay_intent_projections_do_not_widen_identity_scope() -> None:
    trusted = _trusted_context()
    metadata = {
        "policy_version": "policy.v1",
        "model_version": "gpt-test.v1",
        "tool_version": "tool.v2",
        "artifact_refs": ["artifact-1"],
    }

    projections = [
        project_to_memory_context(trusted, **metadata),
        project_to_approval_context(trusted, approval_ref="approval-1", safety_snapshot_ref="safety-1", **metadata),
        project_to_replay_context(trusted, **metadata),
        project_to_intent_policy_context(trusted, channel="agent_runs", **metadata),
    ]

    for projection in projections:
        payload = projection.model_dump()
        assert payload["tenant_id"] == trusted.tenant_id
        assert payload["user_id"] == trusted.user_id
        assert payload["role"] == trusted.role
        assert payload["thread_id"] == trusted.thread_id
        assert payload["run_id"] == trusted.run_id
        assert payload["trace_id"] == trusted.trace_id
        assert payload.get("permissions") in (None, trusted.permissions)
        assert payload.get("merchant_scope") in (None, trusted.merchant_scope.model_dump(), ["merchant-1"])

    canonical_payload = trusted.model_dump()
    for local_field in ("policy_version", "model_version", "tool_version", "artifact_ref", "artifact_refs"):
        assert local_field not in canonical_payload


def test_intent_policy_context_channel_is_projection_local() -> None:
    trusted = _trusted_context()

    context = project_to_intent_policy_context(trusted, channel="agent_runs", policy_version="intent_policy.v1")

    assert context.channel == "agent_runs"
    assert context.tenant_id == trusted.tenant_id
    assert context.role == trusted.role
    assert context.locale == trusted.locale
    assert "channel" not in trusted.model_dump()
    assert "policy_version" not in trusted.model_dump()


def test_agent_state_identity_projection_uses_canonical_run_id() -> None:
    trusted = _trusted_context()

    identity = project_to_agent_state_identity(trusted)

    assert identity == {
        "tenant_id": trusted.tenant_id,
        "user_id": trusted.user_id,
        "role": trusted.role,
        "session_id": trusted.session_id,
        "thread_id": trusted.thread_id,
        "run_id": trusted.run_id,
        "trace_id": trusted.trace_id,
    }
    assert "current_run_id" not in identity
    assert "permissions" not in identity
    assert "merchant_scope" not in identity


def test_legacy_agent_state_identity_adapter_is_explicit() -> None:
    trusted = _trusted_context()

    identity = project_to_legacy_agent_state_identity(trusted)

    assert identity["current_run_id"] == trusted.run_id
    assert identity["tenant_id"] == trusted.tenant_id
    assert identity["user_id"] == trusted.user_id
    assert identity["thread_id"] == trusted.thread_id
    assert "permissions" not in identity
    assert "merchant_scope" not in identity
