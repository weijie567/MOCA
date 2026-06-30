# Phase 35: Replay and Eval Hardening - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 35 closes observability and eval coverage for the v1.9 platform boundaries so future implementation phases can be judged by deterministic contract gates. It hardens replay, trace, and eval coverage for existing platform decisions across trusted context projection, intent/slot policy, memory load/write policy, tool visibility/auth, RAG validation, claim verification, risk/approval, and action draft boundaries.

This phase does not rebuild the event envelope foundation, does not introduce real external execution, does not physically split services, and does not allow raw prompts, raw tool payloads, PII, or raw action payloads into replay artifacts.

</domain>

<decisions>
## Implementation Decisions

### Replay Coverage Model

- **D-01:** Phase 35 uses a platform-boundary coverage matrix plus blocking contract tests as the deterministic acceptance layer. The matrix must map each platform boundary to replay events, trace projections, eval gate level, forbidden behavior, and acceptance tests.
- **D-02:** Blocking replay tests must cover event completeness, sequence/order, terminal timeline status, redaction, permission isolation, operation identity where applicable, and forbidden behavior. This is stronger than patching only visible gaps.
- **D-03:** Coverage applies to existing platform boundaries and events. Phase 35 must not re-implement `DecisionEventEnvelopeV1`, create a parallel event envelope, introduce full artifact storage, or add real external action execution.
- **D-04:** Replay remains audit replay, not deterministic LLM/tool/RAG rerun. Replay artifacts must preserve stable refs, reason codes, hashes, versions, safe summaries, and redacted payloads only.

### Trace And Replay Visibility

- **D-05:** Keep business-data run, trace, and replay API visibility owner/admin-only in Phase 35. `support`, `manager`, legacy `merchant`, `supervisor`, and `approval_manager` must not read another user's business-data run/trace/replay in this phase.
- **D-06:** Phase 35 should add or harden the proof chain needed for future same-merchant authorization without opening that authorization yet. Proof should include `target_merchant_id` or equivalent target merchant proof, scoped `BusinessFactRefV1` / `BusinessFactResultV1`, proof source, proof status, and fail-closed status for unknown, mixed, denied, invalid, or cross-merchant scopes.
- **D-07:** Negative tests must prove `requested_by.user.merchant_id` is not an acceptable same-merchant authorization approximation for trace/replay access.
- **D-08:** Future manager same-merchant trace/replay visibility is allowed as a later phase only after the proof chain is stable and tested.

### Eval Gate Placement

- **D-09:** Phase 35 splits eval gates into `dev-contract`, `release`, and `monitoring` levels.
- **D-10:** Only deterministic `dev-contract` gates block Phase 35. Blocking gates include schema validity, platform event coverage, event order, terminal replay timelines, redaction, owner/admin-only permissions, cross-tenant/cross-merchant negatives, forbidden behavior, and release/monitoring manifest format.
- **D-11:** Release gates are Phase 35 artifacts, not hard blockers unless they expose a deterministic forbidden-behavior regression. Release artifacts should include dataset version/hash, coverage manifest hash, command entrypoint, metrics, pass/fail/statistical_gate_not_demonstrated status, and sample-size or coverage gaps.
- **D-12:** Monitoring gates are Phase 35 artifacts, not hard blockers. Monitoring artifacts should define metric/report schemas for replay completeness, drift, false-negative trend, tool deny reasons, RAG no-evidence trend, and memory write quality. Missing production data should be represented as `pending`, `not_applicable`, or `sample_only`, not a Phase 35 blocker.
- **D-13:** Safety, permission, raw payload exposure, unsupported-claim-to-action, stale business fact, invalid evidence scope, or no-evidence-to-action behaviors that can be deterministically tested must be classified as `dev-contract` blocking tests.

### Golden And Negative Dataset Priority

