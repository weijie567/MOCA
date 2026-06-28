# Phase 31: Memory Platform Boundary - Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 26 planned new/modified files + 5 shared reference analogs
**Analogs found:** 26 / 26

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/memory/context_refs.py` | model | transform | `src/memory/schemas.py` | role-match |
| `src/memory/context_service.py` | service | request-response / transform | `src/memory/session_bundle.py` | role-match |
| `src/memory/schemas.py` | model | transform | `src/memory/schemas.py` | exact |
| `src/memory/session_bundle.py` | service | request-response | `src/memory/session_bundle.py` | exact |
| `src/agent/state.py` | store / contract | event-driven state | `src/agent/state.py` | exact |
| `src/agent/nodes/session_context_load.py` | route / controller | request-response | `src/agent/nodes/session_memory_load.py` | exact behavior, new name |
| `src/agent/nodes/session_memory_load.py` | route / compatibility wrapper | request-response | `src/agent/nodes/session_memory_load.py` | exact |
| `src/agent/nodes/reviewed_memory_context_retrieve.py` | route / controller | request-response | `src/agent/nodes/long_term_memory_retrieve.py` | exact behavior, new guarded boundary |
| `src/agent/nodes/long_term_memory_retrieve.py` | route / compatibility wrapper | request-response | `src/agent/nodes/long_term_memory_retrieve.py` | exact |
| `src/agent/nodes/memory_write.py` | route / controller | event-driven write | `src/agent/nodes/memory_write.py` | exact |
| `src/agent/graph.py` | config / graph assembly | event-driven | `src/agent/graph.py` | exact |
| `src/agent/routing.py` | route | event-driven | `src/agent/routing.py` | exact |
| `src/agent/intent_policy.py` | config | transform | `src/agent/intent_policy.py` | exact |
| `src/agent/context/session_memory_bundle.py` | utility | transform / request-response | `src/agent/context/session_memory_bundle.py` | exact |
| `src/agent/context/projectors.py` | utility | transform | `src/agent/context/projectors.py` | exact |
| `src/agent/rag_context/verifier.py` | service / validator | transform | `src/agent/rag_context/verifier.py` | exact |
| `tests/memory/test_context_refs.py` | test | contract validation | `tests/memory/test_session_memory_schema.py` | role-match |
| `tests/memory/test_session_memory_bundle.py` | test | integration / transform | `tests/memory/test_session_memory_bundle.py` | exact |
| `tests/agent/test_session_memory_load.py` | test | graph node request-response | `tests/agent/test_session_memory_load.py` | exact |
| `tests/agent/test_reviewed_memory_context_retrieve.py` | test | graph node request-response | `tests/agent/test_graph.py` reviewed-memory cases | role-match |
| `tests/agent/test_memory_write_node.py` | test | event-driven write | `tests/agent/test_memory_write_node.py` | exact |
| `tests/agent/test_memory_evidence_boundary.py` | test | authority-boundary integration | `tests/agent/test_memory_evidence_boundary.py` | exact |
| `tests/agent/rag_context/test_authority_boundaries.py` | test | authority-boundary transform | `tests/agent/rag_context/test_authority_boundaries.py` | exact |
| `tests/memory/test_case_memory_retrieval.py` | test | CRUD / retrieval filtering | `tests/memory/test_case_memory_retrieval.py` | exact |
| `tests/memory/test_long_term_memory_service.py` | test | CRUD / lifecycle | `tests/memory/test_long_term_memory_service.py` | exact |
| `tests/memory/test_memory_tombstones.py` | test | CRUD / lifecycle | `tests/memory/test_memory_tombstones.py` | exact |

Reference-only analogs for shared rules: `src/platform/trusted_context.py`, `src/platform/context_projections.py`, `src/knowledge/schemas.py`, `src/tools/contracts.py`, `src/replay/decision_events.py`, `src/replay/validators.py`.

## Pattern Assignments

### `src/memory/context_refs.py` (model, transform)

**Analog:** `src/memory/schemas.py`

**Imports / strict DTO pattern** (`src/memory/schemas.py` lines 3-8):
```python
from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field
```

**Memory-owned ref identity pattern** (`src/memory/schemas.py` lines 13-48):
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


class MemoryCandidateIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    memory_type: str
    scope_type: str
    scope_id: str
    content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_identity_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    candidate_hash: str = Field(pattern=_SHA256_PATTERN)
```

**Apply:** Define `SessionContextRef`, `ReviewedMemoryRef`, `SessionContextLoadStatusV1`, `ReviewedMemoryContextRetrieveStatusV1`, `ReviewedMemoryContextBundle`, and `MemoryWriteDecisionV2` as strict Pydantic DTOs here or in an equivalent memory-owned schema module. Include `authority_class: Literal["contextual_only"] = "contextual_only"` and do not import `EvidenceRefV1`, `BusinessFactRefV1`, approval schemas, action schemas, or replay DTOs.

