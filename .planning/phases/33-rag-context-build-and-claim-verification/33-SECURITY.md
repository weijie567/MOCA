---
phase: 33
slug: rag-context-build-and-claim-verification
phase_name: rag-context-build-and-claim-verification
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-29T02:03:46Z
updated: 2026-06-29T02:03:46Z
auditor: codex-gsd-security-auditor
block_on: high
threats_total: 33
threats_closed: 33
---

# Phase 33 Security Audit

## 结论

Phase 33 的威胁登记共 33 项，全部为 `mitigate` 处置。审计按计划中声明的缓解模式做定向代码与测试证据核验，未做盲扫扩展；未修改任何实现文件或测试文件。

结果：33/33 CLOSED，`threats_open: 0`。

## Trust Boundaries

| Boundary | 安全关注点 | 核验结果 |
| --- | --- | --- |
| graph state -> KnowledgeService | LLM/检索候选 ref 进入严格 DTO 和 canonical validation 边界。 | CLOSED |
| KnowledgeService -> prompt/verifier/replay/debug projections | raw/debug/verifier/replay 投影必须隔离，普通 prompt/API 面只拿 safe projection。 | CLOSED |
| old checkpoint -> new turn AgentState | 旧 turn 的 package、bundle、claims、safe refs 不能串到新 turn。 | CLOSED |
| investigate -> rag_context_build -> recommendation_generation | candidate refs 只能经 `rag_context_build` 验证后进入 generation。 | CLOSED |
| recommendation_generation -> claim_verify -> risk/action | generation 只产 claim；claim support 和 action gate 由 bundle/safe refs 控制。 | CLOSED |
| trace/API/replay -> caller | `rag_claim_summary.v1` 只暴露 allowlist summary，并保持 owner/admin 与 tenant scope。 | CLOSED |

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| T-33-01-01 | Tampering / Elevation of privilege | `VerifiedEvidencePackageV1.status` | mitigate | CLOSED | `src/knowledge/schemas.py:73` 定义严格 status；`src/knowledge/service.py:727` 映射 hash/scope/auth/stale/conflict；`tests/knowledge/test_verified_evidence_package.py:211` 覆盖 invalid/stale 映射。 |
| T-33-01-02 | Spoofing / Elevation of privilege | `ClaimVerificationBundleV1` / business claims | mitigate | CLOSED | `src/agent/rag_context/verifier.py:450` 区分 policy/business authority；`src/agent/rag_context/verifier.py:813` 拒绝 memory/model/prompt/raw rows；`tests/agent/rag_context/test_authority_boundaries.py:254` 覆盖非权威来源。 |
| T-33-01-03 | Information disclosure | package/bundle projections | mitigate | CLOSED | `src/knowledge/schemas.py:135` 分离 prompt/verifier/replay/debug projection；`tests/knowledge/test_verified_evidence_package.py:201` 验证投影分离；`tests/agent/rag_context/test_leakage.py:371` 覆盖 raw source/OCR 不泄漏。 |
| T-33-01-04 | Tampering | semantic review | mitigate | CLOSED | `src/agent/rag_context/verifier.py:291` 先跑 domain hard rules；`tests/agent/rag_context/test_semantic_verifier.py:176` 验证 semantic success 不能覆盖 hard gate；`tests/knowledge/test_claim_verification_bundle.py:373` 验证 rule checks preserved。 |
| T-33-01-05 | Tampering / Repudiation | `receive_request` state reset | mitigate | CLOSED | `src/agent/nodes/receive_request.py:91` 重置 Phase 33 fields；`tests/agent/test_nodes/test_receive_request.py:190` 构造旧 package/bundle/claims；`tests/agent/test_nodes/test_receive_request.py:202` 断言全部清空。 |
| T-33-02-01 | Tampering / Elevation of privilege | `rag_context_build` | mitigate | CLOSED | `src/agent/nodes/rag_context_build.py:39` 调用 `build_verified_context`；`src/knowledge/service.py:735` 映射 invalid_hash/scope/stale；`tests/agent/test_nodes/test_rag_context_build.py:203` 覆盖 invalid scope/stale/hash fail-closed。 |
| T-33-02-02 | Information disclosure | candidate refs | mitigate | CLOSED | `src/agent/working_state.py:207` 只从 verified package/safe refs 投影；`tests/agent/rag_context/test_leakage.py:173` 覆盖 candidate-only prompt unsafe；`tests/agent/test_phase22_action_boundary.py:316` 覆盖 candidate-only 不绑定 action snapshot。 |
| T-33-02-03 | Denial of service / Tampering | `route_after_rag_context` | mitigate | CLOSED | `src/agent/routing.py:22` 定义十个 status；`src/agent/routing.py:296` exception-safe fallback；`tests/agent/test_rag_context_routing.py:13` 参数化全 status。 |
| T-33-02-04 | Elevation of privilege | graph edge wiring | mitigate | CLOSED | `src/agent/graph.py:236` `rag_context_build` 条件边只通向 generation/clarification/final；`tests/agent/test_graph.py:928` 验证 route keys；`tests/architecture/test_phase33_rag_claim_boundaries.py:100` 静态验证 finite routes。 |
| T-33-02-05 | Information disclosure | raw package debug projection | mitigate | CLOSED | `src/agent/working_state.py:234` 只读 `prompt_projection.safe_refs`；`src/agent/rag_claim_summary.py:10` raw package keys strip list；`tests/agent/test_working_state.py:231` 覆盖 debug/verifier/private 不进入 working state。 |
| T-33-03-01 | Tampering | `generate_recommendation` | mitigate | CLOSED | `src/agent/nodes/generate_recommendation.py:263` 只返回 `material_claims`；`tests/architecture/test_phase33_rag_claim_boundaries.py:157` 静态验证 writer ownership；`tests/agent/test_nodes/test_generate_recommendation.py:650` 断言不写 bundle/safe refs。 |
| T-33-03-02 | Information disclosure | prompt context | mitigate | CLOSED | `src/agent/nodes/generate_recommendation.py:318` 读取 `verified_evidence_package`；`src/agent/nodes/generate_recommendation.py:585` 使用 `prompt_projection`；`tests/agent/test_nodes/test_generate_recommendation.py:588` 覆盖 verified prompt projection consumption。 |
| T-33-03-03 | Elevation of privilege | proposed action | mitigate | CLOSED | `src/agent/nodes/generate_recommendation.py:344` 缺 verified package 返回 required reason；`tests/agent/test_nodes/test_generate_recommendation.py:650` 断言 invalid package 不输出 `proposed_action`。 |
| T-33-04-01 | Spoofing / Elevation of privilege | business fact claims | mitigate | CLOSED | `src/agent/rag_context/verifier.py:465` business claim 缺 authority 加 `business_fact_ref_required`；`src/agent/rag_context/verifier.py:813` 拒绝 memory/model/prompt/raw rows；`tests/knowledge/test_claim_verification_bundle.py:178` 覆盖 RAG evidence 不能替代 business authority。 |
| T-33-04-02 | Tampering | semantic review | mitigate | CLOSED | `src/agent/rag_context/domain_rules.py:20` `DomainRuleVerifier`；`src/agent/rag_context/verifier.py:291` hard rules before semantic support；`tests/agent/rag_context/test_semantic_verifier.py:176` 覆盖 semantic 不能 override。 |
| T-33-04-03 | Repudiation | bundle aggregation | mitigate | CLOSED | `src/knowledge/service.py:580` 按 claim 聚合 results/reasons/safe refs；`src/knowledge/service.py:604` 返回 bundle status/route/blocked/safe refs/policy version；`tests/knowledge/test_claim_verification_bundle.py:373` 覆盖 hard-rule aggregation。 |
| T-33-05-01 | Tampering | `claim_verify` | mitigate | CLOSED | `src/agent/nodes/claim_verify.py:19` node 调 `verify_claims`；`src/agent/nodes/claim_verify.py:65` 只写 bundle/blocked/safe refs；`tests/agent/test_nodes/test_claim_verify.py:194` 断言非 owned fields 不写。 |
| T-33-05-02 | Elevation of privilege | `route_after_claim_verify` | mitigate | CLOSED | `src/agent/routing.py:307` exception-safe route wrapper；`src/agent/routing.py:345` blocked/manual/error fail closed；`tests/agent/rag_context/test_routing.py:269` 覆盖 blocked business/action claims -> final_response。 |
| T-33-05-03 | Repudiation | graph vocabulary | mitigate | CLOSED | `src/agent/graph_vocabulary.py:77` `rag_context_build` runtime；`src/agent/graph_vocabulary.py:84` `claim_verify` runtime；`tests/agent/test_graph_vocabulary.py:93` 验证 runtime/runnable。 |
| T-33-06-01 | Elevation of privilege | risk/action gate | mitigate | CLOSED | `src/agent/nodes/assess_risk_and_approval.py:200` bundle guards；`src/agent/nodes/action_draft.py:144` action draft bundle guard；`tests/agent/test_phase22_action_boundary.py:296` 覆盖 action claim disallow fail-closed。 |
| T-33-06-02 | Tampering | candidate refs | mitigate | CLOSED | `src/agent/nodes/assess_risk_and_approval.py:363` action evidence 只从 safe refs resolve；`src/agent/nodes/assess_risk_and_approval.py:382` 候选源是 safe_support_refs；`tests/agent/test_phase22_action_boundary.py:316` 覆盖 candidate-only retrieved refs 不绑定 snapshot。 |
| T-33-06-03 | Repudiation | action safety | mitigate | CLOSED | `src/agent/nodes/assess_risk_and_approval.py:255` block 时清空 proposed/action/snapshot/hash；`tests/agent/test_phase22_action_boundary.py:252` 覆盖 blocked bundle 清 action state；`tests/agent/test_phase22_action_boundary.py:395` 覆盖 action_draft route blocks。 |
| T-33-07-01 | Information disclosure | final response | mitigate | CLOSED | `src/agent/nodes/final_response.py:358` bundle block safe payload；`src/agent/nodes/final_response.py:382` package block safe payload；`tests/agent/test_phase22_final_response.py:244` 覆盖 blocked package no-leak。 |
| T-33-07-02 | Information disclosure | working state | mitigate | CLOSED | `src/agent/working_state.py:207` verified status gate；`src/agent/working_state.py:225` safe support refs precedence；`tests/agent/test_working_state.py:255` 覆盖 safe support subset。 |
| T-33-07-03 | Tampering | candidate refs | mitigate | CLOSED | `src/agent/working_state.py:210` 非 verified/allowed status 返回空；`tests/agent/rag_context/test_leakage.py:173` 覆盖 candidate-only policy refs rejected；`tests/agent/test_working_state.py:255` 覆盖 candidate-only refs stay out。 |
| T-33-08-01 | Information disclosure | trace/API | mitigate | CLOSED | `src/agent/rag_claim_summary.py:9` `rag_claim_summary.v1`；`src/agent/rag_claim_summary.py:10` raw key strip list；`tests/agent/test_trace.py:329` 覆盖 allowlisted summary without raw fields。 |
| T-33-08-02 | Elevation of privilege | API visibility | mitigate | CLOSED | `src/api/routers/agent_runs.py:47` admin-only role set；`src/api/routers/agent_runs.py:1156` owner/admin guard；`src/api/routers/traces.py:37` owner/admin guard；tests at `tests/test_agent_runs_api.py:1201` and `tests/test_trace_api.py:123` cover 403 no leak. |
| T-33-08-03 | Repudiation | trace summary | mitigate | CLOSED | `src/agent/rag_claim_summary.py:146` returns status/count summary only；`src/repositories/trace_repo.py:131` builds persisted summary；`tests/test_trace_api.py:196` asserts exact count/status fields。 |
| T-33-08-04 | Information disclosure | cross-tenant trace/replay | mitigate | CLOSED | `src/repositories/trace_repo.py:32` tenant-scoped `get_run`；`src/api/routers/traces.py:32` uses tenant lookup before summary；`tests/test_trace_api.py:236` and `tests/replay/test_replay_api.py:76` assert cross-tenant 404 without summary。 |
| T-33-09-01 | Repudiation | Phase 32 static guards | mitigate | CLOSED | `tests/architecture/test_phase33_rag_claim_boundaries.py:75` checks runtime graph nodes；`tests/architecture/test_phase33_rag_claim_boundaries.py:86` checks runtime/runnable vocabulary；`33-09-SUMMARY.md:72` records stale Phase 32 guard migration。 |
| T-33-09-02 | Tampering | writer ownership | mitigate | CLOSED | `tests/architecture/test_phase33_rag_claim_boundaries.py:157` writer ownership static guard；`tests/architecture/test_phase33_rag_claim_boundaries.py:170` no repository/raw DB bypass guard。 |
| T-33-09-03 | Information disclosure | projection code | mitigate | CLOSED | `tests/architecture/test_phase33_rag_claim_boundaries.py:186` safe summary strips raw package/verifier fields；`tests/architecture/test_phase33_rag_claim_boundaries.py:225` serialized sanitized payload excludes raw/candidate fields。 |
| T-33-09-04 | Repudiation | validation artifacts | mitigate | CLOSED | `tests/architecture/test_phase33_rag_claim_boundaries.py:243` scans phase artifacts for bare pytest commands；`33-VALIDATION.md:37` declares bare commands invalid；`33-09-SUMMARY.md:151` records approved full gate command。 |

