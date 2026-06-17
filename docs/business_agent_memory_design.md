# 业务型 Agent 的记忆机制设计

适用对象：智能客服 Agent、退款 Agent、政策审查 Agent、理赔 Agent、发票审核 Agent、账号申诉 Agent 等。

核心结论：业务型 Agent 可以使用“LLM 应用视角”的记忆机制，但不能把它作为核心。业务型 Agent 的核心是结构化业务状态、规则/政策版本、工具执行、人工审批和审计链；记忆系统主要用于上下文增强、减少重复询问、压缩对话和帮助模型生成更连贯的回复。

---

## 1. 业务型 Agent 的设计立场

业务型 Agent 的第一原则不是“让模型记住用户”，而是“让系统可靠地执行流程”。

以退款客服 Agent 为例，系统真正需要维护的是：

- 当前是哪一个工单。
- 当前是哪一个订单。
- 用户申请退款的原因是什么。
- 适用哪一个政策版本。
- 用户已经提供了哪些证据。
- 还缺哪些材料。
- 是否满足退款条件。
- 是否需要人工审核。
- 谁在什么时候基于什么依据做出了什么判断。

这些信息不能只靠 prompt、summary 或 LLM 记忆维护，必须落在结构化数据库、规则引擎、政策知识库和审计日志中。

可以把业务型 Agent 理解成：

```text
业务型 Agent = 状态机 / 工作流 / 工具执行 / 审计
             + 上下文记忆 / 短期摘要 / 工具结果压缩
```

记忆系统在这里是“辅助层”，不是“权威业务层”。

---

## 2. 总体架构

```text
User
  ↓
Conversation API
  ↓
Case Loader
  ├── 读取工单状态：cases / case_states
  ├── 读取订单事实：Order API / CRM / OMS
  ├── 读取政策依据：Policy KB / Rule Engine
  ├── 读取当前会话摘要：case_summaries
  ├── 读取最近消息：messages
  └── 读取必要的用户沟通偏好：limited user memories
  ↓
Context Assembler
  ↓
LLM / Agent Runtime
  ├── 生成回复
  ├── 选择工具
  ├── 解释政策
  └── 识别缺失材料
  ↓
Tool Executor / Rule Engine / Policy Checker
  ↓
Decision Gate
  ├── 自动回复
  ├── 要求补充材料
  ├── 人工审核
  ├── 拒绝越权承诺
  └── 写入业务状态
  ↓
Response
  ↓
Persist
  ├── Raw Conversation Log
  ├── Tool Call Log
  ├── Case State
  ├── Case Summary
  └── Audit Log
```

---

## 3. 数据分层：哪些是权威数据，哪些是派生数据

| 数据层 | 示例 | 是否权威 | 是否默认进入 prompt | 说明 |
|---|---|---:|---:|---|
| Business State | case_id、order_id、current_stage、refund_reason、eligibility_result | 是 | 部分进入 | 业务流程的事实源 |
| Policy KB | 政策条款、版本、生效时间、失效时间 | 是 | 检索后部分进入 | 政策审查依据 |
| Rule Engine Result | 是否可退、是否需人工审核 | 是 | 摘要进入 | 不能只由 LLM 自行判断 |
| Raw Conversation Log | 完整 user/assistant/tool 消息 | 是 | 不默认全部进入 | 回放、纠错、审计来源 |
| Audit Log | 工具调用、模型版本、政策引用、决策依据 | 是 | 不默认进入 | 合规追踪，不是记忆 |
| Short-term Summary | 当前工单摘要、缺失材料、未解决问题 | 派生 | 通常进入 | 提升对话连续性 |
| Working State | 当前处理步骤、最近工具结果摘要 | 运行态 | 通常进入 | 辅助本轮推理 |
| Long-term User Memory | 沟通偏好、语言偏好 | 是，但范围受限 | 检索后少量进入 | 业务场景中必须谨慎 |
| Memory Block | prompt 中的记忆片段 | 否 | 是 | 临时上下文，不是数据库记录 |

关键判断：

