# Phase 35: Replay and Eval Hardening - Research

**Researched:** 2026-06-29  
**Domain:** Replay, trace authorization, eval gates, contract tests  
**Confidence:** HIGH for existing code surfaces; MEDIUM for exact new artifact filenames because those are planner discretion.

## User Constraints (from 35-CONTEXT.md)

### Locked Decisions

- **D-01:** Phase 35 uses a platform-boundary coverage matrix plus blocking contract tests as the deterministic acceptance layer. The matrix must map each platform boundary to replay events, trace projections, eval gate level, forbidden behavior, and acceptance tests. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-02:** Blocking replay tests must cover event completeness, sequence/order, terminal timeline status, redaction, permission isolation, operation identity where applicable, and forbidden behavior. This is stronger than patching only visible gaps. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-03:** Coverage applies to existing platform boundaries and events. Phase 35 must not re-implement `DecisionEventEnvelopeV1`, create a parallel event envelope, introduce full artifact storage, or add real external action execution. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-04:** Replay remains audit replay, not deterministic LLM/tool/RAG rerun. Replay artifacts must preserve stable refs, reason codes, hashes, versions, safe summaries, and redacted payloads only. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-05:** Keep business-data run, trace, and replay API visibility owner/admin-only in Phase 35. `support`, `manager`, legacy `merchant`, `supervisor`, and `approval_manager` must not read another user's business-data run/trace/replay in this phase. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-06:** Phase 35 should add or harden the proof chain needed for future same-merchant authorization without opening that authorization yet. Proof should include `target_merchant_id` or equivalent target merchant proof, scoped `BusinessFactRefV1` / `BusinessFactResultV1`, proof source, proof status, and fail-closed status for unknown, mixed, denied, invalid, or cross-merchant scopes. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-07:** Negative tests must prove `requested_by.user.merchant_id` is not an acceptable same-merchant authorization approximation for trace/replay access. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-08:** Future manager same-merchant trace/replay visibility is allowed as a later phase only after the proof chain is stable and tested. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-09:** Phase 35 splits eval gates into `dev-contract`, `release`, and `monitoring` levels. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-10:** Only deterministic `dev-contract` gates block Phase 35. Blocking gates include schema validity, platform event coverage, event order, terminal replay timelines, redaction, owner/admin-only permissions, cross-tenant/cross-merchant negatives, forbidden behavior, and release/monitoring manifest format. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-11:** Release gates are Phase 35 artifacts, not hard blockers unless they expose a deterministic forbidden-behavior regression. Release artifacts should include dataset version/hash, coverage manifest hash, command entrypoint, metrics, pass/fail/statistical_gate_not_demonstrated status, and sample-size or coverage gaps. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-12:** Monitoring gates are Phase 35 artifacts, not hard blockers. Monitoring artifacts should define metric/report schemas for replay completeness, drift, false-negative trend, tool deny reasons, RAG no-evidence trend, and memory write quality. Missing production data should be represented as `pending`, `not_applicable`, or `sample_only`, not a Phase 35 blocker. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-13:** Safety, permission, raw payload exposure, unsupported-claim-to-action, stale business fact, invalid evidence scope, or no-evidence-to-action behaviors that can be deterministically tested must be classified as `dev-contract` blocking tests. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-14:** Phase 35 golden and negative datasets prioritize the `dev-contract` blocking gate, not broad statistical release expansion. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-15:** P0 replay terminal golden cases must cover normal completed, interrupted approval-required, resumed, rejected, responded/needs-info, expired, error, and cancelled timelines. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-16:** P0 redaction/exposure negatives must prove replay excludes raw prompt, raw tool payload, ticket/order/refund PII, raw action payload, secrets, and unsafe debug payloads. Replay should contain only redacted payloads, stable refs, reason codes, hashes, versions, and safe summaries. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-17:** P0 permission negatives must cover non-owner `support` / `manager` / `merchant` access denial, cross-tenant 404 behavior, cross-merchant fail-closed behavior, and lack of target merchant / scoped business fact proof. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-18:** P0 action-bound forbidden behavior must cover unsupported claims blocked before risk/approval/action, no-evidence not producing deterministic action recommendations, stale or wrong-scope `BusinessFactRefV1` not entering action paths, invalid-scope evidence not entering action paths, and approval payload hash mismatch not producing action drafts. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-19:** Intent hard negatives, RAG semantic claim-support statistics, and approval/action safety release datasets should receive manifests, coverage gaps, and limited smoke cases in Phase 35, but broad statistical expansion is deferred. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-20:** Phase 35 must not be planned as one broad `35-01-PLAN.md` despite the roadmap placeholder. It spans replay contracts, trace visibility/proof, eval gates, golden datasets, and final verification across multiple service boundaries. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- **D-21:** Planning should split into dependency-ordered plans. A likely shape is: coverage matrix and event/replay contract gaps; trace/replay proof and permission tests; dev-contract eval gate and forbidden-behavior datasets; release/monitoring manifests and report artifacts; final static/focused/eval closure. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]

