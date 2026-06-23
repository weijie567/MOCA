# Phase 28: Decision Event Foundation - Research

**Researched:** 2026-06-23 [VERIFIED: system current date]
**Domain:** Replay / observability event envelope, trusted identity projection, redaction, and contract tests [VERIFIED: .planning/ROADMAP.md]
**Confidence:** HIGH [VERIFIED: codebase inspection + contract-spec.md]

<user_constraints>
## User Constraints (from CONTEXT.md)

Source: copied from `.planning/phases/28-decision-event-foundation/28-CONTEXT.md`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

### Locked Decisions

#### Envelope Contract Surface

- **D-01:** Add an explicit `DecisionEventEnvelopeV1` Pydantic schema. The current `ReplayService.project_minimal_event()` dict projection and `src.agent.events` constants are too implicit for the Phase 28 foundation contract.
- **D-02:** Place the schema in `src/replay/decision_events.py`. Observability / Replay owns `DecisionEventEnvelopeV1`, `emit_decision_event`, and replay lifecycle events; do not put this contract under `src/platform/`.
- **D-03:** Lock the schema strictly: `schema_version="minimal_event_envelope.v1"`, required fields from `contract-spec.md` §17.2, `extra="forbid"`, registered `event_type` validation, and basic conditional validation such as operation lifecycle events requiring `operation_id`.
- **D-04:** Do not implement `ReplayEventV3` parent/attempt pairing in Phase 28; that remains full replay/event pairing responsibility.
- **D-05:** Do not change DB schema. Reuse existing `agent_trace_events` / `AgentTraceEvent` support for `minimal_event_envelope.v1` and `replay_event.v3` rows. Phase 28 should add the facade, emitter, normalization helpers, and tests.

#### Emitter API And Trusted Identity

- **D-06:** Add `emit_decision_event(...)` in `src/replay/decision_events.py`. It should be the replay-owned entrypoint for minimal decision event emission and should call the existing `ReplayService.append_event(...)` persistence path.
- **D-07:** Keep `src.agent.events.emit_event` as a compatibility wrapper, but route it through the new replay-owned entrypoint so existing tool/memory/approval/action writers enter the unified contract without broad rewrites.
- **D-08:** Prefer `ReplayContext` / trusted projection as the identity source for new emitter usage. `run_id`, `tenant_id`, `thread_id`, and `trace_id` should come from Phase 27 trusted context projection, not caller-assembled ad hoc values.
- **D-09:** Identity/source failures must fail closed with a testable error. Decision events are audit/replay truth; do not write partial-identity events and do not silently skip event emission as a normal success path.
- **D-10:** Migrate only the thin wrapper and key path in Phase 28. Do not broadly rewrite all existing writer call sites; later domain phases own their service-specific event payload migrations.

#### Reason-Code And Version Placement

- **D-11:** Standardize decision payloads on `reason_codes: list[str]`. Single-reason decisions still use a one-item list.
- **D-12:** Compatibility wrappers may accept legacy `reason_code` and normalize it into `reason_codes`, but downstream platform services should not continue producing split singular/plural formats.
- **D-13:** Normalize `reason_codes` with first-seen de-duplication. Preserve business priority order; `reason_codes[0]` carries primary-reason semantics. Do not alphabetically sort reason codes.
- **D-14:** Place policy/model/tool version metadata under `redacted_payload.versions`, for example `policy_version`, `model_version`, and `tool_version`. The envelope top level keeps only `redaction_policy_version`.
- **D-15:** Reason codes must be non-empty `snake_case` strings and de-duplicated. Phase 28 should add tests for this convention, but should not introduce a global allowlist because Phase 29-35 service-specific reason codes are not all known yet.

#### Redaction, Resource Refs, And Initial Coverage

- **D-16:** Tighten common helpers and add focused key-path tests. Phase 28 should establish the foundation and necessary regressions, not pull full Tool/Memory/RAG/Approval/Action domain migrations into this phase.
- **D-17:** `resource_refs` must contain only stable typed refs, hashes, and ids. Continue patterns such as `action_payload_hash`, `safety_snapshot_hash`, approval revision refs, `draft_id`, tool names, and evidence/business fact refs.
- **D-18:** Do not store raw business payloads, tool arguments, prompts, user text, PII, or secrets in `resource_refs`. Business identifiers such as order/refund numbers should not be naked debug fields; when needed, use typed refs, hashes, or business fact / evidence refs.
- **D-19:** Redaction guard coverage must inspect both `redacted_payload` and `resource_refs`, so unsafe keys cannot bypass redaction through refs.
- **D-20:** Phase 28 tests should emphasize contract strictness, negative leakage, and wrapper compatibility: required/conditional fields, schema extra rejection, reason/version normalization, legacy `reason_code` conversion, forbidden key checks in payload and refs, and no regression in sequence allocation.

### Claude's Discretion

- Exact class/helper names are flexible as long as `DecisionEventEnvelopeV1` and `emit_decision_event(...)` exist at the replay boundary and the existing `src.agent.events.emit_event` compatibility path remains usable.
- Exact test file split is flexible. Prefer focused tests near `tests/replay/` and compatibility regressions for `tests/agent/test_events.py` or equivalent existing event tests.
- Exact error class names are left to planning, but identity and contract failures must be explicit and testable.

### Deferred Ideas (OUT OF SCOPE)

