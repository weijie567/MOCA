# Phase 44 Plan Review — 合并裁决留痕（gsd-plan-checker + Codex 交叉审）

**裁决人：** Claude（裁决者，逐条拿仓库真实代码核对，不盲信任一审核器）
**日期：** 2026-07-03
**输入：** gsd-plan-checker 报告（1 blocker / 5 warnings / 2 info）+ Codex 独立交叉审（5 blockers / 3 warnings / 3 info）
**范围：** 44-01 / 44-02 / 44-03 / 44-04 四个 PLAN（waves 1-4）
**下一步：** 本清单整体交 Codex 执行修订（跨全部 4 plan + 动 schema 字段/task 结构，命中判定线，绑定 Codex），执行后重跑 gsd-plan-checker 复核。

> 铁律执行说明：所有关键 findings 已用 `rg`/read 定位仓库原文核对，区分「已确认」与「未确认」。零误报——两个审核器互补（plan-checker 偏契约合规，Codex 偏实现炸弹 + 项目硬规则）。B5 是我此前研究未抓到的漏（AGENTS.md 验证命令硬规则），如实记录。

---

## 一、Blocker 级（11 项，执行前必修）

### 来自 gsd-plan-checker

**PC-B1 — CWC 写入未强制 provenance，违反锁定的 D-CWC-3 / D-CWC-4**
- 现象：D-CWC-4 逐字「Required on write: tenant id + case id + **source_ref present**」；D-CWC-3「every write records run_id / source_ref」。但 44-02 Task2 `source_ref: MemorySourceRefV1 | None`、`updated_by_run_id: uuid.UUID | None`，44-01 Task2 两列均 nullable/空默认，无任一 task 在写时强制存在。
- 证据：44-CONTEXT.md:55/59-60、44-02-PLAN.md:154-156、44-01-PLAN.md:170-171
- 修法：让 `source_ref` 在写候选（或 `write_working_context`）中必填，并要求每次写带 provenance run identity。落点（pydantic model vs repo 写路径）由执行者定，但必须显式强制，不得留 nullable 裸奔。
- 裁决：✅ 成立，与锁定决策直接矛盾。

### 来自 Codex

**CX-B1 — 022 downgrade 遇已有 `case_working_context` audit row 时无法回滚**
- 现象：44-01 downgrade 要把 `memory_write_events.memory_type` CHECK 从 5 值降回 4 值；但 schema test/后续运行会插入 `case_working_context` 事件，存量行存在时 `ADD CHECK` 校验失败。
- 证据：44-01-PLAN.md:187、44-01-PLAN.md:218、src/db/models.py:647
- 修法：downgrade 恢复 CHECK 前显式处理 `case_working_context` rows（删除/转换/阻断并给清晰错误），downgrade round-trip test 覆盖「已有 CWC audit row」场景。
- 裁决：✅ 成立，downgrade 数据安全缺口。

**CX-B2 — CWC content 字段名与 JSONB 列名不匹配（最直接的实现炸弹）**
- 现象：44-01 DDL 列为 `claims_json`/`verified_facts_json` 等；44-02 Pydantic content 字段为 `claims`/`verified_facts` 等，且要求直接 `.model_dump(mode="json")`。字面实现 dump 出的 key 存不进 ORM 列。
- 证据：44-01-PLAN.md:167、44-02-PLAN.md:151、44-02-PLAN.md:190
- 修法：44-02 明确 hydrate/dehydrate 映射表，或给 Pydantic 字段加 alias 到 `*_json` 列；测试断言每个 content 字段能写入并读回对应列。
- 裁决：✅ 成立。

