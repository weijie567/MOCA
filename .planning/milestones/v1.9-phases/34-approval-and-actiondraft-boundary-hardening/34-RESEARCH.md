# Phase 34: Approval and ActionDraft Boundary Hardening - Research

**Researched:** 2026-06-29  
**Domain:** Approval/action authorization boundary, risk-gate routing, demo action draft persistence  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

Source for this whole user-constraints block: [VERIFIED: .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-CONTEXT.md]

### Locked Decisions

#### Contract and Persistence Boundary

- **D-01:** Introduce explicit approval/action boundary contracts rather than relying on untyped graph state or raw JSON blobs. Minimum contracts are `ActionProposalV1` / existing `proposed_action.v1`, `RiskDecisionV1`, `ApprovalResultV1`, and `ActionDraftV2Data` with stable refs.
- **D-02:** Phase 34 should persist or denormalize the binding fields needed for authorization, replay handoff, and manager-scoped queues. At minimum, `ApprovalRequest` and `ActionDraft` must carry target merchant binding, business fact refs, verified evidence refs, claim verification refs or a stable claim-verification bundle ref/summary, risk decision refs or safe JSON, action payload hash, safety snapshot ref/hash, approval/revision refs, and idempotency key.
- **D-03:** It is acceptable to extend the existing `approval_requests` / `action_drafts` v2 tables and JSON fields rather than introducing a large new table family, as long as service contracts expose the target fields and tests prove they are not reconstructed from prompts, memory, raw tool payloads, or LLM text.
- **D-04:** Existing `ActionSafetySnapshot` remains the canonical immutable safety binding. Phase 34 should validate and carry it forward; downstream approval/action code must not rebuild snapshots except where ApprovalService creates a new revision for edit/info-supplied material changes.
- **D-05:** `ActionDraftV2Data` should be enriched enough for downstream Phase 35 replay/eval hardening to read stable refs without parsing raw action payloads. Raw payload can remain stored for draft ownership, but prompt/API/working-state projections must expose only safe summaries and refs.

#### Risk Gate and Approval Gate Responsibility Split

- **D-06:** `risk_gate` owns action proposal normalization, risk decision, approval plan generation, blocked/approval-required/auto-draft routing, and safety snapshot creation before either `approval_gate` or `action_draft`.
- **D-07:** `approval_gate` must not re-decide blocked vs approval-required vs auto-draft. It should only create/interrupt approval requests from a structured approval plan, accept trusted `approval_result.v1` resume payloads, and route based on approval state machine results.
- **D-08:** The current `assess_risk_and_approval` node may remain as a compatibility implementation while Phase 34 extracts/labels target `risk_gate` semantics, but planning must not leave approval policy decisions buried in `approval_gate`.
- **D-09:** `route_after_risk` must be deterministic and side-effect-free: blocked -> final response; approval required -> `approval_gate`; auto allowed -> `action_draft`. Invalid or missing risk/action bindings fail closed to approval/manual-review/final safe response.
- **D-10:** `route_after_approval` must follow the spec transition table: approved all required levels -> `action_draft`; next required level pending -> stay approval/interrupted; edit -> `risk_gate`; respond/needs_info -> interrupted lifecycle finalizer; reject/ignore/expired/cancelled -> final safe response.

#### Target Merchant and Manager Approval Scope

- **D-11:** Target merchant binding must come from scoped `BusinessFactRefV1` / `BusinessFactResultV1` authority or a service-approved target merchant field derived from those refs. It must not be inferred from `requested_by`, final response text, memory, RAG evidence, or user/model payloads.
- **D-12:** `ApprovalRequest` and `ActionDraft` should carry a target merchant id or target merchant ref when the action is merchant-scoped. Business fact refs remain the authority; the denormalized merchant field is for filtering and fail-closed route/API checks.
- **D-13:** Manager list/get/decide should be restored only for approvals whose target merchant is inside the manager actor's trusted merchant scope. If target merchant is missing, ambiguous, multi-merchant, or outside scope, manager access fails closed. `admin` remains explicitly platform-wide.
- **D-14:** Approval resume for manager actors must use `TrustedContextFactory` merchant scope from the actor plus trusted server tool permission injection only. `ACTION_DRAFT_PERMISSION` may be injected by server code, but it must not widen merchant scope.
- **D-15:** Non-admin human actors must never receive wildcard `server_merchant_scope` through approval resume. Future system-owned wildcard approval/action jobs require a separate trusted system context contract, not `TrustedContextFactory.create_from_request(user=...)`.

#### Auto-Draft and No-Approval Binding

- **D-16:** Keep the default no-approval action path fail-closed unless `risk_gate` writes a durable, exact auto-allowed binding with action payload hash, safety snapshot ref/hash, risk decision, target merchant, business fact refs, verified evidence refs, claim verification refs, and idempotency key.
- **D-17:** Phase 34 should define the auto-allowed contract even if current policy keeps all action-bearing merchant operations approval-required. This satisfies the APF-16 ownership split without broadening unsafe behavior.
- **D-18:** Do not implement broad low-risk real actions. If any auto-draft is enabled, it creates a demo `ActionDraft` and `draft_outcome.v1(status=not_executed_demo, external_side_effect=false)` only.
- **D-19:** Existing `ActionService` behavior that rejects missing approval as `AUTO_ALLOWED_BINDING_REQUIRED` is a safe baseline. Planning may replace it only with a durable auto-allowed binding check owned by `risk_gate`, not with implicit "approval_required=false" trust.

#### Approval Revision and Action Draft Binding

- **D-20:** Approval accept/approve authorizes only the exact approval revision's action payload hash and safety snapshot hash. Any changed action args, target, amount, evidence refs, policy/risk/retrieval versions, business fact refs, or claim verification support invalidates the old approval and requires revalidation/revision.
- **D-21:** Approval edit must create a new proposed action revision and route back through risk/snapshot validation. It must not route directly to draft creation.
- **D-22:** Approval respond/needs_info preserves interrupted lifecycle state and cannot complete the run through ordinary clarification/final-response/memory-write as if no approval were pending.
- **D-23:** `action_draft` must validate exact trusted approval result or durable auto-allowed binding against current state, trusted context tenant/run, payload hash, safety snapshot ref/hash, and target merchant binding before invoking the node-only action tool.
- **D-24:** Idempotency keys must include tenant id, run id, approval revision or auto-allowed marker, action type, target id, and action payload hash so the same target with different payloads does not collide.

#### No-Real-Execution Boundary

- **D-25:** Phase 34 must not introduce external adapters, outbox dispatch, reconciliation, compensation workers, action execution records, or external side effects.
- **D-26:** `execute_action` remains a compatibility shim only if it still exists. New graph/action paths should target canonical `action_draft` and `draft_outcome.v1`.
- **D-27:** Final responses must say draft-created / pending approval / rejected / needs info, never "coupon issued", "refund completed", or other real side-effect wording.

#### Plan Granularity and Verification

- **D-28:** Do not plan Phase 34 as one large `34-01-PLAN.md` despite the roadmap placeholder. This phase spans contracts/schema, risk/action proposal binding, approval service/API scope, graph routing, action draft service, and final verification. MOCA project rules require splitting into dependency-ordered plans before execution.
- **D-29:** Recommended plan units:
  - contracts and persistence bindings for `ActionProposal` / `RiskDecision` / approval / draft refs;
  - `risk_gate` responsibility extraction, approval plan, target merchant/business/evidence/claim/risk binding, and durable auto-allowed contract;
  - `approval_gate` / ApprovalService / approval API manager-scope restore and trusted resume hardening;
  - `agent_runs` approval-interrupt bridge and live approval-required safe projection;
  - `action_draft` / ActionService validation, draft schema enrichment, idempotency, and no-real-execution projection cleanup;
  - final static/focused/eval closure.
