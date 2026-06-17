# Phase 13: Approval State Machine - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 43 new/modified file targets
**Analogs found:** 43 / 43, including partial contract-backed analogs where the repo has no exact implementation yet

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/common/__init__.py` | config | request-response | `src/actions/__init__.py` | role-match |
| `src/common/canonical_hash.py` | utility | transform | `src/knowledge/text_hash.py`; `src/agent/intent_manifest.py`; `docs/contract-spec.md` | partial + contract |
| `src/approvals/__init__.py` | config | request-response | `src/actions/__init__.py`; `src/memory/__init__.py` | role-match |
| `src/approvals/schemas.py` | model | request-response | `src/memory/schemas.py`; `src/tools/contracts.py` | role-match |
| `src/approvals/snapshots.py` | service/model | transform + CRUD | `src/knowledge/schemas.py`; `tests/knowledge/test_evidence_projection.py` | exact for evidence projection |
| `src/approvals/policy.py` | service | request-response | `src/api/routers/approvals.py`; `src/api/routers/agent_runs.py` | partial |
| `src/approvals/repository.py` | repository | CRUD + CAS | `src/repositories/approval_repo.py`; `src/memory/repository.py`; `src/repositories/action_draft_repo.py` | role-match |
| `src/approvals/service.py` | service | CRUD + request-response | `src/actions/service.py`; `src/memory/repository.py`; `src/repositories/approval_repo.py` | role-match |
| `src/approvals/events.py` | service/utility | event-driven | `src/agent/events.py`; `tests/agent/test_events.py` | exact envelope analog |
| `src/approvals/sla_scanner.py` | service | batch + event-driven | `src/config.py`; `src/agent/events.py`; `src/memory/service.py` | partial |
| `src/repositories/approval_repo.py` | repository shim/deletion | CRUD | `tests/architecture/test_tool_boundaries.py`; `src/actions/service.py` compatibility function | role-match |
| `src/db/models.py` | model | CRUD + event-driven | existing `ApprovalRequest`, `ApprovalStep`, `ActionDraft`, `AgentTraceEvent` | exact legacy base |
| `src/db/migrations/versions/008_approval_state_machine.py` | migration | CRUD | `005_approval_tables.py`; `006_agent_trace_events.py`; `007_session_memories.py` | exact migration style |
| `src/api/schemas/approvals.py` | model | request-response | `src/api/schemas/approvals.py`; `src/memory/schemas.py`; `src/tools/contracts.py` | exact legacy + role-match |
| `src/api/routers/approvals.py` | controller | request-response | same file current route; `src/api/routers/agent_runs.py` auth/claim patterns | exact cutover target |
| `src/api/routers/agent.py` | controller | request-response | same file `_handle_interrupt`; `src/api/routers/agent_runs.py` stream interrupt path | exact cutover target |
| `src/api/routers/agent_runs.py` | controller | streaming + request-response | same file `_handle_approval_required`, `_claim_pending_run_for_stream` | exact cutover target |
| `src/agent/state.py` | model | event-driven | current approval fields and EvidenceRef typed projection | exact |
| `src/agent/graph.py` | route | event-driven | current `route_after_risk` / `route_after_approval` | exact |
| `src/agent/routing.py` | route | request-response | approval-chat-not-trusted fail-closed routing | exact |
| `src/agent/nodes/assess_risk_and_approval.py` | service/node | transform | current proposed action/risk producer | exact |
| `src/agent/nodes/approval_gate.py` | service/node | event-driven | current LangGraph interrupt node | exact |
| `src/agent/nodes/execute_action.py` | service/node | request-response | current action guard and tool context handoff | partial |
| `src/agent/events.py` | utility/service | event-driven | same file minimal envelope registry/emitter | exact |
| `src/config.py` | config | request-response | existing settings fields and memory feature toggle | exact |
| `.env.example` | config | request-response | existing env var listing | exact |
| `tests/approvals/test_canonical_hash.py` | test | transform | `tests/knowledge/test_text_hash.py`; `tests/knowledge/test_evidence_projection.py` | role-match |
| `tests/approvals/test_snapshots.py` | test | transform + CRUD | `tests/knowledge/test_evidence_projection.py`; `tests/memory/test_session_memory_repository.py` | role-match |
| `tests/approvals/test_service_transitions.py` | test | CRUD + CAS | `tests/test_approval_models.py`; `tests/memory/test_session_memory_repository.py` | role-match |
| `tests/approvals/test_needs_info_resume.py` | test | request-response | `tests/agent/test_clarification_gate.py`; `tests/test_approval_api.py` | role-match |
| `tests/approvals/test_multi_level_contract.py` | test | CRUD + CAS | `tests/test_approval_models.py`; `docs/contract-spec.md` Section 18.2 | partial + contract |
| `tests/approvals/test_sla_scanner.py` | test | batch + event-driven | `tests/agent/test_events.py`; memory disabled tests | partial |
| `tests/approvals/test_hash_binding.py` | test | transform + CRUD | `tests/knowledge/test_evidence_projection.py`; `tests/test_execute_action.py` | role-match |
| `tests/approvals/test_events.py` | test | event-driven | `tests/agent/test_events.py` | exact |
| `tests/approvals/test_migration_contract.py` | test | CRUD | `tests/memory/test_session_memory_repository.py`; Alembic migration files | role-match |
| `tests/architecture/test_approval_boundaries.py` | test | transform/static | `tests/architecture/test_tool_boundaries.py` | exact |
| `tests/test_approval_api.py` | test | request-response | existing approval API tests | exact rewrite target |
| `tests/test_approval_integration.py` | test | request-response + CRUD | existing approval integration tests | exact rewrite target |
| `tests/test_approval_models.py` | test | CRUD | existing approval model tests | exact rewrite target |
| `tests/test_approval_gate.py` | test | event-driven | existing approval gate tests | exact rewrite target |
| `tests/test_graph_routing.py` | test | event-driven | existing route-after-approval tests | exact |
| `tests/test_execute_action.py` | test | request-response | existing execute action guard tests | exact |
| `tests/agent/test_events.py` | test | event-driven | same file memory event additions and redaction tests | exact |

## Pattern Assignments

### `src/common/canonical_hash.py` and `tests/approvals/test_canonical_hash.py` (utility/test, transform)

**Analogs:** `src/knowledge/text_hash.py`, `src/agent/intent_manifest.py`, `tests/knowledge/test_text_hash.py`, `tests/knowledge/test_evidence_projection.py`, `docs/contract-spec.md`.

**Imports/hash output pattern** (`src/knowledge/text_hash.py` lines 3-19):

```python
import hashlib
import unicodedata

