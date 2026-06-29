# Phase 34: Approval and ActionDraft Boundary Hardening - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 34`; `request_user_input` was unavailable in Codex Default mode, so Codex selected conservative defaults after reading roadmap, requirements, prior phase context, target architecture/spec docs, and current approval/action code.

<domain>
## Phase Boundary

Phase 34 hardens the approval and action draft boundary. It must bind structured action proposals, approval decisions, and action drafts to current business fact refs, verified policy evidence refs, claim verification refs, risk decisions, exact payload hashes, immutable action safety snapshots, and target merchant scope.

This phase must satisfy APF-15 and APF-16. `risk_gate` owns blocked / approval-required / auto-draft decisions, risk decisions, approval plans, and safety snapshot creation. `approval_gate` only executes approval plans, trusted resume, interrupt, and approval revision state machine behavior. `action_draft` creates durable demo drafts only after a trusted approved result or a durable auto-allowed binding.

This phase must restore manager approval list/get/decide only when target merchant binding is explicit and scoped. It must preserve the no-real-execution boundary: no external outbox worker, no real refund/coupon/ticket side effect, no action execution records, and no final response that implies real execution.

</domain>

<decisions>
## Implementation Decisions

### Contract and Persistence Boundary

- **D-01:** Introduce explicit approval/action boundary contracts rather than relying on untyped graph state or raw JSON blobs. Minimum contracts are `ActionProposalV1` / existing `proposed_action.v1`, `RiskDecisionV1`, `ApprovalResultV1`, and `ActionDraftV2Data` with stable refs.
- **D-02:** Phase 34 should persist or denormalize the binding fields needed for authorization, replay handoff, and manager-scoped queues. At minimum, `ApprovalRequest` and `ActionDraft` must carry target merchant binding, business fact refs, verified evidence refs, claim verification refs or a stable claim-verification bundle ref/summary, risk decision refs or safe JSON, action payload hash, safety snapshot ref/hash, approval/revision refs, and idempotency key.
- **D-03:** It is acceptable to extend the existing `approval_requests` / `action_drafts` v2 tables and JSON fields rather than introducing a large new table family, as long as service contracts expose the target fields and tests prove they are not reconstructed from prompts, memory, raw tool payloads, or LLM text.
- **D-04:** Existing `ActionSafetySnapshot` remains the canonical immutable safety binding. Phase 34 should validate and carry it forward; downstream approval/action code must not rebuild snapshots except where ApprovalService creates a new revision for edit/info-supplied material changes.
- **D-05:** `ActionDraftV2Data` should be enriched enough for downstream Phase 35 replay/eval hardening to read stable refs without parsing raw action payloads. Raw payload can remain stored for draft ownership, but prompt/API/working-state projections must expose only safe summaries and refs.

### Risk Gate and Approval Gate Responsibility Split

- **D-06:** `risk_gate` owns action proposal normalization, risk decision, approval plan generation, blocked/approval-required/auto-draft routing, and safety snapshot creation before either `approval_gate` or `action_draft`.
- **D-07:** `approval_gate` must not re-decide blocked vs approval-required vs auto-draft. It should only create/interrupt approval requests from a structured approval plan, accept trusted `approval_result.v1` resume payloads, and route based on approval state machine results.
- **D-08:** The current `assess_risk_and_approval` node may remain as a compatibility implementation while Phase 34 extracts/labels target `risk_gate` semantics, but planning must not leave approval policy decisions buried in `approval_gate`.
- **D-09:** `route_after_risk` must be deterministic and side-effect-free: blocked -> final response; approval required -> `approval_gate`; auto allowed -> `action_draft`. Invalid or missing risk/action bindings fail closed to approval/manual-review/final safe response.
- **D-10:** `route_after_approval` must follow the spec transition table: approved all required levels -> `action_draft`; next required level pending -> stay approval/interrupted; edit -> `risk_gate`; respond/needs_info -> interrupted lifecycle finalizer; reject/ignore/expired/cancelled -> final safe response.