- **D-30:** Verification must use MOCA's valid local entrypoint: `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or `.venv/bin/pytest ...`. Bare `pytest` and bare `python -m pytest` are invalid for this repository.
- **D-31:** Tests must prove ordinary chat cannot forge approval/action authority, payload changes invalidate old approval, unsupported claims cannot reach approval/action, manager A cannot see/decide merchant B approvals, missing target merchant fails closed for managers, non-admin resume cannot get wildcard merchant scope, and no full real execution is introduced.

### Claude's Discretion

- Exact class/module names are planner discretion, but contracts should live under the owning domains (`src/approvals/`, `src/actions/`, and shared schemas only where reuse requires it).
- Exact persistence shape is planner discretion if it preserves stable service contracts and fail-closed manager filtering.
- Exact event payload names are planner discretion, but they must use the Phase 28 decision-event/redaction/resource-ref conventions and avoid raw payload leakage.

### Deferred Ideas (OUT OF SCOPE)

- Full real external execution, outbox, reconciliation, compensation dispatch, and external idempotency workers remain future scope.
- Broad replay/eval hardening for every platform decision belongs to Phase 35, though Phase 34 must leave stable refs and events for that work.
- System-owned wildcard approval/action jobs require a future trusted system context contract and are not part of Phase 34.
- Database/RLS hardening, broad retention lifecycle implementation, role enum cleanup, and merchant-specific policy schema remain Phase 36+ / future hardening.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APF-15 | Action proposals, approval decisions, and action drafts bind structured payloads to business fact refs, verified evidence refs, claim verification refs, risk decisions, payload hashes, and safety snapshots. [VERIFIED: .planning/REQUIREMENTS.md] | Use contract/schema/persistence plan first; current ApprovalRequest and ActionDraft models have payload/snapshot fields but lack first-class target merchant, business fact, claim verification, and risk-decision binding fields. [VERIFIED: src/db/models.py; VERIFIED: src/approvals/schemas.py; VERIFIED: src/actions/schemas.py] |
| APF-16 | `risk_gate` owns blocked/approval-required/auto-draft decisions, while `approval_gate` only executes approval plans, trusted resume, interrupt, and revision state machine behavior. [VERIFIED: .planning/REQUIREMENTS.md] | Split risk-gate extraction from approval-gate/API work; current `assess_risk_and_approval` carries target risk-gate semantics while graph routing still returns the legacy node name for edits. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py; VERIFIED: src/agent/graph.py; CITED: docs/contract-spec.md Section 9.4-9.5] |
</phase_requirements>

## Summary

Phase 34 is a boundary-hardening phase, not a new execution feature: it must make action proposals, approval decisions, and demo action drafts carry stable authority refs and exact hashes while preserving the existing no-real-execution contract. [VERIFIED: .planning/ROADMAP.md; VERIFIED: .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-CONTEXT.md; CITED: docs/target-agent-platform-architecture-plan.md Section 13; CITED: docs/contract-spec.md Section 16.1-16.4]

The current implementation already has useful foundations: strict Pydantic approval DTOs, `TrustedApprovalResultV1`, canonical payload hashing, immutable `ActionSafetySnapshot`, an approval state machine, and a demo-only `ActionDraftV2Data`. [VERIFIED: src/approvals/schemas.py; VERIFIED: src/approvals/snapshots.py; VERIFIED: src/approvals/snapshot_service.py; VERIFIED: src/approvals/service.py; VERIFIED: src/actions/schemas.py; VERIFIED: src/actions/service.py] The main gaps are binding target merchant/business fact/claim/risk refs into persisted approval and draft records, restoring manager approval scope through target merchant authority, and making the legacy `assess_risk_and_approval` implementation express target `risk_gate` ownership clearly. [VERIFIED: src/db/models.py; VERIFIED: src/api/routers/approvals.py; VERIFIED: src/agent/nodes/assess_risk_and_approval.py; VERIFIED: .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-CONTEXT.md]

Planning must split Phase 34 into dependency-ordered plans because the phase crosses contracts/schema, graph routing, ApprovalService/API authorization, ActionService validation, and final verification boundaries. [VERIFIED: AGENTS.md; VERIFIED: CLAUDE.md; VERIFIED: .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-CONTEXT.md D-28/D-29]

**Primary recommendation:** Use six plans in this order: contracts+persistence, `risk_gate` binding, approval/API manager-scope restore, `agent_runs` approval-interrupt bridge, action-draft validation/projection, then static/focused/eval closure. [VERIFIED: .planning/phases/34-approval-and-actiondraft-boundary-hardening/34-CONTEXT.md D-29]

## Project Constraints (from CLAUDE.md)