**CX-B3 — CWC 首写并发 race 未处理，未复用仓库既有 advisory lock 惯例**
- 现象：44-02 只对已存在 active row `FOR UPDATE`；两个并发首写都读到 none 时同时 insert，最终靠 `uq_case_working_contexts_active_scope` 抛 IntegrityError，plan 无 retry/conflict/merge 路径。
- 证据：44-01-PLAN.md:174、44-02-PLAN.md:184、src/conversation/repository.py:517（`func.pg_advisory_xact_lock(lock_key)` 惯例已存在）
- 修法：首写前对 `(tenant_id, case_id)` 加 advisory lock，或捕获 unique violation 后 reload active row 返回 conflict/retry；新增并发首写测试。
- 裁决：✅ 成立。

**CX-B4 — 44-03 引用 `candidate.pii_classification`，44-02 candidate 无此字段（符号缺失炸弹）**
- 现象：44-03 从 candidate 取 `pii_classification`，但 44-02 `CaseWorkingContextWriteCandidate` 字段清单（tenant_id/case_id/updated_by_run_id/source_ref/expected_version/content）无此字段，字面实现 AttributeError。与 PC-W4（PII 门禁逻辑缺口）是两件事：此为符号缺失。
- 证据：44-02-PLAN.md:154、44-03-PLAN.md:177
- 修法：44-02 candidate 显式加 `pii_classification: Literal[...] = "none"`，44-03 service/test 使用同一字段。
- 裁决：✅ 成立。

