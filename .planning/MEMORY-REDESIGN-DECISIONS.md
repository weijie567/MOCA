# 记忆机制重设计 — 决策记录

> 状态:**探索性设计决策,尚未进入 GSD plan-phase**。本文件是一次关于 MOCA 记忆分层的讨论收敛,作为后续 plan-phase 的干净输入。命名不动、schema 改动走评审、Case Working Context 定位为"非权威可修正"。
> 创建日期:2026-07-02
> 关联:`ARCHITECTURE-DEBT.md`(memory 是四个核心子系统债务中的第四个);memory 子系统源码在 `src/memory/`、`src/agent/nodes/`、`src/agent/context/`。

---

## 一、触发这次讨论的仓库事实(已核实,非推测)

以下均通过只读代码/查库确认,不是文档转述:

1. **治理层两张表在本地库全空**:`long_term_memories = 0`、`case_memories = 0`、`memory_write_events = 0`、`memory_tombstones = 0`;只有 `session_memories = 13`(本地 `moca` 库,`moca-postgres-1` 容器)。
2. **治理层写路径本身是通的**:在 `moca_test` 用临时 harness 显式传入 long_term/case 候选,三张表都正常长出记录(event 分别为 `long_term_fact/needs_review/requires_review`、`case_memory/needs_review/requires_review`),验后未污染主库。
3. **但生产代码里没有任何节点给 long_term/case 喂候选**:`memory_write` 默认只构造 session 候选;long_term/case 只消费 `state.memory_write_candidates`,而该字段在 `receive_request`(图入口)每轮被清空为 `[]`,全库(src)再无写入方。→ 治理层是"建好但没接输入管的机器",三表空的病根是**没有候选生成**,不是"审核空转"。
4. **session 记忆按 thread 分,不按 case 分**:唯一键 `(tenant, user, thread)`。`session_memories` 表**没有任何 case 字段**(已核实完整列;早期草稿误写"已挂 refund_case_id 外键"——该字段实为 `tickets.refund_case_id`,见 [[reference_lessons_ledger]] L-010)。`conversation_threads`/`conversation_summaries` 带 `case_id`(String(128),无 FK)。记忆的 scope 未和业务的 case 对齐。
5. **业务骨架是 case 中心的**:有 `refund_cases`、`tickets` 一等实体;"当前案件工作摘要"的字段其实已零散存在(`tickets.summary`、`tickets.messages`、`session_memories.session_summary/active_slots_json/unresolved_questions_json/last_business_context_refs_json`),但**没有一个 case-scoped 的聚合视图**。
6. **thread↔case 当前 schema 只支持一对多**:`conversation_threads.case_id` 是单个 nullable `String(128)`(无 FK),支持"一个 case 跨多个 thread",**支持不了"一个 thread 含多个 case"**,且无 join 表。**case 标识三种形态并存(已核实)**:`conversation_threads.case_id` 是 String(128) 无 FK;业务/工具层全程用业务单号 `refund_case_no`(string);`tickets.refund_case_id` 是 UUID FK→`refund_cases.id`。三者不统一——新层的 scope key 必须显式锁定绑 `refund_cases.id`(UUID)。

---

## 二、核心判断

**MOCA 真正的核心记忆是 case-scoped 的"当前案件工作上下文",不是商家画像/跨 case 模式。** 现有系统建了一套通用 agent 长期记忆框架,却缺了一线客服最刚需的那一层,所以没人给治理层喂数据。分层的"轴"选错了(按时效/按 thread),应改为按业务 scope(session / case / tenant)。

---

## 三、目标分层(三层,全部 Postgres)

```
   thread  ◇────◇  case         (业务上多对多/至少一对多)

  ① Session Context        scope = thread    快、易变、会过期
     "这一通对话聊到哪了"    现有 session_memories,基本不动

  ② Case Working Context   scope = case      跨 thread/客服存活、可自动更新、非权威、可人工改
     "这个 case 处理到哪了"  ★ 新增,MOCA 真正的核心记忆

  ③ Case Precedent         scope = tenant    已办结 case、人审后、跨 case 只读复用
     "类似 case 以前怎么处理" 现有 case_memories,只改定位/文档,不改表名
```

