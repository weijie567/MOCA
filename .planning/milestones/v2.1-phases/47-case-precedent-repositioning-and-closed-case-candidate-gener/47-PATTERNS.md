# Phase 47: Case Precedent Repositioning and Closed-Case Candidate Generation - Pattern Map

**Mapped:** 2026-07-03
**Files analyzed:** 20
**Analogs found:** 19 / 20

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `docs/contract-spec.md` | config | transform | `docs/contract-spec.md` sections 13.4-13.7 | exact |
| `docs/current-implementation-map.md` | config | transform | `docs/current-implementation-map.md` memory rows | exact |
| `docs/architecture-overview.md` | config | transform | `docs/architecture-overview.md` memory boundary section | exact |
| `src/memory/case_precedent.py` | service | request-response + CRUD + transform | `src/memory/case_working_context_lifecycle.py` + `src/memory/case_memory.py` | composite |
| `src/memory/schemas.py` | model | transform | existing `CaseMemory*` and `MemorySourceRefV1` schemas | exact |
| `src/memory/policy.py` | utility | transform | existing case-memory source-type policy | exact |
| `src/memory/identity.py` | utility | transform | source-ref allowed-key and identity hash helpers | conditional exact |
| `src/repositories/refund_repo.py` | service | CRUD | existing refund/order repository lookup methods | role-match |
| `src/memory/case_memory.py` | service | CRUD + request-response | existing candidate, review, retrieval service | exact |
| `src/memory/context_service.py` | service | request-response | reviewed memory context scope construction | exact |
| `src/tools/executors/memory.py` | service | request-response | planner-facing `search_case_memory` executor | exact |
| `src/tools/catalog.py` | config | request-response | `search_case_memory` tool declaration | exact |
| `tests/memory/test_phase47_case_precedent_alignment.py` | test | transform | `tests/memory/test_phase45_contract_alignment.py` + `tests/memory/test_phase46_session_context_alignment.py` | role-match |
| `tests/memory/test_case_precedent_generation.py` | test | CRUD + request-response + transform | `tests/memory/test_case_memory_retrieval.py` + `tests/agent/test_case_working_context_lifecycle.py` | composite |
| `tests/memory/test_memory_policy.py` | test | transform | existing memory policy tests | exact |
| `tests/memory/test_case_memory_retrieval.py` | test | request-response | existing reviewed retrieval tests | exact |
| `tests/memory/test_reviewed_memory_context_boundary.py` | test | request-response | existing reviewed prompt-context boundary tests | exact |
| `tests/test_memory_review_api.py` | test | request-response | existing memory review API tests | exact |
| `tests/agent/test_reviewed_memory_context_retrieve.py` | test | request-response | reviewed memory node fail-closed scope tests | exact |
| `tests/tools/test_catalog.py` | test | request-response | tool schema and descriptor tests | exact |

## Pattern Assignments

### `src/memory/case_precedent.py` (service, request-response + CRUD + transform)

**Analog:** `src/memory/case_working_context_lifecycle.py` + `src/memory/case_memory.py`

**Imports/service boundary pattern** (`src/memory/case_working_context_lifecycle.py` lines 3-27; `src/memory/case_memory.py` lines 27-34):

```python
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.case_working_context import CaseWorkingContextRepository, hydrate_content
from src.memory.case_working_context_schemas import CaseWorkingContextContentV1
from src.memory.schemas import MemorySourceRefV1
```

Copy the constructor-injection style from `CaseWorkingContextLifecycleAdapter` lines 61-73: accept repository/service classes as dependencies so tests can pass fakes.

**Trusted close seam pattern** (`src/repositories/refund_repo.py` lines 11-20; `src/db/models.py` lines 133-174; `src/api/routers/refund_cases.py` lines 21-53):

