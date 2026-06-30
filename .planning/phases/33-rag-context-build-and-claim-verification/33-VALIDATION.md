---
phase: 33
slug: rag-context-build-and-claim-verification
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-29
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_leakage.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_rag_context_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/agent/test_working_state.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/business/test_schemas.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_text_hash.py tests/platform/test_context_projections.py tests/replay/test_replay_api.py -q --tb=short` |
| **Estimated runtime** | quick smoke <30 seconds; full focused suite ~120-240 seconds as phase-gate-only validation |

---

## Sampling Rate

- **After every task commit:** Run the plan-local quick command for the touched boundary.
- **Fast smoke/static feedback:** Before any full phase gate, run the relevant plan-local command plus targeted architecture/static tests for the touched boundary.
- **After state/reset changes:** Also run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py -q --tb=short`.
- **After graph/routing changes:** Also run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py -q --tb=short`.
- **After risk/action/final-response changes:** Also run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/architecture/test_action_draft_boundaries.py -q --tb=short`.
- **After every plan wave:** Run the full focused suite above.
- **Before `$gsd-verify-work`:** Full focused suite plus `uv run ruff check` on touched Python files and `git diff --check` must pass.
- **Invalid command guard:** Bare `pytest` and bare `python -m pytest` are invalid validation in MOCA.
- **Max feedback latency:** <30 seconds for plan-local smoke/static commands; 4 minutes allowed only for the final focused phase gate.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 33-01 | 1 | APF-13/APF-14 | T-33-01 | New package/bundle/state schemas are strict, reset per turn, and writer ownership is testable. | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` | yes | verified |
| 33-02-01 | 33-02 | 2 | APF-13 | T-33-02 | Candidate refs are re-fetched and rejected on combined invalid scope/hash/version/effective-date inputs before prompt/action surfaces. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_rag_context_build.py tests/agent/rag_context/test_context_builder.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` | yes | verified |
| 33-02-02 | 33-02 | 2 | APF-13 | T-33-03 | `route_after_rag_context` is deterministic and total over all status values. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py -q --tb=short` | yes | verified |
| 33-03-01 | 33-03 | 3 | APF-14 | T-33-04 | `recommendation_generation` emits `MaterialClaimV1` and does not mark claims supported. | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_generate_recommendation.py tests/agent/rag_context/test_material_claims.py -q --tb=short` | yes | verified |
| 33-04-01 | 33-04 | 4 | APF-14 | T-33-05 | Domain hard gates and bundle aggregation require current policy/business/action authority. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_semantic_verifier.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` | yes | verified |
| 33-05-01 | 33-05 | 5 | APF-14 | T-33-06 | `claim_verify` writes bundle, blocked claims, and safe support refs without downgrading business/action authority failures to safe. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_claim_verify.py tests/agent/rag_context/test_routing.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph.py -q --tb=short` | yes | verified |
| 33-06-01 | 33-06 | 6 | APF-13/APF-14 | T-33-07 | Unsupported action claims and candidate-only refs cannot reach risk, approval, action draft, or safety snapshots. | negative/security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` | yes | verified |
| 33-07-01 | 33-07 | 7 | APF-13/APF-14 | T-33-08 | Final response and working-state projections expose safe evidence/claim text only. | negative/security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_final_response.py tests/agent/test_working_state.py tests/agent/rag_context/test_leakage.py -q --tb=short` | yes | verified |
| 33-08-01 | 33-08 | 8 | APF-13/APF-14 | T-33-09 | Trace/API/replay projections expose only safe statuses/counts/refs, preserve visibility guards, and do not fabricate summaries for legacy runs. | integration/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py -q --tb=short` | yes | verified |
| 33-09-01 | 33-09 | 9 | APF-13/APF-14 | T-33-10 | Static/focused final gates prove runtime nodes, ownership, no raw leakage, and valid commands. | integration/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` | yes | verified |

*Status values before closure: pending · green · red · flaky*

---

## Wave 0 Requirements