### Claude's Discretion

- Exact matrix file path and schema are planner discretion, but the matrix must be machine-checkable or test-backed enough to block drift. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Exact event type additions are planner discretion if they use the existing replay-owned event registry and redaction rules. Do not create a parallel event family outside `src/replay/`. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Exact report filenames are planner discretion, but release and monitoring artifacts must be discoverable by future planning/execution agents and must include commands and non-blocking status semantics. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Exact test split is planner discretion, but tests must use `uv run pytest ...` or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid in MOCA. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)

- Broader release dataset expansion for intent hard negatives, RAG claim support, and approval/action safety is deferred to a later eval expansion or release-readiness phase. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Opening manager same-merchant trace/replay visibility is deferred until a later phase can use the Phase 35 proof chain safely. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APF-17 | Replay/trace coverage records platform decisions for trusted context projection, intent/slot policy, memory load/write policy, tool visibility/auth, RAG validation, claim verification, risk/approval, and action draft boundaries. [VERIFIED: .planning/REQUIREMENTS.md] | Existing replay events, trace APIs, platform-boundary tests, and missing matrix gaps are listed below. [VERIFIED: src/replay/validators.py; src/api/routers/traces.py; tests/replay/test_tool_policy_events.py] |
| APF-18 | Contract tests and eval gates distinguish dev-contract, release, and monitoring gates for new platform boundaries, including negative cases for scope leaks, unsupported claims, unsafe action paths, and raw payload exposure. [VERIFIED: .planning/REQUIREMENTS.md] | Existing intent manifests already separate contract and release gates; Phase 35 should replicate that pattern for replay/eval hardening. [VERIFIED: eval/intent/coverage-manifest.v1.json; eval/intent/m6-statistical-gate.v1.json; tests/agent/test_intent_manifest.py] |

## Existing Surfaces

### Replay schema, storage, and event registry

- `ReplayEventV3` and `ReplayResponseV3` are strict Pydantic schemas; replay responses expose `final_status`, `started_at`, `completed_at`, `timeline`, and optional `rag_claim_summary`. [VERIFIED: src/replay/schemas.py]
- `ReplayService.append_event` validates event type, retention class, redacted payload, resource refs, operation pairing, and per-run sequence allocation before persisting `AgentTraceEvent`. [VERIFIED: src/replay/service.py]
- `ReplayService.get_replay` loads an `AgentRun`, orders `AgentTraceEvent` records by `sequence`, builds the replay timeline, and projects events through the V3 schema. [VERIFIED: src/replay/service.py]
- `DecisionEventEnvelopeV1` and `emit_decision_event` are the existing minimal envelope path; event writers should use this path instead of inventing a second envelope. [VERIFIED: src/replay/decision_events.py; docs/contract-spec.md]
- The current replay event registry includes lifecycle, node, tool call, RAG retrieval, LLM call, memory write, approval, action draft, and tool policy event types. [VERIFIED: src/replay/validators.py]
- `AgentTraceEvent` stores replay events in `agent_trace_events`; the ORM check constraint hard-codes the same event-type set, so any new event type needs a model and migration update, not only a Python registry edit. [VERIFIED: src/db/models.py]
- The contract states that observability/replay owns `DecisionEventEnvelopeV1`, replay artifacts, redaction policy, eval artifact refs, and public methods such as `emit_decision_event`, `append_trace_event`, `build_replay_view`, and `record_eval_artifact_ref`. [CITED: docs/contract-spec.md]
- The contract forbids replay by rerunning LLMs and forbids raw prompt, raw tool, PII, and raw action payload persistence in replay artifacts. [CITED: docs/contract-spec.md]