### Target Merchant and Manager Approval Scope

- **D-11:** Target merchant binding must come from scoped `BusinessFactRefV1` / `BusinessFactResultV1` authority or a service-approved target merchant field derived from those refs. It must not be inferred from `requested_by`, final response text, memory, RAG evidence, or user/model payloads.
- **D-12:** `ApprovalRequest` and `ActionDraft` should carry a target merchant id or target merchant ref when the action is merchant-scoped. Business fact refs remain the authority; the denormalized merchant field is for filtering and fail-closed route/API checks.
- **D-13:** Manager list/get/decide should be restored only for approvals whose target merchant is inside the manager actor's trusted merchant scope. If target merchant is missing, ambiguous, multi-merchant, or outside scope, manager access fails closed. `admin` remains explicitly platform-wide.
- **D-14:** Approval resume for manager actors must use `TrustedContextFactory` merchant scope from the actor plus trusted server tool permission injection only. `ACTION_DRAFT_PERMISSION` may be injected by server code, but it must not widen merchant scope.
- **D-15:** Non-admin human actors must never receive wildcard `server_merchant_scope` through approval resume. Future system-owned wildcard approval/action jobs require a separate trusted system context contract, not `TrustedContextFactory.create_from_request(user=...)`.

### Auto-Draft and No-Approval Binding

- **D-16:** Keep the default no-approval action path fail-closed unless `risk_gate` writes a durable, exact auto-allowed binding with action payload hash, safety snapshot ref/hash, risk decision, target merchant, business fact refs, verified evidence refs, claim verification refs, and idempotency key.
- **D-17:** Phase 34 should define the auto-allowed contract even if current policy keeps all action-bearing merchant operations approval-required. This satisfies the APF-16 ownership split without broadening unsafe behavior.
- **D-18:** Do not implement broad low-risk real actions. If any auto-draft is enabled, it creates a demo `ActionDraft` and `draft_outcome.v1(status=not_executed_demo, external_side_effect=false)` only.
- **D-19:** Existing `ActionService` behavior that rejects missing approval as `AUTO_ALLOWED_BINDING_REQUIRED` is a safe baseline. Planning may replace it only with a durable auto-allowed binding check owned by `risk_gate`, not with implicit "approval_required=false" trust.

### Approval Revision and Action Draft Binding

- **D-20:** Approval accept/approve authorizes only the exact approval revision's action payload hash and safety snapshot hash. Any changed action args, target, amount, evidence refs, policy/risk/retrieval versions, business fact refs, or claim verification support invalidates the old approval and requires revalidation/revision.
- **D-21:** Approval edit must create a new proposed action revision and route back through risk/snapshot validation. It must not route directly to draft creation.
- **D-22:** Approval respond/needs_info preserves interrupted lifecycle state and cannot complete the run through ordinary clarification/final-response/memory-write as if no approval were pending.
- **D-23:** `action_draft` must validate exact trusted approval result or durable auto-allowed binding against current state, trusted context tenant/run, payload hash, safety snapshot ref/hash, and target merchant binding before invoking the node-only action tool.
- **D-24:** Idempotency keys must include tenant id, run id, approval revision or auto-allowed marker, action type, target id, and action payload hash so the same target with different payloads does not collide.

### No-Real-Execution Boundary

- **D-25:** Phase 34 must not introduce external adapters, outbox dispatch, reconciliation, compensation workers, action execution records, or external side effects.
- **D-26:** `execute_action` remains a compatibility shim only if it still exists. New graph/action paths should target canonical `action_draft` and `draft_outcome.v1`.
- **D-27:** Final responses must say draft-created / pending approval / rejected / needs info, never "coupon issued", "refund completed", or other real side-effect wording.

### Plan Granularity and Verification

