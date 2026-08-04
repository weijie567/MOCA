# Phase 55: Memory Context Load Cutover - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning
**Source:** `$gsd-phase-autopilot 55` auto discuss, Phase 50 SPEC, Phase 54 verification, Phase 46-48.1 memory artifacts, current source scan.

<domain>
## Phase Boundary

Phase 55 replaces the active `long_term_memory_retrieve` graph naming with canonical `memory_context_load`, positioned after `slot_resolution_gate` and before `investigate`, while locking all loaded memory as contextual-only.

In scope:

1. Register `memory_context_load` as the active main-chain graph node and route destination for reviewed memory context loading.
2. Ensure `route_after_slot_resolution` can route resolved slot state to `memory_context_load` before `investigate`.
3. Preserve memory authority boundaries: loaded memory can guide context and investigation hints only.
4. Add or tighten output labels for memory usage/source/authority so memory cannot be mistaken for policy evidence, current business fact authority, approval/action authority, or replay truth.
5. Keep Phase 46 session context, Phase 47 reviewed case precedent/CWC, Phase 48 explicit preference-only long-term memory, and Phase 48.1 compatibility boundaries distinct.
6. Record any retained `long_term_memory_retrieve` compatibility surface with owner, reason, trace projection, validation, and delete phase.

Out of scope:

- Phase 56 `recommendation_generation`, RAG, or claim fail-closed alignment.
- Phase 57 `risk_gate` / `approval_gate` canonicalization.
- Phase 58 final removal of all historical graph aliases.
- Destructive renames or drops for `session_memories`, `long_term_memories`, `case_memories`, `case_working_contexts`, memory API paths, config names, or persisted historical traces.
- Changing Phase 45 CWC lifecycle semantics, Phase 46 session-context semantics, Phase 47 reviewed precedent semantics, or Phase 48 preference-only long-term memory policy.

</domain>

<decisions>
## Implementation Decisions

### Active graph naming cutover
- **D-55-01:** Active `StateGraph.add_node(...)` registration must use `memory_context_load`, not `long_term_memory_retrieve`.
- **D-55-02:** `slot_resolution_gate -> route_after_slot_resolution` must map reviewed-memory-needed route values to `memory_context_load`; `memory_context_load` then flows directly to `investigate`.
- **D-55-03:** `long_term_memory_retrieve` may remain only as a non-active compatibility/import wrapper if tests or historical callers still require it; it must not remain an active graph registration or active route destination after Phase 55.
- **D-55-04:** Prefer implementing `memory_context_load` as the canonical node owner over blindly renaming `reviewed_memory_context_retrieve`; the existing reviewed-memory implementation already owns the real load semantics.

### Memory authority and usage labels
- **D-55-05:** All loaded memory surfaces remain `authority_class = "contextual_only"`.
- **D-55-06:** Outputs should carry explicit finite usage/source labels, at minimum distinguishing session continuity, explicit preference memory, reviewed case precedent/case hint, and case working context status where those surfaces are present.
- **D-55-07:** Reviewed memory may guide prompts, context, or `investigate` hints only. It must not create or satisfy `EvidenceRefV1`, `BusinessFactRefV1`, approval decisions, action drafts, action authorization, or replay truth.
- **D-55-08:** Unavailable, missing trusted context, missing scope, denied scope, or service-error memory loads must continue without long-term/case memory and expose explicit skipped/unavailable status rather than fail open.

### Memory layer separation
- **D-55-09:** Preserve Phase 46: `session_context` is same-thread temporary context; legacy `session_memory` may remain fallback/compatibility but cannot become policy/business/action/replay authority.
- **D-55-10:** Preserve Phase 47: reviewed `case_memory` is historical precedent; CWC is active case working state; neither replaces the other.
- **D-55-11:** Preserve Phase 48: published long-term memory is explicit preference-only; broad patterns, policy rules, current business state, and action/approval authority are not long-term memory.
- **D-55-12:** Preserve Phase 48.1: active readers should prefer canonical surfaces, but storage identities, config names, public memory API paths, and historical compatibility wrappers are not deletion targets in this phase.

