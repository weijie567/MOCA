from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.agent.context.budget import PromptAssembly, PromptBlock, TokenBudgetPolicy
from src.agent.context.projectors import (
    extract_business_ids_from_prompt_parts,
    project_business_context_for_prompt,
    project_case_memory_for_prompt,
    project_policy_refs_for_prompt,
    project_profile_memory_for_prompt,
    project_recent_message_for_prompt,
    project_tool_result_summary,
    project_working_state_for_prompt,
)
from src.agent.working_state import WorkingStateV1


DEFAULT_SAFETY_CONSTRAINTS = (
    "Use only prompt-safe summaries and refs.",
    "Do not expose private reasoning, upstream payloads, authority objects, or debug traces.",
    "Require policy evidence before recommending material action.",
)


class ContextAssembler:
    def __init__(self, budget_policy: TokenBudgetPolicy | None = None) -> None:
        self.budget_policy = budget_policy or TokenBudgetPolicy()

    def assemble(
        self,
        *,
        system_prompt: str,
        current_user_message: str,
        working_state: WorkingStateV1,
        thread_rolling_summary: str | None = None,
        recent_messages: Sequence[Mapping[str, Any]] | None = None,
        verified_policy_snippets: Sequence[Any] | None = None,
        profile_memory_snippets: Sequence[Any] | None = None,
        case_memory_snippets: Sequence[Any] | None = None,
        tool_result_summaries: Sequence[Any] | None = None,
        business_context: Mapping[str, Any] | None = None,
        node_hints: str | Sequence[str] | None = None,
        safety_constraints: Sequence[str] | None = None,
    ) -> PromptAssembly:
        blocks: list[PromptBlock] = [
            PromptBlock("system_prompt", system_prompt, priority=100, protected=True),
        ]

        constraints = safety_constraints or DEFAULT_SAFETY_CONSTRAINTS
        blocks.append(
            PromptBlock(
                "safety_constraints",
                "\n".join(f"- {item}" for item in constraints if item),
                priority=95,
                protected=True,
            )
        )

        business_ids = extract_business_ids_from_prompt_parts(
            current_user_message,
            business_context or {},
            working_state.model_dump(mode="json"),
        )
        if business_ids:
            blocks.append(PromptBlock("business_ids", ", ".join(business_ids), priority=90, protected=True))

        policy_block = project_policy_refs_for_prompt(verified_policy_snippets)
        if policy_block:
            blocks.append(PromptBlock("policy_refs", policy_block, priority=85, protected=True))

        working_state_block = project_working_state_for_prompt(working_state)
        if working_state_block:
            blocks.append(PromptBlock("working_state", working_state_block, priority=75))

        business_context_block = project_business_context_for_prompt(business_context)
        if business_context_block:
            blocks.append(PromptBlock("business_context", business_context_block, priority=72))

        if thread_rolling_summary:
            blocks.append(PromptBlock("thread_rolling_summary", thread_rolling_summary, priority=70))

        tool_block = _project_tool_summaries(tool_result_summaries)
        if tool_block:
            blocks.append(PromptBlock("tool_summaries", tool_block, priority=58))

        hint_block = _project_node_hints(node_hints)
        if hint_block:
            blocks.append(PromptBlock("node_hints", hint_block, priority=65))

        profile_memory_block = project_profile_memory_for_prompt(profile_memory_snippets)
        case_memory_block = project_case_memory_for_prompt(case_memory_snippets)
        profile_memory_block, case_memory_block = _cap_memory_blocks(profile_memory_block, case_memory_block)
        if profile_memory_block:
            blocks.append(PromptBlock("profile_memory", profile_memory_block, priority=55))
        if case_memory_block:
            blocks.append(PromptBlock("case_memory", case_memory_block, priority=54))

        recent_block = _project_recent_messages(recent_messages)
        if recent_block:
            blocks.append(PromptBlock("recent_messages", recent_block, priority=60))

        blocks.append(PromptBlock("current_user_message", current_user_message, priority=100, protected=True))
        return self.budget_policy.apply(blocks)


def _project_recent_messages(messages: Sequence[Mapping[str, Any]] | None) -> str:
    projected = [project_recent_message_for_prompt(message) for message in messages or []]
    return "\n".join(item for item in projected if item)


def _project_tool_summaries(summaries: Sequence[Any] | None) -> str:
    projected = [project_tool_result_summary(summary) for summary in summaries or []]
    return "\n".join(item for item in projected if item)


def _project_node_hints(hints: str | Sequence[str] | None) -> str:
    if hints is None:
        return ""
    if isinstance(hints, str):
        return hints.strip()
    return "\n".join(str(item).strip() for item in hints if str(item).strip())


def _cap_memory_blocks(profile_memory: str, case_memory: str, *, max_chars: int = 1600) -> tuple[str, str]:
    separator_chars = 1 if profile_memory and case_memory else 0
    if len(profile_memory) + len(case_memory) + separator_chars <= max_chars:
        return profile_memory, case_memory

    profile_cap = min(len(profile_memory), max_chars // 2)
    profile_memory = _bounded(profile_memory, profile_cap)
    remaining = max(0, max_chars - len(profile_memory) - (1 if profile_memory and case_memory else 0))
    return profile_memory, _bounded(case_memory, remaining)


def _bounded(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    marker = " [truncated]"
    return value[: max(0, max_chars - len(marker))] + marker
