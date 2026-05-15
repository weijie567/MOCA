---
phase: 03-langgraph-core
verified: 2026-05-15T07:31:23Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/7
  gaps_closed:
    - "Execution trace records all graph nodes traversed, tool calls made, and evidence referenced; trace is queryable by run_id"
    - "Same-thread conversation remembers order_id, refund_case_id, and previously retrieved evidence via LangGraph checkpointer"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Live agent smoke with real configured LLM and local database"
    expected: "A refund/policy question returns an evidence-cited answer, trace_summary includes run_id/nodes/tools/evidence_count, and AgentRun/AgentStep rows are queryable by run_id."
    why_human: "The automated suite intentionally uses FakeLLM; real external LLM/provider behavior and local operator environment require manual smoke verification."
    result: "passed"
    evidence: "03-HUMAN-UAT.md records 3/3 live smoke cases passing: policy QA completed with evidence_count=5, refund troubleshooting completed with evidence_count=5, and no-evidence fallback returned insufficient_evidence with evidence_count=0."
---

# Phase 3: LangGraph Core Verification Report

**Phase Goal:** Submit a refund question and receive an evidence-cited answer with full execution trace, tool calls, and same-thread memory — the complete read-only happy path without approval interruption.
**Verified:** 2026-05-15T07:31:23Z
**Status:** passed
**Re-verification:** Yes — after 03-06 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Agent accepts a refund question, identifies intent, loads business context via read tools, retrieves evidence, and returns a structured response with validated doc/chunk citations. | VERIFIED | `build_graph()` wires all 8 deterministic nodes in `src/agent/graph.py:31-54`. `generate_recommendation()` validates cited chunk IDs before returning `recommendation_draft` in `src/agent/nodes/generate_recommendation.py:135-153`. Graph happy-path tests assert final response, intent, evidence refs, risk level, and trace steps in `tests/agent/test_graph.py:163-188`. |
| 2 | Execution trace records graph nodes, tool calls, and evidence references and is queryable by run_id. | VERIFIED | Closed prior gap. `write_agent_steps()` now persists each trace step by `run_id`, normalizes `tools_called` into `AgentStep.tool_name`, preserves `tools_called` in `tool_output_summary`, and writes `evidence_refs` in `src/agent/trace.py:50-110`. The DB-backed regression queries `AgentStep` rows by `run_id` and asserts tool/evidence persistence in `tests/agent/test_trace.py:14-79`. |
| 3 | Same-thread memory remembers order/refund/ticket slots and previously retrieved evidence via LangGraph checkpointer. | VERIFIED | Closed prior gap. `receive_request()` resets `retrieved_evidence` but does not reset persistent `evidence_refs` in `src/agent/nodes/receive_request.py:25-40`. Retrieval merges new refs into persistent state in `src/agent/nodes/retrieve_policy_evidence.py:89-130`; recommendation merges citation-validated refs in `src/agent/nodes/generate_recommendation.py:146-153`. `tests/agent/test_graph.py:260-278` proves prior refs survive a same-thread no-evidence turn while the current turn remains insufficient evidence. |
| 4 | Current-turn no-evidence/low-evidence turns still refuse definitive conclusions and return missing_info. | VERIFIED | `retrieve_policy_evidence()` sets an `insufficient_evidence` draft when retrieval status is `no_evidence` or score is below `MIN_EVIDENCE_SCORE` in `src/agent/nodes/retrieve_policy_evidence.py:120-139`. Graph and node tests cover no-evidence refusal and ensure definitive refund phrases are absent in `tests/agent/test_graph.py:191-204` and `tests/agent/test_nodes/test_retrieve_policy_evidence.py:35-110`. |
| 5 | LLM/DB/tool timeout or provider failure degrades to structured errors instead of crashing. | VERIFIED | Retrieval tool errors become `retrieval_error`, `node_errors`, and error trace status in `src/agent/nodes/retrieve_policy_evidence.py:131-136`; recommendation validation/provider failures retry and then return a structured insufficient-evidence draft in `src/agent/nodes/generate_recommendation.py:155-177`; API graph exceptions return a structured fallback and persist an error run in `src/api/routers/agent.py:51-82` and `132-160`. |
| 6 | FastAPI exposes authenticated `POST /api/v1/agent/chat` and initializes AsyncPostgresSaver once in lifespan. | VERIFIED | Endpoint enforces `agent:chat` at `src/api/routers/agent.py:24-30`, invokes `request.app.state.agent_graph` at `src/api/routers/agent.py:32-52`, and persists run/steps at `src/api/routers/agent.py:92-108`. Lifespan initializes `AsyncPostgresSaver`, calls `setup()`, and compiles the graph once in `src/api/main.py:28-34`; router is mounted in `src/api/main.py:101-106`. |
| 7 | Phase remains read-only without approval interrupts or write tools. | VERIFIED | `rg` found no LangGraph `interrupt()` usage or write-tool execution in `src/agent`; only trace audit writes are present. Phase 3 tools are read-only `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`, with tenant/merchant checks shown in `src/agent/tools/*.py` and `src/agent/tools/authz.py`. `assess_risk_and_approval()` only marks risk/approval_required and returns state in `src/agent/nodes/assess_risk_and_approval.py:133-188`. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/agent/trace.py` | AgentStep persistence maps `tools_called` and `evidence_refs` into existing DB columns | VERIFIED | Artifact check passed. `_normalize_tool_name()` and `_normalize_tool_output_summary()` are wired into `write_agent_steps()` at `src/agent/trace.py:61-76`. |
| `src/agent/nodes/retrieve_policy_evidence.py` | Retrieved evidence ref extraction, trace attachment, and persistent `evidence_refs` merge | VERIFIED | Artifact check passed. Evidence refs are extracted from real retrieval results and merged into persistent state at `src/agent/nodes/retrieve_policy_evidence.py:69-130`. |
| `src/agent/nodes/generate_recommendation.py` | Validated recommendation evidence refs in trace and persistent memory | VERIFIED | Artifact check passed. Invalid citations are stripped and only validated refs are merged/traced at `src/agent/nodes/generate_recommendation.py:135-153`. |
| `tests/agent/test_trace.py` | DB-backed run_id query regression for persisted tool/evidence trace | VERIFIED | Artifact check passed. Test queries `AgentStep` by `run_id` and asserts tool/evidence fields at `tests/agent/test_trace.py:64-79`. |
| `tests/agent/test_graph.py` | Same-thread evidence memory regression through MemorySaver | VERIFIED | Artifact check passed. Regression proves retained refs plus current-turn no-evidence refusal at `tests/agent/test_graph.py:260-278`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `retrieve_policy_evidence.py` | `write_agent_steps()` / `agent_steps` | `trace_steps[].tools_called` and `trace_steps[].evidence_refs` | VERIFIED | Retrieval trace step includes `tools_called=["search_policy"]` and refs when present at `src/agent/nodes/retrieve_policy_evidence.py:19-29`; persistence reads both fields at `src/agent/trace.py:69-76`. |
| `generate_recommendation.py` | `write_agent_steps()` / `agent_steps` | validated recommendation `evidence_refs` on trace step | VERIFIED | Validated refs are attached to recommendation trace steps at `src/agent/nodes/generate_recommendation.py:34-46` and `146-153`. |
| `src/api/routers/agent.py` | `agent_runs` / `agent_steps` | `write_agent_run()` then `write_agent_steps(session, run_id=run_id, trace_steps=trace_steps)` | VERIFIED | API persistence path is wired at `src/api/routers/agent.py:92-108`. |
| LangGraph checkpointer | `AgentState.evidence_refs` | persistent field not reset by `receive_request`, merged by retrieval/recommendation nodes | VERIFIED | `evidence_refs` is a persistent AgentState field at `src/agent/state.py:44-53`; `receive_request()` resets only ephemeral fields at `src/agent/nodes/receive_request.py:25-40`; MemorySaver regression passes. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/agent/trace.py` | `AgentStep.tool_name`, `AgentStep.tool_output_summary`, `AgentStep.evidence_refs` | `final_state["trace_steps"]` from graph nodes via API persistence | Yes | VERIFIED — DB-backed test persists and queries tool/evidence fields by `run_id`. |
| `src/agent/nodes/retrieve_policy_evidence.py` | `retrieved_evidence`, `evidence_refs` | `search_policy()` result from `Retriever.search()` wrapper | Yes | VERIFIED — refs are generated only from retrieved evidence items containing `doc_key` and `chunk_id`. |
| `src/agent/nodes/generate_recommendation.py` | `recommendation_draft.evidence_refs`, persistent `evidence_refs` | LLM structured output filtered through `validate_citations()` against current retrieval result | Yes | VERIFIED — invalid chunk IDs are stripped before state/trace persistence. |
| `src/agent/nodes/receive_request.py` | `retrieved_evidence` vs `evidence_refs` | Per-turn reset plus checkpointer-retained persistent state | Yes | VERIFIED — current-turn evidence is reset; same-thread refs persist for memory/audit only. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| 03-06 focused regressions | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_graph.py -q --tb=short -m "not live"` | 18 passed, 1 LangGraph warning | PASS |
| Full test suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` | 86 passed, 1 LangGraph warning | PASS |
| Schema drift | `gsd-sdk query verify.schema-drift "03" --raw` | `valid: true`, no issues, 6 checked | PASS |
| Artifact verification | `gsd-sdk query verify.artifacts .planning/phases/03-langgraph-core/03-06-PLAN.md --raw` | 5/5 artifacts passed | PASS |
| Key-link verification | `gsd-sdk query verify.key-links .planning/phases/03-langgraph-core/03-06-PLAN.md --raw` plus manual check | 3/4 automated links; abstract checkpointer link manually verified by code/test evidence | PASS |
| Live DashScope smoke | `set -a; source .env; set +a; LIVE_SMOKE_CASE_TIMEOUT_SECONDS=420 UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/smoke_agent_live.py` | 3/3 passed: policy QA completed with evidence_count=5; refund troubleshooting completed with evidence_count=5; no-evidence fallback returned insufficient_evidence with evidence_count=0 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| AGNT-01 | 03-03, 03-05 | Intent recognition and routing | SATISFIED | Graph happy-path tests verify policy/refund intents and deterministic node path. |
| AGNT-02 | 03-01, 03-03, 03-04, 03-05 | LangGraph happy path state machine | SATISFIED | `build_graph()` wires all 8 nodes; graph tests assert all 8 trace steps. |
| AGNT-03 | 03-02, 03-05 | Structured read tools for order/refund/ticket | SATISFIED | Tool wrappers exist, are read-only, and full suite passes tool contract/auth tests. |
| AGNT-04 | 03-02, 03-05, 03-06 | Knowledge retrieval with concrete citations | SATISFIED | Retrieval and recommendation nodes produce/validate doc/chunk refs; node regressions pass. |
| AGNT-05 | 03-01, 03-03, 03-06 | Same-thread context memory including evidence refs | SATISFIED | Same-thread MemorySaver regression proves retained `evidence_refs` across turns. |
| AGNT-06 | 03-01, 03-04, 03-05, 03-06 | Structured execution trace records nodes/tools/evidence | SATISFIED | `write_agent_steps()` persists nodes, tools, and evidence refs; DB-backed run_id regression passes. |
| AGNT-08 | 03-03, 03-05 | Refuse definitive conclusions when evidence is insufficient | SATISFIED | No-evidence/low-score paths return `insufficient_evidence`; graph test checks no definitive refund phrases. |
| INFR-09 | 03-01, 03-03, 03-04 | Timeout and graceful degradation | SATISFIED | Retrieval, recommendation, risk, and API fallback paths produce structured errors/fallbacks. |
| RAG-05 | 03-02, 03-05, 03-06 | Agent answer includes evidence list | SATISFIED | `RecommendationDraft.evidence_refs` is validated, preserved in current response, and persisted as compact memory refs. |
| SAFE-06 | 03-01, 03-04, 03-06 | Complete audit log by run_id | SATISFIED | AgentRun/AgentStep schema exists; API writes run/steps; DB-backed test queries by run_id. |
| SAFE-08 | 03-02, 03-04, 03-05 | Tool permission checks | SATISFIED | Read tools enforce tenant and merchant access; review-fix regressions are included in the 86-test full suite. |

