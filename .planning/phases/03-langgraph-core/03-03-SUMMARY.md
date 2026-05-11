---
phase: 03-langgraph-core
plan: "03"
subsystem: agent
tags: [langgraph, stategraph, agent-nodes, rag, risk-rules, citations]

requires:
  - phase: 03-langgraph-core
    provides: "Plan 03-02 AgentState, structured schemas, prompts, and read-only tool wrappers"
  - phase: 02-rag-pipeline
    provides: "Retriever output schema and citation validator for evidence-grounded recommendations"
provides:
  - "Eight async LangGraph node implementations for the read-only refund agent happy path"
  - "rules/risk_rules.yaml with low, medium, and high risk tiers"
  - "build_graph(checkpointer) StateGraph assembly with fixed routing and retry policy"
  - "Evidence gate that skips recommendation LLM calls when retrieval has no usable evidence"
affects: [03-langgraph-core, agent-api, trace-persistence, approval-workflow, testing]

tech-stack:
  added: []
  patterns:
    - "Request-scoped DB sessions are read from RunnableConfig configurable state inside tool-calling nodes."
    - "LLM-facing nodes use structured output, two in-node attempts, safe fallback dictionaries, and LangGraph RetryPolicy(max_attempts=2)."
    - "Citation validation converts retrieved evidence dictionaries into RetrievalResult before filtering generated evidence refs."

key-files:
  created:
    - rules/risk_rules.yaml
    - src/agent/nodes/__init__.py
    - src/agent/nodes/receive_request.py
    - src/agent/nodes/classify_intent.py
    - src/agent/nodes/extract_slots.py
    - src/agent/nodes/load_business_context.py
    - src/agent/nodes/retrieve_policy_evidence.py
    - src/agent/nodes/generate_recommendation.py
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/final_response.py
    - src/agent/graph.py
  modified: []

key-decisions:
  - "Risk rules are loaded from rules/risk_rules.yaml at assessment time, with deterministic high-risk overrides applied after the LLM result."
  - "No-evidence retrieval sets recommendation_draft.recommended_action to insufficient_evidence before generate_recommendation, so that node skips its LLM call."
  - "LLM provider failures are converted to structured node_errors and safe fallbacks inside nodes instead of relying only on graph-level retries."

patterns-established:
  - "Each graph node is async def and returns a partial AgentState update dictionary."
  - "Trace steps append node, status, timestamps, tool names or model name, and token placeholders without exposing prompts or raw tool outputs."
  - "Phase 3 graph routing remains linear and deterministic; no conditional edges are used before the approval phase."

requirements-completed: [AGNT-01, AGNT-02, AGNT-05, AGNT-08, INFR-09]

duration: 7m
completed: 2026-05-11
---

# Phase 03 Plan 03: LangGraph Nodes and Graph Assembly Summary

**Eight-node LangGraph refund agent path with evidence gating, citation validation, configurable risk rules, and fixed StateGraph routing**

## Performance

- **Duration:** 7m
- **Started:** 2026-05-11T08:00:23Z
- **Completed:** 2026-05-11T08:07:46Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Added all eight async agent nodes: request reset, intent classification, slot extraction, business context loading, policy retrieval, recommendation generation, risk assessment, and final response.
- Added `rules/risk_rules.yaml` and risk assessment logic that loads those rules instead of hardcoding the risk table.
- Implemented the no-evidence gate so `generate_recommendation` skips LLM generation when retrieval lacks usable evidence.
- Added citation validation before returning recommendation drafts, stripping fabricated chunk citations and degrading to `citation_invalid` when none remain.
- Assembled `build_graph(checkpointer)` with all eight nodes, fixed edges, and `RetryPolicy(max_attempts=2)` on LLM-facing nodes.

## Task Commits

Each planned task was committed atomically:

1. **Task 1: risk_rules.yaml + 8 node implementations** - `3ced4b9` (feat)
2. **Task 2: Graph assembly (graph.py)** - `65f1f97` (feat)

Additional deviation fix:

- **Rule 2 hardening:** `fcd5e85` (fix)

## Files Created/Modified

- `rules/risk_rules.yaml` - Configures low, medium, and high risk rules.
- `src/agent/nodes/receive_request.py` - Resets all ephemeral state fields and starts the per-run trace.
- `src/agent/nodes/classify_intent.py` - Uses structured LLM output to set current and last intent.
- `src/agent/nodes/extract_slots.py` - Extracts identifiers and merges them into persistent active slots.
- `src/agent/nodes/load_business_context.py` - Loads order, refund case, and ticket data through read-only tools using the injected session.
- `src/agent/nodes/retrieve_policy_evidence.py` - Searches policy evidence and applies the insufficient-evidence gate.
- `src/agent/nodes/generate_recommendation.py` - Generates recommendation drafts and validates evidence citations.
- `src/agent/nodes/assess_risk_and_approval.py` - Produces risk assessments with YAML-backed deterministic overrides.
- `src/agent/nodes/final_response.py` - Produces final Chinese responses or safe fallback text.
- `src/agent/graph.py` - Builds and compiles the fixed LangGraph StateGraph.
- `src/agent/nodes/__init__.py` - Initializes the node package.

## Decisions Made

- `retrieve_policy_evidence` stores the full tool wrapper result in state so downstream code can preserve tool status and evidence data together.
- `assess_risk_and_approval` short-circuits insufficient-evidence drafts to low risk because no action is recommended.
- LLM token counts are recorded as `None` placeholders until Plan 04 trace persistence defines the callback/usage extraction path.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... all 8 nodes are async OK"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... graph.py OK"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... graph assembly OK"` - passed, with a non-failing LangGraph checkpointer deprecation warning from the installed package.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 50 tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added in-node fallbacks for LLM provider failures**
- **Found during:** Post-task threat model scan for T-03-08.
- **Issue:** The planned retry examples focused on validation failures. Timeout or provider errors could still propagate after graph retries and fail the run without a structured fallback.
- **Fix:** Updated LLM-facing nodes to catch provider/timeout failures after two in-node attempts and return safe fallback state with `node_errors`.
- **Files modified:** `src/agent/nodes/classify_intent.py`, `src/agent/nodes/extract_slots.py`, `src/agent/nodes/generate_recommendation.py`, `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/final_response.py`
- **Verification:** Graph assembly import passed, ruff passed, full pytest passed.
- **Committed in:** `fcd5e85`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Correctness and graceful-degradation hardening only; no graph scope expansion.

## Issues Encountered

- `git add` for `graph.py` initially failed to create `.git/index.lock` inside the sandbox; rerunning the same staging command with the approved git escalation succeeded. No code changes were affected.

## Known Stubs

None. Stub scan found local empty containers and `last_error = None` initialization only; no placeholder data flow or mock UI output was introduced.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03-04 can wire the compiled graph into FastAPI lifespan, pass `config["configurable"]["session"]` for tool nodes, and persist `trace_steps`, `tool_results`, `evidence_refs`, `risk_assessment`, and `final_response` to `agent_runs` and `agent_steps`.

## Self-Check: PASSED

- Found `.planning/phases/03-langgraph-core/03-03-SUMMARY.md`.
- Found `rules/risk_rules.yaml`.
- Found `src/agent/graph.py`.
- Found representative node files: `receive_request.py`, `retrieve_policy_evidence.py`, and `generate_recommendation.py`.
- Found task commit `3ced4b9`.
- Found task commit `65f1f97`.
- Found deviation fix commit `fcd5e85`.

---
*Phase: 03-langgraph-core*
*Completed: 2026-05-11*
