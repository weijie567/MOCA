# Requirements: MOCA v1.7 Short-term Memory Unification

**Defined:** 2026-06-20  
**Milestone:** v1.7 Short-term Memory Unification

## Core Value

When a merchant or support agent asks about a refund issue, the system must retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure any risky action goes through approval before execution -- never silently executing something irreversible.

## Milestone Goal

Complete the short-term memory chain for the current Agent Console main path, `/api/v1/agent-runs + SSE`, so same-thread follow-up turns can use structured session slots, conversation messages, prompt-safe tool summaries, and rolling thread summaries without weakening evidence, business-fact, approval, action, or replay authority boundaries.

## v1 Requirements

### Agent Runs Conversation Persistence

- [ ] **STM-01:** Current Agent Console `/api/v1/agent-runs` creates or resolves a conversation thread and persists exactly one user conversation message for each submitted query before graph execution.
- [ ] **STM-02:** `/agent-runs` graph execution receives trusted `conversation_thread_id` and `conversation_message_id` in the run config so tool calls and tool results can be linked to the current turn.
- [ ] **STM-03:** Completed `/agent-runs` runs persist exactly one assistant conversation message containing the final response and final status metadata.
- [ ] **STM-04:** Completed `/agent-runs` runs update the thread rolling summary from newly committed user/assistant messages and eligible prompt-safe tool summaries.

### Short-term Prompt Context

- [ ] **STM-05:** Same-thread follow-up turns on `/agent-runs` can load recent conversation messages, the latest prior rolling summary, and prompt-safe tool summaries into prompt context.
- [ ] **STM-06:** PostgreSQL-authoritative session slot memory remains active on `/agent-runs`, and explicit current-turn slots continue to override inherited trusted session slots.
- [ ] **STM-07:** Tool prompt summaries persisted from `/agent-runs` exclude raw payloads, private reasoning, authority bodies, debug traces, secrets, and PII beyond the existing allowed summary surface.
- [ ] **STM-08:** Legacy `/api/v1/agent/chat` remains compatible with the shared conversation, tool summary, rolling summary, and session memory infrastructure.

### Failure and Idempotency Semantics

- [ ] **STM-09:** Error, cancelled, and approval-interrupted runs have deterministic conversation persistence behavior and do not create false completed assistant messages or false completed rolling summaries.
- [ ] **STM-10:** Retried, re-opened, or duplicate SSE streams do not duplicate user messages, assistant messages, tool result records, rolling summaries, or session memory writes.
- [ ] **STM-11:** Memory writes are ordered so an incomplete stage stays running until its persistence obligations are done, then the next stage can begin with consistent state.

### Authority Boundaries and Verification

- [ ] **STM-12:** Rolling summaries, recent messages, tool summaries, session memory, long-term memory, and case memory remain contextual assistance only and cannot satisfy policy evidence, current business fact, approval/action authority, or replay/audit truth requirements.
- [ ] **STM-13:** Regression tests cover `/agent-runs` conversation persistence, rolling summary generation, prompt context loading, session slot continuity, idempotent stream retry behavior, and legacy `/agent/chat` compatibility.
- [ ] **STM-14:** A live or integration smoke flow verifies a three-turn Agent Console conversation can use both slot continuity and rolling-summary context.

## v2 / Future Requirements

- [ ] **STM-FUT-01:** User-facing memory inspection and management UI.
- [ ] **STM-FUT-02:** Configurable conversation retention, archival, and deletion policy controls.
- [ ] **STM-FUT-03:** Admin review workflow for promoting short-term conversation patterns into reviewed long-term or case memory.
- [ ] **STM-FUT-04:** Broader memory observability dashboard across tenants, users, threads, runs, and replay artifacts.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full long-term or case memory redesign | v1.2 Phase 16 already owns reviewed long-term and case memory foundations; v1.7 wires the current short-term runtime path. |
| Treating memory as evidence or business fact authority | Violates established `EvidenceRefV1`, tool-result, and current-business-fact boundaries. |
| Approval/action execution redesign | Approval and real external action execution remain separate boundaries; memory can provide context but not authorization or side effects. |
| Replay truth redesign | Replay must continue to rely on persisted run/step/tool/audit artifacts, not generated memory summaries. |
| Frontend redesign | The current Agent Console API and UX should keep working; v1.7 is backend memory persistence and prompt-context work. |
| Policy source operations UI | Separate future milestone. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STM-01 | Phase 24 | Pending |
| STM-02 | Phase 24 | Pending |
| STM-03 | Phase 24 | Pending |
| STM-04 | Phase 24 | Pending |
| STM-05 | Phase 24 | Pending |
| STM-06 | Phase 24 | Pending |
| STM-07 | Phase 24 | Pending |
| STM-08 | Phase 24 | Pending |
| STM-09 | Phase 24 | Pending |
| STM-10 | Phase 24 | Pending |
| STM-11 | Phase 24 | Pending |
| STM-12 | Phase 24 | Pending |
| STM-13 | Phase 24 | Pending |
| STM-14 | Phase 24 | Pending |

---
*Last updated: 2026-06-20 when v1.7 roadmap traceability was created.*