### Trace and replay API authorization

- `/trace` and `/replay` both resolve runs through tenant-scoped lookup and then allow only the run owner or role `admin`; non-owner non-admin users receive 403 after same-tenant lookup. [VERIFIED: src/api/routers/traces.py]
- `agent_runs` status, evidence, and stream APIs use equivalent owner/admin-only guards for business-data run visibility. [VERIFIED: src/api/routers/agent_runs.py]
- Existing replay API tests cover owner access, admin access, cross-tenant 404, same-tenant non-owner 403, and denial for `support`, `manager`, `merchant`, `supervisor`, and `approval_manager` roles. [VERIFIED: tests/replay/test_replay_api.py]
- Existing trace API tests cover same visibility rules and verify raw user input, final response, and secrets are not projected in trace output. [VERIFIED: tests/test_trace_api.py]
- Existing agent-run API tests cover status/evidence/stream visibility and include static checks that authorization guards do not use `target_merchant_context` yet. [VERIFIED: tests/test_agent_runs_api.py]
- The normative contract says business-data run/evidence/trace/replay access is owner/admin-only until a later phase proves same-merchant access through target merchant or scoped `BusinessFactRefV1`; it also forbids using `requested_by.user.merchant_id` as the approximation. [CITED: docs/contract-spec.md]

### Redaction and sanitization

- `guard_redacted_payload` recursively rejects forbidden keys including raw prompt, raw args, raw payload, raw tool output, secrets, credentials, PII, source document/parser/OCR fields, and unsafe tool descriptor internals. [VERIFIED: src/replay/validators.py]
- `guard_resource_refs` applies the same unsafe-key discipline to replay resource references. [VERIFIED: src/replay/validators.py]
- `ReplayService.project_event` sanitizes RAG/claim payloads before V3 projection and validates the resulting `ReplayEventV3`. [VERIFIED: src/replay/service.py; src/agent/rag_claim_summary.py]
- Replay redaction tests verify every registered event has a retention classification and verify append/projection rejection for unsafe payload keys. [VERIFIED: tests/replay/test_replay_redaction_retention.py]
- Tool policy replay tests verify low-payload tool policy events and reject raw descriptor or args payloads. [VERIFIED: tests/replay/test_tool_policy_events.py]
- Approval event emission has an additional approval-event metadata/resource-ref/redacted-payload guard. [VERIFIED: src/approvals/events.py]
- Action draft event emission records safe action type, demo execution mode, external-side-effect false, hashes, refs, and draft outcome; it does not emit raw proposed action payloads. [VERIFIED: src/actions/service.py]
- Memory write event emission records lifecycle/status refs and bounded counts/status details rather than raw memory content. [VERIFIED: src/agent/nodes/memory_write.py]

### Business fact and merchant proof fields

- `BusinessFactRefV1` currently carries tenant, source system, resource type, resource id/version, freshness timestamp, and retrieved timestamp; it does not currently carry explicit `proof_status` or `proof_source` fields. [VERIFIED: src/tools/contracts.py]
- `BusinessFactResultV1` currently carries tenant, status, fact payload, business fact refs, resource version, freshness, source system, `scope_check_result`, missing facts, and safe errors. [VERIFIED: src/business/schemas.py]
- `BusinessFactService` returns `permission_denied` without leaking resource existence when merchant scope does not allow the read. [VERIFIED: src/business/service.py]
- `project_target_merchant_context` produces a safe `target_merchant_context.v1` projection with status/source/reason codes and optional ref count, and tests verify spoofed resolved status is downgraded and raw ids/query strings are not leaked. [VERIFIED: src/agent/merchant_context.py; tests/agent/test_trace.py]
- Approval/action binding code already binds target merchant, business fact refs, verified evidence refs, claim verification refs, risk decision refs, payload hashes, and safety snapshots for action safety. [VERIFIED: src/approvals/schemas.py; src/agent/nodes/assess_risk_and_approval.py; src/actions/service.py]
- Existing Phase 34 tests cover target merchant binding persistence, missing target merchant fail-closed behavior, approval/action binding validation, and payload/snapshot mismatch rejection. [VERIFIED: tests/agent/test_nodes/test_assess_risk_and_approval.py; tests/actions/test_phase34_action_draft_bindings.py; tests/actions/test_action_draft_v2.py]

