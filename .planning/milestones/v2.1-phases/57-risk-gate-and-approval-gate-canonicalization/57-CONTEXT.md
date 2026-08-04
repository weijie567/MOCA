# Phase 57: Risk Gate and Approval Gate Canonicalization - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 57 delivers CAGM-08: make `risk_gate` the active registered graph node that owns blocked, manual-review, approval-required, and auto-draft risk/action decisions, while preserving `approval_gate` as the approval request/resume state machine.

This phase is not the final no-debt cleanup. It must remove `assess_risk_and_approval` from active graph registration and active current-run route values, but it may keep explicitly documented direct import, test, and historical trace compatibility until Phase 58 if the plan records owner, reason, trace projection, validation, and delete phase.

</domain>

<decisions>
## Implementation Decisions

### Canonical risk node cutover
- **D-57-01:** Active `StateGraph.add_node(...)` registration must use `risk_gate`, not `assess_risk_and_approval`.
- **D-57-02:** Active conditional edge path maps from `claim_verify` and `approval_gate` edit rerisk paths must route the `risk_gate` route value to the active `risk_gate` node.
- **D-57-03:** Current-run router return values must not point to `assess_risk_and_approval` after cutover. Historical compatibility may be projection-only and must be labeled non-current.
- **D-57-04:** The existing `assess_risk_and_approval` behavior may be reused only as a narrow implementation compatibility layer if the plan records legacy surface, canonical owner, reason, trace projection, validation, and `DELETE_BY_PHASE_58`. It must not remain the active graph registration after Phase 57.

### Risk gate authority
- **D-57-05:** `risk_gate` owns risk assessment, deterministic risk-rule overrides, proposed action creation, action safety snapshot binding, approval-plan creation, blocked/manual-review outcomes, and auto-allowed draft binding.
- **D-57-06:** `risk_gate` must continue to fail closed when claim verification, evidence, action payload hash, safety snapshot ref/hash, policy/risk/retrieval versions, or approval-plan bindings are missing or invalid.
- **D-57-07:** LLM output may assist draft/risk wording only through the existing structured-output path; final risk lowering, approval requirement, blocked/manual decisions, snapshot binding, and route choice stay deterministic or fail closed.
- **D-57-08:** `llm_outputs`, trace steps, node errors, API payload extraction, and eval/frontend/runtime vocabulary for current runs should use `risk_gate`. Any legacy `assess_risk_and_approval` key must be compatibility-only and cannot become current-run authority.

### Approval gate separation
- **D-57-09:** `approval_gate` handles approval interrupt/request resume behavior only: request payload display, pending self-loop, trusted accept/approve resume, edit/superseded rerisk, respond/needs-info interrupted lifecycle, and rejected/expired/invalid finalization.
- **D-57-10:** `approval_gate` must not decide risk, lower risk, create new action recommendations, create safety snapshots, or reinterpret ordinary chat approval text.
- **D-57-11:** Trusted edit resume must route to `risk_gate` for rerisk. New current-run `resume_route` values from ApprovalService/API should be canonical `risk_gate`.
- **D-57-12:** If existing persisted approvals or historical traces still contain `resume_route == "assess_risk_and_approval"`, compatibility handling must be explicit, tested, and marked for Phase 58 deletion. It cannot be the normal current-run path.

### Trusted approval boundary
- **D-57-13:** Ordinary chat approval text cannot become trusted approval. The only trusted approval entry is the authenticated approval API/inbox command path that constructs server-side `TrustedApprovalResultV1` data with tenant/user/role, approval id, expected versions, payload hash, and safety snapshot hash.
- **D-57-14:** Tests must preserve the existing safety-pre-route and intent-policy behavior where ordinary chat `approval_decision` or approval-like wording is unsupported/untrusted and cannot enter `approval_gate`, `action_draft`, or trusted graph resume.

