# Phase 39: contract-spec §12.5/§12.6 Reconciliation - Pattern Map

**Mapped:** 2026-07-02  
**Files analyzed:** 1 new/modified target file  
**Analogs found:** 1 / 1 target file, with 6 supporting code/test analogs

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `docs/contract-spec.md` | normative contract spec | transform (implemented contract fields -> spec text) | `docs/contract-spec.md` §8.0 + current §12.5/§12.6, backed by `src/tools/contracts.py`, `src/tools/catalog.py`, `src/tools/policy.py` | exact |

Excluded from implementation target list: `src/tools/contracts.py`, `src/tools/catalog.py`, `src/tools/policy.py`, `tests/architecture/test_trusted_context_boundaries.py`, `tests/tools/test_catalog.py`, and `tests/tools/test_tool_platform.py` are evidence/validation analogs only. No production-code reason was found; Phase 39 should remain docs-only unless a later planner check finds a new mismatch not present in current research.

## Pattern Assignments

### `docs/contract-spec.md` (normative contract spec, transform)

**Analog:** same document structure in `docs/contract-spec.md` §8.0 / §12.5 / §12.6, plus implemented model sources.

**Doc section pattern** (`docs/contract-spec.md` lines 1219-1224):
```markdown
### 12.5 Tool contract

Tool contract 必须区分 system-injected context、tool request、tool result 和 audit obligations。LLM 或用户输入不得生成或覆盖 tenant/user/permission/run/trace context。`ToolCallContext` 的 identity/scope/permission 字段（`tenant_id`、`user_id`、`role`、`permissions`、`merchant_scope`、`session_id`、`thread_id`、`run_id`、`trace_id`）是 §8.0 canonical `TrustedContext` 的投影，不在此处重新定义语义；其余字段是 tool-call-local（由调用方注入）。

class ToolCallContext(BaseModel):
```

**§8.0 identity guard to preserve** (`docs/contract-spec.md` lines 37-39):
```markdown
### 8.0 Canonical TrustedContext (normative)

> Producer phase + schema_version annotation: Phase 7 shared foundation contract; schema_version literal is `trusted_context.v1`. This is the single canonical trusted-identity/scope contract. `KnowledgeContext` (§8.3), `ToolCallContext` (§12.5), and `AgentState` identity fields (§10) are projections of it and MUST NOT redefine, widen, or rename these fields. Per F4/F5, the producer owns the schema; consumers project and never redefine a divergent variant.
```

**Projection table pattern** (`docs/contract-spec.md` lines 149-154):
```markdown
Projection 规则（消费者只取子集，字段语义与本表一致，不得重命名或放宽 trusted-source）：

| Projection | Section | Subset fields | Notes |
| --- | --- | --- | --- |
| `KnowledgeContext` | §8.3 | `tenant_id`, `user_id`, `role`, `merchant_scope`, `run_id`, `trace_id`, `locale`, `effective_at` | `effective_at` 不是 TrustedContext 字段，而是 run-derived 检索时间（默认 run start，见 §8.3）；其余字段是 TrustedContext 投影。`merchant_scope` 必填，使 KnowledgeService 能校验 request 的 `merchant_id` filter 是否在授权范围内 |
| `ToolCallContext` | §12.5 | `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, `trace_id` + tool-call-local fields | tool-call-local fields（`request_id`/`tool_call_id`/`caller_node`/`deadline_at`/`attempt`/`idempotency_key`/`policy_snapshot_ref`）由调用方注入，不属于 TrustedContext |
```

Use this pattern if updating the §8.0 projection note: only add `effective_at`, `approval_ref`, and `safety_snapshot_ref` to tool-call-local fields; do not alter the nine projected identity/scope fields.

**§12.5 field source** (`src/tools/contracts.py` lines 13-36):
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

Copy into §12.5 by adding only the missing local fields near the existing local execution fields:
```python
    deadline_at: datetime | None = None
    effective_at: str | None = None
    attempt: int = 1
    max_attempts: int = 1
    idempotency_key: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None
    policy_snapshot_ref: str | None = None
```

**Current stale §12.5 snippet to patch** (`docs/contract-spec.md` lines 1235-1242):
```python
    request_id: str
    tool_call_id: str
    caller_node: str
    deadline_at: datetime | None = None
    attempt: int = 1
    max_attempts: int = 1  # per-tool maximum attempts, injected by caller
    idempotency_key: str | None = None
    policy_snapshot_ref: str | None = None
