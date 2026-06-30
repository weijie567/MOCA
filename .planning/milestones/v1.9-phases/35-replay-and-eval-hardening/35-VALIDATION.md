---
phase: 35-replay-and-eval-hardening
nyquist_compliant: true
apf_17_status: covered
apf_18_status: covered
---

# Phase 35 Validation

Final closure evidence for Phase 35 replay and eval hardening. This artifact records the exact focused/static/eval gates used to close APF-17 and APF-18 without adding runtime behavior, external execution, outbox, reconciliation, physical microservice deployment, or replay-by-rerun scope.

## Command Evidence

| Gate | Command | Exit | Observed result |
| --- | --- | --- | --- |
| Replay focused closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_coverage_matrix.py tests/replay/test_phase35_trace_replay_permissions.py tests/replay/test_phase35_terminal_timelines.py tests/replay/test_phase35_operation_identity.py tests/replay/test_phase35_redaction_negatives.py -q --tb=short` | 0 | `73 passed, 1 warning in 38.29s` |
| Eval and architecture closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py tests/architecture/test_phase35_replay_eval_boundaries.py -q --tb=short` | 0 | `16 passed, 1 warning in 0.41s` |
| Replay/API regression closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_trace_api.py tests/test_agent_runs_api.py tests/replay/test_replay_api.py tests/replay/test_replay_service.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_operation_pairing.py tests/replay/test_replay_redaction_retention.py tests/replay/test_tool_policy_events.py -q --tb=short` | 0 | `120 passed, 1 warning in 171.21s` |
| Agent/action regression closure | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/agent/test_memory_write_node.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/actions/test_phase34_action_draft_bindings.py tests/actions/test_action_draft_v2.py -q --tb=short` | 0 | `86 passed, 1 warning in 23.94s` |
| Scoped replay/eval ruff gate | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/replay tests/replay tests/eval tests/architecture/test_phase35_replay_eval_boundaries.py` | 0 | `All checks passed!` |

No validation command failed during Task 1, so no new `.planning/LOCAL-VALIDATION-ISSUES.md` record was required for this task.

## Multi-Source Coverage Audit

| Source row | Coverage result |
| --- | --- |
| `GOAL` | Phase 35 goal covered by plans 35-01 through 35-06. |
| `REQ APF-17` | covered by 35-01, 35-02, 35-03, and 35-06. |
| `REQ APF-18` | covered by 35-01, 35-03, 35-04, 35-05, and 35-06. |
| `RESEARCH coverage_matrix_gap` | covered by 35-01. |
| `RESEARCH owner_admin_trace_replay_gap` | covered by 35-02. |
| `RESEARCH terminal_timeline_gap` | covered by 35-03. |
| `RESEARCH dev_contract_manifest_gap` | covered by 35-04. |
| `RESEARCH release_monitoring_manifest_gap` | covered by 35-05. |
| `CONTEXT D-01..D-21` | covered by the plan mapping in `35-VALIDATION.md`: D-01..D-04 by matrix/replay contract inventory, D-05..D-08 by proof and permission hardening, D-09..D-13 by dev/release/monitoring gates, D-14..D-19 by golden/redaction/forbidden-behavior datasets, and D-20..D-21 by the six-plan Phase 35 split plus this closure plan. |

## Boundary Assertion Audit

Every row in `eval/replay/phase35-coverage-matrix.v1.json` maps to at least one concrete `decision_assertions[].assertion_id` and test path. The audit below records content checks from matrix, manifest, or test sources rather than file existence alone.

| Boundary | Assertion id and test path | Boundary-specific content check |
| --- | --- | --- |
| `trusted_context_projection` | `trusted_context_projection_replay_context` -> `tests/replay/test_phase35_trace_replay_permissions.py` | `rg` found `FORBIDDEN_AUTH_SHORTCUT_PATTERNS`, `project_replay_authorization_proof`, `proof_status`, and owner/admin guard checks in `tests/replay/test_phase35_trace_replay_permissions.py:22-26,51-59,187-220`; matrix line 33 records this assertion id. |
| `trusted_context_projection` | `trusted_context_projection_owner_admin_guard` -> `tests/replay/test_phase35_trace_replay_permissions.py` | `rg` found explicit owner/admin and 403/404 assertions for trace, replay, status, evidence, and stream in `tests/replay/test_phase35_trace_replay_permissions.py:81-220`. |
| `intent_policy` | `intent_policy_effective_route_trace` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found matrix projection `target_graph.contextual_intent_resolve.v1` and assertion id at `eval/replay/phase35-coverage-matrix.v1.json:54,68`; the test validates manifest forbidden behavior cases and concrete paths at `tests/eval/test_phase35_replay_eval_gates.py:54-68`. |
| `intent_policy` | `intent_policy_release_gate_manifest` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found release/monitoring non-blocking checks in `tests/eval/test_phase35_replay_eval_gates.py:77-91` and release `statistical_gate_not_demonstrated` in `eval/replay/release-gate.v1.json`. |
| `slot_policy` | `slot_policy_inheritance_trace` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found matrix projection `slot_resolution_gate.v1` and assertion id at `eval/replay/phase35-coverage-matrix.v1.json:89,103`; the eval test validates the manifest path and blocking gate linkage at `tests/eval/test_phase35_replay_eval_gates.py:29-68`. |
| `memory_load_policy` | `memory_load_scope_trace` -> `tests/replay/test_phase35_trace_replay_permissions.py` | `rg` found memory regression source mapping in `tests/replay/test_phase35_trace_replay_permissions.py:31-38`, and memory authority/scope content in `tests/agent/test_reviewed_memory_context_retrieve.py:50-61,74-172`. |
| `memory_write_policy` | `memory_write_policy_safe_payload` -> `tests/replay/test_phase35_redaction_negatives.py` | `rg` found memory write lifecycle/status and contextual-only decisions in `tests/agent/test_memory_write_node.py:43-86,263-350`, plus raw/PII replay alias rejection in `tests/replay/test_phase35_redaction_negatives.py:14-26,51-102`. |
| `memory_write_policy` | `memory_write_monitoring_manifest` -> `tests/eval/test_phase35_release_monitoring_manifests.py` | `rg` found monitoring metric ids and allowed statuses in `tests/eval/test_phase35_release_monitoring_manifests.py:15-27,93-115`; `eval/replay/monitoring-gate.v1.json` records `memory_write_quality` with `phase35_blocking=false`. |
| `tool_visibility` | `tool_visibility_prompt_safe_view` -> `tests/replay/test_phase35_redaction_negatives.py` | `rg` found `ToolViewV1` prompt-safe platform projection in `src/tools/platform.py:22,91-92`, visibility event emission in `src/tools/platform.py:168-179`, and low-payload visibility tests rejecting `required_permission` in `tests/replay/test_tool_policy_events.py:94-126`. |
| `tool_runtime_auth` | `tool_runtime_auth_resource_scope_trace` -> `tests/replay/test_phase35_trace_replay_permissions.py` | `rg` found runtime authorization event tests for `tool_policy_runtime_auth_recorded`, `decision`, `reason_codes`, denied status, and raw arg exclusion in `tests/replay/test_tool_policy_events.py:131-193`; runtime source records scoped denial reasons in `src/tools/runtime.py:96-142,228-312`. |
| `business_fact_read_scope_freshness` | `business_fact_scope_freshness_proof` -> `tests/replay/test_phase35_trace_replay_permissions.py` | `rg` found `BusinessFactRefV1`/proof projection setup and `proof_status == "resolved"` checks in `tests/replay/test_phase35_trace_replay_permissions.py:187-220`, plus action-bound business fact bindings in `tests/actions/test_phase34_action_draft_bindings.py:27-130`. |
| `business_fact_read_scope_freshness` | `business_fact_wrong_scope_blocks_action_path` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found dev-contract case ids for stale/wrong-scope facts in `eval/replay/dev-contract-manifest.v1.json:184-210` and concrete action binding mismatch tests in `tests/actions/test_phase34_action_draft_bindings.py:221-225,388-403`. |
| `rag_validation` | `rag_validation_safe_package_projection` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found invalid-scope, stale, tenant mismatch, invalid hash, and no-leak assertions in `tests/agent/test_nodes/test_rag_context_build.py:203-263`; the manifest maps invalid-scope evidence to concrete RAG/claim tests in `eval/replay/dev-contract-manifest.v1.json:216-226`. |
| `claim_verification` | `claim_verification_blocks_unsupported_action_claim` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found `blocked_claims`, `safe_support_refs`, `verification_route`, `unsupported`, and `allows_action_recommendation is False` in `tests/agent/test_nodes/test_claim_verify.py:241-294`. |
| `risk_decision` | `risk_decision_action_path_trace` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found risk manual-review fallback in `tests/agent/test_nodes/test_assess_risk_and_approval.py:432` and action payload hash/business fact/claim/safety bindings in `tests/actions/test_phase34_action_draft_bindings.py:88-105,184-192,295-324`. |
| `risk_decision` | `risk_decision_dev_contract_forbidden_paths` -> `tests/eval/test_phase35_replay_eval_gates.py` | `rg` found forbidden path case ids `unsupported_claim_to_action_bound_path`, `no_evidence_to_deterministic_action_recommendation`, `unsafe_action_path`, `stale_business_fact_ref_accepted`, and hash mismatch cases in `eval/replay/dev-contract-manifest.v1.json:135-242`; tests validate all cases at `tests/eval/test_phase35_replay_eval_gates.py:54-68`. |
| `approval_lifecycle` | `approval_lifecycle_terminal_timeline` -> `tests/replay/test_phase35_terminal_timelines.py` | `rg` found P0 replay timelines for `normal_completed`, `interrupted_approval_required`, `resumed_completed`, `rejected`, `responded_needs_info`, `expired`, `error`, and `cancelled` in `tests/replay/test_phase35_terminal_timelines.py:234-558`. |
| `action_draft` | `action_draft_demo_only_safe_payload` -> `tests/replay/test_phase35_redaction_negatives.py` | `rg` found raw action payload alias rejection in `tests/replay/test_phase35_redaction_negatives.py:14-26,51-102` and demo-only `external_side_effect is False` action draft assertions in `tests/actions/test_action_draft_v2.py:231-274,341-354`. |
| `action_draft` | `action_draft_timeline_no_real_execution` -> `tests/replay/test_phase35_terminal_timelines.py` | `rg` found explicit `action_execution_completed` absence checks in `tests/replay/test_phase35_terminal_timelines.py:458,558`. |

## Roadmap Criterion 4 Scope Audit

Roadmap criterion 4 requires replay, trace, and eval views to preserve Phase 29.5 merchant scope boundaries with no cross-merchant leakage through run listing, trace detail, tool result records, approval views, memory, or replay artifacts.

| Surface | Audit result |
| --- | --- |
| `run listing` | Phase 35 direct regression: `tests/replay/test_phase35_trace_replay_permissions.py:59-77,81-220` checks AgentRun status/evidence/stream visibility remains owner/admin-only or owner-only for execution, with same-tenant non-owner 403 and cross-tenant 404. |
| `trace detail` | Phase 35 direct regression: `tests/replay/test_phase35_trace_replay_permissions.py:51-59,81-220` checks trace guard source is owner/admin-only and proof-free, then API calls deny non-owner business roles. |
| `tool result records` | Existing regression plus Phase 35 no-widening decision: `tests/replay/test_tool_policy_events.py:94-193` verifies tool policy event payloads are low-payload and raw args/descriptors are rejected; `tests/replay/test_phase35_trace_replay_permissions.py:32-43` records no Phase 35 authorization widening for tool result records. |
| `approval views` | Existing regression plus Phase 35 no-widening decision: `tests/test_approval_api.py` is tracked in `PHASE35_SURFACE_REGRESSION_SOURCES`, and `tests/replay/test_phase35_trace_replay_permissions.py:32-43` records no Phase 35 authorization widening for approval review views. |
| `memory` | Existing regression plus Phase 35 no-widening decision: `tests/replay/test_memory_foundation_alignment.py:266-278` and `tests/agent/test_reviewed_memory_context_retrieve.py:50-172` preserve memory authority/scope limits; `tests/replay/test_phase35_trace_replay_permissions.py:32-43` records no Phase 35 authorization widening for memory surfaces. |
| `replay artifacts` | Phase 35 direct regression: `tests/replay/test_phase35_trace_replay_permissions.py:51-59,81-220` and `tests/replay/test_replay_api.py:76-165,202-266` keep replay owner/admin-only, cross-tenant 404, same-tenant non-owner 403, and raw replay payload omissions. |

## Matrix Path Existence Audit

Command:

`UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'import json,pathlib; m=json.load(open("eval/replay/phase35-coverage-matrix.v1.json", encoding="utf-8")); paths={p for r in m["rows"] for p in [*r["acceptance_tests"], *(a["test_path"] for a in r["decision_assertions"])]}; missing=sorted(p for p in paths if not pathlib.Path(p).exists()); print(f"matrix path existence audit: {len(paths)} unique paths checked, missing={len(missing)}"); raise SystemExit(1 if missing else 0)'`

Exit: 0

Observed result: `matrix path existence audit: 8 unique paths checked, missing=0`

This checked every path listed under matrix `acceptance_tests` and every `decision_assertions[].test_path`.

## Redaction Limitation

Phase 35 blocks raw prompt, raw tool payload, PII fixtures, and action raw payload exposure through deterministic key/path/value fixture negatives. The blocking coverage includes raw prompt/tool/action aliases, ticket/order/refund PII aliases, buyer names, secrets, credentials, API keys, and unsafe debug payloads in `tests/replay/test_phase35_redaction_negatives.py`, with replay API/raw projection regressions in `tests/replay/test_replay_api.py` and tool policy raw payload tests in `tests/replay/test_tool_policy_events.py`.

Residual limitation: arbitrary PII hidden inside otherwise safe free-text summary fields remains a release/monitoring follow-up. Phase 35 does not claim general natural-language PII detection for every safe summary string as a dev-contract guarantee.

## MVP Scope Notes

`replay_authorization_proof.v1` is intentionally projection-only in Phase 35. It is not wired into trace, replay, AgentRun, stream, or approval authorization guards. The proof projection is reserved for a named post-Phase 35 same-merchant trace/replay authorization-expansion phase that can safely open manager same-merchant access after proof-chain semantics are stable.

## No Scope Creep Checks

| Check | Command | Exit | Result |
| --- | --- | --- | --- |
| Real execution/outbox/reconciliation surface scan | `rg -n "action_outbox_events|action_reconciliation_jobs|action_compensation_records|ExternalExecutionWorker|OutboxDispatcher|ReconciliationWorker|CompensationWorker" src/` | 1 | No output. `rg` exit 1 means no matches; no exclusions required. |
| Replay-by-rerun scoped scan | `rg -n "invoke_graph|with_structured_output|PolicyKnowledgeService.search|create_coupon_grant_draft|create_draft" src/replay src/api/routers/traces.py` | 1 | No output. `rg` exit 1 means no matches; no exclusions required. |
| Approved-entrypoint scan | `rg -n '^[[:space:]]*(\x60)?(pytest|python -m pytest)\b|\x60(pytest|python -m pytest)[^\x60]*\x60' .planning/phases/35-replay-and-eval-hardening/35-*-PLAN.md docs/evaluation.md` | 1 | No output. `rg` exit 1 means no disallowed bare `pytest` or bare `python -m pytest` command snippets. |
| Whitespace/conflict marker check | `git diff --check` | 0 | No output. |

The no-scope scans did not require excluding test-owned negative fixtures. Redaction negative fixtures intentionally contain raw-payload aliases, but those aliases are outside the first two no-scope grep pattern sets and remain under `tests/`.

## Nyquist Validation Audit 2026-06-29

| Metric | Count |
| --- | --- |
| Plans audited | 6 |
| Requirement groups audited | 2 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only | 0 |

### Test Infrastructure

| Framework | Config | Approved entrypoint |
| --- | --- | --- |
| pytest | `pyproject.toml` | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` |
| ruff | `pyproject.toml` | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` |

### Per-Plan Coverage Map

| Plan | Requirements / decisions | Automated coverage | Status |
| --- | --- | --- | --- |
| `35-01` | APF-17/APF-18, D-01..D-04, D-20..D-21 | `tests/replay/test_phase35_coverage_matrix.py`; matrix validator and six-plan roadmap-shape tests | COVERED |
| `35-02` | APF-17, D-05..D-08, D-17 | `tests/agent/test_trace.py`; `tests/replay/test_phase35_trace_replay_permissions.py`; API visibility regressions referenced in the validation audit | COVERED |
| `35-03` | APF-17/APF-18, D-14..D-16 | `tests/replay/test_phase35_terminal_timelines.py`; `tests/replay/test_phase35_operation_identity.py`; `tests/replay/test_phase35_redaction_negatives.py` | COVERED |
| `35-04` | APF-18, D-09..D-13, D-18 | `tests/eval/test_phase35_replay_eval_gates.py`; `tests/architecture/test_phase35_replay_eval_boundaries.py` | COVERED |
| `35-05` | APF-18, D-11..D-12, D-19 | `tests/eval/test_phase35_release_monitoring_manifests.py`; release/monitoring hash/status artifact checks | COVERED |
| `35-06` | APF-17/APF-18 closure, D-20..D-21 | `35-VALIDATION.md` command evidence, source audit, matrix path audit, no-scope-creep checks, and UAT/security/code-review artifacts | COVERED |

### Audit Commands

| Command | Exit | Observed result |
| --- | --- | --- |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/architecture/test_phase35_replay_eval_boundaries.py tests/eval/test_phase35_release_monitoring_manifests.py tests/eval/test_phase35_replay_eval_gates.py tests/replay/test_phase35_coverage_matrix.py tests/replay/test_phase35_operation_identity.py tests/replay/test_phase35_redaction_negatives.py tests/replay/test_phase35_terminal_timelines.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` | 0 | `122 passed, 1 warning in 40.20s` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_trace_replay_permissions.py tests/replay/test_phase35_redaction_negatives.py tests/eval/test_phase35_replay_eval_gates.py tests/architecture/test_phase35_replay_eval_boundaries.py -q --tb=short` | 0 | `57 passed, 1 warning in 28.23s` |
| `git diff --check` | 0 | No whitespace or conflict-marker output before validation audit write. |

### Manual-Only

None. Phase 35 is a replay/eval contract hardening phase with deterministic artifact, API, static, and pytest coverage. Release-scale statistical evidence and production telemetry remain intentionally non-blocking artifacts, not manual-only Phase 35 validation gaps.

### Nyquist Sign-Off

- [x] APF-17 has automated validation coverage.
- [x] APF-18 has automated validation coverage.
- [x] All six Phase 35 plans have automated or static validation coverage.
- [x] No validation gaps are open.
- [x] `nyquist_compliant: true` remains correct.
