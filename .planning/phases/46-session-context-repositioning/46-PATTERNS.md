# Phase 46: Session Context Repositioning - Pattern Map

**Mapped:** 2026-07-03
**Files analyzed:** 17
**Analogs found:** 17 / 17

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docs/contract-spec.md` | config | transform | `docs/contract-spec.md` memory sections | exact |
| `docs/current-implementation-map.md` | config | transform | `docs/architecture-overview.md` memory sections | role-match |
| `docs/architecture-overview.md` | config | transform | `docs/contract-spec.md` memory-layer contract | role-match |
| `.planning/MEMORY-REDESIGN-DECISIONS.md` | config | transform | `.planning/MEMORY-REDESIGN-DECISIONS.md` defer block | exact |
| `tests/memory/test_phase46_session_context_alignment.py` | test | transform | `tests/memory/test_phase45_contract_alignment.py` | exact |
| `tests/tools/test_catalog.py` | test | request-response | `tests/tools/test_catalog.py` | exact |
| `tests/memory/test_session_precedent_search.py` | test | CRUD | `tests/memory/test_session_precedent_search.py` | exact |
| `tests/agent/test_memory_evidence_boundary.py` | test | request-response | `tests/agent/test_memory_evidence_boundary.py` | exact |
| `tests/memory/test_session_memory_bundle.py` | test | transform | `tests/memory/test_session_memory_bundle.py` | exact |
| `tests/agent/test_session_memory_load.py` | test | request-response | `tests/agent/test_session_memory_load.py` | exact |
| `tests/agent/test_reviewed_memory_context_retrieve.py` | test | request-response | `tests/agent/test_reviewed_memory_context_retrieve.py` | role-match |
| `src/memory/session_bundle.py` | service | transform | `src/memory/session_bundle.py` | exact |
| `src/agent/nodes/session_context_load.py` | controller | request-response | `src/agent/nodes/session_context_load.py` | exact |
| `src/agent/nodes/session_memory_load.py` | controller | request-response | `src/agent/nodes/session_memory_load.py` | exact |
| `src/tools/executors/memory.py` | service | request-response | `src/tools/executors/memory.py` | exact |
| `src/memory/search.py` | service | CRUD | `src/memory/search.py` | exact |
| `src/memory/write_service.py` / `src/agent/nodes/memory_write.py` | service/controller | event-driven | `src/memory/write_service.py`, `src/agent/nodes/memory_write.py` | exact |

## Pattern Assignments

### `tests/memory/test_phase46_session_context_alignment.py` (test, transform)

**Analog:** `tests/memory/test_phase45_contract_alignment.py`

**Imports and helper pattern** (lines 1-32):
```python
from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SPEC_PATH = ROOT / "docs" / "contract-spec.md"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]
```

**Contract section assertions** (lines 82-124):
```python
def test_contract_cwc_lifecycle_records_active_read_run_auto_and_terminal_writeback() -> None:
    section = _section_13_4a()

    for term in (
        "active CWC read",
        "tenant + `refund_cases.id`",
        "`link_source=\"run_auto\"`",
        "linked_by_run_id",
        "terminal finalizer",
        "CaseWorkingContextService.write_case_working_context(...)",
        "best-effort memory side effect",
    ):
        assert term in section
```

**AST/static source check pattern** (lines 148-164):
```python
tree = ast.parse(_source(INVESTIGATE_PATH))
violations: list[str] = []

for node in ast.walk(tree):
    if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
        for key in node.value.keys:
            if _constant_str(key) == "active_slots":
                violations.append("return {'active_slots': ...}")

assert violations == []
```

**Approved verification-entrypoint check** (lines 201-209):
```python
checked_paths = sorted(PHASE45_DIR.glob("45-*-PLAN.md")) + [PHASE45_DIR / "45-VALIDATION.md"]
snippets: list[tuple[Path, str]] = []
for path in checked_paths:
    snippets.extend((path, snippet) for snippet in _pytest_command_snippets(path))

assert snippets
for path, snippet in snippets:
    assert snippet.startswith("UV_CACHE_DIR=/tmp/uv-cache uv run pytest"), (path, snippet)