```

**§12.6 descriptor source** (`src/tools/catalog.py` lines 14-32):
```python
class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: Literal["read", "retrieval", "write"]
    side_effect: Literal["none", "read_only", "retrieval", "write"]
    required_permission: str
    caller_allowlist: list[str]
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False
```

**Current stale §12.6 snippet to patch** (`docs/contract-spec.md` lines 1317-1328):
```python
class ToolDescriptor(BaseModel):
    name: str
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]  # schema for ToolResultV2.data; envelope is always ToolResultV2
    risk_level: Literal["read", "retrieval", "write"]
    side_effect: Literal["none", "read_only", "retrieval", "write"]
    required_permission: str  # namespaced token, for example "tool:get_order"
    caller_allowlist: list[str]
    event_family: Literal["tool_call_*", "rag_retrieval_*"]
    resource_type: str | None
```

Patch by preserving the existing code-block style and adding implemented fields:
```python
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False
```

**Action descriptor metadata source** (`src/tools/catalog.py` lines 325-364):
```python
_ToolDeclaration(
    name="create_coupon_grant_draft",
    kind="write",
    input_schema={
        "type": "object",
        "properties": {
            "approval_request_id": {"type": "string", "minLength": 1},
            "action_type": {"type": "string", "minLength": 1},
            "payload": {"type": "object"},
            "action_payload_hash": {"type": "string", "minLength": 1},
            "safety_snapshot_ref": {"type": "string", "minLength": 1},
            "safety_snapshot_hash": {"type": "string", "minLength": 1},
            "target_merchant_id": {"type": "string", "minLength": 1},
            "target_merchant_ref": {"type": "object"},
            "business_fact_refs": {"type": "array", "items": {"type": "object"}},
            "verified_evidence_refs": {"type": "array", "items": {"type": "object"}},
            "claim_verification_ref": {"type": "string", "minLength": 1},
            "claim_verification_summary": {"type": "object"},
            "risk_decision_ref": {"type": "string", "minLength": 1},
            "risk_decision": {"type": "object"},
            "auto_allowed_binding": {"type": "object"},
        },
        "required": [
            "action_type",
            "payload",
            "action_payload_hash",
            "safety_snapshot_ref",
            "safety_snapshot_hash",
        ],
    },
    output_schema=_GENERIC_OBJECT_SCHEMA,
    side_effect="write",
    caller_allowlist=("action_draft",),
    event_family="action",
    resource_type=None,
    executor="action",
    exposure="node_only",
    requires_safety_snapshot=True,
    requires_idempotency_key=True,
)
```

**Descriptor construction source** (`src/tools/catalog.py` lines 369-387):
```python
def _descriptor(declaration: _ToolDeclaration) -> ToolDescriptor:
    return ToolDescriptor(
        name=declaration.name,
        description=declaration.description,
        kind=declaration.kind,
        input_schema=declaration.input_schema,
        output_schema=declaration.output_schema,
        risk_level=declaration.kind,
        side_effect=declaration.side_effect,
        required_permission=f"tool:{declaration.name}",
        caller_allowlist=list(declaration.caller_allowlist),
        event_family=declaration.event_family,
        resource_type=declaration.resource_type,
        executor=declaration.executor,
        exposure=declaration.exposure,
        requires_approval=declaration.requires_approval,
        requires_safety_snapshot=declaration.requires_safety_snapshot,
        requires_idempotency_key=declaration.requires_idempotency_key,
    )
