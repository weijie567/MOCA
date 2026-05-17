---
status: complete
phase: 04-approval-workflow-audit
source:
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
  - 04-03-SUMMARY.md
  - 04-04-SUMMARY.md
  - 04-05-SUMMARY.md
  - 04-06-SUMMARY.md
started: 2026-05-17T09:12:42+08:00
updated: 2026-05-17T11:45:00+08:00
---

## Current Test

[testing complete]

## Tests

### 1. High-risk chat creates a pending approval
expected: A support user calling `POST /api/v1/agent/chat` with a high-risk 600 CNY compensation request gets an interrupted response with an approval id, run id, high risk level, and no final action execution.
result: pass
evidence: "User reported pass after re-running with ingested policy documents and new thread_id `uat-phase4-approve-2`."

### 2. Manager/admin approval resumes execution and creates an action draft
expected: Logging in as `admin_user`, calling `POST /api/v1/approvals/{approval_id}/decide` with `{"decision":"approve","reason":"UAT approve"}` returns status `approved`; fetching the run trace shows a completed run and one action draft linked to the approval.
result: pass
evidence: "After action-type canonicalization fix and API reload, user reported trace key fields: final_status=completed, action_drafts=1, and timeline_types included action_draft."

### 3. Manager/admin rejection resumes without action execution
expected: A second high-risk chat can be rejected through `POST /api/v1/approvals/{approval_id}/decide`; the response status is `rejected`, the run completes, the final response includes the rejection reason, and trace replay shows zero action drafts for that run.
result: pass
evidence: "User reported pass after reject path returned decision_status=rejected, decision_reason=UAT reject, final_status=completed, and action_drafts=0."

### 4. Low-risk policy query bypasses approval
expected: Calling `POST /api/v1/agent/chat` with a policy question such as `七天无理由退款政策规则是什么？` returns a completed response with `trace_summary.final_status` equal to `completed` and no `approval_id` field.
result: pass
evidence: "User reported pass after file-based JSON request returned final_status=completed, risk_level=low, and approval_id_fields=0."

### 5. Approval API enforces reviewer role
expected: A support token calling `POST /api/v1/approvals/{approval_id}/decide` receives HTTP 403 with code `FORBIDDEN`; the pending approval remains pending and is not resumed.
result: pass
evidence: "User reported http_status=403 with error.code=FORBIDDEN and previously confirmed approval_status=pending for approval 56d00820-0559-44c1-b2d4-58da935722ef."

### 6. Trace replay is complete but sanitized
expected: `GET /api/v1/agent-runs/{run_id}/trace` returns steps, approvals, approval steps, action drafts, and a unified timeline for the run; timeline entries do not expose raw `input_query`, `final_response`, or reasoning summaries.
result: pass
evidence: "Trace for run c1c4b819-9287-41f4-b904-36a77f2e6478 returned final_status=completed, steps/approvals/action_drafts/timeline arrays, one action_draft event, no input_query field, no reasoning_summary field, and only final_response as sanitized node names rather than a raw response field."

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
