---
phase: 4
reviewers: [codex]
reviewed_at: 2026-05-16T12:00:00Z
plans_reviewed: [04-01-PLAN.md, 04-02-PLAN.md, 04-03-PLAN.md, 04-04-PLAN.md, 04-05-PLAN.md, 04-06-PLAN.md]
---

# Cross-AI Plan Review — Phase 4

## Codex Review

**Summary**

The plan set is directionally strong and covers the right major pieces: approval interruption, conditional graph routing, write-draft idempotency, approval APIs, trace reconstruction, and CI-safe tests. The biggest risks are not scope gaps, but correctness gaps around LangGraph interrupt/resume semantics, checkpoint thread identity, persistence across the interrupted/resumed halves of a run, and stale state leakage. As written, the plans are likely to produce a partially working approval API but fail the real end-to-end path unless those issues are fixed before implementation.

**Strengths**

- Clear phase decomposition: schema/state, graph nodes, API, audit timeline, and validation are separated well.
- Good safety posture: self-approval blocking, tenant filtering, idempotent decisions, and "reject is not failed" are all correct domain decisions.
- Draft-only write action is a pragmatic Phase 4 boundary and avoids real compensation issuance too early.
- Trace timeline design is useful for Phase 5 and avoids overcommitting to a full audit event stream.
- Testing plan correctly emphasizes mock LLMs, high-risk interception, idempotency, and end-to-end approve/reject paths.

**Concerns**

- **HIGH: LangGraph interrupt handling is probably wrong in Plan 04-04.** The chat endpoint plan catches `GraphInterrupt`, but LangGraph commonly returns interrupt data through the graph result under `__interrupt__` rather than surfacing it as an API-level exception. This must be verified against the installed LangGraph version before coding. A generic `except Exception` would otherwise turn approvals into 500s.

- **HIGH: Resume thread ID is wrong.** Current code uses `tenant_id:user_id:thread_id` in `_checkpoint_thread_id()`. Plan 04-04 resumes with `tenant_id:run_id`, which will not find the interrupted checkpoint.

- **HIGH: Reject path does not resume the graph.** D-02f says reject resumes into `final_response`, but Plan 04-04 only resumes on approve. That leaves the graph paused and prevents a real final response explaining rejection.

- **HIGH: Interrupted run persistence is incomplete.** Current `write_agent_run()` only inserts. Plans do not define how the existing `interrupted` run is updated to `completed`, `expired`, or `failed` after resume, nor how resumed trace steps are appended without duplicating earlier steps.

- **HIGH: `approval_gate` does not create or remember `approval_id`.** Plan 03 says the node does not write DB and only emits an interrupt payload. But the threat model says resume payload should be validated against the created approval. That validation is impossible unless the approval ID is persisted in state or deterministically created before interrupt.

- **HIGH: State reset is missing.** `receive_request` currently resets ephemeral state to avoid stale checkpointer memory. The plans add `proposed_action`, `approval_result`, and `action_result` but do not update `receive_request` to reset them. This can cause a later low-risk turn to inherit an old proposed action.

- **HIGH: Node signature for `execute_action` is incompatible with existing graph pattern.** Existing nodes that need DB access accept `config: RunnableConfig` and read `config["configurable"]["session"]`. `async def execute_action(state, *, session)` is unlikely to be called correctly by LangGraph.

- **HIGH: `final_response` is not updated for approval outcomes.** Current `final_response` only looks at `recommendation_draft` and `risk_assessment`. It will not mention approved draft creation, rejected approval, or action failure unless explicitly modified.

- **MEDIUM: Wave 1 has migration/model conflicts.** Plans 04-01 and 04-02 both modify `src/db/models.py` and both autogenerate migrations independently. That should be serialized or combined to avoid migration drift.

- **MEDIUM: Alembic path is wrong in acceptance criteria.** The repo uses `src/db/migrations/versions`, not `alembic/versions`.

- **MEDIUM: Latency instrumentation omits reliable `latency_ms`.** The plan adds provider latency, but all nodes also need node latency. Current `write_agent_steps()` does not compute it from timestamps if absent.

- **MEDIUM: Retry metrics may be misleading.** LangGraph has graph-level `RetryPolicy(max_attempts=2)` and nodes also have manual retry loops. Failed graph-level attempts may not append trace steps, so `retry_count` needs a consistent definition.

- **MEDIUM: ApprovalRepository needs transactional locking.** `decide()` should use row-level locking or equivalent to prevent concurrent approve/reject races. Idempotency alone is not enough under simultaneous requests.

- **MEDIUM: Expiry is under-specified.** API-time expiry checks are not enough for "agent_run marked expired" if nobody calls decide. Add a sweep function, list-time expiry check, or background job.

