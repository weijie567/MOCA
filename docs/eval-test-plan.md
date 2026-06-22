NOTE: This file carries the contract test matrix, eval plan, and golden cases. The normative Wilson/M6 gate formula remains in `docs/contract-spec.md` Section 11.4; this file does not duplicate that formula.

## 20. 测试和 eval 计划

测试计划必须从功能清单升级为 contract matrix：每个 contract 都有正例、反例、边界条件和禁止行为。

### 20.0 Eval gate levels

后续 phase 的 eval 需要区分三类门槛，避免用生产统计门槛阻塞所有开发，也避免用少量单测宣称生产级能力：

| Gate level | 用途 | 典型要求 | 不通过时 |
| --- | --- | --- | --- |
| Dev-contract gate | 每个 phase 合并前的最小契约保障 | schema、router totality、state writer、forbidden behavior、scope/permission negative cases | 不应合并该 phase |
| Release gate | 宣称生产级或开启高风险路径前的统计/覆盖门槛 | per-intent calibration、hard negatives、OOD、RAG groundedness、approval/action safety、Wilson/M6 等 | 能力只能保持 guarded/MVP path |
| Monitoring gate | 上线后的持续质量约束 | drift、false negative、tool deny reason、RAG no-evidence、memory write quality、replay completeness | 触发降级、review 或 policy/model 回滚 |

每个新增平台能力在 phase plan 中都应标注对应 eval 属于哪一类 gate。安全、权限、证据、approval/action 相关的 forbidden behavior 默认至少是 Dev-contract gate；高风险 intent calibration 和 action-bound 路径默认需要 Release gate。

### 20.1 Contract test matrix