None - discussion stayed within Phase 28 scope. Full Tool/Memory/RAG/Approval/Action event payload migrations remain owned by their later phases, and full ReplayEventV3 enrichment/replay service behavior remains outside Phase 28.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APF-05 | A minimal `DecisionEventEnvelopeV1` / event emitter foundation records stable reason codes, policy/model/tool versions, redaction policy, and run/tenant/trace identity for later platform service decisions. [VERIFIED: .planning/REQUIREMENTS.md] | Use `src/replay/decision_events.py` to formalize the existing minimal envelope, route `src.agent.events.emit_event` through `emit_decision_event(...)`, normalize reason/version fields in `redacted_payload`, guard both payload and refs, and preserve `ReplayService.append_event(...)` allocation/persistence. [VERIFIED: src/replay/service.py; src/agent/events.py; src/replay/validators.py; src/platform/context_projections.py] |
</phase_requirements>

## Summary

Phase 28 should be a narrow replay/observability foundation phase, not a schema migration or broad event-writer rewrite. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] The existing `AgentTraceEvent` table already stores `schema_version`, run/tenant/thread/trace identity, sequence, operation id, event type, actor, resource refs, redaction policy, and redacted payload, and its checks already allow both `minimal_event_envelope.v1` and `replay_event.v3`. [VERIFIED: src/db/models.py; src/db/migrations/versions/006_agent_trace_events.py; src/db/migrations/versions/010_replay_event_v3.py]

The main implementation target is a new replay-owned `src/replay/decision_events.py` facade containing `DecisionEventEnvelopeV1`, normalization helpers, resource-ref redaction guard coverage, and `emit_decision_event(...)`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] That facade should call `ReplayService.append_event(...)`, which already validates registered event types, guards redacted payloads, obtains a per-run advisory lock, allocates monotonic sequence numbers, generates stable UUIDv5 event ids from `(run_id, sequence)`, persists rows, and returns the minimal projection when `schema_version="minimal_event_envelope.v1"`. [VERIFIED: src/replay/service.py]

The highest-risk compatibility seams are `src.agent.events.emit_event`, `RunLifecycleService` using singular `reason_code`, `memory_write` silently skipping/catching event emission, and existing tool/approval/action event writers that already depend on current call signatures. [VERIFIED: src/agent/events.py; src/replay/lifecycle.py; src/agent/nodes/memory_write.py; src/agent/nodes/investigate.py; src/approvals/events.py; src/actions/service.py] The planner should preserve current writer signatures while adding strict validation at the new facade and focused tests around missing identity, singular-to-plural reason conversion, version placement, resource-ref leakage, and sequence allocator regressions. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; tests/agent/test_events.py; tests/replay/test_sequence_allocator.py]

**Primary recommendation:** Implement `src/replay/decision_events.py` as the single typed minimal-envelope facade over the existing `ReplayService.append_event(...)`, then convert `src.agent.events.emit_event` into a compatibility shim that normalizes legacy payloads and delegates to `emit_decision_event(...)`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/replay/service.py; src/agent/events.py]

## Project Constraints (from CLAUDE.md)

