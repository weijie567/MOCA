# Phase 36: merchant-scope-db-hardening-role-cleanup - Pattern Map

**Mapped:** 2026-06-30
**Files analyzed:** 31 likely new/modified files
**Analogs found:** 31 / 31

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `docs/contract-spec.md` | docs/contract | transform | `docs/contract-spec.md` §8.0.1 lines 70-132 | exact |
| `scripts/seed_demo.py` | seed/config | batch | `scripts/seed_demo.py` lines 72-160 | exact |
| `tests/conftest.py` | test fixture | batch | `tests/conftest.py` lines 88-183, 318-323 | exact |
| `src/platform/trusted_context.py` | provider/utility | request-response | `src/platform/trusted_context.py` lines 12-215 | exact |
| `src/auth/permissions.py` | auth dependency/middleware | request-response | `src/auth/permissions.py` lines 16-116 | exact |
| `src/api/schemas/auth.py` | schema | request-response | `src/api/schemas/auth.py` lines 6-26 | exact |
| `src/api/routers/auth.py` | route/controller | request-response | `src/api/routers/auth.py` lines 24-90 | exact |
| `src/db/models.py` | ORM model | CRUD | `src/db/models.py` lines 80-96, 327-350, 638-742, 944-984 | exact |
| `src/db/migrations/versions/019_phase36_merchant_scope_hardening.py` | migration | batch | `016_agent_run_memory_idempotency.py`; `018_phase34_approval_action_bindings.py` | role-match |
| `src/agent/run_scope.py` | utility/domain helper | transform | `src/agent/merchant_context.py`; `src/replay/proof_projection.py` | role-match |
| `src/agent/state.py` | model/contract | event-driven | `src/agent/state.py` lines 55-168 | exact |
| `src/api/schemas/agent_runs.py` | schema | streaming + request-response | `src/api/schemas/agent_runs.py` lines 11-43 | exact |
| `src/agent/trace.py` | service | CRUD + event-driven | `src/agent/trace.py` lines 19-81, 127-165, 322-358 | exact |
| `src/api/routers/agent_runs.py` | route/controller | streaming + request-response | `src/api/routers/agent_runs.py` lines 95-140, 143-248, 971-1031, 1234-1244 | exact |
| `src/agent/merchant_context.py` | utility/projection | transform | `src/agent/merchant_context.py` lines 43-70, 73-114 | exact |
| `src/replay/proof_projection.py` | utility/projection | transform | `src/replay/proof_projection.py` lines 61-115, 160-180 | exact |
| `src/approvals/schemas.py` | schema/validation | transform | `src/approvals/schemas.py` lines 32-118, 198-254 | exact |
| `src/approvals/snapshots.py` | utility/schema | transform | `src/approvals/snapshots.py` lines 44-93, 96-120 | exact |
| `src/approvals/snapshot_service.py` | service | CRUD | `src/approvals/snapshot_service.py` lines 45-103 | exact |
| `src/actions/service.py` | service | CRUD + validation | `src/actions/service.py` lines 63-170, 216-359, 440-506 | exact |
| `src/actions/drafts.py` | persistence adapter | CRUD | `src/actions/drafts.py` lines 12-74 | exact |
| `src/replay/phase36_readiness.py` | utility/artifact contract | transform + batch | `src/replay/phase35_eval_manifest.py` lines 52-57, 101-138, 201-220 | role-match |
| `tests/platform/test_merchant_scope.py` | test | request-response | `tests/platform/test_merchant_scope.py` lines 14-113 | exact |
| `tests/integration/test_auth.py` | test | request-response | `tests/integration/test_auth.py` lines 7-133 | exact |
| `tests/agent/test_phase36_run_scope.py` | test | transform + CRUD | `tests/replay/test_phase35_trace_replay_permissions.py` lines 240-261; `src/agent/trace.py` lines 19-81 | role-match |
| `tests/approvals/test_migration_contract.py` | test | batch/static schema | `tests/approvals/test_migration_contract.py` lines 1-180, 265-326 | exact |
| `tests/db/test_phase36_migration_preflight.py` | test | batch + DB smoke | `016_agent_run_memory_idempotency.py`; `tests/approvals/test_migration_contract.py` | role-match |
| `tests/actions/test_phase34_action_draft_bindings.py` | test | CRUD + validation | `tests/actions/test_phase34_action_draft_bindings.py` lines 1-145, 148-261, 268-404 | exact |
| `tests/approvals/test_phase36_scope_consistency.py` | test | CRUD + validation | `tests/actions/test_phase34_action_draft_bindings.py` lines 205-261, 268-404 | role-match |
| `tests/replay/test_phase35_trace_replay_permissions.py` | test | request-response | `tests/replay/test_phase35_trace_replay_permissions.py` lines 21-288 | exact |
| `tests/replay/test_phase36_readiness.py` | test | transform + static artifact | `tests/eval/test_phase35_replay_eval_gates.py` lines 31-128 | role-match |
| `tests/test_trace_api.py` | test | request-response | `tests/test_trace_api.py` lines 104-180, 621-655 | exact |