| Contract | Test type | Required cases | Forbidden behavior |
| --- | --- | --- | --- |
| Node contract | input/output contract tests | 每个 node 缺 required input、合法输出、error output、state writes。 | node 写不属于自己的 state 字段；node 直接越权调用 repository/external API。 |
| Router contract | totality + determinism tests | 每个合法 state shape 返回合法 next node；同 input 多次同 output；invalid state 走 safe fallback。 | router 调 LLM/tool/service；router 返回未知 node；安全相关状态走低风险路径。 |
| State lifecycle | reset/property-based tests | 新 turn reset run/turn fields；same interrupted run resume 保留 snapshot；跨 thread/tenant 不继承。 | stale approval/action/evidence/business context 泄漏到新 run。 |
| Module ownership boundary contract | static boundary + docs contract tests | `docs/contract-spec.md` §0.2 每个模块都有 owned schemas/tables/events、public methods、allowed downstream dependencies、forbidden imports/access、decision events；graph/router/service import checks 覆盖所有 module rows。 | graph/router/service 直接 import 或调用未允许 repository/adapter；architecture/eval docs 定义 spec 未登记的新 service boundary；新增 public dependency 未先做 spec delta。 |
| Intent precedence | golden-set tests | `docs/contract-spec.md` §11.2 precedence table 的所有 ordinary-chat precedence conflict 至少一正一反；multi-intent 拆分或澄清；trusted approval command 与 chat entry 隔离。 | action request 被误路由成纯 policy QA；ordinary chat 形成 approval decision 或 trusted resume。 |
| Confidence calibration | eval threshold tests | 低置信澄清、高风险 intent 更高阈值、risk-weighted confusion matrix。 | 未校准 confidence 直接授权动作。 |
| Tool contract | adapter contract tests | success/partial/not_found/permission_denied/timeout/unavailable/conflict/invalid_response。 | raw upstream payload 进入 graph；缺 `tool_call_id`/scope 仍执行。 |
| Tool policy decision contract | visibility/runtime auth tests | `ToolView` prompt-safe；visible/hidden/allowed/denied 都有 `ToolPolicyDecision`、reason codes、scope binding、policy version。 | planner 可见即 runtime 自动允许；deny 无 reason；raw descriptor/internal permission reason 进 prompt。 |
| Business fact contract | domain facade contract tests | `BusinessFactResultV1` 的 ok/partial/not_found/permission_denied/stale/unavailable/invalid_request；resource_version、scope_check_result、safe_errors。 | permission denied 泄露资源存在性；business fact ref 被当作 `EvidenceRefV1`；stale fact 进入 action-bound path。 |
| Knowledge contract | retrieval contract tests | strong/partial/no evidence、effective time filtering、deterministic tenant-scoped behavior、citation membership validation；global-policy / tenant-over-global deferred to later policy-scope phase。 | no evidence 或 failed citation membership 仍生成确定动作建议；把 membership 当作 semantic support。 |
| RAG context build contract | deterministic evidence package tests | `VerifiedEvidencePackageV1` status 枚举、hash/scope/effective-date validation、projection separation、rejected/stale/conflict refs、route_after_rag_context totality。 | candidate refs 直接进入 prompt/action；invalid_hash/invalid_scope 仍生成 action-bound recommendation；router 调 LLM/tool。 |
| Claim verification contract | rules-first support tests | `MaterialClaimV1` 输入、policy/business/action claim 类型、amount/time/negation/condition/exception hard checks、timeout fail-closed。 | LLM semantic review 覆盖 hard gate；unsupported action claim 进入 risk/approval/action；business fact claim 由 RAG/memory 证明。 |
| Session memory contract | lifecycle + routing safety tests | same-thread continuity；PostgreSQL CAS deterministic merge；scope/freshness/intent compatibility；explicit current-turn override；unresolved question carryover；optional Redis hot-cache miss/unavailable fallback；disable/read-switch fallback telemetry；PII blocked。 | session memory 被当作政策证据；stale/wrong-thread/wrong-user/wrong-tenant slots 通过 slot gate；Redis-only correctness；silent last-write-wins；模型直接写 session memory。 |
| Long-term/case memory contract | lifecycle tests | write/skip/review/delete/supersede；PII blocked；long-term/case predicates 分离；tombstone match 阻止异步重写并 emit event；scope isolation；supersede transaction rollback。 | case memory 使用 `is_current`；deleted/tombstoned/prohibited/superseded/non-current long-term memory 被检索；异步候选重建 tombstoned memory；模型直接写库。 |
| Approval contract | transition table tests | accept/edit/respond/reject/ignore/expire/payload_changed；multi-level any_one/all；next-level pending 不进入 draft；canonical hash golden sample；payload/snapshot hash mismatch；cross-table mismatch transaction rollback。 | `next_level_pending -> action_draft`；expired/superseded approval 可执行；edit 沿用旧 payload hash；并发双执行；ordinary chat 伪造 approval decision。 |
| Action contract | safety/idempotency tests | demo draft only；external execution allowlist；unknown/reconciling；outbox claim-before-dispatch；reconciliation no-new-key retry guard；compensation metadata。 | demo mode 产生 external side effect；未审批高风险动作执行；timeout 被当作成功；未持久化 outbox 就 dispatch。 |
| Decision event / Replay contract | completeness/order/redaction tests | `DecisionEventEnvelopeV1` / minimal envelope、normal/interrupted/resumed/rejected/responded/expired/error/cancelled；shared per-run sequence allocator concurrent writers；started/terminal pair 共享 operation_id；retry parent/attempt；V3 shape。 | 空 timeline；sequence 重复/倒退/事后重排；不同 writer 绕过 allocator；prompt/raw tool/ticket PII/action raw payload 泄漏；服务自建并行 envelope。 |
| Metrics/logging | observability tests | low-cardinality labels；trace_id/run_id log correlation；error counters。 | tenant_id/user_id/run_id/thread_id 成为 Prometheus label。 |

### 20.2 Integration golden flows

