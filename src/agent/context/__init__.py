"""Prompt-safe context assembly boundary."""

from src.agent.context.assembler import ContextAssembler
from src.agent.context.budget import PromptAssembly, PromptBlock, TokenBudgetPolicy
from src.agent.context.projectors import (
    project_business_context_for_prompt,
    project_candidate_slot_hints_for_prompt,
    project_case_memory_for_prompt,
    project_policy_refs_for_prompt,
    project_profile_memory_for_prompt,
    project_recent_message_for_prompt,
    project_tool_result_summary,
    project_working_state_for_prompt,
)

__all__ = [
    "ContextAssembler",
    "PromptAssembly",
    "PromptBlock",
    "TokenBudgetPolicy",
    "project_business_context_for_prompt",
    "project_candidate_slot_hints_for_prompt",
    "project_case_memory_for_prompt",
    "project_policy_refs_for_prompt",
    "project_profile_memory_for_prompt",
    "project_recent_message_for_prompt",
    "project_tool_result_summary",
    "project_working_state_for_prompt",
]
