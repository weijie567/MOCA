---
phase: 13-approval-state-machine
verified: 2026-06-15T12:24:32Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
must_haves:
  truths:
    - "Single-level runtime transition, CAS, revision invalidation, and needs_info resume tests pass."
    - "Action payload and safety snapshot hashes bind approval to the exact revision."
    - "Multi-level-compatible schema/contracts are verified; active SLA scanner remains an owned follow-up gate."
    - "CanonicalHashProfile v1 and ActionSafetySnapshot canonical/golden contracts are implemented and shared."
    - "Approval v2 schema, migration, and legacy non-executable handling exist with migration report."
    - "ApprovalService owns transitions and validates request, level, assignment, revision, tenant, actor, and hash binding."
    - "API, chat/SSE, and graph paths are cut over to ApprovalService and trusted approval_result.v1 payloads."
    - "respond, attach_info, and edit implement needs_info/supersede semantics without old-revision execution."
    - "Approval events are registered on the minimal envelope and carry safe refs only."
    - "SLA scanner exists but is disabled by default, with Phase 15 owning active enablement."
    - "Legacy approval transition paths are deleted/quarantined and protected by boundary tests."
    - "Coverage, eval manifest, schema drift, ruff, and pytest gates are documented or verified."
  artifacts:
    - path: "src/common/canonical_hash.py"
      provides: "CanonicalHashProfile v1"
    - path: "src/approvals/snapshots.py"
      provides: "ActionSafetySnapshot contract and immutable hash projection"
    - path: "src/db/models.py"
      provides: "Approval v2 ORM tables and fields"
    - path: "src/db/migrations/versions/008_approval_state_machine.py"
      provides: "Approval state machine schema migration"
    - path: "src/approvals/service.py"
      provides: "ApprovalService state machine"
    - path: "src/approvals/repository.py"
      provides: "Approval persistence locks, inserts, and CAS helpers"
    - path: "src/approvals/events.py"
      provides: "Approval minimal-event helpers"
    - path: "src/approvals/sla_scanner.py"
      provides: "Feature-disabled SLA scanner"
    - path: "src/api/routers/approvals.py"
      provides: "Trusted approval decision API adapter"
    - path: "src/api/routers/agent_runs.py"
      provides: "Service-backed streaming approval interrupt creation"
    - path: "src/agent/graph.py"
      provides: "Trusted approval result routing"
    - path: "tests/approvals"
      provides: "Focused approval contract and state-machine tests"
    - path: "tests/architecture/test_approval_boundaries.py"
      provides: "Approval ownership boundary tests"
    - path: ".planning/phases/13-approval-state-machine/13-COVERAGE.md"
      provides: "Requirement coverage, deferred owners, and final gate record"
    - path: "tests/approvals/phase13_eval_manifest.json"
      provides: "Blocking approval-contract eval metadata"
  key_links:
    - from: "src/api/routers/approvals.py"
      to: "src/approvals/service.py"
      via: "ApprovalDecisionCommand and ApprovalService.decide"
    - from: "src/api/routers/agent_runs.py"
      to: "src/approvals/service.py"
      via: "ApprovalRequestCreateCommand and ApprovalService.create_request"
    - from: "src/approvals/service.py"
      to: "src/approvals/repository.py"
      via: "lock_request, lock_current_level, lock_assignment, insert_decision, insert_approval_event"
    - from: "src/approvals/service.py"
      to: "src/approvals/snapshot_service.py"
      via: "persist_action_safety_snapshot"
    - from: "src/approvals/service.py"
      to: "src/approvals/events.py"
      via: "emit_approval_requested, emit_approval_decided, emit_approval_expired"
    - from: "src/agent/graph.py"
      to: "src/agent/nodes/execute_action.py"
      via: "route_after_approval only accepts trusted approval_result.v1 with exact binding"