**CX-B5 — 验证命令违反 AGENTS.md 硬规则（我此前研究的漏）**
- 现象：4 个 plan 多处用 `. .venv/bin/activate ...; python -m pytest` 或裸 `python -c`。AGENTS.md 明文：裸 `python -m pytest` 结果在 MOCA 视为无效验证（会命中本机旧 Python 3.9，`datetime.UTC` 等 3.12+ 代码在 collection 阶段假失败）。
- 证据：AGENTS.md:26-30、44-01-PLAN.md:126/160/194/225、44-02 同类、44-03 同类、44-04-PLAN.md:146
- 修法：统一改 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`；临时 Python 改 `uv run python -c ...` 或 `.venv/bin/python -c ...`。全 4 plan 的 `<automated>` 与 `<verification>` 命令全量替换。
- 裁决：✅ 成立。

---

## 二、Warning 级（7 项，实质，建议一并修）

### 来自 gsd-plan-checker

**PC-W1 — 审计 `memory_write_events.run_id` NOT NULL 与 run-less（staff）写冲突（与 PC-B1 耦合）**
- 证据：src/db/models.py:340（run_id nullable=False）、44-03-PLAN.md Task3、44-01 revisions `edit_source` 含 `staff_manual`
- 修法：明确 CWC 审计事件的 run_id 来源，以及 run-less/staff 编辑如何审计（可能需要专用审计路径或 sentinel run）。与 PC-B1 一并处理。

**PC-W2 — `commitments.confirmed_by_staff` 与 `actions_taken.source_ref` 未定型**
- 证据：44-CONTEXT.md:42-44（D-CWC-2 逐字锁定）、44-02-PLAN.md:151-153
- 修法：加 `CaseWorkingContextCommitmentV1(... confirmed_by_staff: bool)`，给 `actions_taken` 定型带 `source_ref`。commitment 是 D-CWC-4 高后果项，confirmed_by_staff 是人工纠正锚点。

**PC-W3 — B3 有 writer（`link_case`）但本 phase 无调用点，「在流程哪个点写」只答一半**
- 证据：44-03-PLAN.md Task2（建 link_case 且正确拒绝从 append_message 自动写），无 task 接入真实 run/staff flow；`read_active`/CWC service 同样无 in-phase consumer
- 修法：要么命名一个具体 linkage point 并接一处调用；要么像 CWC auto-update hook 那样，对 link_case/read_active 无 caller 显式 defer 留痕（命名目标 phase）。让 B3 的「who/when」上账而非隐含。

**PC-W4 — CWC 写无 PII 门禁，违反 D-CWC-3「never store sensitive raw PII text」**
- 证据：src/memory/policy.py:31（`BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS = {"sensitive","prohibited"}`）、44-03-PLAN.md Task3、44-01 `customer_request` 为裸 Text
- 修法：CWC 写应用 PII block，或按 spec↔phase 无静默偏离规则显式声明「CWC 依赖 caller 预分类、只存引用/摘要」（二选一写明）。

### 来自 Codex

**CX-W1 — CWC JSONB / `schema_version` 未显式 `nullable=False`**
- 证据：44-01-PLAN.md:164/167、src/db/migrations/versions/013_long_term_case_memory.py:113（同类列均显式 not null）
- 修法：CWC 所有默认空对象/数组 JSONB、`schema_version`、revision `source_ref_json` 的 nullable 明确写死；schema test 比对 ORM/migration nullable。

**CX-W2 — 44-03 hash 调用示例缺 `tenant_id`（必填）+ `source_identity_hash`**
- 证据：44-03-PLAN.md:178、src/memory/identity.py:156-164（真实签名 `canonical_memory_candidate_hash(*, tenant_id, memory_type, scope_type, scope_id, content_hash, source_identity_hash=None)`，tenant_id 必填）
- 修法：plan 写全调用：`tenant_id=str(candidate.tenant_id)`、`source_identity_hash=canonical_source_identity_hash(source_ref_json)`。缺 tenant_id 字面实现 TypeError。

**CX-W3 — DB fixture 无 DB 时不 skip，与 44-04「不能跑记 LOCAL issue」自相矛盾**
- 证据：tests/conftest.py:70（test_engine 直连 localhost）、44-04-PLAN.md:141
- 修法：plan 明确要求 compose Postgres，或给 Phase 44 DB tests 加环境探测 skip 分支；未跑 DB 验证记入 `.planning/LOCAL-VALIDATION-ISSUES.md`。

---

## 三、低优先 / 文档卫生（记录，不阻塞执行）

- **PC-W5** — 44-01 Task1-2 verify 仅 `ast.parse`（Task3 的 alembic upgrade + DB test 把关整个 wave，checker 自评 acceptable）。可加 metadata 级断言，nice-to-have。
- **PC-Info1** — `MemoryPolicyMemoryType` 加 `case_working_context` 目前无消费者（44-03 直接构造 MemoryWriteEvent 而非 MemoryPolicyDecision）。harmless additive；修 rationale 或保留均可。
- **PC-Info2** — RESEARCH §6 open items 已被 plan 决定但未标 RESOLVED。可回填 RESEARCH.md。
- **CX-I1** — 单 alembic head 核对：Codex 自证不成立，020 现 head、021→020/022→021 方向正确，无需改。
- **CX-I2** — `RefundRepository.get_by_case_no` 复用点核对成立，无需改。
- **CX-I3** — soft-delete resurrection 未确认；主并发风险是首写 race（已入 CX-B3），无需单列。

---

## 四、执行与复核约束（交 Codex 前锁定）

1. **整体交 Codex 执行**：修订跨全部 4 个 plan + 动 schema 字段与 task 结构，命中大改判定线（跨 ≥3 文件 / 结构性 / 需回核源码）。判定线一旦判 Codex 即绑定，Claude 不自行改判。
2. **红线不动**：D-REDLINE 不重命名 `case_memories`/`long_term_memories`；D-STORAGE 仅 Postgres；conversation_threads.case_id 保持 additive 不迁移 26 处 readers。
3. **DEFER 留痕不丢**：DEFER-1/2/3（① session 重定位、③ precedent 抽取、long_term 窄版）仍须在 plan out-of-scope 段落原样保留。
4. **验证入口**：修订后所有验证命令必须是 `uv run pytest` / `.venv/bin/pytest` 形态（CX-B5）。
5. **复核门**：Codex 执行完，重跑 gsd-plan-checker；Claude 逐条核对修订是否落地、有无引入新偏离，确认后本 phase plan 方可定稿进 execute-phase。

---

*留痕人 Claude；本文件为 Codex 执行修订与后续复核的必备输入（阶段 B 轻量收尾复核的差异记录基线）。*