- policy QA bypasses business tools and approval。
- refund troubleshooting loads business context + policy evidence。
- no-evidence returns insufficient evidence and does not draft action。
- compensation suggestion creates approval when policy requires。
- appeal/unban execute or draft request loads merchant risk + policy evidence and passes risk/approval before action safety path。
- complaint escalation loads ticket context + escalation policy evidence；escalation action passes risk/approval。
- approval accept creates action draft bound to exact payload hash only when request is approved/all required levels complete；next-level pending remains approval/interrupted。
- approval edit invalidates old revision and revalidates action。
- approval respond writes a clarification message/ref, leaves the run interrupted, and does not execute old approval or mark the run completed。
- approval reject/ignore/expired does not execute action。
- demo action creates durable draft but no external side effect。
- external action timeout enters `unknown` or `reconciling`。
- trace/replay includes node/tool/RAG/approval/action timeline, terminal status or current interrupted status as applicable, and no sensitive payload leakage。

### 20.3 Eval

当前 README 已有 RAG Hit@5、intent/route accuracy、tool selection、citation rate、safety interception。目标新增：

- Intent confusion matrix with risk-weighted penalties。
- Clarification precision：低置信度或缺 slot 是否正确澄清。
- Required-slot accuracy：required slots 是否符合 intent policy。
- Citation membership：引用的 `evidence_id` 是否存在于 retrieved evidence；该指标不计作完整 semantic claim support。
- RAG semantic groundedness/support：引用证据是否支持 material claims；作为独立 deferred eval 或 reviewed rule-based mapping，不得由 citation membership 代替。
- Approval policy accuracy：高风险是否拦截，低风险是否不过度拦截。
- Action safety：未审批高风险动作执行率必须为 0。
- Session memory route safety：同 thread 补槽成功率、跨 scope 泄漏率、stale/incompatible slot 拒绝率、cache-miss fallback 成功率。
- Memory write quality：长期记忆写入 precision、PII leakage、过期记忆过滤。
- Replay completeness：每个 run 是否覆盖 node/tool/RAG/approval/action events。

### 20.4 Reference dataset requirements

- 每个 intent 至少 5 个 positive cases 和 3 个 hard negatives。M6 high-risk/action validation set 的 gate-pass 样本量是 **per-class** 的：critical write、approval decision、appeal/unban、complaint escalation 每类必须达到 coverage manifest 的 `per_class_expected_min_n`（当前每类 300，合计下限 1200）。"总计至少 200 个独立去重样例" 仅为早期探索性最低覆盖参考，不足以 pass M6 gate（详见 `docs/contract-spec.md` §11.4）。
- M6 critical write、approval decision、appeal/unban、complaint escalation classes 要求逐 class zero false negatives，并记录 one-sided 95% Wilson upper bound；每个 class 只有 `wilson_upper_95_one_sided <= 0.01` 才能通过，pooled metric 不可替代，且每个 class 必须达到 `per_class_expected_min_n`（当前 300）。样本不足时结论必须为 `statistical_gate_not_demonstrated`。
- 每个 precedence conflict 至少 1 个 primary/secondary 对照样例。
- 每个 approval transition 至少 1 个正例和 1 个 forbidden 反例。
- 每个 replay terminal status 至少 1 个 golden timeline。
- 数据集必须标注 expected route、required slots、expected evidence policy、approval/action expectation、forbidden behavior。
- M6 eval result 必须至少输出 `{dataset_version, dataset_hash, coverage_manifest_hash, coverage_status, class_name, required_min_n, n, false_negatives, wilson_upper_95_one_sided, formula_version, confidence_level, gate_status, gate_reason}`；`formula_version` 固定为 `wilson_one_sided_95_v1`，`confidence_level=0.95`，`gate_status` 取值为 `pass | fail | statistical_gate_not_demonstrated`，并且 per-class gate 不可被 pooled metric 覆盖。`gate_reason` 必须是第一条命中的 precedence code：`coverage_missing | coverage_incomplete | coverage_invalid | below_per_class_min_n | false_negatives_present | wilson_upper_exceeded | passed`。

---

## 21. Golden cases

Golden cases 是 spec 的最终自洽检查。每个 case 都必须能映射到 intent、state writes、routes、approval/action/replay contract 和 forbidden behavior。

### 21.1 Intent routing examples

