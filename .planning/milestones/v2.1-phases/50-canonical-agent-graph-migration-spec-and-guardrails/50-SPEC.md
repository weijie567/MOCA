# Phase 50: Canonical Agent Graph Migration Spec and Guardrails — Specification

**Created:** 2026-07-06
**Ambiguity score:** 0.08 (gate: <= 0.20)
**Requirements:** 11 locked

## Goal

Create a binding migration charter that keeps all post-Phase 50 Agent Graph phases aligned on one simple canonical runtime graph, with explicit guardrails that forbid final legacy aliases, dual active routes, or unclear graph node ownership.

## Background

The current runtime graph in `src/agent/graph.py` still registers a legacy/canonical mixed chain:

`receive_request -> classify_intent -> session_memory_load -> extract_slots -> long_term_memory_retrieve -> investigate -> rag_context_build -> generate_recommendation -> claim_verify -> assess_risk_and_approval -> approval_gate/action_draft/final_response`.

The accepted target architecture is now documented in `docs/target-agent-platform-architecture-plan.md` §6.1 and `docs/contract-spec.md` §9 as a 15-node canonical runtime graph:

1. `receive_request`
2. `safety_pre_route`
3. `session_context_load`
4. `contextual_intent_resolve`
5. `slot_resolution_gate`
6. `memory_context_load`
7. `investigate`
8. `rag_context_build`
9. `recommendation_generation`
10. `claim_verify`
11. `risk_gate`
12. `approval_gate`
13. `action_draft`
14. `clarification_gate`
15. `final_response`

`slot_extraction` is intentionally not a final registered graph node. Slot candidate extraction is an internal capability of `contextual_intent_resolve` / `slot_resolution_gate`; the registered route/eval/replay boundary is `slot_resolution_gate`.

Phase 49 already migrated `investigate` to a bounded read-only ReAct planner main path with deterministic fallback. Post-Phase 50 migration work must not re-plan "implement ReAct investigate"; it should preserve and harden that state while migrating the outer graph to the canonical node set above.

## Requirements

1. **Source hierarchy**: Phase 50 must define which documents guide future graph migration and how conflicts are handled.
   - Current: `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, historical Section 9 drafts, README docs, and current-source diagrams can be read as competing authorities if not labeled.
   - Target: Future phases treat `docs/contract-spec.md` §9 as the primary accepted contract reference, `docs/target-agent-platform-architecture-plan.md` §6.1 as the readable target architecture view, and this Phase 50 SPEC as the migration execution charter. Current-source docs describe current implementation only.
   - Acceptance: This SPEC contains a "Source Hierarchy and Conflict Protocol" section, and future phase plans can cite that section instead of inventing their own source-of-truth rules.

2. **Exact canonical node set**: Phase 50 must lock the final runtime graph to exactly the 15 registered nodes listed in the Background section.
   - Current: The source graph registers legacy nodes such as `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `generate_recommendation`, and `assess_risk_and_approval`.
   - Target: The final runtime graph registers only the 15 canonical node names for the main graph. `START`, `END`, `route_after_*` routers, `investigate` internal loop steps, and lifecycle concerns do not count as registered runtime graph nodes.
   - Acceptance: A final architecture/static test can enumerate `StateGraph.add_node(...)` registrations and prove the active main graph node set equals the 15-name list exactly.

3. **Node-internal and lifecycle exclusions**: Phase 50 must prevent helper capabilities from becoming accidental graph nodes.
   - Current: Older drafts and discussion can imply `slot_extraction`, `normalize_input`, `memory_write`, `trace_close`, or `action_execution` are peer graph nodes.
   - Target: `normalize_input` is internal to `receive_request`; slot candidate extraction is internal to `contextual_intent_resolve` / `slot_resolution_gate`; `memory_write` and `trace_close` are post-response or lifecycle concerns; `action_execution` is a future external execution extension after `action_draft`, not part of the current runtime graph.
   - Acceptance: This SPEC explicitly lists these exclusions, and future phase plans must fail review if they add any of them as current main-chain registered graph nodes without first changing `docs/contract-spec.md` and this SPEC.

