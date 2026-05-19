---
phase: 06-evaluation-polish
plan: 01
subsystem: evaluation
tags: [golden-set, jsonl, rag, agent-eval, seed-validation]

requires:
  - phase: 03-langgraph-core
    provides: Agent golden set seed cases and graph intent/tool expectations
  - phase: 04-approval-workflow-audit
    provides: Approval and permission workflow behavior for safety cases
  - phase: 05-frontend-sse
    provides: Demo-facing trace and approval context
provides:
  - RAG golden set migrated to evaluation/golden/rag_cases.jsonl
  - Agent golden set expanded to 35 JSONL cases across 10 categories
  - Seed-reference validator for golden-set IDs and evidence doc keys
  - Chinese matching rules for deterministic eval routing
affects: [06-evaluation-polish, eval-agent, eval-rag, demo]

tech-stack:
  added: []
  patterns:
    - JSONL golden cases with explicit expected intent, tool, approval, permission, evidence, and response fields
    - Seed-reference validation before eval execution

key-files:
  created:
    - evaluation/golden/rag_cases.jsonl
    - evaluation/golden/agent_cases.jsonl
    - evaluation/golden/MATCHING_RULES.md
    - scripts/validate_golden_seeds.py
  modified: []

key-decisions:
  - "Kept runtime intent names while using Phase 6 category taxonomy: normal_policy_qa maps to policy_qa."
  - "Used actual seeded IDs from scripts/seed_demo.py, including ORD-2024-* and RF-2024-* prefixes."
  - "Used ASCII-only ID lookarounds for Chinese queries instead of Unicode word boundaries."

patterns-established:
  - "Golden agent cases include both expected_tools and expected_tools_called for compatibility with D-01e and existing eval naming."
  - "Only tool_failure_or_not_found cases may reference deliberately missing order/refund/ticket IDs."

requirements-completed: [EVAL-03, EVAL-04, EVAL-06]

duration: 8 min
completed: 2026-05-19
---

# Phase 6 Plan 01: Golden Set Foundation Summary

**Evaluation golden sets now live under `evaluation/golden/`, with 14 RAG cases, 35 agent cases, seed-reference validation, and documented Chinese matching rules.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-19T02:49:04Z
- **Completed:** 2026-05-19T02:57:56Z
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Migrated the existing 14-case RAG golden set byte-for-byte to `evaluation/golden/rag_cases.jsonl`.
- Expanded the agent golden set to 35 JSONL cases covering all 10 Phase 6 categories.
- Added seed ID validation for order, refund, ticket, policy doc, and demo user references.
- Documented Chinese intent, risk, approval, amount, seed ID, response matching, and FakeLLM routing rules.

## Task Commits

1. **Task 1: Migrate RAG golden set** - `1ff81e3` (feat)
2. **Task 2: Expand agent golden set** - `13217b6` (feat)
3. **Task 3: Validate golden set seed ID references** - `1742878` (fix)
4. **Task 4: Document Chinese normalization and matching rules** - `ca35d15` (docs)

## Files Created/Modified

- `evaluation/golden/rag_cases.jsonl` - Byte-identical migrated RAG JSONL golden set with 14 cases.
- `evaluation/golden/agent_cases.jsonl` - Expanded 35-case agent JSONL golden set with approval, permission, evidence, and response expectations.
- `scripts/validate_golden_seeds.py` - Validates golden-set IDs and evidence doc keys against deterministic seed data.
- `evaluation/golden/MATCHING_RULES.md` - Documents Chinese query normalization and deterministic matching rules.

## Verification

- `diff eval/golden_rag_queries.jsonl evaluation/golden/rag_cases.jsonl` - PASS
- `wc -l eval/golden_rag_queries.jsonl evaluation/golden/rag_cases.jsonl` - PASS, both files have 14 lines
- `uv run python -c "... rag JSONL validation ..."` - PASS, 14 RAG cases with required keys
- `uv run python -c "... agent schema/category validation ..."` - PASS, 35 agent cases across 10 categories
- `uv run python scripts/validate_golden_seeds.py` - PASS, seed validation passed
- `uv run ruff check scripts/validate_golden_seeds.py` - PASS
- `test -f evaluation/golden/MATCHING_RULES.md && grep ...` - PASS

## Decisions Made

- Kept the existing runtime `policy_qa` intent while using `normal_policy_qa` as the evaluation category.
- Matched the actual seed data prefixes in this repo (`ORD-2024-*`, `RF-2024-*`, `TK-2024-*`) rather than the generic plan examples.
- Used `uv run python` for all Python validation because `/opt/homebrew/bin/python` is currently linked to a missing Python 3.13 framework.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created seed validator during Task 2**
- **Found during:** Task 2 (Expand agent golden set)
- **Issue:** Task 2's verification command required `scripts/validate_golden_seeds.py`, but the plan did not create the script until Task 3.
- **Fix:** Added the initial validator in the Task 2 commit so Task 2 verification could run; Task 3 then hardened the validator.
- **Files modified:** `scripts/validate_golden_seeds.py`
- **Verification:** `uv run python scripts/validate_golden_seeds.py`
- **Committed in:** `13217b6`

**2. [Rule 1 - Bug] Fixed Chinese-adjacent seed ID extraction**
- **Found during:** Task 3 (Validate golden set seed ID references)
- **Issue:** A regex using Unicode word boundaries did not match IDs adjacent to Chinese characters.
- **Fix:** Replaced word boundaries with ASCII-only negative lookarounds and added a negative validation check.
- **Files modified:** `scripts/validate_golden_seeds.py`
- **Verification:** Negative validator check caught `ORD-NONEXIST-777` in a non-failure case; normal validation still passed.
- **Committed in:** `1742878`

---

**Total deviations:** 2 auto-fixed (1 Rule 3, 1 Rule 1)
**Impact on plan:** Both fixes were required for the planned verification to be meaningful. No scope expansion beyond the golden-set foundation.

## Issues Encountered

- Plan read-first path `src/moca/agent/nodes/classify_intent.py` does not exist in this repo. Used the actual path `src/agent/nodes/classify_intent.py`.
- System `python` executable is broken due a missing Homebrew Python 3.13 framework. Used `uv run python`, matching the project workflow.

## Known Stubs

None.

## Threat Flags

None. This plan added static evaluation data and local validation only; it introduced no network endpoints, auth paths, file access across trust boundaries, or schema changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 02 to build evaluation scripts against the new `evaluation/golden/` data layout and seed validator.

## Self-Check

PASSED - all created files exist on disk and all four task commits are present in `git log --all`.

---
*Phase: 06-evaluation-polish*
*Completed: 2026-05-19*
