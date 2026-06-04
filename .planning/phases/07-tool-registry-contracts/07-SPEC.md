# Phase 7: Tool Registry & Investigation Contracts — Specification

**Created:** 2026-06-04
**Ambiguity score:** 0.09 (gate: ≤ 0.20)
**Requirements:** 9 locked

## Goal

The workflow gains a schema-first tool registry, safe investigator-facing invocation boundary, and dormant typed investigation state contracts that expose only approved read/retrieval tools while preserving existing graph, API, and v1.0 runtime behavior.

## Background

The current codebase already has read/retrieval agent tool functions in `src/agent/tools/get_order.py`, `src/agent/tools/get_refund_case.py`, `src/agent/tools/get_ticket.py`, and `src/agent/tools/search_policy.py`. These functions are called directly by existing graph nodes: `load_business_context` calls the order/refund/ticket tools, and `retrieve_policy_evidence` calls `search_policy`. The codebase also has a write/action tool, `create_coupon_grant_draft`, used only by `execute_action` after approval rules are satisfied.

There is currently no unified schema-first tool registry, no investigator allowlist metadata, no registry invocation boundary that validates tool name/input before execution, and no typed `InvestigationResult` or dormant investigation fields in `AgentState`. Existing tests cover individual tools, graph flow, action execution, and trace persistence, but current repository evidence does not show registry validation, unsafe tool exclusion, or schema-first investigator tool metadata tests.

## Requirements

1. **Schema-first registry entries**: Each registry-visible tool is declared through one typed metadata format containing `name`, `description`, `input_schema`, `output_schema`, `risk_level`, `side_effect`, `allowed_in_investigator`, `when_to_use`, `required_identifiers`, and `result_summary_fields`.
   - Current: Tool functions exist as Python functions with implicit dict outputs, but no shared registry metadata or investigator-facing selection guidance exists.
   - Target: A registry entry cannot be created without all required schema, safety, and prompt-selection metadata fields.
   - Acceptance: A unit test can enumerate registry entries and verify every entry has all required fields with typed/validated values.

2. **Investigator allowlist**: The investigator-visible registry includes only `get_order`, `get_refund_case`, `get_ticket`, and `search_policy` as allowed tools for Phase 7.
   - Current: These four read/retrieval tools exist, but there is no registry-level investigator allowlist.
   - Target: These four tools have `allowed_in_investigator=true` with `risk_level` of `read` or `retrieval`; no write/action/approval mutation tools are investigator-allowed.
   - Acceptance: A unit test asserts the set of investigator-allowed tool names equals exactly `{get_order, get_refund_case, get_ticket, search_policy}`.

3. **Unsafe tool exclusion**: Write/action and approval mutation tools are explicitly excluded from investigator access, including `create_coupon_grant_draft`, `execute_action`, and approval mutation operations.
   - Current: `create_coupon_grant_draft` is reachable only through `execute_action`, but no registry metadata marks it unsafe for investigator use.
   - Target: Unsafe tools are either absent from the investigator registry or declared with `allowed_in_investigator=false` and non-read/retrieval safety metadata.
   - Acceptance: Tests prove `create_coupon_grant_draft`, `execute_action`, and approval mutation operations cannot appear in the investigator-allowed tool set.

4. **Fail-fast registry validation**: Registry validation fails before runtime execution when schema or safety metadata is missing, inconsistent, or unsafe.
   - Current: Invalid tool metadata cannot be detected because no registry validation layer exists.
   - Target: Registry construction/validation rejects missing schemas, missing safety metadata, `allowed_in_investigator=true` combined with non-read/retrieval risk, and side-effecting tools marked as investigator-allowed.
   - Acceptance: Tests create invalid registry definitions and confirm validation fails before any tool function can run.

5. **Adapter-based tool wrapping**: Registry adapters wrap existing `src/agent/tools/*` functions instead of changing those functions' public signatures unless strictly necessary.
   - Current: Existing nodes and tests call tool functions directly with their current parameters.
   - Target: The registry invocation boundary uses typed input/output adapters around existing functions while preserving existing direct call compatibility.
   - Acceptance: Existing tool tests still pass unchanged, and new adapter tests prove each allowed tool can be invoked through the registry adapter.