### Compatibility and validation scope
- **D-55-13:** `graph_vocabulary.py` should make `memory_context_load` the runtime node entry and keep any `long_term_memory_retrieve -> memory_context_load` entry as `compatibility_alias` with Phase 55 reason codes and a named delete phase.
- **D-55-14:** If `llm_outputs["long_term_memory_retrieve"]` is retained for legacy tests/API readers, active canonical metrics must also be written under `llm_outputs["memory_context_load"]`, and the retained key must be documented as compatibility-only.
- **D-55-15:** Static graph baseline tests must change only the Phase 55-owned legacy row. `generate_recommendation` and `assess_risk_and_approval` remain Phase 56/57 active legacy rows until their phases.
- **D-55-16:** Plans must use approved MOCA command entrypoints only: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or verified `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.

### the agent's Discretion
- Exact module shape: a new `src/agent/nodes/memory_context_load.py` wrapper, alias import, or direct canonical export is acceptable if active graph identity and tests are correct.
- Exact usage label field name and enum values, provided labels are finite, test-covered, and do not blur authority boundaries.
- Exact test split, provided graph baseline, routing totality, vocabulary projection, memory boundary, graph smoke, docs/ledger sync, and artifact command scans are covered.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Migration Charter
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - binding CAGM migration charter, target graph, compatibility policy, authority matrix, validation matrix, and no-debt gate.
- `.planning/ROADMAP.md` - Phase 55 goal, CAGM-06 success criteria, and Phase 56-58 boundaries.
- `.planning/REQUIREMENTS.md` - CAGM-06 requirement text and pending status.
- `.planning/phases/54-slot-resolution-gate-cutover/54-VERIFICATION.md` - confirms Phase 54 left `long_term_memory_retrieve` as Phase 55-owned active compatibility destination.

### Memory Layer Contracts
- `.planning/phases/46-session-context-repositioning/46-CONTEXT.md` - same-thread session context boundary and non-authority rules.
- `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-CONTEXT.md` - reviewed case precedent vs CWC boundary.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-CONTEXT.md` - explicit preference-only long-term memory boundary.
- `.planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-RESEARCH.md` - active-reader compatibility cleanup patterns and anti-patterns.
- `.planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-04-SUMMARY.md` - verified retained compatibility surfaces and final guard status.

### Architecture Docs
- `docs/contract-spec.md` §9.4 and §9.5 - `memory_context_load` node/router contract and deterministic route values.
- `docs/contract-spec.md` §13.2-13.6 - memory layer authority, write, storage, CWC, and contextual-only boundaries.
- `docs/target-agent-platform-architecture-plan.md` §6.1 and P2 item 6 - canonical graph position and memory usage/trust labeling target.
- `docs/current-langgraph-architecture.md` - current source snapshot and Phase 55-owned `long_term_memory_retrieve` compatibility row.
- `.planning/ARCHITECTURE-DEBT.md` - architecture debt ledger rows for memory compatibility and CAGM remaining active legacy names.

### Current Source Surfaces
- `src/agent/graph.py` - active graph node registration and edge maps.
- `src/agent/routing.py` - `SLOT_RESOLUTION_ROUTES`, `route_after_slot_resolution`, and reviewed-memory hint routing.
- `src/agent/graph_vocabulary.py` - runtime/compatibility target graph projection.
- `src/agent/state.py` - memory context fields in `AgentState`.
- `src/agent/nodes/long_term_memory_retrieve.py` - current active compatibility wrapper.
- `src/agent/nodes/reviewed_memory_context_retrieve.py` - real reviewed memory/CWC load implementation.
- `src/memory/context_refs.py` - contextual-only memory DTOs and status refs.
- `src/memory/context_service.py` - reviewed memory scope filtering and bundle composition.

