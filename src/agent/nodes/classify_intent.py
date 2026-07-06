from __future__ import annotations

from typing import Any

from src.agent.nodes import contextual_intent_resolve as _canonical
from src.agent.schemas import IntentResultV3
from src.agent.state import AgentState


FORBIDDEN_STATE_WRITES = _canonical.FORBIDDEN_STATE_WRITES
INTENT_POLICY_REGISTRY = _canonical.INTENT_POLICY_REGISTRY
SLOT_POLICY_REGISTRY = _canonical.SLOT_POLICY_REGISTRY
_get_llm = _canonical._get_llm


def _with_legacy_intent_output_mirror(update: dict[str, Any]) -> dict[str, Any]:
    llm_outputs = update.get("llm_outputs")
    if not isinstance(llm_outputs, dict):
        return update
    canonical_output = llm_outputs.get("contextual_intent_resolve")
    if not isinstance(canonical_output, dict):
        return update
    return {
        **update,
        "llm_outputs": {
            **llm_outputs,
            "intent_classification": canonical_output,
        },
    }


def _with_compat_globals(callback):
    original_get_llm = _canonical._get_llm
    original_intent_registry = _canonical.INTENT_POLICY_REGISTRY
    original_slot_registry = _canonical.SLOT_POLICY_REGISTRY
    try:
        _canonical._get_llm = _get_llm
        _canonical.INTENT_POLICY_REGISTRY = INTENT_POLICY_REGISTRY
        _canonical.SLOT_POLICY_REGISTRY = SLOT_POLICY_REGISTRY
        return callback()
    finally:
        _canonical._get_llm = original_get_llm
        _canonical.INTENT_POLICY_REGISTRY = original_intent_registry
        _canonical.SLOT_POLICY_REGISTRY = original_slot_registry


def intent_result_to_state(
    result: IntentResultV3,
    prior_llm_outputs: dict[str, Any] | None = None,
    pre_route: Any | None = None,
    user_query: str = "",
    role: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """Compatibility adapter for tests/imports; canonical logic lives in contextual_intent_resolve."""

    return _with_legacy_intent_output_mirror(
        _with_compat_globals(
            lambda: _canonical.intent_result_to_state(
                result,
                prior_llm_outputs=prior_llm_outputs,
                pre_route=pre_route,
                user_query=user_query,
                role=role,
                channel=channel,
            )
        )
    )


async def classify_intent(state: AgentState) -> dict[str, Any]:
    """Compatibility wrapper for the canonical contextual_intent_resolve node."""

    original_get_llm = _canonical._get_llm
    original_intent_registry = _canonical.INTENT_POLICY_REGISTRY
    original_slot_registry = _canonical.SLOT_POLICY_REGISTRY
    try:
        _canonical._get_llm = _get_llm
        _canonical.INTENT_POLICY_REGISTRY = INTENT_POLICY_REGISTRY
        _canonical.SLOT_POLICY_REGISTRY = SLOT_POLICY_REGISTRY
        return _with_legacy_intent_output_mirror(await _canonical.contextual_intent_resolve(state))
    finally:
        _canonical._get_llm = original_get_llm
        _canonical.INTENT_POLICY_REGISTRY = original_intent_registry
        _canonical.SLOT_POLICY_REGISTRY = original_slot_registry
