# Phase 10: State Lifecycle + Routing Migration - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 10 delivers three things together:

1. **AgentState lifecycle enforcement** — trusted-writer rules, reset/merge semantics, persistence, cross-scope isolation (STATE-01, STATE-02).
2. **Deterministic router totality** — every router is deterministic, side-effect-free, total for valid state, and routes invalid/unsafe state to an explicit safe fallback (ROUTE-01, ROUTE-02).
3. **Investigation segment agentic merge** — collapse the three read-only investigation nodes (`business_context_fetch` / `policy_evidence_retrieve` / `case_memory_retrieve`) into a single registered `investigate` node running a bounded tool loop, with a single `route_after_investigate`.

**Scope note (deviation — see Deferred/Deviations):** The ROADMAP Phase 10 goal text names only items 1–2 (state lifecycle + router totality). Item 3 (investigate agentic merge) is a scope expansion authorized this session by升级 GAD-01 to OPEN and the `§9 agentic draft`. It is in-scope for Phase 10 by explicit decision, not by ROADMAP literal text.

**Hard red line (unchanged, do not weaken):** Write-action side (refund/coupon/ban/unban/close_ticket) stays deterministic + human-reviewed. Write tools are never called directly by the LLM. The bounded tool loop exists ONLY on the read-only investigation side and must never reach a write tool or bypass `risk_gate` / `approval_gate` / `action_draft` / `action_execution`.
</domain>

<decisions>
## Implementation Decisions

### Investigate node structure (head decision)
- **D-01:** Phase 10 absorbs the investigation merge. The three investigation nodes collapse into one registered `investigate` node; they become internal conceptual sub-capabilities still callable inside the loop. Externally `investigate` is a single deterministic node (fixed in/out edges + single `route_after_investigate`).
- **D-02:** Rationale for merge (not three-nodes-each-looping): the target scenario is cross-data-source dynamic investigation ("check logistics, then decide whether to pull policy") — three fixed-chained nodes cannot express cross-node dynamics at the router layer. See `docs/contract-spec.md` §9 draft and DEFERRED-DECISIONS.md GAD-01 structural decision.

### Bounded tool loop guardrails (normative, none droppable)
- **D-03:** `max_iterations` hard cap, enforced; on hit, lifecycle status stays `completed` but `termination_reason=max_iterations_reached` is written.
- **D-04:** Loop allowlist contains read-only tools only (union of the three old node allowlists: get_order, get_refund_case, get_ticket, get_logistics, get_merchant_risk, search_policy, search_sop, search_case_memory). Loop never calls allowlist-external or any write tool.
- **D-05:** Every loop tool/RAG call emits an independent trace event (§17.2).
- **D-06:** Loop produces only `proposed_action` candidates; never触达 write tool; never bypasses risk/approval/executor gates.
- **D-07:** Externally deterministic — loop does not change the node's outward routing contract.

### permission denied semantics
- **D-08:** Fine-grained, NOT one-shot-to-final. permission denied blocks only the part of the answer that depends on the denied resource; facts legitimately obtained in the same loop are preserved (enterprise RBAC: an agent may be authorized for orders but not merchant-risk). Denied resources must not appear in the reply and must not leak via inference. TrustedContext scope checks remain (`docs/contract-spec.md:935-937`). This replaces the §9 draft's placeholder one-shot `permission denied -> final`.