- Local debugging, startup, verification, UI manual testing, API testing, RAG/agent/memory/tool-call investigation failures must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` after handling. [VERIFIED: CLAUDE.md]
- Phase-level plans and larger changes use the dual-review workflow: GSD plan/checker first, Codex independent review next, and accepted structural/multi-file plan repairs go to Codex rather than ad hoc planner edits. [VERIFIED: CLAUDE.md]
- `docs/contract-spec.md` is the normative contract source for contract semantics, but implementation scope is decided per phase and spec/implementation mismatch must be recorded rather than silently ignored. [VERIFIED: CLAUDE.md]
- Deferred items must name a target phase rather than saying only "future" or "later." [VERIFIED: CLAUDE.md]
- Phase B closeout review requires a difference record when implementation intentionally diverges from the contract spec. [VERIFIED: CLAUDE.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Action proposal normalization and risk decision | API / Backend graph service | Knowledge/Business domain services | `risk_gate` owns action proposal normalization, risk decision, approval plan generation, routing, and safety snapshot creation, while business facts and verified evidence come from prior domain services. [VERIFIED: 34-CONTEXT.md D-06; CITED: docs/contract-spec.md Section 9.5] |
| Safety snapshot creation | API / Backend service | Database / Storage | `risk_gate` creates the action safety snapshot before approval or action draft, and downstream code validates the stored snapshot ref/hash. [CITED: docs/contract-spec.md Section 15.3; VERIFIED: src/approvals/snapshots.py; VERIFIED: src/approvals/snapshot_service.py] |
| Approval state machine | API / Backend service | Frontend/API router entry | ApprovalService owns request/decision/revision state transitions, while the approvals API is the trusted command entry for human decisions. [VERIFIED: src/approvals/service.py; VERIFIED: src/api/routers/approvals.py; CITED: docs/contract-spec.md Section 15.4] |
| Manager approval scope | API / Backend authorization | Database / Storage | Manager list/get/decide must filter by explicit target merchant binding stored on approval/draft resources, with admin remaining platform-wide. [VERIFIED: 34-CONTEXT.md D-11-D-15; CITED: docs/contract-spec.md Section 8.0.1] |
| Durable demo action draft | API / Backend service | Database / Storage | ActionService creates `ActionDraft` records and `draft_outcome.v1` in demo mode after exact approval/snapshot/hash validation. [VERIFIED: src/actions/service.py; VERIFIED: src/actions/schemas.py; CITED: docs/contract-spec.md Section 16.1-16.4] |
| No-real-execution boundary | API / Backend service and tests | Final response projection | The phase must not add external adapters, outbox workers, real side effects, or execution records, and final responses must describe draft/pending/rejected states rather than real execution. [VERIFIED: 34-CONTEXT.md D-25-D-27; VERIFIED: tests/architecture/test_action_draft_boundaries.py; VERIFIED: src/agent/nodes/final_response.py] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | >=3.12 project requirement; local `python3` is 3.13.3 | Runtime language | Project code uses Python 3.12+ features and local validation must avoid older Python PATH pollution. [VERIFIED: pyproject.toml; VERIFIED: python3 --version; VERIFIED: AGENTS.md] |
| Pydantic | 2.13.4 | Strict DTO and contract validation | Existing approval/action/knowledge/business contracts use Pydantic models with `extra="forbid"`, so Phase 34 should extend that pattern. [VERIFIED: uv.lock; VERIFIED: src/approvals/schemas.py; VERIFIED: src/actions/schemas.py; VERIFIED: src/knowledge/schemas.py] |
| SQLAlchemy async | 2.0.49 | ORM persistence for approval/snapshot/draft rows | Existing approval/draft/snapshot models and repositories are SQLAlchemy ORM classes and async services. [VERIFIED: uv.lock; VERIFIED: src/db/models.py; VERIFIED: src/approvals/repository.py; VERIFIED: src/actions/drafts.py] |
| Alembic | 1.18.4 | Schema migrations | Project migrations live under `src/db/migrations/versions`, with `017_tool_policy_events.py` currently present, so Phase 34 schema additions belong in a new migration there. [VERIFIED: uv.lock; VERIFIED: rg --files] |
| FastAPI | 0.136.1 | Approval API routes | Approval list/get/decide/resume endpoints are FastAPI router code in `src/api/routers/approvals.py`. [VERIFIED: uv.lock; VERIFIED: src/api/routers/approvals.py] |
| LangGraph | 1.1.10 | Agent graph routing and interrupts | Current graph routing registers approval/action nodes and uses router functions around risk and approval state. [VERIFIED: uv.lock; VERIFIED: src/agent/graph.py] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 | Focused unit/integration/architecture validation | Use through `uv run pytest ...` or `.venv/bin/pytest ...`; bare `pytest` is invalid in MOCA. [VERIFIED: uv.lock; VERIFIED: AGENTS.md] |
| pytest-asyncio | 1.3.0 | Async DB/service tests | Approval and action services use async SQLAlchemy sessions and test fixtures. [VERIFIED: uv.lock; VERIFIED: tests/conftest.py] |
| Docker | 29.4.2 local CLI/daemon | Local Postgres-backed test environment | Docker is available locally; DB CLI tools are not on PATH, so DB availability should be validated by test fixtures or compose, not by `pg_isready`. [VERIFIED: docker --version; VERIFIED: docker info; VERIFIED: command -v psql; VERIFIED: command -v pg_isready] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extending current approval/draft tables | New approval/action binding table family | Locked Phase 34 context allows extending existing v2 tables if service contracts expose stable fields and tests prevent reconstruction from unsafe sources. [VERIFIED: 34-CONTEXT.md D-03] |
| Keeping legacy `assess_risk_and_approval` name only | Full immediate rename to `risk_gate` | Context allows a compatibility implementation, but planning must surface target `risk_gate` semantics and must not leave approval policy decisions in `approval_gate`. [VERIFIED: 34-CONTEXT.md D-08; CITED: docs/target-agent-platform-architecture-plan.md Section 4/13] |
| Enabling low-risk auto-draft broadly | Keep no-approval path fail-closed while defining durable auto-allowed contract | Current service behavior rejects missing approvals as `AUTO_ALLOWED_BINDING_REQUIRED`, which is a safe baseline unless risk_gate writes a durable exact auto-allowed binding. [VERIFIED: 34-CONTEXT.md D-16-D-19; VERIFIED: src/actions/service.py] |

**Installation:**
```bash
# No new runtime packages are recommended for Phase 34.
uv sync --extra dev
```
[VERIFIED: pyproject.toml; VERIFIED: uv.lock]

**Version verification:** Recommended versions above were read from `uv.lock`, project requirements from `pyproject.toml`, and local tool availability from `uv --version`, `python3 --version`, and `docker --version`. [VERIFIED: uv.lock; VERIFIED: pyproject.toml; VERIFIED: uv --version; VERIFIED: python3 --version; VERIFIED: docker --version]

## Architecture Patterns

### System Architecture Diagram

```mermaid
flowchart TD
    ClaimVerify[claim_verify: verified evidence + claim bundle] --> RiskGate[risk_gate / legacy assess_risk_and_approval]
    BusinessRefs[BusinessFactRefV1 / BusinessFactResultV1 authority] --> RiskGate
    RiskGate --> Proposal[ActionProposalV1 + payload hash]
    RiskGate --> RiskDecision[RiskDecisionV1 + approval plan]
    RiskGate --> Snapshot[ActionSafetySnapshot ref/hash]
    RiskGate --> Route{deterministic route_after_risk}
    Route -->|blocked / invalid binding| FinalSafe[final_response safe status]
    Route -->|approval required| ApprovalGate[approval_gate]
    Route -->|durable auto-allowed binding only| ActionDraft[action_draft]
    ApprovalGate --> ApprovalService[ApprovalService state machine]
    ApprovalService -->|trusted approval_result.v1| Resume[trusted graph resume]
    Resume --> RouteApproval{route_after_approval}
    RouteApproval -->|approved exact revision| ActionDraft
    RouteApproval -->|edit| RiskGate
    RouteApproval -->|respond / pending / reject| FinalSafe
    ActionDraft --> ActionService[ActionService create demo draft]
    ActionService --> Draft[(ActionDraft + draft_outcome.v1)]
    Draft --> FinalSafe
```
[VERIFIED: src/agent/graph.py; VERIFIED: src/agent/nodes/assess_risk_and_approval.py; VERIFIED: src/agent/nodes/approval_gate.py; VERIFIED: src/agent/nodes/action_draft.py; VERIFIED: src/actions/service.py; CITED: docs/contract-spec.md Section 9.4-9.5]

### Recommended Project Structure

```text
src/
|-- approvals/        # Approval contracts, state machine, snapshot binding, manager-scope checks.
|-- actions/          # ActionDraftV2Data enrichment and demo draft validation.
|-- agent/nodes/      # risk_gate compatibility implementation, approval_gate, action_draft.
|-- agent/            # routing and vocabulary updates.
|-- api/routers/      # trusted approval list/get/decide/resume API.
|-- db/migrations/    # new Phase 34 binding-field migration.
`-- platform/         # TrustedContextFactory and merchant-scope projection reuse.
```
[VERIFIED: rg --files; VERIFIED: 34-CONTEXT.md canonical refs]

### Pattern 1: Contract-First Binding

**What:** Extend strict Pydantic contracts and database rows before widening manager access or action draft routes. [VERIFIED: 34-CONTEXT.md D-01-D-05; VERIFIED: src/approvals/schemas.py; VERIFIED: src/actions/schemas.py]  
**When to use:** Use this as Plan 34-01 because later manager/API/action-draft checks need stored target merchant, business fact refs, verified evidence refs, claim refs, risk decisions, payload hash, and safety snapshot ref/hash. [VERIFIED: 34-CONTEXT.md D-02; VERIFIED: .planning/ROADMAP.md]

**Example:**
```python
class ApprovalRequestCreateCommand(BaseModel):
    """Trusted server-side input for creating an executable v2 approval request."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    run_id: UUID
    thread_id: str = Field(min_length=1)
    requested_by: UUID
    proposed_action: dict[str, Any]
    action_payload_hash: str | None = None
    safety_snapshot_ref: str | None = None
    safety_snapshot_hash: str | None = None
    evidence_refs: list[EvidenceRefV1] = Field(min_length=1)
```
[VERIFIED: src/approvals/schemas.py]

