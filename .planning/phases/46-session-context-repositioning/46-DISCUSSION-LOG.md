# Phase 46: Session Context Repositioning - Discussion Log

> Audit trail only. Do not use as input to planning, research, or execution agents.
> Decisions are captured in `46-CONTEXT.md`; this log preserves the alternatives considered.

**Date:** 2026-07-03
**Phase:** 46-session-context-repositioning
**Areas discussed:** scope shape, table identity, allowed session contents, authority boundary, CWC separation, reviewed precedent separation, long-term preference separation, verification entrypoint

---

## Scope Shape

| Option | Description | Selected |
| --- | --- | --- |
| Boundary lock with audit-driven narrowing | Make the session/CWC/case/long-term boundary explicit through docs/tests; only narrow code if the audit proves a current violation. | Yes |
| Full session memory redesign | Rewrite session memory storage and lifecycle as part of Phase 46. |  |
| Docs-only no audit | Only edit prose and leave existing behavior untested. |  |

**Decision:** Use boundary lock with audit-driven narrowing.
**Notes:** MEM-03 asks for repositioning after CWC, not a new storage layer. Current code already keeps `session_memories` tenant/user/thread scoped.

---

## Table Identity

| Option | Description | Selected |
| --- | --- | --- |
| Preserve `session_memories` | Keep the existing table name and tenant/user/thread identity; no migration unless planning proves a concrete defect. | Yes |
| Add a `case_id` column | Make session memory case-scoped by schema. |  |
| Rename/drop session memory | Replace `session_memories` with a new table. |  |

**Decision:** Preserve `session_memories`.
**Notes:** Phase 44 created CWC for case-scoped durable state. Adding case scope to session memory would blur the new boundary and risk duplicating CWC.

---

## Allowed Session Contents

| Option | Description | Selected |
| --- | --- | --- |
| Short-lived same-thread continuity | Keep slots, last intent, lightweight summary, unresolved questions, prompt-safe recent context, and refs/hints. | Yes |
| Remove all refs/hints | Strip policy/business refs even when they are prompt-safe contextual hints. |  |
| Expand to durable case state | Let session memory carry current case working state across threads. |  |

**Decision:** Keep short-lived same-thread continuity.
**Notes:** The useful prompt hints are not the problem; authority confusion is. Phase 46 should label and test the boundary rather than deleting useful non-authoritative context.

---

## Authority Boundary

| Option | Description | Selected |
| --- | --- | --- |
| Contextual-only hints | Session refs/hints may guide the prompt but cannot satisfy evidence, business fact, approval, action, or replay requirements. | Yes |
| Promote session refs to authority | Treat session refs as policy evidence or business-system truth. |  |
| Treat persistence as long-term authority | Treat any persisted session content as durable long-term memory. |  |

**Decision:** Contextual-only hints.
**Notes:** This follows the existing memory contract: memory is assistance context, not source-of-truth.

---

## CWC Separation

| Option | Description | Selected |
| --- | --- | --- |
| Separate CWC lifecycle | CWC remains loaded/written through Phase 45 lifecycle and canonical case resolution; session memory cannot backfill CWC. | Yes |
| Session fallback for missing CWC | If no active CWC exists, infer or synthesize it from session memory. |  |
| Move CWC into session memory | Store CWC fields in the session table. |  |

**Decision:** Separate CWC lifecycle.
**Notes:** Active current-case state belongs to `case_working_contexts`, not `session_memories`.

---

## Reviewed Precedent Separation

| Option | Description | Selected |
| --- | --- | --- |
| Reviewed store only | `search_case_memory` remains backed by reviewed `case_memories` / `CaseMemoryService`. | Yes |
| Session-derived precedent | Use `session_memories` as the planner-facing historical precedent store. |  |
| Generate precedents in Phase 46 | Add closed-case candidate generation now. |  |

**Decision:** Reviewed store only.
**Notes:** Code scout confirmed `MemoryToolExecutor` already uses `CaseMemoryService`; `LegacySessionPrecedentSearchService` is legacy/debug-only and must stay non-planner-facing.

---

## Long-Term Preference Separation

| Option | Description | Selected |
| --- | --- | --- |
| Defer explicit preference memory | Do not add durable preference writes in Phase 46; keep them for Phase 48. | Yes |
| Auto-extract preferences from all runs | Infer long-term preferences from ordinary conversations. |  |
| Store preferences in session summary | Put merchant/team preferences into `session_summary`. |  |

**Decision:** Defer explicit preference memory.
**Notes:** Long-term memory is already scoped in `.planning/MEMORY-REDESIGN-DECISIONS.md` as narrow explicit preferences, not automatic sedimentation.

---

## ReAct / Slot Feedback Boundary

| Option | Description | Selected |
| --- | --- | --- |
| Keep loop-local decision | Reuse GAD-01 option A: future investigation observations stay loop-local and do not become a new global `active_slots` writer. | Yes |
| Add discovered slot writer | Let `investigate` write a new slot surface during Phase 46. |  |

**Decision:** Keep loop-local decision.
**Notes:** Phase 46 should not reopen ReAct architecture. It only protects the memory boundary.

---

## Verification Entrypoint

| Option | Description | Selected |
| --- | --- | --- |
| MOCA uv pytest entrypoint | Every Phase 46 automated test command starts with `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. | Yes |
| Bare pytest acceptable | Allow `pytest` / `python -m pytest`. |  |

**Decision:** MOCA uv pytest entrypoint.
**Notes:** This is a project-level hard rule from `AGENTS.md`.

---

## Planner's Discretion

- Exact plan split.
- Whether the first plan is docs/static-tests only or includes small code narrowing after audit.
- Exact wording of the `docs/contract-spec.md` delta.
- Exact location of Phase 46 alignment tests.
- Whether legacy session-derived precedent tests remain in place with stronger non-production assertions.

## Deferred Ideas

- Phase 47: reviewed case precedent repositioning and closed-case candidate generation.
- Phase 48: narrow explicit tenant preference memory.
- Future graph phase: investigate ReAct implementation.
