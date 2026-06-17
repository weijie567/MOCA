# 通用 / 个人助手 Agent 的记忆机制设计

适用对象：通用智能助手、个人学习助手、工作助理、项目助理、代码学习助手、长期陪伴型生产力 Agent。

核心结论：通用/个人助手 Agent 的主轴是记忆系统。它需要长期理解用户是谁、正在做什么、偏好什么、上次做到哪里，以及如何更省力地继续帮助用户。它仍然需要轻量 working state 和局部任务状态，但这些主要服务于当前任务执行，而不是像业务型 Agent 那样用严格状态机驱动所有流程。

---

## 1. 与业务型 Agent 的根本区别

```text
业务型 Agent：流程状态是核心，记忆是辅助上下文。
通用/个人助手：用户记忆是核心，流程状态是局部执行能力。
```

通用助手面对的不是一个固定退款流程，而是长期、多主题、多项目的协作：

- 学习计划。
- 求职准备。
- 项目推进。
- 写作。
- 日程管理。
- 邮件处理。
- 文件整理。
- 代码调试。
- 长期偏好适配。

因此，它必须沉淀用户偏好、长期目标、项目历史、学习进度、稳定工作方式和重要事件。

---

## 2. 总体架构

```text
User
  ↓
Conversation API
  ↓
Raw Log Writer
  ↓
Context Assembler
  ├── System Prompt
  ├── Current User Message
  ├── Recent Messages
  ├── Working Memory / Lightweight State
  ├── Short-term Memory / Thread Summary
  ├── Long-term Personal Memory
  │     ├── Semantic Memory
  │     ├── Episodic Memory
  │     └── Procedural Memory
  ├── Task State
  ├── Recent Tool Result Summary
  └── External Data Sources
        ├── Calendar
        ├── Gmail / Email
        ├── Drive / Docs / Files
        ├── Notes
        ├── GitHub / Code Repo
        └── Search / Browser
  ↓
LLM / Agent Runtime
  ↓
Response / Tool Call / Task Update
  ↓
Persistence
  ├── messages
  ├── thread_summaries
  ├── working_state cache
  ├── memories
  ├── memory_events
  ├── memory_tombstones
  ├── tasks
  └── tool_calls
```

---

## 3. 先澄清：短期记忆不是上下文窗口

这是最容易混淆的点。

```text
短期记忆 = 系统在模型外部保存的近期上下文。
上下文窗口 = 本轮真正发给模型看的输入包。
```

短期记忆通常包括：

- 当前 thread 的 rolling summary。
- 最近若干轮消息。
- 当前目标。
- 未解决问题。
- 最近工具结果摘要。
- 当前主题。

上下文窗口是每轮由 Context Assembler 临时组装的：

```text
System Prompt
+ Current User Message
+ Recent Messages
+ Short-term Summary
+ Working State
+ Retrieved Long-term Memories
+ Tool Result Summary
+ External Context
= 本轮 Context Window
```

一条历史消息的身份可能有三种：

```text
1. Raw Conversation Log：完整保存的原始聊天记录。
2. Short-term Memory Source：用于生成或更新摘要。
3. Context Window Part：被本轮选中后，才进入模型输入。
```

因此：

```text
聊天界面里看到的历史消息 ≠ 模型本轮一定完整看到的上下文。
历史消息只有被选中并放入 prompt 时，才是本轮上下文窗口的一部分。
```

---

## 4. 数据分层和权威性