### Pattern 2: Canonical Snapshot and Hash Reuse

**What:** Reuse `compute_action_payload_hash`, `ActionSafetySnapshot`, and persisted snapshot validation instead of adding new hash formats. [VERIFIED: src/approvals/snapshot_service.py; VERIFIED: src/approvals/snapshots.py]  
**When to use:** Any new Phase 34 ref binding must be compared alongside exact `action_payload_hash` and `safety_snapshot_hash`; changed payload/evidence/policy/risk/retrieval/business/claim inputs invalidate old approval. [VERIFIED: 34-CONTEXT.md D-20; CITED: docs/contract-spec.md Section 15.3]

**Example:**
```python
def build_action_safety_snapshot(
    *,
    tenant_id: str,
    run_id: str,
    snapshot_id: str,
    snapshot_ref: str,
    policy_config_version: str,
    risk_config_version: str,
    retrieval_config_version: str,
    evidence: list[EvidenceRefV1 | Mapping[str, Any]],
    action_payload_hash: str,
    created_at: str | datetime,
    **extra: Any,
) -> ActionSafetySnapshot:
    ...
```
[VERIFIED: src/approvals/snapshots.py]

### Pattern 3: Fail-Closed Router Before Draft

**What:** Keep routing deterministic and conservative; if claim verification, proposed action, snapshot binding, or safety verification is missing, route to safe final response. [VERIFIED: src/agent/graph.py]  
**When to use:** Update `route_after_risk` to return `action_draft` only when a durable auto-allowed binding exists; otherwise keep the current final-response fail-closed behavior. [VERIFIED: 34-CONTEXT.md D-16-D-19; VERIFIED: src/agent/graph.py]

**Example:**
```python
def route_after_risk(state: AgentState) -> str:
    if not _verification_allows_action_path(state):
        return "final_response"
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if not proposed:
        return "final_response"
    if not _snapshot_binding_ready(state):
        return "final_response"
    if state.get("safety_snapshot_verified") is not True:
        return "final_response"
    if risk.get("approval_required"):
        return "approval_gate"
    return "final_response"
```
[VERIFIED: src/agent/graph.py]

### Pattern 4: Trusted Resume Without Scope Widening

**What:** Approval resume should construct a trusted context from the authenticated actor and may inject server tool permissions, but must not inject wildcard merchant scope for non-admin humans. [VERIFIED: 34-CONTEXT.md D-14-D-15; VERIFIED: src/platform/trusted_context.py; VERIFIED: src/api/routers/approvals.py]  
**When to use:** Plan manager approval API restoration only after target merchant binding exists and keep `TrustedContextFactory.create_from_request(user=...)` as the human-context factory. [VERIFIED: docs/contract-spec.md Section 8.0.1; VERIFIED: .planning/todos/deferred/2026-06-27-merchant-scope-approval-action.md]

**Example:**
```python
permissions = list(dict.fromkeys(
    permissions + cls._validated_server_tool_permissions(server_tool_permissions)
))
merchant_scope = cls._merchant_scope_from_user(
    user,
    server_merchant_scope=server_merchant_scope,
)
```
[VERIFIED: src/platform/trusted_context.py]

### Anti-Patterns to Avoid

- **One giant Phase 34 plan:** This violates MOCA phase-level granularity rules and locked D-28. [VERIFIED: AGENTS.md; VERIFIED: CLAUDE.md; VERIFIED: 34-CONTEXT.md D-28]
- **Target merchant from `requested_by`:** Phase 29.5 explicitly rejected `requested_by -> user.merchant_id` as an authorization approximation until Phase 34 binding exists. [CITED: docs/contract-spec.md Section 8.0.1; VERIFIED: .planning/ROADMAP.md]
- **Approval gate re-deciding policy:** `approval_gate` must execute plans and trusted resumes, not decide blocked/approval-required/auto-draft. [VERIFIED: 34-CONTEXT.md D-07; CITED: docs/contract-spec.md Section 9.5]
- **Treating `approval_required=false` as authorization:** Current safe baseline rejects missing approval unless a durable exact auto-allowed binding exists. [VERIFIED: 34-CONTEXT.md D-16-D-19; VERIFIED: src/actions/service.py]
- **Adding real execution plumbing:** External adapters, outbox, reconciliation, compensation, execution records, and real side effects are out of scope. [VERIFIED: 34-CONTEXT.md D-25; CITED: docs/contract-spec.md Section 16.1-16.4]

## Recommended Plan Units

