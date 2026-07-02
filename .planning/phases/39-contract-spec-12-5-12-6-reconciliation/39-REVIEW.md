---
phase: 39-contract-spec-12-5-12-6-reconciliation
reviewed: 2026-07-02T03:31:58Z
depth: deep
files_reviewed: 1
files_reviewed_list:
  - docs/contract-spec.md
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 39: Code Review Report

**Reviewed:** 2026-07-02T03:31:58Z
**Depth:** deep
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed the Phase 39 `docs/contract-spec.md` diff against `src/tools/contracts.py`, `src/tools/catalog.py`, and relevant tool-platform enforcement code/tests. The scoped implementation diff is docs-only, and no changed diff line mutates the protected §8.0 identity/scope/permission field definitions (`tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, `trace_id`).

The new §12.5 local fields and §12.6 `ToolDescriptor` / `ToolPolicyDecision` fields mostly match the implemented Pydantic models. Two §12.6 contract drift issues remain: the protocol return type for `event_family()` is now inconsistent with the optional descriptor/implementation, and the write-tool path still points at the retired `execute_action` node instead of the canonical `action_draft` tool caller.

## Warnings

### WR-01: `event_family()` Protocol Still Promises Non-Null Return

**File:** `docs/contract-spec.md:1384`

**Issue:** Phase 39 correctly updates `ToolDescriptor.event_family` to `Literal["tool_call_*", "rag_retrieval_*", "action"] | None`, matching `src/tools/catalog.py`. However, the §12.6 `ToolPlatform` protocol still says `def event_family(self, name: str) -> str: ...`. The concrete facade returns `str | None` for missing tools or descriptors with no event family (`src/tools/platform.py:139`). The spec currently tells callers that event routing is always available, which can produce incorrect audit/event assumptions for unknown or intentionally non-emitting tools.

**Fix:**
```python
class ToolPlatform(Protocol):
    def visible_tools(self, caller: str, ctx: ToolCallContext) -> list[ToolView]: ...
    async def invoke(self, name: str, input_data: dict[str, Any], ctx: ToolCallContext) -> ToolInvocationOutcome: ...
    def descriptor(self, name: str) -> ToolDescriptor | None: ...
    def event_family(self, name: str) -> str | None: ...
```

Also add a rule that callers must handle `None` explicitly instead of fabricating a fallback event family.

### WR-02: §12.6 Write-Tool Path Names Retired `execute_action` Node

**File:** `docs/contract-spec.md:1404`

**Issue:** The spec says write tools execute through `risk_gate -> approval -> execute_action -> ToolPlatform.invoke -> action executor`. Current code and architecture tests make `action_draft` the canonical caller for the write descriptor: `create_coupon_grant_draft` has `caller_allowlist=["action_draft"]`, `exposure="node_only"`, and safety/idempotency requirements in `src/tools/catalog.py`; tests assert `_side_effect_allowed("execute_action", descriptor) is False` and the graph does not register `execute_action`. Leaving `execute_action` in this normative §12.6 path can steer future implementation toward the compatibility shim or a caller name that runtime auth must reject.

**Fix:** Replace the path wording with the implemented canonical caller:

```markdown
- catalog 是 read/retrieval/write 全量工具的声明来源，但「可被 LLM 在 `investigate` loop 内调用」仅限上一条的 read/retrieval 子集；write 工具在 catalog 中声明为 node-only，执行走 §13/§16 risk_gate -> approval/auto-allow binding -> `action_draft` -> `ToolPlatform.invoke("create_coupon_grant_draft", ..., ctx.caller_node="action_draft")` -> action executor / ActionDraftService 确定性安全链。write 工具的执行事件走 §17 `action_*` 事件族。
```

---

_Reviewed: 2026-07-02T03:31:58Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