- **D-14:** Phase 35 golden and negative datasets prioritize the `dev-contract` blocking gate, not broad statistical release expansion.
- **D-15:** P0 replay terminal golden cases must cover normal completed, interrupted approval-required, resumed, rejected, responded/needs-info, expired, error, and cancelled timelines.
- **D-16:** P0 redaction/exposure negatives must prove replay excludes raw prompt, raw tool payload, ticket/order/refund PII, raw action payload, secrets, and unsafe debug payloads. Replay should contain only redacted payloads, stable refs, reason codes, hashes, versions, and safe summaries.
- **D-17:** P0 permission negatives must cover non-owner `support` / `manager` / `merchant` access denial, cross-tenant 404 behavior, cross-merchant fail-closed behavior, and lack of target merchant / scoped business fact proof.
- **D-18:** P0 action-bound forbidden behavior must cover unsupported claims blocked before risk/approval/action, no-evidence not producing deterministic action recommendations, stale or wrong-scope `BusinessFactRefV1` not entering action paths, invalid-scope evidence not entering action paths, and approval payload hash mismatch not producing action drafts.
- **D-19:** Intent hard negatives, RAG semantic claim-support statistics, and approval/action safety release datasets should receive manifests, coverage gaps, and limited smoke cases in Phase 35, but broad statistical expansion is deferred.

### Plan Granularity

- **D-20:** Phase 35 must not be planned as one broad `35-01-PLAN.md` despite the roadmap placeholder. It spans replay contracts, trace visibility/proof, eval gates, golden datasets, and final verification across multiple service boundaries.
- **D-21:** Planning should split into dependency-ordered plans. A likely shape is: coverage matrix and event/replay contract gaps; trace/replay proof and permission tests; dev-contract eval gate and forbidden-behavior datasets; release/monitoring manifests and report artifacts; final static/focused/eval closure.

### the agent's Discretion

- Exact matrix file path and schema are planner discretion, but the matrix must be machine-checkable or test-backed enough to block drift.
- Exact event type additions are planner discretion if they use the existing replay-owned event registry and redaction rules. Do not create a parallel event family outside `src/replay/`.
- Exact report filenames are planner discretion, but release and monitoring artifacts must be discoverable by future planning/execution agents and must include commands and non-blocking status semantics.
- Exact test split is planner discretion, but tests must use `uv run pytest ...` or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid in MOCA.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope

- `.planning/ROADMAP.md` - Phase 35 goal, APF-17/APF-18 requirements, success criteria, and core references.
- `.planning/REQUIREMENTS.md` - APF-17/APF-18 requirement text and v1.9 out-of-scope boundaries.
- `.planning/STATE.md` - Current milestone state, Phase 34 completion notes, and Phase 35 readiness.
- `.planning/PROJECT.md` - v1.9 modular-monolith target, safety boundaries, and no-real-execution constraints.

### Normative Replay And Eval Contracts

- `docs/contract-spec.md` §0.2 - Observability / Replay ownership, decision events, public methods, and forbidden raw payload persistence.
- `docs/contract-spec.md` §8.0 / §8.0.1 - Trusted context, merchant scope semantics, and owner/admin-only interim business-data run/trace/replay access.
- `docs/contract-spec.md` §9 / §10 - Target graph vocabulary, AgentState observability fields, replay handoff fields, and writer ownership.
- `docs/contract-spec.md` §17.1-§17.7 - Run lifecycle, `DecisionEventEnvelopeV1`, `ReplayEventV3`, per-run sequence allocator, trace spans, metrics/logs, replay API, redaction, and retention rules.
- `docs/contract-spec.md` §18.4 - `agent_trace_events` storage shape, event type registry, and migration constraints.
- `docs/eval-test-plan.md` §20.0-§20.4 - Gate levels, contract matrix, eval metrics, dataset requirements, Wilson/M6 release semantics, and replay terminal golden-case requirement.
- `docs/eval-test-plan.md` §21.8 - Replay timeline examples for normal, interrupted/resumed, error, cancelled, responded, and expired runs.
- `docs/target-agent-platform-architecture-plan.md` §14 / Phase 35 section - Architecture target for decision-event coverage, replay artifact coverage, and eval gate inclusion.

### Prior Phase Context

- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - TrustedContext source, projection-local fields, and replay context projection.
- `.planning/phases/28-decision-event-foundation/28-CONTEXT.md` - Replay-owned `DecisionEventEnvelopeV1`, `emit_decision_event`, reason/version/redaction conventions, and no parallel envelope.
- `.planning/phases/29-tool-platform-boundary/29-CONTEXT.md` - Tool visibility/runtime auth decision events, tool result projection, and Phase 35 projection-event deferral.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-CONTEXT.md` - Owner/admin-only AgentRun/trace interim visibility and manager same-merchant deferral.
- `.planning/phases/30-businessfactservice-boundary/30-CONTEXT.md` - `BusinessFactService`, scoped `BusinessFactRefV1`, no-leak business fact semantics, and current business fact authority.
- `.planning/phases/31-memory-platform-boundary/31-CONTEXT.md` - Memory contextual-only authority, memory status refs, and replay event coverage deferral to Phase 35.
- `.planning/phases/32-intent-graph-migration/32-CONTEXT.md` - Target graph vocabulary, trace/eval projections, and target merchant context evidence.
- `.planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md` - `VerifiedEvidencePackageV1`, `ClaimVerificationBundleV1`, RAG/claim replay handoff, and blocked action-claim gates.
- `.planning/phases/34-approval-and-actiondraft-boundary-hardening/34-CONTEXT.md` - Approval/action draft bindings, risk/approval split, no-real-execution boundary, and Phase 35 broad trace/run projection hardening deferral.

### Current Code Sites

- `src/replay/service.py` - `ReplayService.append_event`, sequence allocation, minimal/V3 projection, and `/replay` response construction.
- `src/replay/decision_events.py` - `DecisionEventEnvelopeV1`, `emit_decision_event`, reason-code normalization, version placement, and trusted identity resolution.
- `src/replay/validators.py` - Event registry, retention classification, `guard_redacted_payload`, and `guard_resource_refs`.
- `src/replay/schemas.py` - Strict `ReplayEventV3` and `ReplayResponseV3` contracts.
- `src/replay/lifecycle.py` - Run lifecycle event emission and terminal/current status handling.
- `src/replay/pairing.py` - Operation pairing validation for V3 replay projection.
- `src/api/routers/traces.py` - `/trace` and `/replay` API authorization and owner/admin-only visibility guard.
- `src/api/routers/agent_runs.py` - AgentRun visibility guard, target merchant context projection, streaming trace payloads, and memory-write scheduling.
- `src/agent/trace.py` - AgentRun/AgentStep persistence, safe trace summary, target graph projection, lifecycle status event handoff, and target merchant context summary.
- `src/agent/graph_vocabulary.py` - Legacy-to-target graph projection for trace/eval contract assertions.
- `src/agent/merchant_context.py` - Target merchant proof projection used by trace summaries.
- `src/tools/platform.py` and `src/tools/runtime.py` - Tool visibility and runtime auth decision event emission.
- `src/agent/nodes/memory_write.py` - Memory write decision/status refs and memory write lifecycle events.
- `src/agent/nodes/rag_context_build.py` and `src/agent/nodes/claim_verify.py` - RAG/claim node outputs that Phase 35 should make replay/eval assertable.
- `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/approval_gate.py`, and `src/agent/nodes/action_draft.py` - Risk, approval, target merchant, and action draft binding sources for replay/eval coverage.
- `src/actions/service.py` - `action_draft_created` event emission and demo-only draft outcome boundary.
- `src/approvals/events.py`, `src/approvals/repository.py`, and `src/api/routers/approvals.py` - Approval lifecycle event emission, target merchant filtering, and trusted decision/resume behavior.
- `scripts/eval_all.py`, `scripts/eval_agent.py`, `scripts/eval_rag.py`, and `scripts/eval_phase22_hallucination.py` - Existing eval entrypoints and report patterns.
- `eval/intent/coverage-manifest.v1.json` and `eval/intent/m6-statistical-gate.v1.json` - Existing contract-vs-release gate separation and `statistical_gate_not_demonstrated` pattern.
- `.github/workflows/ci.yml` - Current CI runs lint and non-integration pytest, not DB-backed eval.
- `docs/evaluation.md` - Current eval docs and local-vs-CI split.
- `Makefile` - `make eval`, `make eval-agent`, `make eval-rag`, and `make eval-live` command entrypoints.

### Tests To Inspect Or Extend

- `tests/replay/test_decision_events.py`
- `tests/replay/test_replay_service.py`
- `tests/replay/test_replay_api.py`
- `tests/replay/test_sequence_allocator.py`
- `tests/replay/test_operation_pairing.py`
- `tests/replay/test_lifecycle_finalizer.py`
- `tests/replay/test_replay_redaction_retention.py`
- `tests/replay/test_tool_policy_events.py`
- `tests/agent/test_events.py`
- `tests/agent/test_graph_vocabulary.py`
- `tests/agent/test_memory_write_node.py`
- `tests/agent/test_nodes/test_rag_context_build.py`
- `tests/agent/test_nodes/test_claim_verify.py`
- `tests/agent/test_nodes/test_assess_risk_and_approval.py`
- `tests/architecture/test_phase32_static_contract.py`
- `tests/architecture/test_phase33_rag_claim_boundaries.py`
- `tests/architecture/test_phase34_approval_action_boundaries.py`
- `tests/architecture/test_tool_boundaries.py`
- `tests/test_agent_runs_api.py`
- `tests/test_trace_api.py`
- `tests/test_approval_api.py`
- `tests/actions/test_phase34_action_draft_bindings.py`
- `tests/approvals/test_events.py`
- `tests/agent/test_intent_manifest.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `ReplayService`: already owns append, projection, sequence allocation, `/replay` response generation, and V3/minimal envelope projection. Phase 35 should harden and assert coverage around it rather than replacing it.
- `DecisionEventEnvelopeV1` / `emit_decision_event`: already provide the replay-owned minimal envelope path. New coverage should use this path.
- `guard_redacted_payload` and `guard_resource_refs`: existing recursive unsafe-key guards can be extended for new forbidden payload cases.
- `project_trace_step_for_contract`: existing trace-to-target graph projection can support contract/eval assertions.
- `project_target_merchant_context`: existing target merchant proof projection can be extended or tested as the future same-merchant proof chain.
- Existing replay tests already cover sequence allocation, redaction, API access, operation pairing, and tool policy events. Phase 35 should add a matrix-driven layer instead of duplicating these ad hoc.
- Existing eval manifests under `eval/intent/` already model contract-vs-release separation and `statistical_gate_not_demonstrated`.

