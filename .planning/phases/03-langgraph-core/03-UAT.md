---
status: complete
phase: 03-langgraph-core
source:
  - 03-01-SUMMARY.md
  - 03-02-SUMMARY.md
  - 03-03-SUMMARY.md
  - 03-04-SUMMARY.md
  - 03-05-SUMMARY.md
  - 03-06-SUMMARY.md
started: 2026-05-15T13:29:25Z
updated: 2026-05-16T02:11:58Z
---

## Current Test

[testing complete]

## Tests

### 1. Agent chat policy answer
expected: Calling `POST /api/v1/agent/chat` with a valid `agent:chat` user and a refund-policy question returns a completed Chinese answer, includes policy evidence references, and the public trace summary reports the expected intent, node list, evidence count, risk status, latency, and final status without exposing raw prompts or full tool output.
result: pass
evidence: "Retest returned final_status='completed', intent='policy_qa', evidence_count=5, tools_called=['search_policy'], and a Chinese response citing merchant_faq_005, refund_policy_006, and refund_time_limits_004."
note: "Initial Swagger issue was an old running server process. Follow-up returned 401 Not authenticated, meaning the request reached FastAPI auth but lacked a Bearer token. Code review also found role-issued tokens were missing the required agent:chat scope; src/auth/jwt.py now issues agent:chat for support, manager, merchant, and admin roles. Swagger Authorize also used OAuth2 password flow against JSON /auth/login, causing 422; /api/v1/auth/token now provides a standard form-compatible token endpoint. Initial retrieval failure was fixed by making EmbeddingService use settings.dashscope_api_key."

### 2. Refund troubleshooting with business context
expected: Asking about seeded order `ORD-2024-001` returns a completed refund-troubleshooting response that uses tenant-scoped order/refund/ticket context plus retrieved policy evidence, and does not reveal another tenant's data or ticket message history.
result: pass
evidence: "Retest returned final_status='completed', intent='refund_troubleshooting', tools_called=['get_order','search_policy'], evidence_count=5, risk_level='high', and a Chinese response citing cross_border_refund and high_value_refund evidence."

### 3. No-evidence fallback
expected: Asking an unrelated question returns the configured insufficient-evidence response, sets final status to `insufficient_evidence`, returns zero current evidence, and skips definitive recommendation generation.
result: pass
evidence: "Retest returned final_status='insufficient_evidence', intent='unknown', evidence_count=0, risk_level='low', and the configured no-evidence response without surfacing retrieval infrastructure errors."

### 4. Same-thread evidence memory
expected: Reusing the same thread preserves compact prior `evidence_refs` for audit/memory while each new turn still gates the answer on current-turn retrieved evidence; a no-evidence follow-up still refuses instead of relying on stale evidence.
result: pass
evidence: "Retest used thread_id='uat-03-memory-retest'. First turn returned final_status='completed' and evidence_count=5 for refund policy. Second turn with unrelated query returned final_status='insufficient_evidence' and evidence_count=0, proving current-turn evidence gating did not use stale same-thread evidence."

### 5. Trace persistence and audit rows
expected: Each agent call writes one `agent_runs` row and node-level `agent_steps` rows keyed by the run id; persisted step rows include normalized tool names and compact evidence refs while excluding raw prompts, stack traces, and full business context.
result: pass
evidence: "Run 46b9315e-bd2a-4957-8367-425fbb338883 persisted one completed agent_runs row and eight agent_steps rows. retrieve_policy_evidence persisted tool_name='search_policy' plus five compact evidence_refs; generate_recommendation persisted three citation-validated evidence_refs; error_message was null for all steps."

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