| Plan | Scope | File Surfaces | Exit Criteria |
|------|-------|---------------|---------------|
| 34-01 Contracts and persistence bindings | Add/extend contracts for `ActionProposalV1`/`proposed_action.v1`, `RiskDecisionV1`, approval result binding, and `ActionDraftV2Data`; add DB columns/migration for target merchant, business refs, evidence refs, claim refs, risk decision, payload/snapshot hashes, approval/revision/idempotency refs. [VERIFIED: 34-CONTEXT.md D-01-D-05] | `src/approvals/schemas.py`, `src/actions/schemas.py`, `src/db/models.py`, `src/db/migrations/versions/*`, `tests/approvals/*`, `tests/actions/test_action_draft_v2.py`. [VERIFIED: rg --files] | New active approval/draft rows can persist and return stable binding fields; legacy rows missing target merchant fail closed for manager authorization rather than being guessed. [VERIFIED: 34-CONTEXT.md D-02/D-11-D-13] |
| 34-02 `risk_gate` binding and routing | Extract/label risk-gate semantics from `assess_risk_and_approval`; bind business/evidence/claim/risk refs into proposal, risk decision, approval plan, snapshot, and optional auto-allowed contract. [VERIFIED: 34-CONTEXT.md D-06-D-10/D-16-D-19] | `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/graph.py`, `src/agent/graph_vocabulary.py`, `src/agent/state.py`, `tests/test_graph_routing.py`, `tests/agent/test_nodes/test_assess_risk_and_approval.py`, `tests/architecture/test_phase33_rag_claim_boundaries.py`. [VERIFIED: rg --files] | Unsupported claims fail closed before approval/action; `route_after_risk` is deterministic; any auto-draft route requires durable binding. [VERIFIED: docs/eval-test-plan.md; VERIFIED: src/agent/graph.py] |
| 34-03 ApprovalService/API manager scope | Restore manager list/get/decide only through explicit target merchant/business fact binding; keep trusted resume free of non-admin wildcard `server_merchant_scope`; make ApprovalService reject stale/mismatched binding refs. [VERIFIED: 34-CONTEXT.md D-11-D-15/D-20-D-22] | `src/approvals/service.py`, `src/approvals/repository.py`, `src/api/routers/approvals.py`, `src/api/schemas/approvals.py`, `src/platform/trusted_context.py`, `tests/test_approval_api.py`, `tests/platform/test_merchant_scope.py`, `tests/tools/test_merchant_scope_static.py`. [VERIFIED: rg --files] | Manager A cannot list/get/decide merchant B; missing/ambiguous target merchant fails closed; resume injects tool permission but not wildcard merchant scope. [VERIFIED: .planning/ROADMAP.md; VERIFIED: tests/test_approval_api.py; VERIFIED: tests/tools/test_merchant_scope_static.py] |
| 34-04 agent_runs approval-interrupt bridge | Preserve Phase 34 target merchant/business/evidence/claim/risk refs when live graph interrupts create ApprovalRequest rows; expose only safe approval-required payload refs/summaries. [VERIFIED: 34-CONTEXT.md D-02/D-05/D-29] | `src/api/routers/agent_runs.py`, `src/api/schemas/agent_runs.py`, `tests/test_agent_runs_api.py`. [VERIFIED: rg --files] | Approval interrupt creation no longer drops Phase 34 bindings; spoofed run/action identities still fail closed; broad trace API projection remains Phase 35. [VERIFIED: src/api/routers/agent_runs.py; VERIFIED: tests/test_agent_runs_api.py] |
| 34-05 Action draft validation/projection | Enrich draft schema and service validation with target merchant/business/evidence/claim/risk refs; preserve idempotency shape and demo-only draft outcome; keep tool node-only. [VERIFIED: 34-CONTEXT.md D-23-D-27] | `src/actions/service.py`, `src/actions/drafts.py`, `src/actions/schemas.py`, `src/tools/executors/action.py`, `src/tools/catalog.py`, `src/agent/nodes/action_draft.py`, `src/agent/nodes/final_response.py`, `src/agent/working_state.py`, `tests/test_execute_action.py`, `tests/actions/test_action_draft_v2.py`, `tests/architecture/test_action_draft_boundaries.py`. [VERIFIED: rg --files] | Exact trusted approval or durable auto-allowed binding is required; payload/target/ref changes invalidate old approval; final response still says draft/not executed. [VERIFIED: src/actions/service.py; VERIFIED: src/agent/nodes/final_response.py; VERIFIED: tests/architecture/test_action_draft_boundaries.py] |
| 34-06 Static/focused/eval closure | Run focused suites, static guards, and eval negative-case mapping; update any phase validation artifacts if planner/executor owns them. [VERIFIED: docs/eval-test-plan.md; VERIFIED: 34-CONTEXT.md D-30-D-31] | `tests/architecture/*approval*`, `tests/architecture/*action*`, `tests/test_agent_runs_api.py`, `tests/test_graph_routing.py`, `tests/test_approval_api.py`, `tests/test_execute_action.py`, docs/eval-test-plan.md if acceptance mapping needs notes. [VERIFIED: rg --files] | Focused APF-15/APF-16 tests cover chat forgery, payload change, unsupported claims, manager scope, wildcard scope, agent_runs bridge, and no real execution. [VERIFIED: 34-CONTEXT.md D-31; VERIFIED: docs/eval-test-plan.md] |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Payload hashing | New ad hoc hash functions or JSON string sorting | `src.approvals.snapshot_service.compute_action_payload_hash` and `src.common.canonical_hash` | Existing approval/action code already uses canonical profile hashing for proposed actions. [VERIFIED: src/approvals/snapshot_service.py] |
| Safety snapshots | New mutable policy/evidence snapshot format | `ActionSafetySnapshot` and `persist_action_safety_snapshot` | Existing snapshot contract rejects raw payload keys and binds evidence/config/payload material. [VERIFIED: src/approvals/snapshots.py; VERIFIED: src/approvals/snapshot_service.py] |
| Approval transitions | Router-level status mutation | `ApprovalService` and repository methods | ApprovalService already owns expected-version guards, edit/respond, decisions, and trusted result generation. [VERIFIED: src/approvals/service.py; VERIFIED: src/approvals/repository.py] |
| Trusted identity and merchant scope | User/body/model state as authority | `TrustedContextFactory`, `MerchantScopeV1`, and authenticated actor context | Trusted context source is API/auth/run state, and non-admin wildcard scope must be rejected. [VERIFIED: src/platform/trusted_context.py; CITED: docs/contract-spec.md Section 8.0/8.0.1] |
| Business fact authority | RAG evidence, memory, or final response text | `BusinessFactRefV1` / BusinessFactService outputs | Business facts are separate authority refs and cannot be replaced by policy evidence or memory. [VERIFIED: src/tools/contracts.py; CITED: docs/contract-spec.md Section 13; VERIFIED: docs/target-agent-platform-architecture-plan.md] |
| Policy evidence and claim support | Raw snippets or LLM paraphrase | `VerifiedEvidencePackageV1`, `ClaimVerificationBundleV1`, and safe support refs | Phase 33 created verified evidence and claim verification contracts that Phase 34 should consume. [VERIFIED: src/knowledge/schemas.py; VERIFIED: src/agent/state.py; VERIFIED: 34-CONTEXT.md] |
| Action dispatch | Direct write tool invocation from chat/model | Node-only `create_coupon_grant_draft` through `action_draft` and ToolPlatform | The action tool is cataloged as node-only and requires safety snapshot/idempotency fields. [VERIFIED: src/tools/catalog.py; VERIFIED: src/agent/nodes/action_draft.py] |