```

**§12.6 policy decision source** (`src/tools/contracts.py` lines 161-185):
```python
class ToolPolicyDecision(BaseModel):
    """Domain-level tool policy decision object.

    This is NOT a replay event envelope; it must not contain event_id,
    sequence, occurred_at, run_id, or tenant_id.  It is persisted through
    DecisionEventEnvelopeV1 / emit_decision_event as a redacted_payload
    sub-object.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["tool_policy_decision.v1"] = "tool_policy_decision.v1"
    tool_name: str
    caller: str
    decision_stage: Literal["visibility", "runtime_auth"]
    decision: Literal["visible", "hidden", "allowed", "denied"]
    reason_codes: list[str]
    required_scopes: list[str]
    matched_scope: str | None = None
    policy_version: str
    data_classification: Literal["public", "internal", "sensitive", "restricted"]
    resource_scope_binding: dict[str, Any] | None = None
    runtime_available: bool | None = None
    availability_summary: str | None = None
```

Patch the §12.6 `ToolPolicyDecision` code block by adding:
```python
    runtime_available: bool | None = None
    availability_summary: str | None = None
```

**Availability population pattern** (`src/tools/policy.py` lines 310-327):
```python
availability_summary = None
if not runtime_available:
    availability_summary = f"Tool {descriptor.name!r} is currently unavailable"

return ToolPolicyDecision(
    tool_name=descriptor.name,
    caller=caller,
    decision_stage="visibility",
    decision="visible" if visible else "hidden",
    reason_codes=reason_codes,
    required_scopes=[descriptor.required_permission],
    matched_scope=None,
    policy_version=self._policy_version,
    data_classification="internal",
    resource_scope_binding=None,
    runtime_available=runtime_available,
    availability_summary=availability_summary,
)
```

**Runtime auth denied/allowed availability pattern** (`src/tools/policy.py` lines 397-438):
```python
is_available = available.get(tool_name, True)
if not is_available:
    return self._denied_decision(
        tool_name=tool_name,
        caller=ctx.caller_node,
        reason_codes=["tool_unavailable"],
        required_scopes=[descriptor.required_permission],
        runtime_available=False,
        availability_summary=f"Tool {tool_name!r} is currently unavailable",
    )

resource_scope_binding = self._build_resource_binding(args, ctx)
reason_codes = [
    gate.reason_code
    for gate in self._runtime_auth_gates
    if gate.denies(descriptor, args, ctx, resource_scope_binding)
]

if reason_codes:
    return self._denied_decision(
        tool_name=tool_name,
        caller=ctx.caller_node,
        reason_codes=reason_codes,
        required_scopes=[descriptor.required_permission],
        resource_scope_binding=resource_scope_binding,
        runtime_available=True,
    )

return ToolPolicyDecision(
    tool_name=tool_name,
    caller=ctx.caller_node,
    decision_stage="runtime_auth",
    decision="allowed",
    reason_codes=["visible"],
    required_scopes=[descriptor.required_permission],
    matched_scope=descriptor.required_permission,
    policy_version=self._policy_version,
    data_classification="internal",
    resource_scope_binding=resource_scope_binding,
    runtime_available=True,
    availability_summary=None,
)
```

**Action-safety runtime gate source** (`src/tools/policy.py` lines 144-171 and 236-244):
```python
def _denies_approval(
    descriptor: ToolDescriptor,
    args: dict[str, Any],
    ctx: ToolCallContext,
    resource_scope_binding: dict[str, Any],
) -> bool:
    del args, resource_scope_binding
    return descriptor.requires_approval and not ctx.approval_ref


def _denies_safety_snapshot(
    descriptor: ToolDescriptor,
    args: dict[str, Any],
    ctx: ToolCallContext,
    resource_scope_binding: dict[str, Any],
) -> bool:
    del args, resource_scope_binding
    return descriptor.requires_safety_snapshot and not ctx.safety_snapshot_ref


def _denies_idempotency(
    descriptor: ToolDescriptor,
    args: dict[str, Any],
    ctx: ToolCallContext,
    resource_scope_binding: dict[str, Any],
) -> bool:
    del args, resource_scope_binding
    return descriptor.requires_idempotency_key and not ctx.idempotency_key
```

```python
_runtime_auth_gates: tuple[RuntimeAuthGate, ...] = (
    RuntimeAuthGate("caller_allowlist", "caller_not_allowed", _denies_caller_allowlist),
    RuntimeAuthGate("permission", "missing_permission", _denies_permission),
    RuntimeAuthGate("side_effect", "side_effect_blocked", _denies_side_effect),
    RuntimeAuthGate("resource_scope", "scope_denied", _denies_resource_scope),
    RuntimeAuthGate("approval", "approval_required", _denies_approval),
    RuntimeAuthGate("safety_snapshot", "safety_snapshot_required", _denies_safety_snapshot),
    RuntimeAuthGate("idempotency", "idempotency_required", _denies_idempotency),
)
```

**Catalog/platform rules to preserve** (`docs/contract-spec.md` lines 1386-1393):
```markdown
- `ToolPlatform.invoke` 必须先从 `ToolCatalog` 解析 descriptor，再校验 `ctx.caller_node`、`required_permission`、`input_schema`、`side_effect`、`exposure` 和 action safety fields，全部通过后才可调 domain executor；executor 输出必须按 descriptor `output_schema` 校验，封装或适配为 `ToolResultV2`，并通过 `ToolResultProjector` 生成 `ToolInvocationOutcome.projection`。
- `ToolPlatform.visible_tools` 输出给 planner 的只能是 `ToolView`，不能暴露 raw adapter、hidden side-effect capability、internal permission reason、raw exception shape 或 prompt-unsafe fields。
- `UnifiedToolManager` 可保留 legacy `invoke(...) -> ToolResultV2` / `visible_tools(...)` 兼容接口，但必须委托 `ToolPlatform`；新 graph/tool-platform integration 不得把它作为 policy/runtime owner。
- `ToolPolicyEngine` 必须为 planner visibility 和 runtime authorization 都产生 `ToolPolicyDecision` 或等价 decision event。Planner visible 不等于 runtime allowed；`invoke` 必须按 tool args、resource scope 和 current `ToolCallContext` 重新授权。
- `caller_allowlist` 必须使用合并后的单一节点名 `investigate`；不得声明旧节点名 `load_business_context` 或 `retrieve_policy_evidence`。
- `kind=read|retrieval` 的 descriptor 才可出现在 `investigate` allowlist，且 `side_effect` 必须为 `none|read_only|retrieval` 之一（非写副作用）；`kind=write` 不得通过 `BusinessToolService.invoke_tool` 或 `investigate` loop 执行。
- `event_family` 必须与 §12.4 事件族规则一致；同一 operation 只发 descriptor 指定的一族事件。
- catalog 是 read/retrieval/write 全量工具的声明来源，但「可被 LLM 在 `investigate` loop 内调用」仅限上一条的 read/retrieval 子集；write 工具在 catalog 中声明为 node-only，执行走 §13/§16 risk_gate → approval → `execute_action` → `ToolPlatform.invoke` → action executor 确定性安全链。write 工具的执行事件走 §17 `action_*` 事件族。
```

## Shared Patterns

### Docs-Only Reconciliation Boundary

**Source:** `39-RESEARCH.md` lines 146-172 and `39-VALIDATION.md` lines 45-55  
**Apply to:** Entire Phase 39 implementation.

Use the implemented Pydantic/catalog fields as evidence, then patch `docs/contract-spec.md`. Do not edit production code unless a new contradiction is proven and explicitly justified.

```markdown
| Markdown in `docs/contract-spec.md` | n/a | Normative contract source for §8.0, §12.5, and §12.6. | Phase 39 is a spec reconciliation phase and should edit this source, not production code. |
| Editing production models | Add fields to `src/tools/contracts.py` or `src/tools/catalog.py`. | Do not use; implementation already has required fields and Phase 39 is spec-catches-up-to-code. |
```

### Trusted Context Boundary

**Source:** `tests/architecture/test_trusted_context_boundaries.py` lines 58-82  
**Apply to:** §12.5 wording and any optional §8.0 projection-note update.

```python
def test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors() -> None:
    seams = [
        ROOT / "src" / "api" / "routers" / "search.py",
        ROOT / "src" / "api" / "routers" / "agent.py",
        ROOT / "src" / "api" / "routers" / "agent_runs.py",
        ROOT / "src" / "agent" / "nodes" / "investigate.py",
        ROOT / "src" / "agent" / "nodes" / "action_draft.py",
        ROOT / "src" / "tools" / "executors" / "knowledge.py",
    ]
    required_helpers = {
        "TrustedContextFactory",
        "project_to_tool_context",
        "project_to_knowledge_context",
        "project_tool_context_to_knowledge_context",
    }
    violations: list[str] = []

    for path in seams:
        source = path.read_text()
        if not any(helper in source for helper in required_helpers):
            violations.append(f"{path.relative_to(ROOT)} does not use trusted-context projection helpers")
        if "ToolCallContext(" in source or "KnowledgeContext(" in source:
            violations.append(f"{path.relative_to(ROOT)} still directly constructs service context")

    assert violations == []
    assert required_helpers
```

### Descriptor Action-Safety Metadata

**Source:** `tests/tools/test_catalog.py` lines 218-225  
**Apply to:** §12.6 descriptor fields and action `event_family`.

```python
def test_action_descriptor_is_node_only_and_requires_idempotency() -> None:
    descriptor = _descriptor("create_coupon_grant_draft")

    assert descriptor.kind == "write"
    assert descriptor.exposure == "node_only"
    assert descriptor.caller_allowlist == ["action_draft"]
    assert descriptor.requires_idempotency_key is True
```

### Policy Decision Is Not Event Envelope

**Source:** `tests/tools/test_tool_platform.py` lines 442-478  
**Apply to:** §12.6 `ToolPolicyDecision` edits; add availability fields without adding replay envelope fields.

```python
def test_tool_policy_decision_is_not_an_event_envelope() -> None:
    decision = ToolPolicyDecision(
        tool_name="get_order",
        caller="investigate",
        decision_stage="runtime_auth",
        decision="denied",
        reason_codes=["missing_permission"],
        required_scopes=["tool:get_order"],
        matched_scope=None,
        policy_version="tool_policy.v1",
        data_classification="internal",
        resource_scope_binding=None,
        runtime_available=True,
        availability_summary=None,
    )
    dumped = decision.model_dump()
    for envelope_field in ("event_id", "sequence", "occurred_at", "run_id", "tenant_id"):
        assert envelope_field not in dumped
    assert dumped["schema_version"] == "tool_policy_decision.v1"
    assert dumped["decision_stage"] == "runtime_auth"

    with pytest.raises(Exception):
        ToolPolicyDecision(
            tool_name="get_order",
            caller="investigate",
            decision_stage="runtime_auth",
            decision="denied",
            reason_codes=["missing_permission"],
            required_scopes=["tool:get_order"],
            matched_scope=None,
            policy_version="tool_policy.v1",
            data_classification="internal",
            resource_scope_binding=None,
            runtime_available=True,
            availability_summary=None,
            event_id="must-be-rejected",
        )
```

### Runtime Gate Ordering

**Source:** `tests/tools/test_tool_platform.py` lines 512-546  
**Apply to:** §12.6 action-safety wording.

```python
def test_runtime_auth_gate_sequence_is_declarative_and_ordered() -> None:
    gates = ToolPolicyEngine()._runtime_auth_gates

    assert [gate.name for gate in gates] == [
        "caller_allowlist",
        "permission",
        "side_effect",
        "resource_scope",
        "approval",
        "safety_snapshot",
        "idempotency",
    ]
```

```python
def test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order() -> None:
    decision = ToolPolicyEngine().runtime_auth(
        tool_name="create_coupon_grant_draft",
        args={"merchant_id": "M-DENIED"},
        ctx=_ctx(
            caller_node="investigate",
            permissions=[],
            merchant_scope=MerchantScopeV1(merchant_ids=["M-ALLOWED"]),
        ),
        availability_map={"create_coupon_grant_draft": True},
    )

    assert decision.decision == "denied"
    assert decision.reason_codes == [
        "caller_not_allowed",
        "missing_permission",
        "side_effect_blocked",
        "scope_denied",
        "safety_snapshot_required",
        "idempotency_required",
    ]
```

### Prompt-Safe View Boundary

**Source:** `tests/tools/test_tool_platform.py` lines 384-403  
**Apply to:** §12.6 descriptor metadata wording; raw descriptor fields are catalog/runtime metadata, not prompt-visible `ToolView` fields.

```python
def test_tool_view_exposes_only_prompt_safe_fields() -> None:
    engine = ToolPolicyEngine()
    views = engine.tool_views_for_decisions(
        engine.visibility_decisions(caller="investigate", ctx=_ctx()),
    )
    assert views, "at least one ToolViewV1 must be visible for investigate"
    view = next(item for item in views if item.name == "get_order")

    dumped = view.model_dump()
    assert set(dumped.keys()) == {
        "name",
        "description",
        "input_schema",
        "safe_usage_notes",
        "result_contract_version",
    }
    assert view.result_contract_version == "tool_result.v2"
    for forbidden in _FORBIDDEN_VIEW_FIELDS:
        assert forbidden not in dumped
    assert "create_coupon_grant_draft" not in {item.name for item in views}
```

### Availability Decisions Stay Outside Prompt Views

**Source:** `tests/tools/test_tool_platform.py` lines 549-581  
**Apply to:** §12.6 `runtime_available` / `availability_summary` wording.

```python
@pytest.mark.asyncio
async def test_visible_tools_records_hidden_and_unavailable_decisions_outside_prompt() -> None:
    from src.tools.platform import ToolPlatform

    catalog = ToolCatalog()
    # Make get_order unavailable by supplying an executor registry that lacks it.
    platform = ToolPlatform(catalog=catalog, executors={})
    views = await platform.visible_tools(caller="investigate", ctx=_ctx(), session=None)

    assert isinstance(views, list)
    assert all(isinstance(view, ToolViewV1) for view in views)
    visible_names = {view.name for view in views}
    assert "get_order" not in visible_names
    assert "create_coupon_grant_draft" not in visible_names
    write_descriptor = _descriptor("create_coupon_grant_draft")
    assert write_descriptor.exposure == "node_only"
    # Hidden / unavailable decisions are recorded outside the returned prompt views.
    visibility_events = getattr(platform, "last_visibility_decisions", None)
    assert visibility_events is not None, "ToolPlatform must retain/emit visibility decisions outside the prompt"
    decisions_by_name = {decision.tool_name: decision for decision in visibility_events}
    assert {"get_order", "create_coupon_grant_draft"} <= set(decisions_by_name)

    get_order_decision = decisions_by_name["get_order"]
    assert get_order_decision.decision_stage == "visibility"
    assert get_order_decision.decision == "hidden"
    assert get_order_decision.runtime_available is False
    assert "tool_unavailable" in get_order_decision.reason_codes

    draft_decision = decisions_by_name["create_coupon_grant_draft"]
    assert draft_decision.decision_stage == "visibility"
    assert draft_decision.decision == "hidden"
    assert "hidden_by_policy" in draft_decision.reason_codes
```

## Structural Validation Commands

Use these exact command patterns from `39-VALIDATION.md` lines 20 and 31-55. They use project-approved `uv run pytest` for Python tests and standard shell tools for doc/diff checks.

```bash
rg -n "effective_at|approval_ref|safety_snapshot_ref" docs/contract-spec.md
rg -n "executor|exposure|requires_approval|requires_safety_snapshot|requires_idempotency_key" docs/contract-spec.md
rg -n "event_family: Literal\\[.*action|runtime_available|availability_summary" docs/contract-spec.md
git show --stat --oneline 4dcb673 -- docs/contract-spec.md
git show --unified=80 4dcb673 -- docs/contract-spec.md
git diff --name-only -- docs/contract-spec.md src/tools/contracts.py src/tools/catalog.py src/tools/policy.py src/tools/runtime.py tests
git diff --check
uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py::test_action_descriptor_is_node_only_and_requires_idempotency tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope tests/tools/test_tool_platform.py::test_runtime_auth_gate_sequence_is_declarative_and_ordered tests/tools/test_tool_platform.py::test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order -q
```

Full focused suite if the planner wants the broader validation gate:
```bash
uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q
```

If any Python file is changed despite the expected docs-only scope, add an explicit justification and use project-approved lint wording such as:
```bash
uv run ruff check src/tools tests
```

## No Analog Found

None for the expected target file. The codebase has exact source analogs for every required §12.5/§12.6 field addition.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| n/a | n/a | n/a | No unmatched expected target files. |

## Metadata

**Analog search scope:** `docs/contract-spec.md`, `src/tools/contracts.py`, `src/tools/catalog.py`, `src/tools/policy.py`, `tests/architecture/test_trusted_context_boundaries.py`, `tests/tools/test_catalog.py`, `tests/tools/test_tool_platform.py`, and targeted `rg` over `docs`, `src`, `tests`, and `.planning/phases`.  
**Files read:** 9 required phase/source/test files plus `CLAUDE.md`.  
**Prior pattern maps discovered:** `37-PATTERNS.md`, `38-PATTERNS.md`; not used as primary analogs because current §12.5/§12.6 source files are more direct.  
**Current dirty worktree note:** `.planning/LOCAL-VALIDATION-ISSUES.md` was already modified before this pattern write and was not touched.  
**Pattern extraction date:** 2026-07-02