6. **Safe invocation boundary**: Tool invocation validates requested tool name and input schema before execution and returns a structured unsafe result for disallowed requests instead of executing the requested function.
   - Current: There is no shared boundary where a future investigator can request a tool by name and have the request validated against an allowlist and input schema.
   - Target: Requests for unknown tools, tools not allowed for the investigator, write/action tools, or schema-invalid inputs return a structured `unsafe_tool_request` or validation error result without calling the underlying function.
   - Acceptance: Tests prove unsafe/disallowed requests return structured rejection results and that the underlying unsafe tool function is not awaited/called.

7. **Investigator-facing result sanitization**: `ToolExecutionResult` exposes only registry-declared `result_summary_fields` plus `status`, `error`, and `evidence_refs` to investigator prompts.
   - Current: Tool outputs are plain dicts; `search_policy` includes raw evidence text, and no shared result contract prevents raw payloads from being passed into future investigator prompts.
   - Target: Registry invocation separates internal raw tool payloads from the investigator-facing `ToolExecutionResult`; raw payloads are not included in the prompt-facing result.
   - Acceptance: Tests confirm investigator-facing results contain only `status`, `error`, `evidence_refs`, and declared summary fields, and do not include raw payload fields such as policy evidence `text` unless explicitly declared as summary fields.

8. **Typed investigation contracts**: `InvestigationResult` is explicitly typed and versioned/evolvable, with separate fields for facts, `evidence_refs`, `missing_info`, `candidate_action`, confidence, `stop_reason`, and `safety_notes`.
   - Current: No `InvestigationResult` schema exists in `src/agent/schemas.py`; investigation output would have to be represented as untyped free-form data.
   - Target: A typed schema exists for downstream phases to consume without mixing facts, evidence, missing information, candidate action advice, confidence, stop reason, or safety notes into free-form text.
   - Acceptance: Schema tests validate a well-formed `InvestigationResult` and reject invalid confidence/stop reason structures according to the declared contract.

9. **Dormant backward-compatible state fields**: `AgentState` is extended with optional dormant investigation fields without changing existing graph edges, routing, recommendation generation, investigator execution, API responses, or v1.0 runtime behavior.
   - Current: `AgentState` includes persistent thread memory and current runtime fields, but no `investigation_result`, `investigation_steps`, `investigation_trigger_reason`, or `investigation_path` fields.
   - Target: `AgentState` includes optional `investigation_result`, `investigation_steps`, `investigation_trigger_reason`, and `investigation_path` fields for future phases while all current graph behavior remains unchanged.
   - Acceptance: Existing graph/API regression tests still pass, and a state/schema test confirms the new fields are optional and absent from public API responses unless later phases explicitly add them.

## Boundaries

**In scope:**
- Schema-first registry metadata contract for tool definitions.
- Investigator allowlist metadata for `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`.
- Explicit exclusion of write/action/approval mutation tools from investigator access.
- Registry validation that fails fast for missing, inconsistent, or unsafe metadata.
- Typed adapters around existing agent tool functions.
- Safe invocation boundary that validates tool name and input schema before execution.
- Structured unsafe-tool rejection results that do not execute disallowed tools.
- Investigator-facing `ToolExecutionResult` sanitization based on registry-declared `result_summary_fields` plus `status`, `error`, and `evidence_refs`.
- Typed `InvestigationResult` contract and optional dormant `AgentState` fields.
- Unit/regression tests covering registry validation, unsafe tool exclusion, schema validation failures, allowed read-only invocation, result sanitization, and v1.0 behavior preservation.

**Out of scope:**
- Changing graph edges or adding an investigator node — Phase 7 only prepares contracts and boundaries for later routing/execution phases.
- Changing `generate_recommendation` behavior or making it consume `InvestigationResult` — recommendation integration belongs to a later workflow preservation phase.
- Implementing deterministic investigation routing — Phase 8 owns routing trigger decisions.
- Implementing the bounded investigator execution loop — Phase 9 owns iteration, tool selection, stop conditions, and advisory output generation.
- Replacing existing tool function signatures wholesale — adapters should wrap existing functions unless a minimal compatibility-preserving change is strictly necessary.
- Full field-level PII redaction system — Phase 7 prevents raw payloads from entering investigator-facing prompt results, but complete PII redaction policy is not part of this phase.
- Changing public API request/response contracts — v1.0 clients must remain backward compatible.
- Changing approval semantics, action draft creation, or action execution — approval and execution remain downstream and authoritative.

## Constraints