## Summary Threat Flags

| Source | Flag | Mapping |
| --- | --- | --- |
| `33-01-SUMMARY.md` | None | 无 unregistered flag |
| `33-02-SUMMARY.md` | 仅计划内 `investigate -> rag_context_build -> recommendation_generation` boundary | 已映射到 T-33-02-01..T-33-02-05 |
| `33-03-SUMMARY.md` | None | 无 unregistered flag |
| `33-04-SUMMARY.md` | None | 无 unregistered flag |
| `33-05-SUMMARY.md` | None | 无 unregistered flag |
| `33-06-SUMMARY.md` | None；仅 fail-closed routing logic | 已映射到 T-33-06-01..T-33-06-03 |
| `33-07-SUMMARY.md` | None | 无 unregistered flag |
| `33-08-SUMMARY.md` | 未显式包含 `## Threat Flags` section | 计划 threat model 已覆盖 T-33-08-01..T-33-08-04 |
| `33-09-SUMMARY.md` | 未显式包含 `## Threat Flags` section | 计划 threat model 已覆盖 T-33-09-01..T-33-09-04 |

Unregistered flags: none.

## Accepted Risks Log

None. 本阶段威胁登记未包含 `accept` disposition，且所有 `mitigate` 项均已关闭。

## Transfer Log

