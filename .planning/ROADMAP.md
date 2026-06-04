# Roadmap: MOCA

## Milestones

- [x] **v1.0 MVP** — Merchant Operations Collaborative Agent demo shipped on 2026-05-22. Full archive: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [ ] **v1.1 Agentic Investigation** — Phases 7-11 add a bounded investigation layer inside the existing deterministic workflow without breaking v1.0 behavior.

## Phases

<details>
<summary>v1.0 MVP (Phases 1-6) — SHIPPED 2026-05-22</summary>

- [x] Phase 1: Foundation (5/5 plans) — Docker Compose services, schema, auth, seed data, repository layer, CRUD/tool-call foundations.
- [x] Phase 2: RAG Pipeline (7/7 plans) — Chinese policy ingestion, pgvector retrieval, citation validation, search API, RAG Hit@5 83.3%.
- [x] Phase 3: LangGraph Core (6/6 plans) — read-only refund agent path, evidence-cited responses, trace persistence, same-thread memory.
- [x] Phase 4: Approval Workflow & Audit (6/6 plans) — high-risk interrupt/resume, approval APIs, action drafts, audit replay, 100% interception.
- [x] Phase 5: Frontend & SSE (8/8 plans) — React/Vite support console, SSE timeline, evidence/trace panels, approval handling, Docker demo stack.
- [x] Phase 6: Evaluation & Polish (4/4 plans) — 14 RAG cases, 35 agent cases, eval scripts, CI baseline, demo script, README/docs polish.

</details>

### v1.1 Agentic Investigation (Phases 7-11)

- [ ] **Phase 7: Tool Registry & Investigation Contracts** - Establish schema-first tool metadata, validated investigator boundaries, and backward-compatible state contracts.
- [ ] **Phase 8: Deterministic Investigation Routing** - Add explicit routing rules that preserve the fast path and enter investigation only for bounded scenarios.
- [ ] **Phase 9: Bounded Investigator Execution** - Deliver the iterative read-only investigator with structured outputs, stop conditions, and safe fallbacks.
- [ ] **Phase 10: Workflow Preservation & Trace Integration** - Feed investigation outputs through the existing recommendation, approval, execution, and replay flow without changing public contracts.
- [ ] **Phase 11: Evaluation & Regression Proof** - Prove trigger quality, tool-selection quality, safety boundaries, and latency overhead with milestone-specific evals.

## Phase Details

### Phase 7: Tool Registry & Investigation Contracts
**Goal**: The workflow has a schema-first registry and typed investigation contracts that safely expose only approved read/retrieval tools to the future investigator while preserving existing tool and API compatibility.
**Depends on**: Phase 6
**Requirements**: REG-01, REG-02, REG-03, REG-04, REG-05, REG-06, REG-07, REG-08, REG-09, STATE-01, STATE-02, STATE-03, STATE-04, TEST-01
**Success Criteria** (what must be TRUE):
  1. Investigator-visible tools are defined through one validated registry format that includes schemas, safety metadata, and prompt-facing selection guidance.
  2. Existing `get_order`, `get_refund_case`, `get_ticket`, and `search_policy` functions are exposed through registry adapters without rewriting or signature-changing the existing tool functions unless strictly necessary.
  3. Attempts to expose missing-schema, unsafe, or write-capable tools to the investigator fail validation before runtime execution begins.
  4. Tool calls requested through the investigator boundary validate name and input shape before execution and return structured safe rejection results for disallowed requests.
  5. Tool invocation returns a sanitized/summarized `ToolExecutionResult` for investigator use while raw tool payloads remain internal or trace-safe referenced.
  6. Downstream graph nodes can read a typed `InvestigationResult` and new investigation state fields without breaking existing thread memory or v1.0 API responses.
**Plans**: TBD

