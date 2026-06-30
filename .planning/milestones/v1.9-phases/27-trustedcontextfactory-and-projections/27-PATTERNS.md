# Phase 27: TrustedContextFactory and Projections - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 22 likely new/modified files
**Analogs found:** 22 / 22 (1 composite factory analog; no single existing runtime factory)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/platform/__init__.py` | config | transform | `src/agent/context/__init__.py` | exact |
| `src/platform/trusted_context.py` | model/service | request-response, transform | `src/tools/contracts.py` + `src/api/routers/agent_runs.py` | composite |
| `src/platform/context_projections.py` | utility/service | transform | `src/tools/executors/knowledge.py` | exact |
| `src/agent/intent_policy.py` | utility | transform, request-response | `src/agent/intent_policy.py` | exact-self |
| `src/api/routers/search.py` | route | request-response | `src/api/routers/search.py` | exact-self |
| `src/api/routers/agent.py` | route | request-response | `src/api/routers/agent.py` | exact-self |
| `src/api/routers/agent_runs.py` | route | streaming, request-response | `src/api/routers/agent_runs.py` | exact-self |
| `src/agent/nodes/investigate.py` | service | event-driven, transform | `src/agent/nodes/investigate.py` | exact-self |
| `src/agent/nodes/action_draft.py` | service | event-driven, transform | `src/agent/nodes/action_draft.py` | exact-self |
| `src/tools/executors/knowledge.py` | service | transform, request-response | `src/tools/executors/knowledge.py` | exact-self |
| `src/knowledge/schemas.py` | model | transform | `src/knowledge/schemas.py` | exact-self |
| `tests/platform/test_trusted_context.py` | test | transform | `tests/agent/test_tools/test_tool_contracts.py` | role-match |
| `tests/platform/test_trusted_context_factory.py` | test | request-response | `tests/test_agent_runs_api.py` | role-match |
| `tests/platform/test_merchant_scope.py` | test | transform | `tests/agent/test_tools/test_unified_tool_manager.py` | role-match |
| `tests/platform/test_context_projections.py` | test | transform | `tests/agent/test_tools/test_unified_tool_manager.py` | role-match |
| `tests/agent/test_intent_policy_registry.py` | test | transform | `tests/agent/test_intent_golden_contract.py` | role-match |
| `tests/architecture/test_trusted_context_boundaries.py` | test | static boundary | `tests/architecture/test_tool_boundaries.py` | exact |
| `tests/test_search_integration.py` | test | request-response | `tests/test_search_integration.py` | exact-self |
| `tests/test_agent_runs_api.py` | test | streaming, request-response | `tests/test_agent_runs_api.py` | exact-self |
| `tests/agent/test_nodes/test_investigate.py` | test | event-driven, transform | `tests/agent/test_nodes/test_investigate.py` | exact-self |
| `tests/agent/test_tools/test_unified_tool_manager.py` | test | transform | `tests/agent/test_tools/test_unified_tool_manager.py` | exact-self |
| `tests/knowledge/test_tenant_scope.py` | test | request-response | `tests/knowledge/test_tenant_scope.py` | exact-self |

## Pattern Assignments

### `src/platform/__init__.py` (config, transform)

**Analog:** `src/agent/context/__init__.py`

**Package export pattern** (lines 1-29):
```python
"""Prompt-safe context assembly boundary."""

from src.agent.context.assembler import ContextAssembler
from src.agent.context.budget import PromptAssembly, PromptBlock, TokenBudgetPolicy
from src.agent.context.projectors import (
    project_business_context_for_prompt,
    project_candidate_slot_hints_for_prompt,
    project_case_memory_for_prompt,
    project_policy_refs_for_prompt,
    project_profile_memory_for_prompt,
    project_recent_message_for_prompt,
    project_tool_result_summary,
    project_working_state_for_prompt,
)

__all__ = [
    "ContextAssembler",
    "PromptAssembly",
    "PromptBlock",
    "TokenBudgetPolicy",
    "project_business_context_for_prompt",
    "project_candidate_slot_hints_for_prompt",
    "project_case_memory_for_prompt",
    "project_policy_refs_for_prompt",
    "project_profile_memory_for_prompt",
    "project_recent_message_for_prompt",
    "project_tool_result_summary",
    "project_working_state_for_prompt",
]
```

**Apply:** keep `src/platform/__init__.py` as a narrow public export list. Export only stable contracts/factory/projection helpers; do not import routers, graph nodes, services, or prompt projectors.

---

### `src/platform/trusted_context.py` (model/service, request-response + transform)

**Analog:** composite of strict contract models, auth request state, trusted tool config, and merchant-scope helper.

**Strict Pydantic contract pattern** from `src/tools/contracts.py` (lines 5-8, 13-37):
```python
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    request_id: str
    tool_call_id: str
    caller_node: str
    deadline_at: datetime | None = None
    effective_at: str | None = None
    attempt: int = 1
    max_attempts: int = 1
    idempotency_key: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None
    policy_snapshot_ref: str | None = None
```

**Copy rule:** `TrustedContext` should copy the `BaseModel` + `ConfigDict(extra="forbid")` + `Literal[...]` style, but its canonical fields must be only the Phase 27 D-01 fields. Do not copy tool-local fields into canonical context.

**Trusted auth input pattern** from `src/auth/permissions.py` (lines 60-74):
```python
# Validate scopes claim is a collection of strings before preservation
raw_scopes = payload.get("scopes", [])
if not isinstance(raw_scopes, list) or not all(isinstance(s, str) for s in raw_scopes):
    raise credentials_error