**Key insight:** Phase 34 is mostly about making existing authoritative contracts meet at one boundary; custom shortcuts are risky because every shortcut tends to bypass target merchant authority, exact hash binding, trusted resume, or the no-real-execution guarantee. [VERIFIED: 34-CONTEXT.md; CITED: docs/contract-spec.md Sections 8/9/15/16]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Existing Postgres-backed approval/action tables include `approval_requests`, `action_drafts`, `action_safety_snapshots`, and related approval level/assignment/decision/event rows; current ORM models do not expose all Phase 34 target binding fields. [VERIFIED: src/db/models.py; VERIFIED: src/db/migrations/versions/005_approval_tables.py; VERIFIED: src/db/migrations/versions/008_approval_state_machine.py; VERIFIED: src/db/migrations/versions/009_action_draft_v2.py] | Add Alembic migration under `src/db/migrations/versions`; make new binding fields nullable/backfillable where needed; do not authorize manager/action paths from legacy rows with missing target merchant/business binding. [CITED: docs/contract-spec.md Section 18.2; VERIFIED: 34-CONTEXT.md D-02/D-13] |
| Live service config | No approval/action external UI config was found in `src`, `docker-compose.yml`, `.env.example`, `AGENTS.md`, or `CLAUDE.md`; only an unrelated study `launchd` helper exists under `scripts/study`. [VERIFIED: rg "n8n|Datadog|Cloudflare|Tailscale|launchd|systemd|pm2|Task Scheduler|cron|outbox|worker"] | No live service config migration is required for Phase 34; do not add outbox/worker config. [VERIFIED: 34-CONTEXT.md D-25] |
| OS-registered state | No approval/action launchd/systemd/pm2/Task Scheduler registration was found; study-plan launchd files are unrelated to approval/action runtime. [VERIFIED: rg "launchd|systemd|pm2|Task Scheduler|cron"] | None for Phase 34. [VERIFIED: rg results] |
| Secrets/env vars | Current environment config includes `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, and `APPROVAL_SLA_SCANNER_ENABLED`; no approval/action-specific secret or env var rename is required by this phase. [VERIFIED: .env.example; VERIFIED: docker-compose.yml; VERIFIED: src/config.py; VERIFIED: tests/conftest.py] | No secret rename; keep any tests using project entrypoint and local test DB settings. [VERIFIED: AGENTS.md; VERIFIED: tests/conftest.py] |
| Build artifacts | `moca.egg-info` and multiple `__pycache__` directories exist; they are generic Python artifacts and do not encode approval/action binding state. [VERIFIED: find . -maxdepth 3 -name "*.egg-info" -o -name "__pycache__"] | No build-artifact migration unless implementation changes packaging metadata, which Phase 34 research does not recommend. [VERIFIED: pyproject.toml; VERIFIED: 34-CONTEXT.md] |

## Common Pitfalls

### Pitfall 1: Manager Scope From Requester Identity
**What goes wrong:** Manager approval restoration becomes tenant-wide or requester-derived instead of target-merchant-derived. [VERIFIED: docs/contract-spec.md Section 8.0.1; VERIFIED: .planning/ROADMAP.md]  
**Why it happens:** Current API is admin-only and list-pending is tenant-level, so a naive restoration can add `manager` back to `APPROVAL_ROLES` without target merchant filtering. [VERIFIED: src/api/routers/approvals.py; VERIFIED: src/approvals/service.py]  
**How to avoid:** Add target merchant/business fact binding first, then filter list/get/decide against trusted actor merchant scope. [VERIFIED: 34-CONTEXT.md D-11-D-13]  
**Warning signs:** A plan edits only `APPROVAL_ROLES` or uses `requested_by`, user body, or final response text to infer merchant scope. [VERIFIED: 34-CONTEXT.md D-11; VERIFIED: src/api/routers/approvals.py]

### Pitfall 2: Approval Required Flag Becomes Authorization
**What goes wrong:** `approval_required=false` lets a model-shaped state create a draft. [VERIFIED: 34-CONTEXT.md D-16-D-19]  
**Why it happens:** Current router has a comment that Phase 14 has no durable auto-allowed binding, and a planner may mistake that as only historical behavior. [VERIFIED: src/agent/graph.py]  
**How to avoid:** Keep no-approval path fail-closed unless `risk_gate` writes a durable auto-allowed record with exact payload/snapshot/refs/idempotency. [VERIFIED: 34-CONTEXT.md D-16]  
**Warning signs:** Tests do not cover no-approval draft rejection or durable auto-allowed binding mismatch. [VERIFIED: tests/test_execute_action.py; VERIFIED: tests/test_graph_routing.py]

### Pitfall 3: Approval Gate Re-Decides Risk
**What goes wrong:** Approval code mixes policy routing with state machine behavior, making replay and revision invalidation ambiguous. [VERIFIED: 34-CONTEXT.md D-06-D-10]  
**Why it happens:** The legacy `assess_risk_and_approval` name already combines multiple semantics, and `approval_gate` interrupt payloads are display/control-heavy. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py; VERIFIED: src/agent/nodes/approval_gate.py]  
**How to avoid:** Make `risk_gate` produce structured approval plan and safety binding; keep `approval_gate` limited to request creation, interrupt, trusted resume, and revision state machine. [CITED: docs/contract-spec.md Section 9.4-9.5; VERIFIED: 34-CONTEXT.md D-06-D-07]  
**Warning signs:** `approval_gate` code starts checking unsupported claims, target merchant derivation, or risk thresholds. [VERIFIED: 34-CONTEXT.md D-07]

### Pitfall 4: Snapshot Rebuild Downstream
**What goes wrong:** Action draft or approval resume silently rebuilds a snapshot and approves a different material set. [VERIFIED: 34-CONTEXT.md D-04/D-20/D-23]  
**Why it happens:** Evidence refs and policy/risk/retrieval config versions are easy to pass as loose JSON unless exact snapshot ref/hash is treated as the authority. [VERIFIED: src/approvals/snapshots.py; CITED: docs/contract-spec.md Section 15.3]  
**How to avoid:** Downstream services validate existing snapshot ref/hash/action hash and only ApprovalService edit/info revision paths create new snapshots. [VERIFIED: src/actions/service.py; VERIFIED: src/approvals/service.py; CITED: docs/contract-spec.md Section 15.3]  
**Warning signs:** New code calls snapshot build helpers in `action_draft` or after approval resume. [VERIFIED: 34-CONTEXT.md D-04]

### Pitfall 5: No-Real-Execution Wording Drift
**What goes wrong:** The system still creates only a draft but final text says the coupon/refund/ticket was issued or completed. [VERIFIED: 34-CONTEXT.md D-27]  
**Why it happens:** Compatibility fields named `action_result` can be mistaken for an external result. [VERIFIED: src/actions/service.py]  
**How to avoid:** Keep `draft_outcome.v1(status="not_executed_demo", external_side_effect=false)` and final-response wording tied to draft/pending/rejected/needs-info states. [VERIFIED: src/actions/schemas.py; VERIFIED: src/agent/nodes/final_response.py]  
**Warning signs:** Tests accept `status="success"` or final strings like "issued" / "completed" for action-bearing paths. [VERIFIED: tests/architecture/test_action_draft_boundaries.py]

## Code Examples

### Exact Trusted Approval Result Validation

```python
if (
    trusted.action_payload_hash != state.get("action_payload_hash")
    or trusted.safety_snapshot_ref != state.get("safety_snapshot_ref")
    or trusted.safety_snapshot_hash != state.get("safety_snapshot_hash")
):
    return None
```
[VERIFIED: src/agent/graph.py]

### Demo-Only Draft Outcome Contract

```python
class DraftOutcomeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["draft_outcome.v1"] = "draft_outcome.v1"
    status: Literal["not_executed_demo"] = "not_executed_demo"
    external_side_effect: Literal[False] = False
```
[VERIFIED: src/actions/schemas.py]

### Action Draft Idempotency Shape

```python
idempotency_key = _build_idempotency_key(
    tenant_id=tenant_uuid,
    run_id=run_uuid,
    revision_marker=binding.revision_marker,
    action_type=action_type,
    target_id=target_id,
    action_payload_hash=action_payload_hash,
)
```
[VERIFIED: src/actions/service.py]

### Manager Scope Source of Truth

```python
if role in MERCHANT_BOUND_ROLES:
    merchant_id = getattr(user, "merchant_id", None)
    return MerchantScopeV1(merchant_ids=[str(merchant_id)] if merchant_id is not None else [])

if role in PLATFORM_ADMIN_ROLES:
    return MerchantScopeV1(merchant_ids=["*"])