No Phase 3 requirement IDs are orphaned: the 11 roadmap requirements all appear in Phase 03 plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/agent/nodes/retrieve_policy_evidence.py` | 71, 93, 123 | Empty-list initialization / no-evidence branch | INFO | Intentional local accumulation and no-evidence behavior; not a stub because real retrieval populates refs and no-evidence is tested. |
| `src/agent/trace.py` | 57, 88, 121 | Empty-list initialization | INFO | Intentional accumulator setup before iterating trace steps/tools; not user-visible hollow data. |
| `tests/agent/test_graph.py` | 195, 270, 273 | Empty evidence fixtures/assertions | INFO | Intentional no-evidence regression fixtures proving insufficient-evidence behavior. |

### Human Verification

The live agent smoke item is resolved and recorded in `03-HUMAN-UAT.md`.

**Result:** 3/3 live cases passed against DashScope and the local database.
**Evidence:** Policy QA returned `completed` with `evidence_count=5`; refund troubleshooting for `ORD-2024-001` returned `completed` with `evidence_count=5`; the unrelated query returned `insufficient_evidence` with `evidence_count=0`.

### Gaps Summary

No automated gaps remain. The two original blockers are closed:

- AgentStep rows now preserve `tools_called` and evidence refs through existing DB columns.
- Same-thread `AgentState.evidence_refs` now persists across turns while `retrieved_evidence` remains per-turn and no-evidence turns still return `insufficient_evidence`.

Phase 3 is complete against the roadmap contract. The prior `human_needed` item is closed by the recorded live DashScope smoke verification.

---

_Verified: 2026-05-15T07:31:23Z_
_Verifier: Claude (gsd-verifier)_
