# Requirements: MOCA v1.1 Agentic Investigation

**Defined:** 2026-06-04
**Core Value:** When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution — never silently executing something irreversible.

## v1.1 Requirements

Requirements for the v1.1 Agentic Investigation milestone. Each requirement maps to exactly one roadmap phase.

### Tool Registry

- [x] **REG-01**: System has a schema-first tool registry where each tool declares `name`, `description`, `input_schema`, `output_schema`, `risk_level`, `side_effect`, and `allowed_in_investigator`.
- [ ] **REG-02**: Investigator can only select tools whose registry metadata has `allowed_in_investigator=true` and `risk_level` of `read` or `retrieval`.
- [ ] **REG-03**: Initial investigator-visible registry includes only `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`.
- [ ] **REG-04**: Registry metadata explicitly excludes write/action/approval mutation tools from investigator access, including `create_coupon_grant_draft`, `execute_action`, and approval mutation operations.
- [ ] **REG-05**: Tool registry validation fails fast when a tool's declared schema or safety metadata is missing, inconsistent, or unsafe for investigator use.
- [ ] **REG-06**: Registry tools expose typed input/output adapters around the existing tool functions rather than changing the existing tool function contracts unnecessarily.
- [ ] **REG-07**: Tool invocation validates requested tool name and input schema before execution, and records a structured `unsafe_tool_request` result instead of executing tools outside the investigator allowlist.
- [ ] **REG-08**: Tool results passed back into the investigator are summarized or sanitized to avoid prompt/context bloat and sensitive raw payload leakage.
- [ ] **REG-09**: Tool registry metadata includes enough information for tool-selection prompting, including `when_to_use`, `required_identifiers`, and `result_summary_fields`.

### State and Contracts

- [ ] **STATE-01**: `AgentState` is extended in a backward-compatible way to include optional `investigation_result`, `investigation_steps`, `investigation_trigger_reason`, and `investigation_path` fields without changing existing API response contracts.
- [ ] **STATE-02**: `InvestigationResult` schema is versioned or explicitly typed so future tool/result fields can evolve without breaking `generate_recommendation`.
- [ ] **STATE-03**: `InvestigationResult` distinguishes facts, `evidence_refs`, `missing_info`, `candidate_action`, confidence, `stop_reason`, and `safety_notes` rather than mixing them into free-form text.
- [ ] **STATE-04**: Existing persistent thread-scoped memory fields such as `active_slots`, `last_intent`, `evidence_refs`, and `last_business_context_refs` continue to work unchanged.

### Investigation Routing

- [ ] **ROUTE-01**: Graph preserves the explicit-ID fast path through `load_business_context` for simple requests with sufficient evidence.
- [ ] **ROUTE-02**: Graph evaluates whether to enter investigation after `retrieve_policy_evidence` using explicit trigger reasons.
- [ ] **ROUTE-03**: Investigator is entered only for ambiguity, multi-hop dependency, insufficient evidence, or compensation-advice scenarios.
- [ ] **ROUTE-04**: Fast path remains the default; clear explicit-ID cases with sufficient business context and policy evidence do not enter investigator.
- [ ] **ROUTE-05**: Investigation routing is deterministic or rule-scored, not LLM-decided, for v1.1; the router produces explicit `trigger_reason` values.
- [ ] **ROUTE-06**: Router trigger reasons are enumerated and testable, including `low_evidence_score`, `no_evidence`, `ambiguous_intent`, `compensation_advice`, `missing_required_context`, and `multi_hop_question`.
- [ ] **ROUTE-07**: Router avoids entering investigator for unsupported intents or simple policy QA when baseline retrieval is sufficient.
- [ ] **ROUTE-08**: Router preserves existing `insufficient_evidence` fallback behavior when investigation is not applicable or budget is exhausted.

### Bounded Investigator