## Pattern Assignments

### `src/db/models.py` (ORM model, CRUD)

**Analog:** `src/db/models.py`

**Imports and constraint/index style** (lines 9-24):
```python
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
```

**User identity currently global username; Phase 36 changes must coordinate auth first** (lines 80-96):
```python
class User(TimestampMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("merchants.id"))
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

**AgentRun lacks scope fields today; add explicit classification + target binding here** (lines 327-350):
```python
class AgentRun(TimestampMixin, Base):
    """One row per graph.ainvoke() call. Records run-level trace. Per D-05b."""

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    input_query: Mapped[str] = mapped_column(Text, nullable=False)
    final_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
```

**Approval/action/snapshot binding columns already exist; extend consistently** (lines 638-664, 667-742, 944-984):
```python
class ActionSafetySnapshot(Base):
    __tablename__ = "action_safety_snapshots"
    __table_args__ = (UniqueConstraint("tenant_id", "immutable_hash", name="uq_action_safety_snapshots_tenant_hash"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    immutable_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
```

```python
target_merchant_id: Mapped[str | None] = mapped_column(String(128))
target_merchant_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
business_fact_refs: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
Index("ix_approval_requests_tenant_target_merchant", ApprovalRequest.tenant_id, ApprovalRequest.target_merchant_id)
Index("ix_action_drafts_tenant_target_merchant", ActionDraft.tenant_id, ActionDraft.target_merchant_id)
```

**Planner constraints:**
- Use stable names for any new checks/indexes, matching existing `ck_*`, `ix_*`, `uq_*` style.
- Couple `AgentRun.scope_classification` and `target_merchant_id`: `business_merchant` requires exactly one target merchant; `policy_only` / `merchant_not_required` and `unknown_legacy` must not become business-visible.
- Keep `RefundCase` and `Ticket` order-derived; models have `order_id` only, no local authoritative merchant field (lines 111-170).

---

### `src/db/migrations/versions/019_phase36_merchant_scope_hardening.py` (migration, batch)

**Analogs:** `016_agent_run_memory_idempotency.py`, `018_phase34_approval_action_bindings.py`

**Revision/import pattern** (`018` lines 8-20):
```python
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "018_phase34_approval_action_bindings"
down_revision: str | None = "017_tool_policy_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
```

**Add column/index pattern** (`018` lines 23-72):
```python
_APPROVAL_REQUEST_BINDING_COLUMNS = (
    sa.Column("target_merchant_id", sa.String(length=128)),
    sa.Column("target_merchant_ref", postgresql.JSONB(astext_type=sa.Text())),
)

def upgrade() -> None:
    for column in _APPROVAL_REQUEST_BINDING_COLUMNS:
        op.add_column("approval_requests", column)

    op.create_index(
        "ix_approval_requests_tenant_target_merchant",
        "approval_requests",
        ["tenant_id", "target_merchant_id"],
    )
```

**Preflight-before-constraint pattern** (`016` lines 22-41, 49-75):
```python
def upgrade() -> None:
    _ensure_no_run_role_message_duplicates()
    op.create_index(
        "uq_conversation_messages_active_tenant_run_role",
        "conversation_messages",
        ["tenant_id", "run_id", "role"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND run_id IS NOT NULL AND role IN ('user', 'assistant')"),
    )

def _ensure_no_run_role_message_duplicates() -> None:
    bind = op.get_bind()
    duplicate = (
        bind.execute(sa.text("""SELECT tenant_id, run_id, role, COUNT(*) AS duplicate_count ..."""))
        .mappings()
        .first()
    )
    if duplicate is not None:
        raise RuntimeError("Cannot create ... duplicate rows. ...")
```

**Downgrade pattern** (`018` lines 75-91):
```python
def downgrade() -> None:
    op.drop_index("ix_action_drafts_tenant_target_merchant", table_name="action_drafts")
    op.drop_index("ix_approval_requests_tenant_target_merchant", table_name="approval_requests")

    for column in reversed(_ACTION_DRAFT_BINDING_COLUMNS):
        op.drop_column("action_drafts", column.name)
```

**Planner constraints:**
- Preflight must cover null active business user merchant binding, same-tenant username duplicates, malformed target refs, contradictory approval/action/snapshot/run bindings, ambiguous legacy runs, and downgrade/reupgrade behavior.
- Do not use `requested_by -> users.merchant_id`, username, thread id, prompt text, memory, RAG, raw tool payload, or LLM output as scope backfill proof.
- No PostgreSQL RLS, session tenant variables, or per-connection DB context in this phase.

---

### `src/platform/trusted_context.py` and `src/auth/permissions.py` (provider/auth, request-response)

**Analogs:** same files

**Canonical role constants** (`trusted_context.py` lines 12-15; `permissions.py` lines 16-17):
```python
TRUSTED_CONTEXT_SCHEMA_VERSION = "trusted_context.v1"
MERCHANT_SCOPE_SCHEMA_VERSION = "merchant_scope.v1"
MERCHANT_BOUND_ROLES = {"support", "manager", "merchant"}
PLATFORM_ADMIN_ROLES = {"admin"}
```

**Deny-first merchant scope** (`trusted_context.py` lines 25-70):
```python
class MerchantScopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    merchant_ids: list[str]

    def allows(self, merchant_id: str | None = None, category: str | None = None, risk_level: str | None = None) -> bool:
        if not self.merchant_ids:
            return False
        ...
        if "*" not in allowed and requested not in allowed:
            return False
```

**Role-to-scope derivation and server narrowing** (`trusted_context.py` lines 149-200):
```python
def _base_merchant_scope_from_user(user: Any, *, role: str) -> MerchantScopeV1:
    if role in MERCHANT_BOUND_ROLES:
        merchant_id = getattr(user, "merchant_id", None)
        return MerchantScopeV1(merchant_ids=[str(merchant_id)] if merchant_id is not None else [])
    if role in PLATFORM_ADMIN_ROLES:
        return MerchantScopeV1(merchant_ids=["*"])
    return MerchantScopeV1(merchant_ids=[])

if "*" in override_scope.merchant_ids:
    raise ValueError("server merchant scope cannot widen non-admin merchant scope")
```

**API helper for business resources** (`permissions.py` lines 94-116):
```python
def require_merchant_access(user: User, merchant_id: object, *, resource_name: str = "resource") -> None:
    role = str(user.role)
    if role in PLATFORM_ADMIN_ROLES:
        return
    if role not in MERCHANT_BOUND_ROLES:
        _raise_merchant_access_forbidden(resource_name)
    user_merchant_id = getattr(user, "merchant_id", None)
    if user_merchant_id is None or str(user_merchant_id) != str(merchant_id):
        _raise_merchant_access_forbidden(resource_name)
```

**Planner constraints:**
- `merchant` remains compatibility-only, support-equivalent, and non-wildcard.
- `manager` remains merchant-bound, not tenant-wide.
- Unknown roles stay deny-all for business data.
- If constants are centralized, keep both existing import sites aligned; do not introduce a new role authority table/model in Phase 36.

---

### `src/api/routers/auth.py` and `src/api/schemas/auth.py` (route/schema, request-response)

**Analogs:** same files

**Current token payload includes tenant id** (`auth.py` lines 24-33):
```python
def _token_for_user(user: User) -> TokenResponse:
    token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "tenant_id": str(user.tenant_id),
        }
    )
    return TokenResponse(access_token=token)
```

**Current lookup is username-only and must not coexist with relaxed global uniqueness** (`auth.py` lines 36-62, 70-90):
```python
@router.post("/login", response_model=ApiResponse)
async def login(payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)) -> ApiResponse:
    stmt = select(User).where(User.username == payload.username)
    user = (await session.execute(stmt)).scalar_one_or_none()