| Case | Input | Expected primary intent | Requested operation | Secondary / hints | Expected route | Forbidden behavior |
| --- | --- | --- | --- | --- | --- | --- |
| Policy-only refund question | “退款超过 48 小时有什么政策？” | `policy_qa` | `advise` | refund policy | policy evidence -> recommendation/final | 调 business tools 或创建 action draft。 |
| Refund troubleshooting | “ORD-1001 退款为什么还没到账？” | `refund_troubleshooting` | `read_status` | policy_qa | session memory -> slots -> business context -> policy evidence -> recommendation | 没有订单/退款事实就给确定结论。 |
| Compensation advice, no execution | “这个退款拖太久，建议怎么补偿？” | `compensation_suggestion` | `advise` | refund_troubleshooting | session memory -> slots -> business context -> policy evidence -> recommendation -> risk gate | 直接发券或创建 action draft。 |
| Explicit compensation write | “给 RF-1001 发 100 元券。” | `compensation_suggestion` | `execute_action` | action safety hint | session memory -> slots -> business context -> policy evidence -> recommendation -> risk/approval -> action draft | 把领域 intent 降级为 generic action_request，或绕过政策证据/审批直接执行。 |
| Appeal/unban high-risk action | “解除商家 M-1001 的封禁。” | `appeal_or_unban` | `execute_action` | merchant risk + action safety hint | session memory -> slots -> business/merchant risk context -> policy evidence -> recommendation -> risk/approval -> action safety path | 缺政策证据或商家风险上下文就 draft/execute；降级为 generic action_request。 |
| Complaint escalation | “把投诉 TKT-1001 升级给主管并起草回复。” | `complaint_escalation` | `escalate` | ticket/escalation hint | session memory -> slots -> business/ticket context -> escalation policy evidence -> recommendation/draft_reply -> risk/approval -> action draft | 没有 escalation policy evidence 就升级；把回复草稿误当已执行升级。 |
| Generic write action | “对 TKT-1001 执行 allowlist 中的 custom action。” | `action_request` | `execute_action` | action type/target hint | session memory -> slots -> business context -> policy evidence -> recommendation -> risk/approval -> action draft | 在可识别专用领域 intent 时仍使用 generic action_request。 |
| Multi-target request | “查 ORD-1，同时给 RF-2 发券。” | clarification or split runs | clarification/split | order/action | ask to split or confirm target | 在一个 action draft 混合多个 target。 |

### 21.2 Trusted approval command examples

Trusted approval commands are not ordinary chat intent-routing cases. They enter through authenticated approval API / inbox command handling and never through LLM intent classification.

| Case | Trusted input | Expected command type | Expected flow | Required guards | Forbidden behavior |
| --- | --- | --- | --- | --- | --- |
| Approval inbox accept | `approval_id=APR-1`, `decision=accept`, `expected_request_version`, `expected_level_version`, `expected_assignment_version` | `approval_review` / `approval_decision` trusted command | approval API/inbox -> ApprovalService.decide -> graph.resume trusted result -> route_after_approval -> action_draft if all levels approved | tenant/user/role injected by server；actor role matches；CAS expected versions；payload/snapshot hash match | ordinary chat text creates approval decision；LLM outputs trusted marker；skip expected version/CAS；use untrusted tenant/user/role |
| Approval inbox respond | `approval_id=APR-1`, `decision=response` external type, `response_text`, expected versions | external `response` mapped by server adapter to internal `respond` | ApprovalService.decide -> approval `needs_info` -> run remains interrupted with clarification message/ref | response text present；trusted adapter maps to `respond`；old approval revision cannot execute | treat as completed run；normal memory_write/final_response completed path；execute old approval after user reply without revalidation |

### 21.3 Missing slot cross-turn example

Turn 1：

```json
{
  "input": "帮我看看这笔退款为什么没到账",
  "expected_intent": "refund_troubleshooting",
  "expected_missing_slot_groups": [["refund_case_id", "order_id"]],
  "expected_route": "clarification_gate",
  "state_writes": {
    "clarification_request": {"reason": "missing_required_slots"},
    "session_memory.unresolved_questions": [{"any_of": ["refund_case_id", "order_id"]}]
  }
}
```