### RAG vs tool event classification (Phase 15 contract)
- **D-09:** Classify by call nature, not by "inside the loop." `search_policy` / `search_sop` → `rag_retrieval_*` events; `get_*` → `tool_call_*` events. A single operation does NOT emit both event families (avoids Phase 15 started/terminal pairing ambiguity).
- **D-10:** `search_case_memory` classification: it is vector retrieval but semantically case-memory. **Decided: emit `rag_retrieval_*`** (it is a retrieval call by nature; consistent with D-09's "by call nature"). Planner/Phase 15 to confirm pairing.

### termination_reason as canonical state
- **D-11:** `termination_reason` is added to §9.4 `investigate` State writes AND §10.1 canonical field registry, reset each turn. Rationale: §9.5 `route_after_investigate` Reads already lists it — the router must read it from state, and routers do not read trace payload. So it cannot live only in `redacted_payload`.

### max_iterations configuration shape
- **D-12:** Configured per-intent (GAD-02 already defines `max_iterations` as a required intent-admission field) + a global hard ceiling backstop. Default 3 / ceiling 5 are **discussion parameters only, NOT normative** — final values set during planning/eval. NOT per-tenant (MVP over-design; pollutes replay).

### Claude's Discretion
- **CD-01:** `long_term_memory_retrieve` stays an independent node (`fixed -> investigate`), NOT merged into the loop. Reasons: its identity/scope semantics belong to Phase 16 (memory_identity.v1/tombstone), a different contract from read-only investigation allowlist; it is a pre-load, not "fetch-on-demand during investigation"; Phase 16 is deferred-beyond-MVP. Planner may proceed on this basis unless evidence contradicts.
- **CD-02:** `iteration` annotation lands in the Phase 10 emitter at first emit (not deferred to Phase 15), placed in `redacted_payload` (not envelope top-level). Rationale: §17.2 principle "carry at first emit, Phase 15 must not fabricate"; iteration is a runtime fact backfill cannot reconstruct. Non-schema-breaking (payload-internal).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 10 agentic merge proposal (primary input — read first)
- `.planning/SECTION-9-AGENTIC-DRAFT.md` — Full v2 draft of the §9/§12.4/§17.2 + §8.4/§10.1/§11.5/§17.3 rewrites for the investigate merge. NON-normative draft; this discussion's decisions refine it. Contains the 12-block coverage, bounded-loop guardrails, and open-question list.
- `.planning/SECTION-9-DRAFT-REVIEW.md` — Codex adversarial review of the draft (4 blockers + 5 warnings + 10 omission points, all adjudicated valid by Claude).
- `.planning/DEFERRED-DECISIONS.md` — GAD-01 (now Status OPEN — the agentic merge authorization), GAD-02 (intent admission fields incl. `bounded_loop_allowed` / `max_iterations`), structural decision block.

### Normative spec (current — to be raised AFTER discuss定稿, NOT during Phase 10 plan unless explicitly promoted)
- `docs/contract-spec.md` §9.0–9.5 — Canonical node/router vocab, node list, state transition, conditional routing, node contract table, router contract table. Current text still names the three old nodes/routers.
- `docs/contract-spec.md` §12.4 — Node-level tool allowlist (three old nodes → to merge into `investigate`).
- `docs/contract-spec.md` §17.2 — ReplayEventV3 / minimal envelope; tool_call_*/rag_retrieval_* are Phase 10-owned (lines 1612,1618); parent_operation_id/attempt are Phase 15 enrichment (1600,1628,1681-1682).
- `docs/contract-spec.md` §8.4 — BusinessContextV1 (`status drives route_after_business_context` → route_after_investigate, line 181).
- `docs/contract-spec.md` §10.1 — AgentState lifecycle matrix + canonical field registry (writers/routers for business_context, policy_evidence, retrieval_status, best_score, last_business_context_refs — lines 548-549, 581-587). evidence_refs writer stays recommendation_generation/citation validator (585,605).
- `docs/contract-spec.md` §11.5 — clarification blocked_nodes example (line 765, contains business_context_fetch).
- `docs/contract-spec.md` §17.3 — trace spans (line 1724, agent.node.business_context_fetch).

### Cross-phase dependency
- `.planning/phases/09-business-tool-facade/09-CONTEXT.md` — Phase 9 facade decisions. ⚠️ Its "drop investigator whitelist / no bounded-investigator caller" lock is OVERRIDDEN by this phase (see Deviations). The BusinessToolService service-layer reuse remains valid; only the "no bounded caller" stance is reversed.
- `docs/agent-architecture-phase-decomposition.md` §1 — Deviation Handling Protocol (status enum, deviation table fields).
- `docs/migration-plan.md:16` — Phase 10 acceptance "不引入自由 ReAct" → reframe to "investigate node allows bounded loop under the three guardrails, still not free ReAct" when promoting spec.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/nodes/load_business_context.py`, `retrieve_policy_evidence.py` — current separate investigation nodes; these collapse into the new `investigate` node logic.
- `src/agent/graph.py` — central routing wiring; where route_after_business_context/route_after_policy_evidence get replaced by route_after_investigate.
- `src/agent/state.py` — AgentState definition; where termination_reason (D-11) and lifecycle/trusted-writer rules land.
- Phase 10 `UnifiedToolManager` — the loop CALLS this single node-facing dispatch path. Manager executors call Phase 9 `BusinessToolService` and Phase 8 `KnowledgeService`; service layers do not rework (only node wiring / who-calls-how-many-times changes).

### Established Patterns
- LangGraph `StateGraph.add_node` / `add_conditional_edges` — registered nodes + deterministic routers.
- Read-only tools already go through facade services (Phase 8/9 contracts).

### Integration Points
- `route_after_intent` / `route_after_slots` now route to `investigate` (was: to business_context_fetch / policy_evidence_retrieve).
- `long_term_memory_retrieve` → `fixed -> investigate` (CD-01).
- `investigate` → `route_after_investigate` → {final_response, clarification_gate, recommendation_generation}.
</code_context>

<specifics>
## Specific Ideas

- The §9 draft (515 lines) is the concrete target text. Planner should treat it as the design contract for the merge, applying this discussion's refinements (D-08 fine-grained permission, D-10 case-memory RAG class, D-11 termination_reason canonical).
- Loop guardrails (D-03..D-07) are the safety contract — they are the demo's safety selling point and must be verifiable, not just asserted.
</specifics>

<deferred>
## Deferred Ideas / Deviations

### Deviations (MUST be recorded — plan-checker will cross-check)
- **P10-DEV-01 (scope expansion):** ROADMAP Phase 10 goal text names only state lifecycle + router totality. The investigate agentic merge is added by this session's authority (GAD-01 OPEN + §9 draft). Type: REQUIRES_BLUEPRINT_UPDATE. Owner: Phase 10. Handling: proceed; ROADMAP goal line should be updated to mention the merge when spec is promoted.
- **P10-DEV-02 (owner drift / prior-phase override):** Phase 9 CONTEXT locked "drop investigator whitelist / no bounded-investigator caller" (made when the agentic line was considered replaced). This phase reverses that stance. Type: OWNER_DRIFT. Owner: Phase 10. Handling: explicitly record the reversal; Phase 9's BusinessToolService service-layer reuse is unaffected — only the "no bounded caller" stance is overridden. The loop is the bounded caller that Phase 9 said wouldn't exist.

### Spec promotion sequencing (not a Phase 10 code task)
- The §9 draft must be raised into `docs/contract-spec.md` (12 blocks) AFTER this discuss定稿 + Codex cross-review, BEFORE Phase 10 implementation plan executes against live spec. The two必须-discuss items (D-08 permission, D-09/10 RAG class) are now resolved; the draft's ⚠️待替换 markers can be finalized.

### Open items handed to planner (from §9 draft open-question list, resolved or assigned)
- max_iterations default/ceiling exact values → planning/eval (D-12 sets shape, not final numbers).
- migration-plan.md:16 "不引入自由 ReAct" acceptance line → reword during spec promotion (noted in canonical_refs).

None of the above is scope creep — all clarify HOW to implement the Phase 10 merge already decided.
</deferred>

---

*Phase: 10-state-lifecycle-routing-migration*
*Context gathered: 2026-06-11*
