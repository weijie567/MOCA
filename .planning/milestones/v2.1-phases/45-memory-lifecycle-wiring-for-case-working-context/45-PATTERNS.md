# Phase 45: Memory Lifecycle Wiring for Case Working Context - Pattern Map

**Mapped:** 2026-07-03
**Files analyzed:** 16 likely new/modified files
**Analogs found:** 16 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/memory/case_working_context_lifecycle.py` | service/adapter | request-response + CRUD + transform | `src/memory/case_working_context_service.py`; `src/agent/nodes/reviewed_memory_context_retrieve.py` | role-match |
| `src/memory/context_refs.py` | model/schema | transform | `src/memory/context_refs.py` | exact |
| `src/agent/state.py` | store/state contract | transform | `src/agent/state.py` | exact |
| `src/agent/nodes/receive_request.py` | node/hook | event-driven reset | `src/agent/nodes/receive_request.py` | exact |
| `src/agent/nodes/reviewed_memory_context_retrieve.py` | node/adapter | request-response read | `src/agent/nodes/reviewed_memory_context_retrieve.py` | exact |
| `src/agent/nodes/long_term_memory_retrieve.py` | node/compatibility wrapper | transform | `src/agent/nodes/long_term_memory_retrieve.py` | exact |
| `src/api/services/agent_run_memory.py` | service/finalizer | event-driven + file/DB side effects | `src/api/services/agent_run_memory.py` | exact |
| `src/agent/nodes/memory_write.py` | node/service | event-driven write | `src/agent/nodes/memory_write.py` | conditional exact |
| `src/agent/graph.py` | config/graph wiring | event-driven routing | `src/agent/graph.py` | conditional exact |
| `src/agent/graph_vocabulary.py` | config/utility | transform | `src/agent/graph_vocabulary.py` | conditional exact |
| `docs/contract-spec.md` | config/docs | contract transform | `docs/contract-spec.md` | exact |
| `tests/agent/test_case_working_context_lifecycle.py` | test | CRUD + request-response | `tests/memory/test_case_working_context_service.py`; `tests/memory/test_thread_case_links.py` | role-match |
| `tests/test_agent_runs_api.py` | test | request-response + event-driven | `tests/test_agent_runs_api.py` | exact |
| `tests/memory/test_phase45_contract_alignment.py` | test | contract transform | `tests/memory/test_phase44_contract_alignment.py` | role-match |
| `tests/agent/test_graph.py` | test | graph/event-driven | `tests/agent/test_graph.py` | exact |
| `tests/agent/test_graph_vocabulary.py` | test | transform | `tests/agent/test_graph_vocabulary.py` | exact |

## Pattern Assignments

### `src/memory/case_working_context_lifecycle.py` (service/adapter, request-response + CRUD + transform)

**Analogs:** `src/memory/case_working_context_service.py`, `src/memory/case_identity.py`, `src/conversation/repository.py`, `src/memory/thread_case_links.py`, `src/memory/case_working_context.py`

**Imports pattern** (from `src/memory/case_working_context_service.py` lines 7-17; `src/memory/case_identity.py` lines 6-11):
```python
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.case_working_context import CaseWorkingContextRepository
from src.memory.case_working_context_schemas import (
    CaseWorkingContextWriteCandidate,
    normalize_case_working_context_content_sources,
    normalize_case_working_context_source_ref,
)
```

**Result/status model pattern** (from `src/memory/case_working_context_service.py` lines 34-45):
```python
class CaseWorkingContextServiceWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["written", "blocked", "conflict"]
    memory_id: uuid.UUID | None = None
    version: int | None = None
    decision: Literal["write", "write_blocked", "skip"]
    reason_code: str
    pii_classification: Literal["none", "low", "sensitive", "prohibited"]
    candidate_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    event_id: uuid.UUID