| 数据层 | 作用 | 存储 | 是否权威 | 是否默认进入 prompt |
|---|---|---|---:|---:|
| Raw Conversation Log | 完整对话记录 | Postgres + S3 | 是 | 否 |
| Working Memory | 当前回合工作台 | 内存 / Redis / Postgres checkpoint | 不是长期权威 | 是，摘要进入 |
| Short-term Memory | 当前 thread 摘要和近期上下文 | Postgres / Redis | 派生 | 是 |
| Long-term Semantic Memory | 稳定偏好、长期事实、目标 | Postgres + pgvector | 是 | 检索后少量进入 |
| Long-term Episodic Memory | 重要事件、项目进度、上次做到哪里 | Postgres + pgvector | 是 | 检索后少量进入 |
| Long-term Procedural Memory | 用户喜欢的协作方式 | Postgres + pgvector | 是 | 检索后少量进入 |
| Task State | 提醒、邮件、日程、自动化任务状态 | Postgres | 是 | 相关时进入 |
| External Data | 日历、邮件、文件、代码仓库 | 外部系统 | 是 | 按需检索进入 |
| Memory Block | prompt 中的记忆片段 | 临时 prompt | 否 | 是 |

关键原则：

```text
记忆负责理解用户。
工具源负责获取事实。
任务状态负责执行到哪一步。
上下文窗口只是本轮给模型看的材料包。
```

---

## 5. Raw Conversation Log：完整历史记录

Raw Log 是完整事实记录，不是短期记忆，也不是上下文窗口。

作用：

- 用户问“你刚才说过什么”时可回溯。
- 重新生成摘要。
- 解释某条长期记忆的来源。
- Debug 模型或工具行为。
- 支持用户导出、删除、查看历史。

推荐表结构：

```sql
CREATE TABLE threads (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE messages (
  id BIGSERIAL PRIMARY KEY,
  thread_id TEXT NOT NULL REFERENCES threads(id),
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,                   -- user / assistant / tool / system
  content TEXT,
  content_type TEXT DEFAULT 'text',      -- text / json / file_ref / image_ref
  tool_call_id TEXT,
  token_count INT,
  pii_level TEXT DEFAULT 'unknown',      -- none / low / medium / high
  object_key TEXT,                       -- 大文本、附件、工具结果的位置
  created_at TIMESTAMPTZ DEFAULT now()
);
```

存储策略：

```text
普通消息 → Postgres messages.content
大段代码 / 文件 / PDF / 图片 → S3，对象 key 写入 messages.object_key
大型工具返回 → S3，tool_calls 表保存摘要和 object_key
```

注意：摘要不能替代原始日志。摘要会丢细节、会压缩错误、会受模型误解影响，不能作为唯一事实源。

---

## 6. Working Memory：Prompt Context + Lightweight Working State

通用助手里的 working memory 可以理解成当前回合的工作台。

它由两部分组成：

```text
Working Memory = 本轮 prompt context + lightweight working state
```

其中 lightweight working state 存的是当前任务相关的临时结构化状态：

- current_goal：当前目标。
- active_topic：当前主题。
- open_questions：未解决问题。
- constraints：本轮约束。
- recent_tool_results：最近工具结果摘要。
- draft_artifact：当前草稿。
- active_project：当前项目。
- pending_actions：待确认动作。
- last_user_intent：上轮意图。

示例：

```json
{
  "thread_id": "thread_agent_memory",
  "user_id": "u_001",
  "current_goal": "帮助用户理解通用个人助手的记忆机制",
  "active_topic": "short-term memory vs context window",
  "active_project": "AI Agent 学习",
  "open_questions": [
    "历史消息和上下文窗口是什么关系",
    "working memory 应该存在哪里"
  ],
  "constraints": [
    "中文",
    "工程化解释",
    "不要泛泛而谈"
  ],
  "recent_tool_results": [],
  "draft_artifact": null,
  "pending_actions": []
}
```

存储选择：

| 场景 | 存储 | 说明 |
|---|---|---|
| 单轮请求 / demo | 进程内内存 | 请求结束可丢弃 |
| 多实例部署 | Redis | 多台服务共享活跃 thread 状态 |
| 需要恢复 | Postgres checkpoint | 服务重启后恢复任务状态 |
| 长期保存 | 不建议直接长期化 | 应抽取成长期 memory 或 task state |

推荐：