- [ ] **INV-01**: Investigator performs bounded factual investigation using only registry-approved read-only/retrieval tools.
- [ ] **INV-02**: Investigator has explicit stop conditions, including maximum iterations and stop reasons for sufficient evidence, insufficient evidence, unsafe tool request, or iteration budget exhausted.
- [ ] **INV-03**: Investigator outputs a structured `InvestigationResult` containing gathered facts, evidence references, tool calls, confidence/evidence sufficiency, candidate actions, and stop reason.
- [ ] **INV-04**: Investigator does not produce the final user-facing response.
- [ ] **INV-05**: Investigator does not perform final risk assessment, approval decisions, approval mutations, action draft creation, or action execution.
- [ ] **INV-06**: Investigator handles tool errors and missing evidence with structured fallback results instead of graph-level crashes.
- [ ] **INV-07**: Investigator has a fixed maximum iteration count configured in code/settings and covered by tests.
- [ ] **INV-08**: Investigator can request only one tool call per iteration for v1.1 unless explicitly expanded later.
- [ ] **INV-09**: Investigator does not directly mutate `active_slots`, `approval_result`, `proposed_action`, `action_result`, or `final_response` except through approved structured outputs consumed by downstream nodes.
- [ ] **INV-10**: Candidate actions produced by investigator are advisory only and must be revalidated by `generate_recommendation` and `assess_risk_and_approval`.

### Workflow and Recommendation Preservation

- [ ] **FLOW-01**: Existing `generate_recommendation` remains responsible for producing the final `RecommendationDraft`, using `InvestigationResult` when present.
- [ ] **FLOW-02**: Existing risk and approval flow remains authoritative: `assess_risk_and_approval` determines approval requirements and `approval_gate` enforces human interruption.
- [ ] **FLOW-03**: Existing `execute_action` remains the only place where action execution or action draft creation can occur after approval rules are satisfied.
- [ ] **FLOW-04**: Existing API request/response contract remains backward compatible for v1.0 clients.
- [ ] **FLOW-05**: Existing v1.0 deterministic behavior remains covered by regression tests/evals.
- [ ] **FLOW-06**: `generate_recommendation` prompt/input is updated to consume `InvestigationResult` when present while preserving citation validation and existing fallback behavior.
- [ ] **FLOW-07**: If `InvestigationResult` has insufficient evidence, tool errors, unsafe tool requests, or exhausted iteration budget, `generate_recommendation` produces a safe missing-info or insufficient-evidence recommendation rather than fabricating support.
- [ ] **FLOW-08**: Existing `final_response` templating remains the user-facing response owner and is not bypassed by investigator output.

### Observability and Trace

- [ ] **TRACE-01**: Each investigator tool selection records iteration, tool name, sanitized input, tool status, result summary or reference, selection reason, and stop reason.
- [ ] **TRACE-02**: Investigator trace events are available through the existing trace replay capability without exposing sensitive raw tool payloads.
- [ ] **TRACE-03**: Trace output distinguishes fast path, investigation path, fallback path, approval path, and action execution path.

### Evaluation

- [ ] **EVAL-01**: Golden/eval cases compare v1.0 deterministic workflow and v1.1 investigator path across ambiguous, multi-hop, insufficient-evidence, and compensation-advice scenarios.
- [ ] **EVAL-02**: Evaluation reports investigator trigger accuracy.
- [ ] **EVAL-03**: Evaluation reports tool selection accuracy.
- [ ] **EVAL-04**: Evaluation reports evidence sufficiency.
- [ ] **EVAL-05**: Evaluation reports unsafe action rate and verifies it remains zero for investigator calls.
- [ ] **EVAL-06**: Evaluation verifies approval boundary preservation for risky compensation/action scenarios.
- [ ] **EVAL-07**: Evaluation reports latency overhead introduced by investigation.

### Tests

- [ ] **TEST-01**: Unit tests cover registry validation, unsafe tool exclusion, schema validation failures, and allowed read-only tool invocation.
- [ ] **TEST-02**: Routing tests cover fast path skip, low evidence trigger, compensation trigger, ambiguous question trigger, and unsupported/simple cases.
- [ ] **TEST-03**: Investigator tests cover max iterations, tool error fallback, unsafe tool request rejection, structured `InvestigationResult` output, and no write/action execution.
- [ ] **TEST-04**: Regression tests prove v1.0 approval, `execute_action`, `final_response`, trace, and API behavior remain backward compatible.

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Investigator Expansion