```

**Fail-closed canonical case identity pattern** (from `src/memory/case_identity.py` lines 23-50):
```python
async def resolve_case_id(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    raw_case_ref: str | None,
) -> CaseIdentityResult:
    stripped = raw_case_ref.strip() if raw_case_ref is not None else ""
    if not stripped:
        return CaseIdentityResult(status="invalid", case_id=None, input_form="unknown")

    parsed_case_id = _parse_uuid(stripped)
    if parsed_case_id is not None:
        result = await session.execute(
            select(RefundCase).where(
                RefundCase.id == parsed_case_id,
                RefundCase.tenant_id == tenant_id,
            )
        )
        refund_case = result.scalar_one_or_none()
        if refund_case is not None:
            return CaseIdentityResult(status="resolved", case_id=refund_case.id, input_form="uuid")
        return CaseIdentityResult(status="not_found", case_id=None, input_form="uuid")
```

**Explicit thread-case link pattern** (from `src/conversation/repository.py` lines 97-121):
```python
async def link_case(
    self,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    thread_id: str,
    case_id: uuid.UUID,
    link_source: str,
    linked_by_run_id: uuid.UUID | None = None,
) -> ThreadCaseLink:
    from src.memory.thread_case_links import ThreadCaseLinkRepository

    thread = await self.get_or_create_thread(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
    )
    return await ThreadCaseLinkRepository(self.session).link_thread_to_case(
        tenant_id=tenant_id,
        conversation_thread_id=thread.id,
        thread_id=thread.thread_id,
        case_id=case_id,
        link_source=link_source,
        linked_by_run_id=linked_by_run_id,
    )
```

**Link dedupe/tenant guard pattern** (from `src/memory/thread_case_links.py` lines 19-62, 115-153):
```python
if link_source not in ALLOWED_THREAD_CASE_LINK_SOURCES:
    raise ValueError(f"link_source must be one of {sorted(ALLOWED_THREAD_CASE_LINK_SOURCES)}")

await self._lock_link_scope(
    tenant_id=tenant_id,
    conversation_thread_id=conversation_thread_id,
    case_id=case_id,
)
validated_thread_id = await self._validate_scope(
    tenant_id=tenant_id,
    conversation_thread_id=conversation_thread_id,
    case_id=case_id,
    linked_by_run_id=linked_by_run_id,
)
existing = await self._get_active_link(
    tenant_id=tenant_id,
    conversation_thread_id=conversation_thread_id,
    case_id=case_id,
)
if existing is not None:
    return existing
```

**Active CWC read pattern** (from `src/memory/case_working_context.py` lines 48-61):
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
```

**Audited isolated write pattern** (from `src/memory/case_working_context_service.py` lines 47-58, 76-146):
```python
class CaseWorkingContextService:
    async def write_case_working_context(
        self,
        parent_session: AsyncSession,
        candidate: CaseWorkingContextWriteCandidate,
        *,
        run_id: uuid.UUID,
    ) -> CaseWorkingContextServiceWriteResult:
        _validate_write_inputs(candidate=candidate, run_id=run_id)
        trusted_candidate = _trusted_write_candidate(candidate=candidate, run_id=run_id)

        async def operation(child_session: AsyncSession) -> CaseWorkingContextServiceWriteResult:
            ...
            if trusted_candidate.pii_classification in BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS:
                event = await _emit_write_event(...)
                return CaseWorkingContextServiceWriteResult(
                    status="blocked",
                    decision="write_blocked",
                    reason_code="pii_blocked",
                    ...
                )
            repository_result = await CaseWorkingContextRepository(child_session).write_working_context(trusted_candidate)
            if repository_result.status == "conflict":
                event = await _emit_write_event(...)
                return CaseWorkingContextServiceWriteResult(
                    status="conflict",
                    decision="skip",
                    reason_code="version_conflict",
                    ...
                )
            ...
        return await run_memory_side_effect_in_isolated_session(parent_session, operation)
```

**Apply to Phase 45:** lifecycle adapter should orchestrate resolve -> link -> read and terminal project -> write, but it should not reimplement CWC repository/service semantics.

---

### `src/memory/context_refs.py` (model/schema, transform)

**Analog:** `src/memory/context_refs.py`