- ①②③ **平级**,靠 `case_id` 关联;不存在"case 属于 session 记忆"这种从属关系(多对多下谁装谁都错)。
- **②③ 性质不同,不能互为 fallback**:② 是"当前这个 case 自己的工作状态",③ 是"别的已办结 case 的经验"。当前 case 上下文缺失,不能拿别的 case 先例来顶。③ 只在"生成建议时想参考历史类似案例"时检索。

---

## 四、已定决策

### D1 — 长期记忆:砍成极窄的"租户显式偏好",不是核心
- 商家画像事实、跨 case 模式 → **不放记忆**(统计洞察给运营看,或本质是规则进 RAG/规则引擎)。
- 运营硬约束("超 200 元必须主管审批") → **不放记忆**(规则引擎/配置;记忆是软的可错的,规则是硬的必执行的,不能混)。
- **唯一保留**:商家/团队**显式**说"以后记住这个偏好"的软偏好(如"回复默认先展示 policy 依据再给话术")。只在用户明说时写,不自动沉淀。
- 现有 `long_term_memories` 表**保留但用途收窄**,不作为自动沉淀主路径。

### D2 — 存储:三层全 Postgres,不用 Redis
- ①② 需要**持久 + 审计 + 可人工修正 + 绑 run_id/来源**;Redis 是"可丢的缓存",与之性质冲突。② 尤其要跨 session/交接存活,更不能依赖可被驱逐的缓存。
- **规模测算**:1000 商家 × 10 客服 × 每人每分钟一次读 ≈ **167 QPS**,Postgres 单表索引查询可轻松扛几千~几万 QPS,余量巨大。速度不是瓶颈。
- **"Postgres 比 Redis 快"的澄清**:论裸延迟 Redis(内存)更快;但本场景是人机交互频率,Postgres 已快到客服无感,不值得为感知不到的提升引入新组件 + 缓存一致性/失效复杂度。用 Postgres 是"够快且更简单可靠",不是"更快"。
- **Redis 未来的正当位置**(均为后续增长阶段的优化,现在过早):全租户共享+极少变+被狂读的数据(政策解析结果/规则配置)、限流、分布式锁、在线状态。届时是"Postgres 权威源 + Redis 加速副本",不是替代。

### D3 — Case Precedent:MVP 先不依赖向量,走 metadata 检索
- 退款 case 高度结构化(`reason_code`、`issue_type`、policy 版本/family、金额),用结构化标签过滤 + 排序大概率已能圈出同类案例。
- 向量的价值在"自由文本、标签覆盖不到的语义相似",退款先例恰是标签覆盖较好的领域 → **MVP 不需要向量**,省掉 embedding 生成/向量存储/HNSW 一整套。
- 现有 `case_memories` 已建向量列 + HNSW 索引:新检索**先不依赖向量**;存量向量列先留着不用,未来按实际检索效果再定去留(拆列也是 schema 改动,不免费)。

### D4 — 自动写入分三条链路(呼应"可自动抽候选,但不自动发布为长期记忆")
- **② Case Working Context**:run 结束**可自动更新**(它只是当前 case 工作状态,非泛化知识)。约束:必须有 tenant_id + case_id + source_ref;claim 与 fact 分离;工具事实只存引用/摘要(带 observed_at)不取代业务系统;不写 policy 正文/敏感原文;**整体标为非权威、允许人工修正、保留版本历史**。
- **③ Case Precedent**:case **关闭后**从 ② + trace + outcome 自动生成**候选**,默认 `needs_review`,人审通过才成为可检索先例。不能一步自动进先例库。
- **租户偏好(收窄后的 long_term)**:默认**不**从普通 run 自动抽取;仅显式"记住这个偏好"/管理员保存/人审通过才写,且只存软偏好,不碰订单/退款/工单状态/规则/审批/动作授权。

### D5 — 命名不动(红线)
- **不重命名 `case_memories` / `long_term_memories`**:它们已有 migration 011/013、identity 哈希、replay 身份契约、eval manifest(`phase35_eval_manifest.py`)依赖。重命名是跨多文件破坏性 schema 改动 + 动 replay 契约。
- 语义澄清用**文档/注释锁定**:`case_memories = reviewed case precedent, NOT active case state`。新增层用新名 `case_working_contexts`,不占用旧名。