```

```python
class LoginRequest(BaseModel):
    username: str
    password: str

class DemoTokenRequest(BaseModel):
    username: str
```

**Trusted token validation is tenant-aware after login** (`permissions.py` lines 53-61):
```python
sub = payload.get("sub")
tenant_id = payload.get("tenant_id")
stmt = select(User).where(User.id == uuid.UUID(str(sub)), User.tenant_id == uuid.UUID(str(tenant_id)))
user = (await session.execute(stmt)).scalar_one_or_none()
if user is None or not user.is_active:
    raise credentials_error
```

**Planner constraints:**
- Decide and test a trusted tenant selector before relaxing `users.username` uniqueness.
- If a product-ready selector is unavailable, keep same-tenant duplicate usernames impossible and document/test the transitional invariant.
- Update `auth_headers` helpers and tests that post `{"username": ..., "password": ...}` if request schema changes.

---

### `src/agent/run_scope.py` (new utility/domain helper, transform)

**Analogs:** `src/agent/merchant_context.py`, `src/replay/proof_projection.py`, `src/tools/contracts.py`, `src/business/service.py`

**Projection helper style** (`merchant_context.py` lines 43-70):
```python
def project_target_merchant_context(state: Mapping[str, Any]) -> dict[str, Any]:
    explicit = state.get("target_merchant_context")
    ...
    approved_refs = _service_approved_business_fact_refs(state)
    if approved_refs:
        return _status("resolved", source="business_fact_refs", reason_codes=[], business_fact_ref_count=len(approved_refs))
    if _is_business_scoped_path(state):
        return _status("deferred", source="business_fact_refs", reason_codes=[DEFERRED_REASON])
    return _status("not_applicable", source="intent_policy", reason_codes=[])
