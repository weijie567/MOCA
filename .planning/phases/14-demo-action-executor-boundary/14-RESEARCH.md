# Phase 14: Demo Action Executor Boundary - Research

**Researched:** 2026-06-16 [VERIFIED: environment_context]
**Domain:** Backend action-draft boundary, SQLAlchemy/Alembic persistence, LangGraph node routing, FastAPI approval resume, trace events [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]
**Confidence:** HIGH [VERIFIED: local code/docs/runtime inspection]

<user_constraints>
## User Constraints (from CONTEXT.md) [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

### Locked Decisions
## Implementation Decisions

### Draft Schema and Migration
- **D-01:** Implement the full target `action_draft.v2` schema for new Phase 14 drafts. This includes self-describing draft fields such as `schema_version`, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`, `draft_outcome`, version/lifecycle/retention fields, and existing approval linkage where applicable.
- **D-02:** Treat Phase 14 schema work as draft-row persistence and replay readiness, not a reimplementation of Phase 13 validation. Current `ActionService` already requires binding fields and validates them against `ActionSafetySnapshot`; Phase 14 persists those validated fields on the draft row.
- **D-03:** Persist `draft_outcome.v1` on `action_drafts`. Demo outcome must carry `status=not_executed_demo` and `external_side_effect=false`.
- **D-04:** Do not backfill legacy draft rows into complete `action_draft.v2`. New columns may be nullable for old rows; contract tests should assert v2 completeness only for drafts created after Phase 14. Old pre-v2 rows are not an authorization surface.
- **D-05:** Do not create `action_executions`, outbox, reconciliation, or compensation tables in Phase 14. Add negative tests proving demo mode writes no execution rows or external-only records.

### Compatibility Output and Wording
- **D-06:** Prefer `draft_outcome.v1` as the graph/API success signal for draft creation. Any retained `action_result` field is deprecated compatibility output only and must not use `status=success` to imply external execution.
- **D-07:** Migrate existing success sentinels together. `src/api/routers/approvals.py` and `src/agent/nodes/final_response.py` currently depend on `action_result.status == "success"`; Phase 14 must change those checks to `draft_outcome` created/not-executed semantics so valid drafts are not misclassified as failures.
- **D-08:** Final backend/API responses must say a draft was created and no coupon/refund/ticket action was executed. Do not use wording such as waiting for final issuance, issued coupon, refunded, closed ticket, executed, or external success.
- **D-09:** Keep frontend/timeline copy changes out of Phase 14 except where required by backend contract tests. Record `frontend/src/components/timeline/TimelineStep.tsx` wording for `execute_action` as a known UI/replay wording difference deferred to Phase 15.
- **D-10:** Add strict forbidden-phrase tests for backend/final/API output to prevent external-success claims in demo mode.

### Idempotency and Conflict Behavior
- **D-11:** The server/service boundary constructs the draft idempotency key from trusted fields only. Do not let callers or the graph node supply arbitrary key shape.
- **D-12:** Target key shape: `{tenant_id}:{run_id}:{approval_revision_or_auto}:{action_type}:{target_id}:{action_payload_hash}`.
- **D-13:** Missing `target_id` must fail validation instead of falling back to `"unknown"`, because unknown-target keys can collide across distinct actions.
- **D-14:** Same target/action with a different `action_payload_hash` represents a distinct draft intent or revision and should create a distinct draft key.
- **D-15:** Exact key reuse returns the existing draft only when binding remains exact. Because the key embeds tenant, run, revision/auto marker, action type, target id, and payload hash, the additional required reuse check is `safety_snapshot_hash` consistency. A key hit with mismatched snapshot hash must return an idempotency conflict.
- **D-16:** Use explicit `auto_allowed` as the no-approval revision marker for low-risk auto-allowed drafts. Do not collapse auto-allowed drafts into the current `no_approval` marker.
- **D-17:** Keep the global unique `idempotency_key` constraint if the key embeds tenant id. With this key shape, global uniqueness is equivalent to tenant-isolated key uniqueness. The existing tenant comparison may remain as defense-in-depth but is no longer the primary isolation mechanism.

### Graph and Naming Boundary
- **D-18:** Rename the registered graph node from `execute_action` to `action_draft` in Phase 14. Update graph registration, conditional edges, imports, trace/node-name contracts, and route naming to align with the canonical node.
- **D-19:** Before renaming, check whether LangGraph checkpoints or replay/timeline compatibility store node names. If old names are persisted, document legacy run behavior and add compatibility handling only as a named shim.
- **D-20:** Keep the tool name `create_coupon_grant_draft`; it is already draft-explicit and node-only. Do not introduce a generic `create_action_draft` abstraction until additional action types justify it.
- **D-21:** Hard-quarantine backend "execute" language for demo draft semantics. New backend call sites, output fields, and docs should use draft/action_draft wording except for named compatibility shims.
- **D-22:** Any retained `execute_action` alias must have a named owner, forbidden new references, boundary tests, and a dated removal phase/gate.
- **D-23:** Do not rename `requested_operation="execute_action"` in Phase 14. Intent taxonomy is a Phase 11 contract. The user's requested operation may remain "execute action" while the graph maps that intent to safe draft creation after risk and approval guards.

### Trace and Replay Event Surface
- **D-24:** Emit `action_draft_created` in Phase 14 through the existing Phase 10 minimal `AgentTraceEvent` envelope after successful draft creation.
- **D-25:** The event must use safe refs only. Suggested shape: `resource_refs={draft_id, target_id, action_payload_hash, safety_snapshot_hash}` and `redacted_payload={action_type, execution_mode:"demo", external_side_effect:false}`. Do not include raw action payload, raw tool args, or full `ActionDraft.payload`.
- **D-26:** Update backend `/trace` action draft output to include `draft_outcome` from `action_drafts`. Do not add a new replay API, ReplayEventV3 read switch, retention model, or event-store-first trace read in Phase 14.
- **D-27:** Add negative tests across persistence, events, and wording: no `action_executions` rows or writes, no `action_execution_*` events, no external refs, and no external success wording.

### the agent's Discretion
- Exact column names may follow `docs/contract-spec.md` target names and existing SQLAlchemy conventions.
- Exact compatibility shim shape is planner discretion, but only if it satisfies D-19 and D-22.
- Exact test file split may follow current tests under `tests/test_execute_action.py`, `tests/agent/test_tools/`, `tests/test_trace_api.py`, and approval integration tests.

### Deferred Ideas (OUT OF SCOPE)
- Frontend timeline label cleanup for `execute_action` is deferred to Phase 15/replay UI work unless planning finds it blocks backend contract tests.
- Full ReplayEventV3 enrichment, lifecycle finalizer, event-store-first `/trace` or `/replay` reads, retention, and richer replay API are Phase 15.
- External action execution, `action_executions`, outbox, reconciliation, compensation, external idempotency keys, and real side effects are Phase 17.
- Generic `create_action_draft` naming can be reconsidered when more action types are implemented.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEMO-01 | Demo mode creates durable draft and `draft_outcome` only, with no execution row or external side effect. [VERIFIED: .planning/REQUIREMENTS.md] | Use `action_drafts` v2 expansion, `draft_outcome.v1`, `action_draft_created`, and negative persistence/event tests; do not introduce Phase 17 tables. [VERIFIED: docs/contract-spec.md Sections 16.1-16.4, 17.2, 18.3] |
| DEMO-02 | Demo wording and hash/revision guards cannot claim or authorize real execution. [VERIFIED: .planning/REQUIREMENTS.md] | Replace `action_result.status == "success"` sentinels with `draft_outcome` semantics, keep Phase 13 snapshot validation, and add forbidden wording/hash mismatch tests. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; src/actions/service.py; src/agent/nodes/final_response.py] |
</phase_requirements>

## Summary

Phase 14 is a backend boundary-hardening phase, not a library-selection phase. The correct plan is to turn the current `execute_action` draft path into an explicit `action_draft` domain path that persists the full new-draft `action_draft.v2` fields plus `draft_outcome.v1`, emits `action_draft_created`, and makes final/API wording say "draft created, not executed." [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; docs/phase-13-17-architecture-plan.md]

The important existing asset is `ActionService._validate_action_binding`, which already checks `tenant_id`, `run_id`, `action_payload_hash`, `safety_snapshot_ref`, and `safety_snapshot_hash` against `ActionSafetySnapshot`, and checks approved `ApprovalRequest` rows when an approval id is present. [VERIFIED: src/actions/service.py] The important current gaps are persistence and output shape: `ActionDraft` stores only run/tenant/approval/idempotency/action_type/status/payload, `execute_action.py` builds the old key with an `"unknown"` target fallback, graph routes still return `"execute_action"`, and final/API paths still interpret `action_result.status == "success"` as the draft success sentinel. [VERIFIED: src/db/models.py; src/agent/nodes/execute_action.py; src/agent/graph.py; src/api/routers/approvals.py; src/agent/nodes/final_response.py]

**Primary recommendation:** Implement a package-owned action draft service boundary that constructs the trusted idempotency key, persists v2 draft fields and `draft_outcome`, emits `action_draft_created`, returns `draft_outcome` to graph/API/final response, and quarantines any `execute_action` alias with tests and a removal gate. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; docs/contract-spec.md Sections 16.1-16.4]

## Project Constraints (from CLAUDE.md)

- `docs/contract-spec.md` is the normative source for MOCA contract semantics, but phase scope controls implementation detail; a target contract is not automatically implemented fact. [VERIFIED: CLAUDE.md]
- Any phase implementation/spec mismatch must be recorded; either fix the spec or explicitly mark MVP scope/deferred ownership in `.planning/`. [VERIFIED: CLAUDE.md]
- Deferred work must name the owner phase, not vague future work. [VERIFIED: CLAUDE.md]
- Phase-level plans and larger changes use the Claude/Codex cross-review workflow; Codex is the implementation/review workhorse, and GSD tools are the first review layer. [VERIFIED: CLAUDE.md]
- `study_plan/` documents default to Chinese, but source identifiers, API names, file paths, commands, classes, functions, and tests may stay English. [VERIFIED: CLAUDE.md]
- No `AGENTS.md` file exists in the repository root, and no project skill `SKILL.md` files exist under `.claude/skills` or `.agents/skills`. [VERIFIED: find commands; .claude listing]
- The `rules/` directory has no Markdown rule files to load for this phase. [VERIFIED: find rules]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Approval/snapshot binding validation | API / Backend | Database / Storage | `ActionService` validates Phase 13 `ActionSafetySnapshot` and approved `ApprovalRequest`; Phase 14 must consume, not reproduce, snapshot production. [VERIFIED: src/actions/service.py; docs/contract-spec.md Section 15.3] |
| Durable demo draft persistence | API / Backend | Database / Storage | The action domain owns draft creation; SQLAlchemy/Alembic own durable `action_drafts` schema expansion. [VERIFIED: src/actions/service.py; src/repositories/action_draft_repo.py; src/db/models.py] |
| Draft idempotency key construction | API / Backend | Database / Storage | Trusted service/server code must construct the key; the DB unique constraint enforces global uniqueness. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; src/db/models.py] |
| Graph node rename and routing | API / Backend | LangGraph checkpoint storage | `src/agent/graph.py` currently registers/routes `execute_action`; live checkpoints also store `branch:to:execute_action`. [VERIFIED: src/agent/graph.py; docker PostgreSQL checkpoint queries] |
| Demo final/API wording | API / Backend | Browser / Client | Phase 14 backend/final/API wording must avoid execution claims; frontend timeline wording is deferred unless backend contract tests require it. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; frontend/src/components/timeline/TimelineStep.tsx] |
| Trace event emission | API / Backend | Database / Storage | `AgentTraceEvent` and `emit_event` provide the minimal envelope/allocator; Phase 14 only registers/emits `action_draft_created`. [VERIFIED: src/agent/events.py; src/db/models.py; docs/contract-spec.md Section 17.2] |
| External action execution/outbox/reconciliation | API / Backend | External Services | Explicitly Phase 17; Phase 14 must add only negative guards proving no execution/outbox side effect. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; docs/phase-13-17-architecture-plan.md] |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.3 runtime; project requires `>=3.12` | Backend runtime and tests | The project is Python/FastAPI and already declares `requires-python >=3.12`. [VERIFIED: `python3 --version`; pyproject.toml] |
| FastAPI | 0.136.1 | Approval/trace/agent HTTP boundaries | Existing routers and test client are FastAPI-based. [VERIFIED: importlib.metadata; src/api/routers/approvals.py; src/api/routers/traces.py] |
| SQLAlchemy | 2.0.49 | Async ORM models/repositories | Existing `ActionDraft`, `ActionSafetySnapshot`, and repositories use SQLAlchemy async sessions. [VERIFIED: importlib.metadata; src/db/models.py; src/repositories/action_draft_repo.py] |
| Alembic | 1.18.4 | Schema migrations | Existing migrations are Alembic revision files; Phase 14 needs migration `009` after `008_approval_state_machine`. [VERIFIED: importlib.metadata; src/db/migrations/versions] |
| PostgreSQL + pgvector image | PostgreSQL 16.13 via `pgvector/pgvector:pg16` | Durable test/dev storage and LangGraph checkpoints | Docker Compose runs PostgreSQL and tests use a PostgreSQL test DB fixture. [VERIFIED: docker compose; tests/conftest.py] |
| LangGraph | 1.1.10 | Graph orchestration and checkpoints | `src/agent/graph.py` builds the StateGraph and uses checkpoint tables in PostgreSQL. [VERIFIED: importlib.metadata; src/agent/graph.py; docker PostgreSQL table query] |
| langgraph-checkpoint-postgres | 3.0.5 | PostgreSQL checkpoint persistence | The graph imports `AsyncPostgresSaver`; live DB has checkpoint tables. [VERIFIED: importlib.metadata; src/agent/graph.py; docker PostgreSQL table query] |
| Pydantic | 2.13.4 | API/contract schema validation | Approval request/response schemas and snapshot schemas use Pydantic models. [VERIFIED: importlib.metadata; src/api/schemas/approvals.py; src/approvals/snapshots.py] |

### Supporting

| Library/Tool | Version | Purpose | When to Use |
|--------------|---------|---------|-------------|
| pytest | 9.0.3 | Unit/integration validation | Required for Phase 14 quick, focused, and full gates. [VERIFIED: `uv run pytest --version`] |
| pytest-asyncio | 1.3.0 | Async tests | Existing DB/API/service tests are async. [VERIFIED: importlib.metadata; tests/conftest.py] |
| httpx | 0.28.1 | ASGI API tests | Existing `AsyncClient` API tests use `httpx`. [VERIFIED: importlib.metadata; tests/conftest.py] |
| Ruff | 0.15.12 | Lint/format | Existing Makefile lint target runs `uv run ruff check src/ tests/`. [VERIFIED: `uv run ruff --version`; Makefile] |
| Docker Compose | available; services healthy | Local PostgreSQL/Redis services | Required for DB-backed tests unless an equivalent local PostgreSQL is available. [VERIFIED: docker compose ps] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing SQLAlchemy/Alembic stack | Raw SQL migration only | Raw SQL can express constraints, but the project already mirrors schema in SQLAlchemy models and Alembic files; planning should update both. [VERIFIED: src/db/models.py; src/db/migrations/versions] |
| Existing `emit_event` helper | New ReplayService | ReplayService is Phase 15; Phase 14 must only register and emit the minimal `action_draft_created` event. [VERIFIED: docs/contract-spec.md Section 17.2; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |
| Existing `create_coupon_grant_draft` tool | New generic `create_action_draft` | The user locked the coupon draft tool name for Phase 14 and deferred generic naming until more action types exist. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |

**Installation:** No new package is required for Phase 14; use the existing uv-managed environment. [VERIFIED: pyproject.toml; importlib.metadata]

```bash
uv sync --extra dev
```

**Version verification:** Versions above were verified with `uv run python -c "import importlib.metadata as m; ..."` and direct CLI version checks on 2026-06-16. [VERIFIED: tool output]

## Architecture Patterns

### System Architecture Diagram

```mermaid
flowchart TD
    U[User action request] --> I[Intent / slots / investigate / recommendation]
    I --> R[Risk and snapshot producer]
    R -->|auto_allowed with snapshot refs| D[action_draft node]
    R -->|approval required| A[ApprovalService + approval_gate]
    A -->|trusted approval_result.v1 with exact hashes| D
    A -->|reject / ignore / needs_info / edit| F[final_response or revalidation]
    D --> S[ActionDraftService]
    S --> V[Validate Phase 13 ActionSafetySnapshot + approval binding]
    V -->|mismatch| F
    V -->|match| K[Construct trusted idempotency key]
    K --> P[(action_drafts action_draft.v2 + draft_outcome.v1)]
    P --> E[(agent_trace_events action_draft_created)]
    E --> T[/trace action_drafts with draft_outcome]
    E --> F
    D -. external mode deferred .-> X[action_execution / outbox Phase 17]