**Write-result metadata pattern** (`src/memory/schemas.py` lines 243-255 and 309-321):
```python
class LongTermMemoryWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["written", "needs_review", "skipped", "error"]
    memory_id: uuid.UUID | None = None
    review_status: LongTermReviewStatus | None = None
    decision: LongTermWriteDecision
    reason_code: str
    pii_classification: LongTermPiiClassification = "none"
    candidate_hash: str = Field(pattern=_SHA256_PATTERN)
    content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_identity_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    event_id: uuid.UUID | None = None
```

### `src/memory/context_service.py` (service, request-response / transform)

**Analog:** `src/memory/session_bundle.py`

**Service composition pattern** (`src/memory/session_bundle.py` lines 16-68):
```python
class SessionMemoryBundleService:
    def __init__(self, *, conversation_service: ConversationService, memory_service: MemoryService) -> None:
        self.conversation_service = conversation_service
        self.memory_service = memory_service

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
        fallback_reasons: dict[str, str] = {}
        try:
            prompt_context = await self.conversation_service.load_prompt_context(...)
        except Exception:
            prompt_context = None
            fallback_reasons["prompt_context"] = "unavailable"

        try:
            slot_continuity = await self.memory_service.load_session_memory(...)
        except Exception:
            slot_continuity = _empty_slot_continuity("unavailable")
            fallback_reasons["slot_continuity"] = "unavailable"

        return SessionMemoryBundle(...)
```

**Apply:** If a `MemoryContextService` facade is added, make it a real boundary over session context and reviewed memory context, not a thick adapter. It should consume existing `SessionMemoryBundleService`, `LongTermMemoryService`, and `CaseMemoryService`; add target DTOs/status refs at the facade boundary and preserve storage service names internally.

### `src/memory/schemas.py` and `src/memory/session_bundle.py` (model/service, transform / request-response)

**Analog:** current session memory bundle schema and service.

**Existing bundle to alias or wrap** (`src/memory/schemas.py` lines 129-142):
```python
class SessionMemoryBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_memory_bundle.v1"] = "session_memory_bundle.v1"
    source: Literal["session_memory_bundle"] = "session_memory_bundle"
    tenant_id: str
    user_id: str
    thread_id: str
    run_id: str
    rolling_summary: SessionRollingSummaryView | None = None
    recent_messages: list[SessionRecentMessageView] = Field(default_factory=list)
    tool_summaries: list[SessionToolSummaryView] = Field(default_factory=list)
    slot_continuity: SlotContinuityMemoryView
    fallback_reasons: dict[str, str] = Field(default_factory=dict)
```

**Fallback pattern** (`src/memory/session_bundle.py` lines 137-144):
```python
def _empty_slot_continuity(reason: str) -> SessionMemoryView:
    return SessionMemoryView(
        source="empty_adapter",
        continuity_claimed=False,
        active_slots={},
        slot_metadata={},
        fallback_reason=reason,
    )
```

**Apply:** Add `SessionContextMemory` / `SessionContextBundle` aliases or target DTOs next to the current bundle, but keep `SessionMemoryBundle` and `session_memory_bundle.v1` compatible unless a plan explicitly migrates callers.

### `src/agent/nodes/session_context_load.py` and `src/agent/nodes/session_memory_load.py` (route/controller, request-response)

**Analog:** `src/agent/nodes/session_memory_load.py`

**Node imports and dependency construction** (`src/agent/nodes/session_memory_load.py` lines 3-15):
```python
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.config import settings
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.memory.repository import SessionMemoryRepository
from src.memory.session_bundle import SessionMemoryBundleService
from src.memory.service import MemoryService
```

**Load + compatibility result pattern** (`src/agent/nodes/session_memory_load.py` lines 21-45):
```python
async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Load same-thread session memory through the PostgreSQL-authoritative service."""
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable.get("session")
    if settings.session_memory_enabled is False:
        return _fallback(state, started_at, source="disabled", fallback_reason="disabled")
    if session is None:
        return _fallback(state, started_at, source="unavailable", fallback_reason="missing_async_session")

    try:
        service = MemoryService(SessionMemoryRepository(session), enabled=settings.session_memory_enabled)
        bundle = await _load_bundle(state, configurable, session, service)
        if bundle is None:
            return _fallback(state, started_at, source="unavailable", fallback_reason="missing_session_memory_bundle")
        memory = bundle.slot_continuity.model_dump(mode="json")
        bundle_dump = bundle.model_dump(mode="json")
        step = _trace_step(started_at, memory)
        result = {
            "session_memory": memory,
            "trace_steps": (state.get("trace_steps") or []) + [step],
        }
        if bundle_dump is not None:
            result["session_memory_bundle"] = bundle_dump
        return result
```

