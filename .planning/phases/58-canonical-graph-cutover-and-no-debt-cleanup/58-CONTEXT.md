# Phase 58: Canonical Graph Cutover and No-Debt Cleanup - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 58 closes CAGM-09 by proving the active main LangGraph runtime is the final 15-node canonical graph and by removing or internalizing remaining migration-era legacy graph vocabulary. This phase is a final no-debt cleanup: active graph registrations and route values must remain canonical, `graph_vocabulary.py` must stop advertising active runtime compatibility aliases for the main graph, and trace/API/eval/frontend/docs must no longer require legacy-to-target interpretation for current runs.

This phase should not re-implement Phase 49-57 behavior. The previous phases already cut over `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, `slot_resolution_gate`, `memory_context_load`, `recommendation_generation`, and `risk_gate`. Phase 58 removes the scaffolding that was explicitly marked `DELETE_BY_PHASE_58`.

</domain>

<decisions>
## Implementation Decisions

### Final No-Debt Scope

- **D-58-01:** Treat `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` Final No-Debt Gate as the controlling checklist. The plan must close every checklist item or record a reviewed spec/implementation exception; silent partial cleanup is not acceptable.
- **D-58-02:** Active runtime graph behavior is already source-verified as canonical: `graph_add_node_names()` currently returns 15 nodes and equals `TARGET_CANONICAL_GRAPH_NODES`; route map scan found no legacy route destinations. Planning should preserve this state and focus on final debt removal, not risky runtime rewiring.
- **D-58-03:** Do not bulk-rewrite historical production data. Historical trace/API/replay rows may remain readable, but current-run projection and active runtime contracts must no longer depend on compatibility aliases labeled as active graph vocabulary.

### Compatibility Alias Cleanup

- **D-58-04:** Close all `DELETE_BY_PHASE_58` compatibility rows intentionally. Primary source candidates include `src/agent/graph_vocabulary.py`, legacy wrapper modules/tests for `generate_recommendation` and `assess_risk_and_approval`, frontend/API trace labels, approval retry normalization, eval replay manifest rows, and stale architecture tests.
- **D-58-05:** Prefer deleting import/test-only wrappers when no current runtime code imports them. If a helper must remain for historical projection or internal implementation, reclassify it as internal/historical and prove it is not a main graph compatibility alias.
- **D-58-06:** Persisted historical approval retry metadata must not authorize a legacy resume route. If `src/api/routers/approvals.py` still needs a server-side canonicalization path for old rows, the plan must name it as bounded data-read compatibility, not graph vocabulary compatibility, and tests must prove graph resume emits `risk_gate`.

### Trace, API, Eval, And Docs

- **D-58-07:** Current-run trace/API/SSE/frontend/eval surfaces should present canonical names. Tests that preserve old node names should be narrowed to historical-row readability only, or removed if they merely preserve migration-era compatibility.
- **D-58-08:** Documentation and planning ledgers must distinguish target contract, implemented current state, and historical references. Current architecture docs should no longer describe legacy names as active runtime nodes, current route values, or current resume routes.
- **D-58-09:** The final skipped gate in `tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_phase58_scope` should become a real assertion as part of closeout.

### Validation Strategy

- **D-58-10:** Verification must use MOCA-approved entrypoints only: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.
- **D-58-11:** Include a static legacy-hit classifier in the plan and final validation. It should report total hits, file/path categories, zero active-runtime legacy hits, and zero unclassified rows. It should avoid recursive self-counting of the generated validation artifact.
- **D-58-12:** Keep verification scoped enough for fast feedback during tasks, then run a broad closeout suite covering graph baseline, routing, graph vocabulary, trace/API projections, approval resume, recommendation/risk wrapper deletions, eval/diagnostic surfaces, docs guards, ruff, and `git diff --check`.

### the agent's Discretion

The agent may choose exact plan decomposition, but it should be split by ownership boundary rather than one large plan. A reasonable split is: source/graph vocabulary cleanup, projection/API/eval/frontend cleanup, docs/debt/validation closeout, and final broad verification. Each plan must have concrete file scope and tests.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Contract

- `.planning/ROADMAP.md` §Phase 58 — Phase goal, dependency, success criteria, and CAGM-09 mapping.
- `.planning/REQUIREMENTS.md` §Canonical Agent Graph Migration Requirements — `CAGM-09` pending requirement and coverage status.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` — Binding migration charter, source hierarchy, target 15-node set, temporary compatibility policy, validation matrix, and Final No-Debt Gate.

### Prior Phase Handoff

- `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md` — Static legacy-hit classification and Phase 58 deletion candidates.
- `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-05-SUMMARY.md` — Docs/debt/validation closeout and explicit Phase 58 readiness notes.
- `.planning/STATE.md` — Phase 57 completion notes and Phase 58 current focus.

### Target And Current Architecture Docs

- `docs/contract-spec.md` §9 — Primary accepted target graph semantics.
- `docs/target-agent-platform-architecture-plan.md` §6.1 — Readable target architecture view.
- `docs/current-langgraph-architecture.md` — Current-source graph snapshot and compatibility-surface table requiring cleanup.
- `docs/architecture-overview.md` and `README.md` — Current user-facing architecture summaries that must stay synchronized.
- `.planning/ARCHITECTURE-DEBT.md` — Agent Graph debt ledger entries to update when Phase 58 closes the migration.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `tests/architecture/graph_baseline.py` exposes AST helpers for active graph node set, direct edges, conditional edge maps, and router return values.
- `tests/architecture/test_canonical_graph_baseline.py` already contains source-level guards for canonical node set, route totality, eval diagnostics, frontend labels, and forbidden registered helper/lifecycle nodes.
- `src/agent/graph_vocabulary.py` centralizes graph name projection and is the main compatibility alias cleanup target.

### Established Patterns

- Runtime node wrappers often keep compatibility metadata dictionaries with `legacy_surface`, `canonical_owner`, `trace_projection`, `validation_tests`, and `delete_phase`.
- Prior validation artifacts use static scan classification with total hit counts, category counts, command evidence, and zero unclassified rows.
- MOCA graph migration phases record subsystem-level fixes in `.planning/ARCHITECTURE-DEBT.md` in Chinese and local validation incidents in `.planning/LOCAL-VALIDATION-ISSUES.md`.

### Integration Points

- `src/agent/graph.py` currently imports and registers only canonical runtime nodes.
- `src/agent/routing.py` current route sets use canonical route values; compatibility router wrappers still exist for older function names (`route_after_intent`, `route_after_slots`) and are Phase 58 cleanup candidates.
- `src/api/routers/approvals.py` still has a `LEGACY_RISK_ROUTE` canonicalization path marked `DELETE_BY_PHASE_58` for persisted historical retry metadata.
- `frontend/src/components/timeline/TimelineStep.tsx`, `src/api/routers/agent_runs.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, and `eval/replay/dev-contract-manifest.v1.json` contain historical projection or dev-contract references that must be audited.

</code_context>

<specifics>
## Specific Ideas

- Auto-discuss selected the conservative no-debt path: delete active migration scaffolding, preserve historical readability only where needed, and make final gates machine-verifiable.
- Current source evidence gathered during discussion:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run python ... graph_add_node_names()` reported 15 active nodes and `matches_target True`.
  - The same scan reported `legacy_route_hits []`.
  - `git grep -n "DELETE_BY_PHASE_58" -- src tests frontend scripts eval rules README.md docs .planning/ARCHITECTURE-DEBT.md .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/STATE.md | wc -l` reported 40 candidate hits before planning.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 58 scope.

</deferred>

---

*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Context gathered: 2026-07-08*