EVIDENCE_TEXT_HASH_VERSION = "evidence_text_hash.v1"

def evidence_text_hash(text: str) -> str:
    """Return sha256:<lowercase hex> of the normalized UTF-8 bytes."""
    digest = hashlib.sha256(normalize_evidence_text(text).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
```

**Do not copy default JSON serialization as-is.** `src/agent/intent_manifest.py` lines 126-129 show the local hash style, but Phase 13 must replace this with the stricter contract serializer:

```python
def compute_dataset_hash(path: Path) -> str:
    data = json.loads(path.read_text())
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
```

**Contract rules to implement** (`docs/contract-spec.md` lines 1451-1461):

```text
CanonicalHashProfile v1:
- output: sha256:<lowercase hex>
- input bytes: hash_profile.v1\n<schema_version>\n<canonical_json>
- object keys sorted by Unicode code point
- no insignificant whitespace
- no bare JSON float in hashable contracts
- explicit nullable fields unless schema says omit_when_absent
- fixed-millisecond UTC datetimes
- EvidenceRefV1[] uses rank-aware sorting and strips score
```

**Golden test pattern** (`tests/knowledge/test_text_hash.py` lines 27-31):

```python
def test_hash_output_format_and_frozen_golden_literal():
    result = evidence_text_hash("...")

    assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)
    assert result == "sha256:14da429414366e3cf6996d34022943fe381b4901065dc785fdc66107402a1427"
```

**Frozen bytes assertion pattern** (`tests/knowledge/test_evidence_projection.py` lines 73-89):

```python
golden_bytes = json.dumps(
    canonical_evidence_projection(refs),
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
).encode()

assert golden_bytes == (
    b'[{"chunk_id":"chunk-a","doc_key":"policy-a",...}]'
)
```

**Spec golden sample to reproduce exactly** (`docs/contract-spec.md` lines 1477-1485):

```text
canonical_json={...proposed_action.v1...}
hash_input=hash_profile.v1\nproposed_action.v1\n{...same canonical_json...}
expected_sha256=sha256:508e649e1b169a9520f7eb76403b0e00c90c1b1c52e17a499fd7bcdce2473094
```

Planner note: `src/common/` does not exist yet. Add `src/common/__init__.py` and keep imports one-way: domain packages import `src.common.canonical_hash`, not the reverse.

---

### `src/approvals/schemas.py` and `src/api/schemas/approvals.py` (model, request-response)

**Analogs:** `src/memory/schemas.py`, `src/tools/contracts.py`, existing `src/api/schemas/approvals.py`.

**Pydantic strict schema pattern** (`src/memory/schemas.py` lines 10-20 and 48-75):

```python
class SessionSlotV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    source: Literal["explicit_user", "system_derived"]
    source_run_id: str
    updated_at: datetime
    expires_at: datetime
    compatible_intents: list[str]

class SessionMemoryWriteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    thread_id: str
    run_id: uuid.UUID
    expected_version: int | None = None
```

**Shared graph-facing contract pattern** (`src/tools/contracts.py` lines 13-36):

```python
class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_context.v2"] = "tool_context.v2"
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    thread_id: str
    run_id: str
    idempotency_key: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None
    policy_snapshot_ref: str | None = None
```

**Current approval schema to replace** (`src/api/schemas/approvals.py` lines 9-11):

```python
class DecideRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    reason: str | None = None
```

Target shape: `ApprovalDecisionCommand` belongs in `src/approvals/schemas.py`; API body schemas can accept client fields but must not let the client set `tenant_id`, `actor_id`, trusted marker, expected versions from auth context, or resume payload. Use `Literal["accept", "approve", "edit", "respond", "reject", "ignore"]` plus expected request/level/assignment versions and revision fields.

---

### `src/approvals/snapshots.py` and `tests/approvals/test_snapshots.py` (service/model, transform + CRUD)

**Analogs:** `src/knowledge/schemas.py`, `tests/knowledge/test_evidence_projection.py`, `docs/contract-spec.md`.

**Evidence schema to import, not duplicate** (`src/knowledge/schemas.py` lines 31-69):

```python
class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
    score: float | None = None
    rank: int | None = Field(default=None, ge=1)
