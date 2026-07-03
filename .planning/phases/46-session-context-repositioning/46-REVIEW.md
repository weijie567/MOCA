---
phase: 46-session-context-repositioning
reviewed: 2026-07-03T10:09:26Z
depth: deep
files_reviewed: 9
files_reviewed_list:
  - docs/architecture-overview.md
  - docs/contract-spec.md
  - docs/current-implementation-map.md
  - src/memory/session_bundle.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_reviewed_memory_context_retrieve.py
  - tests/memory/test_memory_write_service.py
  - tests/memory/test_phase46_session_context_alignment.py
  - tests/memory/test_session_memory_bundle.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 46: Code Review Report

**Reviewed:** 2026-07-03T10:09:26Z
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Deep review covered the Phase 46 docs, session context bundle implementation, authority-boundary tests, reviewed-memory retrieval tests, and memory write tests. The previous WR-02 is resolved in current HEAD: `docs/architecture-overview.md` now routes the memory executor to `CaseMemoryService.retrieve_reviewed`, and the reviewed-memory tests keep session-derived precedent out of the planner-facing path.

The MEM-03 authority boundary is mostly intact: session context and reviewed memory surfaces are `contextual_only`, strict authority DTO parsing rejects contextual refs, reviewed memory fails closed without trusted scope, session context is not used as CWC identity, and memory-supported claims do not authorize policy, business fact, approval, action, or replay truth. Two warnings remain: the implementation map is stale, and the bundle layer still trusts stored prompt summary/hint strings more than the Phase 46 prompt-safe contract and tests imply.

Scoped verification passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_bundle.py tests/memory/test_phase46_session_context_alignment.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_memory_write_service.py tests/agent/context/test_assembler.py::test_context_assembler_consumes_memory_context_bundle_without_promoting_policy_hints_to_evidence -q
```

Result: 45 passed, 3 warnings.

## Warnings

### WR-01: Current Implementation Map Still Marks Implemented Context Storage As Missing

**File:** `docs/current-implementation-map.md:68`
**Issue:** The map still says conversation threads/messages, thread summaries, `ContextAssembler`, and parts of tool call/result storage are "currently not found" or missing. Current HEAD has `ConversationThread`, `ConversationMessage`, `ToolCallRecord`, `ToolResultRecord`, and `ConversationSummary` models, plus `ConversationService.load_prompt_context(...)` and `ContextAssembler`. Phase 46 now depends on these surfaces through `SessionMemoryBundleService`, so the current-state doc can mislead follow-up memory/context phases into planning already-implemented foundations as absent.
**Fix:** Update rows 68-71 and the gap list to distinguish implemented prompt-safe/redacted conversation context from still-missing raw prompt/raw payload reconstruction. For example:

```markdown
| Conversation threads/messages | `src/db/models.py:1212`, `src/db/models.py:1305`, `src/conversation/*` | Stores thread-scoped user/assistant/tool messages and prompt context metadata | conversation log projection | Implemented as redacted/prompt-safe conversation context, not a raw prompt/tool transcript |
| Tool calls/results tables | `src/db/models.py:1357`, `src/db/models.py:1401`, `src/conversation/repository.py:436` | Stores tool call summaries, normalized result JSON, prompt summaries, raw result refs/hashes | tool log projection | Implemented for prompt-safe context; still not a raw payload store |
| Thread summaries | `src/db/models.py:1448`, `src/conversation/repository.py:398` | Stores rolling thread summaries with source message/tool result ids | short-term conversation context | Implemented; `session_memories` remains slot continuity |
| ContextAssembler | `src/agent/context/assembler.py:28` | Assembles system, working state, summary, recent messages, policy refs, tool summaries, and memory context under budget | prompt context assembly | Implemented, with remaining node adoption depending on each agent path |
```

### WR-02: Session Bundle Can Carry Unsanitized Prompt Summary And Hint Text

**File:** `src/memory/session_bundle.py:120`
**Issue:** `_tool_summary_views` copies `record.prompt_summary` directly into `SessionToolSummaryView`, and `_safe_hint_value` only trims/truncates allowed policy hint values. The final prompt assembler strips several forbidden markers later, but the serialized `SessionMemoryBundle` / `SessionContextBundle` can still contain `raw_payload`, `private_reasoning`, `approval_authority_body`, `debug_trace`, `secret`, or similar strings if they appear in `prompt_summary`, `title`, `section`, or another allowed hint field. This is the same underlying gap as the prior WR-03: `tests/memory/test_session_memory_bundle.py:155` mutates `stored_tool_result.summary`, but the bundle reads `prompt_summary`, so the test does not exercise the risky bundle input.
**Fix:** Sanitize prompt summary and hint values at the bundle boundary, then change the test to mutate `prompt_summary` and add a policy title/section marker case. One local implementation shape:

```python
_FORBIDDEN_HINT_MARKERS = (
    "raw_payload",
    "raw_tool_output",
    "private_reasoning",
    "approval_authority_body",
    "action_authority_body",
    "debug_trace",
    "secret",
    "EvidenceRefV1",
    "ReplayEventV3",
)

def _safe_hint_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool | int | float):
        text = str(value)
    elif isinstance(value, str):
        text = " ".join(value.split())
    else:
        return None
    for marker in _FORBIDDEN_HINT_MARKERS:
        text = text.replace(marker, "")
    text = " ".join(text.split())
    return text[:120] if text else None
```

Use the sanitized value for `prompt_summary` before constructing `SessionToolSummaryView`; if it becomes empty, skip that summary or fall back to a known-safe status line.

---

_Reviewed: 2026-07-03T10:09:26Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