4. **Current-to-target migration matrix**: Phase 50 must provide the implementation equivalence map that all later phases use.
   - Current: Legacy names map to target concepts through scattered documentation and `src/agent/graph_vocabulary.py`.
   - Target: This SPEC records the canonical mapping from current runtime names to target names, their current status, and the migration/deletion expectation.
   - Acceptance: The "Current-to-Target Matrix" section contains every final target node and every legacy runtime node that must disappear or be absorbed by final cutover.

5. **No final migration debt**: Phase 50 must define a hard final gate that disallows active compatibility aliases, dual graph paths, and legacy registered node names after migration completion.
   - Current: `graph_vocabulary.py` records compatibility aliases, and current source graph still routes through legacy names.
   - Target: Temporary aliases may exist only inside named migration phases. The final cutover phase must delete or internalize legacy graph nodes, remove active dual routes, and leave no active runtime dependency on legacy graph node names.
   - Acceptance: The "Final No-Debt Gate" section lists concrete `rg` / static-test checks for legacy node registrations, router route names, imports, and graph vocabulary compatibility aliases.

6. **Downstream phase sequence**: Phase 50 must define dependency order for the full migration so later phase plans do not reorder risky boundaries.
   - Current: The target graph is clear, but implementation work could be planned in inconsistent order.
   - Target: Future phases proceed in dependency order: baseline guardrails, `safety_pre_route`, `session_context_load` before intent, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `recommendation_generation`, `risk_gate` / `approval_gate` canonicalization, final graph cutover, and no-debt cleanup.
   - Acceptance: This SPEC contains a "Required Downstream Phase Order" section; any later plan that changes the order must record the reason and update this SPEC before implementation.

7. **Temporary compatibility policy**: Phase 50 must define when temporary aliases are allowed and what metadata they must carry.
   - Current: Compatibility aliases exist without a single deletion policy for this migration.
   - Target: A temporary alias is allowed only when a phase names its owner, target deletion phase, validation coverage, trace projection behavior, and reason it cannot be removed immediately.
   - Acceptance: Later phase plans must include a compatibility table for any alias they introduce or preserve, and the final no-debt phase must close every row.

8. **Validation matrix**: Phase 50 must define the test families that must exist before final migration completion.
   - Current: Existing tests cover many subsystems, but there is no single canonical graph migration validation matrix.
   - Target: Later plans must create or update tests covering graph node set, route totality, safety pre-route, contextual intent, slot provenance, memory authority, investigate ReAct preservation, RAG/claim fail-closed behavior, risk/approval separation, action draft safety, and full graph smoke/replay.
   - Acceptance: This SPEC contains a "Validation Matrix" section with pass/fail test categories and approved MOCA test command requirements.

9. **LLM authority and trust boundaries**: Phase 50 must lock where LLM output can influence behavior and where deterministic gates must remain authoritative.
   - Current: `classify_intent` is thick, and future refactors could accidentally let LLM output select graph routes, satisfy slots, mark evidence verified, or lower risk.
   - Target: Only `investigate` internal bounded read loop may let a planner LLM choose the next read/retrieval tool. `contextual_intent_resolve` and slot extraction produce candidates only; graph routes, slot satisfaction, evidence verification, risk, approval, and action draft decisions remain deterministic gates.
   - Acceptance: This SPEC contains an "Authority Matrix" section, and future phase reviews must treat violations as blockers.

10. **Phase 49 baseline lock**: Phase 50 must prevent future plans from treating `investigate` ReAct migration as undone.
    - Current: Some older docs still described `investigate` as legacy deterministic, while current source and Phase 49 summaries show bounded read-only ReAct is the main path with deterministic fallback.
    - Target: Future graph migration phases preserve the Phase 49 ReAct main path and only plan hardening/canonical integration work around trace, operation identity, and outer graph boundaries.
    - Acceptance: This SPEC names Phase 49 as implemented-with-limitations, not unimplemented; later plans that touch `investigate` must list which Phase 49 invariant they preserve.

