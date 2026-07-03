---
phase: 46-session-context-repositioning
reviewed: 2026-07-03T10:38:39Z
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
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 46: Code Review Report

**Reviewed:** 2026-07-03T10:38:39Z
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Deep re-review covered the Phase 46 architecture docs, contract doc, current implementation map, the new `SessionMemoryBundleService`, and the Phase 46 memory/session-context boundary tests. The prior WR-02 is closed: `src/memory/session_bundle.py` now sanitizes `prompt_summary` and allowed hint fields at the bundle boundary, and `tests/memory/test_session_memory_bundle.py` poisons the actual risky `prompt_summary`, `title`, and `section` inputs. I did not find a new regression in the sanitizer fixes.

The prior WR-01 is mostly closed: rows for conversation threads/messages, tool calls/results, thread summaries, and `ContextAssembler` now describe implemented prompt-safe surfaces and separate them from the still-missing raw prompt/raw payload reconstruction. One stale implementation-map row remains and can still mislead follow-up planning.

Scoped verification passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_bundle.py tests/memory/test_phase46_session_context_alignment.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_memory_write_service.py tests/agent/context/test_assembler.py::test_context_assembler_consumes_memory_context_bundle_without_promoting_policy_hints_to_evidence -q
```

Result: 45 passed, 3 warnings.

## Warnings

### WR-01: Implementation Map Still Says Raw Result Refs Lack A Persistence Path

**File:** `docs/current-implementation-map.md:44`
**Issue:** The `Tool contract` row still says MOCA lacks a formal persistence path for `raw result ref`. Current HEAD has `ToolResultStorageV1.raw_result_ref/raw_result_hash`, `tool_results.raw_result_ref/raw_result_hash`, `ConversationService.append_tool_result(...)`, and `ConversationRepository.append_tool_result(...)` writing those fields. This conflicts with the corrected row 69 and gap item 2, where the remaining gap is raw payload object storage/access/lifecycle, not the ref/hash columns or write path.
**Fix:** Update the row to distinguish the implemented ref/hash persistence path from the still-missing raw payload object-store contract. For example:

```markdown
| Tool contract | `src/tools/contracts.py:71`, `src/tools/contracts.py:111` | `ToolResultV2` is the prompt-safe result envelope; `ToolResultStorageV1` / `tool_results` carry normalized result, prompt summary, and `raw_result_ref` / `raw_result_hash` | tool result projection / storage contract | raw result refs/hashes are persisted; raw payload object storage, access policy, and lifecycle remain unconfirmed |
```

---

_Reviewed: 2026-07-03T10:38:39Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