```

**Trusted source filtering** (`merchant_context.py` lines 103-114; `proof_projection.py` lines 50-58):
```python
TRUSTED_BUSINESS_FACT_SOURCES = {
    "business_fact_service",
    "business_tool_service",
    "demo_orders_db",
    "demo_refund_cases_db",
    "demo_tickets_db",
    "tool_platform",
    "tool_result_v2",
}
```

**Typed authority contract** (`tools/contracts.py` lines 58-68):
```python
class BusinessFactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["business_fact_ref.v1"] = "business_fact_ref.v1"
    tenant_id: str
    source_system: str
    resource_type: Literal["order", "refund_case", "ticket", "logistics", "merchant_risk"]
    resource_id: str
```

**Business service aggregation pattern** (`business/service.py` lines 587-643):
```python
if result.status in FACT_BEARING_TOOL_STATUSES and result.data is not None and result.business_fact_refs:
    facts[resource_name] = result.data
    for fact_ref in result.business_fact_refs:
        key = fact_ref.model_dump_json()
        if key not in fact_ref_keys:
            fact_ref_keys.add(key)
            fact_refs.append(fact_ref)
```

**Planner constraints:**
- Keep literals exactly aligned with SPEC/CONTEXT: `business_merchant`, `policy_only` or `merchant_not_required`, and `unknown_legacy`.
- Null target merchant is valid only for non-business/fail-closed classifications.
- Multi-merchant proof is invalid/out of scope; classify fail-closed or block migration.
- `target_merchant_context` and `replay_authorization_proof` can inform readiness metadata but must not override missing/contradictory AgentRun target binding.

---

### `src/agent/trace.py`, `src/api/routers/agent_runs.py`, `src/api/schemas/agent_runs.py`, `src/agent/state.py` (run lifecycle, CRUD/streaming)

**Analogs:** same files

**Run creation/update helper** (`trace.py` lines 19-81):
```python
async def write_agent_run(..., final_status: str, final_response: str | None, ... ) -> AgentRun:
    run_uuid = uuid.UUID(run_id)
    run = await session.get(AgentRun, run_uuid)
    if run is None:
        run = AgentRun(
            id=run_uuid,
            thread_id=thread_id,
            tenant_id=uuid.UUID(tenant_id),
            user_id=uuid.UUID(user_id),
            input_query=input_query,
            final_status=final_status,
        )
        session.add(run)
    else:
        run.final_status = final_status
        run.final_response = final_response
    await session.flush()
```

**Status lifecycle update helper** (`trace.py` lines 127-165):
```python
async def update_agent_run_status(..., final_status: str, ... ) -> None:
    stmt = select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run:
        previous_status = run.final_status
        run.final_status = final_status
        ...
        await session.flush()
        if emit_if_unchanged or previous_status != final_status:
            await _append_lifecycle_status(...)
```

**API create + transaction pattern** (`agent_runs.py` lines 95-140):
```python
try:
    await write_agent_run(..., final_status="pending", ...)
    await conversation_service.append_or_get_user_message_for_run(...)
    await session.commit()
except Exception:
    await session.rollback()
    raise