**Status/trace pattern to extend** (`src/agent/nodes/session_memory_load.py` lines 87-104):
```python
def _trace_step(started_at: str, memory: dict[str, Any]) -> dict[str, Any]:
    active_slots = memory.get("active_slots") if isinstance(memory.get("active_slots"), dict) else {}
    step = {
        "node": "session_memory_load",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "source": memory.get("source"),
            "continuity_claimed": memory.get("continuity_claimed") is True,
            "fallback_reason": memory.get("fallback_reason"),
            "slot_count": len(active_slots),
            "version": memory.get("version"),
        },
    }
    return step
```

**Apply:** New `session_context_load` should populate target fields such as `session_context`, `session_context_bundle`, and `session_context_load_status`, while continuing to populate `session_memory` and `session_memory_bundle` during compatibility. Update trace node names deliberately; if old node remains, make it call or alias the new implementation.

### `src/agent/nodes/reviewed_memory_context_retrieve.py` and `src/agent/nodes/long_term_memory_retrieve.py` (route/controller, request-response)

**Analog:** `src/agent/nodes/long_term_memory_retrieve.py`

**Current retrieval node shape** (`src/agent/nodes/long_term_memory_retrieve.py` lines 38-106):
```python
async def long_term_memory_retrieve(state: AgentState, config: RunnableConfig) -> dict:
    """Load reviewed long-term and case memory as contextual prompt snippets."""
    started_at = _now_iso()
    configurable = (config.get("configurable") or {}) if config else {}
    session = configurable.get("session")
    tenant_id = _uuid_or_none(state.get("tenant_id"))

    profile_service = configurable.get("long_term_memory_service")
    case_service = configurable.get("case_memory_service")
    if tenant_id is None or (session is None and (profile_service is None or case_service is None)):
        return _memory_result(..., source="reviewed_memory_unavailable", fallback_reason="missing_dependencies")

    try:
        if profile_service is None:
            profile_service = LongTermMemoryService(LongTermMemoryRepository(session))
        if case_service is None:
            case_service = CaseMemoryService(CaseMemoryRepository(session))

        scopes = _memory_scopes(state)
        profile_items = await profile_service.retrieve_profile_memory(...)
        case_items: list[Any] = []
        case_query = _case_memory_query(state)
        if case_query:
            case_result = await case_service.retrieve_reviewed(CaseMemorySearchRequest(...))
            case_items = list(getattr(case_result, "items", []))
    except Exception:
        result = _memory_result(..., source="reviewed_memory_unavailable", fallback_reason="service_error")
        result["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "long_term_memory_retrieve", "error_code": "REVIEWED_MEMORY_UNAVAILABLE"}
        ]
        return result
```

**Current scope derivation to replace or guard** (`src/agent/nodes/long_term_memory_retrieve.py` lines 157-176):
```python
def _memory_scopes(state: AgentState) -> list[tuple[str, str]]:
    slots = _merged_slots(state)
    candidates = [
        ("tenant", state.get("tenant_id")),
        ("user", state.get("user_id")),
        ("thread", state.get("thread_id")),
        ("merchant", slots.get("merchant_id")),
        ("case", slots.get("refund_case_id")),
    ]
    scopes: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for scope_type, raw_scope_id in candidates:
        scope_id = str(raw_scope_id or "").strip()
        if not scope_id:
            continue
        scope = (scope_type, scope_id)
        if scope not in seen:
            scopes.append(scope)
            seen.add(scope)
    return scopes
```

**Projection/sanitization pattern** (`src/agent/nodes/long_term_memory_retrieve.py` lines 202-229):
```python
def _project_profile_memory(item: Any) -> dict[str, Any] | None:
    mapping = _mapping(item)
    content = _safe_text(mapping.get("content") or mapping.get("summary"))
    if not content:
        return None
    projected = _select_keys(mapping, _PROFILE_KEYS)
    projected["content"] = content
    if "source_ref" in projected:
        projected["source_ref"] = _safe_ref_mapping(projected["source_ref"], _SOURCE_REF_KEYS)
    if not projected.get("source_ref"):
        projected.pop("source_ref", None)
    return projected


def _project_case_memory(item: Any) -> dict[str, Any] | None:
    mapping = _mapping(item)
    case_memory_id = _safe_text(mapping.get("case_memory_id") or mapping.get("memory_id") or mapping.get("id"))
    excerpt = _safe_text(mapping.get("excerpt") or mapping.get("summary"))
    if not case_memory_id or not excerpt:
        return None
    projected = _select_keys(mapping, _CASE_KEYS)
    projected["case_memory_id"] = case_memory_id
    projected["excerpt"] = excerpt
```

**Apply:** Target node should return a structured `memory_context` / `reviewed_memory_context` bundle plus legacy `long_term_memory` and `case_memory` aliases. It must derive effective merchant/case scopes only from trusted inputs and explicit/trusted business context; do not keep `_memory_scopes` as-is for merchant or case scope.

### `src/agent/nodes/memory_write.py` (route/controller, event-driven write)

