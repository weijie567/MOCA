---
phase: 06-evaluation-polish
plan: 02
subsystem: evaluation
tags: [rag-eval, agent-eval, json-report, markdown-report, makefile]

requires:
  - phase: 06-evaluation-polish
    plan: 01
    provides: Golden RAG and agent JSONL cases under evaluation/golden/
provides:
  - RAG evaluation script with JSON report output and 0.85 thresholds
  - Deterministic agent evaluation script with CI/live modes and D-03 scoring metrics
  - Unified evaluation orchestrator producing latest.json and latest.md
  - Makefile targets for eval, eval-rag, eval-agent, eval-live, and eval-baseline
affects: [06-evaluation-polish, ci, demo, evaluation]

tech-stack:
  added: []
  patterns:
    - Programmatic eval functions return report dictionaries for orchestration
    - JSON is the source of truth for Markdown report rendering
    - CI agent evaluation uses deterministic FakeLLM-compatible scoring without external API calls

key-files:
  created:
    - scripts/eval_rag.py
    - scripts/eval_agent.py
    - scripts/eval_all.py
    - evaluation/reports/.gitkeep
  modified:
    - Makefile

key-decisions:
  - "Kept RAG evaluation DB-backed to preserve production Retriever scoring behavior."
  - "Implemented agent CI mode as deterministic golden-case scoring with FakeLLM-compatible contracts and explicit trace-route assertions."
  - "Added Makefile .PHONY targets because an existing eval/ directory otherwise prevents make eval from running."

patterns-established:
  - "Eval scripts expose async run_*_eval functions and keep CLI sys.exit handling at the entrypoint."
  - "Unified Markdown reports are rendered from the JSON report object, never recomputed separately."

requirements-completed: [EVAL-03, EVAL-04, EVAL-06, EVAL-07, INFR-07]

duration: 9m 28s
completed: 2026-05-19
---

# Phase 6 Plan 02: Evaluation Scripts and Reports Summary

**RAG, agent, and unified evaluation scripts now produce structured JSON/Markdown reports with deterministic CI agent scoring and Makefile entrypoints.**

## Performance

- **Duration:** 9m 28s
- **Started:** 2026-05-19T03:09:17Z
- **Completed:** 2026-05-19T03:18:45Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added `scripts/eval_rag.py` with `run_rag_eval()`, default `evaluation/golden/rag_cases.jsonl`, JSON output, and 0.85 Hit@5/fallback thresholds.
- Added `scripts/eval_agent.py` with `run_agent_eval()`, CI/live modes, deterministic CI report generation, trace-route assertions, safety-critical scoring, and latency/token fields.
- Added `scripts/eval_all.py` to orchestrate both evaluations, write `evaluation/reports/latest.json`, render `latest.md` from JSON, support timestamped outputs, and compare/save baselines.
- Added Makefile targets for `eval`, `eval-rag`, `eval-agent`, `eval-live`, and `eval-baseline`.

## Task Commits

1. **Task 1: Refactor eval_rag.py with JSON report output** - `58fcf3f` (feat)
2. **Task 2: Create eval_agent.py with deterministic CI scoring** - `6c722e9` (feat)
3. **Task 3: Create eval_all.py orchestrator and Makefile targets** - `9d77a9c` (feat)

## Files Created/Modified

- `scripts/eval_rag.py` - DB-backed RAG Hit@5/fallback evaluation with JSON report output and programmatic `run_rag_eval()`.
- `scripts/eval_agent.py` - Deterministic agent golden-set evaluator with CI/live modes, route assertions, and D-03 metrics.
- `scripts/eval_all.py` - Unified report orchestrator for latest JSON/Markdown, timestamped reports, and baseline comparison.
- `evaluation/reports/.gitkeep` - Tracks the reports directory in git.
- `Makefile` - Adds eval targets and `.PHONY` declarations so `make eval` invokes the script despite the existing `eval/` directory.

## Verification

- `uv run python -c "import ast; [ast.parse(open(p).read()) for p in ('scripts/eval_rag.py','scripts/eval_agent.py','scripts/eval_all.py')]; print('all syntax OK')"` - PASS
- `uv run python -c "import scripts.eval_rag, scripts.eval_agent, scripts.eval_all; print('imports OK')"` - PASS, with a non-blocking LangGraph deprecation warning from dependency import
- `uv run ruff check scripts/eval_rag.py scripts/eval_agent.py scripts/eval_all.py` - PASS
- `uv run python scripts/eval_agent.py --output /tmp/moca_agent_eval_final.json` - PASS, 35/35 deterministic CI cases passed
- `make -n eval eval-rag eval-agent eval-live eval-baseline` - PASS, all targets print the expected `uv run python ...` commands
- `test -f evaluation/reports/.gitkeep` - PASS
- `rg -n "(sk-[A-Za-z0-9]|AKIA[0-9A-Z]{16}|BEGIN PRIVATE KEY|password\\s*=|token\\s*=)" scripts/eval_rag.py scripts/eval_agent.py scripts/eval_all.py || true` - PASS, no credential literals found

`uv run python scripts/eval_all.py` was not executed end-to-end because the RAG evaluator intentionally requires a running seeded PostgreSQL/pgvector environment. The orchestrator was verified by syntax/import checks, schema markers, Makefile dry-run, and Markdown rendering from synthetic JSON data.

## Decisions Made

- Preserved the RAG evaluator's production DB/retriever path instead of replacing it with a mock, so Hit@5 remains comparable to prior live Phase 2 scoring.
- Kept CI agent evaluation deterministic and API-free while reporting `run_mode: ci_deterministic`, `average_latency_ms: null`, and token count `0`.
- Added `.PHONY` to all Makefile targets because `eval/` already exists and would otherwise make `make eval` a no-op.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Makefile eval target collision**
- **Found during:** Task 3 (Create eval_all.py orchestrator and Makefile targets)
- **Issue:** `make -n eval` reported `make: 'eval' is up to date` because the repository already has an `eval/` directory.
- **Fix:** Added `.PHONY: up down migrate seed test lint format dev eval eval-rag eval-agent eval-live eval-baseline`.
- **Files modified:** `Makefile`
- **Verification:** `make -n eval eval-rag eval-agent eval-live eval-baseline`
- **Committed in:** `9d77a9c`

---

**Total deviations:** 1 auto-fixed (1 Rule 1)
**Impact on plan:** The fix was required for the planned `make eval` target to actually execute. No scope expansion.

## Issues Encountered

- Importing the eval modules emits a LangGraph dependency deprecation warning about serializer `allowed_objects`; this is upstream noise and does not affect import success.
- `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, and several phase planning files were already modified before this run. To preserve unrelated work, the final metadata commit for this plan is scoped to this new summary file only.

## Known Stubs

None. Stub scan hits were type annotations or local accumulator initializers, not user-visible placeholder data.

## Threat Flags

None beyond the planned local evaluation surfaces. This plan added local JSONL parsing and report file writing only; it introduced no network endpoints, auth paths, schema changes, or credential output.

## User Setup Required

None - no external service configuration required for CI-mode agent evaluation. End-to-end RAG evaluation still requires the existing seeded Postgres/pgvector environment.

## Next Phase Readiness

Ready for Plan 03 to wire evaluation into CI and polish documentation against the report schema and Makefile targets from this plan.

## Self-Check

PASSED - all created files exist on disk, all three task commits are present in `git log --all`, no tracked deletions were introduced, and unrelated pre-existing planning modifications remain unstaged.

---
*Phase: 06-evaluation-polish*
*Completed: 2026-05-19*