```

**Claim pending run with lock** (`agent_runs.py` lines 971-1003):
```python
result = await session.execute(
    select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id).with_for_update()
)
run = result.scalar_one_or_none()
_ensure_can_view_run(run, user=user)
_ensure_can_execute_run(run, user=user)
...
await update_agent_run_status(session, run_id=str(run.id), final_status="running", trace_id=None)
await session.commit()
```

**Owner/admin-only guard must remain unchanged** (`agent_runs.py` lines 1234-1244):
```python
def _ensure_can_view_run(run: AgentRun | None, *, user: User) -> None:
    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})

def _ensure_can_execute_run(run: AgentRun, *, user: User) -> None:
    if run.user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot execute this run"})
```

**State/schema fields already carry target binding material** (`state.py` lines 127-149; `agent_runs.py` schema lines 24-43):
```python
target_merchant_id: str | None
target_merchant_ref: dict[str, Any] | None
business_fact_refs: list[dict[str, Any]]
verified_evidence_refs: list[dict[str, Any]]
```

**Planner constraints:**
- Persist AgentRun target scope at the earliest trustworthy business-scope source in graph/tool/business-fact flow.
- Do not infer target scope from run owner identity, prompt, thread id, memory, RAG text, raw tool payload, or LLM output.
- Adding response fields is fine for status/readiness if needed, but do not make them authorization gates in Phase 36.

---

### `src/api/routers/traces.py` and run/status/evidence/replay guard tests (request-response)

**Analogs:** `src/api/routers/traces.py`, `tests/replay/test_phase35_trace_replay_permissions.py`, `tests/test_trace_api.py`

**Trace/replay guard baseline** (`traces.py` lines 23-98):
```python
run = await repo.get_run(run_uuid, user.tenant_id)
if not run:
    raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
```

**Static no-shortcut regression** (`test_phase35_trace_replay_permissions.py` lines 21-77):
```python
FORBIDDEN_AUTH_SHORTCUT_PATTERNS = (
    r"target_merchant_context",
    r"project_replay_authorization_proof",
    r"proof_status",
    r"requested_by.*merchant",
    r"merchant_id.*requested_by",
)

assert "run.user_id != user.id" in source
assert "user.role not in ADMIN_RUN_VISIBILITY_ROLES" in source
_assert_no_phase35_auth_shortcut(source)
```

**Runtime owner/admin/no-leak tests** (`test_phase35_trace_replay_permissions.py` lines 80-220):
```python
assert [response.status_code for response in responses] == [404, 404, 404, 404, 404]
assert {response.json()["error"]["code"] for response in responses} == {"NOT_FOUND"}
...
assert [response.status_code for response in responses] == [403, 403, 403, 403, 403]
assert {response.json()["error"]["code"] for response in responses} == {"FORBIDDEN"}
```

**Planner constraints:**
- Phase 36 can make readiness possible; it must not consume readiness to grant same-merchant manager/support run/status/evidence/trace/replay access.
- Extend forbidden shortcut patterns for new Phase 36 helper names if a readiness/run-scope helper is introduced.

---

### `src/approvals/schemas.py`, `src/approvals/snapshots.py`, `src/approvals/snapshot_service.py`, `src/actions/service.py`, `src/actions/drafts.py` (schemas/services, validation + CRUD)

**Analogs:** same files and Phase 34 action tests

**Strict typed binding schemas** (`approvals/schemas.py` lines 32-78):
```python
class TargetMerchantBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["target_merchant_binding.v1"] = "target_merchant_binding.v1"
    target_merchant_id: str
    source: Literal["business_fact_ref", "business_fact_result"]
    business_fact_ref: dict[str, Any]

class AutoAllowedActionBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str
    run_id: str
    target_merchant_id: str
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
```

**Snapshot hash boundary** (`approvals/snapshots.py` lines 44-93):
```python
class ActionSafetySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["action_safety_snapshot.v1"] = ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION
    tenant_id: str
    run_id: str
    snapshot_ref: str
    evidence: list[EvidenceRefV1]
    action_payload_hash: str
    immutable_hash: str
```

**Snapshot persistence verifies hash and reload** (`snapshot_service.py` lines 54-103):
```python
computed_hash = compute_action_payload_hash(proposed_action)
if action_payload_hash is not None and action_payload_hash != computed_hash:
    raise ActionSafetySnapshotPersistenceError("action_payload_hash mismatch")
...
row = await repo.create_snapshot_row(snapshot, created_by=created_by)
if row.action_payload_hash != computed_hash:
    raise ActionSafetySnapshotPersistenceError("persisted snapshot action hash mismatch")