- Phase 7 should add dormant typed state fields and a safe invocation boundary, but must not change graph edges, `generate_recommendation` behavior, routing, investigator execution, API responses, or v1.0 runtime behavior.
- Investigator-visible tools must be limited to read/retrieval risk levels for this phase.
- Existing direct uses of `get_order`, `get_refund_case`, `get_ticket`, `search_policy`, and `create_coupon_grant_draft` must remain compatible with existing tests.
- Raw tool payloads may remain internal for adapter execution or future trace-safe references, but must not be passed into investigator prompts through `ToolExecutionResult`.
- Validation errors and unsafe requests must be structured data, not graph-level crashes.

## Acceptance Criteria

- [ ] Registry entries require `name`, `description`, `input_schema`, `output_schema`, `risk_level`, `side_effect`, `allowed_in_investigator`, `when_to_use`, `required_identifiers`, and `result_summary_fields`.
- [ ] Investigator-allowed tool names are exactly `get_order`, `get_refund_case`, `get_ticket`, and `search_policy`.
- [ ] `create_coupon_grant_draft`, `execute_action`, and approval mutation operations cannot be exposed as investigator-allowed tools.
- [ ] Registry validation fails fast for missing schemas, missing safety metadata, unsafe risk/side-effect combinations, and inconsistent investigator allowlist metadata.
- [ ] Registry adapters invoke allowed read/retrieval tools without changing existing tool function signatures or breaking existing direct-call tests.
- [ ] Unknown, schema-invalid, or disallowed tool requests return structured rejection results and do not call the underlying unsafe function.
- [ ] Investigator-facing `ToolExecutionResult` contains only declared `result_summary_fields` plus `status`, `error`, and `evidence_refs`; raw payloads are not exposed to investigator prompts.
- [ ] `InvestigationResult` schema has typed fields for facts, `evidence_refs`, `missing_info`, `candidate_action`, confidence, `stop_reason`, and `safety_notes`.
- [ ] `AgentState` includes optional dormant `investigation_result`, `investigation_steps`, `investigation_trigger_reason`, and `investigation_path` fields.
- [ ] Existing graph edges, routing, `generate_recommendation`, investigator execution, API responses, and v1.0 runtime behavior remain unchanged as proven by existing regression tests.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.94  | 0.75 | ✓ | Goal narrowed to registry, safe invocation boundary, typed contracts, and dormant state fields. |
| Boundary Clarity   | 0.92  | 0.70 | ✓ | Explicitly excludes graph wiring, routing, investigator loop, recommendation behavior changes, API changes, and full PII redaction. |
| Constraint Clarity | 0.88  | 0.65 | ✓ | Preserves existing tool signatures and v1.0 runtime/API behavior; raw payloads stay out of investigator prompts. |
| Acceptance Criteria| 0.87  | 0.70 | ✓ | Pass/fail criteria cover metadata validation, allowlist, unsafe rejection, sanitization, typed schemas, and regression preservation. |
| **Ambiguity**      | 0.09  | ≤0.20| ✓ | Gate passed after round 2. |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| Initial | Researcher | What does ROADMAP/REQUIREMENTS already define for Phase 7? | Phase 7 maps REG-01 through REG-09, STATE-01 through STATE-04, and TEST-01. Existing repo has tool functions and state, but no registry/contracts. |
| 1 | Researcher | What is the primary verifiable deliverable? | Registry + contracts: schema-first registry, typed contracts, safe invocation boundary, and tests; no routing/investigator loop. |
| 1 | Researcher | Should adapters wrap functions, rewrite tools, or target API routers? | Wrap existing `src/agent/tools/*` functions with typed adapters; preserve current direct-call compatibility. |
| 1 | Researcher | How far should result sanitization go? | `ToolExecutionResult` exposes only registry-declared `result_summary_fields` plus `status`, `error`, and `evidence_refs`; full field-level PII redaction is out of scope, but raw payloads must not enter investigator prompts. |
| 2 | Researcher + Simplifier | How far should `InvestigationResult` go in Phase 7? | Define typed schema and optional dormant state fields; do not integrate with `generate_recommendation`. |
| 2 | Researcher + Simplifier | What is the unsafe tool request boundary? | Invocation-level rejection: unknown, disallowed, write/action, or schema-invalid requests return structured unsafe/validation results without executing. |
| 2 | Researcher + Simplifier | Does the minimum success version include graph wiring? | Dormant typed state fields only; no graph edge, routing, investigator execution, recommendation, API response, or v1.0 runtime behavior changes. |

---

*Phase: 07-tool-registry-contracts*
*Spec created: 2026-06-04*
*Next step: /gsd-discuss-phase 7 — implementation decisions (how to build what's specified above)*