```

**Apply to Phase 46:** Create the new alignment file with the same `ROOT`, `_source`, `_between`, and targeted string/AST assertions. It should lock:
- `session_memories` table remains tenant/user/thread scoped and has no `case_id`.
- `session_context` / session hints never construct authority DTOs.
- `search_case_memory` stays reviewed-case backed.
- CWC fallback is not derived from raw session/reviewed memory.
- Phase 47 and Phase 48 defers remain named.
- Phase 46 plan/validation commands use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.

### `docs/contract-spec.md` (config, transform)

**Analog:** Existing memory-layer contract in `docs/contract-spec.md`

**Layering pattern** (lines 1423-1437):
```markdown
Memory architecture decision：MOCA memory is contextual assistance, not authority. Policy evidence, approval authorization, action safety snapshots, and replay truth must come from their own authoritative services, not memory.

| Session memory | Same-thread continuity across turns | active slots, last intent, lightweight summary, unresolved questions | PostgreSQL `session_memories` with CAS; optional Redis hot cache with TTL and Postgres fallback |
| Case Working Context | Current case working state across threads and handoffs | customer request, separated claims and verified facts, missing info, refs, actions taken, pending tasks, next action | PostgreSQL `case_working_contexts` scoped by tenant + `refund_cases.id`, versioned by append-only revisions |
```

**Session-memory boundary pattern** (lines 1449-1490):
```markdown
### 13.2 Session memory

同一 tenant + user + thread 内保留短期上下文，用于回答“继续刚才那个退款单”“这个订单呢”等 same-thread continuity。

Session slot inheritance rules are deterministic:

1. Current-turn explicit validated slots win.
2. Existing session slots may be inherited only when tenant/user/thread match, the slot is not expired, it is compatible with the current intent, and the current turn did not provide a conflicting explicit slot.
3. Inherited slots can help pass the slot gate, but they cannot satisfy policy evidence, risk, approval, or action safety requirements.

The `summary` column has session-summary semantics only.
```

**CWC separation pattern** (lines 1517-1529):
```markdown
### 13.4a Case Working Context

Case Working Context is a durable working-state memory layer for one active refund case.

Case Working Context is NOT an `EvidenceRefV1`. It cannot authorize policy/risk/approval/action, cannot satisfy policy or approval evidence requirements, and cannot replace current business facts, authoritative policy evidence, approval policy, action safety snapshots, audit logs, or replay truth.

The read is keyed by tenant + `refund_cases.id` only; `case_memories`, session memory, reviewed `case_memory`, or ambiguous text must not backfill or guess the CWC case.
```

**Storage/CAS pattern** (lines 2565-2566):
```markdown
- `session_memories`: unique `(tenant_id, user_id, thread_id)` where `deleted_at is null`; add `version int not null default 1` and update with lock/CAS on `(id, version)` so concurrent runs cannot silently lose `active_slots_json`, `session_summary`, `unresolved_questions_json`, `last_intent`, or `last_business_context_refs_json`.
```

**Apply to Phase 46:** Update Section 13.2 to explicitly say after CWC, session memory remains same-thread temporary context only. Keep CWC/reviewed-case/long-term authority language in separate sections. Do not imply a migration.

### `docs/current-implementation-map.md` and `docs/architecture-overview.md` (config, transform)

**Analogs:** Current stale-wording sections in both docs.

**Current stale wording to reconcile** (`docs/current-implementation-map.md` lines 37-38, 154-158):
```markdown
| Session precedent search | `src/memory/search.py:15` | 基于 `session_memories` 做 transitional search projection | short-term memory projection | 不是严格 case memory；命名上容易和业务 case precedent 混淆 |
| Case memory tool | `src/tools/executors/memory.py:32` | `search_case_memory` 包装 session precedent search，返回 `ToolResultV2` | tool / short-term projection | 当前只是 session memory 搜索，不是真正长期 case memory |

