# Phase 33 RAG / Claim Target Mapping

本文记录 Phase 33 结束时 `rag_context_build` 与 `claim_verify` 的目标态落地情况。文档表达使用中文，契约标识、类名、字段名、命令保留英文。

## 结论

Phase 33 将 Phase 32 中的 RAG / claim 占位目标提升为真实 runtime behavior：

- `KnowledgeService.search` 仍归属 `investigate` 的候选政策检索能力，只产生 candidate policy refs。
- `rag_context_build` 已成为 runtime/runnable graph node，负责把 candidate refs 升级为 `VerifiedEvidencePackageV1`。
- `recommendation_generation` 只消费 verified package prompt projection，并输出 `MaterialClaimV1`。
- `claim_verify` 已成为 runtime/runnable graph node，负责把 `material_claims` 验证为 `ClaimVerificationBundleV1`。

## 三段式 RAG 拆分

| 阶段 | 位置 | 输入 | 输出 | 边界 |
| --- | --- | --- | --- | --- |
| Candidate retrieval | `investigate` 内部 | 用户问题、resolved slots、trusted `KnowledgeContext`、retrieval policy | `policy_evidence` / `retrieved_evidence` candidate refs、`retrieval_status`、`best_score` | `KnowledgeService.search` / `search_policy` 只说明可能相关，不可直接进入 prompt/action/risk/approval。 |
| Verified context build | `rag_context_build` node | candidate refs、business fact refs、trusted `KnowledgeContext`、evidence policy | `rag_context_status`、`verified_evidence_package`、`citation_map`、`evidence_map` | 只做 deterministic evidence validation/context projection；invalid scope/hash/stale/conflict/no evidence fail closed。 |
| Claim verification | `claim_verify` node | `material_claims`、`verified_evidence_package`、`business_context`、`proposed_action` | `claim_verification_bundle`、`blocked_claims`、`safe_support_refs` | rules-first verifier；business fact claim 只能由 `BusinessFactRefV1` / `BusinessFactResultV1` 支持；unsupported action claim 不进入 risk/action。 |

## Writer Ownership

| Writer | Owns | Must not write |
| --- | --- | --- |
| `investigate` | `policy_evidence`、`retrieved_evidence`、`retrieval_status`、`best_score`、`business_context`、`tool_results` | `verified_evidence_package`、`claim_verification_bundle`、`safe_support_refs` |
| `rag_context_build` | `rag_context_status`、`verified_evidence_package`、`citation_map`、`evidence_map` | `material_claims`、`claim_verification_bundle`、`blocked_claims`、`safe_support_refs` |
| `recommendation_generation` | `recommendation_draft`、`material_claims`、validated `evidence_refs` subset | `rag_context_status`、`verified_evidence_package`、`claim_verification_bundle`、claim support status |
| `claim_verify` | `claim_verification_bundle`、`blocked_claims`、`safe_support_refs`、legacy verifier compatibility fields | `verified_evidence_package`、`citation_map`、`evidence_map`、`proposed_action` |
| `risk_gate` / `action_draft` / `final_response` / projections | 只读 package/bundle safe surfaces，并做下游 fail-closed / sanitized projection | 不得重新验证 evidence，也不得把 candidate refs 或 raw verifier/debug payload 提升为 authority。 |

## Route Summary

| Router | Reads | Valid routes | Summary |
| --- | --- | --- | --- |
| `route_after_investigate` | business context、retrieval status、candidate refs、evidence policy | `rag_context_build` / `recommendation_generation` / `clarification_gate` / `final_response` | 需要 policy evidence 或存在 candidate refs 时进入 `rag_context_build`；fact-only 或 no-policy-required 才可跳过。 |
| `route_after_rag_context` | `rag_context_status`、package status、risk/evidence policy | `recommendation_generation` / `clarification_gate` / `final_response` | `verified` 可进入 generation；`not_required` 仅在 policy evidence 不需要时进入；`partial` 只允许低风险 answer path；`no_evidence` / `unauthorized` / `stale` / `conflict` / `invalid_hash` / `invalid_scope` / `build_error` fail closed。 |
| `route_after_recommendation` | `material_claims`、`proposed_action`、user-visible claim payload、legacy verifier route | `claim_verify` / `final_response` | 有 material claims、proposed action 或 user-visible policy/business/action claims 时进入 `claim_verify`。 |
| `route_after_claim_verify` | `claim_verification_bundle`、`blocked_claims`、`proposed_action`、`risk_signals` | `assess_risk_and_approval` / `final_response` | bundle `continue` 且 `overall_status` 为 `verified` / `not_required` 时，只有 action/risk path 进入 risk；answer-only verified bundle 直接 final response。 |

## Projection / No-Leak Summary

Phase 33 的安全投影遵循 allowlist，而不是传递 raw package/bundle：

- Prompt-facing generation 只消费 `verified_evidence_package.prompt_projection`、`citation_map`、`evidence_map` 的安全子集。
- WorkingState evidence refs 优先使用 `claim_verification_bundle.safe_support_refs` / state `safe_support_refs`，其次使用 package `prompt_projection.safe_refs`，最后才在兼容路径读取 verified `evidence_map`。
- Final response 将 blocking `rag_context_status` 和 blocked `claim_verification_bundle` 转成 insufficient-evidence / manual-review 安全模板，不复用 draft `missing_info` 中的 raw reasoning。
- Trace / SSE / Trace API / Replay 暴露 `rag_claim_summary.v1`，只包含 status 和 counts。
- Replay projection 会移除 `verified_evidence_package`、`claim_verification_bundle`、`debug_projection`、`verifier_projection`、`prompt_projection`、`raw_semantic`、`source_block*`、`ocr*`、candidate refs、`evidence_map` 等 raw/debug/verifier/provenance payload。

## Explicit Deferrals

| Owner | Deferred Scope |
| --- | --- |
| Phase 34 | approval/action binding：把 action proposals、approval decisions、action drafts 明确绑定到 business fact refs、verified evidence refs、claim verification refs、risk decisions、payload hashes、safety snapshots。 |
| Phase 35 | broad replay/eval hardening：覆盖 platform decisions、RAG/claim decisions、risk/approval/action decisions 的完整 replay/eval gate。 |
| Policy Scope | tenant-over-global / global fallback：tenant public policy 与未来 global/default policy precedence 的 owner，不在 Phase 33 静默实现。 |
| Phase RAG-5 | external search backend：如果 PostgreSQL hybrid 不再满足规模或质量，再规划外部 SearchBackend；Phase 33 不引入新 backend。 |
| Future execution-boundary phase | real external execution：真实外部副作用、outbox、reconciliation、compensation dispatch 与 idempotent external worker 仍在未来执行边界阶段。 |

## Validation Anchors

- Static guards: `tests/architecture/test_phase33_rag_claim_boundaries.py`
- Runtime node tests: `tests/agent/test_nodes/test_rag_context_build.py`, `tests/agent/test_nodes/test_claim_verify.py`
- Router tests: `tests/agent/test_rag_context_routing.py`, `tests/agent/rag_context/test_routing.py`
- Leakage/projection tests: `tests/agent/rag_context/test_leakage.py`, `tests/agent/test_working_state.py`, `tests/agent/test_phase22_final_response.py`, `tests/agent/test_trace.py`, `tests/test_agent_runs_api.py`, `tests/test_trace_api.py`, `tests/replay/test_replay_api.py`
