---
phase: 03-langgraph-core
plan: "02"
subsystem: agent
tags: [langgraph, agent-state, pydantic, rag, tools, tenant-scoping]

requires:
  - phase: 03-langgraph-core
    provides: "Plan 03-01 dependency, configuration, and trace table foundation"
  - phase: 02-rag-pipeline
    provides: "Retriever, evidence schemas, embedding service, and policy chunk repository"
provides:
  - "AgentState TypedDict contract with persistent and ephemeral state fields"
  - "Pydantic structured output schemas for intent, slot extraction, recommendations, risk, and final responses"
  - "Static English system prompts for all LLM-facing agent contract steps"
  - "Read-only tenant-scoped tool wrappers for order, refund case, ticket, and policy search"
affects: [03-langgraph-core, agent-nodes, agent-tools, rag-evidence, safety]

tech-stack:
  added: []
  patterns:
    - "Agent contracts live under src/agent and are imported by downstream graph nodes"
    - "Tools return D-08d {status, data, error} dictionaries and convert expected failures into structured errors"
    - "Tool wrappers pass tenant_id into repository calls and omit full ticket message history"

key-files:
  created:
    - src/agent/__init__.py
    - src/agent/state.py
    - src/agent/schemas.py
    - src/agent/prompts.py
    - src/agent/tools/__init__.py
    - src/agent/tools/get_order.py
    - src/agent/tools/get_refund_case.py
    - src/agent/tools/get_ticket.py
    - src/agent/tools/search_policy.py
  modified: []

key-decisions:
  - "Tool wrappers validate UUID-shaped tenant/resource IDs before repository access and return VALIDATION_ERROR for malformed IDs."
  - "Ticket tool output intentionally includes only ticket_no, status, channel, and summary; messages are excluded as PII-bearing conversation history."

patterns-established:
  - "Use total=False TypedDict state so graph invocations can construct partial state incrementally."
  - "Use static system prompt constants in prompts.py; dynamic user/business/evidence content belongs in downstream node messages."
  - "Use repository-layer tenant scoping for read tools and preserve not-found responses instead of exposing tenant existence."

requirements-completed: [AGNT-03, AGNT-04, RAG-05, SAFE-08]

duration: 4m
completed: 2026-05-11
---

# Phase 03 Plan 02: Agent Contracts and Read-Only Tools Summary

**Agent state, structured LLM outputs, static prompts, and tenant-scoped read-only tool wrappers for the LangGraph happy path**

## Performance

- **Duration:** 4m
- **Started:** 2026-05-11T07:52:05Z
- **Completed:** 2026-05-11T07:56:27Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Created `AgentState` with persistent memory fields and per-turn ephemeral context fields required by D-07.
- Added structured Pydantic output models for intent classification, slot extraction, recommendation drafting, risk assessment, and final response generation.
- Added fixed English system prompts with Chinese examples/output rules where required.
- Added four read-only tool wrappers that use tenant-scoped repository/retriever calls and return D-08d-compatible response dictionaries.

## Task Commits

Each task was committed atomically:

1. **Task 1: AgentState TypedDict + Pydantic output schemas + system prompts** - `226b31b` (feat)
2. **Task 2: 4 read-only tool wrappers** - `63e018d` (feat)

## Files Created/Modified

- `src/agent/__init__.py` - Initializes the agent package.
- `src/agent/state.py` - Defines `AgentState` and supporting TypedDict contracts for persistent and ephemeral fields.
- `src/agent/schemas.py` - Defines structured output schemas: `IntentResult`, `SlotExtractionResult`, `RecommendationDraft`, `RiskAssessment`, and `FinalResponseOutput`.
- `src/agent/prompts.py` - Stores static English system prompt constants and the Chinese insufficient-evidence fallback text.
- `src/agent/tools/__init__.py` - Initializes the agent tools package.
- `src/agent/tools/get_order.py` - Wraps `OrderRepository.get_with_hints()` with structured success/error output.
- `src/agent/tools/get_refund_case.py` - Wraps `RefundRepository.get_by_case_no()` with structured success/error output.
- `src/agent/tools/get_ticket.py` - Wraps `TicketRepository.get_by_id()` while excluding `messages`.
- `src/agent/tools/search_policy.py` - Wraps `Retriever.search()` using `EmbeddingService` and `PolicyChunkRepository`.

## Decisions Made

- Tool wrappers return `VALIDATION_ERROR` for malformed UUID inputs instead of collapsing validation failures into generic DB/search errors.
- `get_ticket` does not reference or serialize `Ticket.messages`, preserving the D-05e/D-08 information disclosure boundary.
- Relation hint UUIDs from `get_order` are converted to strings so tool output remains JSON-serializable.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.agent.state import AgentState; from src.agent.schemas import IntentResult, RecommendationDraft, FinalResponseOutput; from src.agent.prompts import CLASSIFY_INTENT_SYSTEM, INSUFFICIENT_EVIDENCE_RESPONSE; print('contracts OK')"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.agent.schemas import IntentResult; IntentResult(intent='policy_qa', confidence=0.9, reasoning='test')"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.agent.schemas import RecommendationDraft"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.agent.tools.get_order import get_order; from src.agent.tools.get_refund_case import get_refund_case; from src.agent.tools.get_ticket import get_ticket; from src.agent.tools.search_policy import search_policy; print('tools OK')"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... print('all agent contracts OK')"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent` - passed.
- `rg -n "messages" src/agent/tools/get_ticket.py` - no matches.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 50 tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added explicit UUID validation errors**
- **Found during:** Task 2 (read-only tool wrappers)
- **Issue:** The plan required tenant/resource scoping but did not specify how malformed UUID inputs should be handled. Letting `UUID(...)` exceptions fall through would produce generic DB/search errors and reduce caller clarity.
- **Fix:** Added structured `VALIDATION_ERROR` returns for malformed `tenant_id`, `ticket_id`, or other UUID inputs before repository access.
- **Files modified:** `src/agent/tools/get_order.py`, `src/agent/tools/get_refund_case.py`, `src/agent/tools/get_ticket.py`, `src/agent/tools/search_policy.py`
- **Verification:** Tool imports passed, ruff passed, full pytest passed.
- **Committed in:** `63e018d`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Security/correctness hardening only; no API scope expansion.

## Issues Encountered

None.

## Known Stubs

None. Stub scan found optional schema defaults and optional tool filters only; no placeholder data flow or UI-facing mock values were introduced.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03-03 can import `AgentState`, the structured output schemas, prompt constants, and all four read-only tools to implement graph nodes without inventing field names or response shapes.

## Self-Check: PASSED

- Found `.planning/phases/03-langgraph-core/03-02-SUMMARY.md`.
- Found `src/agent/state.py`.
- Found `src/agent/tools/search_policy.py`.
- Found task commit `226b31b`.
- Found task commit `63e018d`.

---
*Phase: 03-langgraph-core*
*Completed: 2026-05-11*
