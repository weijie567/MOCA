---
phase: 16-long-term-case-memory
plan: 07
subsystem: agent-context
tags: [context-assembler, prompt-safety, long-term-memory, case-memory, tdd]

requires:
  - phase: 16-03-long-term-memory-service
    provides: reviewed LongTermMemoryView profile memory retrieval views
  - phase: 16-06-reviewed-case-memory
    provides: prompt-safe CaseMemorySearchItem precedent views
provides:
  - Bounded non-protected profile_memory and case_memory prompt blocks
  - Prompt-safe memory projectors with safe refs and raw payload/hash/authority exclusions
  - ContextAssembler memory parameters for reviewed profile and case snippets
  - TDD coverage for memory caps, leakage exclusions, and protected authority preservation
affects: [16-08-memory-retrieval-integration, 16-09-legacy-search-eval-closure, ContextAssembler]

tech-stack:
  added: []
  patterns:
    - Explicit allowlist projection for memory prompt refs
    - Non-protected memory blocks below protected policy/business/current-user authority
    - Combined memory prompt hard cap before prompt block construction

key-files:
  created: []
  modified:
    - src/agent/context/__init__.py
    - src/agent/context/assembler.py
    - src/agent/context/budget.py
    - src/agent/context/projectors.py
    - tests/agent/context/test_assembler.py

key-decisions:
  - "Memory prompt blocks remain non-protected; profile_memory and case_memory are added to BlockName but not PROTECTED_BLOCK_NAMES."
  - "ContextAssembler caps combined profile/case memory prompt text at 1600 chars before adding prompt blocks."
  - "Case memory prompt refs prioritize compact source and policy identifiers, including business_object_id, while excluding EvidenceRefV1, hashes, raw payloads, and authority bodies."

patterns-established:
  - "Memory projectors accept mapping or Pydantic model inputs through prompt-safe projection, not repository or ORM objects."
  - "Profile memory is limited to three compact content items; case memory is limited to three compact precedent items."
  - "Prompt order keeps protected policy refs before memory, then profile_memory, case_memory, recent_messages, and current_user_message."

requirements-completed:
  - MEMCTX-01
  - MEMCTX-02
  - LONGMEM-02
  - CASEMEM-02
  - MEMEVAL-01

duration: 6 min
completed: 2026-06-18
---

# Phase 16 Plan 07: ContextAssembler Memory Blocks Summary

**Bounded prompt-safe profile and case memory blocks in ContextAssembler without raw payload, hash, or authority leakage**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-17T16:57:09Z
- **Completed:** 2026-06-17T17:03:32Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added failing TDD coverage for bounded profile/case memory prompt blocks, 3-item caps, the 1600-char combined memory cap, forbidden raw/authority/hash strings, and protected block preservation.
- Added `profile_memory` and `case_memory` prompt block names while keeping them outside `PROTECTED_BLOCK_NAMES`.
- Implemented `project_profile_memory_for_prompt(...)` and `project_case_memory_for_prompt(...)` with allowlisted compact refs and bounded fields.
- Wired `ContextAssembler.assemble(...)` to accept reviewed memory snippets and place memory below protected policy/business/current-user authority.

## Task Commits

1. **Task 16-07-01: Add memory prompt projection tests** - `8a79ed4` (test)
2. **Task 16-07-02: Implement memory prompt projectors** - `f0138c5` (feat)
3. **Task 16-07-03: Wire memory blocks into ContextAssembler** - `3cc0d4c` (feat)

## Files Created/Modified

- `src/agent/context/budget.py` - Adds `profile_memory` and `case_memory` as recognized prompt block names without making them protected.
- `src/agent/context/projectors.py` - Adds bounded profile/case memory prompt projectors, memory-safe ref formatting, and forbidden marker/hash filtering.
- `src/agent/context/assembler.py` - Adds memory snippet parameters, 1600-char combined memory cap, non-protected memory blocks, and final prompt ordering.
- `src/agent/context/__init__.py` - Exports the memory projectors from the context boundary.
- `tests/agent/context/test_assembler.py` - Covers bounded memory injection, raw/authority/hash exclusion, protected block preservation, and projector exports.