5. **`search_case_memory` 命名容易误导**：当前实现基于 session memories，不是真正 case memory。
```

**Same issue in architecture overview** (`docs/architecture-overview.md` lines 483-496):
```markdown
- Session memory：同一 tenant/user/thread 的连续对话，包含 active slots、last intent、轻量 summary、unresolved questions；Postgres `session_memories` + CAS 是事实源，Redis 可选做带 TTL 的 hot cache。
- Case memory：历史类似 case、处理结果、审批结果、outcome；只能作为 precedent；Phase 16。当前 `search_case_memory` 仅使用 session-derived precedent 过渡实现，不等于 reviewed case memory。

- Memory 是辅助上下文，不是政策依据。
- Session memory 只负责同 thread 连续性，不等于 workflow checkpoint；workflow checkpoint 只负责 run 恢复，不等于下一轮对话记忆。
- Case memory 只能作为 precedent，不能覆盖当前 policy evidence。
```

**Apply to Phase 46:** Preserve the useful layer-boundary bullets, but update/annotate outdated production-implementation statements. Current code uses `MemoryToolExecutor -> CaseMemoryService` for `search_case_memory`; keep `src/memory/search.py` described as legacy/debug-only.

### `.planning/MEMORY-REDESIGN-DECISIONS.md` (config, transform)

**Analog:** Existing defer ledger.

**Named defer pattern** (lines 93-105):
```markdown
- **DEFER-1 → Phase 46:① Session Context 重新定位。** 现 session_memories 是 thread-scoped,② 落地后要厘清 ① 与 ② 的职责边界(① 只管单通对话临时上下文,不再承担跨 case 状态),避免二者内容重叠。本次 phase 不动 ①。
- **DEFER-2 → Phase 47:③ Case Precedent 改定位 + case 关闭自动生成候选。**
- **DEFER-3 → Phase 48:long_term 窄版落地。**

> 三个 DEFER 项在进入本次 phase 的 PLAN.md 时,须在 plan 的 "out of scope / follow-up" 段落原样带上,确保 plan-checker 和 Codex 评审都能看到边界。
```

**Apply to Phase 46:** If planning docs are touched, carry Phase 47 and Phase 48 forward by exact phase number. Do not mark them implemented.

### `tests/tools/test_catalog.py` (test, request-response)

**Analog:** Same file.

**Descriptor helper and output-schema pattern** (lines 73-74, 226-239):
```python
def _descriptor(name: str) -> ToolDescriptor:
    return next(descriptor for descriptor in ToolCatalog().descriptors() if descriptor.name == name)

memory_item_schema = scoped_schemas["search_case_memory"]["properties"]["items"]["items"]
assert scoped_schemas["search_case_memory"]["required"] == ["items"]
assert memory_item_schema["additionalProperties"] is False
assert set(memory_item_schema["properties"]) == {
    "case_memory_id",
    "excerpt",
    "applicability",
    "outcome",
    "caveats",
    "score",
    "policy_refs",
    "source_refs",
}
```

**Reviewed store wording assertion** (lines 338-344):
```python
def test_search_case_memory_descriptor_names_reviewed_case_memory_store() -> None:
    descriptor = _descriptor("search_case_memory")

    assert "reviewed case memory" in descriptor.description
    assert "reviewed case store" in descriptor.description
    assert "session-derived" not in descriptor.description.lower()
```

**Apply to Phase 46:** Extend this file only for catalog descriptor wording/schema checks. Do not test executor wiring here unless keeping it as a pure static descriptor assertion.

### `src/tools/catalog.py` (config, request-response)

**Analog:** Same file.

**Descriptor pattern** (lines 438-455):
```python
_ToolDeclaration(
    name="search_case_memory",
    description=(
        "Retrieve reviewed case memory precedents from the reviewed case store. "
        "Returned snippets are contextual only, not policy evidence or action authority."
    ),
    kind="retrieval",
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}},
        "required": ["query"],
    },
    output_schema=_SEARCH_CASE_MEMORY_OUTPUT_SCHEMA,
    side_effect="retrieval",
    caller_allowlist=("investigate",),
    event_family="rag_retrieval_*",
    resource_type=None,
    executor="memory",
)
```

**Apply to Phase 46:** Keep reviewed-memory wording and contextual-only warning. Any wording change must keep `executor="memory"`, `kind="retrieval"`, and planner-visible read-only semantics.

### `src/tools/executors/memory.py` (service, request-response)

**Analog:** Same file.

**Imports and service wiring** (lines 6-11, 14-27):
```python
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.schemas import CaseMemorySearchRequest, CaseMemorySearchResult
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager_results import result