### Eval datasets, manifests, runners, and gate levels

- `eval/intent/coverage-manifest.v1.json` is an existing blocking phase-contract manifest with a dataset hash and manifest hash. [VERIFIED: eval/intent/coverage-manifest.v1.json]
- `eval/intent/m6-statistical-gate.v1.json` is an existing release gate manifest that records incomplete coverage and `statistical_gate_not_demonstrated` instead of blocking an earlier phase on missing release sample volume. [VERIFIED: eval/intent/m6-statistical-gate.v1.json]
- `tests/agent/test_intent_manifest.py` validates intent manifest hashes, contract-vs-release separation, and Wilson release-gate result fields. [VERIFIED: tests/agent/test_intent_manifest.py]
- `scripts/eval_agent.py` runs deterministic agent eval cases using `FakeLLM` and writes an agent eval report under `evaluation/reports`. [VERIFIED: scripts/eval_agent.py]
- `scripts/eval_all.py` combines RAG and agent eval results into `evaluation/reports/latest.json` and `.md`. [VERIFIED: scripts/eval_all.py]
- The Makefile eval targets use `uv run python ...`, and the project test target uses `uv run pytest`. [VERIFIED: Makefile]
- The eval plan defines `dev-contract`, `release`, and `monitoring` gate levels, and it states that deterministic contract replay tests belong in the blocking dev-contract layer while broader statistical gates can report release readiness. [CITED: docs/eval-test-plan.md]

### Terminal statuses and golden timeline surfaces

- `RunLifecycleService` emits `run_status_changed` events for running, interrupted, resumed, completed, rejected, expired, error, and cancelled lifecycle transitions. [VERIFIED: src/replay/lifecycle.py]
- Existing lifecycle tests cover normal completion, approval interruption, resume plus completion, responded/needs-info remaining interrupted, rejection, expiry, error, cancellation, and repository status writes through lifecycle helpers. [VERIFIED: tests/replay/test_lifecycle_finalizer.py]
- The eval plan requires at least one golden replay timeline per terminal status. [CITED: docs/eval-test-plan.md]
- The eval plan lists replay timelines for normal, interrupted/resumed, error, cancelled, responded, and expired runs. [CITED: docs/eval-test-plan.md]

## Gaps/Risks

