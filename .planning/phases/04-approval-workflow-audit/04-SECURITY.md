---
phase: 04
slug: approval-workflow-audit
status: verified
threats_open: 0
asvs_level: 1
block_on: open
created: 2026-05-17
review_fix: 3f217f4
---

# Phase 04 — Security

Per-phase security contract: threat register, accepted risks, and audit trail for the approval workflow and trace APIs.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Agent chat API -> LangGraph | Authenticated user request invokes graph and may interrupt for human approval. | User query, tenant/user IDs, thread ID, trace metadata |
| LangGraph interrupt -> Approval API | High-risk action pauses, persists approval request, and resumes only after reviewer decision. | Proposed action, risk metadata, approval decision |
| Approval API -> Database | Reviewer reads and decides tenant-scoped approval rows. | Approval requests, approval steps, agent run status |
| Execute action -> Action draft repository | Approved or low-risk proposed actions create durable action drafts. | Action payload, idempotency key, tenant/run IDs |
| Trace API -> Client | Tenant-scoped audit timeline exposes replay metadata. | Agent steps, approval metadata, action draft identifiers |
| Diagnostic script -> Agent steps | Read-only latency analysis over persisted steps. | Latency metrics, retry counts, context length |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| 04-01-T01 | Info leakage | Latency metrics + `diagnose_latency.py` | mitigate | `metrics_json` stores only `model`, `provider`, `context_chars`; diagnostic script reads numeric metrics only. Evidence: `src/agent/nodes/classify_intent.py:49`, `src/agent/nodes/extract_slots.py:49`, `src/agent/nodes/generate_recommendation.py:53`, `src/agent/nodes/assess_risk_and_approval.py:62`, `scripts/diagnose_latency.py:27`, `tests/test_latency_instrumentation.py:94`. | closed |
| 04-02-T01 | Cross-tenant access | `approval_requests`, `approval_steps`, `action_drafts` | mitigate | New approval/action tables carry tenant IDs and indexes; repositories require tenant-scoped reads/mutations. Evidence: `src/db/models.py:230`, `src/db/models.py:276`, `src/db/migrations/versions/005_approval_tables.py:46`, `src/db/migrations/versions/005_approval_tables.py:85`, `src/repositories/approval_repo.py:46`, `src/repositories/action_draft_repo.py:47`. | closed |
| 04-02-T02 | Idempotency collision | `action_drafts` | mitigate | Global unique idempotency key exists; cross-tenant reuse raises conflict instead of returning another tenant draft. Evidence: `src/db/models.py:271`, `src/db/migrations/versions/005_approval_tables.py:82`, `src/repositories/action_draft_repo.py:26`, `src/repositories/action_draft_repo.py:29`, `tests/test_approval_models.py:143`. | closed |
| 04-02-T03 | Concurrent approve/reject race | Approval decision | mitigate | `decide()` selects row with `FOR UPDATE` and returns a locked transition flag. Evidence: `src/repositories/approval_repo.py:53`, `src/repositories/approval_repo.py:60`, `src/repositories/approval_repo.py:76`, `src/repositories/approval_repo.py:103`, `tests/test_approval_models.py:75`. | closed |
| 04-03-T01 | Approval bypass | Graph routing | mitigate | If `risk_assessment.approval_required` is true, `route_after_risk()` returns only `approval_gate`; conditional edge maps that branch to approval gate. Evidence: `src/agent/graph.py:36`, `src/agent/graph.py:40`, `src/agent/graph.py:77`, `tests/test_graph_routing.py:16`, `tests/test_interception_rate.py:88`. | closed |
| 04-03-T02 | Execution without approval | `execute_action` | mitigate | Approval-required states whose resume decision is not `approve` return `NOT_APPROVED` before the write tool is called. Evidence: `src/agent/nodes/execute_action.py:33`, `src/agent/nodes/execute_action.py:54`, `tests/test_execute_action.py:57`. | closed |
| 04-03-T03 | Forged resume payload | Approval API resume | mitigate | API parses approval ID, fetches tenant-scoped approval, enforces reviewer auth and self-approval denial, checks expiry, and uses locked decision transition before `Command(resume=...)`. Evidence: `src/api/routers/approvals.py:31`, `src/api/routers/approvals.py:41`, `src/api/routers/approvals.py:45`, `src/api/routers/approvals.py:48`, `src/api/routers/approvals.py:55`, `src/api/routers/approvals.py:65`, `src/api/routers/approvals.py:80`. | closed |
| 04-04-T01 | Unauthorized approval | Approval REST API | mitigate | Decide/get/list endpoints require `approvals:review`; decide additionally gates reviewer role to `admin` or `manager`. Evidence: `src/api/routers/approvals.py:22`, `src/api/routers/approvals.py:31`, `src/api/routers/approvals.py:33`, `src/api/routers/approvals.py:124`, `src/api/routers/approvals.py:141`, `tests/test_approval_api.py:195`. | closed |
| 04-04-T02 | Self-approval | Approval REST API | mitigate | Decide endpoint rejects `requested_by == user.id`. Evidence: `src/api/routers/approvals.py:45`, `tests/test_approval_api.py:179`. | closed |
| 04-04-T03 | Cross-tenant approval access | Approval REST API + repositories | mitigate | Approval reads/list/decide use `user.tenant_id`; repository queries include `ApprovalRequest.tenant_id`. Evidence: `src/api/routers/approvals.py:41`, `src/api/routers/approvals.py:57`, `src/api/routers/approvals.py:127`, `src/api/routers/approvals.py:144`, `src/repositories/approval_repo.py:49`, `tests/test_approval_api.py:304`. | closed |
| 04-04-T04 | Replay/race on decide | Approval REST API + repository | mitigate | Row-level locking plus idempotent state machine returns `transitioned`; API records decision events and resumes graph only when transition is true, matching review fix `3f217f4`. Evidence: `src/repositories/approval_repo.py:88`, `src/repositories/approval_repo.py:94`, `src/repositories/approval_repo.py:103`, `src/api/routers/approvals.py:55`, `src/api/routers/approvals.py:65`, `tests/test_approval_api.py:226`, `04-REVIEW-FIX.md`. | closed |
| 04-04-T05 | Expired approval resume | Approval REST API | mitigate | Expired approvals are locked, marked expired, committed, and return 409 before resume. Evidence: `src/api/routers/approvals.py:48`, `src/api/routers/approvals.py:49`, `src/api/routers/approvals.py:52`, `src/repositories/approval_repo.py:111`, `tests/test_approval_integration.py:146`. | closed |
| 04-05-T01 | Unauthorized trace access | Trace API | mitigate | Trace endpoint requires `agent:chat`, loads run by `(run_id, tenant_id)`, and allows only owner or supervisor-equivalent roles. Evidence: `src/api/routers/traces.py:26`, `src/api/routers/traces.py:30`, `src/api/routers/traces.py:35`, `src/repositories/trace_repo.py:16`, `tests/test_trace_api.py:76`, `tests/test_trace_api.py:112`. | closed |
| 04-05-T02 | Trace information leakage | Trace API | mitigate | Trace response omits raw `input_query` and `final_response`; proposed actions are sanitized to `action_type`, `amount`, `currency`; tests assert seeded secret text is absent. Evidence: `src/api/routers/traces.py:44`, `src/api/routers/traces.py:51`, `src/api/routers/traces.py:60`, `src/repositories/trace_repo.py:77`, `src/repositories/trace_repo.py:114`, `tests/test_trace_api.py:51`. | closed |

## Accepted Risks Log

No accepted risks.

## Unregistered Threat Flags

None. `04-05-SUMMARY.md` and `04-06-SUMMARY.md` explicitly record no threat flags; earlier summaries do not contain `## Threat Flags` sections.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-17 | 14 | 14 | 0 | Codex security auditor |

## Verification Notes

- Loaded all phase plans, summaries, review, review-fix, verification, cited implementation files, and security-relevant tests listed for this audit.
- Verified review finding CR-01 is closed by `ApprovalRepository.decide()` returning `(approval, transitioned)` from the locked path and the API resuming only on `transitioned`.
- Verified review finding WR-02 is closed by `_safe_proposed_action()` and trace API tests that assert no seeded secret content leaks.
- Recent verification context: full suite passed with `164 passed, 1 warning`; focused approval/security tests passed with `35 passed, 1 warning`.

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-17