---

## 五、拍板结果(2026-07-02,用户已定)

- **P1 — thread↔case 多对多:确认支持(选 b)。** 加 thread↔case join 表,属 schema 改动,走评审。→ **纳入本次 phase。**
- **P2 — ② Case Working Context 落地形态:独立新表 `case_working_contexts`(选 a)。** → **纳入本次 phase。**
- **P3 — long_term 定性:留窄版。** 按 D1 收窄为"租户显式偏好",不砍死、不作自动沉淀主路径。→ **归入后续 phase(见第六节 deferred)。**

---

## 六、Phase 拆分(本次范围 vs 后续,不可遗漏)

**本次 phase(下一个 v2.1 整数 phase)只做两件事,内聚、可独立评审/回滚:**

- **B1 — thread↔case 多对多 join 表**(P1)。② 的 case scope 落地前提,先把干净的 thread↔case 关系建出来。
- **B2 — 新增 `case_working_contexts` 独立表 + ② Case Working Context 的写入/读取链路**(P2 + D4 的 ② 部分)。MOCA 核心记忆层。约束照 D4:tenant_id+case_id+source_ref 必填、claim/fact 分离、工具事实只存引用/摘要带 observed_at、不写 policy 正文/敏感原文、整体非权威、可人工修正、保留版本历史。

**后续 phase(必须留痕,不能忘 — 按你们"defer 须命名目标 phase"规则):**

- **DEFER-1 →(② 之后的下一个整数 phase):① Session Context 重新定位。** 现 session_memories 是 thread-scoped,② 落地后要厘清 ① 与 ② 的职责边界(① 只管单通对话临时上下文,不再承担跨 case 状态),避免二者内容重叠。本次 phase 不动 ①。
- **DEFER-2 →(③ 相关的下一个整数 phase):③ Case Precedent 改定位 + case 关闭自动生成候选。** 含 D5 的文档/注释锁语义(`case_memories = reviewed precedent, NOT active case state`)、D3 的 metadata-first 检索、D4 的"case 关闭 → 从 ② 生成候选进 needs_review"链路。本次 phase 不动 ③。
- **DEFER-3 →(long_term 收窄 phase):long_term 窄版落地。** 按 D1 收窄为"租户显式偏好",接"记住我的偏好"这类显式请求;非核心,优先级最低。本次 phase 不动 long_term。

Phase 44 delivered: CWC layer + thread↔case M:N; auto-update hook wiring deferred to Phase 45 memory lifecycle wiring.

> 三个 DEFER 项在进入本次 phase 的 PLAN.md 时,须在 plan 的 "out of scope / follow-up" 段落原样带上,确保 plan-checker 和 Codex 评审都能看到边界。

---

## 六、红线与流程约束

- 这是**记忆分层重设计 + 新增核心表 + 可能的 schema 改动**,属 phase-level 大改,**必须走 GSD plan-phase + Codex 交叉评审**,不可直接开写。
- 依 `ARCHITECTURE-DEBT.md` 的 rescope 规则:清理既有子系统债 → 作为 v2.1 下一个整数 phase 追加;若判定 ② 是**全新用户可见能力**(而非债务修复),则可能需开新 milestone —— 归类待 plan 阶段定。
- **禁止基于未验证假设设计**:本轮已两次踩到"拿空表推断需求"的陷阱(先误判"队列空转",后险些接受"长期记忆非真需求"的先验断言)。"长期记忆非核心"的结论建议以生产库(非本地空库)真实读写数据佐证,或明确标注为"基于产品判断、未经运营数据验证"。

---

## 八、下一步

1. ✅ P1/P2/P3 已拍板(见第五节)。
2. 走 GSD plan-phase 为**本次 phase(B1 join 表 + B2 case_working_contexts)**出 PLAN.md → 内置 gsd-plan-checker 先审 → Codex 独立交叉审核 → Claude 逐条拿仓库核对裁决 → 定稿。
3. 定稿后阶段 B 由 Codex 按 PLAN.md 实现(schema/多文件/结构性改动按判定线交 Codex)。
4. DEFER-1/2/3 在本次 phase 的 PLAN.md "out of scope" 段落原样带上,后续各自独立立 phase。