- `docs/contract-spec.md` is the only normative MOCA architecture contract source; implementation phases must not silently diverge from it. [VERIFIED: CLAUDE.md; docs/contract-spec.md]
- If implementation and spec differ, the phase must either fix the spec or record an MVP/target-state scope annotation and leave a `.planning/` decision record. [VERIFIED: CLAUDE.md]
- Phase-level plans and larger changes require GSD native review first, then independent Codex cross-check; small bugs do not need the full workflow. [VERIFIED: CLAUDE.md]
- Phase plan revisions that add/delete/reorder tasks, affect dependencies/waves, cross at least three files, or require source rereading are treated as large edits delegated to Codex in the project workflow. [VERIFIED: CLAUDE.md]
- Local debugging, launch, UI/API/RAG/agent/memory/tool-call validation failures must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese after handling. [VERIFIED: CLAUDE.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Minimal decision event envelope | API / Backend - Observability / Replay | Database / Storage | `contract-spec.md` assigns `DecisionEventEnvelopeV1`, minimal event envelope, replay artifacts, sequence allocator, and redaction policy to Observability / Replay; rows persist in `agent_trace_events`. [CITED: docs/contract-spec.md §0.2; VERIFIED: src/db/models.py] |
| Trusted event identity | API / Backend - TrustedContextFactory projection | API / Backend - Replay emitter | `TrustedContext` supplies trusted tenant/user/thread/run/trace fields, and `ReplayContext` projects those fields plus projection-local version metadata for replay consumers. [CITED: docs/contract-spec.md §8.0; VERIFIED: src/platform/trusted_context.py; src/platform/context_projections.py] |
| Sequence allocation and ordering | API / Backend - ReplayService | Database / Storage | `ReplayService` locks per run with `pg_advisory_xact_lock`, reads `MAX(sequence)+1`, and the table enforces unique `(run_id, sequence)`. [VERIFIED: src/replay/service.py; src/db/models.py] |
| Redaction and resource-reference safety | API / Backend - Replay validators | API / Backend - Service emitters | `guard_redacted_payload(...)` already rejects recursive unsafe payload keys; Phase 28 must extend equivalent coverage to `resource_refs` by user decision D-19. [VERIFIED: src/replay/validators.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |
| Domain-specific payload details | API / Backend - owning platform/domain service | API / Backend - Replay emitter | `contract-spec.md` allows services to extend decision data inside `redacted_payload`; Phase 28 must not add service-specific top-level envelope fields. [CITED: docs/contract-spec.md §17.2] |

## Standard Stack

### Core

| Library / Component | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Python | `>=3.12`; local `uv run` uses Python 3.13.3 [VERIFIED: pyproject.toml; terminal `python --version`] | Runtime for backend, tests, and schema code. [VERIFIED: pyproject.toml] | Existing project runtime and all inspected modules are Python. [VERIFIED: pyproject.toml; src/replay/service.py] |
| Pydantic | 2.13.4 [VERIFIED: `uv run python` import; uv.lock] | Strict contract schema via `BaseModel`, `ConfigDict(extra="forbid")`, `Field`, validators. [VERIFIED: src/replay/schemas.py; src/platform/trusted_context.py] | Existing ReplayEventV3, TrustedContext, and projections already use this pattern. [VERIFIED: src/replay/schemas.py; src/platform/context_projections.py] |
| SQLAlchemy async ORM | 2.0.49 [VERIFIED: `uv run python` import; uv.lock] | Persist/query `AgentTraceEvent` through async sessions and table metadata. [VERIFIED: src/replay/service.py; src/db/models.py] | Existing replay service and tests use `AsyncSession`, `select`, and mapped ORM models. [VERIFIED: src/replay/service.py; tests/replay/test_sequence_allocator.py] |
| PostgreSQL + asyncpg | PostgreSQL 16.13 available locally; asyncpg 0.31.0 [VERIFIED: asyncpg connection probe; `uv run python` import; uv.lock] | Transactional event-store tests, advisory locks, JSONB, UUID columns. [VERIFIED: tests/conftest.py; src/replay/service.py; src/db/models.py] | Existing test fixtures create a PostgreSQL test DB, enable `vector`, and rebuild metadata. [VERIFIED: tests/conftest.py] |
| Pytest + pytest-asyncio | pytest 9.0.3 under `uv run`; pytest-asyncio 1.3.0 [VERIFIED: `uv run python` import; uv.lock] | Contract, async DB, and compatibility tests. [VERIFIED: pyproject.toml; tests/conftest.py] | Existing event/replay tests already use `pytest.mark.asyncio` and shared async fixtures. [VERIFIED: tests/agent/test_events.py; tests/replay/test_sequence_allocator.py] |
| Alembic | 1.18.4 [VERIFIED: `uv run python` import; uv.lock] | Migration contract inspection, not expected to change in Phase 28. [VERIFIED: tests/replay/test_replay_migration_contract.py] | Existing migration tests assert the current table supports minimal/V3 coexistence. [VERIFIED: tests/replay/test_replay_migration_contract.py] |

### Supporting

| Library / Component | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| `ReplayService` | Repository component, not external package [VERIFIED: src/replay/service.py] | Single persistence, sequence allocation, event projection path. [VERIFIED: src/replay/service.py] | Always use for event persistence; do not insert `AgentTraceEvent` directly except in tests. [VERIFIED: tests/replay/test_sequence_allocator.py] |
| `REPLAY_EVENT_TYPES` / validators | Repository component [VERIFIED: src/replay/validators.py] | Registered event-type validation and redaction-key registry. [VERIFIED: src/replay/validators.py] | Reuse in `DecisionEventEnvelopeV1` field validation and resource-ref guard. [VERIFIED: src/replay/validators.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |
| `ReplayContext` | Repository component [VERIFIED: src/platform/context_projections.py] | Trusted identity plus projection-local policy/model/tool/artifact metadata. [VERIFIED: src/platform/context_projections.py] | Prefer for new `emit_decision_event(...)` usage and version normalization. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/platform/context_projections.py] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `DecisionEventEnvelopeV1` over existing `agent_trace_events` | New table or parallel event format | Rejected because user decision D-05 forbids schema changes and `contract-spec.md` says `DecisionEventEnvelopeV1` must use `minimal_event_envelope.v1`, not a parallel envelope. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; CITED: docs/contract-spec.md §17.2] |
| Compatibility shim through `src.agent.events.emit_event` | Broadly migrate all writer call sites | Rejected for Phase 28 because D-10 says only the thin wrapper and key path should migrate now. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |
| Reason-code global allowlist | Service-owned allowlists now | Rejected because Phase 29-35 service-specific reason codes are not all known and D-15 forbids a global allowlist in Phase 28. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |
| Full `ReplayEventV3` operation pairing in new facade | Require parent/attempt on minimal events | Rejected because D-04 keeps V3 parent/attempt pairing outside Phase 28, and current V3 pairing already exists in `ReplayService` for `schema_version="replay_event.v3"`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/replay/service.py; src/replay/pairing.py] |

**Installation:**

No new dependency is needed for Phase 28 because the required schema, ORM, async DB, and test libraries are already in `pyproject.toml` and `uv.lock`. [VERIFIED: pyproject.toml; uv.lock]

```bash
uv sync --extra dev
```

Use `uv run ...` when invoking Python or pytest so the locked project environment is used instead of the global Python 3.9 pytest binary. [VERIFIED: terminal `pytest --version`; terminal `uv run python` imports]

## Architecture Patterns

### System Architecture Diagram

```text
Trusted API/Auth/Run boundary
  -> TrustedContextFactory
  -> ReplayContext projection
       | carries run_id, tenant_id, thread_id, trace_id
       | carries projection-local policy/model/tool/artifact metadata
       v
Domain or graph event writer
  -> compatibility wrapper: src.agent.events.emit_event(...)
  -> replay-owned facade: src.replay.decision_events.emit_decision_event(...)
       | validate DecisionEventEnvelopeV1 shape
       | normalize reason_code -> reason_codes
       | place versions under redacted_payload.versions
       | guard redacted_payload and resource_refs
       | require operation_id for operation lifecycle event types
       v
ReplayService.append_event(...)
       | validate registered event_type
       | lock run and allocate next sequence
       | persist AgentTraceEvent row
       v
agent_trace_events
       | unique(run_id, sequence)
       | schema_version in minimal_event_envelope.v1 / replay_event.v3
       v
Minimal event projection returned to caller
  -> later ReplayEventV3 projection/read API can coexist without backwriting minimal rows
```