```

**Canonical evidence projection to reuse** (`src/knowledge/schemas.py` lines 120-133):

```python
def canonical_evidence_projection(refs: list[EvidenceRefV1]) -> list[dict]:
    """Strip score and deterministically sort the producer-side hash projection."""
    items = []
    for ref in refs:
        item = ref.model_dump()
        item.pop("score", None)
        items.append(item)

    all_ranked = all(item.get("rank") is not None for item in items) and len(items) > 0
    if all_ranked:
        items.sort(key=lambda item: (item["rank"], item["evidence_id"], item["text_hash"]))
    else:
        items.sort(key=lambda item: (item["evidence_id"], item["text_hash"]))
    return items
```

**Tests to copy for score stripping and rank sort** (`tests/knowledge/test_evidence_projection.py` lines 16-27):

```python
projected = canonical_evidence_projection(refs)

assert all("score" not in item for item in projected)
assert [item["rank"] for item in projected] == [1, 2, 3]
```

**Snapshot contract fields** (`docs/contract-spec.md` lines 1405-1447):

```text
ActionSafetySnapshot:
- schema_version: action_safety_snapshot.v1
- tenant_id, run_id, snapshot_id, snapshot_ref
- policy_config_version, risk_config_version, retrieval_config_version
- evidence_ids and evidence: EvidenceRefV1[]
- action_payload_hash
- immutable_hash
- lifecycle fields archived_at, retention_until, deleted_at
```

Planner note: builder must compute `action_payload_hash` before snapshot hash, persist through `action_safety_snapshots`, and reject raw action payload/prompt/tool output in snapshot JSON.

---

### `src/approvals/policy.py` (service, request-response)

**Analogs:** role/self-approval code in `src/api/routers/approvals.py`; role visibility in `src/api/routers/agent_runs.py`; contract self-approval rules.

**Current role/self-approval/expiry logic to move out of router** (`src/api/routers/approvals.py` lines 22-52):

```python
APPROVAL_ROLES = {"admin", "manager"}

if user.role not in APPROVAL_ROLES:
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", ...})

if approval.requested_by == user.id:
    raise HTTPException(status_code=403, detail={"code": "SELF_APPROVAL", ...})

if approval.expires_at < datetime.now(UTC):
    await repo.mark_expired(approval.id, user.tenant_id)
    await repo.add_step(approval.id, event_type="expired")
```

**Existing supervisor visibility pattern** (`src/api/routers/agent_runs.py` lines 36 and 574-578):

```python
SUPERVISOR_ROLES = {"supervisor", "admin", "approval_manager", "manager"}