```
[VERIFIED: src/platform/trusted_context.py]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manager approval list/get/decide allowed during earlier approval work | Phase 29.5 made approval review admin-only until Phase 34 target merchant/BusinessFactRef binding exists | Phase 29.5, documented in roadmap/spec/deferred todo | Phase 34 must restore manager access only after target binding is explicit and scope-checked. [VERIFIED: .planning/ROADMAP.md; CITED: docs/contract-spec.md Section 8.0.1; VERIFIED: .planning/todos/deferred/2026-06-27-merchant-scope-approval-action.md; VERIFIED: src/api/routers/approvals.py] |
| `assess_risk_and_approval` as combined legacy node | Target vocabulary names canonical `risk_gate` and keeps legacy name only as semantic compatibility | Phase 32 target graph migration and Phase 34 context | Plans should label/extract `risk_gate` semantics without forcing a risky all-at-once rename. [CITED: docs/target-agent-platform-architecture-plan.md Section 4/13; VERIFIED: 34-CONTEXT.md D-08] |
| Action draft contained payload/hash/snapshot but not all authority refs | Phase 34 target requires business fact, evidence, claim, risk, target merchant, approval/revision, idempotency binding | Phase 34 roadmap and requirements | Contract and persistence plan must precede manager-scope and action-draft widening. [VERIFIED: .planning/REQUIREMENTS.md APF-15; VERIFIED: .planning/ROADMAP.md; VERIFIED: src/actions/schemas.py] |
| Execution wording and compatibility `action_result` could look action-like | Demo mode contract says draft created, not executed, no external side effect | Phase 14/16 contract baseline and Phase 34 no-real-execution decision | Tests must reject real-execution records/adapters/final wording. [CITED: docs/contract-spec.md Section 16.1-16.4; VERIFIED: tests/architecture/test_action_draft_boundaries.py] |

**Deprecated/outdated:**
- `APPROVAL_ROLES={"admin","manager"}` is outdated for the current codebase because the current router and policy expose only admin approval review until Phase 34 safely restores manager scope. [VERIFIED: src/api/routers/approvals.py; VERIFIED: src/approvals/policy.py; VERIFIED: .planning/ROADMAP.md]
- Any `server_merchant_scope={"merchant_ids":["*"]}` resume for a non-admin human is forbidden; future wildcard system jobs need a distinct trusted system context. [VERIFIED: 34-CONTEXT.md D-15; CITED: docs/contract-spec.md Section 8.0.1]
- Treating `execute_action` as a new canonical path is out of date; new graph/action paths should target `action_draft` and `draft_outcome.v1`. [VERIFIED: 34-CONTEXT.md D-26; VERIFIED: tests/architecture/test_action_draft_boundaries.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

All claims in this research were verified or cited during this session; no assumed claims are intentionally present. [VERIFIED: source review in this session]

## Open Questions (Resolved for Planning)

1. **Resolved: persisted approval/draft rows use safe claim verification summary/ref fields.** `ClaimVerificationBundleV1` exists and carries safe support refs, claim results, blocked claims, route, and verifier policy version, but the inspected schema does not expose one stable persisted bundle id/ref. Phase 34 therefore stores a safe JSON summary/ref set unless implementation introduces a stable bundle ref with tests. [VERIFIED: src/knowledge/schemas.py; VERIFIED: 34-CONTEXT.md D-02; VERIFIED: 34-01-PLAN.md; VERIFIED: 34-03-PLAN.md; VERIFIED: 34-05-PLAN.md]
2. **Resolved: Phase 34 defines the durable auto-allowed binding contract while keeping runtime fail-closed by default.** `risk_gate` owns auto-draft routing semantics and the current ActionService safely rejects missing approval as `AUTO_ALLOWED_BINDING_REQUIRED`; Phase 34 may only allow auto-draft when an exact durable binding is produced and validated. [VERIFIED: 34-CONTEXT.md D-16-D-19; VERIFIED: src/actions/service.py; VERIFIED: 34-02-PLAN.md; VERIFIED: 34-05-PLAN.md]
3. **Resolved: target merchant derivation is service-owned and fail-closed.** Target merchant must come from scoped `BusinessFactRefV1` / `BusinessFactResultV1` authority or a service-approved field derived from those refs; Phase 34 implements small service-owned derivation/validation that fails closed on missing, ambiguous, multi-merchant, or outside-scope targets. [VERIFIED: 34-CONTEXT.md D-11-D-13; VERIFIED: src/tools/contracts.py; VERIFIED: 34-01-PLAN.md; VERIFIED: 34-03-PLAN.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Required validation entrypoint | yes | 0.11.2 | `.venv/bin/pytest ...` if repo venv exists and is verified. [VERIFIED: uv --version; VERIFIED: AGENTS.md] |
| Python | Runtime/tests | yes | 3.13.3 local; project requires >=3.12 | Use `uv run` to avoid PATH pollution. [VERIFIED: python3 --version; VERIFIED: pyproject.toml; VERIFIED: AGENTS.md] |
| Docker | Postgres-backed local services/tests | yes | 29.4.2 client and daemon | If Docker is unavailable later, run only unit/static tests or use an already running Postgres. [VERIFIED: docker --version; VERIFIED: docker info] |
| PostgreSQL CLI (`psql`, `pg_isready`) | Direct DB health probes | no | - | Let `uv run pytest` fixtures/asyncpg prove DB reachability, or use Docker compose. [VERIFIED: command -v psql; VERIFIED: command -v pg_isready; VERIFIED: tests/conftest.py] |
| Test Postgres DSN | DB integration tests | Not directly probed | `postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test` in fixtures | Start the compose Postgres if integration tests cannot connect. [VERIFIED: tests/conftest.py; VERIFIED: docker-compose.yml] |

**Missing dependencies with no fallback:** None for research/planning. [VERIFIED: environment probes]

**Missing dependencies with fallback:** PostgreSQL CLI tools are absent, but pytest fixtures and Docker compose are the available fallback path. [VERIFIED: command -v psql; VERIFIED: command -v pg_isready; VERIFIED: tests/conftest.py; VERIFIED: docker-compose.yml]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0. [VERIFIED: uv.lock] |
| Config file | `pyproject.toml` has pytest configuration. [VERIFIED: pyproject.toml] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/test_approval_gate.py tests/test_execute_action.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` [VERIFIED: AGENTS.md; VERIFIED: rg --files] |
| Full focused suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` [VERIFIED: AGENTS.md; VERIFIED: rg --files] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| APF-15 | ApprovalRequest and ActionDraft persist target merchant, business fact refs, verified evidence refs, claim verification refs/summary, risk decision, payload hash, safety snapshot ref/hash, approval/revision refs, and idempotency key. [VERIFIED: .planning/REQUIREMENTS.md; VERIFIED: 34-CONTEXT.md D-02] | contract/migration/service | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_migration_contract.py tests/actions/test_action_draft_v2.py -q --tb=short` | yes, but new Phase 34 cases needed. [VERIFIED: rg --files] |
| APF-15 | Payload/ref/snapshot/business/claim/risk changes invalidate old approval and cannot create a draft. [VERIFIED: 34-CONTEXT.md D-20/D-23] | service/router | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_hash_binding.py tests/test_execute_action.py -q --tb=short` | yes, but new business/claim/risk mismatch cases needed. [VERIFIED: rg --files] |
| APF-15 | Manager A cannot list/get/decide merchant B approval; missing target merchant fails closed. [VERIFIED: 34-CONTEXT.md D-13] | API/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/platform/test_merchant_scope.py -q --tb=short` | yes, but manager restoration cases need replacing current 403-only interim tests. [VERIFIED: tests/test_approval_api.py; VERIFIED: tests/platform/test_merchant_scope.py] |
| APF-16 | `risk_gate` owns blocked/approval-required/auto-draft routing; `approval_gate` does not re-decide risk policy. [VERIFIED: .planning/REQUIREMENTS.md; VERIFIED: 34-CONTEXT.md D-06-D-10] | router/node/architecture | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_approval_boundaries.py -q --tb=short` | yes, but risk_gate vocabulary/auto-binding cases needed. [VERIFIED: rg --files] |
| APF-16 | Ordinary chat cannot forge approval/action authority; approval result must come from trusted service/API path. [VERIFIED: 34-CONTEXT.md D-31; CITED: docs/eval-test-plan.md] | graph/eval contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/test_approval_api.py tests/test_approval_gate.py -q --tb=short` | yes. [VERIFIED: rg --files] |
| APF-16 | No full real external execution is introduced. [VERIFIED: 34-CONTEXT.md D-25-D-27] | architecture/static/final response | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_action_draft_boundaries.py tests/actions/test_action_draft_v2.py -q --tb=short` | yes. [VERIFIED: rg --files] |

### Sampling Rate

- **Per task commit:** Run the quick command above plus the directly touched file's focused test. [VERIFIED: AGENTS.md; VERIFIED: rg --files]
- **Per wave merge:** Run the full focused suite above. [VERIFIED: AGENTS.md; VERIFIED: .planning/config.json]
- **Phase gate:** Full focused suite green and no bare `pytest` result accepted. [VERIFIED: AGENTS.md; VERIFIED: 34-CONTEXT.md D-30]

### Wave 0 Gaps

- [ ] `tests/approvals/test_phase34_boundary_bindings.py` - should cover APF-15 approval binding fields, target merchant fail-closed legacy rows, and payload/business/evidence/claim/risk mismatch invalidation. [VERIFIED: 34-CONTEXT.md D-02/D-13/D-20]
- [ ] `tests/actions/test_phase34_action_draft_bindings.py` - should cover APF-15 draft binding fields, durable auto-allowed binding if enabled, and exact target merchant/snapshot/hash validation. [VERIFIED: 34-CONTEXT.md D-16-D-24]
- [ ] `tests/architecture/test_phase34_approval_action_boundaries.py` - should statically enforce no new external execution/outbox/action execution records and no wildcard `server_merchant_scope` outside admin/system-only contracts. [VERIFIED: 34-CONTEXT.md D-15/D-25; VERIFIED: tests/tools/test_merchant_scope_static.py]
- [ ] Update `tests/test_approval_api.py` - replace interim manager-403-only tests with same-merchant allow/cross-merchant deny/missing-target deny tests after Plan 34-03. [VERIFIED: tests/test_approval_api.py; VERIFIED: 34-CONTEXT.md D-13]
- [ ] Update `tests/test_graph_routing.py` - add `risk_gate` vocabulary/alias and durable auto-allowed route tests if Plan 34-02 enables auto-draft. [VERIFIED: src/agent/graph.py; VERIFIED: 34-CONTEXT.md D-09/D-16]

## Security Domain

### Applicable ASVS Categories

OWASP ASVS is a web application security verification standard and the official project page lists latest stable version 5.0.0 as of the source checked. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Approval commands must originate from authenticated API actors and trusted service-generated resume payloads, not ordinary chat text. [VERIFIED: src/api/routers/approvals.py; VERIFIED: src/agent/graph.py; CITED: docs/eval-test-plan.md] |
| V3 Session Management | yes | Interrupted approval resumes must bind tenant/run/thread state and preserve interrupted lifecycle semantics. [VERIFIED: src/api/routers/approvals.py; VERIFIED: src/approvals/service.py; CITED: docs/contract-spec.md Section 15.4] |
| V4 Access Control | yes | Manager approval access requires target merchant binding inside `TrustedContextFactory` merchant scope; admin remains platform-wide. [VERIFIED: 34-CONTEXT.md D-11-D-15; VERIFIED: src/platform/trusted_context.py] |
| V5 Input Validation | yes | Pydantic `extra="forbid"`, canonical hashes, expected versions, and strict refs validate command input and prevent raw-payload authority. [VERIFIED: src/approvals/schemas.py; VERIFIED: src/actions/schemas.py; VERIFIED: src/approvals/snapshot_service.py] |
| V6 Cryptography | yes, for integrity hashes rather than encryption | Use existing canonical SHA-256-style hash helpers; do not add bespoke hashing. [VERIFIED: src/common/canonical_hash.py; VERIFIED: src/approvals/snapshot_service.py] |

### Known Threat Patterns for Phase 34

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Ordinary chat spoofing approval or action authority | Spoofing / Elevation of Privilege | Only ApprovalService/API-created `approval_result.v1` is trusted, and graph validation rejects untrusted/mismatched approval_result state. [VERIFIED: src/agent/graph.py; VERIFIED: tests/agent/test_graph.py; CITED: docs/eval-test-plan.md] |
| Payload or evidence tampering after approval | Tampering | Compare exact action payload hash and safety snapshot hash/ref before draft creation; changed material creates a new approval revision. [VERIFIED: src/actions/service.py; VERIFIED: src/approvals/service.py; VERIFIED: 34-CONTEXT.md D-20] |
| Manager cross-merchant approval access | Elevation of Privilege / Information Disclosure | Store explicit target merchant/business fact binding and filter list/get/decide by trusted merchant scope; missing/ambiguous/multi/outside scope fails closed. [VERIFIED: 34-CONTEXT.md D-11-D-13] |
| Unsupported action claim reaches approval/action | Tampering / Elevation of Privilege | Claim verification bundle gates action path and blocks unsupported action recommendations before risk/approval/action. [VERIFIED: src/agent/graph.py; VERIFIED: src/knowledge/schemas.py; VERIFIED: tests/architecture/test_phase33_rag_claim_boundaries.py] |
| Real execution creep through compatibility paths | Tampering / Repudiation | Keep action tool node-only, draft outcome demo-only, no external adapters/outbox/execution rows, and final response not-executed wording. [VERIFIED: src/tools/catalog.py; VERIFIED: src/actions/schemas.py; VERIFIED: tests/architecture/test_action_draft_boundaries.py; VERIFIED: 34-CONTEXT.md D-25-D-27] |
| Prompt/API leakage of raw action material | Information Disclosure | Working-state/prompt projections should expose safe summaries and refs, not raw approval bodies, snapshot JSON, or action payloads. [VERIFIED: src/agent/working_state.py; VERIFIED: 34-CONTEXT.md D-05] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/34-approval-and-actiondraft-boundary-hardening/34-CONTEXT.md` - locked decisions, discretion areas, deferred scope, code/test anchors. [VERIFIED]
- `.planning/REQUIREMENTS.md` - APF-15 and APF-16 requirement text. [VERIFIED]
- `.planning/ROADMAP.md` - Phase 34 goal, dependency on Phase 33, and success criteria. [VERIFIED]
- `.planning/STATE.md` - current project focus and phase history. [VERIFIED]
- `AGENTS.md` and `CLAUDE.md` - MOCA testing, validation, review, and planning constraints. [VERIFIED]
- `docs/target-agent-platform-architecture-plan.md` - approval/action target architecture and Phase 34 notes. [CITED]
- `docs/contract-spec.md` - normative TrustedContext, graph route, approval/action/snapshot/demo-mode contracts. [CITED]
- `docs/eval-test-plan.md` - approval/action negative cases and eval expectations. [CITED]
- `src/approvals/*`, `src/actions/*`, `src/agent/*`, `src/api/routers/approvals.py`, `src/platform/trusted_context.py`, `src/db/models.py`, `src/tools/*`, `src/knowledge/schemas.py`, `src/tools/contracts.py` - current implementation anchors. [VERIFIED]
- `tests/test_approval_api.py`, `tests/test_approval_gate.py`, `tests/test_execute_action.py`, `tests/test_graph_routing.py`, `tests/actions/test_action_draft_v2.py`, `tests/approvals/*`, `tests/architecture/*`, `tests/platform/test_merchant_scope.py`, `tests/tools/test_merchant_scope_static.py` - existing validation anchors. [VERIFIED]
- `pyproject.toml`, `uv.lock`, local command probes - stack and environment versions. [VERIFIED]
- OWASP ASVS official project page and GitHub repository - security verification standard context. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://github.com/OWASP/ASVS]