```

This data flow uses the Phase 13 snapshot producer and keeps Phase 17 external execution outside Phase 14. [VERIFIED: docs/phase-13-17-architecture-plan.md; docs/contract-spec.md Sections 15.3, 16.2, 17.2]

### Recommended Project Structure

```text
src/
├── actions/
│   ├── schemas.py          # action_draft.v2 / draft_outcome.v1 typed contracts
│   ├── service.py          # trusted ActionDraftService boundary and binding reuse
│   └── drafts.py           # persistence adapter over ActionDraftRepository
├── repositories/
│   └── action_draft_repo.py # create/get with exact binding conflict checks
├── agent/
│   ├── nodes/action_draft.py # canonical LangGraph node replacing execute_action
│   ├── graph.py             # routes to action_draft, not execute_action
│   └── events.py            # register action_draft_created
└── db/migrations/versions/
    └── 009_action_draft_v2.py # nullable expand for old rows, v2 completeness for new rows
```

This structure follows the current repo boundaries and the locked decision not to invent a generic action-draft tool abstraction. [VERIFIED: src/actions/service.py; src/repositories/action_draft_repo.py; src/agent/graph.py; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

### Component Responsibilities

| Component | Keep / Add | Responsibility |
|-----------|------------|----------------|
| `src/actions/service.py` | Keep and expand | Own trusted key construction, target id validation, binding validation, draft/draft_outcome result shape, and event call orchestration. [VERIFIED: src/actions/service.py] |
| `src/repositories/action_draft_repo.py` | Expand | Persist v2 fields and return exact-binding idempotent reuse or conflict. [VERIFIED: src/repositories/action_draft_repo.py] |
| `src/db/models.py::ActionDraft` | Expand | Add nullable-for-legacy v2 columns, `draft_outcome` JSON, version/lifecycle/retention fields, and redundant binding columns. [VERIFIED: src/db/models.py; docs/contract-spec.md Section 18.3] |
| `src/agent/nodes/action_draft.py` | Add/rename | Canonical graph node; returns `action_draft`, `draft_outcome`, and optional draft-only compatibility output. [VERIFIED: src/agent/nodes/execute_action.py; docs/contract-spec.md Section 10.1] |
| `src/agent/graph.py` | Update | Rename route returns and node registration from `execute_action` to `action_draft`. [VERIFIED: src/agent/graph.py] |
| `src/api/routers/approvals.py` | Update | Reconciliation should key on `draft_outcome.status == not_executed_demo`, not `action_result.status == success`. [VERIFIED: src/api/routers/approvals.py] |
| `src/agent/nodes/final_response.py` | Update | Use `draft_outcome` and forbidden wording tests; no final text should imply external execution. [VERIFIED: src/agent/nodes/final_response.py] |
| `src/api/routers/traces.py` / `src/repositories/trace_repo.py` | Update | Include `draft_outcome` in action draft output/timeline without adding a new replay API. [VERIFIED: src/api/routers/traces.py; src/repositories/trace_repo.py] |

### Pattern 1: Service-Owned Idempotency Key

**What:** Construct `{tenant_id}:{run_id}:{approval_revision_or_auto}:{action_type}:{target_id}:{action_payload_hash}` inside the action service after validating required trusted fields. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

**When to use:** Every draft creation path, including auto-allowed and approved routes. [VERIFIED: docs/contract-spec.md Section 16.4]

**Example:**

```python
# Source: docs/contract-spec.md Section 16.4 and Phase 14 CONTEXT D-11..D-16.
def build_draft_idempotency_key(*, tenant_id, run_id, approval_revision, action_type, target_id, action_payload_hash):
    if not target_id:
        raise ValueError("target_id_required")
    revision_marker = f"r{approval_revision}" if approval_revision is not None else "auto_allowed"
    return f"{tenant_id}:{run_id}:{revision_marker}:{action_type}:{target_id}:{action_payload_hash}"