token_scopes = set(raw_scopes)
missing_scopes = [scope for scope in security_scopes.scopes if scope not in token_scopes]
if missing_scopes:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": FORBIDDEN, "message": "Insufficient scopes", "details": {"missing_scopes": missing_scopes}},
    )

# Preserve verified token scopes in trusted request context (immutable)
request.state.verified_token_scopes = frozenset(token_scopes)
```

**Factory permission/scope derivation pattern** from `src/api/routers/agent_runs.py` (lines 68-82):
```python
def _trusted_tool_config(user: User, token_scopes: Iterable[str], trace_id: str | None) -> dict[str, Any]:
    # Intersect verified token scopes with current DB role scopes
    trusted_scopes = set(token_scopes) & set(ROLE_SCOPES.get(user.role, []))
    permissions = [
        tool_permission for scope, tool_permission in SCOPE_TO_TOOL_PERMISSION.items() if scope in trusted_scopes
    ]
    if user.role == "merchant":
        merchant_scope = {"merchant_ids": [str(user.merchant_id)] if user.merchant_id is not None else []}
    else:
        merchant_scope = {"merchant_ids": ["*"]}
    return {
        "permissions": permissions,
        "merchant_scope": merchant_scope,
        "trace_id": trace_id or "",
    }
```

**Request/run id source pattern** from `src/api/main.py` (lines 52-60):
```python
@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    request.state.trace_id = str(uuid.uuid4())
    request.state.run_id = str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Trace-Id"] = request.state.trace_id
    response.headers["X-Run-Id"] = request.state.run_id
    response.headers["X-Latency-Ms"] = str(round((time.perf_counter() - start) * 1000))
```

**MerchantScopeV1 semantics pattern** from `src/business/service.py` (lines 62-90):
```python
def _merchant_scope_allows(
    merchant_scope: dict[str, Any] | None,
    *,
    merchant_id: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
) -> bool:
    """Apply deny-first, all-provided-dimensions merchant-scope matching."""

    if not merchant_scope:
        return False

    merchant_ids = merchant_scope.get("merchant_ids")
    if not isinstance(merchant_ids, list) or not merchant_ids:
        return False

    dimensions = (
        (merchant_id, merchant_ids),
        (category, merchant_scope.get("categories")),
        (risk_level, merchant_scope.get("risk_levels")),
    )
    for value, allowed in dimensions:
        if value is None:
            continue
        if not isinstance(allowed, list) or not allowed:
            return False
        if "*" not in allowed and value not in allowed:
            return False
    return True
```

**Factory tests to copy from** `tests/test_agent_runs_api.py` (lines 1840-1900):
```python
from unittest.mock import MagicMock
from src.api.routers.agent_runs import _trusted_tool_config

user = MagicMock()
user.role = "support"

config = _trusted_tool_config(user, token_scopes=["agent:chat", "orders:read"], trace_id="test-trace")
assert config["permissions"] == ["tool:get_order"]

user = MagicMock()
user.role = "merchant"
user.merchant_id = None

config = _trusted_tool_config(user, token_scopes=["agent:chat"], trace_id="test-trace")

assert config["merchant_scope"]["merchant_ids"] == []

merchant_id = uuid4()
user = MagicMock()
user.role = "merchant"
user.merchant_id = merchant_id

config = _trusted_tool_config(user, token_scopes=ROLE_SCOPES["merchant"], trace_id="trace-merchant")

assert config["merchant_scope"]["merchant_ids"] == [str(merchant_id)]
assert "tool:get_order" in config["permissions"]
assert config["trace_id"] == "trace-merchant"

config = _trusted_tool_config(
    user,
    token_scopes=["orders:read", "refunds:read", "tickets:read", "knowledge:read", "agent:chat"],
    trace_id="test-trace",
)
assert set(config["permissions"]) == {
    "tool:get_order",
    "tool:get_refund_case",
    "tool:get_ticket",
    "tool:search_policy",
}
```

**Apply:** build the factory from authenticated `User`, verified token scopes, server-created ids, locale, and server-derived merchant scope. Tests must include spoofed request/model/checkpoint fields and assert they cannot widen tenant/user/role/permissions/merchant scope.

---

### `src/platform/context_projections.py` (utility/service, transform)

**Analog:** `src/tools/executors/knowledge.py`, `src/tools/contracts.py`, `src/knowledge/schemas.py`, `src/approvals/schemas.py`, `src/replay/schemas.py`, `src/memory/session_bundle.py`.

**Tool projection target** from `src/tools/contracts.py` (lines 13-37):
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
    request_id: str
    tool_call_id: str
    caller_node: str
    deadline_at: datetime | None = None
    effective_at: str | None = None
    attempt: int = 1
    max_attempts: int = 1
    idempotency_key: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None
    policy_snapshot_ref: str | None = None
```