**Pydantic contextual-only status/bundle pattern** (lines 40-83, 116-125):
```python
class ReviewedMemoryContextRetrieveStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["reviewed_memory_context_retrieve_status.v1"] = (
        "reviewed_memory_context_retrieve_status.v1"
    )
    status: str
    authority_class: Literal["contextual_only"] = "contextual_only"
    trusted_scope_inputs: dict[str, Any] = Field(default_factory=dict)
    effective_scopes: list[dict[str, Any]] = Field(default_factory=list)
    filter_reasons: list[str] = Field(default_factory=list)
    retrieved_refs: list[ReviewedMemoryRef] = Field(default_factory=list)
    fallback_reason: str | None = None

class MemoryContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["memory_context_bundle.v1"] = "memory_context_bundle.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    session_context: SessionContextMemory
    long_term_items: list[dict[str, Any]] = Field(default_factory=list)
    case_items: list[dict[str, Any]] = Field(default_factory=list)
    session_status_ref: SessionContextLoadStatusV1 | None = None
    reviewed_status_ref: ReviewedMemoryContextRetrieveStatusV1 | None = None
```

**Apply to Phase 45:** add optional CWC-specific status/ref fields with `extra="forbid"` and `authority_class="contextual_only"`. Keep CWC separate from `case_items` / reviewed `case_memory`.

---

### `src/agent/state.py` and `src/agent/nodes/receive_request.py` (state contract + reset)

**Analogs:** `src/agent/state.py`, `src/agent/nodes/receive_request.py`

**AgentState field placement pattern** (from `src/agent/state.py` lines 70-128):
```python
# Ephemeral context: reset by receive_request at the start of each turn.
user_query: str | None
...
session_context: dict[str, Any] | None
session_context_bundle: dict[str, Any] | None
session_context_load_status: dict[str, Any] | None
session_memory: dict[str, Any] | None
session_memory_bundle: dict[str, Any] | None
memory_context: dict[str, Any] | None
memory_context_bundle: dict[str, Any] | None
reviewed_memory_context_retrieve_status: dict[str, Any] | None
memory_write_candidates: list[dict[str, Any]] | None
memory_write_result: dict[str, Any] | None
memory_write_decision: dict[str, Any] | None
long_term_memory: list[dict[str, Any]] | None
```

**Reset pattern** (from `src/agent/nodes/receive_request.py` lines 61-119):
```python
return {
    "user_query": state.get("user_query"),
    "normalized_query": None,
    ...
    "session_context": None,
    "session_context_bundle": None,
    "session_context_load_status": None,
    "session_memory": None,
    "session_memory_bundle": None,
    "memory_context": None,
    "memory_context_bundle": None,
    "reviewed_memory_context_retrieve_status": None,
    "memory_write_candidates": None,
    "memory_write_result": None,
    "memory_write_decision": None,
    "long_term_memory": None,
    ...
}
```

**Apply to Phase 45:** any new `case_working_context*` state fields must be declared in `AgentState`, reset in `receive_request`, and covered by contract-alignment tests. Prefer additive fields or optional `MemoryContextBundle` fields over repurposing `case_memory`.

---

### `src/agent/nodes/reviewed_memory_context_retrieve.py` and `src/agent/nodes/long_term_memory_retrieve.py` (memory-context read seam)

**Analogs:** `src/agent/nodes/reviewed_memory_context_retrieve.py`, `src/agent/nodes/long_term_memory_retrieve.py`

**Dependency-injection/service lookup pattern** (from `src/agent/nodes/reviewed_memory_context_retrieve.py` lines 30-60, 77-100):
```python
async def reviewed_memory_context_retrieve(
    state: AgentState,
    config: RunnableConfig,
    *,
    memory_context_service_cls: Any | None = None,
    long_term_memory_repository_cls: Any | None = None,
    case_memory_repository_cls: Any | None = None,
    long_term_memory_service_cls: Any | None = None,
    case_memory_service_cls: Any | None = None,
) -> dict:
    started_at = _now_iso()
    configurable = (config.get("configurable") or {}) if config else {}
    try:
        context_service = _context_service(...)
        bundle = await context_service.load_reviewed_memory_context(...)
    except Exception:
        bundle = _empty_bundle(...)
        result = _context_result(state, started_at, bundle=bundle)
        result["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "reviewed_memory_context_retrieve", "error_code": _SERVICE_ERROR_CODE}
        ]
        return result
```