```text
活跃 thread 的 working state 放 Redis。
关键任务的 checkpoint 写 Postgres。
请求生命周期内再构造 prompt context。
```

---

## 7. Short-term Memory：当前会话/当前任务周期的记忆

短期记忆服务的是“当前一段对话能连续下去”。它不是长期用户画像。

建议默认参数：

```text
messages 原文：DB 中保留最近 20-50 条，长期全量保存在 raw log。
prompt 默认取最近 6-10 轮。
rolling summary：按 thread 保存，生命周期 2-24 小时或 thread 生命周期。
工具结果摘要：保留最近 3-10 个关键结果。
```

短期记忆结构：

```json
{
  "thread_id": "thread_agent_memory",
  "rolling_summary": "用户正在学习 AI Agent 记忆机制，已经对比业务型 Agent 和个人助手 Agent，目前正在澄清短期记忆、上下文窗口、历史消息、working memory 的关系。",
  "current_goal": "建立一套清晰的记忆分层心智模型",
  "active_entities": [
    "working memory",
    "short-term memory",
    "context window",
    "raw conversation log"
  ],
  "open_questions": [
    "历史消息什么时候进入上下文窗口"
  ],
  "last_tool_results_summary": [],
  "last_user_preference_hints": [
    "用户希望用中文、详细、工程化方式解释"
  ],
  "updated_at": "2026-06-17T10:00:00Z"
}
```

表结构：

```sql
CREATE TABLE thread_summaries (
  thread_id TEXT PRIMARY KEY REFERENCES threads(id),
  user_id TEXT NOT NULL,
  summary_json JSONB NOT NULL,
  summary_text TEXT,
  source_message_start BIGINT,
  source_message_end BIGINT,
  token_count INT,
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

更新触发：

- 每 3-5 轮更新一次。
- 最近消息累计超过 6k-10k tokens 更新。
- 上下文窗口使用率超过 70% 更新。
- 检测到话题切换时更新。
- 工具返回重要结果后更新。
- thread 结束或用户要求总结时更新。

摘要 prompt 模板：

```text
你是个人助手的会话摘要器。请基于旧摘要和新增消息更新 thread summary。

必须保留：
1. 用户当前目标。
2. 已确认事实。
3. 关键决策。
4. 未解决问题。
5. 用户偏好线索。
6. 当前项目或主题。
7. 不可丢失的约束。
8. 最近工具结果的关键结论。

必须删除：
1. 寒暄。
2. 重复表达。
3. 不影响后续任务的细节。
4. 模型猜测。

旧摘要：{old_summary}
新增消息：{new_messages}
请输出 JSON。
```

增量摘要伪代码：

```python
def maybe_update_thread_summary(thread_id):
    summary = load_thread_summary(thread_id)
    new_messages = load_messages_after(thread_id, summary.source_message_end)

    if not should_update_summary(summary, new_messages):
        return summary

    new_summary = llm_summarize(
        old_summary=summary.summary_json,
        new_messages=new_messages,
        schema="thread_summary_v1"
    )

    validate_summary(new_summary)
    save_thread_summary(thread_id, new_summary)
    return new_summary


def should_update_summary(summary, new_messages):
    return (
        len(new_messages) >= 6
        or count_tokens(new_messages) > 8000
        or detect_topic_shift(new_messages)
        or context_window_usage() > 0.70
    )
