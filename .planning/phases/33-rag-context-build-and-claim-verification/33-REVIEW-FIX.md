---
phase: 33-rag-context-build-and-claim-verification
review_source: 33-REVIEW.md
fixed_at: 2026-06-28T22:00:02Z
status: fixed
findings_fixed:
  critical: 0
  warning: 2
---

# Phase 33 Code Review Fix

## 处理结果

- WR-01 已修复：`route_after_claim_verify` 现在会识别已验证且允许的 `action_recommendation` claim。即使没有既有 `proposed_action`、风险等级为 low，也会进入 `assess_risk_and_approval`，由风险/快照边界绑定动作授权。
- WR-02 已修复：`generate_recommendation` 不再把旧 `state.evidence_refs` 合并进本轮输出；`final_response` 在 Phase 33 verified/partial package 存在时，只从当前 verified package 的 `evidence_map` 与 claim safe support refs 补全 trace evidence，避免 stale/candidate refs 抢占同一 citation。

## 新增回归

- `tests/agent/rag_context/test_routing.py::test_route_after_claim_verify_sends_verified_action_recommendation_to_risk_gate`
- `tests/agent/test_nodes/test_generate_recommendation.py::test_membership_pass_does_not_carry_stale_state_evidence_refs`
- `tests/agent/test_phase22_final_response.py::test_final_response_trace_prefers_current_verified_package_over_stale_state_refs`

## 验证

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/agent/test_phase22_final_response.py tests/agent/test_nodes/test_generate_recommendation.py -q --tb=short` -> 79 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_phase22_action_boundary.py tests/test_agent_runs_api.py -q --tb=short` -> 90 passed, 22 warnings
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py -q --tb=short` -> 36 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_leakage.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_rag_context_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/agent/test_working_state.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/business/test_schemas.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_text_hash.py tests/platform/test_context_projections.py tests/replay/test_replay_api.py -q --tb=short` -> 476 passed, 22 warnings
- `uv run ruff check src/agent/routing.py src/agent/nodes/final_response.py src/agent/nodes/generate_recommendation.py tests/agent/rag_context/test_routing.py tests/agent/test_phase22_final_response.py tests/agent/test_nodes/test_generate_recommendation.py` -> passed
- `uv run ruff check src/knowledge/schemas.py src/knowledge/service.py src/agent/rag_context/schemas.py src/agent/rag_context/claims.py src/agent/rag_context/domain_rules.py src/agent/rag_context/verifier.py src/agent/rag_context/routing.py src/agent/nodes/rag_context_build.py src/agent/nodes/claim_verify.py src/agent/nodes/generate_recommendation.py src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/action_draft.py src/agent/nodes/final_response.py src/agent/routing.py src/agent/graph.py src/agent/graph_vocabulary.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/working_state.py src/agent/trace.py src/api/routers/agent_runs.py src/api/routers/traces.py src/api/schemas/agent_runs.py src/repositories/trace_repo.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_rag_context_routing.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_graph.py tests/agent/rag_context/test_routing.py tests/agent/test_phase22_final_response.py tests/agent/test_nodes/test_generate_recommendation.py` -> passed
- `git diff --check` -> passed
