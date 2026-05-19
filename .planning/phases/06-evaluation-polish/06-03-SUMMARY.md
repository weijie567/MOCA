---
phase: 06-evaluation-polish
plan: 03
subsystem: infra
tags: [ci, github-actions, demo, readme, documentation]

requires:
  - phase: 06-evaluation-polish
    plan: 02
    provides: Evaluation scripts, report paths, and Makefile eval targets
provides:
  - GitHub Actions CI workflow for lint and unit tests
  - Reproducible curl-based Phase 6 demo script
  - Interview-ready README with architecture diagrams and evaluation overview
affects: [06-evaluation-polish, ci, demo, docs]

tech-stack:
  added: []
  patterns:
    - GitHub Actions uses uv with separate lint and test jobs
    - Demo script uses structured curl output and local demo credentials only
    - README acts as overview layer linking to deeper docs planned in 06-04

key-files:
  created:
    - .github/workflows/ci.yml
    - scripts/demo_phase6.sh
    - .planning/phases/06-evaluation-polish/06-03-SUMMARY.md
  modified:
    - README.md
    - scripts/*.py and src/tests Python files formatted by Ruff for the new CI gate

key-decisions:
  - "Kept CI limited to Ruff lint/format and unit tests; eval scripts remain local-only per D-07b."
  - "Implemented the demo script against actual repo API paths and response wrappers rather than stale plan paths."
  - "Linked README to docs files owned by Plan 06-04 instead of creating those files in Plan 06-03."

patterns-established:
  - "Plan-level overview docs may link forward to next-plan depth docs when the next plan explicitly owns those files."
  - "Demo scripts should parse the ApiResponse data wrapper instead of assuming raw agent fields."

requirements-completed: [INFR-08]

duration: 1h 57m
completed: 2026-05-19
---

# Phase 6 Plan 03: CI, Demo Script, and README Summary

**GitHub Actions CI, a seven-scenario curl demo, and an interview-ready README now anchor the Phase 6 delivery surface.**

## Performance

- **Duration:** 1h 57m
- **Started:** 2026-05-19T03:22:00Z
- **Completed:** 2026-05-19T05:19:25Z
- **Tasks:** 3
- **Files modified:** 4 plan files plus 24 Ruff-format-only Python files

## Accomplishments

- Added `.github/workflows/ci.yml` with separate `lint` and `test` jobs using `astral-sh/setup-uv@v4`.
- Added executable `scripts/demo_phase6.sh` covering auth, policy QA, refund troubleshooting, approval interruption, permission denial, rejection, and trace query.
- Rewrote `README.md` with project overview, capabilities, two Mermaid diagrams, demo instructions, evaluation summary, quick start, repository structure, technical links, and scope limits.

## Task Commits

1. **Task 1: Create GitHub Actions CI workflow** - `9a1d813` (feat)
2. **Task 2: Create demo execution shell script** - `8f527b5` (feat)
3. **Task 3: Rewrite README.md as interview-ready project showcase** - `11742ff` (docs)
4. **Plan-level CI readiness: Ruff format gate** - `8c8226e` (style)

## Files Created/Modified

- `.github/workflows/ci.yml` - GitHub Actions workflow with Ruff lint/format and pytest unit-test jobs.
- `scripts/demo_phase6.sh` - Executable seven-scenario curl demo with preflight checks and formatted output.
- `README.md` - Interview-ready project overview with architecture diagrams, demo commands, evaluation summary, and technical links.
- `.planning/phases/06-evaluation-polish/06-03-SUMMARY.md` - This execution summary.

## Verification

- `ruby -e "require 'yaml'; YAML.load_file('.github/workflows/ci.yml'); puts 'valid YAML'"` - PASS.
- `test -f .github/workflows/ci.yml && grep -q "uv run ruff check" ... && grep -q "uv run pytest" ...` - PASS.
- `rg -n "secret|API_KEY|eval_|eval-|scripts/eval|make eval" .github/workflows/ci.yml || true` - PASS, no output.
- `test -f scripts/demo_phase6.sh && test -x scripts/demo_phase6.sh && bash -n scripts/demo_phase6.sh` - PASS.
- `grep -c "Scenario" scripts/demo_phase6.sh | grep -q "[67]"` - PASS, 7 scenario markers.
- `grep -c '^```mermaid' README.md` - PASS, 2 Mermaid diagrams.
- README section/link grep for Project Overview, Key Capabilities, Quick Start, Repository Structure, Evaluation Summary, `demo-walkthrough`, and `architecture.md` - PASS.
- `rg -n "[emoji ranges]" README.md || true` - PASS, no emoji hits.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .` - initially FAIL on 24 pre-existing Python files; `uv run ruff format .` was run and committed as `8c8226e`; rerun PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -x --ignore=tests/integration -q --tb=short` - sandbox run stopped at 34 passed with `PermissionError: Operation not permitted` connecting to local Postgres; full pytest remains pending outside the sandbox.

## Decisions Made

- Used direct `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest ...` commands in CI to satisfy the plan markers and provide clear failure signals.
- Implemented the demo script against actual package paths and response shapes: `src/api/routers/*`, `ApiResponse.data`, `data.trace_summary`, `data.approval_id`, and `GET /api/v1/agent-runs/{run_id}/trace`.
- Left README links to `docs/demo-walkthrough.md`, `docs/evaluation.md`, `docs/architecture.md`, and `docs/security-and-permission.md` because Plan 06-04 explicitly owns those files.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used actual API package paths for demo script grounding**
- **Found during:** Task 2 (Create demo execution shell script)
- **Issue:** Plan read-first paths used `src/moca/api/routes/*`, but the repo uses `src/api/routers/*`.
- **Fix:** Read the actual router/schema files and implemented the script against the live endpoint contracts.
- **Files modified:** `scripts/demo_phase6.sh`
- **Verification:** `bash -n scripts/demo_phase6.sh`; endpoint and scenario greps passed.
- **Committed in:** `8f527b5`

**2. [Rule 1 - Bug] Corrected trace endpoint and response parsing in demo script**
- **Found during:** Task 2 (Create demo execution shell script)
- **Issue:** The plan showed `GET /api/v1/agent-runs` and raw response fields, but the implemented API exposes `GET /api/v1/agent-runs/{run_id}/trace` and wraps chat data under `data`.
- **Fix:** Captured `data.run_id` / `data.trace_summary.run_id`, used `data.approval_id`, and queried the trace endpoint by run ID.
- **Files modified:** `scripts/demo_phase6.sh`
- **Verification:** `rg -n "api/v1/agent-runs" scripts/demo_phase6.sh`; `bash -n scripts/demo_phase6.sh`.
- **Committed in:** `8f527b5`

**3. [Rule 3 - Blocking] Ruff format drift exposed by new CI gate**
- **Found during:** Plan-level verification
- **Issue:** The new CI workflow includes `uv run ruff format --check .`; the current working tree had 24 Python files that Ruff would reformat.
- **Fix:** Ran `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format .`, committed the mechanical formatting, and made `ruff format --check .` pass.
- **Files modified:** 24 source/test/script files, committed as a mechanical formatting fix.
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run ruff format --check .` - PASS after formatting.
- **Committed in:** `8c8226e`

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 2 Rule 3)
**Impact on plan:** All fixes support the planned CI/demo/readme deliverables. The Ruff formatting commit is broad but mechanical and required by the new CI gate.

## Issues Encountered

- Bare `python` is broken on this machine due a missing Homebrew Python 3.13 framework. YAML verification used Ruby instead.
- `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short` required local Postgres access. The sandboxed run failed with `PermissionError: Operation not permitted` after 34 tests passed.
- Pre-existing unrelated planning files were already modified or untracked before this execution and were not staged or committed.

## Known Stubs

None in the committed 06-03 outputs. README links to docs files that are planned deliverables of 06-04, not placeholder implementation stubs in this plan.

## Threat Flags

None beyond the planned surfaces. The CI workflow references no secrets or eval scripts, and the demo script uses only localhost defaults plus public demo credentials.

## User Setup Required

None for the committed artifacts. Running the full demo still requires the normal local stack and seeded data.

## Next Phase Readiness

Plan 06-04 can create the four README-linked docs files. Before final phase verification, rerun the CI-equivalent pytest command with local Postgres access.

## Self-Check

PASSED - committed task outputs exist, task commits are present in `git log`, Ruff check/format gates pass, and no 06-03 source changes remain unstaged.

---
*Phase: 06-evaluation-polish*
*Completed: 2026-05-19*