### Established Patterns

- Replay and decision events are owned by `src/replay/`; domain services emit through replay-owned helpers and must not invent parallel envelopes.
- API run/trace/replay visibility is currently owner/admin-only, and tests explicitly assert that target merchant context is not used for authorization yet.
- Raw payload leakage is handled through guard functions and projection-level allowlists, not by trusting callers.
- Release evals can be local artifacts when they need DB/fixtures/provider state; deterministic pytest contract tests are the appropriate CI/phase blocker.
- Graph vocabulary migration preserves implementation names while exposing target names for contract/eval assertions.

### Integration Points

- Replay coverage matrix should tie together `src/replay/validators.py`, `src/replay/service.py`, domain event writers, target graph projection, and eval manifests.
- Trace/replay proof chain should connect target merchant context from agent state, scoped `BusinessFactRefV1` / `BusinessFactResultV1`, replay resource refs, and API authorization tests without changing authorization behavior.
- Dev-contract gate should be executable through focused `uv run pytest ...` suites and static/manifest checks.
- Release/monitoring artifact generation can extend existing `scripts/eval_all.py` / report patterns or add a separate Phase 35 manifest generator if planning finds that cleaner.

</code_context>

<specifics>
## Specific Ideas

- The coverage matrix plus blocking tests are the Phase 35 acceptance boundary, not a nice-to-have report.
- Audit view readability is valuable only as a projection of the matrix and tests, not as the main Phase 35 goal.
- Business direction may eventually support manager same-merchant trace/replay visibility, but Phase 35 must first make the proof chain stable and fail-closed.
- Release datasets should report gaps and commands now; broad statistical expansion happens later.

</specifics>

<deferred>
## Deferred Ideas

- Broader release dataset expansion for intent hard negatives, RAG claim support, and approval/action safety is deferred to a later eval expansion or release-readiness phase.
- Opening manager same-merchant trace/replay visibility is deferred until a later phase can use the Phase 35 proof chain safely.

</deferred>

---

*Phase: 35-replay-and-eval-hardening*
*Context gathered: 2026-06-29*
