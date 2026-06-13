# Contract-spec 回归复审 — 修订执行清单(待 Claude 裁决定稿 → 交 Codex)

> 来源:Codex 回归复审第二意见 + Claude 拿仓库逐条核对后的裁决。
> 目标文件:`docs/contract-spec.md`(单文件,但跨 §9.3/§9.4/§11.3/§11.7/§12.5/§12.6/§17 多张相互依赖的表 + field registry)。
> 分流:命中大改线(编辑处 >5、结构性一致性、需回读源码),**整体交 Codex 执行**。
> 边界:只改文档,不动 src/;保持现有 schema/契约风格;不顺手重构无关段落。

---

## 优先级分层(Claude 裁决)

- **真阻塞,必须修**:B5、B4、B1
- **应修,非硬阻塞**:B3、B2
- **本轮一并修**:B6(用户决定:不留 backlog,这轮一起改)

---

## B5 — intent consistency manifest 必然 CI fail(最高优先)

**根因**:§11.7 规则 #2/#3(`:856-857`)要求每个 taxonomy intent 都在 §11.3 required-slot 表**和** §9.3 evidence sufficiency 表有行;taxonomy 含 `small_talk`/`unsupported`(`:708-709`)。但两表(`:747-754` / `:357-364`)都只有 8 个领域 intent。manifest 示例(`:876-877`)却给这两个标 `true`,且 `:860` 明文要求 CI 从 source of truth 验证、不信任 manifest 自声明的 `true`。→ CI 一实现就必 fail。

**关键事实**:`small_talk`/`unsupported` **已在** §9.2 intent-level routing 表(`:320-321`),只缺 evidence-sufficiency 子表的行。二者也根本不经过 `investigate`/`route_after_investigate`,放进 evidence 表语义上是错的。

**改法(外科式,保持 boolean、保持 CI 可验证)**:
1. **§11.3 表**(在 `:754` 后追加两行):
   - `small_talk` | `{"all_of":[],"any_of":[],"optional":[]}` | (none) | n/a
   - `unsupported` | `{"all_of":[],"any_of":[],"optional":[]}` | (none) | n/a
   - 理由:这两个 intent 的 required-slot expression 合法地为空(trivially complete),补行即满足规则 #2,不引入坏语义。
2. **§11.7 规则 #3**(`:857`)拆成两句:
   - intent-level **routing 表**的行:**所有** taxonomy intent 必须有(`small_talk`/`unsupported` 已满足)。
   - **evidence sufficiency decision 表**的行:仅 **经 `investigate` 路由**的 intent 必须有;`small_talk`/`unsupported` 这类直达 `final_response`、不进入 `route_after_investigate` 的 intent **豁免**,其 `in_evidence_table` 必须为 `false`,并由 routing 表行兜底覆盖。
3. **§11.7 示例骨架**(`:876-877`):把 `small_talk`/`unsupported` 的 `"in_evidence_table":true` 改为 `false`(其余标记保持 true)。
4. **§11.7 校验说明**(`:860` 附近)补一句:CI 校验 `in_evidence_table` 时,对豁免 intent 断言「不在 evidence 表 且 在 routing 表」,对非豁免 intent 断言「在 evidence 表」。

---

## B4 — base event table 与完整表两处冲突(必须修)

**冲突 1:schema_version 域**。minimal envelope 固定 `minimal_event_envelope.v1`(`:1705`),但 `agent_trace_events` DDL 默认 `replay_event.v3` 且 check `schema_version in ('replay_event.v3')`(`:2421`、`:2452`);过渡策略(`:2459`)又说 Phase 10 base table 是该表「初始列子集」。按此实例化,Phase 10 写的 `minimal_event_envelope.v1` 行会被 check 拒。

**改法**:
- 改 `:2452` check 为允许两值并注明演进:
  `check schema_version in ('minimal_event_envelope.v1','replay_event.v3')`(注释:Phase 10-14 base table 写前者,Phase 15 migration enrich 后并存/收敛)。
- 在过渡策略 `:2459` 补一句:Phase 10 base table 的 `schema_version` 列默认 `minimal_event_envelope.v1`;Phase 15 扩展列后新事件写 `replay_event.v3`,check 同时容纳两值,旧行不回写。

**冲突 2:主键命名漂移**。DDL 列名 `id`(`:2412`),但 envelope 字段(`:1706`)、字段规则(`:1796`)、过渡列子集清单(`:2459`)都叫 `event_id`。

**改法(用户决定:直接 rename `id`→`event_id`,命名统一)**:
- DDL `:2412`:`id uuid primary key` → `event_id uuid primary key`。
- FK 引用 `:2217`:`replay_event_id uuid null references agent_trace_events(id)` → `... references agent_trace_events(event_id)`。
- 散文 `:2237`:`nullable FK to agent_trace_events(id)` → `... agent_trace_events(event_id)`。
- 过渡列子集清单 `:2459`:本就写 `event_id`,rename 后自动对齐,无需再改。
- **波及面已核实**:`rg 'agent_trace_events|replay_event_id' src/` 零命中,纯文档改动,不波及代码;contract-spec 内引用仅上述三处 + 已对齐的 `:2459`。
- 自检:rename 后全文不得再有 `agent_trace_events(id)` 或把该表主键称 `id` 的残留。

---

## B1 — permission dependency mapping 无 state 字段(必须修)

