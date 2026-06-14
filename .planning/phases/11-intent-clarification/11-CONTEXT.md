# Phase 11: Intent / Clarification - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 11 implements deterministic intent precedence, required-slot expressions, confidence safety gates, and ordinary clarification on top of the Phase 10 graph foundation.

This phase owns the ordinary-chat intent and clarification path only. It must not implement the trusted approval decision lifecycle, approval `respond` resume flow, ApprovalService state machine, action safety snapshot, session-memory CAS, or external execution. Those remain owned by later phases.

Hard safety boundary: ordinary chat cannot create `approval_result`, cannot issue a LangGraph resume command, cannot set trusted approval versions, and cannot produce a trusted approval decision. Approval decisions belong only to authenticated approval API / inbox command adapters.
</domain>

<decisions>
## Implementation Decisions

### Reference Adoption
- **D-01:** Adopt the `agents-from-scratch-ts` triage routing pattern at the structural level: classify first, then route. Apply this as a MOCA domain triage pattern, not as email-domain intent names or prompts.
- **D-02:** Adopt the LangGraph adaptive RAG structured router pattern: use Pydantic `BaseModel` schemas with `Literal[...]` fields for intent/router outputs. Do not parse free-form strings from the model for routing.
- **D-03:** Adopt the `agent-inbox` boundary idea: ordinary chat clarification and approval respond/decision are separate contracts. Ordinary clarification may collect missing business/user information; approval `respond` / `needs_info` remains a trusted approval lifecycle path.

### Reference Exclusions
- **D-04:** Do not use the customer-support notebook, email-domain prompt content, free tool-loop behavior, or memory-driven triage preferences as Phase 11 core design inputs.
- **D-05:** Reference repositories are planning constraints only. Phase 11 should not copy their domain prompt text, mailbox workflow, or agent loop structure into MOCA.

### IntentResultV3 Contract
- **D-06:** Extend the current `IntentResult` into an `IntentResultV3` contract with at least `schema_version`, `primary_intent`, `requested_operation`, `confidence`, `calibrated_confidence`, `secondary_intents`, `required_slots`, `candidate_slots`, `routing_hints`, `classifier_version`, `calibration_version`, and `reason_codes`.
- **D-07:** `primary_intent` captures domain semantics; `requested_operation` captures what the user asks the system to do. Write/escalation operations must route to safety paths without overwriting the most specific domain intent.
- **D-08:** `candidate_slots` from intent classification are hints only. They must not satisfy slot completeness and must not overwrite `extracted_slots` or `active_slots`.

### Deterministic Pre-Router and Precedence
- **D-09:** Phase 11 must implement a deterministic pre-router before or alongside LLM classification for safety-sensitive ordinary text. Action/write/escalation/approval-looking text cannot be allowed to bypass safe routing through ordinary LLM classification.
- **D-10:** The precedence table in `docs/contract-spec.md` §11.2 is the source of truth for conflicts: specialized domain intents beat generic `action_request`, while `requested_operation` preserves action/write/escalation safety implications.
- **D-11:** Any apparent approval decision in ordinary chat is untrusted invalid state for the ordinary graph. It may become unsupported/clarification or a normal domain request, but never a trusted approval decision.

### Required Slots and Clarification
- **D-12:** Required-slot policy uses structured expressions with `all_of`, `any_of`, and `optional`; completeness is deterministic and evaluated after current explicit slots plus allowed session slots are resolved.
- **D-13:** Missing required slots route to ordinary `clarification_gate` with a concrete `clarification_request` object. The gate should ask for the minimal missing information needed to continue.
- **D-14:** Phase 11 upgrades the Phase 10 `clarification_gate` stub for ordinary clarification only. It must not handle approval `respond`, `needs_info`, old approval revision resume, or trusted approval lifecycle state.