### Phase 8: Deterministic Investigation Routing
**Goal**: The graph deterministically decides when investigation is necessary and keeps explicit-ID, evidence-sufficient cases on the existing fast path.
**Depends on**: Phase 7
**Requirements**: ROUTE-01, ROUTE-02, ROUTE-03, ROUTE-04, ROUTE-05, ROUTE-06, ROUTE-07, ROUTE-08, TEST-02
**Success Criteria** (what must be TRUE):
  1. Simple explicit-ID requests with sufficient business context and policy evidence complete through the existing non-investigator path.
  2. Ambiguous, multi-hop, missing-context, no-evidence, low-evidence, and compensation-advice cases produce explicit, testable investigation trigger reasons.
  3. Trigger reasons are enumerated and stable for tests/evals, including `low_evidence_score`, `no_evidence`, `ambiguous_intent`, `missing_required_context`, `multi_hop_question`, and `compensation_advice`.
  4. Unsupported intents and simple policy Q&A with sufficient retrieval avoid unnecessary investigation and preserve the current fallback behavior.
**Plans**: TBD

### Phase 9: Bounded Investigator Execution
**Goal**: The system can run a bounded factual investigation loop that gathers evidence through approved read-only tools and returns structured advisory output without taking action.
**Depends on**: Phase 8
**Requirements**: INV-01, INV-02, INV-03, INV-04, INV-05, INV-06, INV-07, INV-08, INV-09, INV-10, TEST-03
**Success Criteria** (what must be TRUE):
  1. Investigation runs perform at most the configured number of iterations and issue no more than one approved tool call per iteration.
  2. Investigator execution is testable with deterministic planner/model stubs so max-iteration handling, unsafe-tool rejection, stop reasons, and fallback behavior do not depend on live LLM calls.
  3. Completed investigations return a structured `InvestigationResult` with facts, evidence references, missing information, candidate action advice, confidence, and stop reason.
  4. Tool errors, unsafe tool requests, and exhausted budgets end in structured fallback results instead of graph crashes or silent retries.
  5. Investigation output is advisory only: it does not create drafts, mutate approval state, execute actions, or produce the final user-facing response.
**Plans**: TBD

### Phase 10: Workflow Preservation & Trace Integration
**Goal**: Investigation output enriches the existing recommendation pipeline and trace replay while keeping approval authority, action execution ownership, final response formatting, and client contracts unchanged.
**Depends on**: Phase 9
**Requirements**: FLOW-01, FLOW-02, FLOW-03, FLOW-04, FLOW-05, FLOW-06, FLOW-07, FLOW-08, TRACE-01, TRACE-02, TRACE-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. When investigation data is present, `generate_recommendation` uses it to produce safe recommendations with citations or missing-info fallbacks, while `final_response` remains the only user-facing response owner.
  2. `generate_recommendation` integration is additive: existing `business_context` and `retrieved_evidence` behavior remains unchanged when `investigation_result` is absent.
  3. Risk assessment, approval interruption, action draft creation, and action execution still occur only in the existing downstream nodes and remain authoritative for risky cases.
  4. Existing v1.0 clients can call the API and receive backward-compatible responses, including preserved approval and execution behavior.
  5. Trace replay clearly shows whether a run used the fast path, investigation path, fallback path, approval path, or execution path, and investigator tool events are visible without leaking raw sensitive payloads.
**Plans**: TBD

### Phase 11: Evaluation & Regression Proof
**Goal**: The milestone has measurable evidence that the bounded investigation layer improves ambiguous-case handling without weakening safety, approval boundaries, or latency expectations.
**Depends on**: Phase 10
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07
**Success Criteria** (what must be TRUE):
  1. Golden and evaluation runs distinguish v1.0 fast-path behavior from v1.1 investigation behavior across ambiguous, multi-hop, insufficient-evidence, and compensation-advice scenarios.
  2. Existing v1.0 golden/eval cases remain passing and are reported separately from new v1.1 investigation cases.
  3. Evaluation reports expose investigator trigger accuracy, tool-selection accuracy, evidence sufficiency, and latency overhead in a repeatable format.
  4. Evaluation proves unsafe investigator action rate remains zero and risky compensation or action scenarios still preserve the approval boundary.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 7. Tool Registry & Investigation Contracts | 0/TBD | Not started | - |
| 8. Deterministic Investigation Routing | 0/TBD | Not started | - |
| 9. Bounded Investigator Execution | 0/TBD | Not started | - |
| 10. Workflow Preservation & Trace Integration | 0/TBD | Not started | - |
| 11. Evaluation & Regression Proof | 0/TBD | Not started | - |

---
*Updated: 2026-06-04 for milestone v1.1 Agentic Investigation. v1.0 archive remains in `.planning/milestones/v1.0-ROADMAP.md`.*