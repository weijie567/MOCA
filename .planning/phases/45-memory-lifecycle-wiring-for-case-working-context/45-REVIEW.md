---
phase: 45-memory-lifecycle-wiring-for-case-working-context
reviewed: 2026-07-03T06:06:21Z
depth: deep
files_reviewed: 13
files_reviewed_list:
  - docs/contract-spec.md
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/reviewed_memory_context_retrieve.py
  - src/agent/state.py
  - src/api/services/agent_run_memory.py
  - src/memory/case_working_context_lifecycle.py
  - src/memory/context_refs.py
  - tests/agent/test_case_working_context_lifecycle.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_reviewed_memory_context_retrieve.py
  - tests/memory/test_context_refs.py
  - tests/memory/test_phase45_contract_alignment.py
  - tests/test_agent_runs_api.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 45: Code Review Report

**Reviewed:** 2026-07-03T06:06:21Z
**Depth:** deep
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Deep review covered the Phase 45 contract updates, CWC lifecycle adapter, memory-context load wiring, terminal finalizer writeback, and focused tests. The main trust boundaries hold: CWC stays contextual-only, reviewed `case_memory` and `long_term_memory` are not repurposed, `conversation_threads.case_id` is retained, and `investigate` is not made a graph-global `active_slots` writer.

Verification run during review:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase45_contract_alignment.py tests/test_agent_runs_api.py -q` -> `138 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check docs/contract-spec.md src/agent/nodes/receive_request.py src/agent/nodes/reviewed_memory_context_retrieve.py src/agent/state.py src/api/services/agent_run_memory.py src/memory/case_working_context_lifecycle.py src/memory/context_refs.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_context_refs.py tests/memory/test_phase45_contract_alignment.py tests/test_agent_runs_api.py` -> `All checks passed!`

## Warnings

### WR-01: Terminal Link Status Can Report Linked When Repository Deduped an Existing Link

**File:** `src/memory/case_working_context_lifecycle.py:357`

**Issue:** `_link_terminal_thread_case()` checks for an existing link only when both `link_source="run_auto"` and `linked_by_run_id=run_id` match. In a normal multi-run same-thread flow, an active `(tenant, thread, case)` link may already exist from an earlier run. `ThreadCaseLinkRepository.link_thread_to_case()` then returns that existing active link without creating a new row, but `_link_terminal_thread_case()` still returns `"linked"` at line 388 because the pre-check missed the existing row. This does not create duplicate data, but it makes CWC lifecycle status and trace metrics claim a new link when the write path was actually deduped.

**Fix:** Detect any active thread-case link before attempting the terminal link, or derive status from the repository result.

```python
was_already_linked = await _has_active_thread_case_link(
    session,
    conversation_repository=conversation_repository,
    tenant_id=tenant_id,
    user_id=user_id,
    thread_id=thread_id,
    case_id=case_id,
)
if was_already_linked:
    return "deduped"

async with session.begin_nested():
    await conversation_repository.link_case(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        case_id=case_id,
        link_source="run_auto",
        linked_by_run_id=run_id,
    )
return "linked"
```

---

_Reviewed: 2026-07-03T06:06:21Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