11. **Documentation synchronization**: Phase 50 must define which docs must be updated by any graph migration phase so users do not face multiple conflicting architecture stories.
    - Current: The repo contains target architecture docs, current-source diagrams, contract docs, overview docs, older drafts, and planning ledgers.
    - Target: Any future phase that changes graph node names, route boundaries, or authority semantics must update `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, current architecture docs, and `.planning/ARCHITECTURE-DEBT.md` / relevant phase artifacts consistently.
    - Acceptance: This SPEC contains a documentation sync checklist, and future phase DONE criteria must include it when graph semantics change.

## Boundaries

**In scope:**
- Create Phase 50 as the migration charter phase for canonical Agent Graph migration.
- Write this SPEC with locked requirements, boundaries, constraints, acceptance criteria, source hierarchy, migration matrix, validation matrix, and no-debt gate.
- Register Phase 50 in `.planning/ROADMAP.md`, `.planning/STATE.md`, and `.planning/REQUIREMENTS.md`.
- Record the Phase 50 charter in `.planning/ARCHITECTURE-DEBT.md` so later work has a stable planning reference.
- Correct planning-state drift discovered while creating this SPEC, including marking Phase 49 GAD-01 implementation as complete in requirements.

**Out of scope:**
- Runtime graph code changes — Phase 50 is a planning/spec guardrail phase.
- Creating `safety_pre_route`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `recommendation_generation`, or `risk_gate` implementations — these belong to downstream implementation phases.
- Deleting legacy runtime nodes or compatibility aliases — deletion belongs to the final migration cutover/no-debt phase.
- Rewriting `investigate` ReAct internals — Phase 49 already delivered that main path.
- Adding `slot_extraction` as a graph node — rejected by the accepted target architecture.
- Introducing external action execution after `action_draft` — future extension, not current runtime graph scope.

## Constraints

- `docs/contract-spec.md` is the primary accepted contract reference, but it is a living contract. If implementation planning finds it wrong or ambiguous, the phase must stop, record the conflict, and either update the spec or record an explicit scoped implementation limitation.
- `docs/target-agent-platform-architecture-plan.md` §6.1 is the readable target graph view. It must stay aligned with `docs/contract-spec.md` §9.
- Graph-level route decisions must remain deterministic. LLM output may produce candidates but cannot choose graph nodes.
- Memory remains contextual-only. Memory may guide context or investigation but cannot become policy evidence, current business facts, approval/action authority, or replay truth.
- RAG/evidence, claim verification, risk, approval, and action draft boundaries must fail closed.
- All MOCA pytest commands in future phase plans must use `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid verification.
- The final migration state must be simple and debt-free: no active legacy graph node names, no active dual runtime path, no compatibility aliases required for the main graph.

## Source Hierarchy and Conflict Protocol

1. `docs/contract-spec.md` §9 is the primary accepted contract reference for target graph semantics.
2. `docs/target-agent-platform-architecture-plan.md` §6.1 is the canonical readable graph diagram and explanation.
3. This Phase 50 SPEC is the execution charter for all post-Phase 50 migration phases.
4. `src/agent/graph.py`, `src/agent/routing.py`, and node implementations are current implementation facts, not target authority.
5. `docs/current-langgraph-architecture.md` describes current source graph only.
6. Historical drafts such as `.planning/SECTION-9-AGENTIC-DRAFT.md` and `.planning/SECTION-9-DRAFT-REVIEW.md` are historical references only.

If a future phase finds a conflict:

1. Confirm the conflict against current source and the docs above.
2. Classify it as either spec/doc error or implementation limitation.
3. Do not silently diverge.
4. If the spec is wrong, update `docs/contract-spec.md` and dependent docs in the same phase plan with review.
5. If implementation is intentionally partial, add an explicit MVP scope/limitation note and target cleanup phase.

## Current-to-Target Matrix