reloaded = await repo.get_snapshot_by_ref_or_hash(...)
if reloaded is None:
    raise ActionSafetySnapshotPersistenceError("persisted snapshot could not be reloaded")
```

**Action binding validation pattern** (`actions/service.py` lines 216-359):
```python
snapshot = (
    await self.session.execute(
        select(ActionSafetySnapshot).where(
            ActionSafetySnapshot.tenant_id == tenant_id,
            ActionSafetySnapshot.run_id == run_id,
            ActionSafetySnapshot.snapshot_ref == safety_snapshot_ref,
            ActionSafetySnapshot.immutable_hash == safety_snapshot_hash,
            ActionSafetySnapshot.action_payload_hash == action_payload_hash,
            ActionSafetySnapshot.deleted_at.is_(None),
        )
    )
).scalar_one_or_none()
if snapshot is None:
    return _tool_error("ACTION_BINDING_MISMATCH", "Action safety snapshot binding is invalid", retryable=False)
```

```python
if not _approval_phase34_binding_matches(approval, requested_binding):
    return _tool_error("APPROVAL_BINDING_MISMATCH", "Approved request binding is invalid", retryable=False)
```

**Canonical comparison pattern** (`actions/service.py` lines 440-506):
```python
def _approval_phase34_binding_matches(approval: ApprovalRequest, requested: dict[str, Any]) -> bool:
    if approval.target_merchant_id != requested["target_merchant_id"]:
        return False
    if _canonical_target_merchant_ref(approval.target_merchant_ref) != requested["target_merchant_ref"]:
        return False
    if _canonical_business_fact_refs(approval.business_fact_refs) != requested["business_fact_refs"]:
        return False
    return True

