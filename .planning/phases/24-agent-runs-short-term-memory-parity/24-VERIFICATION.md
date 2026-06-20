---
phase: 24-agent-runs-short-term-memory-parity
phase_number: 24
status: passed
requirements:
  - STM-01
  - STM-02
  - STM-03
  - STM-04
  - STM-05
  - STM-06
  - STM-07
  - STM-08
  - STM-09
  - STM-10
  - STM-11
  - STM-12
  - STM-13
  - STM-14
created: 2026-06-20
---

# Phase 24 Verification

## Result

Phase 24 passed verification. The `/api/v1/agent-runs + SSE` path now persists and consumes the short-term memory surfaces required for same-thread follow-up turns: conversation messages, prompt-safe tool summaries, rolling thread summaries, and PostgreSQL-backed session slots.

## Requirement Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| STM-01 | Passed | `test_create_agent_run_persists_exactly_one_user_message`; `ConversationService.append_or_get_user_message_for_run` in `create_agent_run`. |
| STM-02 | Passed | `test_agent_run_stream_passes_conversation_ids_to_graph_and_tools`; SSE config includes trusted `conversation_thread_id` and `conversation_message_id`. |
| STM-03 | Passed | `test_completed_agent_run_persists_exactly_one_assistant_message`; `finalize_completed_agent_run_memory`. |
| STM-04 | Passed | `test_completed_agent_run_updates_thread_summary_idempotently`; `ThreadRollingSummaryService.persist_thread_summary`. |
| STM-05 | Passed | `test_extract_slots_loads_agent_runs_prompt_context_from_trusted_config`; `test_agent_runs_prompt_context_loads_prior_summary_recent_messages_and_tool_summaries`. |
| STM-06 | Passed | Session memory integration tests for same-thread inheritance, explicit override, and wrong-scope fail-closed behavior. |
| STM-07 | Passed | Prompt-safety projector and assembler tests exclude raw/private/authority/debug/secret markers. |
| STM-08 | Passed | `test_agent_chat_only_token_invokes_legacy_chat_with_no_tool_permissions` verifies legacy successful-path compatibility. |
| STM-09 | Passed | `test_agent_run_error_cancel_interrupted_do_not_write_completed_memory`. |
| STM-10 | Passed | `test_duplicate_sse_stream_does_not_duplicate_memory_surfaces`. |
| STM-11 | Passed | `test_sse_final_response_after_bounded_memory_persistence_result` and lifecycle final-response ordering coverage. |
| STM-12 | Passed | `test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority` and authority-boundary tests. |
| STM-13 | Passed | Focused Phase 24 regression command completed with `91 passed, 9 warnings`. |
| STM-14 | Passed | `test_three_turn_agent_runs_smoke_uses_slots_and_summary_context` exercises three completed `/agent-runs + SSE` turns with slot continuity, rolling-summary context, prompt-safe tool summaries, and authority-boundary assertions. |

## Automated Verification

- `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q` - `91 passed, 9 warnings`.
- `uv run ruff check src/ tests/` - passed.
- `gsd-sdk query verify.schema-drift 24` - `valid: true`, no issues.

## Human Verification

No mandatory human verification remains. Browser Agent Console sanity is optional because Phase 24 scope is backend persistence and prompt-context parity, and the provider-free ASGI/SSE three-turn smoke covers STM-14.

## Warnings

- LangGraph emitted existing deprecation/config annotation warnings during tests. These are non-blocking and do not indicate Phase 24 behavioral failure.
- `.planning/LOCAL-VALIDATION-ISSUES.md` records repeated GSD state writer drift to `v1.0`; this is tooling bookkeeping drift, not a Phase 24 product failure.

## Conclusion

Phase 24 achieved its roadmap goal and all STM-01 through STM-14 requirements are accounted for.