| Target node | Current runtime equivalent | Current status | Final expectation |
|-------------|----------------------------|----------------|-------------------|
| `receive_request` | `receive_request` | Runtime node exists | Keep canonical name |
| `safety_pre_route` | `classify_intent` pre-route logic / routing hints | Missing explicit node | Extract as registered node |
| `session_context_load` | `session_memory_load`; `src/agent/nodes/session_context_load.py` also exists | Wrong graph position / mixed naming | Use canonical node before intent |
| `contextual_intent_resolve` | `classify_intent` | Thick legacy node | Replace with canonical node and delete active legacy graph node |
| `slot_resolution_gate` | `extract_slots` + slot helpers + `route_after_slots` | Legacy combined behavior | Replace with canonical gate; no final `slot_extraction` node |
| `memory_context_load` | `long_term_memory_retrieve` / reviewed memory context loaders | Legacy naming and policy boundary | Replace with canonical node after slot resolution |
| `investigate` | `investigate` | Phase 49 ReAct main path implemented with limitations | Keep node; harden trace/operation limitations only |
| `rag_context_build` | `rag_context_build` | Runtime node exists | Keep canonical name |
| `recommendation_generation` | `generate_recommendation` | Legacy name mapped by graph edge labels | Rename/cut over to canonical node |
| `claim_verify` | `claim_verify` | Runtime node exists | Keep canonical name |
| `risk_gate` | `assess_risk_and_approval` | Semantic alias / legacy node name | Replace with canonical node and separate approval state machine responsibility |
| `approval_gate` | `approval_gate` | Runtime node exists, pending loop present | Keep canonical name and preserve pending/trusted resume behavior |
| `action_draft` | `action_draft` | Runtime node exists | Keep canonical name |
| `clarification_gate` | `clarification_gate` | Runtime node exists | Keep canonical name |
| `final_response` | `final_response` | Runtime node exists | Keep canonical name |