### Planning Split
- **D-15:** Split Phase 11 into at least these five small plans:
  - `11-01`: `IntentResultV3` schema + prompt contract.
  - `11-02`: deterministic pre-router + intent precedence.
  - `11-03`: `RequiredSlotExpression` + `route_after_intent` / `route_after_slots`.
  - `11-04`: ordinary clarification gate.
  - `11-05`: intent consistency manifest + golden tests.
- **D-16:** Each plan should explicitly include:
  - Reference used: `agents-from-scratch-ts` triage routing pattern.
  - Reference used: LangGraph adaptive RAG structured output routing.
  - Reference excluded: email prompts, free tool loop, memory-updated triage preferences.
  - Safety constraint: ordinary chat cannot create `approval_result`, resume commands, or trusted approval decisions.

### Targeted Amendment: State Mapping
- **D-17:** Phase 11 must implement the `IntentResultV3 -> AgentState` mapping from `docs/contract-spec.md` §10.4 through an explicit adapter. It must not whole-object merge classifier output into `AgentState`.
- **D-18:** `confidence` writes only to `intent_confidence`. `calibrated_confidence` writes only to intent eval metadata under `llm_outputs`, together with `classifier_version` and `calibration_version`; it must not overwrite `intent_confidence`.
- **D-19:** `secondary_intents`, `required_slots`, `routing_hints`, and `candidate_slots` are schema-validated replace writes. `candidate_slots` remain slot-extraction hints only and must not satisfy completeness or overwrite `extracted_slots` / `active_slots`.
- **D-20:** The intent node must not write final answers, `extracted_slots`, `active_slots`, `risk_signals`, `approval_result`, trusted approval versions, resume commands, or tool/action outputs.

### Targeted Amendment: Eval Gates
- **D-21:** `intent-golden.v1` is not optional polish. Phase 11 planning must include dataset version/hash ownership and explicit blocking/non-blocking gate semantics for intent, slot, clarification, and safety-route tests.
- **D-22:** M6 is a release gate for enabling safety-sensitive confidence-assisted routing, not a Phase 12 migration phase. Phase 11 must preserve the mapping from its artifacts to the M6 release checklist.
- **D-23:** Critical classes `critical_write`, `approval_decision`, `appeal_or_unban`, and `complaint_escalation` require per-class coverage. Each class must meet the coverage manifest minimum before it can pass; pooled metrics cannot substitute for per-class gates.
- **D-24:** Wilson gate output must use the spec-defined one-sided 95% Wilson false-negative upper bound and fixed gate status precedence: coverage missing/incomplete/invalid, below per-class minimum, false negatives present, Wilson upper exceeded, then passed. Insufficient sample size must produce `statistical_gate_not_demonstrated`, not pass.

### Targeted Amendment: Intent Consistency Manifest
- **D-25:** Phase 11 must maintain a machine-readable intent consistency manifest, but it is not a runtime `IntentRegistry` and must not become the source of truth for runtime routing.
- **D-26:** The manifest checker must verify every ordinary-chat taxonomy intent against the source-of-truth tables: §11.2 precedence, §11.3 required slots, §9.3 intent-level routing, evidence sufficiency coverage where applicable, and `intent-golden.v1` positive/negative examples.
- **D-27:** `small_talk` and `unsupported` may set `in_evidence_table=false` only when tests also prove they are exempt because they route directly via the intent-level routing table and do not enter `route_after_investigate`.
- **D-28:** CI/contract tests must fail on missing manifest coverage, stale dataset/hash metadata, or manifest claims that are not backed by the corresponding source-of-truth tables.

### Targeted Amendment: Deferred Register Carry-Forward
- **D-29:** GAD-02 is a Phase 11 planning input: future new intents are allowed only through an explicit admission rule covering `risk_level`, `response_mode`, `tool_allowlist`, `bounded_loop_allowed`, `max_iterations`, `routing_precedence`, and audit/replay requirements. No new intent may inherit those fields by default or be batch-enabled.
- **D-30:** GAD-03 is a Phase 11 planning input: current MVP should confirm existing coverage for `policy_qa`, order/business fact QA, and `advise` / support advice terminal paths. Phase 11 must not add a new generic QA intent or change response mode just to represent these already-covered read-only endpoints.
- **D-31:** Any future multi-step read-only QA expansion remains a separate deferred option and must re-apply GAD-01 guardrails plus GAD-02 admission rules before it is promoted into spec or implementation.