```

### Pattern 2: Draft Outcome as Success Sentinel

**What:** Return and persist `draft_outcome.v1` with `status=not_executed_demo` and `external_side_effect=false`; do not use `action_result.status=success` to mean the demo completed. [VERIFIED: docs/contract-spec.md Section 16.3; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

**When to use:** Graph updates, approval resume reconciliation, final response, trace output, and backend contract tests. [VERIFIED: src/api/routers/approvals.py; src/agent/nodes/final_response.py]

**Example:**

```python
# Source: docs/contract-spec.md Section 16.3.
draft_outcome = {
    "schema_version": "draft_outcome.v1",
    "tenant_id": tenant_id,
    "run_id": run_id,
    "draft_id": str(draft.id),
    "status": "not_executed_demo",
    "external_side_effect": False,
    "created_at": created_at_iso,
}
```

### Pattern 3: Minimal Safe Action Event

**What:** Register `action_draft_created` in `MINIMAL_EVENT_TYPES` and emit it through `emit_event` after a draft is created or idempotently reused with exact binding. [VERIFIED: src/agent/events.py; docs/contract-spec.md Section 17.2]

**When to use:** Successful draft creation in demo mode; never emit `action_execution_*` in Phase 14. [VERIFIED: docs/contract-spec.md Section 17.2]

**Example:**

```python
# Source: src/agent/events.py and Phase 14 CONTEXT D-24/D-25.
await emit_event(
    session,
    run_id=run_id,
    tenant_id=tenant_id,
    thread_id=thread_id,
    event_type="action_draft_created",
    actor={"type": "agent", "id": "moca"},
    resource_refs={
        "draft_id": str(draft.id),
        "target_id": target_id,
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_hash": safety_snapshot_hash,
    },
    redacted_payload={
        "action_type": action_type,
        "execution_mode": "demo",
        "external_side_effect": False,
    },
    trace_id=trace_id,
)
```

### Anti-Patterns to Avoid

- **Graph node returns external-success wording:** Final/API copy must say a draft was created and no coupon/refund/ticket action was executed. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]
- **Caller-supplied idempotency shape:** `execute_action.py` currently constructs the key in the graph node; move this into the trusted service boundary. [VERIFIED: src/agent/nodes/execute_action.py]
- **`target_id` fallback to `"unknown"`:** Current code does this; Phase 14 must reject missing targets. [VERIFIED: src/agent/nodes/execute_action.py; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]
- **Snapshot recomputation inside action draft:** Phase 13 owns `ActionSafetySnapshot`; Phase 14 validates existing refs/hashes only. [VERIFIED: docs/contract-spec.md Section 15.3; src/approvals/snapshot_service.py]
- **Creating Phase 17 tables early:** `action_executions`, outbox, reconciliation, and compensation are out of scope. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Canonical payload hashing | A new JSON serializer/hash helper in `src/actions` | `src/common/canonical_hash.py` and `compute_action_payload_hash` | Phase 13 froze the hash profile and tests; divergent serialization would break approval/draft binding. [VERIFIED: src/common/canonical_hash.py; src/approvals/snapshot_service.py] |
| Snapshot creation | A Phase 14 snapshot/evidence hash generator | Existing Phase 13 `ActionSafetySnapshot` row validation | Phase 14 is a consumer; only ApprovalService/snapshot service rebuilds snapshots on edit/needs_info. [VERIFIED: docs/contract-spec.md Section 15.3; src/actions/service.py] |
| Tool dispatch/permissions | Direct action adapter calls from graph nodes | `UnifiedToolManager -> ActionToolExecutor -> ActionService` | The current node-only write path and tool allowlist are already established. [VERIFIED: src/agent/nodes/execute_action.py; src/tools/catalog.py; src/tools/manager.py] |
| Event sequencing | Manual `sequence` assignment | `emit_event` / `allocate_sequence` | Existing helper locks by run and enforces `unique(run_id, sequence)`. [VERIFIED: src/agent/events.py; src/db/models.py] |
| Replay API | New `/replay` endpoint or event-store-first trace read | Existing `/trace` action draft read extension | Phase 15 owns ReplayEventV3 read switch and richer replay API. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |
| External execution | Execution/outbox/reconciliation/compensation table stubs | Negative tests only | Phase 17 owns real external dispatch and external idempotency. [VERIFIED: docs/phase-13-17-architecture-plan.md] |

**Key insight:** The risky complexity is not drafting a row; it is proving that every visible and durable signal says "draft-only" while the draft remains exactly bound to Phase 13's approved/snapshot revision. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; docs/contract-spec.md Sections 15.3, 16.3]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Live `moca` DB has `checkpoints`, `checkpoint_writes`, and `checkpoint_blobs`; `checkpoints=663`, `checkpoint_writes=3606`, `checkpoint_blobs=1657`. Search found `execute_action` in 12 checkpoint JSON rows, 20 checkpoint write rows, and 8 checkpoint blob rows. [VERIFIED: docker PostgreSQL queries] | Planner must choose and document legacy checkpoint behavior. If resume compatibility is required, add a named `execute_action` shim that forwards to `action_draft` and satisfies D-22; otherwise document old checkpoint runs as non-resumable/clearable local state. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |
| Stored data | Live `moca.action_drafts` currently has 0 rows, and live `agent_trace_events` has 0 rows. [VERIFIED: docker PostgreSQL queries] | No draft data migration is needed for existing live rows, but migration columns should be nullable for legacy rows as required by D-04. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |
| Stored data | `moca_test` currently has no public tables before the test fixture creates schema. [VERIFIED: docker PostgreSQL query; tests/conftest.py] | No manual test DB migration is required before tests; pytest fixture creates/drops metadata. [VERIFIED: tests/conftest.py] |
| Stored data | Existing `agent_steps` rows in live `moca` use older node names such as `load_business_context` and `retrieve_policy_evidence`, and no live `agent_steps` row currently uses `execute_action`. [VERIFIED: docker PostgreSQL query] | No `agent_steps` rename migration is required for current live rows; trace display compatibility should still tolerate legacy node names. [VERIFIED: src/repositories/trace_repo.py] |
| Live service config | Docker Compose runs `postgres` and `redis` services; both are healthy. [VERIFIED: docker compose ps] | Keep using Docker Compose for DB-backed tests; host `psql`, `pg_isready`, and `redis-cli` are missing, so use `docker compose exec` fallback for service probes. [VERIFIED: command probes] |
| OS-registered state | Process inspection found Docker Desktop processes and an unrelated `langgraph dev` process under `/Users/ming/projects/langchain-academy`; no MOCA `uvicorn`, pytest, Alembic, or LangGraph server process was found. [VERIFIED: escalated `ps ax | rg ...`] | No MOCA OS process or service registration needs renaming. [VERIFIED: escalated process inspection] |
| Secrets/env vars | `.env` contains only `DASHSCOPE_API_KEY` by key name; `.env.example` and Compose define DB/Redis/JWT/DashScope/SLA env vars, none named for `execute_action` or `action_draft`. [VERIFIED: `.env` key-name inspection; `.env.example`; docker-compose.yml] | Do not rename env keys for Phase 14. `DASHSCOPE_API_KEY` is only needed for live eval/demo paths, not the automated Phase 14 tests. [VERIFIED: docs/evaluation.md; .env.example] |
| Build artifacts | `moca.egg-info/SOURCES.txt` lists `src/agent/nodes/execute_action.py` and stale removed `src/repositories/approval_repo.py`; multiple `.pyc` files contain old `execute_action`/action strings. [VERIFIED: moca.egg-info/SOURCES.txt; rg over pycache] | Include a cleanup/reinstall step after rename, for example remove stale pycache/egg-info or run a clean `uv` install/test. Do not treat egg-info as source truth. [VERIFIED: moca.egg-info] |

**Canonical runtime question:** After every repo file is updated, old LangGraph checkpoint rows and stale build artifacts can still carry `execute_action`; the source rename alone does not update those runtime/build states. [VERIFIED: docker PostgreSQL queries; moca.egg-info/SOURCES.txt]

## Common Pitfalls

### Pitfall 1: Keeping `action_result.status == "success"` as Truth

**What goes wrong:** Approval reconciliation and final response can misclassify draft creation as external execution success. [VERIFIED: src/api/routers/approvals.py; src/agent/nodes/final_response.py]

**Why it happens:** `execute_action.py` adapts a successful draft write into `{"status": "success"}` and downstream code treats that as the success sentinel. [VERIFIED: src/agent/nodes/execute_action.py]

**How to avoid:** Use `draft_outcome.v1` as the canonical success signal and leave any `action_result` output draft-only, non-success, and compatibility-owned. [VERIFIED: docs/contract-spec.md Section 16.3; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

**Warning signs:** Tests assert `"success"` for draft creation or final wording contains "waiting for final issuance", "issued", "refunded", "closed", "executed", or external-success language. [VERIFIED: tests/test_execute_action.py; src/agent/nodes/final_response.py]

### Pitfall 2: Reusing the Old Idempotency Key

**What goes wrong:** Same target/action with a changed amount or payload can silently reuse a stale draft. [VERIFIED: docs/contract-spec.md Section 16.4; src/agent/nodes/execute_action.py]

**Why it happens:** Current key shape omits tenant id, approval revision/auto marker, and `action_payload_hash`, and falls back to `"unknown"` target. [VERIFIED: src/agent/nodes/execute_action.py]

**How to avoid:** Construct the target key in the service from trusted fields and reject missing `target_id`. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

**Warning signs:** Tests expect `_no_approval_`, underscore-delimited keys, or `"unknown"` target fallback. [VERIFIED: tests/test_execute_action.py]

### Pitfall 3: Treating Idempotent Reuse as Safe Without Binding Checks

**What goes wrong:** An existing row for the same key could be returned even when `safety_snapshot_hash` differs. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

**Why it happens:** `ActionDraftRepository.create_or_get` currently checks only key existence and tenant mismatch. [VERIFIED: src/repositories/action_draft_repo.py]

**How to avoid:** On key hit, compare stored tenant/run/action/payload hash/snapshot hash fields; return existing only on exact match, otherwise return an idempotency conflict. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

**Warning signs:** Repository tests cover only cross-tenant conflicts and do not cover snapshot-hash conflicts. [VERIFIED: tests/agent/test_tools/test_create_coupon_grant_draft.py]

### Pitfall 4: Breaking Legacy Checkpoint Resume With a Blind Node Rename

**What goes wrong:** Live checkpoints already contain `branch:to:execute_action` and task path `~__pregel_pull, execute_action`; a pure graph rename can strand interrupted/resumable runs. [VERIFIED: docker PostgreSQL checkpoint queries]

**Why it happens:** LangGraph checkpoint state persists branch/channel metadata by node name. [VERIFIED: docker PostgreSQL checkpoint queries]

**How to avoid:** Add a named compatibility shim only if resume compatibility is required, forbid new references, test canonical path usage, and name the removal phase/gate. [VERIFIED: docs/phase-13-17-architecture-plan.md; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

**Warning signs:** `rg "execute_action"` still finds graph route/node registration outside named compatibility shims. [VERIFIED: rg source scan]

### Pitfall 5: Emitting Unsafe or Wrong Events

**What goes wrong:** Trace/replay can imply external execution or leak raw payload details. [VERIFIED: docs/contract-spec.md Section 17.2]

**Why it happens:** `MINIMAL_EVENT_TYPES` does not yet include `action_draft_created`, and the redaction guard rejects raw-like keys but the action event emitter does not yet exist. [VERIFIED: src/agent/events.py]

**How to avoid:** Register `action_draft_created`, use safe refs only, and add negative tests for no `action_execution_*` events and no raw action payload. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; src/agent/events.py]

**Warning signs:** Event payload contains `payload`, `raw_payload`, `arguments`, `data`, external refs, or `action_execution_completed`. [VERIFIED: src/agent/events.py; docs/eval-test-plan.md]

## Code Examples

Verified patterns from existing code and contract sources:

### Reuse Phase 13 Binding Validation

```python
# Source: src/actions/service.py
binding_error = await self._validate_action_binding(
    tenant_id=tenant_uuid,
    run_id=run_uuid,
    approval_request_id=approval_uuid,
    action_payload_hash=action_payload_hash,
    safety_snapshot_ref=safety_snapshot_ref,
    safety_snapshot_hash=safety_snapshot_hash,
)
if binding_error is not None:
    return binding_error