**Context result/trace pattern** (from `src/agent/nodes/reviewed_memory_context_retrieve.py` lines 103-131):
```python
def _context_result(state: AgentState, started_at: str, *, bundle: ReviewedMemoryContextBundle) -> dict[str, Any]:
    memory_context = bundle.model_dump(mode="json")
    memory_context["schema_version"] = _BUNDLE_SCHEMA_VERSION
    unified_memory_context = _unified_memory_context_bundle(state, bundle=bundle)
    long_term_items = list(memory_context["long_term_items"])
    case_items = list(memory_context["case_items"])
    status_ref = dict(memory_context["status_ref"])
    metrics = _metrics(memory_context)
    step = {
        "node": "reviewed_memory_context_retrieve",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": metrics,
    }
    return {
        "memory_context": memory_context,
        "memory_context_bundle": unified_memory_context or memory_context,
        "reviewed_memory_context_retrieve_status": status_ref,
        "long_term_memory": long_term_items,
        "case_memory": case_items,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "reviewed_memory_context_retrieve": metrics,
        },
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }
```

**Legacy wrapper pattern** (from `src/agent/nodes/long_term_memory_retrieve.py` lines 15-31):
```python
async def long_term_memory_retrieve(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the reviewed memory context boundary."""
    result = await reviewed_memory_context_retrieve(
        state,
        config,
        long_term_memory_repository_cls=LongTermMemoryRepository,
        case_memory_repository_cls=CaseMemoryRepository,
        long_term_memory_service_cls=LongTermMemoryService,
        case_memory_service_cls=CaseMemoryService,
    )
    legacy_metrics = _legacy_metrics(result)
    result["llm_outputs"] = {
        **(state.get("llm_outputs") or {}),
        **(result.get("llm_outputs") or {}),
        "long_term_memory_retrieve": legacy_metrics,
    }
    return result
```

**Apply to Phase 45:** put CWC active-read invocation at this seam or behind the same adapter. Preserve existing long-term/reviewed outputs and append CWC status/trace without converting CWC into `case_memory`.

---

### `src/api/services/agent_run_memory.py` (terminal finalizer write hook)

**Analog:** `src/api/services/agent_run_memory.py`

**Finalizer skip and terminal persistence pattern** (lines 41-83):
```python
async def finalize_completed_agent_run_memory(
    *,
    session: AsyncSession,
    run: AgentRun,
    user: User,
    input_state: dict[str, Any],
    final_state: dict[str, Any],
    final_status: str,
    final_response: str | None,
    trace_steps: list[dict[str, Any]],
    trace_id: str | None = None,
    conversation_service: ConversationService | None = None,
) -> AgentRunMemoryFinalizeResult:
    started_at = _now_iso()
    if final_status != "completed" or not _has_final_response(final_response):
        return AgentRunMemoryFinalizeResult(
            status="skipped",
            assistant_message_id=None,
            thread_summary_id=None,
            memory_write_status="skipped",
            memory_write_result={"status": "skipped", "reason_code": "not_completed_path"},
            trace_steps=[],
        )

    conversation_repository = _conversation_repository(session, conversation_service)
    conversation_service = conversation_service or ConversationService(conversation_repository)
    assistant_message = await conversation_service.append_or_get_assistant_message_for_run(...)
    thread_summary = await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(...)
    await session.commit()
    memory_write_execution = await _run_terminal_memory_write(...)
```

**Isolated memory side effect pattern** (lines 123-168):
```python
try:
    result_state = await run_memory_side_effect_in_isolated_session(
        session,
        lambda memory_session: memory_write(
            memory_state,
            {"configurable": {"session": memory_session, "trace_id": trace_id or ""}},
        ),
    )
except TimeoutError:
    return TerminalMemoryWriteExecution(
        result={"status": "skipped", "reason_code": "write_timeout"},
        duration_ms=_duration_ms(started),
    )
except Exception as exc:
    return TerminalMemoryWriteExecution(
        result={"status": "error", "reason_code": "write_failed", "error_type": type(exc).__name__},
        duration_ms=_duration_ms(started),
    )
```

