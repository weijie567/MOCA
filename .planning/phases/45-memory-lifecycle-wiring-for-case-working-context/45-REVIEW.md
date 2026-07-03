---
phase: 45-memory-lifecycle-wiring-for-case-working-context
reviewed: 2026-07-03T07:21:51Z
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

**Reviewed:** 2026-07-03T07:21:51Z
**Depth:** deep
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Deep review covered the Phase 45 contract changes, CWC lifecycle adapter, memory-context load seam, terminal finalizer writeback, and targeted tests. The main trust boundaries hold: CWC remains contextual-only, reviewed `case_memory` and `long_term_memory` are not repurposed, legacy `conversation_threads.case_id` is retained, and `investigate` is not made a graph-global `active_slots` writer.

The review traced the cross-file call chain from `reviewed_memory_context_retrieve` to `CaseWorkingContextLifecycleAdapter.link_and_load_active`, and from `finalize_completed_agent_run_memory` to `write_after_terminal_success`, `ConversationRepository.link_case`, `ThreadCaseLinkRepository`, and `CaseWorkingContextService`. No critical security or data-loss issue was found. One warning remains around lifecycle status accuracy when terminal writeback encounters an already-active thread-case link.

## Warnings

### WR-01: Terminal Link Status Can Report Linked When Repository Deduped an Existing Link

**File:** `src/memory/case_working_context_lifecycle.py:357`

**Issue:** `_link_terminal_thread_case()` checks for an existing link only when both `link_source="run_auto"` and `linked_by_run_id=run_id` match. In a normal multi-run same-thread flow, or when a staff/import link already exists for the same `(tenant, thread, case)`, `ThreadCaseLinkRepository.link_thread_to_case()` returns the existing active link because the database uniqueness boundary is `(tenant_id, conversation_thread_id, case_id)`. The current code then returns `"linked"` at line 388 even though no new `run_auto` link was created. This does not create duplicate rows, but it makes lifecycle status and trace metrics overstate what happened.

**Fix:** Detect any active thread-case link before attempting the terminal link, or derive the status from the repository result.

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

_Reviewed: 2026-07-03T07:21:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