Turn 2：

```json
{
  "input": "订单是 ORD-1001",
  "same_thread": true,
  "expected_resolution": {
    "active_slots.order_id": {"value": "ORD-1001", "source": "current_turn"}
  },
  "expected_route": "investigate",
  "forbidden": ["reuse unrelated thread slots", "skip business context", "reuse stale approval"]
}
```

### 21.4 No-evidence examples

Positive no-evidence handling：

```json
{
  "input": "根据政策能不能给 RF-1001 额外赔 1000 元？",
  "retrieval_status": "no_evidence",
  "expected_route": "final_response",
  "expected_response_type": "insufficient_evidence_response",
  "expected_replay_events": ["rag_retrieval_started", "rag_retrieval_completed", "node_completed", "run_status_changed"],
  "forbidden": ["create_action_draft", "approval_requested", "state that policy allows compensation"]
}
```

Strong evidence handling：

```json
{
  "input": "RF-1001 超过承诺时效，政策建议是什么？",
  "retrieval_status": "strong_evidence",
  "expected_route": "recommendation_generation",
  "expected_evidence_refs": ["policy_refund_timeout/chunk_001@v3"],
  "forbidden": ["cite chunks not retrieved", "hide no-evidence uncertainty"]
}
```

### 21.5 Approval lifecycle examples

Accept, all required levels approved：

```json
{
  "approval_id": "APR-1",
  "decision": "accept",
  "trusted_context": "authenticated approval inbox/API; tenant, actor, role and approval_id injected by server",
  "guard": "actor role, action_payload_hash and expected request/level/assignment versions match",
  "expected_status": "approved",
  "expected_route": "action_draft",
  "forbidden": ["modify payload", "execute external action before all levels approved", "route with request status pending"]
}
```

Accept, next level pending：

```json
{
  "approval_id": "APR-1",
  "decision": "accept",
  "trusted_context": "authenticated approval inbox/API",
  "expected_status": "next_level_pending",
  "expected_request_status": "pending",
  "expected_route": "approval_gate or lifecycle_finalizer_preserving_interrupted",
  "forbidden": ["next_level_pending -> action_draft", "action_draft", "action_execution"]
}
```

Reject / ignore：

```json
[
  {"decision":"reject","expected_status":"rejected","expected_route":"final_response","forbidden":["action_draft","resume"]},
  {"decision":"ignore","expected_status":"cancelled","expected_route":"final_response","forbidden":["remain_pending","action_draft"]}
]
```

Edit：

```json
{
  "approval_id": "APR-1",
  "decision": "edit",
  "edited_action": {"amount": "80", "currency": "CNY"},
  "expected_old_status": "superseded",
  "expected_route": "risk_gate",
  "expected_new_revision": 2,
  "forbidden": ["reuse old action_payload_hash", "go directly to action_draft"]
}
```

Payload changed：

```json
{
  "event": "payload_changed",
  "expected_old_status": "superseded",
  "expected_new_revision": 2,
  "expected_route": "risk_gate",
  "forbidden": ["reuse old approval", "execute mismatched payload hash"]
}
```

Multi-level concurrency：

```json
[
  {"mode":"any_one","concurrent_accepts":2,"expected_winners":1,"loser_result":"409 approval_conflict"},
  {"mode":"all","required_assignments":2,"accepted":1,"expected_level_status":"pending"},
  {"mode":"all","required_assignments":2,"accepted":2,"later_required_level_exists":true,"expected_level_status":"approved","expected_request_status":"pending","expected_route":"approval_gate or interrupted"},
  {"mode":"all","all_required_levels_complete":true,"expected_request_status":"approved","expected_route":"action_draft"}
]
```

Respond：

```json
{
  "approval_id": "APR-1",
  "decision": "respond",
  "response_text": "请补充退款通道失败原因。",
  "expected_status": "needs_info",
  "expected_route": "lifecycle_finalizer_preserving_interrupted",
  "expected_message": "approval_needs_info clarification message/ref, not normal completed final_response",
  "next_user_info_rule": "create or resume a new verifiable revision and rerun slot/business/evidence/risk checks",
  "forbidden": ["treat as rejected", "mark run completed", "normal clarification_gate -> final_response -> memory_write path", "execute old approval after user response without revalidation"]
}
```