Legacy runtime nodes that must not remain active in the final main graph: `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `generate_recommendation`, `assess_risk_and_approval`.

Legacy routers that must be renamed, absorbed, or removed from active final route vocabulary: `route_after_intent`, `route_after_slots`, route values pointing to `session_memory_load`, `long_term_memory_retrieve`, `generate_recommendation`, or `assess_risk_and_approval`.

## Required Downstream Phase Order

The exact phase numbers may be adjusted only if roadmap sequencing changes, but the dependency order is locked:

1. **Phase 51 — Baseline graph guardrails and migration matrix tests**: add static graph/node vocabulary tests and current-vs-target projection checks before runtime rewiring.
2. **Phase 52 — `safety_pre_route` extraction**: make request-risk pre-route explicit before memory or intent context enrichment.
3. **Phase 53 — session context before intent and `contextual_intent_resolve` cutover**: move `session_context_load` before intent resolution and replace thick `classify_intent` as the active graph node.
4. **Phase 54 — `slot_resolution_gate` cutover**: absorb `extract_slots` into candidate extraction / slot gate semantics and expose provenance.
5. **Phase 55 — `memory_context_load` cutover**: replace `long_term_memory_retrieve` active graph naming and lock contextual-only memory authority labels.
6. **Phase 56 — `recommendation_generation` canonicalization and RAG/claim fail-closed status alignment**: remove `generate_recommendation` as active node name and align evidence/claim state semantics.
7. **Phase 57 — `risk_gate` / `approval_gate` canonicalization**: replace `assess_risk_and_approval`, preserve approval pending/trusted resume, and keep risk vs approval responsibilities separate.
8. **Phase 58 — canonical graph cutover and no-debt cleanup**: remove active legacy node names, compatibility aliases, route values, imports, and docs drift.

If a downstream phase discovers a dependency that requires reordering, it must update this section and record the reason before implementation.

## Temporary Compatibility Policy

Temporary compatibility is allowed only when all fields below are recorded in the phase plan:

| Field | Required content |
|-------|------------------|
| Legacy surface | Exact node/router/function/import/state key preserved |
| Canonical owner | Target node or service that owns the final semantics |
| Reason | Why it cannot be deleted in the same phase |
| Trace projection | How traces/events map to canonical names while compatibility exists |
| Validation | Tests proving no dual active behavior or semantic drift |
| Delete phase | Named phase where the compatibility surface must be removed |

Compatibility surfaces may not become permanent. The final no-debt cleanup phase must close every compatibility row or explicitly update this SPEC and `docs/contract-spec.md` with a reviewed exception.

## Authority Matrix

| Boundary | LLM allowed authority | Deterministic authority |
|----------|-----------------------|-------------------------|
| `safety_pre_route` | None | Request-risk / unsafe / unsupported / untrusted approval pre-route |
| `contextual_intent_resolve` | Intent, operation, ambiguity, and candidate slot suggestions | IntentPolicyEngine / SlotPolicyRegistry adjudication and route hints |
| `slot_resolution_gate` | Candidate extraction may assist | Slot satisfaction, inheritance, invalidation, stale/conflict handling |
| `memory_context_load` | None required | Memory usage labels and contextual-only authority |
| `investigate` | Planner may choose next read/retrieval tool within allowlist | Tool allowlist, schema validation, resource limits, no write tools |
| `rag_context_build` | None required | Evidence package construction and fail-closed status |
| `recommendation_generation` | Draft text, candidate claims, candidate proposed action | Cannot mark evidence verified or skip claim/risk gates |
| `claim_verify` | May assist claim extraction only if bounded by verifier | Claim support, blocked claims, safe refs |
| `risk_gate` | None for final risk lowering | Blocked/manual review/approval required/auto draft decision |
| `approval_gate` | None | Trusted approval request/resume state machine |
| `action_draft` | None for side effects | Draft-only action boundary and safety snapshot binding |

## Validation Matrix

Future implementation phases must build toward these gates:

| Test family | Required proof |
|-------------|----------------|
| Graph node set | Active `StateGraph.add_node(...)` names equal the 15 canonical names exactly |
| Route totality | Every `route_after_*` returns only canonical route values or terminal safe fallback |
| Safety pre-route | Unsafe/unsupported/untrusted approval chat cannot enter memory, investigate, approval, or action paths |
| Contextual intent | Same-thread short replies use session context; LLM output cannot directly choose graph route |
| Slot provenance | Explicit current-turn, inherited, invalidated, conflicting, stale, resolved, and missing slots are trace-visible |
| Memory authority | Memory remains contextual-only and cannot satisfy evidence/business/approval/action/replay authority |
| Investigate ReAct preservation | Phase 49 allowlist, loop-local slots, projection boundary, fallback, and resource limits still pass |
| RAG/claim fail-closed | Missing, stale, conflict, unauthorized, or unsupported evidence/claims cannot produce unsafe material claims or action drafts |
| Risk vs approval | `risk_gate` decides blocked/manual/approval/auto-draft; `approval_gate` handles pending/trusted resume only |
| Final no-debt | Legacy graph node names, active compatibility aliases, and dual route values are absent |

Approved command pattern for pytest verification: `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or `.venv/bin/pytest ...`.

## Final No-Debt Gate

The migration is not complete until all of these are true:

- [ ] The active main graph registers exactly the 15 canonical node names.
- [ ] `src/agent/graph.py` has no active `add_node(...)` registration for `classify_intent`, `session_memory_load`, `extract_slots`, `long_term_memory_retrieve`, `generate_recommendation`, or `assess_risk_and_approval`.
- [ ] Active router return values do not point to legacy node names.
- [ ] Active imports in `src/agent/graph.py` do not import legacy graph node functions as graph nodes.
- [ ] `graph_vocabulary.py` no longer marks migration-era legacy node aliases as active runtime compatibility surfaces for the main graph.
- [ ] Trace/replay/eval projection uses canonical node names without requiring legacy-to-target interpretation for current runs.
- [ ] Docs no longer describe legacy names as target runtime nodes.
- [ ] Architecture debt entry for this migration is moved from open/planned to fixed/verified, with any non-runtime historical references explicitly labeled.

Suggested final static checks:

