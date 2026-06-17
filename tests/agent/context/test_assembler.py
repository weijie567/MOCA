from __future__ import annotations

from src.agent.context import (
    ContextAssembler,
    PromptAssembly,
    TokenBudgetPolicy,
    project_business_context_for_prompt,
    project_policy_refs_for_prompt,
    project_tool_result_summary,
    project_working_state_for_prompt,
)
from src.agent.working_state import WorkingStateV1


SHOULD_NOT_APPEAR_RAW_TOOL_DATA = "SHOULD_NOT_APPEAR_RAW_TOOL_DATA"
SHOULD_NOT_APPEAR_FULL_POLICY_TEXT = "SHOULD_NOT_APPEAR_FULL_POLICY_TEXT"
SHOULD_NOT_APPEAR_APPROVAL_BODY = "SHOULD_NOT_APPEAR_APPROVAL_BODY"
SHOULD_NOT_APPEAR_ACTION_AUTHORITY_BODY = "SHOULD_NOT_APPEAR_ACTION_AUTHORITY_BODY"
SHOULD_NOT_APPEAR_NESTED_REPR = "{'nested': ['RAW']}"


def _prompt_text(assembly) -> str:
    return "\n".join(message["content"] for message in assembly.to_messages())


def _working_state() -> WorkingStateV1:
    return WorkingStateV1(
        thread_id="thread-1",
        run_id="run-1",
        turn_id="turn-1",
        current_goal="resolve refund dispute",
        current_intent="refund_help",
        active_slots={"order_id": "ORD-1001"},
        open_questions=["confirm delivered status"],
        constraints=["high risk action requires approval"],
        business_context_refs=[
            {
                "source_system": "orders",
                "resource_type": "order",
                "resource_id": "ORD-1001",
                "summary": "Delivered order referenced by current refund dispute.",
                "raw": SHOULD_NOT_APPEAR_NESTED_REPR,
            }
        ],
        recent_tool_results=[
            {
                "tool_call_id": "tool-call-1",
                "tool_result_id": "tool-result-1",
                "tool_name": "get_order",
                "status": "success",
                "summary": "Order ORD-1001 is delivered.",
                "prompt_summary": "Order ORD-1001 delivered; refund case RF-2001 open.",
                "business_fact_refs": [{"resource_type": "order", "resource_id": "ORD-1001"}],
                "policy_evidence_refs": [{"evidence_id": "policy-refund:v1:chunk-1"}],
                "raw_result_ref": "tool-results/tool-result-1",
                "audit_ref": "audit/tool-result-1",
            }
        ],
    )


def test_context_assembler_builds_explicit_prompt_blocks():
    assembly = ContextAssembler(TokenBudgetPolicy(max_chars=4000)).assemble(
        system_prompt="You are a merchant operations agent.",
        current_user_message="Can we refund ORD-1001?",
        working_state=_working_state(),
        thread_rolling_summary="Earlier: user disputed refund RF-2001.",
        recent_messages=[
            {"role": "user", "content": "I need help with ORD-1001."},
            {"role": "assistant", "content": "I will inspect the order and rules."},
        ],
        verified_policy_snippets=[
            {
                "evidence_id": "policy-refund:v1:chunk-1",
                "doc_key": "refund_policy",
                "section": "refund timeout",
                "text": "Delivered orders require policy evidence and approval for high-risk refunds.",
            }
        ],
        tool_result_summaries=_working_state().recent_tool_results,
    )

    block_names = [block.name for block in assembly.blocks]
    prompt = _prompt_text(assembly)

    assert block_names[0] == "system_prompt"
    assert "working_state" in block_names
    assert "thread_rolling_summary" in block_names
    assert "recent_messages" in block_names
    assert "policy_refs" in block_names
    assert "tool_summaries" in block_names
    assert block_names[-1] == "current_user_message"
    assert "ORD-1001" in prompt
    assert "policy-refund:v1:chunk-1" in prompt
    assert "Order ORD-1001 delivered" in prompt


def test_context_assembler_excludes_raw_tool_business_policy_and_authority_payloads():
    assembly = ContextAssembler(TokenBudgetPolicy(max_chars=4000)).assemble(
        system_prompt="System prompt",
        current_user_message="Current user question",
        working_state=_working_state(),
        thread_rolling_summary="Safe rolling summary",
        recent_messages=[
            {
                "role": "tool",
                "content": "summary only",
                "raw_tool_output": SHOULD_NOT_APPEAR_RAW_TOOL_DATA,
            }
        ],
        verified_policy_snippets=[
            {
                "evidence_id": "policy-refund:v1:chunk-1",
                "doc_key": "refund_policy",
                "section": "refund timeout",
                "text": "Allowed policy excerpt.",
                "full_text": SHOULD_NOT_APPEAR_FULL_POLICY_TEXT,
                "approval_authority_body": SHOULD_NOT_APPEAR_APPROVAL_BODY,
            }
        ],
        tool_result_summaries=[
            {
                "tool_call_id": "tool-call-raw",
                "tool_result_id": "tool-result-raw",
                "tool_name": "get_order",
                "status": "success",
                "summary": "Safe summary",
                "prompt_summary": "Safe tool prompt summary",
                "business_fact_refs": [{"resource_type": "order", "resource_id": "ORD-1001"}],
                "policy_evidence_refs": [],
                "raw_result_ref": "opaque/ref",
                "audit_ref": "audit/ref",
                "data": {
                    "secret": SHOULD_NOT_APPEAR_RAW_TOOL_DATA,
                    "approval_authority_body": SHOULD_NOT_APPEAR_APPROVAL_BODY,
                    "action_authority_body": SHOULD_NOT_APPEAR_ACTION_AUTHORITY_BODY,
                },
            }
        ],
        business_context={
            "order": {
                "order_id": "ORD-1001",
                "raw_payload": SHOULD_NOT_APPEAR_RAW_TOOL_DATA,
                "approval_authority_body": SHOULD_NOT_APPEAR_APPROVAL_BODY,
            },
            "facts": {"nested": ["RAW"]},
        },
    )

    prompt = _prompt_text(assembly)

    assert "Safe tool prompt summary" in prompt
    assert "Allowed policy excerpt" in prompt
    assert SHOULD_NOT_APPEAR_RAW_TOOL_DATA not in prompt
    assert SHOULD_NOT_APPEAR_FULL_POLICY_TEXT not in prompt
    assert SHOULD_NOT_APPEAR_APPROVAL_BODY not in prompt
    assert SHOULD_NOT_APPEAR_ACTION_AUTHORITY_BODY not in prompt
    assert SHOULD_NOT_APPEAR_NESTED_REPR not in prompt


def test_context_assembler_does_not_stringify_unprojected_dicts():
    nested = {"nested": ["RAW"]}

    assembly = ContextAssembler(TokenBudgetPolicy(max_chars=3000)).assemble(
        system_prompt="System prompt",
        current_user_message="Current user question",
        working_state=_working_state(),
        thread_rolling_summary="Safe rolling summary",
        recent_messages=[{"role": "user", "content": "safe recent message", "metadata": nested}],
        verified_policy_snippets=[],
        tool_result_summaries=[],
        business_context={"facts": nested},
    )

    prompt = _prompt_text(assembly)

    assert "safe recent message" in prompt
    assert SHOULD_NOT_APPEAR_NESTED_REPR not in prompt
    assert "RAW" not in prompt


def test_context_exports_prompt_projectors():
    assert PromptAssembly
    assert callable(project_business_context_for_prompt)
    assert callable(project_policy_refs_for_prompt)
    assert callable(project_tool_result_summary)
    assert callable(project_working_state_for_prompt)
