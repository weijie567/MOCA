---
phase: 46-session-context-repositioning
reviewed: 2026-07-03T09:40:10Z
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
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 46: Code Review Report

**Reviewed:** 2026-07-03T09:40:10Z
**Depth:** deep
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Deep review covered the Phase 46 session-context bundle code, boundary tests, and docs. The core `src/memory/session_bundle.py` allowlist projection correctly strips full policy evidence identities (`tenant_id`, `evidence_id`, `text_hash`, `retrieved_at`, etc.) and full business fact authority fields (`tenant_id`, freshness/retrieval timestamps), so the serialized session hints are not directly valid `EvidenceRefV1` or `BusinessFactRefV1` authority DTOs. Cross-file tracing also found no Phase 47/48 implementation, no destructive session schema change, no session memory CWC fallback path, and no reviewed precedent path backed by session memory in runtime code.

Scoped verification passed:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_bundle.py tests/memory/test_phase46_session_context_alignment.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_memory_write_service.py tests/agent/context/test_assembler.py::test_context_assembler_consumes_memory_context_bundle_without_promoting_policy_hints_to_evidence -q
```

Result: 45 passed, 3 warnings.

## Warnings

### WR-01: Current Implementation Map Contradicts Implemented Conversation And Tool Context Storage

**File:** `docs/current-implementation-map.md:68`
**Issue:** The map still says conversation threads/messages, tool calls/results, and thread summaries are "currently not found" or missing. The current code has `ConversationThread`, `ConversationMessage`, `ToolCallRecord`, `ToolResultRecord`, and `ConversationSummary` models plus repository/service methods that Phase 46 now depends on for `SessionMemoryBundleService` prompt context. This makes the "current implementation" doc materially stale and can mislead future memory/context work into planning already-implemented foundations as absent.
**Fix:** Update rows 68-71 and the gap list to distinguish "implemented prompt-safe/redacted conversation context" from still-missing raw prompt/raw tool-output replay:

```markdown
| Conversation threads/messages | `src/db/models.py:1212`, `src/conversation/*` | Stores thread-scoped user/assistant/tool messages and prompt-safe context metadata | conversation log projection | Implemented as redacted/prompt-safe conversation context, not raw prompt/tool transcript |
| Tool calls/results tables | `src/db/models.py:1357`, `src/db/models.py:1401`, `src/conversation/repository.py:436` | Stores tool call argument summaries, normalized result JSON, prompt summaries, raw result refs/hashes | tool log projection | Implemented for prompt-safe context; still not a raw payload store |
| Thread summaries | `src/db/models.py:1448`, `src/conversation/repository.py:398` | Stores rolling thread summaries with source message/tool result ids | short-term conversation context | Implemented; session memory remains slot continuity |
```

Then revise the "关键缺口" bullets to say raw prompt/raw tool payload reconstruction is still missing, rather than all conversation/tool/summary primitives.

### WR-02: Target Workflow Diagram Still Names The Old Session Precedent Service

**File:** `docs/architecture-overview.md:359`
**Issue:** The controlled workflow diagram still labels the memory executor as `SessionPrecedentSearchService`, while the same file now says planner-facing `search_case_memory` uses `CaseMemoryService.retrieve_reviewed(...)` and `LegacySessionPrecedentSearchService` is debug-only. This contradicts the Phase 46 red line that reviewed precedent must not come from session memory.
**Fix:** Change the diagram label to match the implemented and documented boundary:

```markdown
Manager -->|memory executor| MemoryExec[MemoryToolExecutor\nCaseMemoryService.retrieve_reviewed]
```

or use `Reviewed case memory service` if the diagram should remain implementation-agnostic.

### WR-03: Prompt-Safety Test Mutates An Unused Column

**File:** `tests/memory/test_session_memory_bundle.py:155`
**Issue:** The test writes forbidden marker text to `stored_tool_result.summary`, then asserts those markers are absent from the serialized session bundle. The bundle code reads `record.prompt_summary` and skips `record.summary`, so this assertion would still pass even if `prompt_summary` itself leaked `raw_payload`, `private_reasoning`, or `secret` into session context. That leaves the MEM-03 prompt-safety guard weaker than it looks.
**Fix:** Either test the actual bundle input, or make the ownership explicit. A defensive version would sanitize/read `prompt_summary` and mutate that field in the test:

```python
stored_tool_result.prompt_summary = "raw_payload private_reasoning approval_authority_body debug_trace secret"
```

If `prompt_summary` is intentionally guaranteed safe only by the upstream projector, replace the current assertion with an upstream projector test and remove the misleading mutation of `summary` from this bundle test.

---

_Reviewed: 2026-07-03T09:40:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