```text
能影响业务结果、审批、合规的内容，必须有结构化权威来源。
能影响回复方式、上下文理解的内容，可以作为 prompt context。
```

---

## 4. 业务状态不是记忆

退款 Agent 的核心状态可以这样设计：

```json
{
  "case_id": "case_123",
  "user_id": "u_001",
  "order_id": "ord_789",
  "current_stage": "policy_review",
  "refund_reason": "商品与描述不符",
  "policy_version": "refund_policy_2026_05",
  "required_evidence": [
    "订单截图",
    "商品照片",
    "物流状态截图"
  ],
  "provided_evidence": [
    "订单截图",
    "商品照片"
  ],
  "eligibility_result": "pending",
  "human_review_required": true,
  "risk_flags": [
    "缺少物流状态截图"
  ],
  "next_action": "要求用户补充物流状态截图"
}
```

这不是 LLM memory，而是 business state。它应该存入 Postgres 等权威存储，而不是只存在上下文窗口里。

建议表结构：

```sql
CREATE TABLE cases (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  order_id TEXT,
  case_type TEXT NOT NULL,             -- refund / dispute / account_appeal
  status TEXT NOT NULL,                -- open / pending_user / pending_review / resolved / rejected
  priority TEXT DEFAULT 'normal',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE case_states (
  case_id TEXT PRIMARY KEY REFERENCES cases(id),
  current_stage TEXT NOT NULL,          -- intake / evidence_collection / policy_review / approval / closed
  state_json JSONB NOT NULL,
  policy_version TEXT,
  eligibility_result TEXT,              -- eligible / ineligible / pending / human_review
  next_action TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

状态转移建议：

```text
created
  ↓
intake
  ↓
evidence_collection
  ↓
policy_review
  ├── eligible → approval_or_refund
  ├── ineligible → explain_and_close
  ├── missing_evidence → pending_user
  └── high_risk → human_review
  ↓