This flow reflects current ownership and data flow: `TrustedContextFactory` owns trusted identity, Observability / Replay owns `emit_decision_event` and the event store, and `ReplayService.append_event(...)` owns persistence and allocation. [CITED: docs/contract-spec.md §0.2 and §8.0; VERIFIED: src/platform/trusted_context.py; src/platform/context_projections.py; src/replay/service.py; src/db/models.py]

### Recommended Project Structure

```text
src/
├── replay/
│   ├── decision_events.py      # new DecisionEventEnvelopeV1, normalization, guard, emitter facade
│   ├── service.py              # existing allocator/persistence/projection; small integration only
│   ├── validators.py           # shared event-type and redaction/resource-ref guards
│   └── __init__.py             # export new public replay boundary
├── agent/
│   └── events.py               # compatibility shim preserving old call signature
└── platform/
    └── context_projections.py  # existing ReplayContext identity/version source; avoid widening

tests/
├── replay/
│   ├── test_decision_events.py         # new strict envelope/emitter tests
│   ├── test_sequence_allocator.py      # extend or preserve allocator sharing regression
│   └── test_replay_service.py          # minimal projection alignment regression
└── agent/
    └── test_events.py                  # wrapper compatibility tests
```

This structure keeps the contract under replay ownership and avoids placing the event schema under `src/platform`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; CITED: docs/contract-spec.md §0.2]

### Pattern 1: Strict Minimal Envelope Schema

**What:** Define `DecisionEventEnvelopeV1` with Pydantic v2, `extra="forbid"`, a literal `schema_version`, required §17.2 fields, and event-type validation. [CITED: docs/contract-spec.md §17.2; VERIFIED: src/replay/schemas.py]

**When to use:** Use for every minimal event projection returned from `emit_decision_event(...)` and for validating `ReplayService.project_minimal_event(...)` alignment. [VERIFIED: src/replay/service.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Example:**

```python
# Source: src/replay/schemas.py strict Pydantic pattern; docs/contract-spec.md §17.2 fields
class DecisionEventEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["minimal_event_envelope.v1"] = "minimal_event_envelope.v1"
    event_id: UUID
    sequence: int = Field(gt=0)
    operation_id: UUID | None = None
    run_id: UUID
    tenant_id: UUID
    thread_id: str = Field(min_length=1)
    trace_id: str | None = None
    event_type: str
    occurred_at: datetime
    actor: dict[str, Any]
    resource_refs: dict[str, Any]
    redaction_policy_version: str = Field(min_length=1)
    redacted_payload: dict[str, Any]

    @field_validator("event_type")
    @classmethod
    def _registered_event_type(cls, value: str) -> str:
        validate_event_type(value)
        return value
```

### Pattern 2: Replay-Owned Emitter Facade

**What:** Add `emit_decision_event(...)` in `src/replay/decision_events.py`, normalize inputs, then call `ReplayService(session).append_event(..., schema_version="minimal_event_envelope.v1")`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/replay/service.py]

**When to use:** Use for new platform service decision events and as the target for the existing `src.agent.events.emit_event` wrapper. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/agent/events.py]

**Example:**

```python
# Source: src/replay/service.py append_event contract and src.agent.events.emit_event wrapper
async def emit_decision_event(
    session: AsyncSession,
    *,
    context: ReplayContext | None = None,
    run_id: UUID | str | None = None,
    tenant_id: UUID | str | None = None,
    thread_id: str | None = None,
    trace_id: str | None = None,
    event_type: str,
    actor: dict[str, Any],
    resource_refs: dict[str, Any],
    redacted_payload: dict[str, Any],
    operation_id: UUID | str | None = None,
    reason_code: str | None = None,
    reason_codes: Sequence[str] | None = None,
    redaction_policy_version: str = "redaction.v1",
) -> dict[str, Any]:
    identity = _identity_from_replay_context_or_args(context, run_id, tenant_id, thread_id, trace_id)
    payload = _normalize_decision_payload(
        redacted_payload,
        reason_code=reason_code,
        reason_codes=reason_codes,
        context=context,
    )
    guard_redacted_payload(payload)
    guard_resource_refs(resource_refs)
    _require_operation_id_for_operation_events(event_type, operation_id)
    raw = await ReplayService(session).append_event(
        **identity,
        event_type=event_type,
        actor=actor,
        resource_refs=resource_refs,
        redacted_payload=payload,
        operation_id=operation_id,
        redaction_policy_version=redaction_policy_version,
        schema_version="minimal_event_envelope.v1",
    )
    return DecisionEventEnvelopeV1.model_validate(raw).model_dump(mode="python")
```

### Pattern 3: Compatibility Wrapper With Legacy Reason Conversion

**What:** Keep `src.agent.events.emit_event` callable by current writers but have it delegate to `emit_decision_event(...)`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/agent/events.py]

**When to use:** Use only to preserve existing graph/tool/memory/approval/action event paths during Phase 28. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/agent/nodes/investigate.py; src/agent/nodes/memory_write.py; src/approvals/events.py; src/actions/service.py]

**Example:**

```python
# Source: src.agent.events.emit_event existing signature
async def emit_event(session: AsyncSession, **kwargs: Any) -> dict[str, Any]:
    return await emit_decision_event(session, **kwargs)
```

### Pattern 4: First-Seen Reason-Code Normalization

**What:** Convert singular `reason_code` and plural `reason_codes` into a non-empty, snake_case, first-seen de-duplicated list under `redacted_payload["reason_codes"]`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**When to use:** Use at the new facade and wrapper boundary so legacy lifecycle/memory payloads can be normalized without broad call-site rewrites. [VERIFIED: src/replay/lifecycle.py; src/agent/nodes/memory_write.py]