**Trace metrics pattern** (lines 208-235):
```python
return {
    "node": FINALIZER_NODE,
    "status": memory_write_status,
    "started_at": started_at,
    "completed_at": _now_iso(),
    "provider_latency_ms": None,
    "retry_count": 0,
    "metrics_json": {
        "assistant_message_id": assistant_message_id,
        "thread_summary_id": thread_summary_id,
        "memory_write_status": memory_write_status,
        "memory_write_reason_code": memory_write_result.get("reason_code"),
        "memory_write_duration_ms": memory_write_duration_ms,
        "slot_count": memory_write_result.get("slot_count"),
        "fallback_reason": memory_write_result.get("fallback_reason"),
        "pii_decision": memory_write_result.get("decision"),
        "pii_classification": memory_write_result.get("pii_classification"),
    },
}
```

**Apply to Phase 45:** add CWC write after terminal rows are committed and generic memory write remains isolated. CWC skip/conflict/error should be reflected in finalizer result/metrics without rolling back assistant message or summary.

---

### `src/agent/nodes/memory_write.py` (optional canonical memory_write extension)

**Analog:** `src/agent/nodes/memory_write.py`

**Skip/error status pattern** (lines 42-81, 175-214):
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
    ...
    except TimeoutError:
        ...
        return _skipped(state, started_at, "write_timeout", final_response=final_response)
    except Exception:
        ...
        return _error(state, started_at, final_response)
```

**Decision projection pattern** (lines 152-172, 217-233):
```python
def _completed(...):
    result_dict = result.model_dump(mode="json")
    decision = _memory_write_decision(state, result_dict, candidate=candidate)
    output = {
        "final_response": state.get("final_response"),
        "memory_write_candidates": [_candidate_projection(item) for item in (candidates or [candidate])],
        "memory_write_result": result_dict,
        "memory_write_decision": decision,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result_dict, decision)],
    }
```

**Apply to Phase 45:** if planner wires CWC through `memory_write`, keep CWC business rules in the lifecycle adapter and copy this node's explicit skip/result/trace shape.

---

### `src/agent/graph.py` and `src/agent/graph_vocabulary.py` (conditional graph/spec alignment)

**Analogs:** `src/agent/graph.py`, `src/agent/graph_vocabulary.py`

**Current graph node/edge pattern** (from `src/agent/graph.py` lines 276-294, 307-317, 374-377):
```python
def build_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the refund agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
    builder.add_node("session_memory_load", session_memory_load)
    builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
    builder.add_node("long_term_memory_retrieve", long_term_memory_retrieve)
    ...
    builder.add_edge("session_memory_load", "extract_slots")
    builder.add_conditional_edges("extract_slots", route_after_slots, {...})
    builder.add_edge("long_term_memory_retrieve", "investigate")
    ...
    builder.add_edge("action_draft", "final_response")
    builder.add_edge("final_response", END)

    return builder.compile(checkpointer=checkpointer)
