---
phase: 03-langgraph-core
verified: 2026-05-11T08:51:40Z
status: gaps_found
score: 5/7 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Execution trace records all graph nodes traversed, tool calls made, and evidence referenced; trace is queryable by run_id"
    status: partial
    reason: "AgentRun/AgentStep persistence writes rows, but AgentStep rows do not persist tools_called lists or referenced evidence because write_agent_steps only reads step.tool_name and step.evidence_refs, while node trace steps populate tools_called and never populate evidence_refs."
    artifacts:
      - path: "src/agent/trace.py"
        issue: "write_agent_steps ignores step['tools_called']; evidence_refs remains None for persisted steps."
      - path: "src/agent/nodes/retrieve_policy_evidence.py"
        issue: "Trace step records tools_called=['search_policy'] but no evidence_refs."
      - path: "src/agent/nodes/load_business_context.py"
        issue: "Trace step records tools_called list, which is visible to build_trace_summary but not persisted to AgentStep.tool_name/tool_input_summary/tool_output_summary."
    missing:
      - "Persist tool call names from tools_called into AgentStep rows, or add a JSONB tools_called field and migration."
      - "Attach referenced evidence refs to trace steps so persisted AgentStep.evidence_refs is queryable by run_id."
  - truth: "Same-thread conversation remembers order_id, refund_case_id, and previously retrieved evidence via LangGraph checkpointer"
    status: partial
    reason: "Same-thread slots are retained through active_slots, but previously retrieved evidence is not copied into persistent AgentState.evidence_refs. retrieved_evidence is explicitly reset by receive_request each turn, and no node updates evidence_refs."
    artifacts:
      - path: "src/agent/state.py"
        issue: "Persistent evidence_refs field is declared."
      - path: "src/agent/nodes/receive_request.py"
        issue: "retrieved_evidence is reset each turn, which is correct for ephemeral state."
      - path: "src/agent/nodes/retrieve_policy_evidence.py"
        issue: "Retrieved evidence is stored only in retrieved_evidence for the current turn; no persistent evidence_refs update."
      - path: "src/agent/nodes/generate_recommendation.py"
        issue: "Validated recommendation evidence_refs are returned in recommendation_draft but not saved to persistent evidence_refs."
    missing:
      - "Update persistent evidence_refs after successful retrieval or citation-validated recommendation."
      - "Add same-thread test proving evidence_refs survives a second turn in the same thread."
---

# Phase 3: LangGraph Core Verification Report

**Phase Goal:** Submit a refund question and receive an evidence-cited answer with full execution trace, tool calls, and same-thread memory — the complete read-only happy path without approval interruption.
**Verified:** 2026-05-11T08:51:40Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Refund question happy path identifies intent, loads read-only business context when slots are present, retrieves policy evidence, validates citations, and returns a structured evidence-cited response. | VERIFIED | `build_graph()` wires the 8-node path in `src/agent/graph.py:31-54`; tools are called from `load_business_context` and `retrieve_policy_evidence`; citation validation runs before recommendation output in `src/agent/nodes/generate_recommendation.py:106-117`. `tests/agent/test_graph.py:163-188` covers policy QA and refund troubleshooting happy paths. |
| 2 | Execution trace records nodes, tool calls, and evidence references and is queryable by run_id. | FAILED | Nodes are persisted as AgentStep rows via `src/api/routers/agent.py:92-108`, but `write_agent_steps()` only persists `tool_name` and `evidence_refs` fields from trace steps. Nodes use `tools_called` lists and do not populate evidence refs, so DB trace rows lose tool/evidence details. |
| 3 | Same-thread memory remembers order/refund/ticket slots and previously retrieved evidence via checkpointer. | FAILED | `active_slots` persists and is merged in `extract_slots`, but persistent `evidence_refs` is declared only in `src/agent/state.py:52`; no production code writes it. `retrieved_evidence` is reset in `receive_request` and remains per-turn only. |
| 4 | Insufficient evidence refuses definitive conclusions and returns missing_info. | VERIFIED | `retrieve_policy_evidence` creates an `insufficient_evidence` draft with `missing_info` on no/low evidence; `final_response` uses the insufficient-evidence fallback. Covered by `tests/agent/test_graph.py:191-205` and `tests/agent/test_nodes/test_retrieve_policy_evidence.py`. |
| 5 | LLM/DB/tool timeout or provider failure degrades to structured errors instead of crashing. | VERIFIED | LLM nodes catch validation/timeout/provider exceptions; tools wrap DB/search timeouts into `{status,error}`; API graph failure path returns structured fallback and attempts AgentRun persistence. Covered by `tests/agent/test_tools/test_get_order.py:69-77` and retrieval error tests. |
| 6 | FastAPI exposes authenticated `POST /api/v1/agent/chat` and initializes AsyncPostgresSaver once in lifespan. | VERIFIED | `src/api/routers/agent.py:24-30` enforces `agent:chat`; `src/api/main.py:28-34` initializes `AsyncPostgresSaver`, calls `setup()`, and stores the compiled graph. |
| 7 | Read-only tool wrappers enforce tenant/user/role authorization and avoid approval interruption in Phase 3. | VERIFIED | Business tools include tenant scoping and merchant access checks in `src/agent/tools/authz.py` and wrapper files; no `interrupt()` usage exists in Phase 3 graph. Review fix commit `1f9aa9b` added regression tests for same-tenant merchant denial. |