None. 本阶段威胁登记未包含 `transfer` disposition。

## Audit Trail

| Time (UTC) | Action | Result |
| --- | --- | --- |
| 2026-06-29T02:03:46Z | 读取 `$gsd-secure-phase` skill、security auditor role、secure-phase workflow、Phase 33 全部 PLAN/SUMMARY/VERIFICATION/UAT/REVIEW artifacts。 | 完成 |
| 2026-06-29T02:03:46Z | 检查 project-local `.claude/skills` / `.agents/skills`。 | 未发现 project-local skill。 |
| 2026-06-29T02:03:46Z | 按 threat register 对实现与测试做定向 `rg`/line-read 核验。 | 33/33 CLOSED。 |
| 2026-06-29T02:03:46Z | 检查现有 `33-SECURITY.md`。 | 不存在，按 State B 创建。 |
| 2026-06-29T02:03:46Z | 写入本安全报告。 | 仅创建本文件；未改实现或测试。 |

## Verification Notes

- 本安全审计未重跑 full pytest；引用了 Phase 33 已记录的 final focused gate 和 review-fix 验证结果，并补充执行了定向 grep/line-read 证据核验。
- 现有验证记录显示 full focused Phase 33 gate、Ruff、schema drift guard、`git diff --check` 均通过；详见 `33-VERIFICATION.md`, `33-UAT.md`, `33-REVIEW.md`, `33-REVIEW-FIX.md`。
- 所有命令遵守 MOCA 项目入口约束；未使用裸 `pytest` 或裸 `python -m pytest` 作为验证结论。

## Sign-off

Security gate: PASS.

ASVS Level: 1.

Threats closed: 33/33.

Threats open: 0.