Expired：

```json
{
  "approval_id": "APR-1",
  "event": "expire",
  "guard": "now >= sla_due_at",
  "expected_status": "expired or escalation-created pending",
  "expected_replay_event": "approval_expired",
  "forbidden": ["resume to action_draft", "silently remove from timeline"]
}
```

### 21.6 Demo draft golden flow

```json
{
  "input": "给 RF-1001 发 100 元券",
  "execution_mode": "demo",
  "expected_route": [
    "intent_classification",
    "session_memory_load",
    "slot_extraction",
    "investigate",
    "recommendation_generation",
    "risk_gate",
    "approval_gate",
    "action_draft",
    "final_response"
  ],
  "expected_draft_outcome": {
    "status": "not_executed_demo",
    "external_side_effect": false
  },
  "expected_final_response_rule": "say draft created, not coupon issued",
  "forbidden": ["action_execution_completed", "external_ref", "已发券"]
}
```

### 21.7 External unknown-result example

```json
{
  "input": "执行已审批的退款动作 ACT-1",
  "execution_mode": "external",
  "upstream_result": "timeout_after_dispatch",
  "expected_action_execution_status": "unknown or reconciling",
  "expected_replay_events": ["action_execution_started", "action_execution_unknown", "action_status_changed", "reconciliation_started"],
  "required_followup": "reconciliation query using external idempotency key",
  "forbidden": ["mark executed without confirmation", "retry with different idempotency key", "auto compensation before reconciliation"]
}
```

### 21.8 Replay timeline examples

Normal completed run with action draft：

```json
{
  "final_status": "completed",
  "timeline_event_types": [
    "run_status_changed",
    "node_started",
    "node_completed",
    "tool_call_started",
    "tool_call_completed",
    "rag_retrieval_started",
    "rag_retrieval_completed",
    "llm_call_started",
    "llm_call_completed",
    "action_draft_created",
    "memory_write_started",
    "memory_write_completed",
    "run_status_changed"
  ],
  "required": ["started/completed_pairs_share_operation_id", "retry_uses_parent_operation_id_and_incremented_attempt", "sequence_monotonic", "schema_version=replay_event.v3", "redacted_payload_only"]
}
```

Interrupted and resumed run：

```json
{
  "final_status": "completed",
  "timeline_event_types": [
    "run_status_changed",
    "node_completed",
    "approval_requested",
    "run_status_changed",
    "approval_decided",
    "approval_resumed",
    "action_draft_created",
    "run_status_changed"
  ],
  "required": ["sequence_continues_after_resume", "approval_id_refs_present"]
}
```

Error run：

```json
{
  "final_status": "error",
  "timeline_event_types": ["run_status_changed", "node_failed", "run_status_changed"],
  "required": ["safe_error_code", "partial_timeline_preserved"],
  "forbidden": ["empty_timeline", "raw_stack_with_secret"]
}
```

Cancelled run：

```json
{
  "final_status": "cancelled",
  "timeline_event_types": ["run_status_changed", "run_status_changed"],
  "required": ["cancellation_actor", "occurred_at"],
  "forbidden": ["resume_allowed", "action_execution_after_cancel"]
}
```

Responded replay：

```json
{
  "final_status": "interrupted",
  "timeline_event_types": ["approval_decided", "run_status_changed"],
  "required": ["decision_type=respond", "approval_status=needs_info", "clarification_request_id"],
  "forbidden": ["run_status_changed:completed", "normal_final_response_completed", "action_draft_created", "action_execution_started"]
}
```

Expired replay：

```json
{
  "final_status": "expired",
  "timeline_event_types": ["approval_expired", "run_status_changed"],
  "required": ["approval_id_ref", "sla_due_at", "terminal_status"],
  "forbidden": ["approval_resumed", "action_draft_created"]
}
```

---
