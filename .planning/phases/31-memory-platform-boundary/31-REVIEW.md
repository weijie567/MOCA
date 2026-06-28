---
phase: 31-memory-platform-boundary
reviewed: 2026-06-28T07:40:43Z
depth: deep
files_reviewed: 24
files_reviewed_list:
  - src/agent/context/projectors.py
  - src/agent/nodes/long_term_memory_retrieve.py
  - src/agent/nodes/memory_write.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/reviewed_memory_context_retrieve.py
  - src/agent/nodes/session_context_load.py
  - src/agent/nodes/session_memory_load.py
  - src/agent/rag_context/verifier.py
  - src/agent/state.py
  - src/memory/__init__.py
  - src/memory/context_refs.py
  - src/memory/context_service.py
  - src/memory/schemas.py
  - src/memory/session_bundle.py
  - tests/agent/rag_context/test_authority_boundaries.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_memory_write_node.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_reviewed_memory_context_retrieve.py
  - tests/agent/test_session_memory_load.py
  - tests/memory/test_context_refs.py
  - tests/memory/test_reviewed_memory_context_boundary.py
  - tests/memory/test_session_memory_bundle.py
  - tests/memory/test_session_memory_isolation.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-06-28T07:40:43Z
**Depth:** deep
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Reviewed the memory platform boundary changes across agent nodes, memory DTOs/services, prompt projection, verifier boundaries, and related tests. The new boundary is mostly well covered for reviewed-memory authority separation, but there is one production-shape authorization bug and two contract/state hygiene issues that should be fixed before treating the phase as clean.

No verification command was run during this review.

## Critical Issues

### CR-01: Production trusted_context dict bypasses session merchant-scope filtering

**File:** `src/agent/nodes/session_context_load.py:285`

**Issue:** `_trusted_merchant_ids()` only reads `trusted_context` via object attributes:

```python
merchant_scope = getattr(trusted_context, "merchant_scope", None)
merchant_ids = getattr(merchant_scope, "merchant_ids", None)
```

However the production graph config serializes the trusted context with `trusted_context.model_dump(mode="json")` before invoking the graph (`src/api/routers/agent.py:243`, also mirrored by agent_runs/approvals). In that real shape, `trusted_context` and `merchant_scope` are dicts, so `_trusted_merchant_ids()` returns `[]`. That disables the `denied_by_trusted_scope` branch at lines 184-188, allowing same-thread session summaries/messages/tool summaries and inherited slots from a different merchant to remain in context whenever the current turn does not explicitly provide a merchant slot. Existing isolation tests pass a `TrustedContext` object, so they do not cover the production dict shape.

**Fix:**

```python
from collections.abc import Mapping

def _trusted_merchant_ids(trusted_context: Any | None) -> list[str]:
    if isinstance(trusted_context, Mapping):
        merchant_scope = trusted_context.get("merchant_scope")
    else:
        merchant_scope = getattr(trusted_context, "merchant_scope", None)

    if isinstance(merchant_scope, Mapping):
        merchant_ids = merchant_scope.get("merchant_ids")
    else:
        merchant_ids = getattr(merchant_scope, "merchant_ids", None)

    if not merchant_ids:
        return []
    return [str(merchant_id) for merchant_id in merchant_ids if str(merchant_id) != "*"]
```

Add a regression test that calls `session_context_load()` with `{"trusted_context": trusted_context.model_dump(mode="json")}` and asserts cross-merchant session context is filtered.

## Warnings

### WR-01: receive_request leaves stale RAG/verifier fields in checkpointed state

**File:** `src/agent/nodes/receive_request.py:87`

**Issue:** `receive_request()` is the per-turn checkpoint reset boundary, but it still does not clear the RAG/verifier fields declared in `AgentState` (`rag_context_bundle`, `verifier_status`, `verification_route`, `verifier_reason_codes`, `verifier_safe_citation_refs`, `verifier_metrics`) and also omits the live `rag_verification` field written by `generate_recommendation`. In a checkpointed thread, those values can leak into a later turn and affect final-response/risk routing helpers that consult `rag_verification` or `verification_route`.

**Fix:**

```python
return {
    ...
    "policy_evidence": None,
    "case_memory": None,
    "claim_dependency_map": None,
    "rag_context_bundle": None,
    "rag_verification": None,
    "verifier_status": None,
    "verification_route": None,
    "verifier_reason_codes": None,
    "verifier_safe_citation_refs": None,
    "verifier_metrics": None,
    "session_context": None,
    ...
}
```

Also add `rag_verification: dict[str, Any] | None` to `AgentState` and extend `tests/agent/test_nodes/test_receive_request.py` to seed all verifier fields and assert they reset to `None`.

### WR-02: SessionContextLoadStatusV1 does not accept status objects produced by the node

**File:** `src/memory/context_refs.py:49`

**Issue:** `session_context_load` adds `filter_reasons` to every `session_context_load_status` dict (`src/agent/nodes/session_context_load.py:332-335` and fallback line 396), but `SessionContextLoadStatusV1` has `extra="forbid"` and no `filter_reasons` field. Any downstream code that validates node output against the public DTO will reject a status object produced by the node itself.

**Fix:**

```python
class SessionContextLoadStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["session_context_load_status.v1"] = "session_context_load_status.v1"
    status: str
    source: str
    authority_class: Literal["contextual_only"] = "contextual_only"
    tenant_id: str
    user_id: str
    thread_id: str
    run_id: str
    loaded_refs: list[SessionContextRef] = Field(default_factory=list)
    fallback_reason: str | None = None
    slot_count: int = 0
    recent_message_count: int = 0
    tool_summary_count: int = 0
    filter_reasons: list[str] = Field(default_factory=list)
```

Add a test that validates `SessionContextLoadStatusV1.model_validate(result["session_context_load_status"])` for both loaded and fallback node outputs.

---

_Reviewed: 2026-06-28T07:40:43Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
