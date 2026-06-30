---
phase: 24-agent-runs-short-term-memory-parity
plan: 08
subsystem: agent-runs-prompt-context
tags: [agent-runs, short-term-memory, prompt-context, slot-extraction, authority-boundary]

requires:
  - phase: 24-agent-runs-short-term-memory-parity
    provides: Completed-run memory finalizer and terminal side-effect guards
provides:
  - Safe prior conversation context for slot extraction
  - Prompt sanitization for summaries, recent messages, and tool summaries
  - Node-level trusted config coverage for agent-runs prompt context
affects: [extract-slots, context-assembler, context-projectors, session-memory-tests]

tech-stack:
  added: []
  patterns: [trusted LangGraph config, ConversationService prompt context, prompt-safe projection boundary]

key-files:
  created: []
  modified:
    - src/agent/nodes/extract_slots.py
    - src/agent/context/assembler.py
    - src/agent/context/projectors.py
    - tests/agent/test_session_memory_integration.py

key-decisions:
  - "Load prior conversation context only from trusted LangGraph configurable values plus tenant/user/thread/run state."
  - "Keep recent messages, rolling summaries, and tool summaries contextual; they do not become slot, policy, business, approval, action, replay, or audit authority."
  - "Sanitize prompt context at projector/assembler boundaries instead of stringifying raw rows or tool payloads."

patterns-established:
  - "extract_slots accepts RunnableConfig and fails closed to empty context when trusted conversation config or services are unavailable."
  - "Prompt summaries are converted to ToolResultPromptSummary before ContextAssembler receives them."
  - "Thread summaries and prompt scalar refs are scrubbed for raw/private/debug/secret/replay markers."

requirements-completed:
  - STM-05
  - STM-06
  - STM-07
  - STM-12
  - STM-13

duration: 18 min
completed: 2026-06-20
---

# Phase 24 Plan 08: Prompt Context Parity Summary

**Follow-up slot extraction can now use safe same-thread prompt context**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-20T14:56:00Z
- **Completed:** 2026-06-20T15:14:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Updated `extract_slots` to accept LangGraph `RunnableConfig` and load prompt context through `ConversationService.load_prompt_context`.
- Passed trusted tenant/user/thread/run identity into context loading while requiring trusted `conversation_thread_id` and `conversation_message_id` from `config["configurable"]`.
- Preserved fail-closed behavior when context services or trusted conversation config are absent.
- Added node-level integration coverage proving `ContextAssembler` receives the latest summary, recent messages, prompt-safe tool summaries, and the protected current user message.
- Hardened prompt projection so raw/private/debug/secret/replay markers do not leak from summaries, recent messages, or tool prompt refs.

## Task Commits

Each task was committed atomically:

1. **Task 1: Load safe prior conversation context into slot extraction** - `b47eae0` (feature/test)
2. **Task 2: Preserve session slot override and fail-closed semantics** - `b47eae0` (feature/test)
3. **Task 3: Enforce prompt-safety and authority boundaries** - `b47eae0` (feature/test)

## Files Created/Modified

- `src/agent/nodes/extract_slots.py` - Adds trusted prompt-context loading for slot extraction.
- `src/agent/context/assembler.py` - Sanitizes thread rolling summary before prompt assembly.
- `src/agent/context/projectors.py` - Centralizes prompt-context text scrubbing and safer scalar projection.
- `tests/agent/test_session_memory_integration.py` - Adds trusted-config node-level prompt-context coverage.

## Decisions Made

- Did not read conversation identity from user payload, query parameters, LLM output, or untrusted state fields.
- Did not treat prior message or summary text as trusted slot authority; session-slot metadata remains the slot-continuity gate.
- Did not add a raw prompt builder; context still flows through `ContextAssembler` and projector helpers.

## Deviations from Plan

- Added focused production hardening in `src/agent/context/assembler.py` and `src/agent/context/projectors.py` after the prompt-safety regression test exposed summary and evidence-ref marker leakage.

## Issues Encountered

- Focused prompt-safety verification initially showed `raw_payload` and `EvidenceRefV1` markers could reach assembled prompt text through summary/ref projection. The projector/assembler sanitization fix is recorded in `.planning/LOCAL-VALIDATION-ISSUES.md` issue #16.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run ruff check src/agent/nodes/extract_slots.py src/agent/context/assembler.py src/agent/context/projectors.py tests/conversation/test_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py` - passed.
- `uv run pytest tests/conversation/test_service.py::test_agent_runs_prompt_context_loads_prior_summary_recent_messages_and_tool_summaries tests/agent/test_session_memory_integration.py::test_extract_slots_loads_agent_runs_prompt_context_from_trusted_config tests/agent/test_session_memory_integration.py::test_agent_runs_session_slots_explicit_current_turn_overrides_inherited tests/agent/test_session_memory_integration.py::test_agent_runs_session_memory_wrong_scope_fails_closed tests/agent/context/test_assembler.py::test_agent_runs_prompt_context_excludes_raw_tool_private_authority_and_debug_fields tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority tests/agent/test_required_slots.py -q` - passed with `13 passed, 2 warnings`.

## Next Phase Readiness

Plan 24-09 can now run the end-to-end agent-runs smoke over completed memory, prompt context loading, and final SSE response behavior.

---
*Phase: 24-agent-runs-short-term-memory-parity*
*Completed: 2026-06-20*