class MemoryToolExecutor:
    executor_name = "memory"

    def __init__(self, session: AsyncSession | None = None, service: Any | None = None) -> None:
        if service is not None:
            self.service = service
        elif session is not None:
            self.service = CaseMemoryService(CaseMemoryRepository(session))
        else:
            self.service = None
```

**Reviewed-case execution pattern** (lines 32-59):
```python
async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
    if name != "search_case_memory":
        return result("unavailable", "Tool is declared but unavailable", code="TOOL_UNAVAILABLE")
    if self.service is None or not hasattr(self.service, "retrieve_reviewed"):
        return result("unavailable", "Reviewed case memory search is unavailable", code="TOOL_UNAVAILABLE")
    request = _case_memory_request(query=str(args["query"]), context=ctx)
    if request is None:
        return result("invalid_request", "Reviewed case memory search context is invalid", code="INVALID_CONTEXT")
    search_result = await self.service.retrieve_reviewed(request)
    return _case_memory_result(search_result)
```

**Result pattern** (lines 97-119):
```python
if search_result.status == "success":
    return ToolResultV2(
        status="success",
        data={"items": [item.model_dump(mode="json") for item in search_result.items]},
        summary=f"Found {len(search_result.items)} reviewed case memory precedent item(s)",
        source_system="case_memory_service",
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=0,
        audit_ref=None,
    )
```

**Apply to Phase 46:** If code narrowing touches this file, preserve `CaseMemoryService.retrieve_reviewed` and do not import `LegacySessionPrecedentSearchService` or `SessionMemoryRepository`.

### `src/memory/search.py` and `tests/memory/test_session_precedent_search.py` (service/test, CRUD)

**Analog:** Existing legacy/debug-only implementation and test.

**Legacy guard docstring** (`src/memory/search.py` lines 15-21):
```python
class LegacySessionPrecedentSearchService:
    """Search legacy precedents derived from same-user session memory.

    This is not the reviewed case-memory store. It is a debug-only read-only
    projection over ``session_memories`` and must not back the planner-facing
    ``search_case_memory`` capability.
    """