## Decisions Made

- Memory blocks are context only: they are lower-priority, non-protected blocks and cannot preserve themselves ahead of protected policy, business IDs, safety, system prompt, or current user message.
- Case memory prompt refs use compact source/policy identifiers, not `EvidenceRefV1` or full policy text. `business_object_id` is prioritized so traceability survives tight ref caps.
- The assembler enforces the combined profile/case 1600-char cap before prompt budgeting, so memory cannot consume the broader prompt budget unexpectedly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Applied minimal assembler plumbing with projector implementation**
- **Found during:** Task 16-07-02 (Implement memory prompt projectors)
- **Issue:** The task acceptance required `uv run pytest tests/agent/context/test_assembler.py -q` to pass, but the RED tests necessarily called `ContextAssembler.assemble(profile_memory_snippets=..., case_memory_snippets=...)`. Projectors alone could not satisfy the task gate.
- **Fix:** Added the memory parameters and minimal non-protected block plumbing alongside the projectors, then completed exact prompt ordering in Task 16-07-03.
- **Files modified:** `src/agent/context/assembler.py`, `src/agent/context/projectors.py`, `src/agent/context/budget.py`, `src/agent/context/__init__.py`
- **Verification:** `uv run pytest tests/agent/context/test_assembler.py -q`
- **Committed in:** `f0138c5`, refined in `3cc0d4c`

**2. [Rule 1 - Bug] Preserved case memory business object traceability under ref caps**
- **Found during:** Task 16-07-02 (Implement memory prompt projectors)
- **Issue:** The first safe-ref cap preserved `source_type` and event-style fields before `business_object_id`, so tight projection could drop the most useful case traceability ref.
- **Fix:** Reordered memory source ref allowlist priority and used a bounded 120-char cap for case memory `source_refs`, while retaining the 1600-char combined memory cap.
- **Files modified:** `src/agent/context/projectors.py`
- **Verification:** `uv run pytest tests/agent/context/test_assembler.py -q`
- **Committed in:** `f0138c5`

---

**Total deviations:** 2 auto-fixed (1 blocking sequencing issue, 1 bug)
**Impact on plan:** Both fixes preserve the planned contract. No extra architecture, storage, endpoint, or repository surface was introduced.

## Issues Encountered

None. All planned verification commands passed. Pytest emitted only the existing LangGraph serializer deprecation warning.

## Known Stubs

None. Stub scan found only existing typed empty-list/string initializers and tests for empty inputs; no UI-facing or behavior-blocking stubs were introduced.

## TDD Gate Compliance

- **RED:** `8a79ed4` added failing memory prompt tests. Initial failure was `TypeError: ContextAssembler.assemble() got an unexpected keyword argument 'profile_memory_snippets'`.
- **GREEN:** `f0138c5` implemented prompt-safe memory projectors plus minimal assembler plumbing and made the focused test pass.
- **Refinement:** `3cc0d4c` finalized prompt ordering and exporter assertions while keeping tests green.

## Verification

- `uv run pytest tests/agent/context/test_assembler.py -q` — passed, 6 tests.
- `uv run ruff check src/agent/context tests/agent/context` — passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `16-08-memory-retrieval-integration-PLAN.md`. `ContextAssembler` now has bounded prompt-safe memory inputs that downstream retrieval wiring can pass through without making memory into policy evidence, current business truth, approval authority, action authority, or replay/audit truth.

---
*Phase: 16-long-term-case-memory*
*Completed: 2026-06-18*

## Self-Check: PASSED

- Found key files: `src/agent/context/__init__.py`, `src/agent/context/assembler.py`, `src/agent/context/budget.py`, `src/agent/context/projectors.py`, `tests/agent/context/test_assembler.py`.
- Found task commits: `8a79ed4`, `f0138c5`, `3cc0d4c`.