**Score:** 5/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `pyproject.toml`, `src/config.py`, `src/db/models.py`, `003_agent_tables.py` | LangGraph deps, LLM/checkpointer config, AgentRun/AgentStep schema | VERIFIED | `gsd-sdk verify.artifacts` passed for Plan 01; schema drift check valid. Manual check confirmed `AgentStep.run_id -> agent_runs.id`. |
| `src/agent/state.py`, `schemas.py`, `prompts.py`, `tools/*` | Agent contracts and read-only tools | VERIFIED | Artifacts pass; tool wrappers return `{status,data,error}` and enforce tenant/merchant access. |
| `src/agent/nodes/*`, `src/agent/graph.py`, `rules/risk_rules.yaml` | 8 async nodes, evidence gate, risk rules, graph assembly | VERIFIED | All 8 graph nodes are wired; evidence gate and citation validator are present; risk rules are YAML-backed. |
| `src/agent/trace.py`, `src/api/routers/agent.py`, `src/api/schemas/agent.py`, `src/api/main.py` | API, trace persistence, lifespan | PARTIAL | API and lifespan work. Trace persistence exists but does not persist tools_called/evidence_refs details needed by the phase goal. |
| `tests/agent/**`, `scripts/smoke_agent_live.py`, `evals/golden_set_phase3.json` | CI-safe tests, smoke script, 15-case golden set | VERIFIED | 31 agent tests pass; full suite has 81 passing tests; golden set has 15 cases. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Agent API | LangGraph graph | `request.app.state.agent_graph.ainvoke()` | VERIFIED | `src/api/routers/agent.py:32-52` |
| Agent API | Trace persistence | `write_agent_run()` + `write_agent_steps()` | PARTIAL | Rows are written, but persisted step content omits tools_called/evidence_refs. |
| Graph | Checkpointer | `builder.compile(checkpointer=checkpointer)` | VERIFIED | `src/agent/graph.py:54` |
| Nodes | Read tools/RAG | Deterministic node calls | VERIFIED | `load_business_context` and `retrieve_policy_evidence` call wrappers directly. |
| Recommendation | Citation validator | `validate_citations()` | VERIFIED | Invalid cited chunk IDs are stripped before final response. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/agent/nodes/retrieve_policy_evidence.py` | `retrieved_evidence` | `search_policy()` -> `Retriever.search()` | Yes | VERIFIED for current-turn evidence. |
| `src/agent/nodes/generate_recommendation.py` | `recommendation_draft.evidence_refs` | LLM structured output filtered by `validate_citations()` | Yes | VERIFIED for response citations. |
| `src/agent/state.py` | persistent `evidence_refs` | No writer found | No | HOLLOW — declared memory field is disconnected. |
| `src/agent/trace.py` | `AgentStep.tool_name`, `AgentStep.evidence_refs` | `trace_steps` | Partial | HOLLOW — source steps contain `tools_called` but persistence ignores it; no source step has evidence refs. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Agent test suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/ -q --tb=short -m "not live"` | 31 passed, 1 LangGraph warning | PASS |
| Phase lint | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent scripts/smoke_agent_live.py tests/agent` | All checks passed | PASS |
| Full test suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` | 81 passed, 1 LangGraph warning | PASS |
| Schema drift | `gsd-sdk query verify.schema-drift "03"` | `valid: true`, no issues | PASS |
| Graph/config import | `uv run python` import/build check | checkpointer URL is psycopg style; graph compiles to `CompiledStateGraph` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| AGNT-01 | 03-03, 03-05 | Intent recognition and routing | SATISFIED | `classify_intent` structured schema and graph tests cover policy/refund intents. |
| AGNT-02 | 03-01, 03-03, 03-04, 03-05 | LangGraph happy path state machine | SATISFIED | 8-node fixed graph exists and tests traverse all 8 nodes. |
| AGNT-03 | 03-02, 03-05 | Structured tools for order/refund/ticket | SATISFIED | Tool wrappers exist; tests cover order/refund/ticket paths. |
| AGNT-04 | 03-02, 03-05 | Knowledge retrieval with doc/chunk citation | SATISFIED | `search_policy` wraps Retriever and `generate_recommendation` validates citations. |
| AGNT-05 | 03-01, 03-03 | Same-thread context memory | PARTIAL | Slots persist; previously retrieved evidence does not persist to `evidence_refs`. |
| AGNT-06 | 03-01, 03-04, 03-05 | Structured execution trace | PARTIAL | API trace summary is present; DB trace rows omit tool/evidence details. |
| AGNT-08 | 03-03, 03-05 | Refuse definitive conclusions when evidence is insufficient | SATISFIED | Evidence gate + fallback response tests. |
| INFR-09 | 03-01, 03-03, 03-04 | Timeout and graceful degradation | SATISFIED | Tool, LLM node, retrieval, and API fallback paths exist and are tested. |
| RAG-05 | 03-02, 03-05 | Agent answer includes evidence list | SATISFIED | `RecommendationDraft.evidence_refs` and final response citation flow verified. |
| SAFE-06 | 03-01, 03-04, 03-05 | Complete audit log by run_id | PARTIAL | Run/step tables and writes exist, but tool/evidence details are not complete in persisted rows. |
| SAFE-08 | 03-02, 03-04, 03-05 | Tool permission checks | SATISFIED | Tenant and merchant checks exist; review-fix tests cover denial paths. |

No Phase 3 requirement IDs from ROADMAP/REQUIREMENTS are orphaned; all 11 requested IDs appear in plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/agent/trace.py` | 69, 76 | Persistence reads `tool_name`/`evidence_refs`, but nodes emit `tools_called` and no evidence refs | BLOCKER | Causes trace completeness gap despite passing API summary tests. |
| `src/agent/state.py` | 52 | Persistent `evidence_refs` field has no writer | BLOCKER | Same-thread evidence memory is declared but disconnected. |
| `tests/agent/test_graph.py` | 245-257 | Same-thread test checks isolation but not evidence memory retention | WARNING | Passing test does not cover AGNT-05 evidence-memory requirement. |

### Human Verification Required

None for the current automated gate. Live real-LLM smoke testing is available through `scripts/smoke_agent_live.py`, but the phase is already blocked by code-level gaps.

### Gaps Summary

Phase 3 has the core read-only graph, API, tool auth, evidence citation, insufficient-evidence fallback, and green automated tests. It does not yet meet the full phase goal because two goal-critical data flows are hollow: persisted run traces lose tool/evidence details, and same-thread memory does not persist previously retrieved evidence.

---

_Verified: 2026-05-11T08:51:40Z_
_Verifier: Claude (gsd-verifier)_