### Tests And Verification Anchors
- `tests/architecture/graph_baseline.py`
- `tests/architecture/test_canonical_graph_baseline.py`
- `tests/agent/test_graph.py`
- `tests/test_graph_routing.py`
- `tests/agent/test_intent_routing.py`
- `tests/agent/test_graph_vocabulary.py`
- `tests/agent/test_reviewed_memory_context_retrieve.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `tests/memory/test_reviewed_memory_context_boundary.py`
- `tests/memory/test_phase46_session_context_alignment.py`
- `tests/memory/test_phase47_case_precedent_alignment.py`
- `tests/memory/test_phase48_long_term_preference_alignment.py`
- `tests/memory/test_phase48_1_memory_compat_alignment.py`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reviewed_memory_context_retrieve(...)` already loads reviewed long-term preference memory, reviewed case memory, CWC, status refs, `memory_context`, `memory_context_bundle`, `long_term_memory`, and `case_memory`.
- `MemoryContextService.load_reviewed_memory_context(...)` already fails closed for missing trusted context, missing actor merchant scope, unsupported tenant/global scopes, denied merchant scope, and missing services.
- `MemoryContextBundle`, `ReviewedMemoryContextBundle`, `ReviewedMemoryRef`, `SessionContextLoadStatusV1`, and `CaseWorkingContextLifecycleStatusV1` already carry `authority_class = "contextual_only"`.
- `tests/agent/test_memory_evidence_boundary.py` already proves session/reviewed memory cannot satisfy policy evidence, current business fact, approval/action authority, or replay truth.
- `tests/architecture/graph_baseline.py` already names `long_term_memory_retrieve -> memory_context_load` as the Phase 55-owned migration row.

### Established Patterns
- Graph routers are deterministic and fail closed to clarification/final safe routes.
- Compatibility wrappers can remain if they are not active graph registrations and are recorded in vocabulary/docs/tests.
- Static architecture tests use AST/source extraction rather than brittle string-only scans where possible.
- Memory compatibility work should migrate active readers and graph identities without destructive table/API/config renames.

### Integration Points
- Active graph: `src/agent/graph.py` currently imports and registers `long_term_memory_retrieve`; Phase 55 changes this registration and edge path to `memory_context_load`.
- Router: `src/agent/routing.py` currently returns `long_term_memory_retrieve` when `needs_reviewed_memory_context` or legacy `needs_long_term_memory` is present after slots resolve.
- Vocabulary/API projection: `src/agent/graph_vocabulary.py` and trace/API tests need canonical runtime projection for current runs while preserving historical row readability.
- Tests: graph baseline, routing totality, graph smoke, memory evidence boundary, reviewed-memory node tests, and Phase 48.1 compatibility guards are the highest-signal validation targets.
</code_context>

<specifics>
## Specific Ideas

- `memory_context_load` should be a first-class active graph node name even if its implementation delegates to `reviewed_memory_context_retrieve`.
- Retained legacy metric keys should be dual-written only if necessary; canonical `llm_outputs["memory_context_load"]` should be the active metric key.
- Add static guards that reject active `builder.add_node("long_term_memory_retrieve", ...)`, active route destinations `"long_term_memory_retrieve"`, and stale Phase 55 delete-phase baseline rows after cutover.
- Add graph smoke proving reviewed-memory-needed input traces `slot_resolution_gate` before `memory_context_load` before `investigate`.
- Keep `needs_reviewed_memory_context` as canonical routing hint and `needs_long_term_memory` as compatibility hint unless Phase 55 planning proves all live callers have moved.
</specifics>

<deferred>
## Deferred Ideas

- Phase 56: `recommendation_generation` active graph name and RAG/claim fail-closed status alignment.
- Phase 57: `risk_gate` / `approval_gate` canonicalization and risk vs approval responsibility split.
- Phase 58: final no-debt cleanup of retained graph aliases, historical compatibility vocabulary rows, and active legacy route values.
- Future product phase: richer preference management UI and user-specific preference scope.
</deferred>

<suggested_plan_split>
## Suggested Plan Granularity

Phase 55 should be split into multiple small plans:

1. **55-01:** Canonical `memory_context_load` node contract, output labels, and focused node/unit tests.
2. **55-02:** Active graph/router/baseline cutover from `long_term_memory_retrieve` to `memory_context_load`, including graph smoke tests.
3. **55-03:** Vocabulary/API/docs/architecture-debt compatibility ledger and final validation closeout.
</suggested_plan_split>

---

*Phase: 55-memory-context-load-cutover*
*Context gathered: 2026-07-07*
