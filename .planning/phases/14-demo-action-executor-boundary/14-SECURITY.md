---
phase: 14
slug: demo-action-executor-boundary
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-16
---

# Phase 14 - Security

Per-phase security contract for Phase 14 demo action executor boundary.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| ORM/migration -> PostgreSQL | Action draft schema changes affect durable draft persistence. | Draft identity, binding hashes, outcome flags |
| Graph/tool caller -> ActionService | Caller state and tool args are untrusted for draft authorization and idempotency. | Proposed action payload, approval refs, safety snapshot refs |
| ActionService -> database | Service writes durable draft rows and events only after binding checks pass. | ActionDraft rows, AgentTraceEvent rows |
| Approval API -> graph resume | Trusted approval decisions may resume draft creation. | approval_result.v1, configured tool permission |
| Trace API -> client/auditor | Trace read model must expose useful audit refs without raw payloads. | draft_outcome, safe action draft refs |
| Compatibility surfaces -> Phase 15 | execute_action/action_result compatibility must remain quarantined and temporary. | Legacy node name and deprecated output fields |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| 14-01:T14-01 | Elevation of Privilege | `009_action_draft_v2.py` | mitigate | Migration/table tests assert no Phase 17 execution/outbox/reconciliation/compensation surfaces. Evidence: `tests/actions/test_action_draft_v2.py:214`, `tests/actions/test_action_draft_v2.py:232`. | closed |
| 14-01:T14-02 | Tampering | `ActionDraft` binding columns | mitigate | Binding fields are first-class ORM/migration columns. Evidence: `src/db/models.py:597`, `src/db/models.py:598`, `src/db/models.py:599`, `src/db/migrations/versions/009_action_draft_v2.py:33`. | closed |
| 14-01:T14-03 | Tampering | `ActionDraft.target_id` | mitigate | `target_id` is persisted and service rejects missing target before draft creation. Evidence: `src/db/models.py:595`, `src/actions/service.py:80`. | closed |
| 14-01:T14-04 | Spoofing / Repudiation | `DraftOutcomeV1` | mitigate | Outcome contract is `draft_outcome.v1`, `not_executed_demo`, `external_side_effect=False`. Evidence: `src/actions/schemas.py:9`, `src/actions/schemas.py:12`, `src/actions/schemas.py:13`, `src/actions/schemas.py:14`. | closed |
| 14-01:T14-05 | Information Disclosure | `draft_outcome` / future trace projection | mitigate | `draft_outcome` carries outcome refs/status only; trace/event tests reject raw payload exposure. Evidence: `src/actions/schemas.py:12`, `tests/test_trace_api.py:53`, `tests/test_trace_api.py:57`, `tests/agent/test_events.py:273`. | closed |
| 14-01:T14-06 | Elevation of Privilege | `execute_action` compatibility alias | mitigate | Retained path is a delegation-only shim with Phase 15 removal gate. Evidence: `src/agent/nodes/execute_action.py:8`, `tests/architecture/test_action_draft_boundaries.py:71`. | closed |
| 14-02:T14-01 | Elevation of Privilege | `ActionService` | mitigate | Service persists drafts only and returns `external_side_effect=False`; external execution surfaces are covered by negative tests. Evidence: `src/actions/service.py:116`, `src/actions/service.py:259`, `tests/actions/test_action_draft_v2.py:214`. | closed |
| 14-02:T14-02 | Tampering | `ActionDraftRepository.create_or_get` | mitigate | Existing-key reuse checks tenant/run/action/target/payload/snapshot binding and raises conflict on mismatch. Evidence: `src/repositories/action_draft_repo.py:42`, `src/repositories/action_draft_repo.py:52`, `src/repositories/action_draft_repo.py:98`, `tests/actions/test_action_draft_v2.py:272`. | closed |
| 14-02:T14-03 | Tampering | `ActionService.create_coupon_grant_draft` | mitigate | Missing target id fails closed; no unknown fallback is used for service idempotency. Evidence: `src/actions/service.py:76`, `src/actions/service.py:80`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:282`. | closed |
| 14-02:T14-04 | Spoofing / Repudiation | service/tool result | mitigate | Canonical success carries `draft_outcome` with not-executed semantics and compatibility `action_result` is not success. Evidence: `src/actions/service.py:160`, `src/actions/service.py:346`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:226`. | closed |
| 14-02:T14-05 | Information Disclosure | service/tool result | mitigate | Tool is node-only; external trace/read projections exclude raw payload. Plan 14-07 intentionally validates internal `ActionDraftV2Data` with `proposed_action`, so closure is based on no external read/trace exposure. Evidence: `src/tools/catalog.py:214`, `src/tools/catalog.py:219`, `tests/test_trace_api.py:53`, `tests/test_trace_api.py:198`. | closed |
| 14-02:T14-06 | Elevation of Privilege | compatibility path | mitigate | `execute_action` is a quarantined shim and source imports of it outside the shim are forbidden. Evidence: `src/agent/nodes/execute_action.py:8`, `tests/architecture/test_action_draft_boundaries.py:121`. | closed |
| 14-02:T14-07 | Tampering | `receive_request` state reset | mitigate | `AgentState` defines draft fields and `receive_request` resets them to `None` each turn. Evidence: `src/agent/state.py:105`, `src/agent/nodes/receive_request.py:59`, `tests/agent/test_nodes/test_receive_request.py:37`. | closed |
| 14-03:T14-01 | Elevation of Privilege | `src/agent/graph.py` | mitigate | Graph registers/routes only canonical `action_draft`; no `execute_action` graph node. Evidence: `src/agent/graph.py:23`, `src/agent/graph.py:131`, `src/agent/graph.py:174`, `tests/architecture/test_action_draft_boundaries.py:109`. | closed |
| 14-03:T14-02 | Tampering | `action_draft` node -> ActionService | mitigate | Node passes Phase 13 binding refs to tool/service and service constructs final key/reuse checks. Evidence: `src/agent/nodes/action_draft.py:223`, `src/tools/executors/action.py:41`, `src/actions/service.py:108`. | closed |
| 14-03:T14-03 | Tampering | `action_draft` node args | mitigate | Node passes proposed action; service enforces missing-target validation. Evidence: `src/agent/nodes/action_draft.py:224`, `src/actions/service.py:76`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:282`. | closed |
| 14-03:T14-04 | Spoofing / Repudiation | node/state output | mitigate | Node output uses `draft_outcome` and final/API consumers use draft outcome semantics. Evidence: `src/agent/nodes/action_draft.py:132`, `src/api/routers/approvals.py:552`, `src/agent/nodes/final_response.py:134`. | closed |
| 14-03:T14-05 | Information Disclosure | node trace step | mitigate | Node trace step records node/status/tool only; event payload uses safe refs. Evidence: `src/agent/nodes/action_draft.py:48`, `src/agent/nodes/action_draft.py:245`, `src/actions/service.py:253`. | closed |
| 14-03:T14-06 | Elevation of Privilege | `src/agent/nodes/execute_action.py` | mitigate | Compatibility shim is owned, delegation-only, and has Phase 15 removal gate/date. Evidence: `src/agent/nodes/execute_action.py:8`, `src/agent/nodes/execute_action.py:13`, `tests/architecture/test_action_draft_boundaries.py:71`. | closed |
| 14-03:T14-07 | Spoofing / Repudiation | `action_result` compatibility | mitigate | Static tests forbid new `action_result.status == "success"` dependencies; retained compatibility is draft-only and gated for Phase 15. Evidence: `src/agent/nodes/action_draft.py:37`, `src/agent/nodes/action_draft.py:78`, `tests/architecture/test_action_draft_boundaries.py:145`. | closed |
| 14-04:T14-04-01 | Spoofing / Repudiation | `src/api/routers/approvals.py` | mitigate | Approval resume uses explicit `draft_outcome` not-executed semantics and fails invalid outcomes. Evidence: `src/api/routers/approvals.py:530`, `src/api/routers/approvals.py:552`, `tests/test_approval_api.py:399`, `tests/test_approval_api.py:423`. | closed |
| 14-04:T14-04-02 | Spoofing / Repudiation | `src/agent/nodes/final_response.py` | mitigate | Final wording says draft created and no external action executed; tests block external-success phrases. Evidence: `src/agent/nodes/final_response.py:9`, `src/agent/nodes/final_response.py:153`, `tests/agent/test_nodes/test_final_response.py:8`, `tests/agent/test_nodes/test_final_response.py:235`. | closed |
| 14-04:T14-04-03 | Elevation of Privilege | API/final compatibility reads | mitigate | API/final consumers do not use deprecated `action_result` as success authority. Evidence: `tests/test_approval_api.py:454`, `tests/agent/test_nodes/test_final_response.py:159`, `tests/architecture/test_action_draft_boundaries.py:145`. | closed |
| 14-05:T14-05-01 | Information Disclosure | `AgentTraceEvent` | mitigate | `action_draft_created` uses safe refs/redacted payload and tests reject raw payload/tool args. Evidence: `src/actions/service.py:253`, `src/actions/service.py:259`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:598`, `tests/agent/test_events.py:273`. | closed |
| 14-05:T14-05-02 | Spoofing / Repudiation | `MINIMAL_EVENT_TYPES` | mitigate | Demo registers only `action_draft_created`; action execution events are not registered/emittable. Evidence: `src/agent/events.py:38`, `tests/agent/test_events.py:151`, `tests/agent/test_events.py:157`, `tests/agent/test_events.py:288`. | closed |
| 14-05:T14-05-03 | Information Disclosure | `/trace` read model | mitigate | Trace output includes `draft_outcome` and excludes raw `ActionDraft.payload`. Evidence: `src/api/routers/traces.py:66`, `src/repositories/trace_repo.py:106`, `tests/test_trace_api.py:53`, `tests/test_trace_api.py:198`. | closed |
| 14-06:T14-06-01 | Elevation of Privilege | final verification / architecture tests | mitigate | Negative tests assert no execution/outbox/reconciliation/compensation tables/imports/events. Evidence: `tests/actions/test_action_draft_v2.py:214`, `tests/architecture/test_action_draft_boundaries.py:135`, `tests/agent/test_events.py:157`. | closed |
| 14-06:T14-06-02 | Spoofing / Repudiation | `action_result` compatibility | mitigate | Static tests forbid new `action_result.status == "success"` dependencies and coverage records Phase 15 gate/date. Evidence: `tests/architecture/test_action_draft_boundaries.py:145`, `.planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md:61`. | closed |
| 14-06:T14-06-03 | Elevation of Privilege | `execute_action` compatibility shim | mitigate | Coverage records owner/removal gate; static tests forbid new imports and prove canonical path. Evidence: `.planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md:60`, `tests/architecture/test_action_draft_boundaries.py:109`, `tests/architecture/test_action_draft_boundaries.py:121`. | closed |
| 14-06:T14-06-04 | Information Disclosure | trace/event final gates | mitigate | Final gates reject raw payload trace/event output and action execution event names. Evidence: `tests/agent/test_events.py:273`, `tests/agent/test_events.py:288`, `tests/test_trace_api.py:198`. | closed |
| 14-07:T-14-07-01 | Tampering | `ActionService.create_coupon_grant_draft` | mitigate | Service recomputes canonical payload hash and rejects mismatch before persistence. Evidence: `src/actions/service.py:82`, `src/actions/service.py:91`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:446`. | closed |
| 14-07:T-14-07-02 | Tampering / Elevation of Privilege | `_validate_action_binding` no-approval branch | mitigate | Omitted approval fails closed with `AUTO_ALLOWED_BINDING_REQUIRED`; tests assert no draft rows. Evidence: `src/actions/service.py:202`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:309`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:405`. | closed |
| 14-07:T-14-07-03 | Elevation of Privilege | `src/agent/nodes/action_draft.py` permissions | mitigate | Node passes configured permissions only; manager returns `PERMISSION_REQUIRED` before executor dispatch. Evidence: `src/agent/nodes/action_draft.py:195`, `src/tools/manager.py:85`, `tests/test_execute_action.py:151`. | closed |
| 14-07:T-14-07-04 | Denial of Service | `_build_idempotency_key` vs `String(256)` | mitigate | Raw keys are preserved up to 256 chars; overlong keys use deterministic `key_sha256` bounded material. Evidence: `src/actions/service.py:287`, `src/actions/service.py:300`, `tests/agent/test_tools/test_create_coupon_grant_draft.py:523`. | closed |
| 14-07:T-14-07-05 | Information Disclosure | action draft trace/read surfaces | accept | Accepted because Plan 14-07 added no trace/read fields; baseline trace/event redaction tests remain in force. Evidence: Accepted Risks Log `AR-14-07-05`; `tests/test_trace_api.py:53`, `tests/test_trace_api.py:198`, `tests/agent/test_events.py:273`. | closed |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-14-07-05 | 14-07:T-14-07-05 | Plan 14-07 did not add trace/read fields. Phase 14 baseline tests prove `/trace` excludes raw `ActionDraft.payload` and `action_draft_created` events reject raw payload/tool args. Internal service projection includes `proposed_action` by validated `ActionDraftV2Data`, but external trace/read surfaces remain redacted. | GSD security auditor | 2026-06-16 |

## Unregistered Flags

None. `## Threat Flags` sections in Phase 14 summaries report no new unregistered attack surface; no summary flag required a new threat mapping.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-16 | 35 | 35 | 0 | GSD security auditor |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-16
