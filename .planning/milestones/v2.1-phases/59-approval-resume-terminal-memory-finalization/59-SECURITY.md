---
phase: 59
slug: approval-resume-terminal-memory-finalization
status: verified
threats_total: 14
threats_closed: 14
threats_open: 0
asvs_level: 1
created: 2026-07-08
verified: 2026-07-08T10:41:06Z
---

# Phase 59 - Security

Per-phase security verification for approval-resume terminal memory finalization. Scope is limited to threats registered in `59-01-PLAN.md`, `59-02-PLAN.md`, and `59-03-PLAN.md`; the auditor did not scan for unrelated vulnerabilities.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Agent final state -> terminal memory write | Completed terminal finalization may sanitize approval markers before session memory write; direct memory writes must keep pending/interrupted approval skips. | Approval markers, final response, memory write state |
| Terminal finalizer -> AgentStep table | Retry or duplicate completion calls must not append duplicate `agent_run_memory_finalize` trace rows. | Trace steps, finalizer metrics |
| Approval reviewer/admin actor -> graph resume | Reviewer/admin identity is trusted for approval resume and action-draft permissions only. | Trusted graph config, permissions |
| Original requester -> terminal memory/CWC finalizer | Assistant message, thread summary, session memory, and CWC writes must bind to the original run requester. | `AgentRun.user_id`, requester `User`, thread/run identifiers |
| Approval resume terminal state -> audit/retry evidence | Completed events must require durable terminal finalizer evidence; interrupted/error paths must not create terminal memory surfaces. | Run status, final response, approval events, finalizer trace evidence |
| Validation and ledger artifacts -> archive evidence | Planning ledgers must summarize commands/issues without raw sensitive payloads. | Test commands, local validation notes, architecture-debt entries |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-59-01-01 | Elevation of privilege | `src/agent/nodes/memory_write.py` approval skip boundary | mitigate | `memory_write.py:42-48` and `354-360` keep `_approval_or_interrupted(...)`; `agent_run_memory.py:331-340` strips markers only in terminal finalizer state. | closed |
| T-59-01-02 | Tampering | `AgentStep` finalizer trace persistence | mitigate | `agent_run_memory.py:77-88` checks existing `FINALIZER_NODE` before append; `90-97` appends only when absent. | closed |
| T-59-01-03 | Spoofing | Requester identity helper | mitigate | `agent_run_memory.py:55-63` builds finalizer input from persisted run plus requester `User`. | closed |
| T-59-01-04 | Repudiation | Finalizer persistence rollback path | mitigate | `agent_run_memory.py:90-101` preserves rollback/default suppression for normal runs; `59-REVIEW-FIX.md` documents approval-resume fail-closed trace persistence. | closed |
| T-59-02-01 | Spoofing | `_resume_graph_after_decision(...)` finalizer identity | mitigate | `approvals.py:380-387` fetches requester by `run.user_id`; `849-861` keeps reviewer/admin `actor_user` scoped to graph resume config. | closed |
| T-59-02-02 | Tampering | Approval resume final state | mitigate | `approvals.py:358-402` updates status and post-approval trace before completed finalizer; shared duplicate guard is in `agent_run_memory.py:77-88`. | closed |
| T-59-02-03 | Elevation of privilege | Action-draft reconciliation | mitigate | `approvals.py:765-776` keeps accept/approve-only action-draft reconciliation and existing-draft guard by run/approval. | closed |
| T-59-02-04 | Information disclosure | Interrupted/error resume branches | mitigate | Completed-only finalizer guard is `approvals.py:377`; tests at `tests/test_approval_api.py:1192-1263` and `1267-1312` assert no terminal surfaces. | closed |
| T-59-02-05 | Tampering | Canonical graph vocabulary | mitigate | `approvals.py:59-60` keeps `risk_gate` canonical and historical retry map only; architecture tests assert no active legacy risk aliases. | closed |
| T-59-03-01 | Tampering | Approval completed regression | mitigate | `tests/test_approval_api.py:1856-1937` asserts assistant message, thread summary, `MemoryWriteEvent`, finalizer step, memory status, and CWC status. | closed |
| T-59-03-02 | Denial of service | Retry/dedupe regression | mitigate | `tests/test_approval_api.py:557-715` injects post-finalizer completed-event failure and verifies retry does not duplicate graph/action/finalizer side effects. | closed |
| T-59-03-03 | Elevation of privilege | Direct `memory_write(...)` approval markers | mitigate | `tests/agent/test_memory_write_node.py:57-73` verifies direct approval-marked states still skip as `not_completed_path`. | closed |
| T-59-03-04 | Repudiation | Validation artifact | mitigate | `59-VALIDATION.md:72-94` records exact `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` and ruff commands with statuses. | closed |
| T-59-03-05 | Information disclosure | Architecture/local ledgers | mitigate | Initial audit found a local test DB password literal in `.planning/LOCAL-VALIDATION-ISSUES.md`; the ledger now uses `REDACTED_LOCAL_TEST_PASSWORD` placeholders, and no such raw literal remains in that ledger. | closed |

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-08 | 14 | 13 | 1 | `gsd-security-auditor` |
| 2026-07-08 | 14 | 14 | 0 | Codex secure-phase orchestrator |

## Auditor Finding Resolution

The independent auditor initially returned `OPEN_THREATS` for T-59-03-05 because a Phase 59 local validation cleanup command recorded a raw local test database password literal. The finding was valid and was remediated by redacting local validation ledger password occurrences to `REDACTED_LOCAL_TEST_PASSWORD`.

Follow-up checks:

- `rg -n "REDACTED_LOCAL_TEST_PASSWORD" .planning/LOCAL-VALIDATION-ISSUES.md` confirms the placeholder is used in affected local validation notes.
- A raw local test password literal search over `.planning/LOCAL-VALIDATION-ISSUES.md` returned no matches.
- Summary threat flags remain none in `59-01-SUMMARY.md`, `59-02-SUMMARY.md`, and `59-03-SUMMARY.md`.

## Verification Evidence

- `59-VERIFICATION.md` reports `status: passed` and `score: 18/18 must-haves verified`.
- `59-REVIEW.md` is clean with zero findings after review fixes.
- `59-REVIEW-FIX.md` records WR-01 and WR-02 fixed and verified.
- Final Phase 59 selected suite after review fixes: `196 passed, 1 warning`.
- Final ruff gate after review fixes: `All checks passed!`.

## Sign-Off

- [x] All threats have a disposition.
- [x] Accepted risks documented in Accepted Risks Log.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

Approval: verified 2026-07-08