**Knowledge projection pattern** from `src/tools/executors/knowledge.py` (lines 39-66, 102-108):
```python
effective_at = ctx.effective_at or datetime.now(UTC).isoformat()
request = KnowledgeSearchRequest(
    query=str(args["query"]),
    primary_intent=args.get("primary_intent"),
    filters=KnowledgeSearchFilters(
        tenant_id=ctx.tenant_id,
        merchant_id=args.get("merchant_id"),
        effective_at=effective_at,
        locale=None,
    ),
    retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
    rerank_config_version=RERANK_CONFIG_VERSION,
    max_results=int(args.get("max_results") or 5),
    allow_partial_evidence=bool(args.get("allow_partial_evidence", True)),
)
search_result = await self.service.search(
    request,
    KnowledgeContext(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        role=ctx.role,
        merchant_scope=_knowledge_merchant_scope(ctx.merchant_scope),
        run_id=ctx.run_id,
        trace_id=ctx.trace_id,
        locale=None,
        effective_at=effective_at,
    ),
)

def _knowledge_merchant_scope(value: object) -> list[str]:
    raw_ids: object = value.get("merchant_ids") if isinstance(value, dict) else value
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    if not all(isinstance(item, str) and item for item in raw_ids):
        return []
    return list(raw_ids)
```

**Memory identity projection pattern** from `src/memory/session_bundle.py` (lines 21-30):
```python
async def load_session_memory_bundle(
    self,
    *,
    tenant_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    thread_id: str,
    run_id: uuid.UUID | str,
    current_intent: str | None,
    max_recent_messages: int = 8,
) -> SessionMemoryBundle:
```

**Approval strict-context pattern** from `src/approvals/schemas.py` (lines 29-55, 75-105, 126-153):
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

class ApprovalDecisionCommand(BaseModel):
    """Trusted server-side decision command for one request/level/assignment binding."""

    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    thread_id: str = Field(min_length=1)
    actor_id: UUID
    actor_role: str = Field(min_length=1)

class TrustedApprovalResultV1(BaseModel):
    """Trusted graph resume payload produced only by ApprovalService."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["approval_result.v1"] = APPROVAL_RESULT_SCHEMA_VERSION
    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    status: ApprovalRequestStatus
    decision_type: ApprovalDecisionType
```

**Replay strict metadata pattern** from `src/replay/schemas.py` (lines 37-59):
```python
class ReplayEventV3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["replay_event.v3"] = "replay_event.v3"
    event_id: UUID
    run_id: UUID
    tenant_id: UUID
    thread_id: str = Field(min_length=1)
    trace_id: str | None = None
    sequence: int = Field(gt=0)
    event_type: str
    occurred_at: datetime
    operation_id: UUID | None = None
    parent_operation_id: UUID | None = None
    attempt: int | None = Field(default=None, gt=0)
    node_name: str | None = None
    actor: dict[str, Any]
    resource_refs: dict[str, Any]
    redacted_payload: dict[str, Any]
    redaction_policy_version: str = Field(min_length=1)
    provenance: ReplayEventProvenance
    retention: ReplayRetention
    error: ReplayError | None = None
```

**Apply:** projection methods should accept canonical `TrustedContext` plus explicit local metadata args. Identity/scope fields should always come from canonical context; `request_id`, `tool_call_id`, `effective_at`, `channel`, approval refs, version refs, and artifact refs stay on returned projection objects or metadata models.

---

### `src/knowledge/schemas.py` (model, transform)

**Analog:** existing `KnowledgeContext`.

**Current schema to preserve or migrate deliberately** (lines 18-29):
```python
class KnowledgeContext(BaseModel):
    """TrustedContext projection fields plus run-derived effective_at."""

    tenant_id: str
    user_id: str
    role: str
    merchant_scope: list[str] | None = None
    run_id: str
    trace_id: str
    locale: str | None = None
    effective_at: str
```

**Knowledge service authorization pattern** from `src/knowledge/service.py` (lines 111-119):
```python
# Merchant filters are authorization inputs only until policy rows gain
# merchant scope. Deny before adapter execution rather than widening an
# unauthorized request into an unfiltered tenant search.
merchant_id = request.filters.merchant_id
merchant_scope = context.merchant_scope
if not merchant_scope:
    return self._no_evidence_result()
if merchant_id is not None and "*" not in merchant_scope and merchant_id not in merchant_scope:
    return self._no_evidence_result()
```

**Apply:** if `KnowledgeContext.merchant_scope` remains `list[str] | None`, centralize the canonical-to-list adapter in `context_projections.py`. If changing it to `MerchantScopeV1`, migrate `PolicyKnowledgeService`, `_scope_reason_codes`, and all knowledge tests in the same task.

---

### `src/agent/intent_policy.py` (utility, transform + request-response)

**Analog:** same file; wrap existing constants without changing routing behavior.

**Read-only source data pattern** (lines 15-24, 36-40, 112-132):
```python
@dataclass(frozen=True)
class IntentDefinition:
    name: IntentLiteral
    required_slots: RequiredSlotExpression
    initial_route: IntentRouteLiteral
    precedence: int
    direct_response: bool = False
    evidence_required: bool = True
    high_risk: bool = False
    critical_route_class: bool = False

INTENT_DEFINITIONS: dict[str, IntentDefinition] = {
    "policy_qa": IntentDefinition(
        name="policy_qa",
        required_slots=RequiredSlotExpression(),
        initial_route="investigate",

ORDINARY_INTENTS: tuple[str, ...] = tuple(INTENT_DEFINITIONS)
REQUIRED_SLOT_POLICY: dict[str, RequiredSlotExpression] = {
    name: definition.required_slots for name, definition in INTENT_DEFINITIONS.items()
}
PRECEDENCE_INTENTS: tuple[str, ...] = tuple(
    name for name, _definition in sorted(INTENT_DEFINITIONS.items(), key=lambda item: item[1].precedence)
)
INTENT_ROUTE_POLICY: dict[str, IntentRouteLiteral] = {
    name: definition.initial_route for name, definition in INTENT_DEFINITIONS.items()
}
DIRECT_RESPONSE_INTENTS = {name for name, definition in INTENT_DEFINITIONS.items() if definition.direct_response}
EVIDENCE_REQUIRED_INTENTS = {name for name, definition in INTENT_DEFINITIONS.items() if definition.evidence_required}
HIGH_RISK_INTENTS = {name for name, definition in INTENT_DEFINITIONS.items() if definition.high_risk}
```

**Routing semantics to preserve** (lines 194-232, 258-289):
```python
def resolve_intent_precedence(
    primary_intent: str,
    requested_operation: str,
    query: str,
    secondary_intents: list[str] | None = None,
) -> tuple[str, str, list[str]]:
    candidates = [primary_intent, *(secondary_intents or [])]
    ...
    for intent in PRECEDENCE_INTENTS:
        if intent in valid_candidates:
            reason_codes = [] if intent == primary_intent else ["intent_precedence_applied"]
            return intent, _operation_for_selected_intent(intent, requested_operation), reason_codes
    return "unsupported", "advise", ["unsupported_intent"]

def resolve_risk_tier(
    primary_intent: str,
    requested_operation: str,
    role: str | None = None,
    channel: str | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> RiskTierLiteral:
    """Resolve ordinary-chat safety tier from effective policy state.

    The role is accepted for policy expansion but does not grant chat approval
    authority in this phase.
    """
    del role
    hints = routing_hints or {}
    effective_channel = channel or str(hints.get("channel") or "ordinary_chat")
    ...
    return "read_only"
```

**Apply:** add `IntentPolicyRegistry` / `SlotPolicyRegistry` as read-only wrappers over these constants. Return tuples or copies for collection APIs so callers cannot mutate source dicts. Do not alter `resolve_intent_precedence`, `resolve_risk_tier`, or graph routing semantics.

---

### `src/api/routers/search.py` (route, request-response)

**Analog:** same router plus factory/auth patterns.

**Current direct construction seam to replace** (lines 21-44):
```python
@router.post("/", response_model=ApiResponse)
async def search_knowledge_base(
    body: SearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["knowledge:read"]),
) -> ApiResponse:
    """Search knowledge base for relevant policy chunks. Scoped to user's tenant."""
    engine = PolicyRetrievalEngine(session, embedder=EmbeddingService())
    status, hits, best_score = await engine.retrieve_hits(
        query=body.query,
        context=KnowledgeContext(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            role=user.role,
            merchant_scope=["*"],
            run_id="api-search",
            trace_id=request.state.trace_id,
            effective_at=datetime.now(UTC).isoformat(),
        ),
        max_results=body.top_k,
        doc_type=body.doc_type,
        risk_level=body.risk_level,
    )