closed
```

LLM 可以辅助判断下一步，但最终状态转移应由规则、工具结果和决策网关确认。

---

## 5. Working Memory 在业务型 Agent 中怎么设计

业务型 Agent 也需要 working memory，但它不是权威状态机，只是当前回合的“工作台”。

它通常包括：

- 当前 case_id / order_id。
- 当前处理目标。
- 当前阶段。
- 本轮需要检查的政策点。
- 最近工具调用结果摘要。
- 待确认问题。
- 本轮不能违反的业务约束。

示例：

```json
{
  "thread_id": "thread_456",
  "case_id": "case_123",
  "current_goal": "判断退款申请是否满足政策条件",
  "active_stage": "policy_review",
  "active_order_id": "ord_789",
  "current_policy_check": "签收后7天内商品问题退款条件",
  "open_questions": [
    "用户是否能补充物流状态截图"
  ],
  "recent_tool_results": [
    {
      "tool": "get_order",
      "summary": "订单 ord_789 已签收3天，商品类型为普通商品，非不可退品类。",
      "raw_result_ref": "s3://tool-results/case_123/get_order_turn_5.json"
    },
    {
      "tool": "retrieve_policy",
      "summary": "refund_policy_2026_05 section 3.2 要求签收后7天内提交问题证据。",
      "policy_ref": "refund_policy_2026_05#3.2"
    }
  ],
  "constraints": [
    "不能承诺一定退款",
    "必须引用政策依据",
    "缺少材料时应要求补充材料",
    "金额超过500元必须人工审核"
  ],
  "pending_confirmation": null
}
```

存储选择：

| 场景 | 存储建议 | 说明 |
|---|---|---|
| 单次 demo | 内存 | 请求结束即丢弃 |
| 多实例客服系统 | Redis | 多台服务共享活跃 case 状态缓存 |
| 需要恢复和排障 | Postgres checkpoint | 记录关键 working state 快照 |
| 最终业务事实 | cases / case_states | 不要只放 working memory |

推荐策略：

```text
Redis 放活跃 working state。
Postgres 放权威 case_state。
重要阶段变化写 checkpoint。
working state 可以重建，但 case_state 必须可靠保存。
```

---

## 6. Raw Conversation Log：完整历史，不等于短期记忆

Raw Conversation Log 是完整原始记录，包括用户消息、助手回复、工具调用、工具结果引用等。

它的作用：

- 回放整个工单处理过程。
- 解释为什么当时这么回复。
- 支持用户投诉后的复核。
- 支持重新生成摘要。
- 支持审计和合规留痕。

它不应该被摘要替代。

推荐表结构：

```sql
CREATE TABLE messages (
  id BIGSERIAL PRIMARY KEY,
  thread_id TEXT NOT NULL,
  case_id TEXT,
  user_id TEXT,
  role TEXT NOT NULL,                   -- user / assistant / tool / system
  content TEXT,
  content_type TEXT DEFAULT 'text',      -- text / json / image_ref / file_ref
  tool_call_id TEXT,
  token_count INT,
  pii_level TEXT DEFAULT 'unknown',      -- none / low / medium / high
  object_key TEXT,                       -- 大文本或附件在对象存储的位置
  created_at TIMESTAMPTZ DEFAULT now()
);
```

大文本和附件处理：

```text
短文本消息 → Postgres content
大型工具结果 → S3 / 对象存储，Postgres 存 object_key
截图、PDF、图片 → S3 / 对象存储，Postgres 存 metadata
可审计关键字段 → Postgres 独立结构化字段
```

不要把完整 raw log 默认全部塞进 prompt。模型当前需要的只是最近几轮、工单摘要、必要政策片段和关键工具结果摘要。

---

## 7. Short-term Memory：当前工单摘要

业务型 Agent 的短期记忆主要是 case-level summary，而不是通用用户画像。

它回答的问题是：

```text
这个工单目前处理到哪里了？
用户已经说过什么？
我们已经要求过什么？
还缺什么？
下一步应该做什么？
```

示例：

```json
{
  "case_id": "case_123",
  "rolling_summary": "用户申请订单 ord_789 的退款，理由是商品与描述不符。已提供订单截图和商品照片，缺少物流状态截图。订单已签收3天，商品非不可退品类。当前政策审查结论为待补充材料。",
  "current_stage": "evidence_collection",
  "confirmed_facts": [
    "订单 ord_789 已签收3天",
    "用户主张商品与描述不符",
    "已提供订单截图和商品照片"
  ],
  "open_questions": [
    "缺少物流状态截图"
  ],
  "last_agent_action": "已要求用户补充物流状态截图",
  "last_policy_reference": "refund_policy_2026_05 section 3.2",
  "updated_at": "2026-06-17T10:00:00Z"
}
```

建议存储：

```sql
CREATE TABLE case_summaries (
  case_id TEXT PRIMARY KEY REFERENCES cases(id),
  summary_json JSONB NOT NULL,
  summary_text TEXT,
  source_message_range INT8RANGE,
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

更新时机：

- 每 3-5 轮对话更新一次。
- 当前消息 token 超过阈值时更新。
- 工单阶段变化时更新。
- 工具返回关键事实后更新。
- 人工审核结果回来后更新。

摘要 prompt 模板：

```text
请基于旧摘要和新增消息更新当前工单摘要。

必须保留：
1. 工单目标和当前阶段。
2. 已确认事实。
3. 用户已经提供的材料。
4. 仍缺失的材料或未解决问题。
5. 已引用的政策版本和条款。
6. 已经向用户承诺或明确说明过的内容。
7. 下一步动作。

必须删除：
1. 寒暄。
2. 重复表达。
3. 没有业务意义的情绪描述。
4. 不确定或模型猜测。

旧摘要：{old_summary}
新增消息：{new_messages}
请输出结构化 JSON。
```

---

## 8. 政策审查不应该放在“记忆”里

政策是可版本化、可追溯、可审计的知识资产，不是用户记忆。

推荐结构：

```sql
CREATE TABLE policies (
  id TEXT PRIMARY KEY,
  policy_name TEXT NOT NULL,
  version TEXT NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE,
  status TEXT NOT NULL,                 -- active / deprecated / draft
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE policy_chunks (
  id BIGSERIAL PRIMARY KEY,
  policy_id TEXT REFERENCES policies(id),
  section_id TEXT NOT NULL,
  title TEXT,
  content TEXT NOT NULL,
  embedding VECTOR(1536),
  metadata JSONB
);
```

政策审查流程：

```text
用户问题 / 工单状态
  ↓
确定场景：退款、换货、投诉、账号申诉
  ↓
检索政策库：policy_id + version + section
  ↓
读取订单事实和证据状态
  ↓
规则引擎或决策网关判断
  ↓
LLM 生成解释性回复
  ↓
写入 audit log：政策引用 + 工具输入输出 + 结论
```

业务上不要让模型凭“记得某条政策”来判断，应让系统显式检索当前生效政策版本。

---

## 9. Tool JSON、工具结果摘要和 Working Memory 的关系

Tool JSON 是工具/API 的原始返回。它可能很大，不应该直接塞进 prompt，也不应该完整放入 working memory。

示例工具返回：

```json
{
  "tool_name": "get_order",
  "order_id": "ord_789",
  "status": "delivered",
  "delivered_at": "2026-06-14T15:30:00Z",
  "items": [
    {
      "sku": "sku_001",
      "category": "normal_goods",
      "returnable": true
    }
  ],
  "payment": {
    "amount": 399,
    "currency": "CNY"
  },
  "provider_raw_payload": {
    "...": "很多业务系统字段"
  }
}
```

推荐处理方式：

```text
完整 Tool JSON → S3 / tool_calls.raw_result_object_key
关键字段 → tool_calls.normalized_result
摘要 → working_memory.recent_tool_results
进入 prompt → 只放必要摘要和可引用字段
```

工具调用表：

```sql
CREATE TABLE tool_calls (
  id TEXT PRIMARY KEY,
  case_id TEXT,
  thread_id TEXT,
  tool_name TEXT NOT NULL,
  input_json JSONB,
  normalized_result JSONB,
  raw_result_object_key TEXT,
  status TEXT,                          -- success / failed / timeout
  latency_ms INT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

压缩策略：

```text
tool raw JSON < 4KB：可存 Postgres JSONB。
tool raw JSON 4KB-100KB：Postgres 存摘要和 key，原文入 S3。
tool raw JSON > 100KB：必须对象存储，prompt 只放结构化摘要。
进入 prompt 的工具结果建议控制在 300-800 tokens。
```

---

## 10. Audit Log：不是记忆，是可追责记录

审计日志回答的是：

```text
当时为什么这么判断？
依据是哪条政策？
调用了什么工具？
工具返回了什么关键事实？
模型版本是什么？
是否经过人工审批？
```

推荐表结构：

```sql
CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  case_id TEXT NOT NULL,
  thread_id TEXT,
  actor TEXT NOT NULL,                  -- agent / human / system
  action TEXT NOT NULL,                 -- policy_check / state_transition / tool_call / human_review
  input_refs JSONB,                     -- message ids, tool ids, policy refs
  output_refs JSONB,
  decision TEXT,
  reason TEXT,
  model_name TEXT,
  model_version TEXT,
  policy_refs JSONB,
  tool_call_ids TEXT[],
  before_state JSONB,
  after_state JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

审计日志建议 append-only。不要因为摘要更新而覆盖审计事实。

---

## 11. 长期记忆在业务型 Agent 中如何使用

业务型 Agent 可以有长期记忆，但范围要保守。

适合存的长期记忆：

1. Procedural Memory：稳定处理流程和回复方式。

```json
{
  "memory_type": "procedural",
  "scope": "refund_agent",
  "content": "退款场景中，如果缺少证据，先要求用户补充材料，不直接拒绝。",
  "source": "sop",
  "confidence": 1.0,
  "importance": 0.9
}
```

2. Case-level Episodic Memory：当前工单处理历史。

```json
{
  "memory_type": "episodic",
  "scope": "case",
  "case_id": "case_123",
  "content": "该工单已在 2026-06-17 要求用户补充物流状态截图。",
  "source": "case_summary",
  "confidence": 0.95,
  "importance": 0.8
}
```

3. 低风险用户沟通偏好。

```json
{
  "memory_type": "user_preference",
  "user_id": "u_001",
  "content": "用户希望使用中文沟通。",
  "source": "user_explicit",
  "confidence": 0.9,
  "importance": 0.6
}
```

不建议自动写入的内容：

- “用户经常投诉”。
- “用户退款风险高”。
- “用户态度不好”。
- “用户可能在骗退款”。
- 用户收入、健康、家庭、身份等敏感信息。
- 模型推测出的个性标签。

如果需要用户历史退款次数、账户风险分、黑名单状态，应来自正式业务系统或风控系统，不应作为 LLM 长期记忆。

---

## 12. Context Assembler：业务型 Agent 每轮如何组装 prompt

业务型 Agent 的 prompt 应该按“事实、约束、依据、当前问题”组织。

伪代码：

```python
def assemble_business_agent_context(user_id, case_id, thread_id, user_message):
    system = load_system_prompt("refund_agent")

    case_state = load_case_state(case_id)
    case_summary = load_case_summary(case_id)
    recent_messages = load_recent_messages(thread_id, limit_turns=6)

    policy_refs = retrieve_policy_chunks(
        query=build_policy_query(user_message, case_state),
        policy_status="active",
        top_k=5
    )

    tool_summaries = load_recent_tool_summaries(case_id, limit=5)

    user_prefs = retrieve_allowed_user_preferences(
        user_id=user_id,
        allowed_types=["communication_preference"],
        top_k=3
    )

    prompt = [
        system,
        render_business_constraints(),
        render_case_state(case_state),
        render_case_summary(case_summary),
        render_policy_refs(policy_refs),
        render_tool_summaries(tool_summaries),
        render_user_preferences(user_prefs),
        render_recent_messages(recent_messages),
        render_current_user_message(user_message),
    ]

    return trim_by_business_priority(prompt)
```

推荐 token budget：

| 模块 | 建议占比 | 裁剪策略 |
|---|---:|---|
| System + 安全/业务约束 | 10-15% | 不裁剪 |
| 当前用户问题 | 5-10% | 不裁剪 |
| Case State | 10-15% | 保留结构化关键字段 |
| Policy Snippets | 15-25% | 只保留当前适用条款 |
| Recent Messages | 20-30% | 保留最近 4-8 轮 |
| Case Summary | 5-10% | 压缩但不删除 |
| Tool Results Summary | 10-15% | raw JSON 不进 prompt |
| 回复预留 | 15-25% | 不挤占 |

裁剪优先级：

```text
先压缩工具原始结果
再减少历史消息轮数
再减少政策候选条款数量
再压缩 case summary
不要删除 system、安全约束、当前问题、关键 case state
```

---

## 13. Tombstone 在业务型 Agent 中的作用

Tombstone 是“删除墓碑”，用于防止用户删除过的记忆被旧对话重新抽取回来。

场景：

```text
系统记住：用户希望通过手机号接收通知。
用户要求删除这个偏好。
后来系统离线扫描旧聊天，发现用户以前说过手机号通知。
如果没有 tombstone，系统可能重新写入这条记忆。
```

处理方式：

```text
删除 memory → memories.status = deleted
写 tombstone → 记录 normalized_content_hash / memory_type / user_id / 删除原因
新候选记忆写入前 → 检查 tombstone
命中 tombstone → 拒绝自动写入，必要时要求用户显式确认
```

表结构示例：

```sql
CREATE TABLE memory_tombstones (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  memory_type TEXT,
  normalized_content_hash TEXT NOT NULL,
  reason TEXT NOT NULL,                 -- user_deleted / policy_delete / privacy_request
  created_at TIMESTAMPTZ DEFAULT now()
);
```

注意：审计日志和法定留存数据不应简单套用用户记忆 tombstone。用户记忆删除、业务审计留存、合规删除请求是不同制度，需要分别设计。

---

## 14. 存储架构

推荐 MVP 存储：

```text
Postgres
├── cases
├── case_states
├── messages
├── tool_calls
├── case_summaries
├── policies
├── policy_chunks
├── audit_logs
└── limited_memories

pgvector
├── policy_chunks.embedding
├── SOP chunks.embedding
└── historical_case_examples.embedding

Redis
├── active_case_state:{case_id}
├── working_state:{thread_id}
├── recent_tool_summary:{case_id}
└── retrieved_policy_cache:{case_id}

S3 / Object Storage
├── attachments
├── screenshots
├── large_tool_results
├── archived_raw_logs
└── evidence_files
```

各组件分工：

| 组件 | 职责 | 是否权威 |
|---|---|---:|
| Postgres | 工单、状态、消息、政策元数据、审计 | 是 |
| pgvector | 政策/SOP/历史案例语义检索 | 不是单独权威，依附 Postgres |
| Redis | 活跃工单缓存、working state、短期热数据 | 否 |
| S3 | 大附件、大工具结果、冷归档 | 对大对象是权威 |
| 日志系统 | 观测、告警、运行指标 | 部分审计可用，但不替代业务审计表 |

---

## 15. MVP 到成熟版本路线图

### MVP

目标：先让退款/政策审查流程可靠。

包括：

- cases / case_states。
- messages 原始日志。
- case_summaries。
- tool_calls。
- policy_chunks + pgvector。
- audit_logs。
- Redis 活跃 case 缓存。
- 人工审核入口。

不要一开始做复杂用户长期记忆。

### V1

目标：提高上下文质量和合规控制。

包括：

- 更严格的 Context Assembler。
- 工具结果结构化摘要。
- policy rerank。
- memory tombstone。
- 用户可见的有限偏好管理。
- 审计报表。
- 冲突检测：当前订单事实优先于历史对话。

### V2

目标：规模化和智能化运营。

包括：

- 热/温/冷分层。
- 历史案例检索辅助人工审核。
- 离线重摘要。
- 政策版本差异对比。
- 知识图谱表达政策条款之间的依赖。
- 多 Agent 协作：客服、政策、风控、人工审核协同。

---

## 16. 常见坑和防护

| 常见坑 | 后果 | 防护 |
|---|---|---|
| 用 prompt 维护退款状态 | 状态丢失、不可审计 | case_state 做权威源 |
| 让 LLM 凭记忆判断政策 | 政策过期、结论不可追溯 | 版本化 Policy KB + Rule Engine |
| 把所有历史对话塞 prompt | 成本高、噪声大、上下文污染 | 最近消息 + case summary |
| 工具 raw JSON 直接进 prompt | token 爆炸、关键信息淹没 | raw 入 S3，summary 入 prompt |
| Redis 当权威存储 | 宕机丢状态 | Redis 只做缓存 |
| 摘要覆盖原始日志 | 无法复核 | raw log 永久保留或按合规留存 |
| 用户删除偏好后又写回 | 违反用户意愿 | tombstone |
| 记忆覆盖当前订单事实 | 错判业务 | 当前工具事实和 case_state 优先 |
| 跨用户/租户召回 | 严重数据泄漏 | user_id / tenant_id 硬过滤 |
| 缺审计链 | 无法解释和追责 | audit log append-only |

---

## 17. 面试回答模板

问题：业务型 Agent 是否适合通用助手那套记忆机制？

回答：

```text
适合使用其中的上下文工程部分，但不能把它作为核心。业务型 Agent 的核心是业务状态机、规则引擎、工具执行和审计日志。比如退款 Agent 中，订单状态、政策版本、证据状态、审批结果必须由业务数据库和政策系统承载，不能靠 LLM 记忆。记忆机制主要用于最近对话摘要、工具结果压缩、政策片段注入 prompt 和低风险沟通偏好。长期用户记忆要非常谨慎，尤其不能自动记录带风险判断或敏感标签的用户信息。
```

---

## 18. 一句话总结

业务型 Agent 的记忆机制不是为了“长期了解用户”，而是为了“在结构化业务流程中提供更好的上下文”；真正的业务事实、政策依据和审计链必须由状态机、数据库、规则引擎和审计日志管理。