### Planning and validation shape
- **D-57-15:** Planning should be split into multiple ordered plans, not one large plan. Expected boundaries are: canonical `risk_gate` callable and compatibility contract; active graph/router/baseline cutover; trusted approval resume and risk/approval separation hardening; vocabulary/API/frontend/eval/docs/debt/validation closeout.
- **D-57-16:** Phase 57 must preserve Phase 56 RAG/claim fail-closed behavior and Phase 58 final cleanup scope. It must not delete every historical `assess_risk_and_approval` reference unless that deletion is explicitly safe and in scope.
- **D-57-17:** Verification commands must use MOCA-approved entrypoints such as `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.

### the agent's Discretion
- Exact module structure is left to the planner as long as active graph identity is canonical and legacy compatibility is narrow, explicit, and Phase 58-scoped.
- Exact names for compatibility metadata constants are implementation discretion.
- Exact API/frontend display copy is implementation discretion as long as current-run identity is `risk_gate` and historical projection remains distinguishable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and migration charter
- `.planning/ROADMAP.md` - Phase 57 goal, dependency on Phase 56, and CAGM-08 success criteria.
- `.planning/REQUIREMENTS.md` - CAGM-08 requirement text and pending status.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - source hierarchy, target 15-node graph, current-to-target matrix, authority matrix, validation matrix, temporary compatibility policy, and final no-debt gate.

### Target risk and approval contract
- `docs/contract-spec.md` §9.1, §9.3, §9.4, §9.5 - canonical node list, route table, node authority table, and risk/approval/action transition semantics.
- `docs/contract-spec.md` §10 and §13 - trusted approval command boundary and state lifecycle ownership for `risk_assessment`, `approval_plan`, `approval_result`, `safety_snapshot_ref`, and `safety_snapshot_hash`.
- `docs/contract-spec.md` §16 - action safety snapshot creation by `risk_gate` and downstream verification by approval/action boundaries.
- `docs/eval-test-plan.md` - approval contract and intent precedence tests for ordinary chat versus trusted approval command separation.

### Prior phase handoff
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md` - Phase 56 decisions preserving Phase 57 risk node scope.
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-02-SUMMARY.md` - active graph cutover pattern and explicit preservation of `assess_risk_and_approval` as the Phase 57 legacy row.
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-03-SUMMARY.md` - claim verification route gate now enters the Phase 57-owned risk node only after explicit allowed action support.
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-04-SUMMARY.md` - projection/docs/debt closeout pattern and Phase 57 boundary.
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-PLAN-REVIEW-DECISIONS.md` - prior plan-review pattern for adjudicating canonical graph migration feedback.
- `.planning/ARCHITECTURE-DEBT.md` - graph/RAG/claim migration debt entries and Phase 57/58 residual risks.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/nodes/assess_risk_and_approval.py` - current risk/action policy implementation, including risk prompt assembly, deterministic high-risk override, proposed action construction, trusted edit rerisk handling, snapshot binding, trace steps, and legacy `llm_outputs` key.
- `src/agent/nodes/approval_gate.py` - current approval interrupt node with display-only interrupt payload, validation of `approval_result.v1`, and approval trace step.
- `src/agent/graph.py` - active graph registration and route maps. Current lines register and route through `assess_risk_and_approval`; Phase 57 must cut these to `risk_gate`.
- `src/agent/routing.py` - current `route_after_claim_verify` still returns `assess_risk_and_approval`; action-bound/high-risk helpers already treat ordinary `approval_decision` as unsafe/action-bound.
- `src/api/routers/approvals.py` - trusted ApprovalService resume adapter currently validates edit `resume_route == "assess_risk_and_approval"` and decides graph resume behavior.
- `src/api/routers/agent_runs.py` - current trace/API payload extraction special-cases `assess_risk_and_approval` for risk-level display.

### Established Patterns
- Phase 56 introduced canonical active-node cutover with narrow legacy compatibility wrappers and Phase 58 delete metadata.
- `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` are the static source-of-truth tests for active graph nodes, route maps, target canonical set, and remaining migration rows.
- `src/agent/graph_vocabulary.py` projects runtime versus compatibility alias semantics for trace/API/frontend/eval surfaces.
- Trusted approval is server-constructed in API/inbox paths; ordinary chat approval-like text is blocked or unsupported before approval/action paths.

### Integration Points
- Active graph changes: `src/agent/graph.py`, `src/agent/routing.py`, and architecture baseline tests.
- Node identity changes: `src/agent/nodes/assess_risk_and_approval.py`, likely new `src/agent/nodes/risk_gate.py`, node tests, and Phase 22 action-boundary regression tests.
- Approval resume changes: `src/api/routers/approvals.py`, `src/approvals/schemas.py`, `tests/test_approval_api.py`, and `tests/test_graph_routing.py`.
- Projection/docs changes: `src/agent/graph_vocabulary.py`, `src/api/routers/agent_runs.py`, trace/API/frontend/eval tests, `docs/current-langgraph-architecture.md`, `docs/architecture-overview.md`, `docs/target-agent-platform-architecture-plan.md`, `README.md`, and `.planning/ARCHITECTURE-DEBT.md`.

</code_context>

<specifics>
## Specific Ideas

- Auto discussion selected conservative defaults: canonical active graph identity first, trusted approval rerisk semantics second, projection/docs/debt closeout third.
- Plan review must explicitly check plan granularity. A single giant plan covering callable migration, graph route maps, trusted approval semantics, API/frontend projections, docs, and validation would violate the MOCA plan-size rule.
- The current target contract already uses `risk_gate`; Phase 57 should update current-source docs and tests rather than treating target docs as stale implementation facts.

</specifics>

<deferred>
## Deferred Ideas

- Final deletion of all active compatibility aliases, historical projections, and remaining migration-era legacy references belongs to Phase 58.
- External action execution after `action_draft` remains out of current runtime scope unless a later spec changes the target graph.

</deferred>

---

*Phase: 57-risk-gate-and-approval-gate-canonicalization*
*Context gathered: 2026-07-07*