```

用户问“刚才我们聊到哪儿了？”时：

```text
优先读取 thread_summary。
如果用户问具体原话，回查 raw messages。
如果问上次某项目进展，结合 episodic memory + project summary。
```

---

## 8. Long-term Memory：通用助手的核心

通用助手的长期记忆至少分三类。

### 8.1 Semantic Memory：稳定事实、偏好、长期目标

适合存：

- 用户偏好中文。
- 用户正在学习 AI Agent。
- 用户目标是提升 AI 产品经理能力。
- 用户常用 Python / VS Code / macOS。
- 用户有某个长期项目。

不适合存：

- 一次性任务中间状态。
- 模型推测的性格。
- 临时情绪。
- 高敏感 PII。
- 未确认的健康、财务、家庭、身份信息。

示例：

```json
{
  "memory_type": "semantic",
  "content": "用户正在系统学习 AI Agent 架构，重点关注记忆机制、状态机、工具调用和上下文工程。",
  "confidence": 0.92,
  "importance": 0.86,
  "source": "repeated_conversation",
  "status": "active"
}
```

### 8.2 Episodic Memory：重要事件和项目进度

适合存：

- 上次某项目讨论到哪一步。
- 某个长期学习计划已经完成哪些阶段。
- 用户对某个架构做过什么决策。
- 某次重要对话的结论。

示例：

```json
{
  "memory_type": "episodic",
  "scope": "project",
  "project_id": "agent_memory_learning",
  "content": "用户已经理解业务型 Agent 应以状态机和审计为核心，现在正在对比个人助手 Agent 的记忆机制。",
  "confidence": 0.9,
  "importance": 0.78,
  "source": "thread_summary"
}
```

### 8.3 Procedural Memory：稳定协作方式

适合存：

- 用户喜欢先讲结论，再讲细节。
- 用户偏好中文、结构化、工程化解释。
- 用户希望复杂概念配 JSON、伪代码、架构图。
- 用户需要面试视角。

示例：

```json
{
  "memory_type": "procedural",
  "content": "用户偏好中文、结构化、工程化解释；复杂概念需要用对比表、JSON、伪代码和架构图说明。",
  "confidence": 0.95,
  "importance": 0.9,
  "source": "repeated_preference"
}
```

---

## 9. Memories 表、事件表和 Tombstone

推荐 memories 表：

```sql
CREATE TABLE memories (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  memory_type TEXT NOT NULL,            -- semantic / episodic / procedural
  scope TEXT DEFAULT 'global',           -- global / project / task / assistant
  project_id TEXT,
  content TEXT NOT NULL,
  normalized_content TEXT,
  embedding VECTOR(1536),
  importance REAL DEFAULT 0.5,
  confidence REAL DEFAULT 0.5,
  source TEXT NOT NULL,                 -- user_explicit / repeated / inferred / imported / summary
  source_message_ids BIGINT[],
  sensitivity TEXT DEFAULT 'normal',     -- normal / sensitive / restricted
  status TEXT DEFAULT 'active',          -- active / decayed / archived / deleted / superseded
  expires_at TIMESTAMPTZ,
  last_accessed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

memory_events 记录生命周期：

```sql
CREATE TABLE memory_events (
  id BIGSERIAL PRIMARY KEY,
  memory_id BIGINT REFERENCES memories(id),
  user_id TEXT NOT NULL,
  event_type TEXT NOT NULL,              -- created / updated / accessed / deleted / superseded / confirmed
  event_payload JSONB,
  actor TEXT DEFAULT 'system',           -- user / system / admin
  created_at TIMESTAMPTZ DEFAULT now()
);
```

memory_tombstones 防止删除后又被写回：

```sql
CREATE TABLE memory_tombstones (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  memory_type TEXT,
  normalized_content_hash TEXT NOT NULL,
  reason TEXT NOT NULL,                  -- user_deleted / privacy_request / policy_block
  created_at TIMESTAMPTZ DEFAULT now()
);
```

Tombstone 的作用：

```text
用户删除某条记忆后，即使旧对话里还存在相关原文，系统离线抽取记忆时也不能自动把它重新写回来。
```

流程：

```text
用户删除记忆
  ↓
memories.status = deleted
  ↓
写入 memory_tombstones
  ↓
新 memory candidate 写入前检查 tombstone
  ↓
命中则拒绝自动写入，除非用户再次明确要求记住
```

---

## 10. 长期记忆什么时候写入

通用助手可以比业务型 Agent 更积极地写长期记忆，但必须有门控。

写入条件：

- 用户显式说“记住”。
- 某个偏好重复出现 2-3 次以上。
- 对未来任务明显有帮助。
- 信息相对稳定。
- 低隐私风险。
- 置信度足够高。
- 与旧记忆不冲突。
- 不命中 tombstone。
- 敏感信息需要确认。

候选记忆抽取流程：

```text
raw messages
  ↓
candidate extraction
  ↓
importance scoring
  ↓
PII / sensitivity filter
  ↓
dedup
  ↓
conflict detection
  ↓
tombstone check
  ↓
user confirmation if needed
  ↓
write memory
```

候选记忆 JSON：

```json
{
  "type": "procedural",
  "content": "用户偏好中文、结构化、工程化解释，复杂概念希望配 JSON 和伪代码。",
  "source": {
    "thread_id": "thread_agent_memory",
    "message_ids": [101, 108, 115]
  },
  "confidence": 0.94,
  "importance": 0.88,
  "ttl": null,
  "requires_confirmation": false,
  "sensitivity": "normal"
}
```

绝对不应自动写入：

- 模型猜测。
- 密码、API key、身份证号、银行卡号。
- 一次性任务中间状态。
- 临时情绪或主观标签。
- 过期事实。
- 用户未确认的敏感偏好。
- 与旧记忆冲突的新事实。
- 用户已经删除过且命中 tombstone 的内容。

---

## 11. 长期记忆如何检索召回

检索不能只靠向量相似度。推荐 hybrid retrieval：

```text
metadata filter
+ vector similarity
+ BM25 / keyword search
+ recency / importance / confidence scoring
+ rerank
```

硬过滤：

```text
user_id = 当前用户
scope / project_id 匹配当前任务
status = active
expires_at 未过期
未删除
未被 tombstone 阻止
敏感级别允许用于当前场景
```

打分公式示例：

```text
final_score =
0.45 * semantic_similarity
+ 0.20 * recency_score
+ 0.20 * importance
+ 0.15 * confidence
```

如果需要加入来源可信度：

```text
final_score =
0.40 * semantic_similarity
+ 0.20 * recency_score
+ 0.20 * importance
+ 0.10 * confidence
+ 0.10 * source_trust
```

召回流程：

```text
当前用户问题
  ↓
构造 memory query
  ↓
向量检索 top 20
  ↓
关键词/BM25 补充 top 20
  ↓
合并去重
  ↓
metadata filter
  ↓
rerank
  ↓
选 top 5-10
  ↓
压缩成 memory snippets
  ↓
组装成 memory block
  ↓
放入 prompt
```

Memory Snippet 是一条压缩后的记忆：

```text
用户偏好中文、结构化、工程化解释。
```

Memory Block 是多条 snippet 组成的 prompt 区块：

```text
[Relevant Personal Memories]
- procedural: 用户偏好中文、结构化、工程化解释，复杂概念需要 JSON、伪代码和架构图。confidence=0.95
- semantic: 用户正在学习 AI Agent 架构，重点关注 memory、state、tool、prompt 的关系。confidence=0.92
- episodic: 用户刚对比过业务型 Agent 和个人助手 Agent 的记忆机制。confidence=0.90
```

注意：Memory Block 不是数据库。它只是本轮临时塞进 prompt 的上下文片段。

---

## 12. Context Assembler：每轮如何组装上下文窗口

伪代码：

```python
def handle_turn(user_id, thread_id, user_message):
    save_raw_message(thread_id, user_id, "user", user_message)

    working_state = load_working_state(thread_id)
    thread_summary = load_thread_summary(thread_id)
    recent_messages = load_recent_messages(thread_id, limit_turns=8)

    intent = classify_intent(user_message)

    memory_query = build_memory_query(
        user_message=user_message,
        working_state=working_state,
        thread_summary=thread_summary
    )

    memories = retrieve_memories(
        user_id=user_id,
        query=memory_query,
        scope=detect_scope(working_state, user_message),
        top_k=10
    )

    external_context = retrieve_external_context_if_needed(
        intent=intent,
        user_message=user_message
    )

    tool_results = load_recent_tool_result_summaries(thread_id, limit=5)

    prompt = assemble_prompt(
        system_prompt=load_system_prompt(),
        working_state=working_state,
        thread_summary=thread_summary,
        memories=memories,
        recent_messages=recent_messages,
        tool_results=tool_results,
        external_context=external_context,
        current_user_message=user_message
    )

    prompt = trim_by_token_budget(prompt)

    response = agent_runtime(prompt)

    save_raw_message(thread_id, user_id, "assistant", response.text)
    update_working_state(thread_id, response.state_updates)
    maybe_update_thread_summary(thread_id)
    maybe_extract_and_write_memories(user_id, thread_id)

    return response.text
```

---

## 13. Token Budget：谁能进入窗口，进入多少

Token budget 是上下文窗口的容量分配规则。模型一次能看的内容有限，所以必须决定哪些信息进 prompt、进多少、超了先裁谁。

以 128k context 为例，推荐初始分配：

| 模块 | 建议占比 | 说明 |
|---|---:|---|
| System Prompt | 5-10% | 身份、安全、能力边界 |
| 当前用户问题 | 5-10% | 必保留 |
| Working State | 3-5% | 当前目标、约束、open questions |
| Short-term Summary | 5-10% | 当前 thread 概览 |
| Recent Messages | 25-35% | 最近 6-10 轮 |
| Long-term Memory Block | 5-10% | top 5-10 条 snippet |
| Tool Result Summary | 10-15% | 原始 JSON 不直接进入 |
| External Context | 10-20% | 文件、日历、邮件、代码片段等 |
| Response Reserve | 15-25% | 给模型输出预留 |

裁剪策略：

```text
1. system prompt、当前用户问题、回复预留不裁剪。
2. 工具 raw JSON 永不直接进入，先结构化压缩。
3. 长期记忆只保留最相关 top 5-10。
4. 最近对话保留最近 6-10 轮。
5. 更早对话进入 rolling summary。
6. 外部文件只放相关片段，不放全文。
7. context window 使用率超过 70% 触发摘要。
8. 超过 85% 强制上下文卸载。
```

示例：

```text
原始上下文：
System 1k
当前问题 500
最近对话 12k
长期记忆 3k
工具结果 20k
外部文件 30k
回复预留 4k
总计 70.5k

裁剪后：
System 1k
当前问题 500
最近对话 6k
短期摘要 1k
长期记忆 800
工具摘要 1k
外部文件片段 6k
回复预留 4k
总计 20.3k
```

---

## 14. Tool JSON、工具结果和记忆的分工

工具原始返回叫 tool JSON。它可能来自搜索、日历、邮件、代码执行、数据库查询等。

不要把 tool JSON 等同于 working memory，也不要把它全部放进 prompt。

正确分工：

```text
完整 tool JSON → tool_calls / S3
结构化关键字段 → tool_calls.normalized_result
摘要 → working_state.recent_tool_results
必要结论 → prompt context
如果稳定且未来有用 → 经过门控后成为长期 memory candidate
```

示例：

```json
{
  "tool_name": "calendar.search_events",
  "raw_result_ref": "s3://tool-results/thread_123/calendar_turn_7.json",
  "summary": "明天下午 14:00-15:00 有项目例会，16:00-17:00 空闲。",
  "used_in_response": true
}
```

这里“明天下午 14:00 有会议”通常不应该写成长期记忆。日历是权威源，下次需要时重新查日历。

---

## 15. Task State：个人助手也需要局部状态机

个人助手不是完全没有状态机。涉及可执行动作时，必须有 task state。

典型场景：

- 设置提醒。
- 创建日程。
- 发送邮件。
- 自动跟进任务。
- 多步骤文件处理。
- 长期学习计划追踪。
- 需要用户确认的高风险操作。

任务表：

```sql
CREATE TABLE tasks (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  task_type TEXT NOT NULL,              -- reminder / email_draft / calendar_event / follow_up / project_task
  status TEXT DEFAULT 'active',          -- active / awaiting_confirmation / completed / cancelled / failed
  schedule JSONB,
  payload JSONB,
  related_memory_ids BIGINT[],
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

发邮件示例：

```json
{
  "task_id": "task_123",
  "task_type": "send_email",
  "status": "awaiting_confirmation",
  "draft": {
    "to": "someone@example.com",
    "subject": "Meeting Follow-up",
    "body": "..."
  },
  "next_action": "等待用户确认后发送"
}
```

原则：

```text
长期记忆记录“用户偏好怎么写邮件”。
Task State 记录“这封邮件写到哪一步”。
Email API 是“邮件是否真的发出”的权威源。
```

---

## 16. 外部个人数据源不是普通记忆

通用助手经常接入日历、邮件、文件、代码仓库、笔记。不要把这些全部抽成长期记忆。

| 问题 | 权威源 | 记忆如何辅助 |
|---|---|---|
| 明天下午有什么安排 | Calendar | 记住用户偏好不要早会 |
| 上封邮件谁发的 | Email API | 记住用户常用回复风格 |
| 继续某个项目 | Project memory + GitHub/Docs | 记住项目目标和上次决策 |
| 总结某个文件 | File/Drive | 记住用户偏好的摘要格式 |
| 制定学习计划 | Long-term memory | 结合用户目标和过往进度 |

原则：

```text
具体事实查权威源。
长期记忆提供个性化上下文。
```

---

## 17. 遗忘机制和生命周期

状态建议：

```text
active       当前有效

decayed      重要性衰减，默认少召回

archived     冷归档，正常不召回

superseded   被新记忆替代

deleted      用户或系统删除

tombstoned   删除墓碑，阻止旧内容自动写回
```

TTL 建议：

| 记忆类型 | TTL 建议 |
|---|---|
| 长期偏好 | 无 TTL，定期复核 |
| 长期目标 | 6-12 个月复核 |
| 项目进度 | 项目结束后 3-12 个月归档 |
| 临时计划 | 到期后自动过期 |
| 工具结果摘要 | 1-7 天 |
| thread summary | thread 生命周期或 2-24 小时热缓存 |

衰减公式：

```python
import math

def decayed_importance(base_importance, age_days, half_life_days):
    return base_importance * math.exp(-math.log(2) * age_days / half_life_days)
```

示例：

```text
普通偏好 half_life = 180 天
项目事件 half_life = 60 天
临时计划 half_life = 7 天
高重要显式记忆不自动衰减或衰减很慢
```

用户纠正旧记忆时：

```text
旧记忆 status = superseded
新记忆 status = active
memory_events 记录 supersede 关系
```

用户删除记忆时：

```text
memory.status = deleted
写 memory_tombstone
从 Redis cache 清理
向量检索过滤 deleted
离线重抽取检查 tombstone
```

---

## 18. 存储架构和成本分层

推荐 MVP：Postgres + pgvector + Redis + S3。

```text
Postgres
├── users
├── threads
├── messages
├── thread_summaries
├── memories
├── memory_events
├── memory_tombstones
├── tasks
└── tool_calls

pgvector
└── memories.embedding

Redis
├── working_state:{thread_id}
├── recent_messages_cache:{thread_id}
├── top_memories_cache:{user_id}
└── tool_summary_cache:{thread_id}

S3 / Object Storage
├── attachments
├── long_raw_logs
├── large_tool_results
├── uploaded_files
└── archived_conversations
```

热/温/冷分层：

| 层 | 数据 | 存储 |
|---|---|---|
| 热 | 活跃 thread、working state、最近工具结果、top memories | Redis |
| 温 | messages、summaries、memories、tasks、embedding | Postgres + pgvector |
| 冷 | 大附件、历史归档、大工具结果、旧对话导出 | S3 |

为什么 MVP 用 Postgres + pgvector 足够：

- 数据模型简单。
- 权限、状态、删除、来源、置信度都能和记忆放在一张表里。
- 向量检索可以和 metadata filter 放在同一个事务系统附近。
- 运维成本低。

什么时候升级专用向量库或知识图谱：

- 向量规模达到数千万以上。
- 检索 QPS 很高，pgvector 成为瓶颈。
- 需要复杂多跳关系查询。
- 需要离线批量重嵌入、重摘要、重聚类。
- 项目、人物、组织、事件关系非常复杂。

---

## 19. 生产级风险和防护

| 风险 | 表现 | 防护 |
|---|---|---|
| 把所有历史塞 prompt | 成本高、噪声大、注意力稀释 | short-term summary + recent messages |
| 长期记忆污染 | 模型猜测被当成事实 | 写入门控 + confidence + source |
| 只用向量库 | 无权限、无状态、难删除 | Postgres 做权威，向量只是索引 |
| 摘要替代原始日志 | 无法回溯原话 | raw log 永久保存或按政策留存 |
| Redis 当权威 | 数据丢失 | Redis 只做 hot cache |
| 删除后自动写回 | 侵犯用户控制权 | tombstone |
| 旧记忆覆盖当前输入 | 回答不听当前用户 | 当前消息优先级最高 |
| 外部事实靠记忆回答 | 日程/邮件过期或错误 | 查外部权威源 |
| 跨用户召回 | 严重隐私泄漏 | user_id / tenant_id 硬过滤 |
| 过度个性化 | 助手固化错误偏好 | 用户可管理记忆 + 定期复核 |

---

## 20. MVP 到成熟版本路线图

### MVP

目标：让助手具备基本连续性和个性化。

包括：

- Raw conversation log。
- Thread rolling summary。
- Working state in Redis。
- memories 表。
- pgvector 检索。
- 简单写入门控。
- top memories 进入 prompt。
- 用户可查看/删除记忆的基础接口。

### V1

目标：提高记忆质量和用户控制。

包括：

- memory_events。
- memory_tombstones。
- hybrid retrieval。
- conflict detection。
- sensitivity filter。
- user confirmation flow。
- project-level memory。
- task state。
- external sources 接入：Calendar / Email / Files。

### V2

目标：成熟个人操作系统型助手。

包括：

- 热/温/冷存储分层。
- 离线重摘要。
- 离线记忆合并和去重。
- 个性化 procedural memory。
- 项目知识图谱。
- 多 Agent 协同。
- 自动复盘用户目标。
- 记忆质量评估和回滚。

---

## 21. 评估指标

通用助手记忆系统可以这样评估：

| 指标 | 含义 |
|---|---|
| Memory Precision | 召回的记忆是否相关、正确 |
| Memory Recall | 应该记得的内容是否被召回 |
| Wrong Memory Rate | 错误记忆进入 prompt 的比例 |
| Memory Write Acceptance | 用户接受写入的比例 |
| Memory Delete Compliance | 删除后是否不再使用和写回 |
| Context Cost | 每轮记忆相关 token 成本 |
| Latency | 检索和组装上下文耗时 |
| User Correction Rate | 用户纠正助手记忆的频率 |
| Continuity Score | 用户是否觉得助手接得住上下文 |
| Task Success Rate | 结合记忆后任务完成率是否提升 |

---

## 22. 一句话总结

通用/个人助手的记忆机制核心，是用 raw log 保留事实、用 short-term summary 延续当前对话、用 long-term semantic/episodic/procedural memory 沉淀用户长期上下文、用 Context Assembler 在每轮选择最相关的信息进入窗口，并用写入门控、检索过滤、遗忘和 tombstone 保证记忆可信、可控、可删除。