**Analog:** `src/agent/nodes/memory_write.py`

**Fail-closed entry and timeout pattern** (`src/agent/nodes/memory_write.py` lines 37-73):
```python
async def memory_write(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    final_response = state.get("final_response")
    if not final_response:
        return _skipped(state, started_at, "not_completed_path")
    if _approval_or_interrupted(state):
        return _skipped(state, started_at, "not_completed_path")
    if settings.session_memory_enabled is False:
        return _skipped(state, started_at, "disabled")

    configurable = config.get("configurable") or {}
    session = configurable.get("session")
    if session is None:
        return _skipped(state, started_at, "missing_async_session")
    memory_operation_id = uuid.uuid4()

    try:
        result = await asyncio.wait_for(
            _write_with_service(state, session, configurable, started_at, operation_id=memory_operation_id),
            timeout=settings.session_memory_write_timeout_seconds,
        )
        return result
    except TimeoutError:
        rollback = getattr(session, "rollback", None)
        if callable(rollback):
            await rollback()
        return _skipped(state, started_at, "write_timeout", final_response=final_response)
```

**Candidate/result projection pattern** (`src/agent/nodes/memory_write.py` lines 235-311):
```python
def _completed(
    state: AgentState,
    started_at: str,
    result: SessionMemoryWriteResult,
    candidate: SessionMemoryWriteCandidate,
) -> dict:
    result_dict = result.model_dump(mode="json")
    return {
        "final_response": state.get("final_response"),
        "memory_write_candidates": [_candidate_projection(candidate)],
        "memory_write_result": result_dict,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result_dict)],
    }


def _candidate_projection(candidate: SessionMemoryWriteCandidate) -> dict[str, Any]:
    return {
        "slot_names": sorted(candidate.explicit_slots),
        "has_unresolved_questions": bool(candidate.unresolved_questions),
        "last_intent": candidate.last_intent,
        "decision": candidate.decision,
        "reason_code": candidate.reason_code,
        "pii_classification": candidate.pii_classification,
    }
```

**Decision-event pattern** (`src/agent/nodes/memory_write.py` lines 323-349):
```python
await emit_event(
    session,
    run_id=run_id,
    tenant_id=tenant_id,
    thread_id=str(thread_id),
    event_type=event_type,
    actor={"type": "agent", "id": "moca"},
    resource_refs={"memory_type": "session_memory"},
    redacted_payload={key: value for key, value in payload.items() if value is not None},
    trace_id=configurable.get("trace_id"),
    operation_id=operation_id,
)
```

**Apply:** Add `memory_write_decision` / `memory_write_decision.v2` projection without removing `memory_write_result` compatibility. Preserve timeout/error semantics: main response, approval path, and action path must not roll back because memory side effects fail.

### `src/agent/state.py` (store/contract, event-driven state)

**Analog:** `src/agent/state.py`

**Existing memory state fields to extend** (`src/agent/state.py` lines 48-101):
```python
class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""

    # Durable graph/checkpoint context: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    active_slot_metadata: dict[str, Any] | None
    last_intent: str | None
    last_recommendation_summary: LastRecommendationSummary | None
    evidence_refs: list[EvidenceRef]
    last_business_context_refs: LastBusinessContextRefs | None

    # Ephemeral context: reset by receive_request at the start of each turn.
    ...
    case_memory: list[dict[str, Any]] | None
    ...
    session_memory: dict[str, Any] | None
    session_memory_bundle: dict[str, Any] | None
    memory_write_candidates: list[dict[str, Any]] | None
    memory_write_result: dict[str, Any] | None
    long_term_memory: list[dict[str, Any]] | None
```

**Apply:** Add target ephemeral fields such as `session_context`, `session_context_bundle`, `session_context_load_status`, `memory_context`, `reviewed_memory_context_retrieve_status`, and `memory_write_decision`. Preserve legacy fields for transition.

### `src/agent/graph.py`, `src/agent/routing.py`, and `src/agent/intent_policy.py` (config/route, event-driven)

**Analogs:** graph assembly and route literals.

**Current graph memory order** (`src/agent/graph.py` lines 135-170):
```python
builder.add_node("receive_request", receive_request)
builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
builder.add_node("session_memory_load", session_memory_load)
builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
builder.add_node("long_term_memory_retrieve", long_term_memory_retrieve)
builder.add_node("investigate", investigate)
...
builder.add_edge("session_memory_load", "extract_slots")
builder.add_conditional_edges(
    "extract_slots",
    route_after_slots,
    {
        "clarification_gate": "clarification_gate",
        "investigate": "investigate",
        "long_term_memory_retrieve": "long_term_memory_retrieve",
    },
)
builder.add_edge("long_term_memory_retrieve", "investigate")
```