```

**Legacy test pattern** (`tests/memory/test_session_precedent_search.py` lines 43-84):
```python
@pytest.mark.asyncio
async def test_legacy_session_precedent_search_reads_session_memory_storage(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    repository = SessionMemoryRepository(session)
    await repository.insert_active(...)

    result = await LegacySessionPrecedentSearchService(repository).search(...)

    assert result.status == "success"
    assert "legacy session-derived precedent" in result.summary
```

**Apply to Phase 46:** Keep this service quarantined as legacy/debug. Add static assertions elsewhere that production executor does not use it; do not delete it in Phase 46 unless a later plan explicitly scopes that cleanup.

### `tests/agent/test_memory_evidence_boundary.py` (test, request-response)

**Analog:** Same file.

**Static authority-import check** (lines 129-136):
```python
def test_session_memory_modules_do_not_import_evidence_ref_v1() -> None:
    memory_sources = "\n".join(path.read_text() for path in Path("src/memory").glob("*.py"))
    memory_write_source = Path("src/agent/nodes/memory_write.py").read_text()

    assert "from src.knowledge.schemas import EvidenceRefV1" not in memory_sources
    assert "EvidenceRefV1" not in memory_sources
    assert "from src.knowledge.schemas import EvidenceRefV1" not in memory_write_source
    assert "EvidenceRefV1(" not in memory_write_source
```

**Strict DTO rejection pattern** (lines 464-509):
```python
def test_contextual_only_memory_refs_reject_strict_authority_dto_parsing() -> None:
    from src.agent.rag_context.claims import MaterialClaim
    from src.approvals.schemas import ApprovalRequestCreateCommand
    from src.replay.schemas import ReplayEventV3
    from src.tools.contracts import BusinessFactRefV1

    surfaces = _planned_contextual_only_memory_surfaces(tenant_id)

    with pytest.raises(ValidationError):
        BusinessFactRefV1.model_validate(surfaces["ReviewedMemoryRef"])
    with pytest.raises(ValidationError):
        ReplayEventV3.model_validate(surfaces["ReviewedMemoryContextRetrieveStatusV1"])
```

**Verifier outcome pattern** (lines 578-656):
```python
policy_result = await verifier.verify_claim(policy_claim, context_bundle=context_bundle)
business_result = await verifier.verify_claim(business_claim, context_bundle=context_bundle)
action_result = await verifier.verify_claim(action_claim, context_bundle=context_bundle, dependency_results=[...])

assert policy_result.outcome == VerificationOutcome.INSUFFICIENT
assert "memory_not_policy_authority" in policy_result.reason_codes
assert business_result.outcome == VerificationOutcome.BUSINESS_FACT_MISSING
assert "memory_not_business_authority" in business_result.reason_codes
assert action_result.allows_action_recommendation is False
assert action_result.blocks_proposed_action is True
assert action_result.safe_support_refs == []
```

**Apply to Phase 46:** Add assertions for `policy_topic_hints`, `prior_policy_mention_refs`, `last_business_context_refs`, and tool-summary refs as contextual hints only. Reuse strict DTO parsing and verifier-reason-code assertions.

### `src/memory/session_bundle.py` and `tests/memory/test_session_memory_bundle.py` (service/test, transform)

**Analog:** Same service and tests.

**Bundle service composition pattern** (`src/memory/session_bundle.py` lines 27-77):
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
    fallback_reasons: dict[str, str] = {}
    prompt_context = await self.conversation_service.load_prompt_context(...)
    slot_continuity = await self.memory_service.load_session_memory(...)
    tool_summaries = _tool_summary_views(prompt_context)
    return SessionMemoryBundle(
        rolling_summary=_rolling_summary_view(prompt_context),
        recent_messages=_recent_message_views(prompt_context),
        tool_summaries=tool_summaries,
        slot_continuity=slot_continuity,
        policy_topic_hints=_policy_topic_hints(tool_summaries),
        prior_policy_mention_refs=_prior_policy_mention_refs(tool_summaries),
        fallback_reasons=fallback_reasons,
    )
```

**Hint projection pattern** (`src/memory/session_bundle.py` lines 151-202):
```python
def _policy_topic_hints(tool_summaries: list[SessionToolSummaryView]) -> list[str]:
    hints: list[str] = []
    for summary in tool_summaries:
        for ref in summary.policy_evidence_refs:
            hint = _policy_topic_hint(ref)
            if hint and hint not in hints:
                hints.append(hint)
            if len(hints) >= _POLICY_HINT_LIMIT:
                return hints
    return hints


def _prior_policy_mention_refs(tool_summaries: list[SessionToolSummaryView]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    ...
```

**Prompt-safe behavioral test** (`tests/memory/test_session_memory_bundle.py` lines 188-194):
```python
serialized = json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False)
assert "rolling_summary" in serialized
assert "recent_messages" in serialized
assert "tool_summaries" in serialized
assert "slot_continuity" in serialized
for forbidden in ("raw_payload", "private_reasoning", "approval_authority_body", "debug_trace", "secret"):
    assert forbidden not in serialized
```

**Policy-hint sanitization test** (`tests/memory/test_session_memory_bundle.py` lines 251-262):
```python
assert bundle.policy_topic_hints == ["refund_policy@v1"]
assert bundle.prior_policy_mention_refs == [
    {"doc_key": "refund_policy", "chunk_id": "chunk-1", "policy_version": "v1", "tool_result_id": "tool-result-1"}
]
serialized_refs = json.dumps(bundle.prior_policy_mention_refs, ensure_ascii=False)
for forbidden in ("schema_version", "evidence_id", "tenant_id", "text_hash", "retrieved_at"):
    assert forbidden not in serialized_refs
```

**Apply to Phase 46:** Treat refs/hints as prompt-safe pointers only. If code is narrowed, keep `_POLICY_HINT_REF_KEYS`, limit/dedupe behavior, and raw/authority marker sanitization.

### `src/agent/nodes/session_context_load.py`, `src/agent/nodes/session_memory_load.py`, and `tests/agent/test_session_memory_load.py` (controller/test, request-response)

**Analog:** Target node and compatibility wrapper.

**Target node dependency pattern** (`src/agent/nodes/session_context_load.py` lines 31-44):
```python
async def session_context_load(
    state: AgentState,
    config: RunnableConfig,
    *,
    node_name: str = "session_context_load",
    settings_obj: Any | None = None,
    memory_service_cls: Any | None = None,
    session_memory_repository_cls: Any | None = None,
    session_memory_bundle_service_cls: Any | None = None,
    conversation_repository_cls: Any | None = None,
    conversation_service_cls: Any | None = None,
    memory_context_service_cls: Any | None = None,
) -> dict:
    """Load same-thread session context through the MemoryContextService facade."""
```

**Current-turn override and merchant filter pattern** (`src/agent/nodes/session_context_load.py` lines 166-209):
```python
explicit_slots = _current_turn_slots(state)
explicit_merchant_id = explicit_slots.get("merchant_id")
trusted_merchant_ids = _trusted_merchant_ids(trusted_context)
effective_merchant_id = explicit_merchant_id or (trusted_merchant_ids[0] if len(trusted_merchant_ids) == 1 else None)
inherited_slots = dict(context.slot_continuity.active_slots)
inherited_merchant_id = inherited_slots.get("merchant_id")

if cross_merchant or denied_by_trusted_scope:
    replacement_slots = explicit_slots or ({"merchant_id": str(effective_merchant_id)} if effective_merchant_id else {})
    return _filtered_context(context, replacement_slots=replacement_slots, filter_reasons=filter_reasons), filter_reasons

if explicit_slots:
    merged_slots = {**inherited_slots, **explicit_slots}
    return _context_with_slots(context, active_slots=merged_slots, explicit_slots=explicit_slots), filter_reasons
```

**Target plus legacy output pattern** (`src/agent/nodes/session_context_load.py` lines 302-328):
```python
session_memory = context.slot_continuity.model_dump(mode="json")
session_context = {
    "schema_version": _TARGET_CONTEXT_SCHEMA,
    "authority_class": _TARGET_CONTEXT_AUTHORITY,
    **session_memory,
}
result = {
    "session_context": session_context,
    "session_context_bundle": SessionContextBundle(session_context=context).model_dump(mode="json"),
    "session_context_load_status": status,
    "session_memory": session_memory,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, node_name, session_memory, status)],
}
if include_legacy_bundle:
    result["session_memory_bundle"] = _legacy_session_memory_bundle_dump(context)
```

**Compatibility wrapper** (`src/agent/nodes/session_memory_load.py` lines 16-29):
```python
async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the target session_context_load node."""
    return await session_context_load(
        state,
        config,
        node_name="session_memory_load",
        settings_obj=settings,
        memory_service_cls=MemoryService,
        session_memory_repository_cls=SessionMemoryRepository,
        session_memory_bundle_service_cls=SessionMemoryBundleService,
        conversation_repository_cls=ConversationRepository,
        conversation_service_cls=ConversationService,
        memory_context_service_cls=MemoryContextService,
    )
```

**Node test pattern** (`tests/agent/test_session_memory_load.py` lines 117-171):
```python
result = await session_context_load(
    {**_state(), "current_run_id": run_id},
    {"configurable": {"session": FakeSession()}},
)

assert result["session_context"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
assert result["session_context_bundle"]["schema_version"] == "session_context_bundle.v1"
assert result["session_context_load_status"]["schema_version"] == "session_context_load_status.v1"
assert result["session_context_load_status"]["authority_class"] == "contextual_only"
assert result["session_memory"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
assert result["session_memory_bundle"]["schema_version"] == "session_memory_bundle.v1"
```

**Apply to Phase 46:** Preserve compatibility fields while adding boundary tests. Do not make `session_memory_load` a separate implementation.

### `tests/agent/test_reviewed_memory_context_retrieve.py` (test, request-response)

**Analog:** Same file.

**Session memory is not reviewed-memory scope authority** (lines 169-188):
```python
async def test_reviewed_memory_context_retrieve_does_not_use_session_memory_to_create_scope() -> None:
    trusted_context = _trusted_context(merchant_ids=["merchant-b"])

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            session_memory={"active_slots": {"merchant_id": "merchant-b"}},
        ),
        {"configurable": {"session": object(), "trusted_context": trusted_context}},
    )

    memory_context = _assert_empty_context_bundle(result, fallback_reason="memory_scope_not_authority")
    assert "memory_scope_not_authority" in memory_context["status_ref"]["filter_reasons"]
```

**Apply to Phase 46:** Reuse this style for CWC fallback and reviewed-memory boundaries: create trusted context, inject tempting session-memory state, assert fail-closed and no derived scope/authority.

### `src/memory/repository.py`, `src/memory/service.py`, `src/memory/write_service.py`, and `src/agent/nodes/memory_write.py` (service/controller, event-driven)

**Analog:** Existing session-memory storage and write path.

**Tenant/user/thread repository scope** (`src/memory/repository.py` lines 28-48):
```python
filters = [
    SessionMemory.tenant_id == tenant_id,
    SessionMemory.user_id == user_id,
    SessionMemory.thread_id == thread_id,
    SessionMemory.deleted_at.is_(None),
]
if not include_expired:
    filters.append(or_(SessionMemory.expires_at.is_(None), SessionMemory.expires_at > func.now()))

result = await self.session.execute(select(SessionMemory).where(and_(*filters)).execution_options(populate_existing=True))
return result.scalar_one_or_none()
```

**Session load filtering and metadata** (`src/memory/service.py` lines 59-121):
```python
memory = await self.repository.get_active(tenant_id, user_id, thread_id, include_expired=True)
if memory is None:
    return _fallback_view("missing_session")
if _is_expired(memory.expires_at, now):
    return _fallback_view("expired")

envelope = SessionSlotsEnvelopeV1.model_validate(memory.active_slots_json)
for slot_name, slot in envelope.slots.items():
    if _is_expired(slot.expires_at, now):
        continue
    if not _slot_intent_compatible(slot_name, slot.compatible_intents, current_intent):
        continue
    active_slots[slot_name] = slot.value
    slot_metadata[slot_name] = {"source": "trusted_session_memory", ...}
```

**Default session-only candidate proposal** (`src/memory/write_service.py` lines 56-67):
```python
def propose_candidates(
    self,
    state: Mapping[str, Any],
    *,
    requested_types: Sequence[str] | None = None,
) -> list[MemoryWriteCandidate]:
    requested = {str(item) for item in requested_types} if requested_types is not None else {"session"}
    candidates: list[MemoryWriteCandidate] = []
    if "session" in requested:
        candidates.append(_build_session_candidate(state))
    candidates.extend(_explicit_candidates(state.get("memory_write_candidates"), requested_types=requested_types))
    return candidates
```

**Write node side-effect pattern** (`src/agent/nodes/memory_write.py` lines 92-132):
```python
write_service = MemoryWriteService(
    MemoryService(SessionMemoryRepository(session), enabled=settings.session_memory_enabled),
    long_term_memory_service=LongTermMemoryService(LongTermMemoryRepository(session)),
    case_memory_service=CaseMemoryService(CaseMemoryRepository(session)),
)
candidates = write_service.propose_candidates(state)
candidate = _session_candidate(candidates)
if candidate.decision == "skip":
    results = await write_service.apply_policy_and_write_all(candidates)
    result = _session_result(candidates, results)
    return _completed(state, started_at, result, candidate, candidates=candidates, results=results)
```

**Write-service tests** (`tests/memory/test_memory_write_service.py` lines 90-127, 175-226):
```python
candidate = service.propose_candidates(_state())[0]
assert set(candidate.explicit_slots) == {"order_id"}
assert candidate.expected_version == 7
assert candidate.decision == "write"

result = await service.apply_policy_and_write(candidates)
assert result.status == "skipped"
assert result.reason_code == "pii_blocked"
assert session_service.candidates == []

assert isinstance(candidates[0], SessionMemoryWriteCandidate)
assert isinstance(candidates[1], LongTermMemoryWriteCandidate)
assert isinstance(candidates[2], CaseMemoryWriteCandidate)
```

**Apply to Phase 46:** Default memory writes remain session-only. Long-term and case candidates must require explicit `state.memory_write_candidates`. If Phase 46 adds tests for no automatic durable preference sedimentation, use `propose_candidates(_state())` and assert only a `SessionMemoryWriteCandidate` is present.

## Shared Patterns

### Session Storage Identity

**Source:** `src/db/models.py` lines 396-428 and `src/db/migrations/versions/007_session_memories.py` lines 23-75.

```python
class SessionMemory(TimestampMixin, Base):
    __tablename__ = "session_memories"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ...

Index(
    "uq_session_memories_active_scope",
    SessionMemory.tenant_id,
    SessionMemory.user_id,
    SessionMemory.thread_id,
    unique=True,
    postgresql_where=SessionMemory.deleted_at.is_(None),
)
```

Apply to static tests: assert no `case_id` inside the `SessionMemory` block and no new destructive migration touching `session_memories`.

### Contextual-Only DTO Shape

**Source:** `src/memory/schemas.py` lines 147-181.

```python
class SessionContextMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_context_memory.v1"] = "session_context_memory.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    tenant_id: str
    user_id: str
    thread_id: str
    run_id: str
    rolling_summary: SessionRollingSummaryView | None = None
    recent_messages: list[SessionRecentMessageView] = Field(default_factory=list)
    tool_summaries: list[SessionToolSummaryView] = Field(default_factory=list)
    slot_continuity: SlotContinuityMemoryView
    policy_topic_hints: list[str] = Field(default_factory=list)
    prior_policy_mention_refs: list[dict[str, Any]] = Field(default_factory=list)
    fallback_reasons: dict[str, str] = Field(default_factory=dict)


class SessionContextBundle(BaseModel):
    schema_version: Literal["session_context_bundle.v1"] = "session_context_bundle.v1"
    authority_class: Literal["contextual_only"] = "contextual_only"
    session_context: SessionContextMemory
```

Apply to code/tests: preserve `authority_class = contextual_only`; do not add authority DTO fields to session context.

### Prompt Hints Are Not Evidence

**Source:** `tests/memory/test_session_memory_bundle.py` lines 251-262 and `tests/agent/test_memory_evidence_boundary.py` lines 578-656.

Pattern: allow narrowed `doc_key` / `chunk_id` / `policy_version` hint projection, then verify memory refs cannot become policy evidence, business facts, approval/action authority, or replay truth.

### Production Reviewed Case Memory Search

**Source:** `src/tools/executors/memory.py` lines 8-25 and `src/tools/catalog.py` lines 438-455.

Pattern: planner-facing `search_case_memory` uses `CaseMemoryService(CaseMemoryRepository(session))` and a descriptor that says reviewed case store. Legacy session precedent is a separate debug/read-only projection.

### CWC Fallback Is Forbidden

**Source:** `docs/contract-spec.md` lines 1527-1529 and `tests/agent/test_reviewed_memory_context_retrieve.py` lines 169-188.

Pattern: raw `session_memory`, raw `session_context`, reviewed memory, and ambiguous text cannot backfill CWC identity or reviewed-memory scope. Tests should inject tempting memory state and assert fail-closed status/reasons.

### Approved Test Entrypoint

**Source:** `AGENTS.md`; static pattern from `tests/memory/test_phase45_contract_alignment.py` lines 201-209.

Use only:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py -x -q
```

Example full phase gate:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py tests/memory/test_session_memory_schema.py tests/memory/test_session_memory_service.py tests/memory/test_session_memory_repository.py tests/memory/test_session_memory_bundle.py tests/memory/test_memory_context_bundle.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/memory/test_phase45_contract_alignment.py -q
```

## No Analog Found

None. All inferred Phase 46 files have close analogs in the existing memory, tool, docs, and static-test surfaces.

## Metadata

**Analog search scope:** `docs/`, `tests/`, `src/`, `.planning/MEMORY-REDESIGN-DECISIONS.md`
**Files scanned:** 459 files under `docs`, `tests`, and `src`, plus phase planning artifacts and memory-redesign decisions.
**Pattern extraction date:** 2026-07-03