if run.user_id != user.id and user.role not in SUPERVISOR_ROLES:
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
```

**Target policy responsibilities:** role/assignment resolution, self-approval block, default single-level assignment, SLA due time calculation, and "feature-disabled scanner" policy. Keep hard-coded role sets as compatibility inputs only.

---

### `src/approvals/repository.py` and `src/repositories/approval_repo.py` (repository, CRUD + CAS)

**Analogs:** current `ApprovalRepository`, `SessionMemoryRepository.cas_update`, `ActionDraftRepository.create_or_get`.

**Session-owned repository style** (`src/repositories/approval_repo.py` lines 13-15):

```python
class ApprovalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
```

**Tenant-scoped lookup and row lock pattern** (`src/repositories/approval_repo.py` lines 46-62):

```python
async def get_by_id_for_update(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
    stmt = (
        select(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    return (await self.session.execute(stmt)).scalar_one_or_none()
```

**Current transition API is obsolete** (`src/repositories/approval_repo.py` lines 76-109):

```python
async def decide(...):
    if decision not in {"approve", "reject"}:
        raise ValueError("invalid_decision")
    approval = await self.get_by_id_for_update(approval_id, tenant_id)
    ...
    approval.status = "approved" if decision == "approve" else "rejected"
    approval.decision = decision
    approval.decided_by = decided_by
    await self.session.flush()
    return approval, True
```

Do not keep this as a public transition path. New repository methods should be lower-level helpers called only by `ApprovalService`.

**CAS update pattern to copy** (`src/memory/repository.py` lines 110-124):

```python
async def cas_update(self, memory_id: uuid.UUID, expected_version: int, values: dict[str, Any]) -> bool:
    update_values = dict(values)
    update_values["version"] = SessionMemory.version + 1
    update_values["updated_at"] = func.now()
    result = await self.session.execute(
        update(SessionMemory)
        .where(
            SessionMemory.id == memory_id,
            SessionMemory.version == expected_version,
            SessionMemory.deleted_at.is_(None),
        )
        .values(**update_values)
    )
    await self.session.flush()
    return result.rowcount == 1
```

**Idempotent create-or-get pattern** (`src/repositories/action_draft_repo.py` lines 16-45):

```python
stmt = select(ActionDraft).where(ActionDraft.idempotency_key == idempotency_key)
existing = (await self.session.execute(stmt)).scalar_one_or_none()
if existing:
    if existing.tenant_id != tenant_id:
        raise ValueError("idempotency_key_conflict")
    return existing, False

self.session.add(draft)
await self.session.flush()
return draft, True
```

---

### `src/approvals/service.py` (service, CRUD + request-response)

**Analogs:** `src/actions/service.py`, `src/memory/repository.py`, current approval router responsibilities.

**Service owns durable operation and nested transaction** (`src/actions/service.py` lines 25-79):

```python
class ActionService:
    """Business owner for durable action draft creation."""

    def __init__(self, session: AsyncSession, *, draft_store: ActionDraftStore | None = None) -> None:
        self.session = session
        self.draft_store = draft_store or ActionDraftStore(session)

    async def create_coupon_grant_draft(...):
        try:
            async with self.session.begin_nested():
                draft, created = await self.draft_store.create_or_get(...)
            return _tool_success({...})
        except ValueError as exc:
            if str(exc) == _IDEMPOTENCY_CONFLICT:
                return _tool_error("IDEMPOTENCY_CONFLICT", ..., retryable=False)
            return _tool_error("INVALID_REQUEST", ..., retryable=False)
        except Exception:
            return _tool_error("DRAFT_CREATION_FAILED", ..., retryable=True)
```

**Target transition order from contract** (`docs/contract-spec.md` lines 2274-2290):

```text
lock/CAS request -> current level -> assignment -> insert decision/event
Required mismatch tests:
- wrong assignment-level
- wrong level-request
- tenant/run/revision/version mismatch
- any mismatch rolls back
```

Planner note: `ApprovalService.decide(command)` should return a typed `ApprovalDecisionResult`; routers may wrap a service-produced `resume_payload` in `Command(resume=...)` but must not assemble resume dicts.

---

### `src/approvals/events.py` and `src/agent/events.py` (service/utility, event-driven)

**Analogs:** `src/agent/events.py`, `tests/agent/test_events.py`, `docs/contract-spec.md`.

**Event registry to extend** (`src/agent/events.py` lines 15-37):

```python
MINIMAL_EVENT_TYPES = {
    "node_started",
    "node_completed",
    "node_failed",
    "run_status_changed",
    "tool_call_started",
    "tool_call_completed",
    "tool_call_failed",
    "rag_retrieval_started",
    "rag_retrieval_completed",
    "rag_retrieval_failed",
    "llm_call_started",
    "llm_call_completed",
    "llm_call_failed",
    "memory_write_started",
    "memory_write_completed",
    "memory_write_failed",
}
EVENT_RETENTION_CLASSIFICATION = {event_type: "minimal_event" for event_type in MINIMAL_EVENT_TYPES}
FORBIDDEN_REDACTED_PAYLOAD_KEYS = {"data", "raw", "arguments", "prompt"}
```

**Allocator and emit shape** (`src/agent/events.py` lines 49-118):

```python
await session.execute(
    sa.text("SELECT pg_advisory_xact_lock(hashtext(:run_id_text))"),
    {"run_id_text": str(run_uuid)},
)
...
envelope = {
    "schema_version": SCHEMA_VERSION,
    "event_id": event_id,
    "sequence": sequence,
    "operation_id": operation_uuid,
    "run_id": run_uuid,
    "tenant_id": tenant_uuid,
    "thread_id": thread_id,
    "trace_id": trace_id,
    "event_type": event_type,
    "occurred_at": occurred_at,
    "actor": actor,
    "resource_refs": resource_refs,
    "redaction_policy_version": redaction_policy_version,
    "redacted_payload": safe_payload,
}
session.add(AgentTraceEvent(**envelope))
await session.flush()
```

**Redaction guard** (`src/agent/events.py` lines 121-133):

```python
def _guard_redacted_payload(redacted_payload: dict[str, Any]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_REDACTED_PAYLOAD_KEYS:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")
```

**Event tests to extend** (`tests/agent/test_events.py` lines 136-140 and 189-224):

```python
def test_memory_write_event_types_and_retention_are_registered():
    assert {"memory_write_started", "memory_write_completed", "memory_write_failed"} <= MINIMAL_EVENT_TYPES
    assert EVENT_RETENTION_CLASSIFICATION["memory_write_started"] == "minimal_event"

with pytest.raises(ValueError):
    await _emit(session, redacted_payload={"data": {"raw": "tool output"}})
```

**Approval additions from contract** (`docs/contract-spec.md` lines 1760-1774, 1850-1855):

```text
Phase 13 owns: approval_requested, approval_decided, approval_expired, approval_resumed.
approval_decided redacted payload / resource refs must distinguish
accept|approve|edit|respond|reject|ignore and carry old/new revision refs for edit/respond or hash/config changes.
```

---

### `src/approvals/sla_scanner.py`, `src/config.py`, and `.env.example` (service/config, batch + event-driven)

**Analogs:** settings in `src/config.py`, disabled feature pattern in memory, event emitter.

**Settings pattern** (`src/config.py` lines 7-19 and 31-35):

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca"
    redis_url: str = "redis://localhost:6379/0"
    enable_demo_auth: bool = True
    database_echo: bool = False
    session_memory_enabled: bool = True
    session_memory_ttl_seconds: int = 1800
```

**Env example pattern** (`.env.example` lines 1-5):

```text
DATABASE_URL=postgresql+asyncpg://moca:moca_dev@localhost:5432/moca
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=dev-secret-change-in-prod-32-bytes-min
JWT_EXPIRE_MINUTES=60
ENABLE_DEMO_AUTH=true
```

Target: add a disabled-by-default approval SLA scanner flag, e.g. `approval_sla_scanner_enabled: bool = False`, and document `APPROVAL_SLA_SCANNER_ENABLED=false`. Scanner tests should assert disabled no-op plus event-shape functions without enabling scheduling.

---

### `src/db/models.py` and `008_approval_state_machine.py` (model/migration, CRUD + event-driven)

**Analogs:** current approval/action/event ORM models and migrations `005`, `006`, `007`.

**Existing approval/action ORM baseline** (`src/db/models.py` lines 279-343):

```python
class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    proposed_action: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ...

class ActionDraft(TimestampMixin, Base):
    __tablename__ = "action_drafts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_action_drafts_idempotency_key"),)
```

**Minimal event ORM style** (`src/db/models.py` lines 378-403):

```python
class AgentTraceEvent(TimestampMixin, Base):
    __tablename__ = "agent_trace_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),)

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(nullable=False)
    actor: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resource_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    redacted_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
```

**Create table/index migration style** (`src/db/migrations/versions/005_approval_tables.py` lines 23-47):

```python
def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        ...
    )
    op.create_index("ix_approval_requests_run_id", "approval_requests", ["run_id"])
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
```

**Event table migration style** (`src/db/migrations/versions/006_agent_trace_events.py` lines 23-51):

```python
op.create_table(
    "agent_trace_events",
    sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
    sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
    sa.Column("sequence", sa.Integer(), nullable=False),
    ...
    sa.UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),
)
```

**Partial unique index pattern** (`src/db/migrations/versions/007_session_memories.py` lines 68-74):

```python
op.create_index(
    "uq_session_memories_active_scope",
    "session_memories",
    ["tenant_id", "user_id", "thread_id"],
    unique=True,
    postgresql_where=sa.text("deleted_at IS NULL"),
)
```

**Target table contract** (`docs/contract-spec.md` lines 2145-2290): create/extend `action_safety_snapshots`, `approval_requests`, `approval_levels`, `approval_assignments`, `approval_decisions`, and `approval_events`; include unique `(tenant_id, immutable_hash)`, unique `(tenant_id, run_id, revision)`, unique `(approval_request_id, level)`, active revision/decision partial uniques, nullable `approval_events.replay_event_id`, and explicit check constraints for statuses/decision types.

---

### `src/api/routers/approvals.py` (controller, request-response)

**Analogs:** same file current endpoint shape, `src/api/schemas/common.py`, approval API tests.

**FastAPI dependency/auth pattern** (`src/api/routers/approvals.py` lines 25-32):

```python
@router.post("/{approval_id}/decide", response_model=ApiResponse)
async def decide_approval(
    approval_id: str,
    body: DecideRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
```

**Response envelope pattern** (`src/api/schemas/common.py` lines 17-27):

```python
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: ErrorDetail | None = None
    trace_id: str | None = None
```

**Current anti-pattern to remove from router** (`src/api/routers/approvals.py` lines 54-81):

```python
updated, transitioned = await repo.decide(...)
...
resume_payload = {
    "run_id": str(approval.run_id),
    "approval_id": str(approval.id),
    "decision": body.decision,
    "reason": body.reason,
    "decided_by": str(user.id),
    "decided_at": datetime.now(UTC).isoformat(),
}
final_state = await graph.ainvoke(Command(resume=resume_payload), config)
```

Target: router parses, authenticates, builds server-side `ApprovalDecisionCommand`, calls `ApprovalService`, maps domain exceptions to `HTTPException`, and resumes graph only with `result.resume_payload`.

**API test pattern to rewrite** (`tests/test_approval_api.py` lines 126-152):

```python
response = await client.post(
    f"/api/v1/approvals/{approval.id}/decide",
    json={"decision": "approve", "reason": "valid"},
    headers=await _admin_headers(client),
)
payload = response.json()

assert response.status_code == 200
assert payload["success"] is True
assert payload["data"]["status"] == "approved"
```

Keep test style; change assertions from router-built `Command.resume` to service-produced trusted resume payload, expected versions, hash refs, and `accept|approve|edit|respond|reject|ignore`.

---

### `src/api/routers/agent.py` and `src/api/routers/agent_runs.py` (controller, request-response + streaming)

**Analogs:** current interrupt handlers and SSE helpers.

**Trusted tool config injection pattern** (`src/api/routers/agent_runs.py` lines 58-74):

```python
def _trusted_tool_config(user: User, token_scopes: Iterable[str], trace_id: str | None) -> dict[str, Any]:
    trusted_scopes = set(token_scopes) & set(ROLE_SCOPES.get(user.role, []))
    permissions = [
        tool_permission
        for scope, tool_permission in SCOPE_TO_TOOL_PERMISSION.items()
        if scope in trusted_scopes
    ]
    return {"permissions": permissions, "merchant_scope": merchant_scope, "trace_id": trace_id or ""}
```

**Current chat interrupt creation to replace** (`src/api/routers/agent.py` lines 239-253):

```python
approval_repo = ApprovalRepository(session)
expires_at = _parse_expires_at(interrupt_data.get("expires_at"))
approval = await approval_repo.create(
    run_id=UUID(run_id),
    tenant_id=user.tenant_id,
    requested_by=user.id,
    proposed_action=interrupt_data.get("proposed_action") or {},
    risk_level=interrupt_data.get("risk_level") or "high",
    ...
)
await approval_repo.add_step(approval.id, event_type="created", actor_id=user.id)
```

**Current SSE interrupt creation to replace** (`src/api/routers/agent_runs.py` lines 359-407):

```python
interrupt_data = _extract_interrupt_data(exc_or_data)
persisted_steps = _with_approval_gate_step(trace_steps, completed_at)
approval_repo = ApprovalRepository(session)
approval = await approval_repo.create(
    run_id=run.id,
    tenant_id=user.tenant_id,
    requested_by=user.id,
    proposed_action=interrupt_data.get("proposed_action") or {},
    risk_level=interrupt_data.get("risk_level") or "high",
    ...
)
yield _sse_event(
    event_type="approval_required",
    run_id=str(run.id),
    status="waiting_approval",
    payload={"approval_id": str(approval.id), "proposed_action": ..., "risk_level": ...},
)
```

Target: both paths call `ApprovalService.create_request(...)` with typed server/auth context and graph interrupt data. SSE payload should include service-produced approval wait data with refs/hashes/versions, not raw proposed action as authority.

**SSE event shape pattern** (`src/api/routers/agent_runs.py` lines 471-491):

```python
data = {
    "event_type": event_type,
    "run_id": run_id,
    "step_index": step_index,
    "node_name": node_name,
    "status": status,
    "message": message,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "payload": payload,
}
return {"data": json.dumps(data, ensure_ascii=False)}
```

---

### `src/agent/nodes/assess_risk_and_approval.py` (service/node, transform)

**Analog:** current risk/proposed-action producer.

**Current proposed action builder** (`src/agent/nodes/assess_risk_and_approval.py` lines 156-166):

```python
def _build_proposed_action(draft: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
    refund_case = context.get("refund_case") or {}
    order = context.get("order") or {}
    amount = _extract_compensation_amount(draft, context)
    return {
        "action_type": _canonical_action_type(draft.get("recommended_action")),
        "target_id": str(refund_case.get("id") or order.get("id") or ""),
        "amount": str(amount) if amount is not None else "",
        "currency": "CNY",
        "reasoning_summary": str(draft.get("reasoning_summary") or ""),
    }
```

**Current risk path** (`src/agent/nodes/assess_risk_and_approval.py` lines 196-273): this node builds `risk_assessment` and `proposed_action`; Phase 13 should add canonical `proposed_action.v1`, `action_payload_hash`, and snapshot creation behind approval-domain helpers here or immediately after this boundary.

Target: this node should not own approval persistence or decisions. It may call `src.approvals.snapshots`/hash helpers to attach hashes/refs before routing, if planner chooses that integration point.

---

### `src/agent/nodes/approval_gate.py`, `src/agent/graph.py`, and `src/agent/state.py` (node/route/model, event-driven)

**Analogs:** current interrupt node and routing.

**Current interrupt mechanics to keep, truth fields to remove** (`src/agent/nodes/approval_gate.py` lines 26-47):

```python
async def approval_gate(state: AgentState) -> dict:
    """Interrupt graph execution until a human approval decision resumes it."""
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action") or {}

    interrupt_payload = {
        "run_id": state.get("current_run_id"),
        "tenant_id": state.get("tenant_id"),
        "user_id": state.get("user_id"),
        "proposed_action": proposed,
        "risk_level": risk.get("risk_level"),
        "risk_reason": risk.get("risk_reason"),
        "risk_rule_ref": risk.get("rule_ref"),
        "expires_at": ...,
    }
    decision = interrupt(interrupt_payload)
    return {"approval_result": decision, ...}
```

Target: show service-generated wait payload, interrupt/resume only. Do not compute hashes, create rows, decide status, or trust arbitrary resumed dicts as authorization.

**Current graph routes** (`src/agent/graph.py` lines 39-55 and 118-127):

```python
def route_after_risk(state: AgentState) -> str:
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if risk.get("approval_required"):
        return "approval_gate"
    if proposed:
        return "execute_action"
    return "final_response"

def route_after_approval(state: AgentState) -> str:
    result = state.get("approval_result") or {}
    if result.get("decision") == "approve":
        return "execute_action"
    return "final_response"
```

Update `route_after_approval` to branch on trusted `approval_result.v1` service outcome: only approved exact hash match routes to action; `respond` / `needs_info` and `edit` must not route to old action.

**State fields to extend** (`src/agent/state.py` lines 93-96):

```python
# Phase 4: approval workflow fields.
proposed_action: dict[str, Any] | None
approval_result: dict[str, Any] | None
action_result: dict[str, Any] | None
```

Add approval revision refs/hash/snapshot refs as explicit ephemeral fields; reset them in `receive_request`.

---

### `src/agent/routing.py`, `classify_intent.py`, and clarification tests (route/trust boundary)

**Analogs:** existing fail-closed ordinary-chat approval handling.

**Forbidden LLM state writes** (`src/agent/nodes/classify_intent.py` lines 63-76):

```python
FORBIDDEN_STATE_WRITES = {
    "approval_result",
    "approval_revision_refs",
    "trusted_approval_result",
    "resume",
    "command",
    ...
    "proposed_action",
}
```

**Fail-closed route for approval chat** (`src/agent/routing.py` lines 91-100):

```python
if requested_operation == "approval_decision":
    return "clarification_gate"
if routing_hints.get("pre_route_disposition") == "approval_chat_not_trusted":
    return "clarification_gate"
if routing_hints.get("clarification_reason") == "approval_chat_not_trusted":
    return "clarification_gate"
```

**Contaminated state test pattern** (`tests/agent/test_clarification_gate.py` lines 67-89):

```python
result = await clarification_gate(
    {
        **base_state,
        "routing_hints": {"clarification_reason": "approval_chat_not_trusted"},
        "approval_result": {"decision": "approve"},
        "approval_revision_refs": {"revision": 2},
        "trusted_approval_result": {"decision": "approve"},
        "resume": {"decision": "approve"},
    },
    {},
)

assert "approval_result" not in result
assert "trusted_approval_result" not in str(request)
assert "resume" not in result
```

Copy this style for Phase 13 tests proving ordinary chat/LLM/client JSON cannot manufacture `approval_result.v1` or trusted resume markers.

---

### `src/agent/nodes/execute_action.py` and `tests/test_execute_action.py` (node/test, request-response)

**Analogs:** current approval guard and tool context handoff.

**Current guard and handoff** (`src/agent/nodes/execute_action.py` lines 74-128):

```python
approval = state.get("approval_result") or {}
risk = state.get("risk_assessment") or {}

if risk.get("approval_required") and approval.get("decision") != "approve":
    return {
        "action_result": {
            "status": "error",
            "error": {"error_code": "NOT_APPROVED", ...},
        },
        ...
    }

tool_ctx = ToolCallContext(
    tenant_id=state.get("tenant_id", ""),
    user_id=state.get("user_id", ""),
    run_id=run_id,
    idempotency_key=idempotency_key,
    approval_ref=approval.get("approval_id"),
    safety_snapshot_ref=(risk.get("safety_snapshot_ref") or risk.get("snapshot_ref")),
    policy_snapshot_ref=None,
)
```

**Guard tests to extend** (`tests/test_execute_action.py` lines 57-68 and 137-149):

```python
state["approval_result"] = {"approval_id": str(uuid4()), "decision": "reject"}
result = await execute_action_module.execute_action(state, {"configurable": {"session": object()}})

assert result["action_result"]["status"] == "error"
assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
create_draft.assert_not_awaited()
```

Target: add exact `action_payload_hash + safety_snapshot_hash` validation before invoking the action tool. Keep full `action_draft.v2` completion out of Phase 13 unless the plan explicitly scopes it as a minimal handoff field addition.

---

### `tests/approvals/*` and legacy approval tests (tests, CRUD/request-response/event-driven)

**Analogs:** current approval tests, DB fixtures, event tests, memory CAS tests.

**DB-backed fixture pattern** (`tests/conftest.py` lines 65-84):

```python
@pytest.fixture
async def test_engine():
    await _ensure_test_database(TEST_DATABASE_URL)
    engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
```

**Seeded tenant/user/run style** (`tests/conftest.py` lines 87-230): reuse `seeded_session` for tenant isolation/self-approval tests.

**CAS test pattern** (`tests/memory/test_session_memory_repository.py` lines 68-94):

```python
updated = await repository.cas_update(memory.id, expected_version=1, values={...})
await session.refresh(memory)
stale = await repository.cas_update(memory.id, expected_version=1, values={...})

assert updated is True
assert memory.version == 2
assert stale is False
```

**Existing v1 approval matrix to replace with service transition matrix** (`tests/test_approval_models.py` lines 61-110):

```python
@pytest.mark.parametrize(
    ("initial_status", "decision", "expected_status", "expected_error"),
    [
        ("pending", "approve", "approved", None),
        ("pending", "reject", "rejected", None),
        ("approved", "approve", "approved", None),
        ("approved", "reject", None, "conflict"),
    ],
)
async def test_approval_decide_idempotency_matrix(...):
    ...
```

Replace with Phase 13 cases: stale request version, stale level version, stale assignment version, stale revision, wrong tenant, self-approval, wrong assignment-level/request binding, expired request, hash mismatch, and CAS rollback leaves no orphan decision/event.

**Integration flow pattern to rewrite** (`tests/test_approval_integration.py` lines 20-75):

```python
chat_response = await client.post("/api/v1/agent/chat", ...)
approval_id = UUID(chat_payload["data"]["approval_id"])
...
decision_response = await client.post(
    f"/api/v1/approvals/{approval_id}/decide",
    json={"decision": "approve", "reason": "Within policy"},
    headers=await auth_headers(approval_test_user.username),
)
...
assert pending_approval.status == "approved"
assert interrupted_run.final_status == "completed"
```

Keep the flow shape but add request/level/assignment versions, revision refs, `action_payload_hash`, `safety_snapshot_hash`, and event assertions.

---

### `tests/architecture/test_approval_boundaries.py` (test, static transform)

**Analog:** `tests/architecture/test_tool_boundaries.py`.

**AST import scanner helpers** (`tests/architecture/test_tool_boundaries.py` lines 10-30):

```python
def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports
```

**Forbidden import assertion pattern** (`tests/architecture/test_tool_boundaries.py` lines 65-90):

```python
violations: list[tuple[str, str]] = []
for base in (ROOT / "src", ROOT / "tests", ROOT / "scripts"):
    for path in sorted(base.glob("**/*.py")):
        if path == Path(__file__):
            continue
        for module in _imports(path):
            if module in forbidden:
                violations.append((str(path.relative_to(ROOT)), module))

assert violations == []
```

**Domain package boundary pattern** (`tests/architecture/test_tool_boundaries.py` lines 146-154):

```python
for package in ("actions", "business", "knowledge", "memory"):
    for path in sorted((ROOT / "src" / package).glob("**/*.py")):
        for module in _imports(path):
            if module.startswith(("src.agent.nodes", "src.tools.manager")):
                violations.append((str(path.relative_to(ROOT)), module))
```

Target approval boundary tests:
- routers and agent run routers do not import `src.repositories.approval_repo` for transitions
- only `src.approvals.service` calls package-owned transition repository helpers
- `src/approvals` does not import graph nodes, raw business/action adapters, or `src.tools.manager`
- graph nodes do not import raw external/action/business adapters for approval decisions

## Shared Patterns

### Auth And API Envelopes

**Source:** `src/api/routers/approvals.py` lines 25-32; `src/api/schemas/common.py` lines 17-27.
**Apply to:** approval HTTP endpoints, agent chat interrupt handling, agent run SSE approval handling.

Use FastAPI `Depends(get_session)` and `Security(get_current_user, scopes=[...])`; return `ApiResponse`; map domain failures to stable `HTTPException.detail.code`.

### Strict Pydantic Contracts

**Source:** `src/memory/schemas.py` lines 10-20; `src/tools/contracts.py` lines 13-36.
**Apply to:** `ApprovalDecisionCommand`, `ApprovalDecisionResult`, `ActionSafetySnapshot`, approval event helper payloads.

Use `model_config = ConfigDict(extra="forbid")`, `Literal[...]` schema versions and enums, UUID-typed server-side fields for commands, and explicit nullable fields where the hash contract requires them.

### Repository And CAS

**Source:** `src/repositories/approval_repo.py` lines 46-62; `src/memory/repository.py` lines 110-124.
**Apply to:** approval request/level/assignment version checks, snapshot insert lookup, decision/event insert transaction.

Repository helpers should be session-owned and tenant-scoped. Transition helpers should return booleans/rows that let `ApprovalService` detect stale versions and roll back before inserting decisions/events.

### Event Envelope And Redaction

**Source:** `src/agent/events.py` lines 17-37, 49-118, 121-133.
**Apply to:** `approval_requested`, `approval_decided`, `approval_expired`, `approval_resumed`, SLA scanner dry-run/event-shape tests.

Register event types before emitting. Actor/resource refs must use IDs/hashes/versions only. Extend forbidden redacted keys beyond `data/raw/arguments/prompt` for approval tests: raw action payload, tool output, secrets, credentials, and PII-heavy text.

### Migration Style

**Source:** `005_approval_tables.py`, `006_agent_trace_events.py`, `007_session_memories.py`.
**Apply to:** `008_approval_state_machine.py`.

Use Alembic `op.create_table`, `postgresql.UUID(as_uuid=True)`, `postgresql.JSONB`, explicit indexes, named unique constraints, and downgrade in reverse order. Use `postgresql_where=sa.text(...)` for active partial unique indexes.

### Trusted Approval Boundary

**Source:** `src/agent/nodes/classify_intent.py` lines 63-76; `src/agent/routing.py` lines 91-100; `tests/agent/test_clarification_gate.py` lines 67-89.
**Apply to:** all chat, graph, API, and service resume paths.

Ordinary chat/LLM output cannot set `approval_result`, trusted markers, expected versions, tenant/user identity, or graph resume payload. Only authenticated API/inbox code builds server-side commands, and only `ApprovalService` returns `approval_result.v1`.

## No Analog Found

No file is completely without a usable source. The following have no exact in-repo implementation and must combine partial analogs with the contract:

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/common/canonical_hash.py` | utility | transform | No existing MOCA Canonical JSON v1 implementation; use `text_hash`, `intent_manifest`, and `docs/contract-spec.md` lines 1451-1487. |
| `src/approvals/service.py` | service | CRUD + CAS | Existing services are simpler; combine `ActionService` nested transaction style with `SessionMemoryRepository.cas_update` and contract transaction order. |
| `src/approvals/sla_scanner.py` | service | batch + event-driven | No scanner exists; implement disabled-by-default using settings pattern and event-shape tests only. |
| `tests/approvals/test_multi_level_contract.py` | test | CRUD + CAS | Runtime is single-level today; use contract matrix and DB/service mismatch tests, not an existing multi-level flow. |

## Metadata

**Analog search scope:** `src/api`, `src/agent`, `src/actions`, `src/approvals` target package, `src/common` target package, `src/db`, `src/knowledge`, `src/memory`, `src/repositories`, `src/tools`, `tests/agent`, `tests/architecture`, `tests/knowledge`, `tests/memory`, legacy approval tests.

**Files scanned:** 60+ source/test/doc files via `rg --files`, targeted `rg`, and line-numbered reads.

**Pattern extraction date:** 2026-06-15

**Planner warning:** Current approval code is v1 behavior. Copy its FastAPI/session/test structure, not its transition ownership. Phase 13 must move approval truth to `src/approvals/ApprovalService`, use exact hash/snapshot binding, and quarantine or delete direct `ApprovalRepository.decide(...)` paths.