- [x] `tests/knowledge/test_verified_evidence_package.py` — package schema, status, citation/evidence maps, rejected/stale/conflict refs, and projection separation.
- [x] `tests/knowledge/test_claim_verification_bundle.py` — bundle schema, blocked claims, safe support refs, verifier policy/config version, and route semantics.
- [x] `tests/agent/test_nodes/test_rag_context_build.py` — node writer ownership, candidate-to-package output, combined invalid scope/hash/version fail-closed, and build-error status.
- [x] `tests/agent/test_nodes/test_claim_verify.py` — node writer ownership, malformed verifier output fail-closed, business fact authority, and unsupported action claim blocking.
- [x] `tests/agent/test_rag_context_routing.py` — `route_after_rag_context` totality and route semantics.
- [x] `tests/architecture/test_phase33_rag_claim_boundaries.py` — Phase 33 static ownership checks replacing Phase 32 non-runnable guards.
- [x] Update `tests/agent/test_graph.py`, `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, trace/API projection tests, and replay fallback tests for runnable target nodes, safe RAG/claim projections, cross-tenant visibility, allowlist enforcement, and legacy no-summary degradation.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | APF-13/APF-14 | Phase 33 must be covered by deterministic unit/integration/static tests. | All phase behaviors have automated verification. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all MISSING references.
- [x] No watch-mode flags.
- [x] Feedback latency <30 seconds for plan-local smoke/static commands; full focused suite is phase-gate-only.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** verified by 33-VERIFICATION.md

---

## Final Closure Notes

- Phase 33 semantic verifier coverage is deterministic/mocked: `tests/agent/rag_context/test_semantic_verifier.py` uses `FakeSemanticProvider`, explicit timeout/error/malformed-output cases, and no live provider requirement.
- The full focused suite remains a phase-gate-only latency check. Fast smoke/static commands should stay under 30 seconds where practical; the focused suite is allowed to take the documented 120-240 seconds.
- Phase 32 compatibility window is closed in Plan 33-09: `rag_context_build` and `claim_verify` are runtime/runnable, and stale Phase 32 non-runnable static assertions were migrated to Phase 33 runtime boundary guards.

Commands recorded for final closure:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_leakage.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_rag_context_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/agent/test_working_state.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/business/test_schemas.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_text_hash.py tests/platform/test_context_projections.py tests/replay/test_replay_api.py -q --tb=short
uv run ruff check src/knowledge/schemas.py src/knowledge/service.py src/agent/rag_context/schemas.py src/agent/rag_context/claims.py src/agent/rag_context/domain_rules.py src/agent/rag_context/verifier.py src/agent/rag_context/routing.py src/agent/nodes/rag_context_build.py src/agent/nodes/claim_verify.py src/agent/nodes/generate_recommendation.py src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/action_draft.py src/agent/nodes/final_response.py src/agent/routing.py src/agent/graph.py src/agent/graph_vocabulary.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/working_state.py src/agent/trace.py src/api/routers/agent_runs.py src/api/routers/traces.py src/api/schemas/agent_runs.py src/repositories/trace_repo.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_rag_context_routing.py tests/architecture/test_phase33_rag_claim_boundaries.py
git diff --check
```

Final gate results from Plan 33-09:

| Check | Result |
| --- | --- |
| Static smoke | `13 passed, 1 warning in 0.07s` |
| Initial full focused suite | Failed on stale Phase 22 compatibility tests expecting `generate_recommendation` to own RAG build/verifier route and stale trace summary shape without `rag_claim_summary` |
| Targeted stale-test rerun after migration | `6 passed, 2 warnings in 0.13s` |
| Final full focused suite | `473 passed, 22 warnings in 160.87s (0:02:40)` |
| Ruff focused target list | `All checks passed!` |
| `git diff --check` | passed |
| Post-review-fix targeted review regressions | `79 passed, 1 warning in 0.11s` |
| Post-review-fix adjacent graph/action/API regressions | `90 passed, 22 warnings in 108.08s (0:01:48)` |
| Post-review-fix full focused suite | `476 passed, 22 warnings in 162.60s (0:02:42)` |
| Post-review-fix Ruff focused target list | `All checks passed!` |
| Post-review-fix `git diff --check` | passed |

The handled local validation issue is recorded in `.planning/LOCAL-VALIDATION-ISSUES.md` under the 2026-06-29 05:29 CST Plan 33-09 entry.