```

### Add Event Type Before Emitting

```python
# Source: src/agent/events.py; target event from docs/contract-spec.md Section 17.2.
MINIMAL_EVENT_TYPES = {
    # existing event types...
    "approval_resumed",
    "action_draft_created",
}
```

### Trace Output Should Carry Draft Outcome

```python
# Source: src/api/routers/traces.py current action_drafts shape; target from Phase 14 CONTEXT D-26.
{
    "id": str(draft.id),
    "action_type": draft.action_type,
    "status": draft.status,
    "draft_outcome": draft.draft_outcome,
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `execute_action` graph node creates a draft and reports `action_result.status=success`. [VERIFIED: src/agent/nodes/execute_action.py] | Canonical graph node should be `action_draft`, with `draft_outcome.v1` as the demo success signal. [VERIFIED: docs/contract-spec.md Sections 9.0-9.5, 16.3] | Target locked for Phase 14 in 2026-06-15 context. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | Plans must rename routes/contracts and update success sentinels together. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |
| Idempotency key `{run_id}_{approval_id}_{action_type}_{target_id}` with `"unknown"` fallback. [VERIFIED: src/agent/nodes/execute_action.py] | Key `{tenant_id}:{run_id}:{approval_revision_or_auto}:{action_type}:{target_id}:{action_payload_hash}` built at service boundary. [VERIFIED: docs/contract-spec.md Section 16.4] | Target locked for Phase 14. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | Same target/different hash creates a distinct draft; key reuse must compare snapshot hash. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |
| Trace timeline composes `ActionDraft` rows without `draft_outcome`. [VERIFIED: src/repositories/trace_repo.py; src/api/routers/traces.py] | `/trace` should include `draft_outcome`; full replay read switch remains Phase 15. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | Phase 14 target. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | Add trace output tests without building `/replay`. [VERIFIED: tests/test_trace_api.py] |
| Approval/snapshot validation was incomplete before Phase 13. [VERIFIED: .planning/phases/13-approval-state-machine/13-CONTEXT.md] | Phase 13 completed `CanonicalHashProfile v1`, `ActionSafetySnapshot`, and exact approval binding. [VERIFIED: .planning/phases/13-approval-state-machine/13-VERIFICATION.md] | Verified 2026-06-15. [VERIFIED: .planning/STATE.md] | Phase 14 must validate stored refs/hashes and not re-own snapshot production. [VERIFIED: docs/phase-13-17-architecture-plan.md] |

**Deprecated/outdated:**
- New backend call sites should not use `execute_action` for demo draft semantics except a named compatibility shim. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]
- New backend call sites should not use `action_result.status=success` for demo draft success. [VERIFIED: docs/contract-spec.md Section 16.3]
- New rows should not rely on `policy_snapshot_ref` or `evidence_snapshot_ref` as authorization guards. [VERIFIED: docs/contract-spec.md Section 15.3]