deferred:
  - truth: "Active SLA scanner scheduling"
    addressed_in: "Phase 15"
    evidence: "13-COVERAGE P13-FU-05 and roadmap Phase 15 replay/allocator ownership"
  - truth: "Durable draft-only demo action executor boundary"
    addressed_in: "Phase 14"
    evidence: "13-COVERAGE P13-FU-08 and roadmap Phase 14 success criteria"
  - truth: "ReplayEventV3 enrichment and replay read switch"
    addressed_in: "Phase 15"
    evidence: "13-COVERAGE P13-FU-09 and roadmap Phase 15 goal"
  - truth: "External execution/outbox/reconciliation/compensation"
    addressed_in: "Phase 17"
    evidence: "13-COVERAGE P13-FU-11 and roadmap Phase 17 goal"
---

# Phase 13: Approval State Machine Verification Report

**Phase Goal:** Implement versioned approval requests/levels/assignments/decisions/events and the canonical ActionSafetySnapshot.  
**Verified:** 2026-06-15T12:24:32Z  
**Status:** passed  
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Single-level runtime transition, CAS, revision invalidation, and needs_info resume tests pass. | VERIFIED | `ApprovalService.decide` locks request, level, and assignment, validates expected versions/revision, and dispatches transition handlers (`src/approvals/service.py:168`, `src/approvals/service.py:179`, `src/approvals/service.py:186`, `src/approvals/service.py:194`). Tests cover stale request/level/assignment/revision, wrong tenant/run/thread/binding, self-approval, and no orphan rows (`tests/approvals/test_service_transitions.py:288`). Single-level runtime tests use one level/assignment and approve only after assignment accept (`tests/approvals/test_single_level_runtime.py:21`). |
| 2 | Action payload and safety snapshot hashes bind approval to the exact revision. | VERIFIED | `ApprovalService` verifies executable v2 rows, snapshot row existence, and exact action/snapshot hashes before decisions (`src/approvals/service.py:836`, `src/approvals/service.py:855`, `src/approvals/service.py:864`). Hash mismatch and changed snapshot material fail closed in `tests/approvals/test_hash_binding.py:70` and `tests/approvals/test_hash_binding.py:106`. Graph and action guards require `approval_result.v1` plus revision/version/hash fields (`src/agent/graph.py:65`, `src/agent/nodes/execute_action.py:85`). |
| 3 | Multi-level-compatible schema/contracts are verified; active SLA scanner remains an owned follow-up gate. | VERIFIED | Models and migration define request/level/assignment/decision/event tables, `any_one`/`all` modes, redundant version fields, partial uniques, and status checks (`src/db/models.py:379`, `src/db/models.py:451`). Contract tests verify multi-level metadata (`tests/approvals/test_multi_level_contract.py:38`). Scanner defaults disabled in config/env (`src/config.py:35`, `.env.example:19`) and coverage defers active enablement to Phase 15. |
| 4 | CanonicalHashProfile v1 and ActionSafetySnapshot canonical/golden contracts are implemented and shared. | VERIFIED | `HASH_PROFILE_VERSION`, canonical JSON validation, exact hash input bytes, and `sha256:` digest are centralized in `src/common/canonical_hash.py:12` and `src/common/canonical_hash.py:56`. `ActionSafetySnapshot` imports `EvidenceRefV1` and `canonical_evidence_projection`, strips `score`, retains `rank`, and computes immutable hash from canonical projection (`src/approvals/snapshots.py:11`, `src/approvals/snapshots.py:75`). |
| 5 | Approval v2 schema, migration, and legacy non-executable handling exist with migration report. | VERIFIED | ORM and migration add `action_safety_snapshots`, v2 request fields, levels, assignments, decisions, and events (`src/db/models.py:279`, `src/db/models.py:310`, `src/db/migrations/versions/008_approval_state_machine.py:49`). Legacy backfill uses row-number revisions and marks old rows non-executable; migration tests verify source and constraints (`tests/approvals/test_migration_contract.py:203`). Migration report records current/head, fallback, rollback, and verification commands. |
| 6 | ApprovalService owns transitions and validates request, level, assignment, revision, tenant, actor, and hash binding. | VERIFIED | API and graph code call `ApprovalService`; repository locks and CAS helpers live under `src/approvals` (`src/approvals/repository.py:35`, `src/approvals/repository.py:241`). The old `src/repositories/approval_repo.py` file is absent and boundary tests forbid reintroduction (`tests/architecture/test_approval_boundaries.py:33`). |
| 7 | API, chat/SSE, and graph paths are cut over to ApprovalService and trusted approval_result.v1 payloads. | VERIFIED | Decision API constructs `ApprovalDecisionCommand` from authenticated server-side user/tenant context and resumes only with service `resume_payload` (`src/api/routers/approvals.py:53`, `src/api/routers/approvals.py:124`). Streaming interrupts create wait payloads through `ApprovalService.create_request` and include revision/version/hash fields plus all allowed decision types (`src/api/routers/agent_runs.py:436`). `approval_gate` rejects non-`approval_result.v1` resumes (`src/agent/nodes/approval_gate.py:53`). |
| 8 | respond, attach_info, and edit implement needs_info/supersede semantics without old-revision execution. | VERIFIED | `respond` writes `needs_info` and returns no resume payload (`src/approvals/service.py:379`). `attach_info` validates clarification id, tenant/thread, versions, and changed material before same-revision revalidation or supersede (`src/approvals/service.py:227`, `src/approvals/service.py:268`). `edit` creates a replacement revision and reroutes to risk validation (`src/approvals/service.py:428`). Tests cover wrong scope, stale versions, single active revision, old revision cannot execute, and replay-linked supersede events (`tests/approvals/test_needs_info_resume.py:135`, `tests/approvals/test_needs_info_resume.py:256`, `tests/approvals/test_needs_info_resume.py:315`). |
| 9 | Approval events are registered on the minimal envelope and carry safe refs only. | VERIFIED | Minimal event types include `approval_requested`, `approval_decided`, `approval_expired`, and `approval_resumed` (`src/agent/events.py:17`). Approval event helpers emit `AgentTraceEvent`, link `ApprovalEvent.replay_event_id`, and reject raw prompt/args/payload/tool output/secrets/PII (`src/approvals/events.py:23`, `src/approvals/events.py:266`). Event tests verify registration, refs, decision types, revision refs, and redaction (`tests/approvals/test_events.py:65`). |
| 10 | SLA scanner exists but is disabled by default, with Phase 15 owning active enablement. | VERIFIED | `ApprovalSlaScanner.scan` returns disabled/no-op unless enabled (`src/approvals/sla_scanner.py:42`), config defaults false (`src/config.py:35`), and `.env.example` sets `APPROVAL_SLA_SCANNER_ENABLED=false`. Tests verify disabled no-op and enabled state consistency without making active scheduling a Phase 13 requirement (`tests/approvals/test_sla_scanner.py:43`, `tests/approvals/test_sla_scanner.py:76`). |
| 11 | Legacy approval transition paths are deleted/quarantined and protected by boundary tests. | VERIFIED | `find src/repositories -maxdepth 1 -name approval_repo.py` returned no file. Static tests forbid router/test imports of `src.repositories.approval_repo` and raw approval decision adapters (`tests/architecture/test_approval_boundaries.py:33`, `tests/architecture/test_approval_boundaries.py:49`, `tests/architecture/test_approval_boundaries.py:66`). |
| 12 | Coverage, eval manifest, schema drift, ruff, and pytest gates are documented or verified. | VERIFIED | `13-COVERAGE.md` has no relevant `MISSING` rows, records covered requirements/deferred owners/spec reconciliation, and contains final gate statuses. Eval manifest has real dataset hash `sha256:89251f64...` and blocking metadata (`tests/approvals/phase13_eval_manifest.json:1`). I re-ran `gsd-sdk query verify.schema-drift 13` (`valid: true`, `issues: []`, `checked: 8`), `uv run ruff check src tests` (passed), and focused behavioral tests (`33 passed`). Orchestrator-provided full gate after review fixes: `uv run pytest -q --tb=short` => `748 passed, 1 warning`. |