```python
class RefundRepository(BaseRepository[RefundCase]):
    model = RefundCase

    async def get_by_case_no(self, refund_case_no: str, tenant_id: UUID) -> RefundCase | None:
        stmt = select(RefundCase).where(
            RefundCase.refund_case_no == refund_case_no,
            RefundCase.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

`RefundCase` links to `Order` and `Order.merchant_id`; use that relationship for merchant-scope precedent storage. The current router is GET-only; do not add a public close endpoint for Phase 47.

**CWC read/hydrate pattern** (`src/memory/case_working_context.py` lines 48-61 and 218-223):

```python
async def read_active(
    self,
    *,
    tenant_id: uuid.UUID,
    case_id: uuid.UUID,
) -> CaseWorkingContext | None:
    result = await self.session.execute(
        select(CaseWorkingContext).where(
            CaseWorkingContext.tenant_id == tenant_id,
            CaseWorkingContext.case_id == case_id,
            CaseWorkingContext.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()

def hydrate_content(row: CaseWorkingContext) -> CaseWorkingContextContentV1:
    payload = {
        content_field: getattr(row, column_name)
        for content_field, column_name in _CWC_CONTENT_COLUMN_MAP.items()
    }
    return CaseWorkingContextContentV1.model_validate(payload)
```

**Deterministic projection pattern** (`src/memory/case_working_context_lifecycle.py` lines 461-492 and 506-513):

```python
source_ref = _terminal_source_ref(run_id=run_id, case_id=case_id)
recommendations, next_action = _project_recommendations_and_next_action(state)
content = CaseWorkingContextContentV1(
    customer_request=_truncate(_non_empty_str(state.get("user_query")), 500),
    issue_type=_project_issue_type(state),
    verified_facts=_project_verified_facts(state, source_ref=source_ref),
    policy_refs=_project_policy_refs(state),
    agent_recommendations=recommendations,
    next_action=next_action,
)

def _terminal_source_ref(*, run_id: uuid.UUID, case_id: uuid.UUID) -> MemorySourceRefV1:
    return MemorySourceRefV1(
        source_type="run_auto_terminal",
        run_id=str(run_id),
        agent_run_id=str(run_id),
        business_object_type="refund_case",
        business_object_id=str(case_id),
    )
```

For Phase 47, project into `CaseMemoryWriteCandidate`, not `CaseWorkingContextWriteCandidate`, and use source type `closed_case_cwc_candidate` if added.

**Projectable/PII pattern** (`src/memory/case_working_context_lifecycle.py` lines 648-674):

```python
def _has_projectable_content(content: CaseWorkingContextContentV1) -> bool:
    return any(
        (
            content.customer_request,
            content.issue_type,
            content.verified_facts,
            content.policy_refs,
            content.agent_recommendations,
            content.next_action.recommended_step,
            content.next_action.blocked_by,
        )
    )

def _classify_terminal_projection_pii(
    content: CaseWorkingContextContentV1,
    *,
    final_response: str,
) -> str:
    values = _collect_strings(content.model_dump(mode="json"))
    values.append(final_response)
    text = " ".join(values).lower()
    if any(marker.lower() in text for marker in _TERMINAL_PROHIBITED_PII_MARKERS):
        return "prohibited"
    if any(pattern.search(text) for pattern in _TERMINAL_SENSITIVE_PII_PATTERNS):
        return "sensitive"
    return "none"
```

**Candidate submission/audit pattern** (`src/memory/case_memory.py` lines 490-620):

```python
identity = _candidate_identity(candidate)
policy_decision = _policy_decision_for_candidate(candidate)
tombstone = await self.repository.check_tombstone_before_write(...)
if tombstone is not None:
    event = await self.repository.emit_write_event(..., decision="skip", reason_code="tombstone_match")
    return _write_result(status="skipped", ...)

if is_blocked_memory_write_pii_classification(candidate.pii_classification):
    event = await self.repository.emit_write_event(..., decision="skip", reason_code="pii_blocked")
    return _write_result(status="skipped", ...)

duplicate = await self.repository.get_active_duplicate(...)
if duplicate is not None:
    event = await self.repository.emit_write_event(..., decision="skip", reason_code=reason_code)
    return _write_result(status="skipped", ...)

review_status = policy_decision.review_status or "needs_review"
memory = await self.repository.insert_case_memory(..., review_status=review_status)
event = await self.repository.emit_write_event(..., decision=policy_decision.decision)
return _write_result(status="written" if review_status == "auto_approved" else "needs_review", ...)
```

Do not insert `CaseMemory` directly from the new service.

**Anti-pattern source:** `src/api/services/agent_run_memory.py` lines 53-68 show completed-run finalization. Phase 47 must not use `final_status == "completed"` as case closure.

### `src/memory/schemas.py` (model, transform)

**Analog:** existing `MemorySourceRefV1`, `CaseMemorySourceType`, `CaseMemoryWriteCandidate`, and search request schemas.

**Source-ref schema pattern** (`src/memory/schemas.py` lines 13-25):

```python
class MemorySourceRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    run_id: str | None = None
    event_id: str | None = None
    conversation_message_id: str | None = None
    tool_result_id: str | None = None
    agent_run_id: str | None = None
    business_object_type: str | None = None
    business_object_id: str | None = None
    policy_version: str | None = None
    outcome_id: str | None = None
```

Prefer encoding close event and CWC version through existing `event_id` / `outcome_id`. If new keys are added, update `src/memory/identity.py` too.

**Source type pattern** (`src/memory/schemas.py` lines 251-274):

```python
CaseMemorySourceType = Literal[
    "explicit_admin_preference",
    "human_reviewed",
    "deterministic_tool_result",
    "confirmed_business_outcome",
    "approved_approval_state",
    "llm_candidate",
    "semantic_episode_candidate",
    "summary_candidate",
    "cross_case_pattern_candidate",
    "behavior_inference",
]
```

Add `closed_case_cwc_candidate` here if the plan chooses the dedicated source-type path.

**Candidate shape pattern** (`src/memory/schemas.py` lines 326-345):

```python
class CaseMemoryWriteCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    run_id: uuid.UUID
    scope_type: CaseMemoryScopeType
    scope_id: str = Field(min_length=1, max_length=128)
    case_type: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=4000)
    excerpt: str = Field(min_length=1, max_length=1500)
    applicability: str | None = Field(default=None, max_length=1500)
    outcome: str | None = Field(default=None, max_length=1500)
    caveats: str | None = Field(default=None, max_length=1500)
    source_type: CaseMemorySourceType
    source_ref: MemorySourceRefV1 | None = None
    policy_family: str | None = Field(default=None, max_length=80)
    policy_version: str | None = Field(default=None, max_length=80)
    policy_refs: list[dict[str, Any]] = Field(default_factory=list)
    embedding: list[float] | None = None
    pii_classification: CaseMemoryPiiClassification = "none"
```

**Search request pattern** (`src/memory/schemas.py` lines 375-385):

```python
class CaseMemorySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: uuid.UUID
    scope_type: CaseMemoryScopeType | None = None
    scope_id: str | None = Field(default=None, max_length=128)
    scopes: list[tuple[CaseMemoryScopeType, str]] | None = None
    case_type: str | None = Field(default=None, max_length=64)
    policy_family: str | None = Field(default=None, max_length=80)
    policy_version: str | None = Field(default=None, max_length=80)
    query: str | None = Field(default=None, min_length=1, max_length=500)
```

### `src/memory/policy.py` (utility, transform)

**Analog:** existing case-memory policy sets and decision function.

**Source type governance pattern** (`src/memory/policy.py` lines 71-88 and 150-174):

```python
AUTO_APPROVED_CASE_SOURCE_TYPES = frozenset(
    {
        "explicit_admin_preference",
        "human_reviewed",
    }
)
REVIEW_REQUIRED_CASE_SOURCE_TYPES = frozenset(
    {
        "deterministic_tool_result",
        "confirmed_business_outcome",
        "approved_approval_state",
        "llm_candidate",
        "semantic_episode_candidate",
        "summary_candidate",
        "cross_case_pattern_candidate",
        "behavior_inference",
    }
)

def case_memory_policy_decision(...):
    if is_blocked_memory_write_pii_classification(pii_classification):
        return MemoryPolicyDecision(..., decision="skip", reason_code="pii_blocked")
    if source_type in AUTO_APPROVED_CASE_SOURCE_TYPES:
        return MemoryPolicyDecision(..., decision="write", review_status="auto_approved")
    if source_type in REVIEW_REQUIRED_CASE_SOURCE_TYPES:
        return _needs_review("case", blocked_by=["source_requires_review"])
    return _needs_review("case", blocked_by=["unknown_source_type"])
```

Add `closed_case_cwc_candidate` to `REVIEW_REQUIRED_CASE_SOURCE_TYPES` only. It must not appear in `AUTO_APPROVED_CASE_SOURCE_TYPES`.

**Test pattern** (`tests/memory/test_memory_policy.py` lines 79-88):

```python
def test_case_memory_only_explicit_review_sources_auto_publish() -> None:
    assert case_memory_review_status_for_source("human_reviewed") == "auto_approved"
    assert case_memory_review_status_for_source("explicit_admin_preference") == "auto_approved"
    assert case_memory_review_status_for_source("deterministic_tool_result") == "needs_review"
    assert case_memory_review_status_for_source("confirmed_business_outcome") == "needs_review"
    assert case_memory_review_status_for_source("approved_approval_state") == "needs_review"
    assert case_memory_review_status_for_source("llm_candidate") == "needs_review"
```

Extend this assertion set for `closed_case_cwc_candidate`.

### `src/memory/identity.py` (utility, transform)

**Analog:** source identity helpers.

**Allowed key and discriminator pattern** (`src/memory/identity.py` lines 19-57):

```python
ALLOWED_SOURCE_REF_KEYS = frozenset(
    {
        "source_type",
        "run_id",
        "event_id",
        "conversation_message_id",
        "tool_result_id",
        "agent_run_id",
        "business_object_type",
        "business_object_id",
        "policy_version",
        "outcome_id",
    }
)

_SOURCE_IDENTITY_DISCRIMINATORS = frozenset(
    {
        "event_id",
        "conversation_message_id",
        "tool_result_id",
        "agent_run_id",
        "business_object_id",
        "outcome_id",
    }
)
```

**Canonical hash pattern** (`src/memory/identity.py` lines 120-153 and 156-183):

```python
unknown_keys = set(source_ref) - ALLOWED_SOURCE_REF_KEYS
if unknown_keys:
    raise MemoryIdentityError(f"unknown source identity fields: {sorted(unknown_keys)}")

if not any(_has_source_discriminator(source_ref.get(key)) for key in _SOURCE_IDENTITY_DISCRIMINATORS):
    return None
```

If `MemorySourceRefV1` is extended with native `cwc_version` or `closed_at`, the planner must also extend `ALLOWED_SOURCE_REF_KEYS`, discriminator logic if needed, and identity tests. Otherwise dedupe will not use the new keys.

### `src/repositories/refund_repo.py` (service, CRUD)

**Analog:** `src/repositories/base.py` and current refund/order lookups.

**Repository style** (`src/repositories/base.py` lines 13-22; `src/repositories/refund_repo.py` lines 11-20):

```python
class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID, tenant_id: UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == id, self.model.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

Add a small tenant-bound helper only if the new service needs it, for example a UUID case lookup with joined order merchant id. Keep it internal; no router change is required for Phase 47.

**Terminal status clue** (`src/repositories/order_repo.py` lines 24-34):

```python
RefundCase.status.not_in(["refunded", "rejected", "closed"])
```

This is only an existing clue for a first allowlist. The planner must still make terminal statuses explicit and test non-terminal statuses such as `open` and `reviewing`.

### `src/memory/case_memory.py` (service, CRUD + request-response)

**Analog:** existing case-memory service. Prefer no direct edits unless tests prove a narrowing gap.

**Repository insert/event pattern** (`src/memory/case_memory.py` lines 44-122):

```python
async def insert_case_memory(...):
    memory = CaseMemory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
        case_type=candidate.case_type,
        summary=candidate.summary,
        excerpt=candidate.excerpt,
        ...
        source_ref_json=source_ref_json,
        source_identity_hash=source_identity_hash,
        review_status=review_status,
        pii_classification=candidate.pii_classification,
        created_by_run_id=candidate.run_id,
    )
    self.session.add(memory)
    await self.session.flush()
    return memory

async def emit_write_event(...):
    event = MemoryWriteEvent(..., authority_class=authority_class, candidate_hash=candidate_hash)
    self.session.add(event)
    await self.session.flush()
    return event
```

**Duplicate pattern** (`src/memory/case_memory.py` lines 371-405):

```python
base_filters = [
    CaseMemory.tenant_id == tenant_id,
    CaseMemory.scope_type == scope_type,
    CaseMemory.scope_id == scope_id,
    CaseMemory.deleted_at.is_(None),
    CaseMemory.review_status.in_(ACTIVE_CASE_DUPLICATE_REVIEW_STATUSES),
    or_(CaseMemory.expires_at.is_(None), CaseMemory.expires_at > now),
]
...
if duplicate is not None:
    return duplicate, "duplicate_active_source_identity"
```

**Reviewed retrieval filters** (`src/memory/case_memory.py` lines 421-458):

```python
query_filter = _query_text_filter(request.query)
if query_filter is not None:
    filters.append(query_filter)
stmt = (
    select(CaseMemory, score_expr.label("score"))
    .where(*filters)
    .order_by(CaseMemory.updated_at.desc(), CaseMemory.created_at.desc())
)

filters = [
    CaseMemory.tenant_id == request.tenant_id,
    _scope_filter(request),
    CaseMemory.review_status.in_(PUBLISHED_CASE_REVIEW_STATUSES),
    CaseMemory.deleted_at.is_(None),
    or_(CaseMemory.expires_at.is_(None), CaseMemory.expires_at > now),
    CaseMemory.pii_classification.in_(tuple(PROMPT_SAFE_PII_CLASSIFICATIONS)),
    ~self._active_tombstone_exists(now=now),
]
```

This is the metadata-first path. Embeddings stay optional.

**Safe output refs** (`src/memory/case_memory.py` lines 941-971):

```python
return CaseMemorySearchItem(
    case_memory_id=str(memory.id),
    excerpt=memory.excerpt,
    applicability=memory.applicability,
    outcome=memory.outcome,
    caveats=memory.caveats,
    score=score,
    policy_refs=_safe_policy_refs(memory.policy_refs_json or []),
    source_refs=_safe_source_refs(memory.source_ref_json or {}),
)
```

### `src/memory/context_service.py` (service, request-response)

**Analog:** reviewed memory context loader.

**Reviewed service call pattern** (`src/memory/context_service.py` lines 123-216):

```python
trusted = _parse_trusted_context(trusted_context)
if trusted is None:
    return _empty_reviewed_memory_context(..., fallback_reason="missing_trusted_context")

if not trusted.merchant_scope.merchant_ids:
    return _empty_reviewed_memory_context(..., fallback_reason="missing_actor_merchant_scope")

case_result = await self.case_memory_service.retrieve_reviewed(
    CaseMemorySearchRequest(
        tenant_id=tenant_id,
        scopes=service_scopes,
        case_type=case_type,
        query=query,
        now=now,
        limit=limit,
    )
)
```

**Scope verification pattern** (`src/memory/context_service.py` lines 431-485):

```python
explicit_merchant_id = _first_string(current_slots, ("merchant_id",))
business_merchant_id = _trusted_business_merchant_id(trusted_business_context)
denied_merchant_id = _first_denied_merchant(trusted.merchant_scope, [explicit_merchant_id, business_merchant_id])
if denied_merchant_id is not None:
    return _ReviewedMemoryScopeDecision(..., fallback_reason="merchant_scope_denied")

case_id = _first_string(current_slots, ("case_id", "refund_case_id")) or _trusted_business_case_id(...)
if case_id is not None:
    case_merchant_id = business_merchant_id or explicit_merchant_id
    if case_merchant_id is None or not merchant_scope_allows(...):
        filter_reasons.append("case_scope_unverified")
```

If Phase 47 adds assertions here, preserve fail-closed trusted scope behavior.

### `src/tools/executors/memory.py` and `src/tools/catalog.py` (service/config, request-response)

**Analog:** planner-facing reviewed memory tool.

**Executor pattern** (`src/tools/executors/memory.py` lines 32-84):

```python
async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
    if name != "search_case_memory":
        return result("unavailable", ...)
    if self.service is None or not hasattr(self.service, "retrieve_reviewed"):
        return result("unavailable", ...)
    request = _case_memory_request(query=str(args["query"]), context=ctx)
    if request is None:
        return result("invalid_request", ...)
    search_result = await self.service.retrieve_reviewed(request)
    return _case_memory_result(search_result)

scopes: list[tuple[str, str]] = [
    ("tenant", str(tenant_id)),
    ("user", context.user_id),
    ("thread", context.thread_id),
]
merchant_ids = _merchant_ids(context.merchant_scope)
scopes.extend(("merchant", merchant_id) for merchant_id in merchant_ids if merchant_id != "*")
```

**Tool contract red line** (`src/tools/contracts.py` lines 13-37; `docs/contract-spec.md` lines 1222-1239):

```python
class ToolCallContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_context.v2"] = "tool_context.v2"
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    merchant_scope: dict[str, Any] | list[str]
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str
```

Do not add `case_id` to `ToolCallContext`. Case source identity belongs in `source_ref_json`; retrieval scope remains `scope_type/scope_id`.

**Catalog pattern** (`src/tools/catalog.py` lines 439-456):

```python
_ToolDeclaration(
    name="search_case_memory",
    description=(
        "Retrieve reviewed case memory precedents from the reviewed case store. "
        "Returned snippets are contextual only, not policy evidence or action authority."
    ),
    kind="retrieval",
    input_schema={"type": "object", "properties": {"query": {"type": "string", "minLength": 1}}, "required": ["query"]},
    output_schema=_SEARCH_CASE_MEMORY_OUTPUT_SCHEMA,
    side_effect="retrieval",
    caller_allowlist=("investigate",),
    event_family="rag_retrieval_*",
    executor="memory",
)
```

### `docs/contract-spec.md`, `docs/current-implementation-map.md`, `docs/architecture-overview.md` (config, transform)

**Analogs:** existing memory boundary docs.

**Case precedent semantic lock** (`docs/contract-spec.md` lines 1515-1521):

```markdown
Case memory is precedent retrieval for analyst assistance and recommendation context. It never substitutes current business facts, current policy evidence, approval policy, or action safety snapshots. Case memory must not be used as citation, automatic compensation amount authority, approval authorization, current order fact source, or policy evidence.

Semantic lock: `case_memories` / `case_memory` are reviewed precedent, NOT active case state. Active current-case state belongs to Case Working Context.
```

**CWC distinction** (`docs/contract-spec.md` lines 1525-1539):

```markdown
Case Working Context is NOT an `EvidenceRefV1`. It cannot authorize policy/risk/approval/action, cannot satisfy policy or approval evidence requirements, and cannot replace current business facts, authoritative policy evidence, approval policy, action safety snapshots, audit logs, or replay truth.

Case Working Context is distinct from `case_memory`: CWC is the current case's working state, while `case_memories` remains reviewed cross-case precedent. CWC stores user claims and verified facts separately; a claim must never silently become a verified fact.
```

Add Phase 47 closed-case candidate language next to these lines: finalized CWC may be projected into a `needs_review` case-memory candidate only through the review pipeline.

**Storage/retrieval policy pattern** (`docs/contract-spec.md` lines 1586-1591 and 1630-1640):

```markdown
`source_ref_json` must be normalized as typed source identity; `MemorySourceRefV1` allowed keys are fixed, unknown keys are rejected, and unknown keys must not participate in identity hash.

Case retrieval predicate: `deleted_at is null`, `review_status in ('auto_approved','approved')`, not tombstoned/rejected/prohibited/expired.
```

**Implementation map pattern** (`docs/current-implementation-map.md` lines 37-38 and 162):

```markdown
`search_case_memory` is served by `MemoryToolExecutor -> CaseMemoryService.retrieve_reviewed(...)`; it uses reviewed case memory and not legacy session precedent search.
```

**Architecture overview pattern** (`docs/architecture-overview.md` lines 483-496):

```markdown
Case memory: historical similar case, treatment, approval result, outcome; reviewed precedent only. Planner-facing `search_case_memory` uses reviewed case memory. Memory is auxiliary context, not policy basis.
```

### `tests/memory/test_phase47_case_precedent_alignment.py` (test, transform)

**Analog:** Phase 45/46 static alignment tests.

**No CWC/case-memory backfill pattern** (`tests/memory/test_phase45_contract_alignment.py` lines 136-145):

```python
def test_phase45_cwc_lifecycle_has_no_case_memories_backfill() -> None:
    source = "\n".join((_source(LIFECYCLE_PATH), _source(FINALIZER_PATH)))

    for token in (
        "CaseMemoryRepository",
        "CaseMemoryService",
        "case_memories",
        "search_case_memory",
    ):
        assert token not in source
```

For Phase 47, invert narrowly: the new `case_precedent.py` may import `CaseMemoryService`, but CWC lifecycle/finalizer must still not generate case precedents from completed runs.

**Protected schema guard pattern** (`tests/memory/test_phase45_contract_alignment.py` lines 177-198; `tests/memory/test_phase46_session_context_alignment.py` lines 155-166):

```python
for term in (
    '__tablename__ = "case_memories"',
    '__tablename__ = "long_term_memories"',
    "ConversationThread.case_id",
    "ix_conversation_threads_case_id",
):
    assert term in models

for pattern in (
    r"drop_table\(['\"]case_memories['\"]",
    r"drop_table\(['\"]long_term_memories['\"]",
    r"drop_column\(['\"]conversation_threads['\"],\s*['\"]case_id['\"]",
    r"rename_table\(['\"]case_memories['\"]",
):
    assert re.search(pattern, phase45_surface) is None
```

Extend the protected set to include `case_working_contexts` and prevent destructive Phase 47 migrations/plans.

**Forbidden authority-import pattern** (`tests/memory/test_phase46_session_context_alignment.py` lines 180-198):

```python
forbidden_tokens = (
    "EvidenceRefV1",
    "BusinessFactRefV1(",
    "ApprovalRequest",
    "ApprovalDecision",
    "ActionDraft",
    "ReplayEvent",
    "ReplayTruth",
)
violations = [token for token in forbidden_tokens if token in checked_source]
assert violations == []
```

Apply this to `src/memory/case_precedent.py` and its projection tests; include raw payload/body tokens.

**Approved pytest-entrypoint pattern** (`tests/memory/test_phase46_session_context_alignment.py` lines 61-78 and 258-266):

```python
def _pytest_command_snippets(path: Path) -> list[str]:
    snippets: list[str] = []
    for line in _source(path).splitlines():
        stripped = line.strip()
        if _is_pytest_prose(stripped):
            continue
        automated_match = re.search(r"<automated>(.*?)</automated>", stripped)
        if automated_match and "pytest" in automated_match.group(1):
            snippets.append(automated_match.group(1).strip())
            continue
        if re.match(r"^(?:UV_CACHE_DIR=\S+\s+)?(?:uv run pytest|pytest|python -m pytest)\b", stripped):
            snippets.append(stripped)
            continue
    return snippets

for path, snippet in snippets:
    assert snippet.startswith("UV_CACHE_DIR=/tmp/uv-cache uv run pytest"), (path, snippet)
```

### `tests/memory/test_case_precedent_generation.py` (test, CRUD + request-response + transform)

**Analog:** `tests/memory/test_case_memory_retrieval.py` + `tests/agent/test_case_working_context_lifecycle.py`.

**Fixture/candidate style** (`tests/memory/test_case_memory_retrieval.py` lines 21-94):

```python
async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str = "case-memory") -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(AgentRun(..., final_status="completed", started_at=datetime.now(UTC)))
    await session.flush()
    return run_id

def _candidate(..., source_type: str = "llm_candidate", ...) -> CaseMemoryWriteCandidate:
    refund_case = seeded_session["refund_case"]
    return CaseMemoryWriteCandidate(
        tenant_id=refund_case.tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id=str(refund_case.id),
        case_type="refund_dispute",
        summary=summary,
        excerpt=excerpt,
        source_type=source_type,
        source_ref=source_ref or _source_ref(...),
        policy_refs=[{"doc_key": "refund_policy", "chunk_id": "chunk-1", "policy_version": "v1"}],
        pii_classification=pii_classification,
    )
```

For Phase 47, use active CWC rows and terminal close inputs rather than constructing the final candidate directly.

**Review-before-retrieval behavior** (`tests/memory/test_case_memory_retrieval.py` lines 151-207):

```python
result = await service.submit_case_memory_candidate(candidate)
before_approval = await service.retrieve_reviewed(CaseMemorySearchRequest(...))
approved_event = await service.approve_case_memory(CaseMemoryReviewDecision(...))
after_approval = await service.retrieve_reviewed(CaseMemorySearchRequest(...))

assert result.status == "needs_review"
assert result.review_status == "needs_review"
assert before_approval.items == []
assert [item.case_memory_id for item in after_approval.items] == [str(row.id)]
assert approved_event.decision == "write"
```

Copy this for closed-case candidates.

**Duplicate and PII behavior** (`tests/memory/test_case_memory_retrieval.py` lines 267-344):

```python
first = await service.submit_case_memory_candidate(candidate)
duplicate = await service.submit_case_memory_candidate(candidate)

assert duplicate.status == "skipped"
assert duplicate.memory_id == first.memory_id
assert duplicate.reason_code == "duplicate_active_identity"

@pytest.mark.parametrize("pii_classification", ["sensitive", "prohibited"])
async def test_blocked_pii_case_memory_candidate_is_skipped_and_evented(...):
    result = await service.submit_case_memory_candidate(candidate)
    assert result.status == "skipped"
    assert result.reason_code == "pii_blocked"
```

Closed-case tests should cover duplicate close event / same CWC version using source identity as well as content hash.

**Prompt-safe projection tests** (`tests/agent/test_case_working_context_lifecycle.py` lines 368-447 and 453-474):

```python
assert [fact.text for fact in projection.candidate.content.verified_facts] == [
    "refund status summary",
    "order delivered summary",
]
projected = repr(projection.candidate.content.model_dump(mode="json"))
assert "raw_payload should not leak" not in projected
assert "full policy evidence text should not leak" not in projected

@pytest.mark.parametrize(("text", "expected"), [...])
def test_project_terminal_write_candidate_classifies_pii_deterministically(text: str, expected: str) -> None:
    assert projection.candidate.pii_classification == expected
```

Use the same style for closed-case projection output.

### `tests/memory/test_memory_policy.py` (test, transform)

**Analog:** existing source-type policy tests.

**Add closed-case source type to review-required cases** (`tests/memory/test_memory_policy.py` lines 79-88 and 112-146):

```python
assert case_memory_review_status_for_source("deterministic_tool_result") == "needs_review"
assert case_memory_review_status_for_source("confirmed_business_outcome") == "needs_review"
assert case_memory_review_status_for_source("approved_approval_state") == "needs_review"
assert case_memory_review_status_for_source("llm_candidate") == "needs_review"
assert case_memory_policy_decision("deterministic_tool_result").decision == "needs_review"
```

Add `closed_case_cwc_candidate` to this test and to the fake-repository service test so insert kwargs and event kwargs show `review_status == "needs_review"` and `decision == "needs_review"`.

### `tests/memory/test_case_memory_retrieval.py` (test, request-response)

**Analog:** existing retrieval exclusion and metadata/text tests.

**Metadata exclusion pattern** (`tests/memory/test_case_memory_retrieval.py` lines 385-456):

```python
filtered_rows = [
    _case_row(..., review_status="needs_review"),
    _case_row(..., review_status="rejected"),
    _case_row(..., deleted_at=now),
    _case_row(..., expires_at=now - timedelta(seconds=1)),
    _case_row(..., pii_classification="sensitive"),
    _case_row(..., pii_classification="prohibited"),
    _case_row(..., tenant_id=other_tenant_id),
]
result = await CaseMemoryRepository(session).search_reviewed(
    CaseMemorySearchRequest(
        tenant_id=tenant_id,
        scope_type="case",
        scope_id=scope_id,
        case_type="refund_dispute",
        policy_family="refund",
        policy_version="v1",
        query_embedding=_embedding(),
        limit=10,
    )
)
```

Add generated closed-case rows to the same exclusion pattern if not fully covered by the new generation test.

**Text-only retrieval pattern** (`tests/memory/test_case_memory_retrieval.py` lines 490-503):

```python
result = await CaseMemoryRepository(session).search_reviewed(
    CaseMemorySearchRequest(
        tenant_id=tenant_id,
        scope_type="case",
        scope_id=scope_id,
        case_type="refund_dispute",
        policy_family="refund",
        policy_version="v1",
        query="payment-channel timeout",
        limit=10,
    )
)
assert [item.case_memory_id for item in result.items] == [str(matching.id)]
```

Use this for metadata-first merchant and exact case-scope retrieval without embeddings.

### `tests/memory/test_reviewed_memory_context_boundary.py` (test, request-response)

**Analog:** reviewed prompt-context boundary tests.

**Merchant-scoped case candidate pattern** (`tests/memory/test_reviewed_memory_context_boundary.py` lines 125-150):

```python
def _case_candidate(..., merchant_id: str, summary: str, source_type: str = "human_reviewed") -> CaseMemoryWriteCandidate:
    return CaseMemoryWriteCandidate(
        tenant_id=seeded_session["tenant"].id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=merchant_id,
        case_type="refund_dispute",
        summary=summary,
        excerpt=f"{summary} excerpt.",
        applicability="Applies only to the scoped merchant.",
        outcome="Contextual precedent only.",
        caveats="Not policy evidence or current business fact authority.",
        source_type=source_type,
        source_ref={
            "source_type": source_type,
            "run_id": str(run_id),
            "business_object_type": "merchant",
            "business_object_id": merchant_id,
        },
```

**Needs-review exclusion pattern** (`tests/memory/test_reviewed_memory_context_boundary.py` lines 448-514):

```python
case_result = await case_service.submit_case_memory_candidate(
    _case_candidate(..., summary="Needs-review case memory must stay out of reviewed prompt context.", source_type="llm_candidate")
)
retrieved_cases = await case_service.retrieve_reviewed(
    CaseMemorySearchRequest(
        tenant_id=tenant_id,
        scope_type="merchant",
        scope_id=merchant_a,
        case_type="refund_dispute",
        query="Needs-review case memory",
    )
)
assert case_decision["status"] == "needs_review"
assert retrieved_cases.items == []
```

Use this for generated closed-case candidates.

### `tests/test_memory_review_api.py` (test, request-response)

**Analog:** existing pending-review/reviewer API tests.

**Pending/review API pattern** (`tests/test_memory_review_api.py` lines 84-145):

```python
case_result = await CaseMemoryService(CaseMemoryRepository(session)).submit_case_memory_candidate(
    _case_candidate(seeded_session, run_id=run_id)
)
await session.commit()

response = await client.get(
    "/api/v1/memory/review/pending",
    headers=_auth_header(manager, ["approvals:review"]),
)
assert ("case", str(case_result.memory_id)) in {
    (item["memory_type"], item["memory_id"]) for item in response.json()["data"]["items"]
}

reject_response = await client.post(
    f"/api/v1/memory/case/{case_result.memory_id}/reject",
    json={"run_id": str(run_id), "review_reason": "not durable enough"},
    headers=_auth_header(manager, ["approvals:review"]),
)
assert reject_response.json()["data"]["decision"] == "skip"
```

Only extend API tests if the generated source type needs explicit pending-review API coverage.

### `tests/agent/test_reviewed_memory_context_retrieve.py` (test, request-response)

**Analog:** reviewed memory node fail-closed scope tests.

**Fail-closed trusted scope pattern** (`tests/agent/test_reviewed_memory_context_retrieve.py` lines 124-221):

```python
class NoCallCaseMemoryService:
    async def retrieve_reviewed(self, request: Any) -> Any:
        raise AssertionError("missing actor merchant scope must not query case memory")

trusted_context = _trusted_context(merchant_ids=[])
result = await reviewed_memory_context_retrieve(..., {"configurable": {"trusted_context": trusted_context}})
memory_context = _assert_empty_context_bundle(result, fallback_reason="missing_actor_merchant_scope")

result = await reviewed_memory_context_retrieve(
    _state(extracted_slots={"merchant_id": "merchant-b"}),
    {"configurable": {"trusted_context": _trusted_context(merchant_ids=["merchant-a"])}},
)
_assert_empty_context_bundle(result, fallback_reason="merchant_scope_denied")
```

Use this style if Phase 47 adds tests around generated merchant-scope precedents in reviewed memory context.

### `tests/tools/test_catalog.py` (test, request-response)

**Analog:** tool descriptor/schema tests.

**ToolCallContext fixture red line** (`tests/tools/test_catalog.py` lines 57-70):

```python
def _context() -> ToolCallContext:
    return ToolCallContext(
        tenant_id="tenant-1",
        user_id="user-1",
        role="support_agent",
        permissions=["tool:get_order"],
        merchant_scope={"merchant_ids": ["*"]},
        thread_id="thread-1",
        run_id="run-1",
        trace_id="trace-1",
        request_id="request-1",
        tool_call_id="tool-call-1",
        caller_node="investigate",
    )
```

Do not add `case_id`.

**Descriptor/contextual-only pattern** (`tests/tools/test_catalog.py` lines 338-343):

```python
def test_search_case_memory_descriptor_names_reviewed_case_memory_store() -> None:
    descriptor = _descriptor("search_case_memory")

    assert "reviewed case memory" in descriptor.description
    assert "reviewed case store" in descriptor.description
    assert "session-derived" not in descriptor.description.lower()
```

**Raw payload rejection pattern** (`tests/tools/test_catalog.py` lines 429-506):

```python
("search_case_memory", {"items": [_valid_case_memory_item()]}),
...
(
    "search_case_memory",
    {"items": [{**_valid_case_memory_item(), "raw_tool_payload": "must-not-pass"}]},
),
...
with pytest.raises((TypeError, ValueError)):
    _validate_json_value(payload, _descriptor(name).output_schema)
```

If Phase 47 changes search output schema, preserve raw-payload rejection.

## Shared Patterns

### Existing Review Pipeline Is Mandatory

**Source:** `src/memory/case_memory.py` lines 490-620
**Apply to:** `src/memory/case_precedent.py`, `tests/memory/test_case_precedent_generation.py`

Closed-case generation must end by calling `CaseMemoryService.submit_case_memory_candidate(...)`. It must not directly insert `CaseMemory` or create a second review/audit queue.

### Closed-Case Source Type Must Be Review-Required

**Source:** `src/memory/policy.py` lines 71-88 and 150-174
**Apply to:** `src/memory/schemas.py`, `src/memory/policy.py`, `tests/memory/test_memory_policy.py`

`closed_case_cwc_candidate` belongs in `REVIEW_REQUIRED_CASE_SOURCE_TYPES`; it must not be auto-approved. Existing `human_reviewed` and `explicit_admin_preference` remain the only auto-approved case sources.

### Retrieval Scope Is Separate From Source Identity

**Source:** `src/db/models.py` lines 508-543; `src/memory/identity.py` lines 19-57; `src/tools/executors/memory.py` lines 71-84
**Apply to:** `src/memory/case_precedent.py`, retrieval tests, tool tests

Use `CaseMemory.scope_type/scope_id` for retrieval, preferably `merchant` when `RefundCase -> Order.merchant_id` is resolvable. Put the source refund case identity in `source_ref_json.business_object_type/business_object_id`.

### Prompt-Safe Projection Only

**Source:** `src/memory/case_working_context_lifecycle.py` lines 461-492; `tests/agent/test_case_working_context_lifecycle.py` lines 368-447
**Apply to:** `src/memory/case_precedent.py`, `tests/memory/test_phase47_case_precedent_alignment.py`

Projection may use summaries and identifiers. It must not serialize raw tool payloads, policy body text, replay/debug blobs, approval/action authority bodies, or sensitive raw PII.

### Metadata-First Retrieval

**Source:** `src/memory/case_memory.py` lines 421-458 and 854-900
**Apply to:** `tests/memory/test_case_precedent_generation.py`, `tests/memory/test_case_memory_retrieval.py`

Keep `query_embedding=None` tests for exact tenant/scope/case type/policy/text retrieval. Embeddings remain optional.

### Tool Contract Must Not Be Widened

**Source:** `src/tools/contracts.py` lines 13-37; `docs/contract-spec.md` lines 1222-1239
**Apply to:** `src/tools/executors/memory.py`, `tests/tools/test_catalog.py`, static alignment tests

Do not add `case_id` to `ToolCallContext`. Planner-facing case memory search should retrieve tenant/user/thread/merchant scopes from trusted tool context.

### No Destructive Schema Changes

**Source:** `src/db/models.py` lines 508-688 and 1213-1252; static test analogs from Phase 45/46
**Apply to:** all plans

Do not rename/drop/retype `case_memories`, `long_term_memories`, `case_working_contexts`, or `conversation_threads.case_id`. No migration should perform destructive operations on these names in Phase 47.

### Approved Verification Entrypoint

**Source:** `AGENTS.md` local verification rule; `tests/memory/test_phase46_session_context_alignment.py` lines 258-266
**Apply to:** every Phase 47 plan/test command

Every automated command must use:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...
```

Bare pytest and bare python -m pytest are invalid verification in MOCA.

## No Analog Found

| File/Capability | Role | Data Flow | Reason |
|---|---|---|---|
| Trusted refund-case close-transition service | service | event-driven/request-response | Current code has a read-only refund-case router and no close-transition service. Build only an internal generation seam in `src/memory/case_precedent.py`; do not invent a public close endpoint. |

## Metadata

**Analog search scope:** `src/memory`, `src/tools`, `src/repositories`, `src/api/routers`, `src/api/services`, `src/db/models.py`, `tests/memory`, `tests/agent`, `tests/tools`, `docs`.

**Files scanned:** 60+ via `rg --files` and targeted `rg` queries.

**Pattern extraction date:** 2026-07-03

**Planner high-risk reminders:**
- Do not infer closure from `AgentRun.final_status == "completed"`.
- Do not widen `ToolCallContext` with `case_id`.
- Do not implement Phase 48 long-term preference memory here.
- Do not let generated candidates appear in `retrieve_reviewed(...)`, reviewed memory context, or `search_case_memory` before approval.
- Do not use arbitrary source-ref keys unless `MemorySourceRefV1` and `ALLOWED_SOURCE_REF_KEYS` are extended together.