### the agent's Discretion
- Exact module names for helper schemas, registry files, manifest location, and test fixture organization may follow existing codebase conventions, as long as source-of-truth boundaries and safety tests remain explicit.
- Exact confidence thresholds may start from `docs/contract-spec.md` defaults; tuning is allowed only through golden/eval evidence and must not authorize action routing by confidence alone.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Normative Intent and Routing Contracts
- `docs/contract-spec.md` §9.3 — Intent-level routing, gate-level routing, ordinary clarification vs approval `respond` lifecycle separation.
- `docs/contract-spec.md` §9.4 — Node contract table for `intent_classification`, `clarification_gate`, `slot_extraction`, `approval_gate`, and `final_response`.
- `docs/contract-spec.md` §9.5 — Router contract table, especially `route_after_intent`, `route_after_slots`, and untrusted ordinary-chat approval decision behavior.
- `docs/contract-spec.md` §9.6 — Trusted approval API / inbox command entry and why ordinary chat cannot create approval decisions.
- `docs/contract-spec.md` §10.1 and §10.4 — AgentState lifecycle and `IntentResultV3 -> AgentState` mapping; explicit adapter required, no whole-object merge, calibrated confidence stays in eval metadata.
- `docs/contract-spec.md` §11.1-§11.3 — Taxonomy, precedence, multi-intent policy, and required-slot table.
- `docs/contract-spec.md` §11.4 — Confidence thresholds, calibration plan, M6 release gate, per-class coverage, and one-sided Wilson false-negative gate semantics.
- `docs/contract-spec.md` §11.5-§11.6 — Ordinary clarification output shape and structured `IntentResultV3` output schema.
- `docs/contract-spec.md` §11.7 — Intent consistency manifest semantics, source-of-truth verification, evidence-table exemptions, and CI failure rules.

### Phase and Evaluation Inputs
- `docs/agent-architecture-phase-decomposition.md` — Phase 11 ownership and acceptance gate: intent golden set, confidence/slot clarification tests, and ordinary chat cannot create trusted approval decision.
- `docs/migration-plan.md` — Phase 11 migration row: intent precedence table, confidence calibration hooks, clarification request id, prompt/schema split, rollback constraints.
- `docs/eval-test-plan.md` — Intent precedence, approval inbox, ordinary-chat forbidden behavior, and safe-route evaluation expectations.
- `.planning/DEFERRED-DECISIONS.md` — GAD-02 intent taxonomy admission rule and GAD-03 existing read-only QA coverage; both are Phase 11 planning inputs.
- `.planning/phases/10-state-lifecycle-routing-migration/10-CONTEXT.md` — Phase 10 graph and router foundation; `clarification_gate` and `session_memory_load` were intentionally minimal.
- `.planning/phases/10-state-lifecycle-routing-migration/10-05-SUMMARY.md` — Live graph wiring summary and Phase 11 readiness notes.
- `docs/architecture-overview.md` — Reference comparison table noting partial adoption of `agents-from-scratch-ts` triage, and explicit rejection of email/news workflow copying.