```

**Vocabulary alias pattern** (from `src/agent/graph_vocabulary.py` lines 41-58, 129-139):
```python
_ENTRIES: tuple[GraphVocabularyEntry, ...] = (
    _entry("receive_request", "receive_request", "node", "runtime", True),
    ...
    _entry("memory_write", "memory_write", "node", "runtime", True),
    ...
    _entry("long_term_memory_retrieve", "memory_context_load", "node", "compatibility_alias", True),
    _entry("reviewed_memory_context_retrieve", "memory_context_load", "node", "runtime", True),
    _entry("memory_context_load", "memory_context_load", "node", "compatibility_alias", True),
)
```

**Apply to Phase 45:** do not depend CWC lifecycle semantics on current graph order. If graph alignment is included, update graph tests/vocabulary together.

---

### `docs/contract-spec.md` (contract/spec alignment)

**Analog:** `docs/contract-spec.md`

**Graph node contract pattern** (lines 642-652):
```markdown
| `memory_context_load` | tenant/user/merchant scope, resolved intent/slots | `memory_context_bundle`, `long_term_memory`, `case_memory` | MemoryContextService post-slot retrieval | none | unavailable -> continue without long-term/case memory and event | fixed -> `investigate` |
| `final_response` | current state, recommendation/action/approval results | `final_response` | deterministic template first; optional final prompt | none | fallback safe error response | fixed -> `memory_write` |
| `memory_write` | final state, outcome, memory candidates | `memory_write_result`, session summary | MemoryService write policy | writes session memory; may enqueue long-term/case candidates | write failure logged; does not block user response | fixed -> lifecycle finalizer |
```

**AgentState registry pattern** (lines 856-872, 896-897, 920-922):
```markdown
| Memory context | `session_context`, `session_memory`, `memory_context_bundle`, `long_term_memory`, `case_memory` | turn read context | MemoryService | session_context_load / memory_context_load | reset loaded context each turn | replace loaded context; memory store owns persistence | memory tables |
| Memory write | `memory_write_candidates`, `memory_write_result` | run | memory_write node / MemoryService | memory_write | reset each new run | candidates replace; result replace | memory write events |
...
| `memory_context_bundle`, `long_term_memory`, `case_memory` | dict/list | memory_context_load / MemoryService | recommendation_generation, investigate planning | reset loaded view each turn; replace | memory tables / AgentStep refs |
...
| `final_response` | dict or null | final_response | API, memory_write, trace_close | reset each turn; replace | AgentRun final response |
| `memory_write_candidates` | `list[dict[str, Any]]` | memory_write candidate adapter | MemoryService | reset each run; validated replace | memory write events |
| `memory_write_result` | dict or null | MemoryService | trace_close, replay | reset each run; replace | memory write events / AgentStep |
```

**CWC authority/red-line pattern** (lines 1514-1526, 2562-2563):
```markdown
Semantic lock: `case_memories` / `case_memory` are reviewed precedent, NOT active case state. Active current-case state belongs to Case Working Context.

Case Working Context is a durable working-state memory layer for one active refund case. It is stored in `case_working_contexts`, scoped by `(tenant_id, case_id)`, where `case_id` is bound to `refund_cases.id` (UUID), and every row has `authority_class = contextual_only`.

Thread-to-case membership is additive many-to-many: `thread_case_links` records tenant + thread + `refund_cases.id` associations and does not drop, rename, retype, or replace the legacy single `conversation_threads.case_id` column.
```

**Apply to Phase 45:** if new CWC fields/statuses are added, update §9 node outputs, §10 AgentState schema/lifecycle/registry, and §13 CWC semantics together. Make implementation compromises explicit; do not silently diverge from this spec.

---

## Shared Patterns

### Deterministic CWC Content Projection

**Sources:** `src/memory/case_working_context_schemas.py` lines 74-101, 104-155

```python
class CaseWorkingContextContentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_class: Literal["contextual_only"] = "contextual_only"
    customer_request: str | None = None
    issue_type: str | None = None
    claims: list[CaseWorkingContextClaimV1] = Field(default_factory=list)
    verified_facts: list[CaseWorkingContextVerifiedFactV1] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    evidence_refs: list[CaseWorkingContextEvidencePointerV1] = Field(default_factory=list)
    actions_taken: list[CaseWorkingContextActionTakenV1] = Field(default_factory=list)
    policy_refs: list[CaseWorkingContextPolicyRefV1] = Field(default_factory=list)
    agent_recommendations: list[CaseWorkingContextRecommendationV1] = Field(default_factory=list)
    pending_tasks: list[str] = Field(default_factory=list)
    commitments: list[CaseWorkingContextCommitmentV1] = Field(default_factory=list)
    next_action: CaseWorkingContextNextActionV1 = Field(default_factory=CaseWorkingContextNextActionV1)
