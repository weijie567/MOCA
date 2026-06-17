from __future__ import annotations

from src.agent.context import PromptBlock, TokenBudgetPolicy


def _block(name: str, content: str, *, priority: int, protected: bool = False) -> PromptBlock:
    return PromptBlock(name=name, content=content, priority=priority, protected=protected)


def test_token_budget_preserves_protected_blocks():
    policy = TokenBudgetPolicy(max_chars=220)
    blocks = [
        _block("system_prompt", "SYSTEM-CRITICAL " * 6, priority=100, protected=True),
        _block("safety_constraints", "SAFETY-CRITICAL " * 5, priority=95, protected=True),
        _block("business_ids", "ORD-1001 RF-2001", priority=90, protected=True),
        _block("policy_refs", "policy-refund:v1:chunk-1", priority=85, protected=True),
        _block("old_recent_messages", "OLD-RECENT-MESSAGE " * 20, priority=20),
        _block("verbose_tool_summaries", "VERBOSE-TOOL-SUMMARY " * 20, priority=30),
        _block("current_user_message", "USER-CRITICAL", priority=100, protected=True),
    ]

    assembly = policy.apply(blocks)
    prompt = "\n".join(block.content for block in assembly.blocks)

    assert "SYSTEM-CRITICAL" in prompt
    assert "SAFETY-CRITICAL" in prompt
    assert "ORD-1001 RF-2001" in prompt
    assert "policy-refund:v1:chunk-1" in prompt
    assert "USER-CRITICAL" in prompt
    assert len(prompt) <= policy.max_chars + len("\n".join(block.content for block in assembly.protected_blocks))


def test_token_budget_truncates_low_priority_blocks_first():
    policy = TokenBudgetPolicy(max_chars=260)
    blocks = [
        _block("system_prompt", "system prompt", priority=100, protected=True),
        _block("current_user_message", "current user message", priority=100, protected=True),
        _block("safety_constraints", "safety constraints", priority=95, protected=True),
        _block("business_ids", "ORD-1001", priority=90, protected=True),
        _block("policy_refs", "policy-refund:v1:chunk-1", priority=85, protected=True),
        _block("old_recent_messages", "OLD_RECENT_MESSAGES " * 40, priority=10),
        _block("verbose_tool_summaries", "VERBOSE_TOOL_SUMMARIES " * 40, priority=20),
        _block("extra_policy_snippets", "EXTRA_POLICY_SNIPPETS " * 40, priority=30),
        _block("low_value_summary_details", "LOW_VALUE_SUMMARY_DETAILS " * 40, priority=40),
        _block("thread_rolling_summary", "important summary", priority=70),
    ]

    assembly = policy.apply(blocks)
    kept_names = [block.name for block in assembly.blocks]
    prompt = "\n".join(block.content for block in assembly.blocks)

    assert "old_recent_messages" not in kept_names
    assert "verbose_tool_summaries" not in kept_names
    assert "extra_policy_snippets" not in kept_names
    assert "low_value_summary_details" not in kept_names
    assert "thread_rolling_summary" in kept_names
    assert "important summary" in prompt
    assert "system prompt" in prompt
    assert "current user message" in prompt