### Reference Constraints Supplied by User
- `agents-from-scratch-ts` triage pattern — Use only as "classify first, then route" structure.
- LangGraph adaptive RAG structured router pattern — Use `BaseModel` + `Literal[...]`; avoid string parsing.
- `agent-inbox` boundary pattern — Keep ordinary clarification separate from approval respond/decision lifecycle.
- Excluded references — customer-support notebook, email prompts, free tool loops, and memory-driven triage preferences are not Phase 11 core inputs.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/schemas.py` — Current `IntentResult` is a small schema with `intent`, `confidence`, and `reasoning`; Phase 11 should evolve it into the V3 schema rather than adding ad hoc dict parsing.
- `src/agent/nodes/classify_intent.py` — Already uses LangChain structured output with Pydantic, but currently writes only `current_intent` / `last_intent`. This is the main adapter seam for V3 state mapping.
- `src/agent/prompts.py` — Current intent prompt has old intent names including `approval_request`; Phase 11 must replace/guard this so LLM output cannot express trusted approval decisions.
- `src/agent/state.py` — Already has Phase 10 fields for `primary_intent`, `requested_operation`, `session_memory`, and approval state. It does not yet expose typed `required_slots`, `candidate_slots`, `routing_hints`, `intent_confidence`, or `clarification_request` fields in the implementation.
- `src/agent/nodes/clarification_gate.py` — Phase 10 safe fallback stub. Phase 11 owns the full ordinary clarification request output.
- `src/agent/nodes/session_memory_load.py` — Empty adapter with `continuity_claimed=False`; Phase 11 can call it for shape compatibility but cannot claim real session continuity.
- `src/agent/routing.py` — Contains `route_after_investigate` only. Phase 11 should add total, deterministic `route_after_intent` and `route_after_slots` here or in the local routing pattern.
- `src/agent/graph.py` — Currently wires `classify_intent -> session_memory_load -> extract_slots -> investigate` unconditionally. Phase 11 must introduce conditional routing after intent and slots.

### Established Patterns
- Agent tests use fake LLMs and direct state fixtures under `tests/agent/test_nodes/` and `tests/agent/test_graph.py`.
- Router tests should remain pure and state-only; no LLM, tool, repository, or network calls inside routers.
- Full-graph tests patch injected seams rather than service internals.

### Integration Points
- `classify_intent` should write validated V3 fields into AgentState through an explicit adapter.
- `route_after_intent` should decide between `clarification_gate`, `final_response`, `investigate`, and `session_memory_load` based on validated ordinary-chat fields and deterministic safety precedence.
- `route_after_slots` should evaluate `RequiredSlotExpression` against `extracted_slots` and allowed `session_memory.active_slots`; missing slots route to `clarification_gate`.
- `clarification_gate` should produce ordinary clarification output without exposing permission/tool errors and without touching approval lifecycle fields.
</code_context>

<specifics>
## Specific Ideas

- Build `intent-golden.v1` and an intent consistency manifest in Phase 11, not as a later polish item.
- Cover taxonomy, precedence conflicts, required-slot expressions, low-confidence clarification, safe-route cases, and ordinary-chat approval boundary cases in golden tests.
- `11-01` should include the explicit `IntentResultV3 -> AgentState` adapter contract and tests proving no whole-object merge, no calibrated-confidence overwrite, and no candidate-slot completeness shortcut.
- `11-05` should include both the manifest checker and eval artifact requirements: dataset version/hash, coverage manifest hash, per-class sample counts, Wilson gate fields, and `statistical_gate_not_demonstrated` output when coverage is insufficient.
- `11-05` should treat GAD-02/GAD-03 as carry-forward checks: future intent admission fields are documented/test-covered, and existing read-only QA terminal paths are confirmed without adding a generic QA intent.
- The plan should include a lightweight gap check after planning: `$gsd-list-phase-assumptions 11` or stricter `$gsd-review 11`.
- Planner should avoid turning reference repos into implementation sources. They provide structural constraints only.
</specifics>

<deferred>
## Deferred Ideas

- Trusted approval lifecycle, approval `respond` / `needs_info` resume, approval version CAS, and old-revision invalidation remain Phase 13.
- PostgreSQL-authoritative session memory CAS and safe slot inheritance remain Phase 12. Redis, if introduced, is only a non-authoritative hot cache. Phase 11 may define deterministic slot expression evaluation but should not claim real continuity.
- ActionSafetySnapshot, durable action draft binding, demo action executor boundary, and external execution remain later phases.
- Free tool loop for write/actions remains explicitly out of scope.
</deferred>

---

*Phase: 11-intent-clarification*
*Context gathered: 2026-06-14*
