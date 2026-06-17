# Phase 16: Long-term / Case Memory - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `16-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-06-17
**Phase:** 16-Long-term / Case Memory
**Areas discussed:** 记忆分层与 schema 切法, 写入来源与 review lifecycle, 检索与 prompt 注入, tombstone、no-rewrite 与 legacy quarantine

---

## 记忆分层与 schema 切法

| Option | Description | Selected |
| --- | --- | --- |
| Family + 分表 | 共享 `memory_identity.v1`、tombstone、review/write event 合同；`long_term_memories` 和 `case_memories` 分表。 | ✓ |
| 完全分离 | Long-term 与 case 各自闭环，边界清楚但重复治理逻辑。 | |
| 单泛表 | 一个 memory 表靠 `memory_type` 区分，最快但容易混淆语义。 | |

**User's choice:** Family + 分表。
**Notes:** 用户明确指出仓库文档与测试计划都指向“统一记忆契约、分开落表”；单泛表会冲掉“case memory 不是当前业务事实源”的边界。

### Semantic Episode Layer

| Option | Description | Selected |
| --- | --- | --- |
| 最小语义扩展 | 保留现有 `summaries` 表，通过新 `summary_type` / `summary_json` 约定产出 candidate。 | ✓ |
| 只读现有 summaries | 不改 summaries，只从现有 records 生成候选。 | |
| 完整 semantic conversation layer | 一次性加入完整语义字段，能力强但 Phase 16 scope 大。 | |
| 用户提供的 Semantic Episode Layer 设计参考 | 不改 `session_memories`，新增语义理解层作为 short-term memory V2。 | ✓ |

**User's choice:** 引入 Semantic Episode Layer。
**Notes:** `session_memory = 事实运行状态`，`semantic_episode = 理解层`，`case_memory = 长期已审计经验`。Semantic episode 不进 `session_memories`，不作为 business truth 或 policy evidence。

---

## 写入来源与 Review Lifecycle

| Option | Description | Selected |
| --- | --- | --- |
| Human-reviewed only | 所有 long-term/case memory 都必须人工 review 后才能检索。 | |
| Deterministic auto-approved + human review | 确定性事实和显式偏好可 auto-approved；LLM/semantic 候选必须 needs_review。 | ✓ |
| LLM candidate 可直接发布 | 最快，但会把模型猜测写成长期记忆。 | |

**User's choice:** 三通道写入模型。
**Notes:** Deterministic facts、explicit user preferences 可以自动批准；LLM、semantic episode、summary、pattern mining、similarity inference 必须 `needs_review`。

### Published 状态

| Option | Description | Selected |
| --- | --- | --- |
| 沿用契约枚举 | DB 只用 `review_status`，published 是 retrieval predicate。 | ✓ |
| 新增 `published` 状态 | 表达直观，但偏离现有 spec 枚举。 | |
| 双字段状态机 | `review_status` 管 review，`publication_status` 管发布，清晰但重。 | |

**User's choice:** 沿用契约枚举。
**Notes:** `review_status in ('auto_approved', 'approved')` 且未 tombstone/deleted/expired/prohibited 才可检索。“usable in retrieval”不是状态。

---

## 检索与 Prompt 注入

### Retrieval Depth

| Option | Description | Selected |
| --- | --- | --- |
| Predicate-first baseline | 只做结构化 predicate 检索，pgvector/hybrid 预留。 | |
| Metadata-first + pgvector | 强过滤后 pgvector top-k，light rerank；不做 full hybrid/RRF。 | ✓ |
| 完整 hybrid retrieval | metadata-first + dense + lexical + RRF + threshold eval。 | |

**User's choice:** Metadata-first + pgvector。
**Notes:** Phase 16 是结构化经验复用层，不是搜索引擎工程。MVP 使用 hard filter -> pgvector top-k=10~30 -> light rerank -> prompt injection。

### Long-term Profile Retrieval

| Option | Description | Selected |
| --- | --- | --- |
| Long-term predicate-only，case memory pgvector | Profile 是结构化约束系统；case memory 是语义经验系统。 | ✓ |
| 两者都 pgvector | 统一检索体验，但 profile 容易语义误召回。 | |
| 两者都 predicate-only | 最安全，但 case memory 相似案例能力弱。 | |

**User's choice:** Long-term profile predicate-only，case memory pgvector。
**Notes:** 用户强调 profile memory 是 key-value / structured constraint，不是 similarity-based knowledge。

### ContextAssembler Position

| Option | Description | Selected |
| --- | --- | --- |
| Policy/business 之后，recent messages 之前 | Memory 有用但不压过当前事实和政策。 | ✓ |
| thread summary 之后立刻注入 | 语义连续性强，但可能早于 policy/business。 | |
| 最后靠近 user query | 模型更容易看到，但容易当成当前事实。 | |

**User's choice:** Policy/business 之后，recent messages 之前。
**Notes:** Prompt ordering principle: `FACT FIRST -> CONTEXT -> MEMORY -> HISTORY -> USER`。

### Memory Budget

| Option | Description | Selected |
| --- | --- | --- |
| 严格小块 | Profile <=3，case <=3，总 memory block <=1600 chars。 | ✓ |
| 中等上下文 | Profile 5 条，case 5 条，总约 2500-3500 chars。 | |
| 按 token budget 动态填满 | 灵活，但测试边界更难稳定。 | |

**User's choice:** 严格小块。
**Notes:** Fixed schema and hard length limit make prompt behavior deterministic and testable.

---

## tombstone、no-rewrite 与 legacy quarantine

### Legacy `search_case_memory`

| Option | Description | Selected |
| --- | --- | --- |
| Quarantine legacy + 新增 reviewed retrieval | 旧路径不再声称 case memory，新路径只读 reviewed store。 | ✓ |
| 保留旧名但改变实现 | 兼容性好，但容易掩盖语义变化。 | |
| 删除 legacy tool | 干净，但可能破坏 tool catalog / allowlist。 | |

**User's choice:** Legacy quarantine + 新增 reviewed retrieval。
**Notes:** 旧系统是不可信 heuristic；新系统是 reviewed production path。Legacy 可 debug/fallback，v2 后期再删除。

### Tombstone No-Rewrite

| Option | Description | Selected |
| --- | --- | --- |
| canonical identity + source identity fallback | 精确 identity 匹配，阻止异步写回并可审计。 | ✓ |
| 只按 content_hash | 简单，但 source-derived candidate 可能绕过删除。 | |
| content_hash + 语义相似度 | 覆盖更广，但容易误删/误挡。 | |

**User's choice:** canonical identity + source identity fallback。
**Notes:** Tombstone 必须 identity-based，不使用 semantic similarity。命中后同事务 skip/write_blocked 并写 `memory_write_event(reason_code='tombstone_match')`。

---

## the agent's Discretion

- Exact module names and service boundaries remain open for planning.
- Exact pgvector index settings and rerank normalization can be researched.
- Semantic Episode Layer representation may be implemented through `summaries` extensions, extractor projection, or a lightweight helper, provided it does not become authoritative business/policy memory.

## Deferred Ideas

- Full hybrid retrieval with lexical + RRF.
- Full memory management UI.
- Reviewed strategy pattern and preference-memory family expansion beyond the Phase 16 baseline.
- Final removal of legacy `search_case_memory` after reviewed retrieval is validated.
