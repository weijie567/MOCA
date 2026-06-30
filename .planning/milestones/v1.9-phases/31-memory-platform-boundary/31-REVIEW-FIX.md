---
phase: 31-memory-platform-boundary
fixed_at: 2026-06-28T10:24:52Z
review_path: .planning/phases/31-memory-platform-boundary/31-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 31: Code Review Fix Report

**Fixed at:** 2026-06-28T10:24:52Z
**Source review:** .planning/phases/31-memory-platform-boundary/31-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: contextual-only memory ref 可通过 citation_map 被当成 policy evidence 支持 claim

**Status:** fixed: requires human verification
**Files modified:** `src/agent/rag_context/verifier.py`, `tests/agent/rag_context/test_authority_boundaries.py`
**Commit:** f54033d
**Applied fix:** Contextual memory/status refs in `citation_map` are now identified as non-authority, excluded from active evidence ids, `safe_refs`, and claim snippets. Added a regression proving a `reviewed_memory_ref.v1` citation cannot support a policy claim.

### CR-02: session memory write 会持久化未参与 PII 分类的 unresolved_questions

**Status:** fixed: requires human verification
**Files modified:** `src/agent/nodes/memory_write.py`, `tests/agent/test_memory_write_node.py`
**Commit:** f5ac4ab
**Applied fix:** `memory_write` now classifies all persisted candidate text, including `unresolved_questions` and `session_summary`, before deciding whether to call `MemoryService`. Added a regression covering phone/id/token text carried only by clarification questions.

### WR-01: reviewed memory retrieval uses LLM candidate_slots to create merchant retrieval scope

**Status:** fixed: requires human verification
**Files modified:** `src/agent/nodes/reviewed_memory_context_retrieve.py`, `tests/agent/test_reviewed_memory_context_retrieve.py`
**Commit:** ccf7c26
**Applied fix:** Reviewed-memory retrieval scope now uses only post-extraction `extracted_slots`, ignoring LLM `candidate_slots`. Added a regression proving candidate-slot merchant ids do not trigger long-term/case memory service calls and fall back with `memory_scope_not_authority`.

---

_Fixed: 2026-06-28T10:24:52Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
