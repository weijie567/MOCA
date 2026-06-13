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
- `docs/contract-spec.md` §10.1 and §10.4 — AgentState lifecycle and `IntentResultV3 -> AgentState` mapping.
- `docs/contract-spec.md` §11.1-§11.7 — Taxonomy, precedence, required-slot policy, confidence gates, clarification path, structured output schema, and intent consistency manifest.

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
- The plan should include a lightweight gap check after planning: `$gsd-list-phase-assumptions 11` or stricter `$gsd-review 11`.
- Planner should avoid turning reference repos into implementation sources. They provide structural constraints only.
</specifics>

<deferred>
## Deferred Ideas

- Trusted approval lifecycle, approval `respond` / `needs_info` resume, approval version CAS, and old-revision invalidation remain Phase 13.
- PostgreSQL-backed session memory CAS and safe slot inheritance remain Phase 12. Phase 11 may define deterministic slot expression evaluation but should not claim real continuity.
- ActionSafetySnapshot, durable action draft binding, demo action executor boundary, and external execution remain later phases.
- Free tool loop for write/actions remains explicitly out of scope.
</deferred>

---

*Phase: 11-intent-clarification*
*Context gathered: 2026-06-14*