**Route literal pattern** (`src/agent/routing.py` lines 22-23 and 241-259):
```python
INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "session_memory_load"}
SLOT_ROUTES = {"clarification_gate", "investigate", "long_term_memory_retrieve"}

def _route_after_slots(state: AgentState) -> str:
    ...
    if routing_hints.get("needs_long_term_memory") is True:
        return "long_term_memory_retrieve"
    return "investigate"
```

**Intent policy literal pattern** (`src/agent/intent_policy.py` lines 14-23 and 45-93):
```python
IntentRouteLiteral = Literal["investigate", "session_memory_load", "final_response"]

@dataclass(frozen=True)
class IntentDefinition:
    name: IntentLiteral
    required_slots: RequiredSlotExpression
    initial_route: IntentRouteLiteral
    precedence: int
    direct_response: bool = False
    evidence_required: bool = True
```

**Apply:** If target node names are registered in Phase 31, update graph node registration, route literals, and compatibility tests together. If reviewed retrieval cannot move after `investigate` yet, route to the target node in the current position but enforce trusted-scope fail-closed behavior in the node/status DTO.

### `src/agent/context/session_memory_bundle.py` and `src/agent/context/projectors.py` (utility, transform)

**Analog:** prompt projection helpers.

**State-first bundle reuse pattern** (`src/agent/context/session_memory_bundle.py` lines 25-40):
```python
async def load_session_prompt_context(state: Mapping[str, Any], config: Mapping[str, Any] | None) -> dict[str, Any]:
    bundle = await load_session_memory_bundle_for_state(state, config)
    if bundle is None:
        return dict(EMPTY_SESSION_PROMPT_CONTEXT)
    return project_session_memory_bundle_for_prompt(bundle)


async def load_session_memory_bundle_for_state(
    state: Mapping[str, Any],
    config: Mapping[str, Any] | None,
    *,
    max_recent_messages: int = 8,
) -> SessionMemoryBundle | None:
    existing = session_memory_bundle_from_state(state)
    if existing is not None:
        return existing
```

**Prompt projection pattern** (`src/agent/context/session_memory_bundle.py` lines 109-140):
```python
def project_session_memory_bundle_for_prompt(bundle: SessionMemoryBundle) -> dict[str, Any]:
    return {
        "thread_rolling_summary": bundle.rolling_summary.summary_text if bundle.rolling_summary else "",
        "recent_messages": [
            {"role": message.role, "content": message.content}
            for message in bundle.recent_messages
            if message.content
        ],
        "tool_result_summaries": [
            summary for summary in (_tool_prompt_summary_from_bundle(view) for view in bundle.tool_summaries) if summary
        ],
    }
```

**Memory prompt sanitization pattern** (`src/agent/context/projectors.py` lines 65-96 and 194-257):
```python
_MEMORY_SOURCE_REF_KEYS = (
    "source_type",
    "business_object_type",
    "business_object_id",
    "run_id",
    "event_id",
    "conversation_message_id",
    "tool_result_id",
    "agent_run_id",
    "policy_version",
    "outcome_id",
)
_FORBIDDEN_PROMPT_VALUE_MARKERS = (
    "EvidenceRefV1",
    "SHOULD_NOT_APPEAR",
    "approval_authority_body",
    "action_authority_body",
    "raw_payload",
    "raw_tool_output",
    "private_reasoning",
    "debug_blob",
    "debug_trace",
    "replay_debug_blob",
    "secret",
    "ReplayEventV3",
)
```

```python
def project_profile_memory_for_prompt(snippets: Sequence[Any] | None, *, max_chars: int = _PROFILE_MEMORY_MAX_CHARS) -> str:
    ...
    source_refs = _format_memory_ref_list(
        mapping.get("source_refs") or mapping.get("source_ref"),
        keys=_MEMORY_SOURCE_REF_KEYS,
        max_chars=80,
    )

def project_case_memory_for_prompt(snippets: Sequence[Any] | None, *, max_chars: int = _CASE_MEMORY_MAX_CHARS) -> str:
    ...
    policy_refs = _format_memory_ref_list(
        mapping.get("policy_refs"),
        keys=_CASE_MEMORY_POLICY_REF_KEYS,
        max_chars=80,
    )
```

**Apply:** Project target `session_context` and `memory_context` fields from structured DTOs, not raw rows. Keep prompt labels as hygiene only; authority boundaries must live in typed refs and verifiers.

### `src/agent/rag_context/verifier.py` (service/validator, transform)

**Analog:** existing authority-boundary verifier plus tests.

**Authority ref schemas to remain incompatible with memory refs** (`src/knowledge/schemas.py` lines 31-43; `src/tools/contracts.py` lines 58-92; `src/approvals/schemas.py` lines 29-50):
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

```python
class BusinessFactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_fact_ref.v1"] = "business_fact_ref.v1"
    tenant_id: str
    source_system: str
    resource_type: Literal["order", "refund_case", "ticket", "logistics", "merchant_risk"]
    resource_id: str
    resource_version: str | None
    data_freshness_at: datetime | None
    retrieved_at: datetime
```

