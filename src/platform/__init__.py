"""Trusted platform context contracts and projections."""

from src.platform.context_projections import (
    ApprovalContext,
    IntentPolicyContext,
    MemoryContext,
    ReplayContext,
    project_merchant_scope_for_knowledge,
    project_to_agent_state_identity,
    project_to_approval_context,
    project_to_intent_policy_context,
    project_to_knowledge_context,
    project_to_legacy_agent_state_identity,
    project_to_memory_context,
    project_to_replay_context,
    project_to_tool_context,
    project_tool_context_to_knowledge_context,
)
from src.platform.trusted_context import (
    MERCHANT_SCOPE_SCHEMA_VERSION,
    TRUSTED_CONTEXT_SCHEMA_VERSION,
    MerchantScopeV1,
    TrustedContext,
    TrustedContextFactory,
    merchant_scope_allows,
)

__all__ = [
    "ApprovalContext",
    "IntentPolicyContext",
    "MERCHANT_SCOPE_SCHEMA_VERSION",
    "MemoryContext",
    "ReplayContext",
    "TRUSTED_CONTEXT_SCHEMA_VERSION",
    "MerchantScopeV1",
    "TrustedContext",
    "TrustedContextFactory",
    "merchant_scope_allows",
    "project_merchant_scope_for_knowledge",
    "project_to_agent_state_identity",
    "project_to_approval_context",
    "project_to_intent_policy_context",
    "project_to_knowledge_context",
    "project_to_legacy_agent_state_identity",
    "project_to_memory_context",
    "project_to_replay_context",
    "project_to_tool_context",
    "project_tool_context_to_knowledge_context",
]