**Example:**

```python
# Source: D-11 through D-15 in 28-CONTEXT.md
REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

def normalize_reason_codes(*values: str | Sequence[str] | None) -> list[str]:
    ordered: list[str] = []
    for value in values:
        raw_items = [value] if isinstance(value, str) else list(value or [])
        for item in raw_items:
            code = str(item).strip()
            if not code or not REASON_CODE_RE.fullmatch(code):
                raise ValueError("reason_codes must be non-empty snake_case strings")
            if code not in ordered:
                ordered.append(code)
    return ordered
```

### Anti-Patterns to Avoid

- **Parallel event envelope:** Do not create `decision_event.v1` rows or a new event table because `DecisionEventEnvelopeV1` must map to `minimal_event_envelope.v1`. [CITED: docs/contract-spec.md §17.2; VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
- **Top-level service metadata:** Do not add top-level fields such as `policy_version`, `model_version`, or `tool_version`; put them under `redacted_payload.versions`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
- **Alphabetic reason sorting:** Do not sort reason codes because the first item carries primary-reason semantics. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
- **Payload-only redaction guard:** Do not only guard `redacted_payload`; Phase 28 must also guard `resource_refs`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/replay/validators.py]
- **Silent event skip:** Do not treat missing identity or emitter failures as normal success for decision events; D-09 requires fail-closed behavior. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
- **Full V3 pairing expansion:** Do not require `parent_operation_id` or `attempt` for minimal events in Phase 28 because full `ReplayEventV3` enrichment is outside scope. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/replay/pairing.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Event persistence and sequence ordering | Direct `AgentTraceEvent` inserts in production code | `ReplayService.append_event(...)` | It already owns advisory locking, sequence allocation, event id generation, validation, flush, and minimal/V3 projection branching. [VERIFIED: src/replay/service.py] |
| Contract schema validation | Manual dict key checks scattered across emitters | `DecisionEventEnvelopeV1` Pydantic schema | Existing strict schemas use Pydantic `extra="forbid"` and validators. [VERIFIED: src/replay/schemas.py; src/platform/trusted_context.py] |
| Event type registry | Local hard-coded event sets in each emitter | `REPLAY_EVENT_TYPES` and `validate_event_type(...)` | Existing registry is used by ReplayEventV3 and migration contract tests compare migration check values against it. [VERIFIED: src/replay/validators.py; tests/replay/test_replay_migration_contract.py] |
| Redaction recursion | One-off top-level forbidden-key checks | Shared recursive guard for payload and refs | Current `guard_redacted_payload(...)` walks nested dict/list structures; Phase 28 should reuse that pattern for `resource_refs`. [VERIFIED: src/replay/validators.py] |
| Trusted identity assembly | Caller-built run/tenant/thread/trace dicts for new code | `ReplayContext` from `project_to_replay_context(...)` | Phase 27 projections already derive identity from `TrustedContext` and keep version metadata projection-local. [VERIFIED: src/platform/context_projections.py; tests/platform/test_context_projections.py] |

**Key insight:** Phase 28 is a contract facade and validation phase over an existing event store, not a data-model invention phase. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/db/models.py; src/replay/service.py]

## Common Pitfalls

### Pitfall 1: Adding a Parallel Decision Event Format

**What goes wrong:** The planner asks for a separate `DecisionEventEnvelopeV1` schema version or table instead of mapping to `minimal_event_envelope.v1`. [CITED: docs/contract-spec.md §17.2]

**Why it happens:** The named schema `DecisionEventEnvelopeV1` can look like a new persisted format even though the contract says its underlying `schema_version` stays fixed to `minimal_event_envelope.v1`. [CITED: docs/contract-spec.md §17.2]

**How to avoid:** Make `DecisionEventEnvelopeV1.schema_version` a literal `"minimal_event_envelope.v1"` and validate `ReplayService.project_minimal_event(...)` through it. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/replay/service.py]

**Warning signs:** New migrations, new event table names, or top-level fields beyond §17.2. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; CITED: docs/contract-spec.md §17.2]

### Pitfall 2: Weakening Existing Writer Compatibility

**What goes wrong:** Existing tool/RAG, memory, approval, action draft, and tests break because `emit_event(...)` loses its current signature or return shape. [VERIFIED: src/agent/events.py; src/agent/nodes/investigate.py; src/agent/nodes/memory_write.py; src/approvals/events.py; src/actions/service.py; tests/agent/test_events.py]

**Why it happens:** Current callers pass run/tenant/thread identity directly and expect a dict minimal envelope. [VERIFIED: src/agent/events.py; tests/agent/test_events.py]

**How to avoid:** Keep `emit_event(...)` as a shim and add new stricter `ReplayContext` support without making it mandatory for legacy call sites in Phase 28. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Warning signs:** Broad writer rewrites, changed return keys, or test churn outside replay/event compatibility files. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

### Pitfall 3: Normalizing Reason Codes in the Wrong Place