- The roadmap still has a single placeholder `35-01-PLAN.md`, but Phase 35 spans replay contracts, API authorization/proof, eval gates, golden datasets, and final closure; planning it as one broad plan violates the project granularity rule. [VERIFIED: .planning/ROADMAP.md; AGENTS.md; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- There is no current machine-checkable Phase 35 coverage matrix mapping platform boundaries to event type, trace projection, gate level, forbidden behavior, and acceptance test path. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md; rg inspection of eval/ and tests/replay]
- The current event registry has generic node/lifecycle/tool/RAG/memory/action/approval/tool-policy events, but it does not have dedicated registered event types named for trusted context projection, intent policy, slot policy, business fact read/scope/freshness, RAG validation, claim verification, or risk decision. [VERIFIED: src/replay/validators.py]
- If the planner chooses to add dedicated event types, the plan must update `src/replay/validators.py`, `src/db/models.py`, and the matching Alembic migration/check constraint; otherwise tests can pass at the service layer but fail when persisted against the DB. [VERIFIED: src/replay/validators.py; src/db/models.py]
- Existing owner/admin API tests are strong, but Phase 35 still needs explicit proof-chain tests showing same-merchant authorization remains closed while proof fields become available for future phases. [VERIFIED: tests/replay/test_replay_api.py; tests/test_trace_api.py; docs/contract-spec.md]
- `BusinessFactRefV1` and `BusinessFactResultV1` provide scoped facts and scope-check status, but explicit proof status/source fields requested by Phase 35 are not present on `BusinessFactRefV1` today. [VERIFIED: src/tools/contracts.py; src/business/schemas.py; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Existing redaction guards are necessary but not sufficient for Phase 35 acceptance; P0 negatives must also seed representative raw prompt, raw tool payload, ticket/order/refund PII, raw action payload, secrets, and debug payload strings through API-level replay/trace projections. [VERIFIED: src/replay/validators.py; tests/replay/test_replay_redaction_retention.py; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Terminal lifecycle behavior is tested at the lifecycle/service layer, but the current inspection did not find a matrix of P0 golden replay API timelines for normal completed, interrupted approval-required, resumed, rejected, responded/needs-info, expired, error, and cancelled. [VERIFIED: tests/replay/test_lifecycle_finalizer.py; docs/eval-test-plan.md]
- Existing eval manifests under `eval/intent/` show the desired contract-vs-release pattern, but Phase 35 needs replay/eval-specific manifests for platform-boundary coverage, release readiness, and monitoring schema/status semantics. [VERIFIED: eval/intent/coverage-manifest.v1.json; eval/intent/m6-statistical-gate.v1.json; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- `docs/evaluation.md` and eval scripts use `evaluation/golden/...` and `evaluation/reports/...`, while intent manifests live under `eval/intent/`; planners should choose Phase 35 artifact paths deliberately and document them so future agents do not split manifest discovery across hidden locations. [VERIFIED: docs/evaluation.md; scripts/eval_agent.py; scripts/eval_all.py; eval/intent/coverage-manifest.v1.json]
- Any plan that touches spec-versus-implementation gaps must not silently reinterpret `docs/contract-spec.md`; MOCA rules require either a spec correction or an MVP scope/decision note when implementation intentionally differs from the normative contract. [VERIFIED: CLAUDE.md; AGENTS.md]

## Recommended Plan Slices

### 35-01 - Coverage matrix and replay contract inventory

**Goal:** Create the deterministic acceptance map before changing behavior. [PLANNING RECOMMENDATION]

Likely files:
- New machine-checkable artifact such as `eval/replay/phase35-coverage-matrix.v1.json` or `docs/replay-eval-coverage-matrix.v1.json`. [PLANNING RECOMMENDATION]
- New tests such as `tests/replay/test_phase35_coverage_matrix.py`. [PLANNING RECOMMENDATION]
- `src/replay/validators.py`, `src/db/models.py`, and Alembic migration only if this slice decides to add missing event types. [VERIFIED: src/replay/validators.py; src/db/models.py]

Required matrix rows:
- Trusted context projection, intent policy, slot policy, memory load policy, memory write policy, tool visibility, runtime tool auth, business fact read/scope/freshness, RAG validation, claim verification, risk decision, approval lifecycle, action draft. [VERIFIED: .planning/REQUIREMENTS.md; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- For each row: replay event(s), trace projection, eval gate level, forbidden behavior, acceptance test command/path, and whether the row is implemented by existing generic events or requires a new registered event. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]

Acceptance focus:
- Matrix test fails when a platform boundary has no replay event/projection/gate/test mapping. [PLANNING RECOMMENDATION]
- New event types, if any, are registered in both Python validation and database constraints. [VERIFIED: src/replay/validators.py; src/db/models.py]

### 35-02 - Trace/replay proof fields and owner/admin-only permission hardening

**Goal:** Make future same-merchant authorization proof inspectable without opening same-merchant access in Phase 35. [PLANNING RECOMMENDATION]

Likely files:
- `src/api/routers/traces.py` and `src/api/routers/agent_runs.py` for API projection or static guard assertions if needed. [VERIFIED: src/api/routers/traces.py; src/api/routers/agent_runs.py]
- `src/agent/merchant_context.py`, `src/business/schemas.py`, or a new replay-safe projection helper if proof fields are added outside auth guards. [VERIFIED: src/agent/merchant_context.py; src/business/schemas.py]
- `tests/replay/test_replay_api.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, and `tests/agent/test_trace.py`. [VERIFIED: tests/replay/test_replay_api.py; tests/test_trace_api.py; tests/test_agent_runs_api.py; tests/agent/test_trace.py]

Acceptance focus:
- Owner/admin-only visibility still passes; `support`, `manager`, `merchant`, `supervisor`, and `approval_manager` still cannot read another user's business-data trace/replay. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md; tests/replay/test_replay_api.py]
- Cross-tenant remains 404, same-tenant non-owner remains 403, and no test opens manager same-merchant read access. [VERIFIED: src/api/routers/traces.py; tests/replay/test_replay_api.py]
- Proof projection includes target merchant proof, scoped business fact refs/results, proof source, proof status, and fail-closed states for unknown, mixed, denied, invalid, or cross-merchant proof. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Negative tests prove `requested_by.user.merchant_id` and `target_merchant_context` are not used as authorization shortcuts. [CITED: docs/contract-spec.md; VERIFIED: tests/test_agent_runs_api.py]

### 35-03 - Golden replay timelines, operation identity, and redaction negatives

**Goal:** Turn lifecycle/replay behavior into golden dev-contract tests for every P0 terminal timeline. [PLANNING RECOMMENDATION]

Likely files:
- `tests/replay/test_phase35_terminal_timelines.py` or fixtures under `tests/replay/fixtures/phase35_timelines/`. [PLANNING RECOMMENDATION]
- `tests/replay/test_lifecycle_finalizer.py`, `tests/replay/test_operation_pairing.py`, `tests/replay/test_replay_redaction_retention.py`, and `tests/replay/test_replay_api.py`. [VERIFIED: tests/replay/test_lifecycle_finalizer.py; tests/replay/test_operation_pairing.py; tests/replay/test_replay_redaction_retention.py; tests/replay/test_replay_api.py]
- `src/replay/lifecycle.py`, `src/replay/service.py`, and `src/replay/validators.py` only for fixes discovered by the golden tests. [VERIFIED: src/replay/lifecycle.py; src/replay/service.py; src/replay/validators.py]

Acceptance focus:
- Golden cases cover normal completed, interrupted approval-required, resumed, rejected, responded/needs-info, expired, error, and cancelled. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md; docs/eval-test-plan.md]
- Each golden timeline asserts sequence/order, final/current status semantics, pairing status where operation ids exist, and no raw prompt/tool/PII/action/debug payload exposure. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Replay remains audit replay; no test should rerun LLMs, tools, RAG, or external actions to build the timeline. [CITED: docs/contract-spec.md]

### 35-04 - Dev-contract eval gate and forbidden-behavior datasets

**Goal:** Make deterministic forbidden behavior block Phase 35 through pytest-backed contract gates. [PLANNING RECOMMENDATION]

Likely files:
- New manifest such as `eval/replay/dev-contract-manifest.v1.json`. [PLANNING RECOMMENDATION]
- New tests such as `tests/eval/test_phase35_replay_eval_gates.py` or `tests/architecture/test_phase35_replay_eval_boundaries.py`. [PLANNING RECOMMENDATION]
- Existing suites around RAG/claim, approval/risk, and action draft: `tests/agent/test_nodes/test_rag_context_build.py`, `tests/agent/test_nodes/test_claim_verify.py`, `tests/agent/test_nodes/test_assess_risk_and_approval.py`, `tests/actions/test_phase34_action_draft_bindings.py`, and `tests/actions/test_action_draft_v2.py`. [VERIFIED: listed test files]

Acceptance focus:
- Deterministic dev-contract blockers include unsupported claims blocked before risk/approval/action, no-evidence not producing action recommendations, stale or wrong-scope business fact refs not entering action paths, invalid-scope evidence not entering action paths, approval payload hash mismatch not producing action drafts, scope leak negatives, and raw payload exposure negatives. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Release and monitoring manifest format validation can be a dev-contract blocker, but missing release sample volume or missing production monitoring data is not a Phase 35 blocker. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md; docs/eval-test-plan.md]

### 35-05 - Release and monitoring artifact manifests

**Goal:** Artifactize future release/monitoring gates without blocking Phase 35 on unavailable production-scale data. [PLANNING RECOMMENDATION]

Likely files:
- `eval/replay/release-gate.v1.json`, `eval/replay/monitoring-gate.v1.json`, or equivalent discoverable files. [PLANNING RECOMMENDATION]
- `docs/evaluation.md` if the artifact discovery path or command entrypoint changes. [VERIFIED: docs/evaluation.md]
- Optional script following `scripts/eval_agent.py` / `scripts/eval_all.py` report patterns if static manifests are insufficient. [VERIFIED: scripts/eval_agent.py; scripts/eval_all.py]

Acceptance focus:
- Release artifact includes dataset version/hash, coverage manifest hash, command entrypoint, metrics, pass/fail/statistical_gate_not_demonstrated status, and coverage/sample gaps. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Monitoring artifact includes replay completeness, drift, false-negative trend, tool deny reasons, RAG no-evidence trend, memory write quality, and status values such as `pending`, `not_applicable`, or `sample_only`. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Manifest tests validate schema and status semantics but do not require production telemetry. [VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]

### 35-06 - Final static/focused/eval closure

**Goal:** Prove APF-17/APF-18 are mapped, tested, and documented without broadening Phase 35 scope. [PLANNING RECOMMENDATION]

Likely files:
- `docs/evaluation.md` or a Phase 35 decision note only if needed to describe artifact paths and gate semantics. [VERIFIED: docs/evaluation.md; CLAUDE.md]
- No real external execution files should be introduced. [VERIFIED: .planning/REQUIREMENTS.md; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]

Acceptance focus:
- Final plan runs focused replay/API/eval/architecture commands, checks APF-17/APF-18 traceability, confirms no broad `35-01-PLAN.md`, and records any spec-vs-MVP deltas. [VERIFIED: .planning/REQUIREMENTS.md; AGENTS.md; CLAUDE.md]

## Verification Commands

Use only repository-scoped test entrypoints; bare `pytest` and bare `python -m pytest` are invalid in MOCA. [VERIFIED: AGENTS.md; CLAUDE.md]

Current focused suites:

```bash
uv run pytest tests/replay/test_decision_events.py tests/replay/test_replay_service.py tests/replay/test_sequence_allocator.py tests/replay/test_operation_pairing.py -q
```

```bash
uv run pytest tests/replay/test_replay_redaction_retention.py tests/replay/test_tool_policy_events.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_replay_api.py -q
```

```bash
uv run pytest tests/test_trace_api.py tests/test_agent_runs_api.py -q
```

```bash
uv run pytest tests/agent/test_trace.py tests/agent/test_memory_write_node.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q
```

```bash
uv run pytest tests/actions/test_phase34_action_draft_bindings.py tests/actions/test_action_draft_v2.py tests/approvals/test_events.py tests/test_approval_api.py -q
```

```bash
uv run pytest tests/agent/test_intent_manifest.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_tool_boundaries.py -q
```

Likely new Phase 35 commands:

```bash
uv run pytest tests/replay/test_phase35_coverage_matrix.py -q
```

```bash
uv run pytest tests/replay/test_phase35_terminal_timelines.py tests/replay/test_phase35_trace_replay_permissions.py -q
```

```bash
uv run pytest tests/eval/test_phase35_replay_eval_gates.py tests/architecture/test_phase35_replay_eval_boundaries.py -q
```

Eval/report smoke commands:

```bash
uv run python scripts/eval_agent.py --mode ci
```

```bash
uv run python scripts/eval_all.py --agent-mode ci
```

Lint/static command:

```bash
uv run ruff check src/ tests/ scripts/
```

## Planning Notes

### Architectural responsibility map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Replay event schema, sequence, redaction, and projection | API / Backend | Database / Storage | `src/replay` owns event validation/projection and `agent_trace_events` persists replay records. [VERIFIED: src/replay/service.py; src/db/models.py] |
| Trace/replay visibility | API / Backend | Auth / Trusted context | API routers enforce tenant lookup plus owner/admin visibility. [VERIFIED: src/api/routers/traces.py; src/api/routers/agent_runs.py] |
| Future same-merchant proof projection | API / Backend | Business domain service | Business facts and target merchant projection provide proof inputs, but Phase 35 must not open authorization. [VERIFIED: src/business/schemas.py; src/agent/merchant_context.py; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md] |
| Eval gate manifests and reports | Test/eval tooling | Documentation | Existing manifests and scripts live under `eval/`, `scripts/`, `evaluation/reports`, and docs. [VERIFIED: eval/intent/coverage-manifest.v1.json; scripts/eval_all.py; docs/evaluation.md] |
| Golden replay timelines | Test suite | Replay service | Existing lifecycle tests cover statuses; Phase 35 should add golden replay API fixtures/assertions. [VERIFIED: tests/replay/test_lifecycle_finalizer.py; docs/eval-test-plan.md] |

### Project constraints from CLAUDE.md / AGENTS.md

- Any MOCA local debugging, startup, validation, UI/API/RAG/agent/memory/tool-call issue discovered during execution must be appended after handling to `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese with symptom, reproduction, evidence, root-cause judgment, handling, remaining issue, and next entry point. [VERIFIED: CLAUDE.md; AGENTS.md]
- Phase-level plans that span multiple service boundaries, waves, or verification gates must be split into multiple numbered plans; a single broad plan across contracts, migrations, compatibility, callers, security, and final validation is a planning blocker. [VERIFIED: AGENTS.md]
- GSD plan checking plus independent Codex review is required for phase-level planning and larger changes. [VERIFIED: CLAUDE.md; AGENTS.md]
- `docs/contract-spec.md` is the normative contract source, but it describes target contract semantics rather than automatically proving implementation reality; implementation divergence requires a spec correction or MVP scope/decision record. [VERIFIED: CLAUDE.md; AGENTS.md]
- MOCA tests must use `uv run pytest ...` or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid validation. [VERIFIED: AGENTS.md]

### Source hierarchy and confidence

- Existing replay, API, authorization, redaction, proof, lifecycle, and eval surfaces were verified from repository source and tests. [VERIFIED: src/replay/service.py; src/api/routers/traces.py; tests/replay/test_replay_api.py; eval/intent/coverage-manifest.v1.json]
- Gate-level and terminal-timeline requirements were checked against `docs/eval-test-plan.md` and Phase 35 context. [CITED: docs/eval-test-plan.md; VERIFIED: .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
- Exact new artifact filenames are recommendations, not existing facts; planners may choose different paths if the artifacts remain discoverable and test-backed. [PLANNING RECOMMENDATION]

### Open questions for planning

1. Should missing boundary coverage be represented by new dedicated replay event types, or by existing generic `node_completed` / `run_status_changed` / tool-policy events plus stricter payload conventions? [VERIFIED: src/replay/validators.py; .planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md]
2. Should proof status/source live on `BusinessFactRefV1`, `BusinessFactResultV1`, `target_merchant_context.v1`, or a replay-only proof projection? [VERIFIED: src/tools/contracts.py; src/business/schemas.py; src/agent/merchant_context.py]
3. Should Phase 35 replay/eval manifests live under `eval/replay/` to match `eval/intent/`, or under `evaluation/` to match existing report/golden paths? [VERIFIED: eval/intent/coverage-manifest.v1.json; docs/evaluation.md; scripts/eval_agent.py]

## Sources

- `.planning/phases/35-replay-and-eval-hardening/35-CONTEXT.md` - Phase decisions, constraints, refs, and plan split. [VERIFIED]
- `.planning/ROADMAP.md` - Phase 35 scope and APF references. [VERIFIED]
- `.planning/REQUIREMENTS.md` - APF-17/APF-18 and out-of-scope boundaries. [VERIFIED]
- `CLAUDE.md` and `AGENTS.md` - project workflow, plan granularity, spec discipline, and validation command rules. [VERIFIED]
- `docs/contract-spec.md` - normative replay, authorization, business fact, and no-raw-payload contracts. [CITED]
- `docs/eval-test-plan.md` - gate levels, replay terminal golden expectations, and release semantics. [CITED]
- `docs/target-agent-platform-architecture-plan.md` - Phase 35 target for replay/eval hardening. [CITED]
- `src/replay/*`, `src/api/routers/*`, `src/business/*`, `src/agent/*`, `src/actions/*`, `src/approvals/*` - implementation surfaces. [VERIFIED]
- `tests/replay/*`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, `tests/agent/*`, `tests/actions/*`, `tests/architecture/*` - current verification surfaces. [VERIFIED]
- `eval/intent/*`, `scripts/eval_*.py`, `docs/evaluation.md`, `Makefile` - eval manifest and runner patterns. [VERIFIED]