### Secondary (MEDIUM confidence)

- None used as authoritative sources; web search results were limited to official OWASP sources for ASVS context. [VERIFIED: web search]

### Tertiary (LOW confidence)

- None. [VERIFIED: source review in this session]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions are from `uv.lock`, requirements from `pyproject.toml`, and tools from local probes. [VERIFIED: uv.lock; VERIFIED: pyproject.toml; VERIFIED: uv --version; VERIFIED: docker --version]
- Architecture: HIGH - target responsibilities match locked Phase 34 context, roadmap, contract spec, and current code anchors. [VERIFIED: 34-CONTEXT.md; VERIFIED: .planning/ROADMAP.md; CITED: docs/contract-spec.md; VERIFIED: src/agent/graph.py]
- Pitfalls: HIGH - pitfalls are derived from locked decisions, current interim guards, existing tests, and contract-spec constraints. [VERIFIED: 34-CONTEXT.md; VERIFIED: tests/test_approval_api.py; VERIFIED: tests/architecture/test_action_draft_boundaries.py; CITED: docs/contract-spec.md]

**Research date:** 2026-06-29  
**Valid until:** 2026-07-29 for codebase-local architecture and 2026-07-06 for package/security version freshness. [VERIFIED: current session date; VERIFIED: uv.lock; CITED: https://owasp.org/www-project-application-security-verification-standard/]