**根因**:`:366` 把它定义为 investigate↔route_after_investigate 的「required state contract」,要求为每个 business fact / policy claim 标注依赖的 typed resource ref;`:337`/`:411` 承诺 permission denied 时「只阻断依赖被拒资源的回答、保留其他事实」。但 investigate State writes(`:382`)、field registry(`:619-627`)、route_after_investigate reads(`:411`)**都没有承载 claim→ref 映射的字段**。

**已存在**:typed refs 本身有(`business_fact_refs`/`BusinessFactRefV1` `:997`、`evidence_refs`)。**缺的是**「答案片段/claim → 依赖哪些 ref」的映射结构。

**改法**:
1. 新增 state 字段,建议名 `claim_dependency_map`(或沿用文风的命名),类型 `list[dict[str, Any]]`,元素形如 `{"claim_id": str, "depends_on_refs": [typed resource ref]}`。
2. **§9.4 investigate State writes**(`:382`):在 writes 列表末尾加该字段。
3. **field registry**(`:619-627` 区域,紧挨 `best_score` 行):加一行 —— writer=`investigate`,reader=`route_after_investigate` / `final_response`,lifecycle=reset each turn; replace,persistence=AgentStep / replay。
4. **§9.3 permission paragraph**(`:366`)和 **route_after_investigate reads**(`:411`):改为显式引用该字段名,说明屏蔽决策依据此字段;并重申「字段缺失/无效/无法验证 → 按依赖被拒资源处理」(保留现有 fail-closed 语义)。

---

## B3 — evidence 表 (intent×operation) totality 缺口(应修,比 Codex 框的窄)

**核对结论**:Codex 举的 `execute_action` 在 `appeal_or_unban`(`:362`)和 `action_request`(`:364`)**已覆盖**。真实缺口只有:
- **`compensation_suggestion`**:precedence(`:729`)允许 `advise/draft_action/execute_action`,但 evidence 表(`:360`)只列 `advise / draft_action` —— **缺 execute_action**。

**改法**:§9.3 表 `:360` 的 Requested operation 单元格补 `execute_action`,evidence strength / best_score 沿用该行 `strong_evidence` / `0.7`(与 draft_action 同档)。
(其余 intent×operation 已核对一致:`order_status_inquiry` `:358`、`complaint_escalation` `:363`、`ticket_reply_draft` `:361` 均与 precedence 对齐,不动。)

---

## B2 — retry 上限无来源(应修)

**根因**:§9.4:396 写「复用 §12.5 `ToolCallContext.attempt` 的每工具 retry **上限**」,但 `attempt: int = 1`(`:950`)是当前尝试**计数器**(`:1015` 确认递增计数),非上限;ToolDescriptor(`:1027-1037`)也无 `max_attempts`。→「三重资源上限」第三重缺可比较的上限值。

**改法**:
1. **ToolCallContext**(`:950` 后)加字段:`max_attempts: int = 1`(每工具最大尝试次数,调用方注入)。
2. **§12.5 contract rules**(`:1015`):改为「`attempt` 递增直到 `max_attempts`;`attempt > max_attempts` 不得再调用」。
3. **§9.4:396**:把「复用 `attempt` 的每工具 retry 上限」改为「以 `ToolCallContext.max_attempts` 为每工具 retry 上限,`attempt` 达到即终止该工具重试」。

---

## B6 — ToolRegistry 仅名称,8 工具 descriptor 实例缺失(本轮一并修)

**核对结论**:descriptor **类型**(`:1027`)与**派生规则**(`:1024`)已 normative;可从现有文本派生的字段不少(event_family `:928`、kind 由 §12.1/§12.2 区分、resource_type 枚举 `:997`、permission token 范式 `:1034`)。真正没枚举的是 8 个工具各自的 `input_schema`/`output_schema` 实例。

**改法(用户决定:本轮一起改,不留 backlog)**:在 §12.6(`:1049` 后)加一张 descriptor 概要表,列出 `investigate` allowlist 的 8 个工具(`get_order`/`get_refund_case`/`get_ticket`/`get_logistics`/`get_merchant_risk`/`search_policy`/`search_sop`/`search_case_memory`)× {kind, side_effect, required_permission, event_family, resource_type}:
- kind:`get_*` 为 `read`,`search_*` 为 `retrieval`(对齐 §12.1/§12.2 分类)。
- event_family:`get_*` 为 `tool_call_*`,`search_*` 为 `rag_retrieval_*`(对齐 `:928`)。
- resource_type:`get_order`=order、`get_refund_case`=refund_case、`get_ticket`=ticket、`get_logistics`=logistics、`get_merchant_risk`=merchant_risk(对齐 `:997` 枚举);`search_*` 三个为 `null`(不产 business fact ref)。
- side_effect:全部 `read_only` 或 `retrieval`(非写)。
- required_permission:按 `:1034` 范式 `tool:<name>`。
- `input_schema`/`output_schema`:表中标注「Phase 9 实现时按 registry 落地」,不在 contract 穷举具体 JSON schema。
- caller_allowlist:全部为单一 `investigate`(对齐 `:1046`,不得用旧节点名)。

---

## 交付要求(给 Codex)

- 只编辑 `docs/contract-spec.md`,逐条按上面 anchors 改,**不重排无关表、不动其他章节措辞**。
- 改完做一次自检:§11.7 规则与示例骨架、§11.3/§9.3 行集、field registry 与 §9.4 writes、DDL check 与 envelope schema_version —— 四处交叉引用必须自洽。
- 输出:改动 diff 摘要 + 逐条对应本清单编号的落点行号,供 Claude 复核。
- 不提交 commit(等 Claude 复核)。