```

Use these schemas for projection. Do not store policy body text or sensitive raw PII. Claims and verified facts must remain separate.

### Terminal Side-Effect Isolation

**Sources:** `src/api/services/agent_run_memory.py` lines 82-92, 123-168; `src/memory/case_working_context_service.py` line 146

```python
await session.commit()
memory_write_execution = await _run_terminal_memory_write(...)
...
return await run_memory_side_effect_in_isolated_session(parent_session, operation)
```

CWC write failure/conflict/PII block should become status/trace data, not a rollback of terminal user-visible rows.

### Trace Step Shape

**Sources:** `src/agent/nodes/reviewed_memory_context_retrieve.py` lines 111-130; `src/api/services/agent_run_memory.py` lines 217-235

```python
step = {
    "node": "reviewed_memory_context_retrieve",
    "status": "completed",
    "started_at": started_at,
    "completed_at": _now_iso(),
    "provider_latency_ms": None,
    "retry_count": 0,
    "metrics_json": metrics,
}
```

New lifecycle statuses should follow this shape and use explicit reason codes such as `skipped_no_case`, `blocked_pii`, `conflict`, and `error`.

### Test Entrypoint

All planner verification commands must use the MOCA-approved entrypoint:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...
```

Bare `pytest` and bare `python -m pytest` are invalid for this repository.

## Testing Patterns

### New `tests/agent/test_case_working_context_lifecycle.py`

**Analogs:** `tests/memory/test_case_working_context_service.py`, `tests/memory/test_thread_case_links.py`

**Service validation before isolated DB write** (from `tests/memory/test_case_working_context_service.py` lines 179-209):
```python
async def fail_if_isolation_opens(*args, **kwargs):  # pragma: no cover - proves validation order
    pytest.fail("isolated write opened before validation")

monkeypatch.setattr(service_module, "run_memory_side_effect_in_isolated_session", fail_if_isolation_opens)
...
with pytest.raises(ValueError):
    await service.write_case_working_context(
        session,
        invalid_candidate,  # type: ignore[arg-type]
        run_id=run_id,  # type: ignore[arg-type]
    )
```

**CWC write/audit assertions** (from `tests/memory/test_case_working_context_service.py` lines 277-300):
```python
result = await service_module.CaseWorkingContextService().write_case_working_context(
    session,
    candidate,
    run_id=scope["run"].id,
)
row = await CaseWorkingContextRepository(session).read_active(
    tenant_id=scope["tenant"].id,
    case_id=scope["refund_case"].id,
)
events = await _events(session, scope["run"].id)

assert result.status == "written"
assert result.decision == "write"
assert result.memory_id == row.id
assert events[-1].memory_type == "case_working_context"
assert events[-1].authority_class == "contextual_only"
```

**PII block/conflict assertions** (from `tests/memory/test_case_working_context_service.py` lines 429-450, 467-486):
```python
assert result.status == "blocked"
assert result.decision == "write_blocked"
assert result.reason_code == "pii_blocked"
assert result.memory_id is None
assert row is None
...
assert conflict.status == "conflict"
assert conflict.decision == "skip"
assert conflict.reason_code == "version_conflict"
assert conflict.memory_id is None
```

**Thread-case link dedupe and explicit append-message red line** (from `tests/memory/test_thread_case_links.py` lines 126-156, 349-396):
```python
first = await repository.link_thread_to_case(..., link_source="run_auto", linked_by_run_id=scope["run"].id)
second = await repository.link_thread_to_case(..., link_source="run_auto", linked_by_run_id=scope["run"].id)
assert first.id == second.id
assert first.link_source == "run_auto"
assert first.linked_by_run_id == scope["run"].id
assert active_count == 1
...
await repository.append_message(...)
count_after_append = await session.scalar(select(func.count()).select_from(ThreadCaseLink))
assert count_after_append == 0
```

### `tests/test_agent_runs_api.py`

**Analog:** `tests/test_agent_runs_api.py`

**Finalizer assistant message/trace pattern** (lines 1236-1268):
```python
await _run_agent_run_stream(client, str(run_id), user)

assistant_messages = await _messages_for_run(session, run_id=run_id, role="assistant")
assert len(assistant_messages) == 1
assert assistant_messages[0].content == "done"
assert assistant_messages[0].metadata_json["status"] == "completed"
assert assistant_messages[0].metadata_json["source"] == "agent_runs.finalizer"
...
metrics = finalizer_step.metrics_json or {}
assert metrics["assistant_message_id"] == str(assistant_messages[0].id)
assert metrics["memory_write_status"] in {"completed", "skipped", "error", "failed"}
```

