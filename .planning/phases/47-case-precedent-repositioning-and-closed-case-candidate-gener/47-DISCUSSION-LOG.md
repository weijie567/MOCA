# Phase 47 Discussion Log

**Date:** 2026-07-03
**Mode:** Execution-style discussion
**Reason:** User explicitly asked "你来执行", so Phase 47 discuss did not pause for every interactive question. Defaults were selected from MEM-04, prior Phase 44-46 decisions, and current repository facts.

## Inputs Read

- `.planning/ROADMAP.md` Phase 47
- `.planning/REQUIREMENTS.md` MEM-04
- `.planning/MEMORY-REDESIGN-DECISIONS.md` DEFER-2 / D3 / D4 / D5
- `.planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-CONTEXT.md`
- `.planning/phases/46-session-context-repositioning/46-CONTEXT.md`
- `docs/contract-spec.md` Section 13.4 / 13.4a / 13.5 / 13.6
- `docs/current-implementation-map.md`
- `docs/architecture-overview.md`
- Relevant source/tests around `CaseMemory`, CWC, memory write, reviewed memory retrieval, memory review API, refund case model, and `search_case_memory`.

## Local Facts Confirmed

- Phase 47 directory had no planning artifacts yet, only `.gitkeep`.
- `gsd-sdk query todo.match-phase 47` returned zero matching todos.
- `case_memories` already has review status, source refs, source identity hash, content hash, optional embedding, metadata filters, and review/audit columns.
- `memory_write_events.memory_type` already includes `case_memory`; case memory writes emit observable events.
- `CaseMemoryService.submit_case_memory_candidate(...)` already writes `needs_review` candidates for review-required sources.
- `CaseMemoryService.retrieve_reviewed(...)` already excludes non-published review statuses and non-prompt-safe PII.
- Existing reviewed memory context and planner-facing `search_case_memory` use `CaseMemoryService.retrieve_reviewed(...)`; session-derived precedent is legacy/debug-only.
- CWC active read/write exists through Phase 44/45, but current code has no dedicated refund-case close-transition service.
- `RefundCase.status` exists as a free string; seeded data currently uses values such as `reviewing` and `open`.
- `ToolCallContext` has merchant scope but no case id, and Phase 47 must not widen locked tool-context identity fields.

## Gray Areas Resolved

### 1. Should generated case precedent auto-publish?

Decision: No.

Generated closed-case precedents are automatic candidates only. They default to `needs_review` and are not retrievable until approved. This follows MEMORY-REDESIGN D4 and reuses the existing case memory review workflow.

Rejected option: directly writing generated closed-case rows as `approved` or `auto_approved`.

### 2. Is a completed agent run a case-close event?

Decision: No.

Phase 45 terminal CWC writeback is per-run working-state update. Phase 47 closed-case precedent generation requires a trusted business close/resolved event or an explicit internal close-trigger seam. If the production close hook does not exist, Phase 47 should deliver the seam and tests, not invent closure from `AgentRun.final_status == "completed"`.

Rejected option: piggyback closed-case generation onto every completed finalizer run.

### 3. Should Phase 47 create a new review queue?

Decision: No.

Use `CaseMemoryService.submit_case_memory_candidate(...)`, existing `case_memories.review_status`, existing pending review list, and existing approve/reject/delete/forget actions.

Rejected option: a second pending-precedent table or queue.

### 4. Where should generated precedents be scoped?

Decision: Separate retrieval scope from source identity.

`CaseMemory.scope_type/scope_id` is how retrieval finds a precedent. `source_ref_json.business_object_type/business_object_id` carries the source refund case. Closed-case precedents should prefer merchant-scope storage when `RefundCase -> Order.merchant_id` is available, while preserving exact source case identity in `source_ref_json`.

Rejected option: storing every generated precedent only as `scope_type="case"` and relying on planner-facing merchant search to find it anyway.

### 5. Should Phase 47 add a dedicated source type?

Recommendation: Prefer an additive review-required source type such as `closed_case_cwc_candidate`.

Reason: it makes closed-case provenance, policy, tests, and duplicate/audit interpretation explicit. It does not require a DB migration because source type is in Pydantic/policy/source-ref handling, not a checked DB column.

Fallback allowed: reuse `summary_candidate` only if planning documents why a new source type is unnecessary and still pins closed-case provenance in `source_ref_json`.

### 6. Should retrieval require vector search?

Decision: No.

Metadata-first retrieval remains the MVP. Exact tenant/scope/case-type/policy/text retrieval must work without embeddings. Optional vector search can stay as a ranking path.

Rejected option: generating embeddings as a required path for Phase 47 acceptance.

### 7. Does Phase 47 touch Phase 48 long-term preference memory?

Decision: No.

DEFER-3 remains Phase 48. Phase 47 must not introduce generic automatic long-term sedimentation or "remember this preference" behavior.

## Planning Implications

- Plan granularity should be split by dependency and ownership:
  - docs/static semantic lock;
  - closed-case CWC projection service;
  - retrieval/review behavior;
  - final contract/validation cleanup.
- The first plan should explicitly inspect whether a trusted close hook exists. If none exists, the implementation should stop at a callable internal seam and tests.
- Every verification command must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- Red lines from Phase 44-46 remain active: no destructive memory table rename/drop, no `conversation_threads.case_id` changes, no CWC fallback from case/session memory, no ReAct/global `active_slots` writer.

## Tooling Note

During discuss, `UV_CACHE_DIR=/tmp/uv-cache uv run gsd-sdk query state.current` and `state.validate` were found to be unavailable in the installed SDK. Status validation should use `node /Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs state validate --raw` instead. This was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Result

Phase 47 is ready for `gsd-plan-phase 47`.