- **D-28:** Do not plan Phase 34 as one large `34-01-PLAN.md` despite the roadmap placeholder. This phase spans contracts/schema, risk/action proposal binding, approval service/API scope, graph routing, action draft service, and final verification. MOCA project rules require splitting into dependency-ordered plans before execution.
- **D-29:** Recommended plan units:
  - contracts and persistence bindings for `ActionProposal` / `RiskDecision` / approval / draft refs;
  - `risk_gate` responsibility extraction, approval plan, target merchant/business/evidence/claim/risk binding, and durable auto-allowed contract;
  - `approval_gate` / ApprovalService / approval API manager-scope restore and trusted resume hardening;
  - `action_draft` / ActionService validation, draft schema enrichment, idempotency, and no-real-execution projection cleanup;
  - final static/focused/eval closure.
- **D-30:** Verification must use MOCA's valid local entrypoint: `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or `.venv/bin/pytest ...`. Bare `pytest` and bare `python -m pytest` are invalid for this repository.
- **D-31:** Tests must prove ordinary chat cannot forge approval/action authority, payload changes invalidate old approval, unsupported claims cannot reach approval/action, manager A cannot see/decide merchant B approvals, missing target merchant fails closed for managers, non-admin resume cannot get wildcard merchant scope, and no full real execution is introduced.

### the agent's Discretion

- Exact class/module names are planner discretion, but contracts should live under the owning domains (`src/approvals/`, `src/actions/`, and shared schemas only where reuse requires it).
- Exact persistence shape is planner discretion if it preserves stable service contracts and fail-closed manager filtering.
- Exact event payload names are planner discretion, but they must use the Phase 28 decision-event/redaction/resource-ref conventions and avoid raw payload leakage.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope

- `.planning/ROADMAP.md` - Phase 34 goal, APF-15/APF-16 success criteria, Phase 33 dependency, and Phase 35 deferral.
- `.planning/REQUIREMENTS.md` - APF-15 and APF-16 requirement text plus v1.9 out-of-scope boundaries.
- `.planning/STATE.md` - Current milestone state and Phase 34 readiness.
- `.planning/todos/deferred/2026-06-27-merchant-scope-approval-action.md` - Required Phase 34 approval/action target merchant binding and manager-scope restoration.

### Architecture Target and Normative Contracts

- `docs/target-agent-platform-architecture-plan.md` §13 - Approval / Action / ExecutionBoundary target, no-real-execution boundary, action proposal, approval decision, action draft minimum contracts, and risk/approval split.
- `docs/target-agent-platform-architecture-plan.md` Phase 34 section - Phase 34 implementation notes.
- `docs/contract-spec.md` §8.0 / §8.0.1 - TrustedContext, MerchantScopeV1, role-to-merchant-scope policy, and Phase 29.5 interim approval guard.
- `docs/contract-spec.md` §9.4 / §9.5 - `risk_gate`, `approval_gate`, `action_draft`, and router contracts.
- `docs/contract-spec.md` §10 - AgentState risk, approval, snapshot, and action draft writer ownership.
- `docs/contract-spec.md` §15.3 - `ActionSafetySnapshot` contract and CanonicalHashProfile v1 rules.
- `docs/contract-spec.md` §15.4 / §15.5 / §15.7 - Approval state machine, response type semantics, storage target, revision/hash/version rules.
- `docs/contract-spec.md` §16.1-§16.4 - Action draft, demo mode, no real execution, and idempotency.
- `docs/contract-spec.md` §18 / §18.4 - Persistence transition and event/replay handoff constraints.
- `docs/eval-test-plan.md` - Approval/action contract negative cases, fake approval chat, payload/snapshot mismatch, and no direct action draft/execution bypass.

### Prior Phase Context

- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - Trusted context source and approval/action projection constraints.
- `.planning/phases/28-decision-event-foundation/28-CONTEXT.md` - Decision event envelope, reason-code, version, and resource-ref conventions.
- `.planning/phases/29-tool-platform-boundary/29-CONTEXT.md` - ToolPlatform runtime auth, side-effect, safety snapshot, and node-only action tool constraints.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-CONTEXT.md` - Merchant-bound role semantics, manager approval interim admin-only guard, and Phase 34 handoff.
- `.planning/phases/30-businessfactservice-boundary/30-CONTEXT.md` - BusinessFactService authority, scoped `BusinessFactRefV1`, and no-leak business fact semantics.
- `.planning/phases/31-memory-platform-boundary/31-CONTEXT.md` - Memory contextual-only boundary and non-substitution rules.
- `.planning/phases/32-intent-graph-migration/32-CONTEXT.md` - Target graph vocabulary and `risk_gate` / `approval_gate` / `action_draft` routing constraints.
- `.planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md` - Verified evidence package, claim verification, and blocked action-claim handoff into Phase 34.

### Current Code Sites

- `src/approvals/schemas.py` - Current approval request/decision/result DTOs and action safety/proposed action schema version literals.
- `src/approvals/service.py` - ApprovalService state machine, snapshot persistence, edit/respond/revision handling, and trusted resume payload owner.
- `src/approvals/repository.py` - Approval request/level/assignment/decision/event persistence helpers and resource refs.
- `src/approvals/snapshot_service.py` and `src/approvals/snapshots.py` - Action payload hash and immutable safety snapshot contract.
- `src/actions/schemas.py` - Current `ActionDraftV2Data` and `DraftOutcomeV1` projection contract.
- `src/actions/service.py` and `src/actions/drafts.py` - Durable action draft creation, approval/snapshot/hash validation, idempotency, and demo-only event emission.
- `src/agent/nodes/assess_risk_and_approval.py` - Current legacy risk/snapshot/proposed-action writer that should become target `risk_gate` semantics or compatibility alias.
- `src/agent/nodes/approval_gate.py` - Current interrupt/resume node.
- `src/agent/nodes/action_draft.py` - Current canonical action draft node and trusted approval result validation.
- `src/agent/graph.py`, `src/agent/routing.py`, and `src/agent/graph_vocabulary.py` - Graph routes, target vocabulary, and router edge expectations.
- `src/api/routers/approvals.py` - Approval list/get/decide/resume API and current Phase 29.5 manager fail-closed behavior.
- `src/api/routers/agent_runs.py` and `src/api/routers/traces.py` - Run/trace visibility and approval/action summaries.
- `src/db/models.py` - `ActionSafetySnapshot`, `ApprovalRequest`, `ApprovalLevel`, `ApprovalAssignment`, `ApprovalDecision`, `ApprovalEvent`, and `ActionDraft` persistence models.
- `src/tools/catalog.py`, `src/tools/runtime.py`, `src/tools/platform.py`, and `src/tools/executors/action.py` - Node-only action tool descriptor/runtime path.

### Tests To Inspect Or Extend

- `tests/test_approval_api.py`
- `tests/test_approval_gate.py`
- `tests/test_approval_integration.py`
- `tests/test_execute_action.py`
- `tests/actions/test_action_draft_v2.py`
- `tests/approvals/test_canonical_hash.py`
- `tests/approvals/test_hash_binding.py`
- `tests/approvals/test_multi_level_contract.py`
- `tests/approvals/test_service_transitions.py`
- `tests/approvals/test_single_level_runtime.py`
- `tests/architecture/test_approval_boundaries.py`
- `tests/architecture/test_action_draft_boundaries.py`
- `tests/architecture/test_phase33_rag_claim_boundaries.py`
- `tests/agent/test_nodes/test_assess_risk_and_approval.py`
- `tests/agent/test_nodes/test_claim_verify.py`
- `tests/agent/test_graph.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src.approvals.service.ApprovalService` already owns v2 approval state transitions, expected version guards, edit/respond flows, snapshot persistence, and trusted resume payload generation.
- `ApprovalRequest`, `ApprovalLevel`, `ApprovalAssignment`, `ApprovalDecision`, and `ApprovalEvent` already exist, so Phase 34 can extend/enrich rather than inventing the entire approval state machine.
- `ActionSafetySnapshot` persistence and canonical hash logic already exist and are tested.
- `ActionService.create_coupon_grant_draft(...)` already validates exact payload hash, safety snapshot ref/hash, approved request binding, and demo-only draft outcome.
- `action_draft` already uses `TrustedApprovalResultV1` validation and `TrustedContext` tenant/run matching before invoking the node-only action tool.
- Phase 33 already writes verified evidence/claim verification fields in `AgentState`; Phase 34 can consume those instead of re-validating policy support from scratch.
- Phase 29.5 already removed manager approval list/get/decide access as an interim fail-closed guard, leaving a clear Phase 34 restoration point.

### Established Patterns

- Strict public contracts use Pydantic models with `extra="forbid"`.
- Trusted identity and merchant scope come from `TrustedContextFactory` and projections, not AgentState, LLM output, user payload, memory, or request-body overrides.
- Domain services own authority: BusinessFactService owns current business facts, KnowledgeService/ClaimVerifier own verified policy support, ApprovalService owns approval transitions, and ActionDraftService/ActionService owns durable demo drafts.
- Prompt/API/working-state projections expose safe refs and summaries, not raw approval bodies, safety snapshot JSON, or action payload bodies.
- Tests emphasize both positive contract behavior and negative fail-closed cases.

### Current Gaps To Close

- Current approval/action persistence does not yet expose target merchant binding, business fact refs, claim verification refs, and risk decision refs as first-class Phase 34 contract fields.
- `assess_risk_and_approval` still combines risk evaluation, action proposal shaping, safety snapshot creation, and approval planning under a legacy name.
- Current `approval_gate` interrupt payload is mostly display/control data; it does not itself enforce the full structured approval plan contract.
- Current manager approval queue remains admin-only by Phase 29.5 design; Phase 34 must restore same-merchant manager access only after target merchant binding exists.
- Current action draft no-approval path is intentionally fail-closed. Phase 34 must either keep that disabled by policy or add a durable auto-allowed binding contract owned by `risk_gate`.
- Existing `ActionDraftV2Data` is close to the target but lacks explicit business fact refs, verified evidence refs, claim verification refs, risk decision refs, and target merchant scope.

</code_context>

<specifics>
## Specific Ideas

- The safest Phase 34 default is contract-first hardening: make existing approval/action machinery consume and persist the refs Phase 30/33 now produce, then restore manager scope and only then widen action draft paths.
- Manager same-merchant approval should be restored through target merchant/business-fact binding, not by the rejected `requested_by -> user.merchant_id` shortcut from Phase 29.5.
- Auto-draft should be treated as a durable authorization binding, not as "approval_required=false" in transient graph state.
- Keep the final user-facing wording in demo mode precise: draft created, approval pending, rejected, needs info, or blocked; never executed.
- Planning should expect multiple plans despite ROADMAP's single placeholder, following MOCA's service-boundary phase granularity rule.

</specifics>

<deferred>
## Deferred Ideas

- Full real external execution, outbox, reconciliation, compensation dispatch, and external idempotency workers remain future scope.
- Broad replay/eval hardening for every platform decision belongs to Phase 35, though Phase 34 must leave stable refs and events for that work.
- System-owned wildcard approval/action jobs require a future trusted system context contract and are not part of Phase 34.
- Database/RLS hardening, broad retention lifecycle implementation, role enum cleanup, and merchant-specific policy schema remain Phase 36+ / future hardening.

</deferred>

---

*Phase: 34-approval-and-actiondraft-boundary-hardening*
*Context gathered: 2026-06-29*