```python
class ApprovalRequestCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ...
    evidence_refs: list[EvidenceRefV1] = Field(min_length=1)
```

**Apply:** Add or preserve verifier deny-list behavior so `SessionContextRef`, `ReviewedMemoryRef`, and status refs never satisfy policy evidence, current business facts, approval evidence refs, action snapshot refs, `MaterialClaim.business_fact_refs`, or replay truth.

## Shared Patterns

### Trusted Scope

**Source:** `src/platform/trusted_context.py`
**Apply to:** `reviewed_memory_context_retrieve`, memory scope DTO/status refs, cross-merchant tests.

```python
class MerchantScopeV1(BaseModel):
    """Merchant scope with deny-first, all-provided-dimensions semantics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["merchant_scope.v1"] = MERCHANT_SCOPE_SCHEMA_VERSION
    merchant_ids: list[str]
    categories: list[str] | None = None
    risk_levels: list[str] | None = None
    match_rule: Literal["all_provided_dimensions"] = "all_provided_dimensions"

    def allows(
        self,
        merchant_id: str | None = None,
        category: str | None = None,
        risk_level: str | None = None,
    ) -> bool:
        if not self.merchant_ids:
            return False
        ...
        if "*" not in allowed and requested not in allowed:
            return False
        return True
```
(`src/platform/trusted_context.py` lines 25-70)

```python
class TrustedContext(BaseModel):
    """Canonical trusted context produced only from API/auth/run boundaries."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trusted_context.v1"] = TRUSTED_CONTEXT_SCHEMA_VERSION
    tenant_id: str
    user_id: str
    role: str
    permissions: list[str]
    merchant_scope: MerchantScopeV1
    session_id: str | None = None
    thread_id: str
    run_id: str
    trace_id: str | None = None
    locale: str | None = None
```
(`src/platform/trusted_context.py` lines 73-88)

### Reviewed Memory Lifecycle

**Source:** `src/memory/long_term.py`, `src/memory/case_memory.py`
**Apply to:** `context_service`, `reviewed_memory_context_retrieve`, write decision projection, lifecycle tests.

```python
tombstone = await self.repository.check_tombstone_before_write(...)
if tombstone is not None:
    event = await self.repository.emit_write_event(
        tenant_id=candidate.tenant_id,
        run_id=candidate.run_id,
        memory_type=LONG_TERM_MEMORY_TYPE,
        memory_id=None,
        decision="skip",
        reason_code="tombstone_match",
        pii_classification=candidate.pii_classification,
        candidate_hash=identity["candidate_hash"],
        source_ref_json=identity["source_ref_json"],
    )
    return LongTermMemoryWriteResult(status="skipped", decision="skip", reason_code="tombstone_match", ...)

if is_blocked_memory_write_pii_classification(candidate.pii_classification):
    ...
    return LongTermMemoryWriteResult(status="skipped", decision="skip", reason_code="pii_blocked", ...)
```
(`src/memory/long_term.py` lines 66-130)

```python
review_status = _review_status_for_source(candidate.source_type)
decision = "write" if review_status == "auto_approved" else "needs_review"
reason_code = "auto_approved_source" if review_status == "auto_approved" else "requires_review"
memory = await self.repository.insert_memory(...)
event = await self.repository.emit_write_event(...)
return LongTermMemoryWriteResult(
    status="written" if review_status == "auto_approved" else "needs_review",
    memory_id=memory.id,
    review_status=review_status,
    decision=decision,
    reason_code=reason_code,
    pii_classification=candidate.pii_classification,
    candidate_hash=identity["candidate_hash"],
    content_hash=identity["content_hash"],
    source_identity_hash=identity["source_identity_hash"],
    event_id=event.id,
)
```
(`src/memory/long_term.py` lines 177-211)

**Retrieval filter pattern:** case memory retrieval filters by tenant, scope, published review statuses, non-deleted, non-expired, prompt-safe PII, and active tombstone exclusion before results (`src/memory/case_memory.py` lines 431-440). Use this behavior through `CaseMemoryService.retrieve_reviewed`; do not reimplement filtering in the node.

### Replay / Audit Boundary

**Source:** `src/replay/decision_events.py`, `src/replay/validators.py`
**Apply to:** memory status refs and memory write decision trace/event metadata.

```python
SCHEMA_VERSION = "minimal_event_envelope.v1"
REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$")
OPERATION_EVENT_PREFIXES = ("node_", "tool_call_", "rag_retrieval_", "llm_call_", "memory_write_")
```
(`src/replay/decision_events.py` lines 20-23)

```python
REPLAY_EVENT_TYPES: set[str] = {
    ...
    "memory_write_started",
    "memory_write_completed",
    "memory_write_failed",
    ...
}

EVENT_RETENTION_CLASSIFICATION: dict[str, str] = {
    ...
    "memory_write_started": "memory_event",
    "memory_write_completed": "memory_event",
    "memory_write_failed": "memory_event",
    ...
}
```
(`src/replay/validators.py` lines 8-32 and 34-58)

