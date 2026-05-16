---
phase: 04-approval-workflow-audit
plan: 06
subsystem: approval-workflow-validation
tags: [pytest, langgraph, approvals, interrupt-resume, risk-rules]

requires:
  - phase: 04-approval-workflow-audit
    provides: approval graph, approval REST API, trace/action draft persistence
provides:
  - MemorySaver-backed approval integration fixtures with deterministic LLM/search mocks
  - End-to-end approval workflow integration tests for approve, reject, low-risk, expiry, and idempotency
  - High-risk interception validation across HR-01, HR-02, and HR-03
affects: [approval-workflow-audit, evaluation, phase-4-validation]

tech-stack:
  added: []
  patterns:
    - Integration tests use real LangGraph MemorySaver interrupt/resume and mock external LLM/search calls only.
    - High-risk interception tests patch only the risk LLM and exercise deterministic rule overrides directly.

key-files:
  created:
    - tests/test_interrupt_contract_spike.py
    - tests/test_approval_integration.py
    - tests/test_interception_rate.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Approval integration fixtures use the existing manager approver role because the approval API currently authorizes admin and manager roles."
  - "The integration tests assert the current idempotency key produced by execute_action, including the empty target_id from existing read-tool context output."

patterns-established:
  - "Mock graph fixtures patch node-local _get_llm factories and retrieve_policy_evidence.search_policy, preserving real graph execution and CI isolation."
  - "Approval API integration tests validate persisted DB state after both the interrupt response and decision resume."

requirements-completed: []
requirements-addressed: [EVAL-05, EVAL-08, AGNT-02a, SAFE-02]

duration: 16min
completed: 2026-05-16
---

# Phase 4 Plan 6: Integration Tests and High-Risk Interception Summary

**MemorySaver-backed approval workflow tests now prove chat interruption, human decision resume, action draft creation, low-risk bypass, and 100% high-risk interception.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-05-16T12:23:26Z
- **Completed:** 2026-05-16T12:39:55Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added deterministic shared fixtures for a real compiled LangGraph graph with `MemorySaver`, fake structured LLM outputs, fake policy search, approval-capable users, and reusable high-risk state.
- Added a LangGraph interrupt contract spike proving invoke -> pause -> `Command(resume=...)` works in the installed LangGraph version.
- Added five end-to-end approval workflow tests covering approve execution, reject without action, low-risk no-approval completion, expired approvals, and idempotent approve without duplicate drafts.
- Added interception-rate tests for HR-01 compensation over 500 CNY, HR-02 full refund on delivered order, HR-03 high-risk merchant, three negative cases, and explicit 3/3 interception.

## Task Commits

Each task was committed atomically:

1. **Task 06-01: Create integration test fixtures** - `6124f36` (test)
2. **Task 06-02: End-to-end approval workflow integration test** - `b8ec093` (test)
3. **Task 06-03: High-risk interception rate validation** - `7b3f124` (test)

## Files Created/Modified

- `tests/conftest.py` - Adds approval manager test user, deterministic mock LLM/search fixtures, real MemorySaver graph fixture, and high-risk state fixture.
- `tests/test_interrupt_contract_spike.py` - Verifies the installed LangGraph interrupt/resume contract with a minimal graph.
- `tests/test_approval_integration.py` - Exercises the full chat -> interrupt -> decide -> resume -> final state workflow through FastAPI and the real graph.
- `tests/test_interception_rate.py` - Validates all high-risk rules and low-risk negative cases at the risk node and router boundary.

## Decisions Made

- Used `approval_manager` with role `manager` for approval decisions, matching the current approval API role contract from Plan 04-04.
- Kept external dependencies mocked at LLM/search boundaries only; graph execution, `interrupt()`, `Command(resume=...)`, API handlers, repositories, and database writes are real.
- Asserted the current action draft idempotency key with an empty target suffix because existing business context tool outputs do not include internal order/refund IDs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected deterministic fixture retrieval contract**
- **Found during:** Task 06-02 (End-to-end approval workflow integration test)
- **Issue:** The fake policy search initially returned `retrieval_status: "success"`, which violated the repository's `RetrievalResult` schema and caused graph invocation to fail.
- **Fix:** Changed the fixture to return `strong_evidence` and made recommendation branching prefer high-risk output when the query context contains `600`.
- **Files modified:** `tests/conftest.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_integration.py -q --tb=short` - 5 passed
- **Committed in:** `b8ec093`

### Plan Adaptations

**1. Approval user role follows current API contract**
- **Found during:** Task 06-01
- **Issue:** The plan requested a `supervisor` approval user, but Plan 04-04 intentionally authorizes `admin` and `manager` approver roles.
- **Adjustment:** Added an `approval_manager` fixture user with role `manager`, preserving the production authorization contract.
- **Files modified:** `tests/conftest.py`
- **Commit:** `6124f36`

**2. Interrupt spike lives in a collected test file**
- **Found during:** Task 06-01
- **Issue:** The plan listed the interrupt contract spike under `tests/conftest.py`, but tests in `conftest.py` are not collected as normal test cases.
- **Adjustment:** Added `tests/test_interrupt_contract_spike.py` so the spike is executed by pytest.
- **Files modified:** `tests/test_interrupt_contract_spike.py`
- **Commit:** `6124f36`

---

**Total deviations:** 1 auto-fixed blocking issue; 2 plan adaptations.
**Impact on plan:** The validation intent is preserved. No production code or new attack surface was added.

## Issues Encountered

- Sandbox networking blocks local PostgreSQL connections with `PermissionError: [Errno 1] Operation not permitted`; DB-backed pytest commands passed when rerun with approved local DB access.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_interrupt_contract_spike.py -q --tb=short` - 1 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_integration.py -q --tb=short` - 5 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_interception_rate.py -q --tb=short` - 8 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_integration.py tests/test_interception_rate.py -v` - 13 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v` - 164 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/` - passed

## Known Stubs

None.

## Threat Flags

None - plan changes are test-only and introduce no runtime endpoint, file access, auth, or schema surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 4 has final validation coverage for the approval workflow and high-risk interception. The approval workflow is ready for phase-level verification and UAT.

## Self-Check: PASSED

- Verified created/modified files exist: `tests/conftest.py`, `tests/test_interrupt_contract_spike.py`, `tests/test_approval_integration.py`, `tests/test_interception_rate.py`, and this summary.
- Verified task commits are reachable: `6124f36`, `b8ec093`, `7b3f124`.
- Verified no stub markers were found in the changed test files.

---
*Phase: 04-approval-workflow-audit*
*Completed: 2026-05-16*