- **FUT-01**: Investigator can support multiple tool calls per iteration when requirements justify the added complexity.
- **FUT-02**: Tool registry can include additional read-only business systems beyond order, refund, ticket, and policy search.
- **FUT-03**: Investigator can support richer scenario expansion beyond refund disputes after v1.1 boundaries are validated.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Full-chain ReAct replacing the deterministic workflow | v1.1 is a bounded investigation layer inside the existing workflow, not a rewrite. |
| Multi-agent rewrite | Adds orchestration complexity and would obscure the v1.0 deterministic approval design. |
| New write/action tools for investigator | Investigator must stay read-only/retrieval-only to preserve safety boundaries. |
| Investigator access to `create_coupon_grant_draft` | Action draft creation belongs only in the existing approval/action flow. |
| Approval API redesign | Existing approval semantics are validated and must remain stable. |
| API contract redesign | v1.0 clients and demo flows must remain backward compatible. |
| Replacing existing risk rules or approval semantics | Risk and approval remain authoritative downstream of investigation. |
| Production deployment or Kubernetes work | Not part of the investigation capability. |
| Real payment/refund execution | MOCA remains a simulated open-source demo with synthetic data. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REG-01 | Phase 7 | Complete |
| REG-02 | Phase 7 | Pending |
| REG-03 | Phase 7 | Pending |
| REG-04 | Phase 7 | Pending |
| REG-05 | Phase 7 | Pending |
| REG-06 | Phase 7 | Pending |
| REG-07 | Phase 7 | Pending |
| REG-08 | Phase 7 | Pending |
| REG-09 | Phase 7 | Pending |
| STATE-01 | Phase 7 | Pending |
| STATE-02 | Phase 7 | Pending |
| STATE-03 | Phase 7 | Pending |
| STATE-04 | Phase 7 | Pending |
| TEST-01 | Phase 7 | Pending |
| ROUTE-01 | Phase 8 | Pending |
| ROUTE-02 | Phase 8 | Pending |
| ROUTE-03 | Phase 8 | Pending |
| ROUTE-04 | Phase 8 | Pending |
| ROUTE-05 | Phase 8 | Pending |
| ROUTE-06 | Phase 8 | Pending |
| ROUTE-07 | Phase 8 | Pending |
| ROUTE-08 | Phase 8 | Pending |
| TEST-02 | Phase 8 | Pending |
| INV-01 | Phase 9 | Pending |
| INV-02 | Phase 9 | Pending |
| INV-03 | Phase 9 | Pending |
| INV-04 | Phase 9 | Pending |
| INV-05 | Phase 9 | Pending |
| INV-06 | Phase 9 | Pending |
| INV-07 | Phase 9 | Pending |
| INV-08 | Phase 9 | Pending |
| INV-09 | Phase 9 | Pending |
| INV-10 | Phase 9 | Pending |
| TEST-03 | Phase 9 | Pending |
| FLOW-01 | Phase 10 | Pending |
| FLOW-02 | Phase 10 | Pending |
| FLOW-03 | Phase 10 | Pending |
| FLOW-04 | Phase 10 | Pending |
| FLOW-05 | Phase 10 | Pending |
| FLOW-06 | Phase 10 | Pending |
| FLOW-07 | Phase 10 | Pending |
| FLOW-08 | Phase 10 | Pending |
| TRACE-01 | Phase 10 | Pending |
| TRACE-02 | Phase 10 | Pending |
| TRACE-03 | Phase 10 | Pending |
| TEST-04 | Phase 10 | Pending |
| EVAL-01 | Phase 11 | Pending |
| EVAL-02 | Phase 11 | Pending |
| EVAL-03 | Phase 11 | Pending |
| EVAL-04 | Phase 11 | Pending |
| EVAL-05 | Phase 11 | Pending |
| EVAL-06 | Phase 11 | Pending |
| EVAL-07 | Phase 11 | Pending |

**Coverage:**
- v1.1 requirements: 53 total
- Mapped to phases: 53
- Unmapped: 0

---
*Requirements defined: 2026-06-04*
*Last updated: 2026-06-04 after v1.1 roadmap creation*