**What goes wrong:** Some events keep singular `reason_code`, some use plural `reason_codes`, and downstream services cannot rely on one convention. [VERIFIED: src/replay/lifecycle.py; src/agent/nodes/memory_write.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Why it happens:** Existing lifecycle and memory paths already store singular `reason_code` in payloads. [VERIFIED: src/replay/lifecycle.py; src/agent/nodes/memory_write.py]

**How to avoid:** Normalize in `emit_decision_event(...)` and the compatibility wrapper, preserving legacy acceptance but returning/storing plural `reason_codes`. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Warning signs:** Tests assert only `reason_code` after Phase 28, or reason-code order changes due to sorting. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

### Pitfall 4: Letting Unsafe Keys Bypass Through Resource Refs

**What goes wrong:** A caller puts raw prompts, raw tool outputs, PII, secrets, or naked business payloads under `resource_refs` because only `redacted_payload` is guarded. [VERIFIED: src/replay/validators.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Why it happens:** Current `ReplayService.append_event(...)` calls `guard_redacted_payload(redacted_payload)` but does not call a guard on `resource_refs`. [VERIFIED: src/replay/service.py]

**How to avoid:** Add a shared `guard_resource_refs(...)` or generalize the existing recursive guard, then invoke it before persistence and in schema validation. [VERIFIED: src/replay/validators.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Warning signs:** A test with `resource_refs={"raw_payload": ...}` persists or returns successfully. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

### Pitfall 5: Treating Minimal Operation Validation as Full V3 Pairing

**What goes wrong:** The minimal facade rejects legitimate lifecycle or domain events because it imports V3 attempt/parent pairing requirements wholesale. [VERIFIED: src/replay/pairing.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Why it happens:** `ReplayService` performs pairing validation only when appending `schema_version="replay_event.v3"`, while minimal events currently bypass V3 pairing. [VERIFIED: src/replay/service.py]

**How to avoid:** For Phase 28, require only basic conditional `operation_id` for operation lifecycle event names and leave `attempt`/parent pairing to V3. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/replay/pairing.py]

**Warning signs:** Minimal `tool_call_started` requires `attempt`, or run/approval lifecycle events require `operation_id`. [CITED: docs/contract-spec.md §17.2; VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

## Code Examples

### Validate Minimal Projection Through the New Schema

```python
# Source: src/replay/service.py project_minimal_event and src/replay/schemas.py strict validation pattern
def project_minimal_event(self, event: AgentTraceEvent) -> dict[str, Any]:
    projected = {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "sequence": event.sequence,
        "operation_id": event.operation_id,
        "run_id": event.run_id,
        "tenant_id": event.tenant_id,
        "thread_id": event.thread_id,
        "trace_id": event.trace_id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "actor": event.actor,
        "resource_refs": event.resource_refs,
        "redaction_policy_version": event.redaction_policy_version,
        "redacted_payload": event.redacted_payload,
    }
    return DecisionEventEnvelopeV1.model_validate(projected).model_dump(mode="python")
```

### Normalize Versions From ReplayContext

```python
# Source: src/platform/context_projections.py ReplayContext metadata fields and D-14 in 28-CONTEXT.md
def _versions_from_context(context: ReplayContext | None) -> dict[str, str]:
    if context is None:
        return {}
    return {
        key: value
        for key, value in {
            "policy_version": context.policy_version,
            "model_version": context.model_version,
            "tool_version": context.tool_version,
        }.items()
        if value
    }
```

### Resource Refs Guard Mirrors Payload Guard

```python
# Source: src/replay/validators.py recursive guard pattern and D-19 in 28-CONTEXT.md
def guard_resource_refs(resource_refs: dict[str, Any]) -> None:
    _guard_forbidden_keys(resource_refs, path="resource_refs")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Untyped minimal envelope dict returned by `ReplayService.project_minimal_event(...)` | Explicit `DecisionEventEnvelopeV1` schema validating the same `minimal_event_envelope.v1` shape | Phase 28 planned [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] | Planner should add schema and tests, not a new format. [CITED: docs/contract-spec.md §17.2] |
| `src.agent.events.emit_event` directly calls `ReplayService.append_event(...)` | Replay-owned `emit_decision_event(...)` with compatibility shim | Phase 28 planned [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] | Preserves current callers while centralizing strict contract rules. [VERIFIED: src/agent/events.py] |
| Some payloads use singular `reason_code` | Standard `reason_codes: list[str]`, with legacy singular accepted only at compatibility boundary | Phase 28 planned [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] | Downstream phases can rely on plural reason-code convention. [VERIFIED: .planning/ROADMAP.md] |
| Redaction guard only applies to `redacted_payload` | Guard both `redacted_payload` and `resource_refs` | Phase 28 planned [VERIFIED: src/replay/service.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md] | Prevents unsafe refs bypassing payload guard. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |

**Deprecated/outdated:**

- Adding real external action execution events remains out of scope; existing tests assert action execution event families are not registered. [VERIFIED: tests/agent/test_events.py; tests/replay/test_replay_redaction_retention.py]
- Relying on `metrics_json` / `trace_steps` as the only replay source is transitional; new platform decisions should go through the event table. [CITED: docs/contract-spec.md §17.2 and §18.4]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| None | All material implementation claims in this research were verified from repository files, local commands, or cited contract docs. [VERIFIED: command outputs and file inspection] | All | No user confirmation needed for researched facts; planner still owns task sequencing choices. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |

## Open Questions

1. **How far should fail-closed behavior reach in `memory_write` during Phase 28?** [VERIFIED: src/agent/nodes/memory_write.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
   - What we know: D-09 requires identity/source failures to fail closed, while D-10 says not to broadly rewrite all existing writer call sites. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
   - What's unclear: `memory_write._emit_memory_event(...)` currently returns on missing identity and catches all emission exceptions. [VERIFIED: src/agent/nodes/memory_write.py]
   - Recommendation: Plan a focused compatibility test and a narrow change at the wrapper/helper seam; avoid broad memory domain migration. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

2. **Should `RunLifecycleService` store only plural `reason_codes`, or keep singular for backward compatibility plus normalized plural?** [VERIFIED: src/replay/lifecycle.py]
   - What we know: lifecycle currently writes `reason_code`, and Phase 28 requires plural `reason_codes` while allowing legacy singular input. [VERIFIED: src/replay/lifecycle.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
   - What's unclear: Existing tests assert singular `reason_code` in lifecycle payloads. [VERIFIED: tests/replay/test_lifecycle_finalizer.py]
   - Recommendation: Normalize to plural at the event facade and update lifecycle tests to assert plural while preserving legacy input acceptance. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Running locked Python/test environment | yes [VERIFIED: terminal `uv --version`] | 0.11.2 [VERIFIED: terminal `uv --version`] | Use system Python only for non-import shell checks; do not use it for tests because project deps are not installed globally. [VERIFIED: terminal import probe] |
| Python | Project runtime | yes [VERIFIED: terminal `python --version`; `uv run python`] | system 3.13.3; project requires `>=3.12` [VERIFIED: pyproject.toml; terminal] | None needed. [VERIFIED: pyproject.toml] |
| PostgreSQL | Async DB tests and advisory-lock sequence tests | yes [VERIFIED: asyncpg connection probe] | PostgreSQL 16.13 [VERIFIED: asyncpg connection probe] | None needed for local tests. [VERIFIED: tests/conftest.py] |
| `asyncpg` | PostgreSQL test fixture and probe | yes [VERIFIED: `uv run python` import] | 0.31.0 [VERIFIED: `uv run python` import; uv.lock] | None needed. [VERIFIED: tests/conftest.py] |
| Docker CLI | Optional local service management | CLI present [VERIFIED: terminal `docker --version`] | 29.4.2 [VERIFIED: terminal `docker --version`] | PostgreSQL is already reachable without needing Docker during research. [VERIFIED: asyncpg connection probe] |
| `psql` / `pg_isready` | Manual DB shell diagnostics | not found in PATH during probe [VERIFIED: terminal command probe] | n/a | Use asyncpg probe or project pytest fixtures. [VERIFIED: tests/conftest.py] |

**Missing dependencies with no fallback:** None identified for planning. [VERIFIED: environment probes]

**Missing dependencies with fallback:** `psql` / `pg_isready` are unavailable, but asyncpg can connect to local PostgreSQL and tests use asyncpg directly. [VERIFIED: environment probes; tests/conftest.py]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 under `uv run` [VERIFIED: `uv run python` import; uv.lock] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py -q` [VERIFIED: existing pytest layout; proposed new file] |
| Full suite command | `uv run pytest tests/replay tests/agent/test_events.py tests/platform/test_context_projections.py -q` [VERIFIED: existing test files] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| APF-05 | `DecisionEventEnvelopeV1` strictly accepts only §17.2 minimal fields, rejects extras/missing required fields, and validates registered event types. [CITED: docs/contract-spec.md §17.2] | unit | `uv run pytest tests/replay/test_decision_events.py -q` | no, Wave 0 [VERIFIED: `rg --files tests/replay`] |
| APF-05 | `emit_decision_event(...)` persists through `ReplayService.append_event(...)` with `schema_version="minimal_event_envelope.v1"` and returns validated minimal envelope. [VERIFIED: src/replay/service.py] | integration | `uv run pytest tests/replay/test_decision_events.py -q` | no, Wave 0 [VERIFIED: `rg --files tests/replay`] |
| APF-05 | `src.agent.events.emit_event` remains compatible and delegates to replay-owned facade. [VERIFIED: src/agent/events.py] | unit | `uv run pytest tests/agent/test_events.py -q` | yes [VERIFIED: tests/agent/test_events.py] |
| APF-05 | Sequence allocator ordering remains shared across graph, memory, approval, action draft, replay backfill, and lifecycle writers. [VERIFIED: tests/replay/test_sequence_allocator.py] | integration | `uv run pytest tests/replay/test_sequence_allocator.py -q` | yes [VERIFIED: tests/replay/test_sequence_allocator.py] |
| APF-05 | Redaction rejects unsafe keys in both `redacted_payload` and `resource_refs`. [VERIFIED: src/replay/validators.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md] | unit/integration | `uv run pytest tests/replay/test_decision_events.py tests/replay/test_replay_redaction_retention.py -q` | partial, Wave 0 for refs [VERIFIED: tests/replay/test_replay_redaction_retention.py] |
| APF-05 | Reason-code normalization converts `reason_code` to first-seen de-duped `reason_codes` and rejects invalid strings. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] | unit | `uv run pytest tests/replay/test_decision_events.py -q` | no, Wave 0 [VERIFIED: `rg --files tests/replay`] |
| APF-05 | Version metadata lands under `redacted_payload.versions`, not top-level envelope fields. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/platform/context_projections.py] | unit | `uv run pytest tests/replay/test_decision_events.py tests/platform/test_context_projections.py -q` | partial, Wave 0 for event payload [VERIFIED: tests/platform/test_context_projections.py] |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py -q` [VERIFIED: existing test layout; proposed new file]
- **Per wave merge:** `uv run pytest tests/replay tests/agent/test_events.py tests/platform/test_context_projections.py -q` [VERIFIED: existing test layout]
- **Phase gate:** Full targeted suite above plus any updated writer-specific tests touched by the implementation. [VERIFIED: existing writer tests from rg results]

### Wave 0 Gaps

- [ ] `tests/replay/test_decision_events.py` - strict `DecisionEventEnvelopeV1`, emitter, reason/version normalization, resource-ref guard, missing identity, conditional operation id. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md]
- [ ] Extend `tests/agent/test_events.py` - wrapper compatibility and legacy `reason_code` conversion. [VERIFIED: tests/agent/test_events.py]
- [ ] Extend `tests/replay/test_replay_service.py` or new tests - `project_minimal_event(...)` validates through `DecisionEventEnvelopeV1`. [VERIFIED: src/replay/service.py; tests/replay/test_replay_service.py]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct auth feature [VERIFIED: phase scope] | Preserve trusted identity from `TrustedContext`; do not accept user/LLM identity overrides. [CITED: docs/contract-spec.md §8.0; VERIFIED: src/platform/trusted_context.py] |
| V3 Session Management | no direct session feature [VERIFIED: phase scope] | Preserve `thread_id`, `run_id`, and optional `session_id` as trusted context projections only. [CITED: docs/contract-spec.md §8.0; VERIFIED: src/platform/context_projections.py] |
| V4 Access Control | yes, identity/scope provenance matters [CITED: docs/contract-spec.md §8.0] | New emitters should prefer `ReplayContext` from `TrustedContextFactory`; legacy args should fail closed when required identity is missing. [VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md; src/platform/context_projections.py] |
| V5 Input Validation | yes [VERIFIED: phase scope] | Pydantic strict schema, registered event types, reason-code regex, required field validation, and recursive forbidden-key guards. [VERIFIED: src/replay/schemas.py; src/replay/validators.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |
| V6 Cryptography | limited, hashes only [VERIFIED: phase scope] | Do not hand-roll crypto; preserve existing hash/resource-ref strings such as `action_payload_hash` and `safety_snapshot_hash` as refs only. [VERIFIED: src/actions/service.py; src/approvals/events.py] |
| V9 Logging and Monitoring | yes [CITED: docs/contract-spec.md §17.2 and §18.4] | Store audit-safe event metadata only; never persist full prompts, raw tool output, secrets, PII, or raw business payloads. [CITED: docs/contract-spec.md §17.2; VERIFIED: src/replay/validators.py] |

### Known Threat Patterns for Decision Events

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| User/LLM identity spoofing in event records | Spoofing | Source identity from `TrustedContext` / `ReplayContext`; fail closed on missing required identity. [CITED: docs/contract-spec.md §8.0; VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |
| Raw prompt/tool/business data in audit store | Information Disclosure | Recursive guards on `redacted_payload` and `resource_refs`; only typed refs, hashes, ids, and prompt-safe summaries allowed. [CITED: docs/contract-spec.md §17.2; VERIFIED: src/replay/validators.py] |
| Unregistered event types bypassing retention/replay rules | Tampering | Use `REPLAY_EVENT_TYPES` and `validate_event_type(...)` in schema and service. [VERIFIED: src/replay/validators.py; tests/replay/test_replay_service.py] |
| Event ordering collision under concurrent writers | Tampering/Repudiation | Use `ReplayService` advisory lock and unique `(run_id, sequence)` constraint; keep concurrency tests. [VERIFIED: src/replay/service.py; src/db/models.py; tests/replay/test_sequence_allocator.py] |
| Service-specific metadata widening top-level envelope | Tampering/Repudiation | Keep §17.2 top-level fields fixed; put service payload under `redacted_payload` or `resource_refs`. [CITED: docs/contract-spec.md §17.2; VERIFIED: .planning/phases/28-decision-event-foundation/28-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/28-decision-event-foundation/28-CONTEXT.md` - locked user decisions D-01 through D-20, discretion, and deferred scope. [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` - APF-05 requirement. [VERIFIED: file read]
- `.planning/ROADMAP.md` - Phase 28 goal, dependency, success criteria, and plan count. [VERIFIED: file read]
- `.planning/STATE.md` - v1.9 status, sequencing, and Phase 27 completion. [VERIFIED: file read]
- `docs/contract-spec.md` §0.2, §8.0, §17.2, §18.4 - normative ownership, trusted context, minimal envelope, and observability transition rules. [CITED: docs/contract-spec.md]
- `src/replay/service.py` - append path, allocator, minimal projection, V3 projection. [VERIFIED: codebase]
- `src/replay/schemas.py` - strict Pydantic schema pattern. [VERIFIED: codebase]
- `src/replay/validators.py` - event registry, redaction guard, retention classification. [VERIFIED: codebase]
- `src/agent/events.py` - current compatibility wrapper. [VERIFIED: codebase]
- `src/platform/trusted_context.py` and `src/platform/context_projections.py` - trusted context and ReplayContext projection. [VERIFIED: codebase]
- `src/db/models.py` and migrations `006`, `010` - current event table and checks/indexes. [VERIFIED: codebase]
- Existing tests under `tests/agent`, `tests/replay`, and `tests/platform`. [VERIFIED: codebase]

### Secondary (MEDIUM confidence)

- `docs/target-agent-platform-architecture-plan.md` §14 and Phase 28 sequence notes - architecture mirror and decision-event coverage rationale; yields to `contract-spec.md`. [CITED: docs/target-agent-platform-architecture-plan.md]

### Tertiary (LOW confidence)

- None. [VERIFIED: research process]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - versions verified with `uv run python` imports, `pyproject.toml`, and `uv.lock`. [VERIFIED: terminal; pyproject.toml; uv.lock]
- Architecture: HIGH - ownership and envelope constraints are in normative contract docs and matching repository code. [CITED: docs/contract-spec.md; VERIFIED: src/replay/service.py; src/db/models.py]
- Pitfalls: HIGH - risks are visible in current writers/tests and locked decisions. [VERIFIED: src/agent/events.py; src/replay/lifecycle.py; src/agent/nodes/memory_write.py; tests/agent/test_events.py; .planning/phases/28-decision-event-foundation/28-CONTEXT.md]

**Research date:** 2026-06-23 [VERIFIED: system current date]
**Valid until:** 2026-07-23 for this repo-specific research, unless Phase 28 implementation or contract docs change first. [VERIFIED: current git state and phase status]