**Score:** 12/12 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|---|---|---|
| 1 | Active SLA scanner scheduling | Phase 15 | 13-COVERAGE P13-FU-05: enable only after replay coverage and allocator concurrency gates pass. |
| 2 | Durable draft-only demo action executor boundary | Phase 14 | 13-COVERAGE P13-FU-08 and roadmap Phase 14 success criteria. |
| 3 | ReplayEventV3 enrichment and replay read switch | Phase 15 | 13-COVERAGE P13-FU-09 and roadmap Phase 15 goal. |
| 4 | External execution/outbox/reconciliation/compensation | Phase 17 | 13-COVERAGE P13-FU-11 and roadmap Phase 17 goal. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| Plan-declared artifacts | 27 artifacts across Plans 13-01 through 13-08 | VERIFIED | `gsd-sdk query verify.artifacts` passed for all eight plans: 4/4, 4/4, 6/6, 4/4, 2/2, 4/4, 1/1, 2/2. |
| `src/common/canonical_hash.py` | Shared canonical hash module | VERIFIED | Substantive implementation with validation and digest helpers; consumed by snapshot and snapshot service. |
| `src/approvals/*` | Approval domain owner package | VERIFIED | Schemas, policy, repository, snapshot service, service, events, and SLA scanner are wired to API/graph/tests. |
| `src/db/models.py` and migration 008 | Durable approval/snapshot schema | VERIFIED | Tables, constraints, indexes, legacy handling, and rollback path exist and are tested. |
| API/graph/action files | Trusted command/resume/action-hash cutover | VERIFIED | Routers construct commands; graph/action code accepts only trusted result and exact binding. |
| Tests and coverage artifacts | Focused tests, eval manifest, coverage matrix | VERIFIED | Focused spot-check passed locally; full suite/ruff/schema drift evidence recorded. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| API decision endpoint | `ApprovalService.decide` | `ApprovalDecisionCommand` | WIRED | Server-side actor/tenant/run/thread/context fields are populated in `src/api/routers/approvals.py:53`. |
| Agent/SSE interrupt handling | `ApprovalService.create_request` | `ApprovalRequestCreateCommand` | WIRED | `_create_approval_wait_payload_from_interrupt` calls service and returns request/level/assignment versions plus hashes (`src/api/routers/agent_runs.py:436`). |
| ApprovalService | ApprovalRepository | Locks, CAS, inserts | WIRED | Service locks request/level/assignment and repository inserts decision/event rows with redundant fields. |
| ApprovalService/risk node | Snapshot service | `persist_action_safety_snapshot` | WIRED | Snapshot persistence computes payload hash, writes row, reloads by ref/hash, and returns binding (`src/approvals/snapshot_service.py:54`). |
| ApprovalService | Minimal event envelope | `emit_approval_*` helpers | WIRED | Events call `emit_event`, link `replay_event_id`, and store safe metadata/refs. |
| Graph route | Execute action | `approval_result.v1` exact binding | WIRED | `route_after_approval` and `execute_action` both fail closed on untrusted/mismatched hashes. |
| Boundary tests | Legacy repository path | AST import checks | WIRED | Static tests forbid legacy transition imports; the legacy file is deleted. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `assess_risk_and_approval.py` | `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash` | Proposed action + evidence refs -> `persist_action_safety_snapshot` -> DB row reload | Yes | FLOWING |
| `agent_runs.py` wait payload | approval id, revision/version refs, hashes | `ApprovalService.create_request` result from persisted request/level/assignment/snapshot rows | Yes | FLOWING |
| `approvals.py` decision route | `ApprovalDecisionCommand` and `resume_payload` | Authenticated user + DB decision context + client expected versions/hashes -> `ApprovalService.decide` | Yes | FLOWING |
| `graph.py` approval route | `approval_result` | Service-built `TrustedApprovalResultV1` only; ordinary payloads fail closed | Yes | FLOWING |
| `execute_action.py` action guard | trusted approval binding | Graph state + `approval_result.v1`; all required revision/version/hash fields checked | Yes | FLOWING |
| `approvals/events.py` | event metadata/refs/payload | Durable request/level/assignment/decision rows -> `emit_event` + `ApprovalEvent.replay_event_id` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Artifact completeness | `gsd-sdk query verify.artifacts` for all 8 plans | 27/27 artifacts passed | PASS |
| Schema drift | `gsd-sdk query verify.schema-drift 13` | `valid: true`, `issues: []`, `checked: 8` | PASS |
| Focused approval state-machine paths | `uv run pytest tests/approvals/test_hash_binding.py tests/approvals/test_needs_info_resume.py tests/approvals/test_sla_scanner.py tests/architecture/test_approval_boundaries.py -q --tb=short` | 33 passed, 1 warning in 45.20s | PASS |
| Lint | `uv run ruff check src tests` | All checks passed | PASS |
| Full suite | `uv run pytest -q --tb=short` | Orchestrator observed after review fixes: 748 passed, 1 warning in 296.53s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| APPROVAL-01 | 13-02, 13-03, 13-04, 13-06, 13-07 | Approval transitions, request/level/assignment CAS, and revision invalidation are enforced. | SATISFIED | Service/repository CAS and transition tests; API/graph cutover; event rows; legacy path deleted. |
| APPROVAL-02 | 13-05, 13-07 | Approval needs_info resume validates clarification identity, scope, versions, changed facts, and old-revision prohibition. | SATISFIED | `respond`, `attach_info`, and `edit` service code plus `test_needs_info_resume.py` coverage. |
| APPROVAL-03 | 13-02, 13-03, 13-06, 13-07 | Single-level runtime complete, multi-level-compatible contracts verified, active SLA scanner owned gate. | SATISFIED | Single-level runtime tests, multi-level schema tests, disabled scanner default and Phase 15 defer row. |
| SNAPSHOT-01 | 13-01, 13-03, 13-04, 13-07 | ActionSafetySnapshot and CanonicalHashProfile bind approval, draft, and execution to exact payload/evidence/config hashes. | SATISFIED | Canonical/golden tests, snapshot persistence, hash-binding tests, graph/action guard tests. |

No orphaned Phase 13 requirements were found: `.planning/REQUIREMENTS.md` maps only `APPROVAL-01..03` and `SNAPSHOT-01` to Phase 13.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| Multiple | n/a | Stub/placeholder scan | INFO | No blocker. Matches were benign helper returns such as interrupt extraction fallback dictionaries and optional parser `None` returns, not user-visible placeholders or hollow data paths. |
| `src/repositories/approval_repo.py` | n/a | Legacy transition path | INFO | File is absent; boundary tests protect against reintroduction. |

### Human Verification Required

None for Phase 13 code completion. The validation file still contains a deployment-only operational check for production/staging legacy approval row counts before deployment; that is not a Phase 13 code-readiness blocker because local migration behavior and legacy non-executable semantics are covered by automated tests and the migration report.

### Gaps Summary

No gaps found. Deferred items are explicitly owned by later roadmap phases and do not reduce Phase 13 completion: Phase 14 owns draft/demo executor behavior, Phase 15 owns ReplayEventV3 and active SLA enablement, Phase 16 owns long-term/case memory, and Phase 17 owns external execution.

---

_Verified: 2026-06-15T12:24:32Z_  
_Verifier: Codex (gsd-verifier)_