**Apply:** Phase 31 status refs are audit-ready and contextual-only; do not make them replay-authoritative `ReplayEventV3` inputs. Full replay coverage is Phase 35.

## Testing Patterns

### Session Context Node Tests

**Source:** `tests/agent/test_session_memory_load.py`
**Apply to:** `tests/agent/test_session_memory_load.py` or new `tests/agent/test_session_context_load.py`.

```python
async def test_session_memory_load_disabled_returns_empty_fallback(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", False)

    result = await session_memory_load(_state(), {"configurable": {"session": object()}})

    memory = result["session_memory"]
    metrics = result["trace_steps"][-1]["metrics_json"]
    assert memory["continuity_claimed"] is False
    assert memory["active_slots"] == {}
    assert memory["source"] == "disabled"
    assert memory["fallback_reason"] == "disabled"
    assert metrics["fallback_reason"] == "disabled"
```
(`tests/agent/test_session_memory_load.py` lines 20-31)

```python
assert result["session_memory"]["active_slots"] == {"order_id": "ORD-BUNDLE-NODE"}
assert result["session_memory"]["version"] == 9
assert result["session_memory_bundle"]["rolling_summary"]["summary_text"] == (
    "bundle rolling summary for ORD-BUNDLE-NODE"
)
assert result["session_memory_bundle"]["slot_continuity"]["active_slots"]["order_id"] == "ORD-BUNDLE-NODE"
```
(`tests/agent/test_session_memory_load.py` lines 104-109)

**Add Phase 31 assertions:** target `session_context`, `session_context_bundle`, `session_context_load_status["schema_version"] == "session_context_load_status.v1"`, and `authority_class == "contextual_only"`, while old `session_memory` fields remain populated.

### Session Bundle Tests

**Source:** `tests/memory/test_session_memory_bundle.py`

```python
bundle = await bundle_service.load_session_memory_bundle(
    tenant_id=tenant_id,
    user_id=user_id,
    thread_id=thread_id,
    run_id=current_run_id,
    current_intent="refund_troubleshooting",
    max_recent_messages=4,
)

assert bundle.rolling_summary is not None
assert [message.content for message in bundle.recent_messages][-1] == "follow-up: 继续查这个订单 ORD-BUNDLE-CURRENT。"
assert bundle.tool_summaries[0].tool_name == "get_order"
assert bundle.slot_continuity.active_slots["order_id"] == "ORD-BUNDLE-CURRENT"
...
for forbidden in ("raw_payload", "private_reasoning", "approval_authority_body", "debug_trace", "secret"):
    assert forbidden not in serialized
```
(`tests/memory/test_session_memory_bundle.py` lines 167-193)

### Reviewed Memory Retrieval Tests

**Source:** `tests/memory/test_case_memory_retrieval.py`

```python
result = await service.submit_case_memory_candidate(candidate)
before_approval = await service.retrieve_reviewed(CaseMemorySearchRequest(...))
approved_event = await service.approve_case_memory(CaseMemoryReviewDecision(...))
after_approval = await service.retrieve_reviewed(CaseMemorySearchRequest(...))

assert result.status == "needs_review"
assert result.review_status == "needs_review"
assert before_approval.items == []
assert [item.case_memory_id for item in after_approval.items] == [str(row.id)]
assert approved_event.memory_type == CASE_MEMORY_TYPE
assert approved_event.decision == "write"
```
(`tests/memory/test_case_memory_retrieval.py` lines 151-208)

```python
filtered_rows = [
    _case_row(seeded_session, summary="Needs review must not surface.", review_status="needs_review"),
    _case_row(seeded_session, summary="Rejected must not surface.", review_status="rejected"),
    _case_row(seeded_session, summary="Deleted must not surface.", deleted_at=now),
    _case_row(seeded_session, summary="Expired must not surface.", expires_at=now - timedelta(seconds=1)),
    _case_row(seeded_session, summary="Sensitive must not surface.", pii_classification="sensitive"),
    _case_row(seeded_session, summary="Prohibited must not surface.", pii_classification="prohibited"),
    _case_row(seeded_session, summary="Cross tenant must not surface.", tenant_id=other_tenant_id),
]
...
assert [item.case_memory_id for item in result.items] == [str(visible.id), str(visible_auto.id)]
```
(`tests/memory/test_case_memory_retrieval.py` lines 363-430)

**Add Phase 31 assertions:** missing `TrustedContext`, empty merchant scope, denied merchant, untrusted case merchant, tenant/global scope, deleted/expired/unreviewed/non-prompt-safe rows all return empty target bundle plus status refs with deterministic filter/fallback reasons.

### Authority Boundary Tests

