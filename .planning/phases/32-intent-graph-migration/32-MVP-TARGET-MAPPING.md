# Phase 32 MVP Target Mapping

本文记录 Phase 32 的 MVP 落地边界：运行时代码继续保留 legacy graph node/router 名称，contract/eval/API 表面通过 `src.agent.graph_vocabulary` 投影到 target canonical vocabulary。本文不是 Phase 33 的 RAG/claim 实现说明。

## Legacy 到 Target 映射

| legacy_name | kind | target | status | runnable | 说明 |
| --- | --- | --- | --- | --- | --- |
| `classify_intent` | `node` | `contextual_intent_resolve` | `compatibility_alias` | `true` | legacy classifier node 继续运行，target 语义由 policy registry 决定。 |
| `intent_classification` | `node` | `contextual_intent_resolve` | `compatibility_alias` | `true` | 兼容旧契约名。 |
| `classify_intent:pre_route` | `node` | `safety_pre_route` | `compatibility_alias` | `true` | pre-route safety disposition 的兼容投影。 |
| `session_memory_load` | `node` | `session_context_load` | `compatibility_alias` | `true` | 当前 wrapper/runtime 名保留，target 表面使用 session context 命名。 |
| `session_context_load` | `node` | `session_context_load` | `runtime` | `true` | target identity mapping。 |
| `long_term_memory_retrieve` | `node` | `memory_context_load` | `compatibility_alias` | `true` | legacy long-term memory retrieval 投影到 target memory context load。 |
| `reviewed_memory_context_retrieve` | `node` | `memory_context_load` | `runtime` | `true` | 当前 reviewed memory runtime node 的 target 语义。 |
| `memory_context_load` | `node` | `memory_context_load` | `compatibility_alias` | `true` | target/compatibility identity mapping。 |
| `extract_slots` | `node` | `slot_resolution_gate` | `compatibility_alias` | `true` | Phase 32 不拆物理 node；通过 registry 和 trace metadata 表达 slot resolution gate。 |
| `slot_resolution_gate` | `node` | `slot_resolution_gate` | `compatibility_alias` | `true` | first-class target vocabulary entry。 |
| `route_after_intent` | `router` | `route_after_contextual_intent` | `compatibility_alias` | `true` | legacy router key 保留，target router 名用于 contract/eval/API 投影。 |
| `route_after_contextual_intent` | `router` | `route_after_contextual_intent` | `compatibility_alias` | `true` | target router identity mapping。 |
| `route_after_slots` | `router` | `route_after_slot_resolution` | `compatibility_alias` | `true` | legacy slot router key 保留，target router 名为 `route_after_slot_resolution`。 |
| `route_after_slot_resolution` | `router` | `route_after_slot_resolution` | `compatibility_alias` | `true` | target router identity mapping。 |
| `rag_context_build` | `node` | `rag_context_build` | `deferred_non_runnable` | `false` | Phase 33 / APF-13 owned；Phase 32 只登记 target 名称，不注册 runnable graph node。 |
| `claim_verify` | `node` | `claim_verify` | `deferred_non_runnable` | `false` | Phase 33 / APF-14 owned；Phase 32 只登记 target 名称，不注册 runnable graph node。 |

## Policy Registry Ownership

- `IntentPolicyRegistry` 是 effective route、risk tier、precedence、direct-response 和 evidence requirement 的决策源；LLM intent 输出只作为 candidate input。
- `SlotPolicyRegistry` 是 required-slot completeness、inherited-slot freshness、scope compatibility、invalidation 和 reason code 的决策源。
- `routing.py` 与 `classify_intent.py` 不再直接消费 `DIRECT_RESPONSE_INTENTS`、`INTENT_ROUTE_POLICY`、`REQUIRED_SLOT_POLICY` 这些底层 policy constants。
- legacy edge keys 仍用于 LangGraph 编译与调试；target router/node 名通过 projection 暴露。

## `target_merchant_context.v1`

`target_merchant_context` 是 evidence/status metadata，不是授权输入。允许的输出字段只有：

- `schema_version`
- `status`
- `source`
- `reason_codes`
- `business_fact_ref_count`

状态含义：

| status | 含义 |
| --- | --- |
| `resolved` | 仅当存在 service-approved `BusinessFactRefV1`-shaped refs 时可返回。 |
| `deferred` | 当前路径需要 business target，但还没有可信 `business_fact_refs`，使用 `TARGET_MERCHANT_CONTEXT_DEFERRED_UNTIL_BUSINESS_FACT_REF`。 |
| `unavailable` | trusted/business context evidence 格式错误、权限失败或 no-authority error。 |
| `not_applicable` | direct response 或 tenant-public-policy-only 路径不需要 business target。 |

禁止从 raw `merchant_id`、`order_id`、`refund_case_id`、`ticket_id`、memory、active slots、prompt summary、LLM text、raw tool payload 或 repository row 推导 `resolved`。

## 明确非 Scope

Phase 32 没有实现以下内容：

- APF-13 `VerifiedEvidencePackageV1` 或完整 `rag_context_build` writer/readers/reset/persist 行为。
- APF-14 `ClaimVerificationBundleV1` 或完整 `claim_verify` material-claim verification 行为。
- full same-merchant AgentRun visibility。
- approval/action binding 的 target merchant 授权扩展。
- replay/eval broad hardening。
- DB/RLS hardening。
- physical microservice extraction。

`rag_context_build` 和 `claim_verify` 在 Phase 32 中只允许是 `deferred_non_runnable` target vocabulary entries。

## 最终验证命令

Phase 32 的验证结论只接受 MOCA 项目入口，不接受裸 `pytest` 或裸 `python -m pytest`。

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase32_static_contract.py -q --tb=short
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/agent/test_required_slots.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_trusted_context_boundaries.py tests/platform/test_trusted_context_factory.py tests/platform/test_context_projections.py tests/architecture/test_phase32_static_contract.py -q --tb=short
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph_vocabulary.py src/agent/merchant_context.py src/agent/intent_policy.py src/agent/routing.py src/agent/nodes/classify_intent.py src/agent/nodes/extract_slots.py src/agent/trace.py src/api/routers/agent_runs.py src/api/routers/traces.py src/repositories/trace_repo.py tests/agent/test_graph_vocabulary.py tests/agent/test_graph.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_routing.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/architecture/test_phase32_static_contract.py
```

```bash
git diff --check
```