- **MEDIUM: Auth roles are inconsistent with current code.** Current JWT role scopes include `manager` and `admin`; the plan uses `supervisor/admin/approval_manager`. Either seed/auth roles must be updated or the approval API will reject valid scoped users.

- **MEDIUM: Approval step event names are inconsistent.** The model says `approved/rejected`, but the API plan records `approve/reject`.

- **LOW: `create_approval_request` tool appears unused.** Either the graph/node should use it, or it should be dropped from Phase 4 to reduce dead code.

- **LOW: Trace API references `SAFE-06`, but Phase 4 requirements list does not include it.** Probably a typo, but requirement mapping should be corrected.

**Suggestions**

- First add a small spike/test proving the actual LangGraph interrupt contract in this repo: initial `ainvoke`, returned interrupt shape, `aget_state`, and `Command(resume=...)` using `MemorySaver`.

- Store enough resume identity in DB: `agent_runs.thread_id` plus `user_id` is already enough if the approval API reconstructs `_checkpoint_thread_id(requested_by_user, run.thread_id)`. Do not derive checkpoint IDs from `run_id`.

- Resume on both approve and reject. Approved should route to `execute_action`; rejected should route to `final_response`.

- Add update helpers such as `update_agent_run_after_resume()` and append-only `write_agent_steps(..., start_index=existing_count)`.

- Make `approval_gate` idempotent. Either create the approval request before `interrupt()` with a deterministic key, or have the API create it after reading returned interrupt data, then resume with an approval ID stored and validated by state. Avoid non-idempotent DB writes before `interrupt()` unless guarded.

- Update `receive_request` to reset `proposed_action`, `approval_result`, and `action_result`.

- Change `execute_action(state, config: RunnableConfig)` and use the existing session access pattern.

- Update `final_response` to handle:
  - approved + draft created
  - rejected + no write
  - action tool failure
  - approval expired, if surfaced through state

- Combine or order DB migrations: latency columns first, then approval tables, or one Phase 4 migration if the project tolerates it.

- Add indexes for operational queries: `approval_requests(tenant_id, status, expires_at)`, `approval_requests(run_id)`, `action_drafts(run_id)`, and possibly unique `action_drafts(idempotency_key)` or `(tenant_id, idempotency_key)`.

- Use `with_for_update()` in approval decision logic and commit expiry changes before returning 409.

- Strengthen sensitive-data tests: do not only check for keys named `prompt` or `messages`; assert allowed `metrics_json` keys instead.

**Plan Risk Assessment**

- **04-01 Latency Instrumentation:** **MEDIUM** — Useful and bounded, but migration path, `latency_ms` computation, retry semantics, and final_response/non-LLM handling need tightening.

- **04-02 DB Schema + State:** **MEDIUM** — Good structure, but repository concurrency, tenant-safe methods, migration ordering, and state reset are missing.

- **04-03 Approval Gate + Execute Action + Graph:** **HIGH** — This is the core path and has the most correctness risk: DB creation vs interrupt timing, resume validation, node signature, final_response behavior, and stale state.

- **04-04 Approval REST API + Resume:** **HIGH** — Main blockers are interrupt handling, wrong checkpoint thread ID, no reject resume, and missing run update after resume.

- **04-05 Audit Trail API:** **LOW-MEDIUM** — Mostly sound. Needs precise schema mapping, route registration in `main.py`, stricter redaction, and requirement ID cleanup.

- **04-06 Integration Tests:** **MEDIUM** — Good coverage intent, but tests must exercise real LangGraph interrupt/resume behavior rather than over-mocking it.

**Overall Risk: HIGH**

The architecture is viable, but the current plans have high-risk integration assumptions around LangGraph and checkpoint identity. Fix those before implementation and the phase becomes medium risk.

---

## Consensus Summary

### Agreed Strengths
- Phase decomposition and wave ordering are sound
- Safety posture (self-approval block, tenant isolation, idempotency) is correct
- Draft-only write boundary is pragmatic for Phase 4

### Agreed Concerns
1. **LangGraph interrupt/resume contract not verified** — must spike before implementing
2. **Checkpoint thread_id mismatch** — resume will fail with wrong ID format
3. **Reject path incomplete** — graph stays paused, no final_response generated
4. **State reset missing** — stale approval fields leak across turns
5. **Node signature incompatible** — execute_action won't receive session from LangGraph
6. **final_response not updated** — won't mention approval outcomes
7. **Run persistence incomplete** — no update from interrupted → completed after resume

### Divergent Views
(Single reviewer — no divergence to report)