```

**Integration test pattern** from `tests/test_search_integration.py` (lines 62-87):
```python
async def _post_search(client, auth_headers, query: str, username: str = "cs_zhang"):
    return await client.post(
        "/api/v1/search/",
        json={"query": query, "top_k": 5},
        headers=await auth_headers(username),
    )

@pytest.mark.asyncio
async def test_search_requires_auth(client):
    """Search without auth token returns 401."""
    response = await client.post("/api/v1/search/", json={"query": "test"})
    payload = response.json()

    assert response.status_code == 401
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNAUTHORIZED"
```

**Apply:** keep the FastAPI dependency pattern, but replace inline `KnowledgeContext(...)` with `TrustedContextFactory` plus `project_to_knowledge_context(effective_at=...)`. Do not use request body fields as identity/scope authority.

---

### `src/api/routers/agent.py` (route, request-response)

**Analog:** same router plus `agent_runs` helper.

**Current graph input/config seam** (lines 39-70):
```python
@router.post("/chat", response_model=ApiResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Submit a refund/order question to the agent."""
    graph = request.app.state.agent_graph
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    run_id = getattr(request.state, "run_id", str(uuid.uuid4()))

    input_state = {
        "user_query": body.query,
        "thread_id": body.thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
        "current_run_id": run_id,
    }
    config = {
        "configurable": {
            "thread_id": _checkpoint_thread_id(user=user, thread_id=body.thread_id),
            "session": session,
            **_trusted_tool_config(
                user,
                getattr(request.state, "verified_token_scopes", None) or [],
                getattr(request.state, "trace_id", None),
            ),
        }
    }
```

**Apply:** preserve `input_state` as graph identity projection but put canonical `TrustedContext` (or derived projections) in `config["configurable"]`. Do not add `permissions` or `merchant_scope` to `AgentState`.

---

### `src/api/routers/agent_runs.py` (route, streaming + request-response)

**Analog:** same router.

**Trusted config helper seam** (lines 45-82):
```python
SCOPE_TO_TOOL_PERMISSION = {
    "orders:read": "tool:get_order",
    "refunds:read": "tool:get_refund_case",
    "tickets:read": "tool:get_ticket",
    "knowledge:read": "tool:search_policy",
}

def _trusted_tool_config(user: User, token_scopes: Iterable[str], trace_id: str | None) -> dict[str, Any]:
    # Intersect verified token scopes with current DB role scopes
    trusted_scopes = set(token_scopes) & set(ROLE_SCOPES.get(user.role, []))
    permissions = [
        tool_permission for scope, tool_permission in SCOPE_TO_TOOL_PERMISSION.items() if scope in trusted_scopes
    ]
    if user.role == "merchant":
        merchant_scope = {"merchant_ids": [str(user.merchant_id)] if user.merchant_id is not None else []}
    else:
        merchant_scope = {"merchant_ids": ["*"]}
    return {
        "permissions": permissions,
        "merchant_scope": merchant_scope,
        "trace_id": trace_id or "",
    }
```

**Streaming config injection pattern** (lines 188-207):
```python
graph = request.app.state.agent_graph
input_state = {
    "user_query": run.input_query,
    "thread_id": run.thread_id,
    "tenant_id": str(user.tenant_id),
    "user_id": str(user.id),
    "role": user.role,
    "current_run_id": str(run.id),
}
# Read verified token scopes from trusted request context; fail closed if absent
verified_token_scopes: Iterable[str] = getattr(request.state, "verified_token_scopes", None) or []
config = {
    "configurable": {
        "thread_id": _checkpoint_thread_id(user=user, thread_id=run.thread_id),
        "session": session,
        "conversation_thread_id": str(user_message.conversation_thread_id),
        "conversation_message_id": str(user_message.id),
        "conversation_service": conversation_service,
        **_trusted_tool_config(user, verified_token_scopes, getattr(request.state, "trace_id", None)),
    }
}
```

**Apply:** move or wrap `_trusted_tool_config` behind `TrustedContextFactory`. Keep the fail-closed verified-token-scope read. Preserve streaming behavior and conversation config keys.

---

### `src/agent/nodes/investigate.py` (service, event-driven + transform)

**Analog:** same node.

**Current tool context builder seam** (lines 233-261):
```python
def _build_tool_context(
    state: AgentState,
    configurable: dict[str, Any],
    tool_name: str,
    operation_id: Any,
    attempt: int,
    max_attempts: int,
    deadline_at: Any,
) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        role=state["role"],
        permissions=list(configurable.get("permissions") or []),
        merchant_scope=configurable.get("merchant_scope") or {},
        session_id=configurable.get("session_id"),
        thread_id=state["thread_id"],
        run_id=state.get("current_run_id") or str(uuid4()),
        trace_id=configurable.get("trace_id") or state.get("current_run_id") or "",
        request_id=configurable.get("request_id") or str(uuid4()),
        tool_call_id=str(operation_id),
        caller_node="investigate",
        deadline_at=deadline_at,
        effective_at=state.get("run_started_at") or _now_iso(),
        attempt=attempt,
        max_attempts=max_attempts,
        idempotency_key=f"{state.get('current_run_id') or 'run'}:{tool_name}:{operation_id}",
        policy_snapshot_ref=None,
    )
```

**Test config pattern** from `tests/agent/test_nodes/test_investigate.py` (lines 29-43):
```python
def _config(manager, events: list[dict[str, Any]], **overrides):
    async def event_emitter(**payload):
        events.append(payload)

    configurable = {
        "tool_manager": manager,
        "event_emitter": event_emitter,
        "permissions": [f"tool:{descriptor.name}" for descriptor in ToolCatalog().descriptors()],
        "merchant_scope": {"merchant_ids": ["*"]},
        "trace_id": "trace-1",
        "max_iterations": 3,
        "max_attempts": 1,
    }
    configurable.update(overrides)
    return {"configurable": configurable}
```

**Apply:** replace identity/scope fields with `project_to_tool_context(trusted_context, ...)`. Keep `tool_call_id`, `caller_node`, `deadline_at`, `effective_at`, attempt counters, and idempotency key as local node metadata.

---

### `src/agent/nodes/action_draft.py` (service, event-driven + transform)

**Analog:** same node.

**Current action draft tool context seam** (lines 248-279):
```python
configurable = config.get("configurable") or {}
session = configurable["session"]
run_id = approval.get("run_id") or state.get("current_run_id") or ""
approval_id = approval.get("approval_id")
action_type = _canonical_action_type(proposed.get("action_type"))
proposed = {**proposed, "action_type": action_type}
permissions = list(configurable.get("permissions") or [])

tool_ctx = ToolCallContext(
    tenant_id=state.get("tenant_id", ""),
    user_id=state.get("user_id", ""),
    role=state.get("role") or "",
    permissions=permissions,
    merchant_scope=configurable.get("merchant_scope") or {},
    session_id=configurable.get("session_id"),
    thread_id=state.get("thread_id") or "",
    run_id=run_id,
    trace_id=configurable.get("trace_id") or state.get("current_run_id") or "",
    request_id=configurable.get("request_id") or run_id,
    tool_call_id=f"{run_id}:action_draft:{ACTION_TOOL_NAME}",
    caller_node="action_draft",
    deadline_at=configurable.get("deadline_at"),
    attempt=1,
    max_attempts=1,
    idempotency_key=f"action_draft_{run_id}_{approval_id or 'auto_allowed'}",
    approval_ref=approval_id,
    safety_snapshot_ref=state.get("safety_snapshot_ref")
    or approval.get("safety_snapshot_ref")
    or risk.get("safety_snapshot_ref")
    or risk.get("snapshot_ref"),
    policy_snapshot_ref=None,
)
```

**Apply:** project trusted identity/scope from canonical context only. Keep approval id, safety snapshot ref, idempotency key, deadline, and tool-call id local to `action_draft`.

---

### `src/tools/executors/knowledge.py` (service, transform + request-response)

**Analog:** same executor.

**Executor projection and error result pattern** (lines 29-99):
```python
async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
    if name != "search_policy":
        return result(
            "unavailable",
            "Tool is declared but unavailable",
            code="TOOL_UNAVAILABLE",
            source="tool",
            source_system="knowledge_tool_executor",
        )

    effective_at = ctx.effective_at or datetime.now(UTC).isoformat()
    request = KnowledgeSearchRequest(
        query=str(args["query"]),
        primary_intent=args.get("primary_intent"),
        filters=KnowledgeSearchFilters(
            tenant_id=ctx.tenant_id,
            merchant_id=args.get("merchant_id"),
            effective_at=effective_at,
            locale=None,
        ),
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        max_results=int(args.get("max_results") or 5),
        allow_partial_evidence=bool(args.get("allow_partial_evidence", True)),
    )
    search_result = await self.service.search(
        request,
        KnowledgeContext(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            role=ctx.role,
            merchant_scope=_knowledge_merchant_scope(ctx.merchant_scope),
            run_id=ctx.run_id,
            trace_id=ctx.trace_id,
            locale=None,
            effective_at=effective_at,
        ),
    )
```

**Apply:** replace direct `KnowledgeContext(...)` construction with central projection helper. Preserve `ToolResultV2` response mapping and `TOOL_UNAVAILABLE` behavior.

---

### Platform Contract Tests

#### `tests/platform/test_trusted_context.py` (test, transform)

**Analog:** strict validation tests.

**Unknown-field rejection style** from `tests/agent/test_tools/test_tool_contracts.py` (lines 72-80):
```python
def test_investigation_result_rejects_unsupported_schema_version():
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(_complete_investigation_result_payload(schema_version="v2"))

def test_investigation_result_rejects_unknown_prompt_fields():
    with pytest.raises(ValidationError):
        InvestigationResult.model_validate(
            _complete_investigation_result_payload(raw_tool_payload={"refund_id": "RF-001"})
        )
```

**Strict replay schema style** from `tests/replay/test_replay_service.py` (lines 110-124):
```python
def test_replay_schemas_are_strict():
    payload = _base_event_payload()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        ReplayEventV3(**payload)

    with pytest.raises(ValidationError):
        ReplayEventProvenance(
            source_schema_version="minimal_event_envelope.v1",
            pairing_status="invented",
        )

    with pytest.raises(ValidationError):
        ReplayRetention(archived_at=None, retention_until=None, deleted_at=None, extra=True)
```

**Apply:** assert exact canonical `TrustedContext.model_fields` equals the 11 D-01 fields, schema version is `trusted_context.v1`, and projection-local extras raise `ValidationError`.

#### `tests/platform/test_trusted_context_factory.py` (test, request-response)

**Analog:** `tests/test_agent_runs_api.py` scope/config tests.

Use the `tests/test_agent_runs_api.py` lines 1840-1900 excerpt above. Add negative cases for request body/user payload/LLM/checkpoint override attempts and assert factory output still follows authenticated user + verified scopes + server ids.

#### `tests/platform/test_merchant_scope.py` (test, transform)

**Analog:** `src/business/service.py` merchant matching and parametrized projection tests.

**Parametrize style** from `tests/agent/test_tools/test_unified_tool_manager.py` (lines 213-247):
```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("merchant_scope", "expected_scope"),
    [
        ({"merchant_ids": ["merchant-1"]}, ["merchant-1"]),
        (["merchant-legacy"], ["merchant-legacy"]),
        ({"categories": ["electronics"]}, []),
        ({"merchant_ids": [123]}, []),
        ({}, []),
    ],
)
async def test_search_policy_projects_merchant_scope_for_knowledge_service(merchant_scope, expected_scope):
    class FakePolicyService:
        async def search(self, request, context):
            del request
            assert context.merchant_scope == expected_scope
            return KnowledgeSearchResult(
                status="no_evidence",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                rerank_config_version=RERANK_CONFIG_VERSION,
                best_score=0.0,
                threshold=0.55,
                evidence_refs=[],
            )

    manager = UnifiedToolManager(executors=[KnowledgeToolExecutor(session=None, service=FakePolicyService())])

    result = await manager.invoke(
        "search_policy",
        {"query": "refund policy"},
        _ctx(tool="search_policy", merchant_scope=merchant_scope),
    )

    assert result.status == "not_found"
```

**Apply:** cover empty deny-all, explicit `"*"`, all-provided-dimensions, invalid values, and no widening.

#### `tests/platform/test_context_projections.py` (test, transform)

**Analog:** `tests/agent/test_tools/test_unified_tool_manager.py`.

**Tool context fixture pattern** (lines 37-66):
```python
def _ctx(
    *,
    tool: str = "get_order",
    permissions: list[str] | None = None,
    caller_node: str = "investigate",
    idempotency_key: str | None = None,
    safety_snapshot_ref: str | None = None,
    merchant_scope: Any | None = None,
) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
        permissions=[f"tool:{name}" for name in INVESTIGATE_TOOLS] if permissions is None else permissions,
        merchant_scope={"merchant_ids": ["*"]} if merchant_scope is None else merchant_scope,
        session_id=None,
        thread_id="thread-1",
        run_id=str(uuid4()),
        trace_id="trace-1",
        request_id=str(uuid4()),
        tool_call_id=str(uuid4()),
        caller_node=caller_node,
        deadline_at=datetime.now(UTC),
        effective_at=datetime.now(UTC).isoformat(),
        attempt=1,
        max_attempts=1,
        idempotency_key=idempotency_key,
        safety_snapshot_ref=safety_snapshot_ref,
        policy_snapshot_ref=None,
    )
```

**Apply:** make projection tests create canonical context once, then derive tool/knowledge/memory/approval/replay/intent contexts. Assert local fields appear only in projections and never in `trusted.model_dump()`.

---

### Registry and Boundary Tests

#### `tests/agent/test_intent_policy_registry.py` (test, transform)

**Analog:** `tests/agent/test_intent_golden_contract.py`.

**Parametrized deterministic helper style** (lines 40-99):
```python
@pytest.mark.parametrize("case", [case for case in _cases() if case["kind"] == "positive"])
def test_positive_golden_cases_exercise_deterministic_helpers(case):
    expected = case["expected"]
    text = case["input"]
    pre_route = detect_pre_route(text)
    if "pre_route_disposition" in expected:
        assert pre_route.disposition == expected["pre_route_disposition"]
    if "primary_intent" in expected:
        update = intent_result_to_state(
            _result(expected["primary_intent"], expected.get("requested_operation", "advise")),
            pre_route=pre_route,
            user_query=text,
        )
        assert update["primary_intent"] == expected["primary_intent"]
        assert update["requested_operation"] == expected.get("requested_operation", update["requested_operation"])
        for key, value in expected.get("required_slots", {}).items():
            assert update["required_slots"][key] == value
        for forbidden in expected.get("forbidden", []):
            assert forbidden not in update
```

**Apply:** assert registry APIs expose the same definitions, required slot policy, route policy, precedence, direct/evidence/high-risk sets, and risk behavior as the existing constants. Include immutability/no-mutation tests.

#### `tests/architecture/test_trusted_context_boundaries.py` (test, static boundary)

**Analog:** `tests/architecture/test_tool_boundaries.py`.

**AST import scanner pattern** (lines 1-30):
```python
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports
```

**Boundary assertion style** (lines 33-62):
```python
def test_graph_nodes_do_not_import_legacy_agent_tools_or_raw_integrations() -> None:
    violations: list[tuple[str, str]] = []
    for path in sorted((ROOT / "src" / "agent" / "nodes").glob("*.py")):
        for module in _imports(path):
            if module.startswith(("src.agent.tools", "src.integrations")):
                violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []


def test_no_code_imports_legacy_agent_tools_package() -> None:
    violations: list[tuple[str, str]] = []
    for base in (ROOT / "src", ROOT / "tests"):
        for path in sorted(base.glob("**/*.py")):
            for module in _imports(path):
                if module.startswith("src.agent.tools"):
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []
```

**Apply:** add checks that `src/agent/context/projectors.py` does not import `TrustedContextFactory`, no duplicate `TrustedContext`/`MerchantScopeV1` model exists outside `src/platform`, and consumers import projections instead of redefining trusted identity/scope.

---

### Integration Test Updates

#### `tests/test_search_integration.py` (test, request-response)

Use existing API style from lines 62-87. Add assertions or monkeypatch spies proving `/api/v1/search/` calls the factory/projection and ignores body-level identity/scope fields if present.

#### `tests/test_agent_runs_api.py` (test, streaming + request-response)

**Graph config identity pattern** (lines 164-205):
```python
async def _append_tool_result(self, *, conversation_service, input_state, config, run_id: UUID, order_id: str) -> None:
    operation_id = uuid4()
    tool_call_id = f"tool-call-{run_id}"
    tool_call = await conversation_service.append_tool_call(
        tenant_id=input_state["tenant_id"],
        user_id=input_state["user_id"],
        thread_id=input_state["thread_id"],
        run_id=run_id,
        trace_id=config["configurable"].get("trace_id"),
        tool_call_id=tool_call_id,
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": order_id},
        argument_summary_json={"order_no": order_id},
        redaction_policy_version="conversation_redaction.v1",
        conversation_message_id=config["configurable"]["conversation_message_id"],
    )
```

**Apply:** update helper assertions from `_trusted_tool_config` to factory/projection output while preserving run/thread/trace identity and permission intersection assertions.

#### `tests/agent/test_nodes/test_investigate.py` (test, event-driven + transform)

**Prompt-safe result assertions** (lines 458-488):
```python
@pytest.mark.asyncio
async def test_investigate_state_tool_results_are_prompt_safe_refs(session: AsyncSession, seeded_session: dict):
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success_with_raw_payload()})
    thread_id = "thread-investigate-tool-projection"
    state = _state([{"next_tool": "get_order", "args": {"order_no": "ORD-RAW-001"}, "reason": "test"}])
    state["tenant_id"] = str(seeded_session["tenant"].id)
    state["user_id"] = str(seeded_session["users"]["cs_zhang"].id)
    state["thread_id"] = thread_id
    state["current_run_id"] = await _insert_run(session, seeded_session, thread_id)

    result = await investigate(_state([]) | state, _config(manager, events, session=session))

    projection = result["tool_results"][0]

    assert {
        "tool_call_id",
        "tool_result_id",
        "tool_name",
        "status",
        "summary",
        "prompt_summary",
        "business_fact_refs",
        "policy_evidence_refs",
    } <= set(projection)
    assert "data" not in projection
    assert "raw_payload" not in projection
```

**Apply:** add assertions that tool calls are built from trusted projection values, while prompt-safe result projection behavior remains unchanged.

#### `tests/agent/test_tools/test_unified_tool_manager.py` (test, transform)

Use current `_ctx` fixture and merchant projection parametrization from lines 37-66 and 213-247. Add tests around `project_to_tool_context` output compatibility with `UnifiedToolManager.invoke`.

#### `tests/knowledge/test_tenant_scope.py` (test, request-response)

**Scope authorization pattern** (lines 75-90):
```python
@pytest.mark.asyncio
async def test_merchant_filter_is_authorized_before_policy_query():
    adapter = SimpleNamespace(retrieve=AsyncMock(return_value=("no_evidence", [], 0.0)))
    service = PolicyKnowledgeService(adapter)
    tenant_id = str(uuid4())
    context = _context(tenant_id, merchant_scope=["merchant-allowed"])

    baseline = await service.search(_request(tenant_id), context)
    unauthorized = await service.search(_request("untrusted-tenant", "merchant-denied"), context)
    authorized = await service.search(_request("untrusted-tenant", "merchant-allowed"), context)

    assert baseline == authorized
    assert unauthorized.status == "no_evidence"
    assert unauthorized.evidence_refs == []
    assert adapter.retrieve.await_count == 2
    assert all(call.kwargs["context"] is context for call in adapter.retrieve.await_args_list)
    assert all("merchant_id" not in call.kwargs for call in adapter.retrieve.await_args_list)
```

**Apply:** preserve deny-before-query behavior when context comes from factory projection.

## Shared Patterns

### Authentication and Trusted Request State

**Source:** `src/auth/permissions.py` lines 60-74; `src/api/main.py` lines 52-60
**Apply to:** `src/platform/trusted_context.py`, `src/api/routers/search.py`, `src/api/routers/agent.py`, `src/api/routers/agent_runs.py`

Use authenticated `User`, immutable `request.state.verified_token_scopes`, and server-created `trace_id`/`run_id`. Never read tenant/user/role/permissions/merchant scope from request body, LLM output, or checkpoint state as authority.

### Strict Contract Models

**Source:** `src/tools/contracts.py` lines 13-37; `src/approvals/schemas.py` lines 29-153; `src/replay/schemas.py` lines 37-59
**Apply to:** `TrustedContext`, `MerchantScopeV1`, `MemoryContext`, `ApprovalContext`, `ReplayContext`, `IntentPolicyContext`, platform tests

Use `BaseModel`, `ConfigDict(extra="forbid")`, schema-version `Literal`s, and focused negative `ValidationError` tests.

### Projection-Local Metadata

**Source:** `src/tools/contracts.py` lines 26-36; `src/agent/nodes/investigate.py` lines 252-260; `src/agent/nodes/action_draft.py` lines 266-278
**Apply to:** tool/knowledge/memory/approval/replay/intent projection methods and tests

Only projections should receive `request_id`, `tool_call_id`, `caller_node`, `deadline_at`, `effective_at`, `attempt`, `max_attempts`, `idempotency_key`, approval/safety/policy refs, `channel`, version refs, and artifact refs.

### Merchant Scope

**Source:** `src/business/service.py` lines 62-90; `tests/agent/test_tools/test_unified_tool_manager.py` lines 213-247
**Apply to:** `MerchantScopeV1`, factory merchant derivation, knowledge compatibility adapter, platform merchant tests

Implement deny-all for missing/empty scope, explicit wildcard only through `"*"`, all-provided-dimensions matching, and invalid value denial.

### Knowledge Compatibility

**Source:** `src/knowledge/schemas.py` lines 18-29; `src/tools/executors/knowledge.py` lines 54-66, 102-108; `src/knowledge/service.py` lines 111-119
**Apply to:** `src/platform/context_projections.py`, `src/tools/executors/knowledge.py`, `src/knowledge/schemas.py`, knowledge tests

Canonical merchant scope may be an object, but current knowledge service consumes `list[str] | None`. Preserve this via a central adapter unless the schema is migrated in one focused task.

### Prompt Projectors Are Not Trusted Authority

**Source:** `src/agent/context/projectors.py` lines 83-99, 125-178; `tests/agent/context/test_assembler.py` lines 145-165, 345-365
**Apply to:** `tests/architecture/test_trusted_context_boundaries.py`, all context factory imports

Prompt projectors sanitize text for prompts. They must not import or create `TrustedContext`, and trusted context modules must not move prompt-safe projection logic into canonical identity/scope authority.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | - | - | Every likely file has a usable analog. `src/platform/trusted_context.py` has no single exact runtime predecessor, so use the composite analogs above instead of copying one file wholesale. |

## Metadata

**Analog search scope:** `src/`, `tests/`, `.planning/phases/27-trustedcontextfactory-and-projections/`
**Source files scanned:** 190 Python files under `src/`
**Test files scanned:** 161 Python files under `tests/`
**Primary analogs read:** `src/tools/contracts.py`, `src/knowledge/schemas.py`, `src/auth/permissions.py`, `src/api/main.py`, `src/api/routers/search.py`, `src/api/routers/agent.py`, `src/api/routers/agent_runs.py`, `src/agent/nodes/investigate.py`, `src/agent/nodes/action_draft.py`, `src/tools/executors/knowledge.py`, `src/agent/intent_policy.py`, `src/business/service.py`, `src/memory/session_bundle.py`, `src/approvals/schemas.py`, `src/replay/schemas.py`, focused tests under `tests/agent`, `tests/knowledge`, `tests/architecture`, `tests/replay`, and `tests/test_agent_runs_api.py`.
**Pattern extraction date:** 2026-06-22