```bash
rg -n "add_node\\(\"(classify_intent|session_memory_load|extract_slots|long_term_memory_retrieve|generate_recommendation|assess_risk_and_approval)\"" src/agent
rg -n "\"(session_memory_load|long_term_memory_retrieve|generate_recommendation|assess_risk_and_approval)\"" src/agent/graph.py src/agent/routing.py
rg -n "compatibility_alias.*(classify_intent|session_memory_load|extract_slots|long_term_memory_retrieve|generate_recommendation|assess_risk_and_approval)" src/agent/graph_vocabulary.py
```

At final completion, these checks must return no active-runtime hits. Historical docs/tests may keep labeled references only if they are outside current runtime behavior.

## Documentation Sync Checklist

Any downstream phase that changes graph semantics must check whether each file below needs an update:

- `docs/contract-spec.md`
- `docs/target-agent-platform-architecture-plan.md`
- `docs/current-langgraph-architecture.md`
- `docs/architecture-overview.md`
- `docs/agent-architecture-routing-explanation.md`
- `docs/rag-architecture-spec.md`
- `README.md`
- `.planning/ARCHITECTURE-DEBT.md`
- `.planning/DEFERRED-DECISIONS.md`
- Current phase `PLAN.md`, `SUMMARY.md`, `VALIDATION.md`, and review artifacts

If a file is intentionally not updated, the phase summary must say why.

## Acceptance Criteria

- [ ] `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` exists and contains all 11 locked requirements.
- [ ] The SPEC names the final runtime graph as exactly 15 registered canonical nodes.
- [ ] The SPEC explicitly rejects `slot_extraction` as a final registered graph node.
- [ ] The SPEC treats Phase 49 `investigate` ReAct as implemented-with-limitations, not pending.
- [ ] The SPEC contains current-to-target matrix coverage for every target node and every legacy runtime node that must disappear.
- [ ] The SPEC contains a required downstream phase order and a temporary compatibility policy.
- [ ] The SPEC contains a final no-debt gate with concrete static checks.
- [ ] `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, and `.planning/ARCHITECTURE-DEBT.md` reference Phase 50 consistently.
- [ ] Phase 50 does not modify runtime source code.
- [ ] `git diff --check` passes.

## Ambiguity Report

| Dimension | Score | Min | Status | Notes |
|-----------|-------|-----|--------|-------|
| Goal Clarity | 0.95 | 0.75 | met | User explicitly asked for simple, clear architecture and a guiding spec before many phases. |
| Boundary Clarity | 0.92 | 0.70 | met | Phase 50 is spec/guardrails only; runtime migration is out of scope. |
| Constraint Clarity | 0.88 | 0.65 | met | 15-node target, no `slot_extraction` node, no final migration debt, Phase 49 preserved. |
| Acceptance Criteria | 0.90 | 0.70 | met | Pass/fail file, node-set, no-debt, and diff-check criteria listed. |
| **Ambiguity** | **0.08** | <=0.20 | met | Weighted clarity passes gate. |

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | What is the delta between current graph and target graph? | Current graph is legacy/canonical mixed; target graph is 15 registered canonical nodes. |
| 2 | Simplifier | Should `slot_extraction` be its own graph node? | No. Slot candidate extraction is internal; `slot_resolution_gate` is the graph boundary. |
| 3 | Boundary Keeper | Should `investigate` be reimplemented? | No. Phase 49 already landed bounded read-only ReAct main path with limitations. |
| 4 | Failure Analyst | What would make the migration fail architecturally? | Ending with dual routes, compatibility aliases, inconsistent node names, or docs disagreeing on the target. |
| 5 | Seed Closer | Do we need a spec to guide many future phases? | Yes. Phase 50 is the migration charter; later implementation phases must follow it or update it explicitly. |

---

*Phase: 50-canonical-agent-graph-migration-spec-and-guardrails*
*Spec created: 2026-07-06*
*Next step: plan downstream implementation phases in the required order, starting with baseline graph guardrails and migration matrix tests.*