**Skip non-completed path pattern** (lines 2299-2323):
```python
result = await finalize_completed_agent_run_memory(
    session=session,
    run=run,
    user=user,
    input_state=_stream_input(run, user),
    final_state={"final_response": "x"},
    final_status="error",
    final_response="x",
    trace_steps=[],
    trace_id=None,
)

assert result.status == "skipped"
assert result.trace_steps == []
assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 0
assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
assert await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run.id) == 0
```

**Rollback preservation pattern** (lines 2327-2383):
```python
async def fake_memory_write(final_state, config):
    memory_session = config["configurable"]["session"]
    assert memory_session is not session
    await memory_session.rollback()
    return {
        **final_state,
        "memory_write_result": {
            "status": "fallback",
            "reason_code": "unavailable",
            "decision": "skip",
            "pii_classification": "none",
        },
        "trace_steps": [],
    }

monkeypatch.setattr("src.api.services.agent_run_memory.memory_write", fake_memory_write)
...
assert result.memory_write_status == "failed"
assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 1
assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 1
```

**Duplicate SSE/idempotence pattern** (lines 2529-2621):
```python
calls = {
    "assistant_message": 0,
    "finalizer": 0,
    "graph": 0,
    "memory_write": 0,
    "summary": 0,
    "user_message": 0,
}
...
assert calls_after_first == {
    "assistant_message": 1,
    "finalizer": 1,
    "graph": 1,
    "memory_write": 1,
    "summary": 1,
    "user_message": 1,
}
assert counts_after_duplicate == counts_after_first
assert calls == calls_after_first
```

### `tests/memory/test_phase45_contract_alignment.py`

**Analog:** `tests/memory/test_phase44_contract_alignment.py`

**Doc section assertion pattern** (lines 6-19, 29-42, 53-63):
```python
ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"

def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _section_13() -> str:
    source = _source(CONTRACT_SPEC_PATH)
    section_start = source.index("## 13. Memory 设计")
    section_end = source.index("## 14. Prompt 设计")
    return source[section_start:section_end]
...
for term in (
    "Case Working Context",
    "case_working_contexts",
    "authority_class = contextual_only",
):
    assert term in section
```

**Apply to Phase 45:** add assertions for any new AgentState fields, `memory_context_load` CWC output/status, terminal write semantics, and red lines: no `case_memories` backfill, no `active_slots` writer from `investigate`, no LLM summarizer.

### `tests/agent/test_graph_vocabulary.py` and `tests/agent/test_graph.py`

**Graph vocabulary assertion pattern** (from `tests/agent/test_graph_vocabulary.py` lines 13-44, 65-90):
```python
@pytest.mark.parametrize(
    ("name", "kind", "target_name", "status", "runnable"),
    [
        ("long_term_memory_retrieve", "node", "memory_context_load", "compatibility_alias", True),
        ("reviewed_memory_context_retrieve", "node", "memory_context_load", "runtime", True),
    ],
)
def test_legacy_graph_names_project_to_target_vocabulary(...):
    entry = graph_vocabulary_entry(name, kind=kind)
    assert entry is not None
    assert entry.legacy_name == name
    assert entry.target_name == target_name
    assert entry.kind == kind
    assert entry.status == status
    assert entry.runnable is runnable
```

**Apply to Phase 45:** if graph wiring changes, update vocabulary tests in the same plan.

## No Analog Found

No files lack an analog. The new lifecycle adapter has no exact prior file, but it has strong role-match analogs across CWC service, memory-context retrieve, finalizer, and thread-case link repositories.

## Metadata

**Analog search scope:** `src/memory`, `src/agent`, `src/api/services`, `src/conversation`, `tests`, `docs/contract-spec.md`
**Files scanned:** 34 candidate source/test/doc paths via `rg --files`/`rg -n`
**Files excerpted:** 20
**Pattern extraction date:** 2026-07-03