**Source:** `tests/agent/test_memory_evidence_boundary.py`, `tests/agent/rag_context/test_authority_boundaries.py`

```python
def test_session_memory_modules_do_not_import_evidence_ref_v1() -> None:
    memory_sources = "\n".join(path.read_text() for path in Path("src/memory").glob("*.py"))
    memory_write_source = Path("src/agent/nodes/memory_write.py").read_text()

    assert "from src.knowledge.schemas import EvidenceRefV1" not in memory_sources
    assert "EvidenceRefV1" not in memory_sources
    assert "from src.knowledge.schemas import EvidenceRefV1" not in memory_write_source
    assert "EvidenceRefV1(" not in memory_write_source
```
(`tests/agent/test_memory_evidence_boundary.py` lines 58-65)

```python
assert final_state["retrieved_evidence"]["evidence_refs"] == []
assert final_state["policy_evidence"] == []
assert final_state.get("evidence_refs", []) == []
assert final_state["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
assert final_state.get("approval_result") is None
assert final_state.get("action_result") is None
assert final_state.get("proposed_action") is None
```
(`tests/agent/test_memory_evidence_boundary.py` lines 203-210 and 266-274)

```python
assert {
    "policy_evidence_required",
    "memory_not_policy_authority",
    "model_knowledge_not_policy_authority",
} <= set(result.reason_codes)
```
(`tests/agent/rag_context/test_authority_boundaries.py` lines 137-143)

```python
assert {"business_fact_ref_required", expected_reason} <= set(result.reason_codes)
```
(`tests/agent/rag_context/test_authority_boundaries.py` lines 269-276)

### Write Decision Tests

**Source:** `tests/agent/test_memory_write_node.py`

```python
async def test_memory_write_failure_preserves_final_response(monkeypatch):
    ...
    result = await memory_write(state, {"configurable": {"session": object()}})

    assert result["final_response"] == "不可变最终回复"
    assert result["memory_write_result"]["status"] == "error"
    assert result["node_errors"][-1]["error_code"] == "SESSION_MEMORY_WRITE_FAILED"
```
(`tests/agent/test_memory_write_node.py` lines 90-105)

```python
result = await memory_write(
    _state(extracted_slots={"order_id": raw_identifier}),
    {"configurable": {"session": object()}},
)

assert called is False
assert result["memory_write_result"]["status"] == "skipped"
assert result["memory_write_result"]["decision"] == "skip"
assert result["memory_write_result"]["pii_classification"] == "sensitive"
assert result["memory_write_result"]["reason_code"] == "pii_blocked"
```
(`tests/agent/test_memory_write_node.py` lines 382-390)

**Add Phase 31 assertions:** `memory_write_decision["schema_version"] == "memory_write_decision.v2"`, `authority_class == "contextual_only"`, includes memory type/scope/source identity/candidate hash/review status/fallback reason, and preserves `memory_write_result`.

### Trusted Scope Tests

**Source:** `tests/platform/test_merchant_scope.py`, `tests/platform/test_trusted_context.py`

```python
def test_merchant_scope_denies_empty_scope() -> None:
    scope = MerchantScopeV1(merchant_ids=[])

    assert merchant_scope_allows(scope, merchant_id="merchant-1") is False
    assert merchant_scope_allows(scope, category="electronics") is False
    assert merchant_scope_allows(scope, risk_level="high") is False
```
(`tests/platform/test_merchant_scope.py` lines 30-35)

```python
@pytest.mark.parametrize(
    "payload",
    [
        {"merchant_ids": [""]},
        {"merchant_ids": ["merchant-1"], "categories": [""]},
        {"merchant_ids": ["merchant-1"], "risk_levels": [""]},
        {"merchant_ids": ["merchant-1"], "match_rule": "any_dimension"},
        {"merchant_ids": ["merchant-1"], "source": "llm"},
        {"merchant_ids": ["merchant-1"], "user_supplied_scope": {"merchant_ids": ["*"]}},
    ],
)
def test_merchant_scope_rejects_invalid_values(payload: dict) -> None:
    with pytest.raises(ValidationError):
        MerchantScopeV1.model_validate(payload)
```
(`tests/platform/test_merchant_scope.py` lines 60-73)

## No Analog Found

None. New Phase 31 files have role-match or exact analogs in the current memory, graph-node, trusted-context, replay, and authority-boundary code.

## Metadata

**Analog search scope:** `src/memory`, `src/agent`, `src/platform`, `src/knowledge`, `src/tools`, `src/approvals`, `src/replay`, `tests/memory`, `tests/agent`, `tests/platform`, `tests/business`, `tests/knowledge`, `tests/replay`

**Files scanned:** `rg --files src tests` plus Phase 31 context/research artifacts.

**Pattern extraction date:** 2026-06-28

**Validation command rule:** Any planner-generated verification must use `uv run pytest ...` or a verified repo `.venv/bin/pytest ...`; bare `pytest` is invalid in MOCA.