def _canonical_target_merchant_ref(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return TargetMerchantBindingV1.model_validate(_json_safe(value)).model_dump(mode="json")
```

**Persistence adapter pattern** (`actions/drafts.py` lines 12-74):
```python
class ActionDraftStore:
    """Persistence adapter for durable action drafts."""

    async def create_or_get(..., target_merchant_id: str | None, target_merchant_ref: dict[str, Any] | None, ...):
        return await self.repository.create_or_get(
            target_merchant_id=target_merchant_id,
            target_merchant_ref=target_merchant_ref,
            business_fact_refs=business_fact_refs,
            verified_evidence_refs=verified_evidence_refs,
        )
```

**Planner constraints:**
- Prefer adding a target merchant binding or immutable scope proof to `ActionSafetySnapshot` in line with the existing hash boundary.
- Do not treat raw `snapshot_json` as authorization proof unless the exact hash/target binding consistency is also verified.
- Cross-table consistency should compare canonical typed bindings, not raw dict order/string formatting.

---

### `scripts/seed_demo.py`, `tests/conftest.py`, `docs/contract-spec.md` (seed/docs/test fixtures)

**Analogs:** same files

**Docs role semantics to preserve/align** (`docs/contract-spec.md` lines 74-120):
```python
merchant_bound_roles = {"support", "manager", "merchant"}
platform_admin_roles = {"admin"}
```

Key contract lines:
- `merchant` is legacy and support-equivalent, not a recommended new role (lines 83-86).
- Missing `merchant_id` on merchant-bound roles is deny-all (lines 91-96).
- Manager is not tenant-wide for run/evidence/trace/approval/action visibility (lines 114-118).
- Wildcard must not be fabricated from graph, memory, RAG, tool args, or approval resume paths (line 120).

**Seed roles/users today still include merchant users** (`seed_demo.py` lines 72-160):
```python
roles = {
    "support": Role(..., name="support", description="Support agent"),
    "manager": Role(..., name="manager", description="Operations manager"),
    "merchant": Role(..., name="merchant", description="Merchant operator"),
    "admin": Role(..., name="admin", description="System admin"),
}
...
("demo_merchant_1", "demo", "merchant_wang", "商家王林", "merchant", merchants["xinghe"].id),
```

**Test fixtures include role/merchant coverage** (`tests/conftest.py` lines 119-183):
```python
users = {
    "admin_user": User(..., role="admin", is_active=True),
    "cs_zhang": User(..., merchant_id=merchant.id, role="support", is_active=True),
    "approval_manager": User(..., merchant_id=merchant.id, role="manager", is_active=True),
    "merchant_wang": User(..., merchant_id=merchant.id, role="merchant", is_active=True),
    "other_support": User(..., tenant_id=other_tenant.id, merchant_id=other_merchant.id, role="support"),
}
```

**Auth helper pattern to update if login schema changes** (`tests/conftest.py` lines 318-323):
```python
async def _headers(username: str = "admin_user", password: str = "moca2024") -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

**Planner constraints:**
- New seed/fixture examples should prefer `support`, `manager`, and `admin`; legacy `merchant` remains only for compatibility regression.
- Any tenant-aware login selector change must be reflected in fixture helpers, auth tests, demo walkthroughs, and seed/demo-token behavior.

---

### Test files (unit/integration/static, request-response + batch)

**Analogs:** existing Phase 34/35 tests

**Migration contract static pattern** (`test_migration_contract.py` lines 51-82, 153-161):
```python
def _column_names(table_name: str) -> set[str]:
    return set(_table(table_name).c.keys())

def _phase34_migration_source() -> str:
    assert PHASE34_MIGRATION_PATH.exists(), "migration 018 must exist"
    return PHASE34_MIGRATION_PATH.read_text(encoding="utf-8")

def test_phase34_approval_and_action_binding_columns_are_declared():
    assert PHASE34_APPROVAL_BINDING_COLUMNS.issubset(_column_names("approval_requests"))
    assert PHASE34_ACTION_DRAFT_BINDING_COLUMNS.issubset(_column_names("action_drafts"))
```

**Deterministic backfill test style** (`test_migration_contract.py` lines 265-309):
```python
normalized_source = re.sub(r"\s+", " ", source.lower())
assert "row_number()" in normalized_source
assert "partition by tenant_id, run_id" in normalized_source
...
for revision, row in enumerate(sorted(group, key=lambda item: (item["created_at"], item["id"])), start=1):
    migrated.append({**row, "revision": revision, "legacy_non_executable": True})
```

**Role/scope fail-closed test style** (`test_merchant_scope.py` lines 80-113):
```python
@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_require_merchant_access_allows_merchant_bound_same_merchant(role: str) -> None:
    require_merchant_access(_user(role=role, merchant_id=merchant_id), str(merchant_id), resource_name="orders")

@pytest.mark.parametrize(...)
def test_require_merchant_access_fails_closed(...):
    with pytest.raises(HTTPException) as exc_info:
        require_merchant_access(...)
    assert exc_info.value.status_code == 403
```

**Auth integration pattern** (`test_auth.py` lines 7-35, 73-133):
```python
response = await client.post("/api/v1/auth/login", json={"username": "admin_user", "password": "moca2024"})
assert response.status_code == 200
...
result = await get_current_user(
    security_scopes=SecurityScopes(scopes=["agent:chat"]),
    token=token,
    session=session,
    request=mock_request,
)
```

**Approval/action consistency tests to copy** (`test_phase34_action_draft_bindings.py` lines 205-261, 268-404):
```python
result = await create_coupon_grant_draft(..., **_phase34_tool_kwargs(request, target_merchant_id="merchant-other"))
assert result["status"] == "error"
assert result["error"]["error_code"] == "APPROVAL_BINDING_MISMATCH"
await _assert_no_drafts(session, request.run_id)
```

```python
assert draft.target_merchant_id == request.target_merchant_id
assert draft.target_merchant_ref == request.target_merchant_ref
assert draft.business_fact_refs == request.business_fact_refs
```

**Readiness/artifact test command discipline** (`phase35_eval_manifest.py` lines 52-57, 201-220; `test_phase35_replay_eval_gates.py` lines 95-122):
```python
APPROVED_PYTEST_ENTRYPOINTS = (
    "UV_CACHE_DIR=/tmp/uv-cache uv run pytest ",
    "uv run pytest ",
    ".venv/bin/pytest ",
    ".venv/bin/python -m pytest ",
)
...
if _contains_bare_pytest(command):
    errors.append(f"required_test_commands contains bare pytest entrypoint: {command!r}")
```

```python
for command in manifest.required_test_commands:
    assert command.startswith(APPROVED_COMMAND_PREFIXES), command
    assert " python -m pytest" not in command
    assert not command.startswith("pytest ")
```

**Planner constraints:**
- New test files from VALIDATION.md:
  - `tests/agent/test_phase36_run_scope.py`
  - `tests/approvals/test_phase36_scope_consistency.py`
  - `tests/db/test_phase36_migration_preflight.py`
  - `tests/replay/test_phase36_readiness.py`
- Required commands must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid in MOCA.

## Shared Patterns

### Auth And Tenant Identity

**Source:** `src/api/routers/auth.py`, `src/auth/permissions.py`
**Apply to:** `src/api/routers/auth.py`, `src/api/schemas/auth.py`, `src/db/models.py`, `tests/integration/test_auth.py`, `tests/conftest.py`

Current login/demo-token/token paths query `User.username` alone, while token validation is already tenant-aware by `User.id` + `tenant_id`. Planner must sequence tenant selector/transitional invariant before changing `username` uniqueness.

### Role Scope And Fail Closed

**Source:** `src/platform/trusted_context.py`, `src/auth/permissions.py`, `docs/contract-spec.md`
**Apply to:** role constants, seeds, fixtures, role tests, contract docs

`support`, `manager`, and legacy `merchant` are merchant-bound; `admin` is the only human wildcard business-data role; unknown roles deny all business data; non-admin `server_merchant_scope` cannot widen.

### Migration Preflight

**Source:** `src/db/migrations/versions/016_agent_run_memory_idempotency.py`
**Apply to:** Phase 36 migration and migration tests

Use `_ensure_*` helper functions before hard constraints/indexes, `op.get_bind().execute(sa.text(...)).mappings().first()`, and actionable `RuntimeError` messages including the first conflicting row/count.

### AgentRun Write/Update Lifecycle

**Source:** `src/agent/trace.py`, `src/api/routers/agent_runs.py`
**Apply to:** `AgentRun` scope persistence, run creation/status/completion tests

Write on create through `write_agent_run`, claim with `with_for_update`, update status through `update_agent_run_status`, flush/commit in the caller, and rollback on exceptions.

### Approval/Action/Snapshot Binding Consistency

**Source:** `src/actions/service.py`, `src/approvals/schemas.py`, `src/approvals/snapshots.py`
**Apply to:** approval request, action draft, safety snapshot, consistency tests

Use Pydantic `extra="forbid"` schemas, canonical model validation/dumps, exact payload hash/safety snapshot hash comparisons, and no raw `snapshot_json` authorization shortcut.

### Owner/Admin-Only Runtime Visibility

**Source:** `src/api/routers/traces.py`, `src/api/routers/agent_runs.py`, `tests/replay/test_phase35_trace_replay_permissions.py`
**Apply to:** all status/evidence/trace/replay guards and tests

The guard remains `run.user_id == user.id or user.role in {"admin"}`. New target merchant/run-scope/readiness proof helpers must not appear in guard code in Phase 36.

### Order-Derived Refund/Ticket Ownership

**Source:** `src/api/routers/refund_cases.py` lines 46-53; `src/api/routers/tickets.py` lines 46-53
**Apply to:** refund/ticket regression tests and any redundant merchant field decision

```python
merchant_id = (
    await session.execute(
        select(Order.merchant_id).where(Order.id == refund_case.order_id, Order.tenant_id == user.tenant_id)
    )
).scalar_one_or_none()
require_merchant_access(user, merchant_id, resource_name="refund cases")
```

Do not introduce refund/ticket-local merchant truth unless it is explicitly non-authoritative and checked against `orders.merchant_id`.

### Test Command Discipline

**Source:** `AGENTS.md` lines 16-21; `36-VALIDATION.md` lines 16-23, 37-45, 85-92
**Apply to:** every plan verification command and any manifest/readiness artifact

Use:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...
```

Never use bare `pytest` or bare `python -m pytest` as valid MOCA verification.

## No Analog Found

No file is completely without an analog. New Phase 36 helper/test files have role-match analogs:

| File | Role | Data Flow | Analog To Use |
|---|---|---|---|
| `src/agent/run_scope.py` | utility | transform | `src/agent/merchant_context.py`, `src/replay/proof_projection.py` |
| `src/replay/phase36_readiness.py` | utility/artifact | transform + batch | `src/replay/phase35_eval_manifest.py`, `tests/eval/test_phase35_replay_eval_gates.py` |
| `tests/db/test_phase36_migration_preflight.py` | test | batch + DB smoke | `016_agent_run_memory_idempotency.py`, `tests/approvals/test_migration_contract.py` |

## Metadata

**Analog search scope:** `src/db`, `src/platform`, `src/auth`, `src/api`, `src/agent`, `src/approvals`, `src/actions`, `src/replay`, `tests`, `scripts`, `docs`
**Files scanned:** local `rg --files src tests docs scripts .planning/codebase` inventory plus targeted `rg` pattern searches
**Pattern extraction date:** 2026-06-30
**Project constraints applied:** no source edits; no `.planning/LOCAL-VALIDATION-ISSUES.md` edits; MOCA test commands must use `uv run` / `.venv/bin` entrypoints