## Assumptions Log

All claims in this research were verified against local source, project planning docs, local runtime state, or tool output; no `[ASSUMED]` claims are intentionally present. [VERIFIED: sources listed below]

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| - | None | - | - |

## Open Questions (RESOLVED)

1. **Legacy checkpoint policy**
   - What we know: live `moca` checkpoints contain `execute_action` branch/task metadata. [VERIFIED: docker PostgreSQL checkpoint queries]
   - Resolution: retain `src/agent/nodes/execute_action.py` only as a Phase 14 action-draft-boundary-owned delegating shim. It must have no independent write/tool/persistence code, must forbid new imports/references outside explicit legacy tests, and must be removed/replaced by Phase 15 Replay Event Contract before Phase 15 verification, target no later than 2026-07-16 unless Phase 15 is replanned. [VERIFIED: docs/phase-13-17-architecture-plan.md; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

2. **Compatibility `action_result` removal gate**
   - What we know: Phase 14 allows retained `action_result` only as draft-only compatibility output with owner/tests/removal gate. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]
   - Resolution: retain `action_result` only as action-draft-boundary-owned deprecated compatibility output while graph/API/final consumers move to `draft_outcome`. It must never use `status="success"` to claim external execution. Phase 14 plans add tests forbidding new dependencies on `action_result.status == "success"` and name replacement/removal by Phase 15 Replay Event Contract before Phase 15 verification, target no later than 2026-07-16 unless Phase 15 is replanned. [VERIFIED: docs/contract-spec.md Section 16.3; docs/phase-13-17-architecture-plan.md; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Backend/tests | yes | 3.13.3 | Project requires `>=3.12`; current runtime satisfies it. [VERIFIED: python3 --version; pyproject.toml] |
| uv | Running tools/tests | yes | 0.11.2 | None needed. [VERIFIED: uv --version] |
| pytest | Validation | yes | 9.0.3 | None needed. [VERIFIED: `uv run pytest --version`] |
| Alembic | Migration | yes | 1.18.4 | None needed. [VERIFIED: `uv run alembic --version`] |
| Ruff | Lint | yes | 0.15.12 | None needed. [VERIFIED: `uv run ruff --version`] |
| Docker Compose | Local DB services | yes | Docker Compose command available; services healthy | Use running Compose services. [VERIFIED: docker compose ps] |
| PostgreSQL | DB-backed tests/runtime | yes via Docker | PostgreSQL 16.13 | Host `psql`/`pg_isready` missing; use `docker compose exec -T postgres ...`. [VERIFIED: command probes] |
| Redis | Existing stack service | yes via Docker | redis-cli 7.4.9 in container | Phase 14 tests should not require Redis; Docker service is healthy if needed. [VERIFIED: docker compose ps; docker compose exec redis] |
| DASHSCOPE_API_KEY | Live eval/demo only | key present by name in `.env` | secret value not read | Use FakeLLM/automated tests for Phase 14; live eval remains optional. [VERIFIED: `.env` key-name inspection; docs/evaluation.md] |

**Missing dependencies with no fallback:** None for Phase 14 automated planning. [VERIFIED: environment probes]

**Missing dependencies with fallback:**
- Host `pg_isready`, `psql`, and `redis-cli` are missing; Docker container commands provide the fallback. [VERIFIED: command probes]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 [VERIFIED: importlib.metadata] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/test_execute_action.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` [VERIFIED: existing test files] |
| Focused phase command | `uv run pytest tests/test_execute_action.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_approval_integration.py tests/test_approval_api.py tests/test_graph_routing.py tests/agent/test_events.py tests/test_trace_api.py tests/agent/test_nodes/test_final_response.py -q --tb=short` [VERIFIED: existing test files] |
| Full suite command | `uv run pytest -q --tb=short` and `uv run ruff check src tests` [VERIFIED: Makefile; pyproject.toml] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DEMO-01 | New draft rows persist `action_draft.v2` fields and `draft_outcome.v1`, with nullable legacy columns only for old rows. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | migration/service integration | `uv run pytest tests/actions/test_action_draft_v2.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` | No for `tests/actions/test_action_draft_v2.py`; yes for tool test. [VERIFIED: rg --files tests] |
| DEMO-01 | Demo mode creates no `action_executions`, outbox, reconciliation, compensation, external refs, or external events. [VERIFIED: docs/contract-spec.md Section 16.3] | negative integration/static | `uv run pytest tests/actions/test_action_draft_v2.py tests/agent/test_events.py -q --tb=short` | Partial; event test exists, action draft v2 negative file missing. [VERIFIED: tests/agent/test_events.py] |
| DEMO-01 | `action_draft_created` is registered/emitted with safe refs only. [VERIFIED: docs/contract-spec.md Section 17.2] | event integration | `uv run pytest tests/agent/test_events.py -q --tb=short` | Yes, needs extension. [VERIFIED: tests/agent/test_events.py] |
| DEMO-02 | Hash/revision/snapshot mismatches reject draft creation and idempotency reuse conflicts on snapshot mismatch. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | service integration | `uv run pytest tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_execute_action.py -q --tb=short` | Yes, needs extension. [VERIFIED: tests/agent/test_tools/test_create_coupon_grant_draft.py; tests/test_execute_action.py] |
| DEMO-02 | Graph routes and node registration use `action_draft`; `requested_operation="execute_action"` remains intent taxonomy only. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | unit/static architecture | `uv run pytest tests/test_graph_routing.py tests/agent/test_graph.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` | Partial; architecture file missing. [VERIFIED: tests/test_graph_routing.py; tests/agent/test_graph.py] |
| DEMO-02 | Final/API responses never claim real execution. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | unit/API golden wording | `uv run pytest tests/agent/test_nodes/test_final_response.py tests/test_approval_api.py -q --tb=short` | Yes, needs forbidden-phrase updates. [VERIFIED: existing tests] |
| DEMO-02 | `/trace` action draft output includes `draft_outcome` and no raw action payload. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] | API integration | `uv run pytest tests/test_trace_api.py -q --tb=short` | Yes, needs extension. [VERIFIED: tests/test_trace_api.py] |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_execute_action.py tests/agent/test_tools/test_create_coupon_grant_draft.py -q --tb=short` [VERIFIED: existing tests]
- **Per wave merge:** focused phase command plus `uv run ruff check src tests` [VERIFIED: Makefile]
- **Phase gate:** `uv run pytest -q --tb=short`, `uv run ruff check src tests`, and schema drift/coverage checks if the GSD planner emits them. [VERIFIED: Phase 13 verification pattern; Makefile]

### Wave 0 Gaps

- [ ] `tests/actions/test_action_draft_v2.py` - covers DEMO-01 v2 row completeness, nullable legacy behavior, `draft_outcome.v1`, and no execution/outbox tables. [VERIFIED: rg --files tests shows file absent]
- [ ] `tests/architecture/test_action_draft_boundaries.py` - forbids new backend references to `execute_action` except named shim/intent taxonomy and forbids direct external adapter/outbox imports. [VERIFIED: tests/architecture/test_approval_boundaries.py pattern exists]
- [ ] Extend `tests/test_execute_action.py` or rename to `tests/test_action_draft_node.py` - canonical node name, target id required, trusted key shape, `draft_outcome` output, and compatibility alias behavior. [VERIFIED: tests/test_execute_action.py]
- [ ] Extend `tests/agent/test_tools/test_create_coupon_grant_draft.py` - same-key exact reuse, snapshot hash conflict, persisted v2 fields, and `not_executed_demo` outcome. [VERIFIED: tests/agent/test_tools/test_create_coupon_grant_draft.py]
- [ ] Extend `tests/agent/test_events.py` - `action_draft_created` registration, retention classification, redaction guard, and no `action_execution_*` in demo mode. [VERIFIED: tests/agent/test_events.py]
- [ ] Extend `tests/test_trace_api.py` - trace `action_drafts[]` and timeline include `draft_outcome` but not raw payload. [VERIFIED: tests/test_trace_api.py]
- [ ] Extend `tests/agent/test_nodes/test_final_response.py` - forbidden phrases and positive "draft created, no action executed" wording. [VERIFIED: tests/agent/test_nodes/test_final_response.py]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Approval/trace APIs use authenticated `User` dependencies; Phase 14 should not accept caller-supplied tenant/user/run identity. [VERIFIED: src/api/routers/approvals.py; src/api/routers/traces.py] |
| V3 Session Management | partial | LangGraph checkpoints store run state; rename planning must handle legacy checkpoint state without treating it as authorization truth. [VERIFIED: docker PostgreSQL checkpoint queries] |
| V4 Access Control | yes | Approval decisions and trace access enforce tenant/user/role boundaries; action draft service must keep tenant/run checks. [VERIFIED: src/api/routers/approvals.py; src/api/routers/traces.py; src/actions/service.py] |
| V5 Input Validation | yes | Use Pydantic schemas and service validation for `target_id`, hashes, snapshot refs, and idempotency conflict behavior. [VERIFIED: src/api/schemas/approvals.py; src/actions/service.py] |
| V6 Cryptography | yes | Use the existing SHA-256 canonical hash helper; do not create a second hash profile. [VERIFIED: src/common/canonical_hash.py] |

### Known Threat Patterns for Phase 14

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stale approval or changed action payload creates a draft | Tampering / Elevation of Privilege | Require exact `approval_result.v1`, `action_payload_hash`, `safety_snapshot_ref`, and `safety_snapshot_hash`; validate against Phase 13 rows. [VERIFIED: src/actions/service.py; tests/approvals/test_hash_binding.py] |
| Cross-tenant idempotency collision | Tampering | Embed tenant id in the service-built key and keep global unique constraint plus tenant defense-in-depth. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; src/db/models.py] |
| Unknown target key collision | Tampering | Reject missing `target_id`; do not fall back to `"unknown"`. [VERIFIED: .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md; src/agent/nodes/execute_action.py] |
| Demo response claims real action executed | Spoofing / Repudiation | `draft_outcome.v1` plus forbidden-phrase tests for backend/final/API output. [VERIFIED: docs/contract-spec.md Section 16.3; src/agent/nodes/final_response.py] |
| Raw action payload leaks into trace event | Information Disclosure | Emit safe refs and redacted payload only; rely on existing redaction guard. [VERIFIED: src/agent/events.py; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |
| External side effect from demo mode | Elevation of Privilege | Do not create execution/outbox tables or call external adapters in Phase 14; add negative tests. [VERIFIED: docs/phase-13-17-architecture-plan.md; .planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/14-demo-action-executor-boundary/14-CONTEXT.md` - locked Phase 14 decisions, boundaries, deferred scope, and code pointers. [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` - DEMO-01 and DEMO-02 requirement text plus planning requirements. [VERIFIED: file read]
- `.planning/ROADMAP.md` - Phase 14 goal, dependency, success criteria, and Phase 13-17 architecture standard. [VERIFIED: file read]
- `.planning/STATE.md` - Phase 13 completion and current focus. [VERIFIED: file read]
- `docs/phase-13-17-architecture-plan.md` - mandatory Phase 14 architecture target, deletion/quarantine rules, and gate tests. [VERIFIED: file read]
- `docs/contract-spec.md` Sections 9, 10.1, 15.3, 16.1-16.4, 17.2, 18.3, 19 - normative action draft, snapshot, event, and storage contracts. [VERIFIED: file read]
- `docs/eval-test-plan.md` Section 21.6 - demo draft golden flow and forbidden external-success examples. [VERIFIED: file read]
- `CLAUDE.md` - project-specific workflow and contract/spec constraints. [VERIFIED: file read]
- Source files: `src/actions/service.py`, `src/actions/drafts.py`, `src/repositories/action_draft_repo.py`, `src/db/models.py`, `src/db/migrations/versions/005_approval_tables.py`, `src/agent/nodes/execute_action.py`, `src/agent/graph.py`, `src/agent/nodes/final_response.py`, `src/api/routers/approvals.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `src/agent/events.py`, `src/tools/catalog.py`, `src/tools/manager.py`, `src/tools/executors/action.py`. [VERIFIED: file reads]
- Tests: `tests/test_execute_action.py`, `tests/agent/test_tools/test_create_coupon_grant_draft.py`, `tests/test_graph_routing.py`, `tests/agent/test_nodes/test_final_response.py`, `tests/test_trace_api.py`, `tests/agent/test_events.py`, `tests/approvals/test_hash_binding.py`. [VERIFIED: file reads]
- Runtime probes: Docker Compose service status, PostgreSQL schema/count/checkpoint searches, importlib package version checks, and environment command probes. [VERIFIED: tool output]

### Secondary (MEDIUM confidence)

- `docs/architecture-overview.md`, `docs/migration-plan.md`, and `docs/agent-architecture-phase-decomposition.md` were used only as supporting mirrors where they align with the contract and phase context. [VERIFIED: rg scan]

### Tertiary (LOW confidence)

- None. [VERIFIED: source log]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions verified from installed environment and project manifests. [VERIFIED: importlib.metadata; pyproject.toml]
- Architecture: HIGH - Phase 14 decisions, mandatory architecture doc, contract spec, and current code all point to the same owner boundaries. [VERIFIED: listed primary sources]
- Runtime inventory: MEDIUM-HIGH - live local DB/checkpoints were queried, but legacy checkpoint business value still needs a planner/user decision. [VERIFIED: docker PostgreSQL queries]
- Pitfalls: HIGH - each pitfall maps to current code/tests and locked Phase 14 decisions. [VERIFIED: listed primary sources]

**Research date:** 2026-06-16 [VERIFIED: environment_context]
**Valid until:** 2026-07-16 for local codebase facts; re-run package/runtime probes if planning occurs after major dependency or migration changes. [VERIFIED: project is active and Phase 14 not yet planned]
