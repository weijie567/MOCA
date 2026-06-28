# 本地验证问题记录

## 13. Phase 28 execute-phase 复现 `state.begin-phase` flag 解析写坏 STATE

日期：2026-06-23

### 问题现象

执行 Phase 28 execute-phase 初始化时，按 workflow 示例运行：

```bash
gsd-sdk query state.begin-phase --phase "28" --name "decision-event-foundation" --plans "1"
```

命令返回 JSON 把 `--phase` 当成 phase、把 `28` 当成 name、把 `--name` 当成 plan_count，并把 `.planning/STATE.md` 写成 `Phase --phase`、`Plan: 1 of --name`、`Current focus: Phase --phase - 28`。

### 如何检测 / 复现

运行上述命令后执行：

```bash
git diff -- .planning/STATE.md
```

### 关键证据或命令

命令输出：

```json
{"phase":"--phase","name":"28","plan_count":"--name"}
```

STATE diff 同时把 frontmatter 从 `ready_to_execute` / `total_plans: 10` / `percent: 30` 回退到 `executing` / `total_plans: 5` / `percent: 80`。

### 当前判断 / 根因

这是既有 `state.begin-phase` 参数解析与统计覆盖问题在 Phase 28 上的再次复现，和此前 Phase 24/26/27 记录同类。workflow documented flag syntax 与当前 SDK handler 不兼容。

### 已做处理

用补丁恢复 `.planning/STATE.md` 到 Phase 28 planned 的正确状态，并确认后续执行不再信任 `state.begin-phase` 自动写入结果。

### 剩余问题

后续 execute-phase 仍可能按 workflow 自动调用该 writer 并写坏 STATE。需要运行后立即检查 diff，或修复 SDK handler / workflow 文档。

### 下次继续排查入口

查看 `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs::cmdStateBeginPhase` 和 `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs` 中 `parseNamedArgs` 的调用方式。

## 12. `state.planned-phase` 重跑会回退 STATE frontmatter 统计

日期：2026-06-23

### 问题现象

Phase 28 plan 已经由 planner 提交为 `ready_to_execute` 后，按 workflow 再运行：

```bash
gsd-sdk query state.planned-phase --phase "28" --name "Decision Event Foundation" --plans "1"
```

命令返回 `updated: true`，但 `.planning/STATE.md` frontmatter 被回退为不一致状态：`status: executing`、`stopped_at: Phase 28 context gathered`、`completed_phases: 2`、`total_plans: 5`、`percent: 80`。

### 如何检测 / 复现

在 Phase 28 已 planned 的状态下重跑上述命令，然后执行：

```bash
git diff -- .planning/STATE.md
```

### 关键证据或命令

`git diff -- .planning/STATE.md` 显示 frontmatter 从已提交的 `ready_to_execute` / `total_plans: 10` / `percent: 30` 回退到旧统计；正文 Current Position 仍显示 Phase 28 ready to execute，说明 frontmatter 与正文不一致。

### 当前判断 / 根因

`state.planned-phase` handler 对当前 MOCA STATE 格式的 frontmatter / progress 统计同步不可靠；重复运行时会把旧 session/frontmatter 值写回。Phase 28 planning completion 其实已经在 `c92adbd docs(28): create phase plan` 中写入并提交。

### 已做处理

用补丁恢复 `.planning/STATE.md` 到命令前已提交的正确 planned 状态，并确认 `git diff -- .planning/STATE.md` 无输出。本次不提交工具生成的错误 STATE diff。

### 剩余问题

后续 plan-phase 如果重复运行 `state.planned-phase`，仍可能造成 STATE frontmatter 回退。需要在运行后强制检查 diff，或修复 GSD state handler。

### 下次继续排查入口

查看 `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs::cmdStatePlannedPhase` 及其读取/替换 frontmatter 的逻辑，重点核对它如何从旧 state block 推导 status、progress、last_updated。

## 11. macOS `find` 不支持 GNU `-printf`

日期：2026-06-23

### 问题现象

执行 Phase 28 plan-phase 预检时，为列出 phase 目录文件尝试运行：

```bash
find .planning/phases/28-decision-event-foundation -maxdepth 1 -type f -printf '%f\n' | sort
```

在当前 macOS/BSD find 环境下失败：

```text
find: -printf: unknown primary or operator
```

### 如何检测 / 复现

在 macOS 默认 `/usr/bin/find` 下运行上述命令即可复现。

### 关键证据或命令

失败来自 `find -printf`，这是 GNU find 扩展，BSD find 不支持。

### 当前判断 / 根因

这是平台命令差异，不是 phase 文件状态问题。

### 已做处理

改用 portable 写法：

```bash
find .planning/phases/28-decision-event-foundation -maxdepth 1 -type f -exec basename {} \; | sort
```

### 剩余问题

后续 workflow 或手工命令如果复用 GNU-only `find -printf`，在 macOS 上仍会失败。

### 下次继续排查入口

遇到 `find: -printf: unknown primary or operator` 时，把 `-printf` 改成 `-exec basename {} \;`、`sed`、`awk`，或明确使用 GNU find。

## 10. plan-phase UI gate 用大小写不敏感 `UI` 正则误匹配 `required`

日期：2026-06-23

### 问题现象

执行 Phase 28 plan-phase 预检时，Phase 28 是 replay / observability foundation，不涉及前端或 UI 交付；但 UI gate 的粗略正则命中，若严格照 workflow 将要求运行 `$gsd-ui-phase 28`。

### 如何检测 / 复现

运行：

```bash
PHASE_SECTION=$(gsd-sdk query roadmap.get-phase 28 2>/dev/null)
printf '%s' "$PHASE_SECTION" | grep -iE "UI|interface|frontend|component|layout|page|screen|view|form|dashboard|widget"
```

### 关键证据或命令

命中内容来自 Phase 28 success criteria 中的英文单词 `required`，因为 `grep -iE "UI"` 会把 `required` 里的 `ui` 当作 UI 命中。

### 当前判断 / 根因

这是 workflow UI gate 的 false positive。大小写不敏感的裸 `UI` pattern 没有词边界，会匹配普通英文单词里的 `ui` 子串。

### 已做处理

本次将 Phase 28 判定为非 UI phase，未中断 plan-phase，也未要求生成 UI-SPEC。

### 剩余问题

workflow 示例正则仍可能在其它非 UI phase 中误命中包含 `ui` 的英文单词。

### 下次继续排查入口

修复 UI gate 时应把 `UI` 改成带词边界的 pattern，例如 `\bUI\b`，或优先检测明确 frontend path / design terms。

## 9. GSD state.record-session 参数解析写坏 STATE 元数据

日期：2026-06-23

### 问题现象

执行 Phase 28 discuss workflow 的 state 更新时，按 workflow 示例运行：

```bash
gsd-sdk query state.record-session --stopped-at "Phase 28 context gathered" --resume-file ".planning/phases/28-decision-event-foundation/28-CONTEXT.md"
```

`.planning/STATE.md` 被写坏：`Last session` / `Resume file` 等字段出现 `--stopped-at`、`--resume-file` 这类 flag 名；frontmatter 的 `status`、`progress.completed_phases`、`progress.total_plans`、`progress.percent` 也被错误改写。

### 如何检测 / 复现

运行上述命令后查看：

```bash
git diff -- .planning/STATE.md
sed -n '1,45p' .planning/STATE.md
sed -n '136,148p' .planning/STATE.md
```

### 关键证据或命令

- flag 形式运行后，STATE diff 中出现 `Last session: --stopped-at`、`Resume file: --resume-file`。
- positional 形式 `gsd-sdk query state.record-session "Phase 28 context gathered" ".planning/phases/28-decision-event-foundation/28-CONTEXT.md"` 仍未按预期写入：`Last session` 被写成 `Phase 28 context gathered`，`Stopped at` 被写成 context 路径，`Resume file` 仍为 `None`。
- 同时 progress 被错误回退为 `completed_phases: 2`、`total_plans: 4`、`percent: 100`，与 STATE 正文中的 v1.9 进度表不一致。

### 当前判断 / 根因

`gsd-sdk query state.record-session` 与 workflow documented flag syntax 不兼容，且 positional 参数含义也与预期不一致；该 query 还会顺带重算或覆盖 progress/frontmatter，导致与当前 milestone 状态漂移。

### 已做处理

- 手动将 `.planning/STATE.md` frontmatter 恢复为 Phase 28 context gathered 后的合理状态：`status: ready_to_plan`、`stopped_at: Phase 28 context gathered`、v1.9 progress 恢复为 10 phases / 10 plans / 4 completed plans / 30%。
- 手动将 Session Continuity 更新为：`Stopped at: Phase 28 context gathered`，`Resume file: .planning/phases/28-decision-event-foundation/28-CONTEXT.md`。

### 剩余问题

GSD SDK 的 `state.record-session` 参数解析和 progress 覆盖问题仍存在；后续直接按 workflow 示例执行可能再次写坏 STATE。

### 下次继续排查入口

检查 `gsd-sdk query state.record-session` query handler 的参数解析与 STATE frontmatter update 逻辑，确认它是否应支持 `--stopped-at` / `--resume-file` flags，或 workflow 文档是否应改成当前实际 positional syntax。

## 8. zsh 下直接 `ls path/*-SPEC.md` 会在无匹配时提前失败

日期：2026-06-23

### 问题现象

执行 Phase 28 discuss workflow 的已有 context / SPEC 检查时，目标 phase 目录尚未创建。命令中直接使用未加保护的 zsh glob，导致 shell 在命令运行前报错：

```text
zsh:1: no matches found: .planning/phases/28-decision-event-foundation/*-SPEC.md
zsh:1: no matches found: .planning/phases/28-decision-event-foundation/*-CONTEXT.md
```

### 如何检测 / 复现

在 zsh 中、且 `.planning/phases/28-decision-event-foundation/` 不存在或没有匹配文件时执行：

```bash
ls .planning/phases/28-decision-event-foundation/*-SPEC.md 2>/dev/null | grep -v AI-SPEC | head -1 || true
ls .planning/phases/28-decision-event-foundation/*-CONTEXT.md .planning/phases/28-decision-event-foundation/*-DISCUSS-CHECKPOINT.json 2>/dev/null || true
```

### 关键证据或命令

上述命令在 zsh 的默认 `nomatch` 行为下会在 `ls` 执行前失败；`2>/dev/null` 不能屏蔽 shell glob expansion 阶段的错误。

### 当前判断 / 根因

这是 shell 行为差异，不是 phase 状态错误。workflow 示例里的 `ls path/*` 写法在 bash 常见环境中通常只表现为 no file 输出，但 zsh 默认会对无匹配 glob 抛 `no matches found`。

### 已做处理

本次继续排查时改用 `find` / 已知 phase metadata 判断，不把该 zsh 报错当成已有 SPEC/CONTEXT 的证据。

### 剩余问题

GSD workflow 文档里的 glob 示例仍可能在 zsh 用户环境复现。后续本地执行类似检查时应优先使用 `find`，或显式使用 `noglob` / `setopt NULL_GLOB` 后再运行。

### 下次继续排查入口

如后续 discuss/plan workflow 在“无匹配文件”场景中异常退出，先检查命令是否包含未保护的 `*.md` / `*.json` glob，再替换为 `find <dir> -name ...`。

## 7. 直接运行 pytest 命中了系统 Python 3.9

日期：2026-06-21

### 问题现象

本次 memory 修复后执行目标测试时，直接运行 `pytest ...` 在加载 `tests/conftest.py` 阶段失败：

```text
ImportError: cannot import name 'UTC' from 'datetime'
```

### 如何检测 / 复现

在当前 shell 中直接执行：

```bash
pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/agent/test_graph.py tests/test_memory_review_api.py
```

### 关键证据或命令

- `which pytest` → `/Users/ming/Library/Python/3.9/bin/pytest`
- `pytest --version` → `pytest 8.4.2`
- `pyproject.toml` 声明 `requires-python = ">=3.12"`
- `.python-version` 为 `3.12`
- `uv run pytest --version` → `pytest 9.0.3`

### 当前判断 / 根因

本地 PATH 中优先命中了用户目录下 Python 3.9 安装的 `pytest`。仓库代码使用 `datetime.UTC`，该符号需要 Python 3.11+，且项目声明 Python 3.12+，所以失败是测试启动解释器错误，不是本次 memory 代码逻辑失败。

### 已做处理

改用项目推荐环境执行：

```bash
uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/agent/test_graph.py tests/test_memory_review_api.py
```

验证结果为 `53 passed, 20 warnings`。

### 剩余问题

当前 shell 中直接运行 `pytest` 仍可能复现该问题。后续本仓库测试应优先使用 `uv run pytest`，或调整 PATH 让项目 Python/venv 的 pytest 优先。

### 下次继续排查入口

若后续仍出现 `datetime.UTC` 相关 ImportError，先检查 `which pytest`、`python --version`、`uv run pytest --version` 是否一致。

## 6. GSD state.begin-phase 参数示例与实际 CLI 行为不一致

日期：2026-06-20

### 问题现象

执行 Phase 24 初始化时，按 `execute-phase.md` 示例运行 `gsd-sdk query state.begin-phase --phase 24 --name agent-runs-short-term-memory-parity --plans 9` 后，`.planning/STATE.md` 被写成 `Phase --phase`、`Plan: 1 of --name`。改用 positional 参数后，phase 字段恢复，但 `milestone` / `milestone_name` 又被写回默认 `v1.0` / `milestone`。

### 如何检测 / 复现

运行初始化命令后读取 `.planning/STATE.md` 前 40 行即可复现字段错位或 milestone 元数据回退。

### 关键证据或命令

- `gsd-sdk query state.begin-phase --phase 24 --name agent-runs-short-term-memory-parity --plans 9`
- `gsd-sdk query state.begin-phase 24 agent-runs-short-term-memory-parity 9`
- `sed -n '1,120p' .planning/STATE.md`

### 当前判断 / 根因

`execute-phase.md` 中 documented flag syntax 与当前 `gsd-sdk query state.begin-phase` 实际 positional 参数解析不一致；同时该 query 在写状态时没有保留当前 milestone 元数据，导致默认值覆盖 v1.7 信息。

### 已做处理

- 已重新运行 positional 形式恢复 Phase 24 执行态。
- 已手动恢复 `.planning/STATE.md` frontmatter 的 `milestone: v1.7` 与 `milestone_name: Short-term Memory Unification`。

### 剩余问题

GSD SDK / workflow 文档仍存在不一致，后续再次调用 `state.begin-phase` 时可能复现，需要避免使用 documented flag syntax，并在调用后检查 milestone 元数据。

### 下次继续排查入口

优先检查 `gsd-sdk query state.begin-phase` 的参数解析实现，以及 `execute-phase.md` 中 begin-phase 示例是否需要改为 positional 形式或修复 CLI 支持 flags。

## 1. RAG 证据已恢复，但 agent 最终回答仍过度保守

日期：2026-06-20

### 问题现象

本地 UI/RAG 验证时，查询 `平台的退款超时处理规则是什么？` 最初返回：

```text
No relevant policy found
```

用户侧回答表示当前知识库没有足够证据。

### 如何检测 / 复现

1. 通过 `/api/v1/search/` 复现无证据返回。
2. 查询 PostgreSQL 后确认：
   - `policy_documents=15`
   - `policy_chunks=30`
   - 所有 chunk 的 `policy_chunks.embedding` 为空
   - `policy_chunks.search_text` 字段存在，但内容实际为空字符串
3. 执行 `scripts/rebuild_policy_search_text.py` 后，补偿类政策检索恢复，但退款超时问题仍无证据。
4. 使用 `rg` 定位到完整的退款时效政策来源：
   - `data/policies/refund_time_limits.md`
   - `scripts/ingest_policies.py` manifest
5. 执行 `scripts/ingest_policies.py` 时失败，外层只返回通用安全错误 `Policy source could not be parsed`。
6. 直接用 `ParserRegistry` 测试 Markdown 文件，解析成功，说明不是政策文件格式问题。
7. 直接测试 `EmbeddingService`，发现失败原因是本地 `ALL_PROXY`/`HTTP_PROXY`/`HTTPS_PROXY` 指向代理，但当前 `httpx` 环境缺少 SOCKS 支持依赖 `socksio`。
8. 临时清空代理环境变量后重新执行 ingest，embedding 成功，政策入库完成。

### 关键证据或命令

- `uv run python scripts/rebuild_policy_search_text.py`
- `ALL_PROXY= HTTPS_PROXY= HTTP_PROXY= all_proxy= https_proxy= http_proxy= uv run python scripts/ingest_policies.py`
- `/api/v1/search/` 对 `平台的退款超时处理规则是什么？` 已返回 `strong_evidence`

### 当前判断 / 根因

最初的无证据问题不是前端或 agent 主流程问题，而是本地政策检索数据不完整：旧数据库中 chunk 缺少 embedding，退款时效政策也没有完成有效 ingest。后续 ingest 失败的直接原因是本地代理环境与 `httpx` SOCKS 依赖不匹配。

### 已做处理

- 已重建 `policy_chunks.search_text`。
- 已在清空代理环境变量的条件下重新 ingest 政策文件。
- 搜索接口现在能为 `平台的退款超时处理规则是什么？` 返回 `strong_evidence`。
- 返回证据包含 `refund_time_limits`、`refund_policy` 以及相关政策 / SOP 文档。
- 已在 `src/agent/nodes/final_response.py` 增加只读 `policy_qa` 的窄分支：当检索为 `strong_evidence`、引用校验通过、无动作/审批/草稿状态，并且 verifier 只因 `level2_partial_overlap_ambiguous` 进入 `manual_review` 时，最终回答渲染为带引用的政策说明，而不是动作类人工复核模板。
- 已新增回归测试覆盖该分支，并确认带 `action_draft` 等动作边界状态时仍失败关闭。

### 剩余问题

- 当前已验证 `/api/v1/agent/chat` 对 `平台的退款超时处理规则是什么？` 返回带引用的政策回答，不再返回过度保守模板。
- 该修复只覆盖只读政策问答中的词面部分重叠误拦截；冲突证据、过期证据、低 OCR、越权证据、业务事实缺失、动作草稿/审批场景仍应保持原失败关闭行为。

### 下次继续排查入口

如同类问题复现，优先检查 `src/agent/nodes/final_response.py` 的 `_can_render_policy_qa_partial_overlap()` 条件、`src/agent/nodes/generate_recommendation.py` 生成的 `citation_validation` 和 `rag_verification.reason_codes`。

### 验证结果

- `uv run pytest tests/agent/test_phase22_final_response.py tests/agent/test_nodes/test_final_response.py -q`：25 passed，1 warning。
- `uv run pytest tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/rag_context/test_routing.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_graph.py -q`：91 passed，1 warning。
- 新镜像下真实接口验证：`/api/v1/agent/chat`，query=`平台的退款超时处理规则是什么？`，run_id=`dea7ea12-5fa1-4eaf-9d4c-265ca26b9033`，intent=`policy_qa`，tool=`search_policy`，`evidence_count=5`，`final_status=completed`。

## 2. Docker 构建期间 PyPI 单个 wheel 下载超时

日期：2026-06-20

### 问题现象

本地执行 `docker compose up -d --build api frontend` 或 `docker compose build api` 时，Debian apt 层已通过缓存，但 Python 依赖安装阶段可能因为 PyPI 单个 wheel 下载超时而失败。

### 如何检测 / 复现

1. 执行 `docker compose up -d --build api frontend`。
2. API 镜像构建进入 `uv pip install --system -e .` 后，下载 `openai==2.43.0` wheel 超时，构建失败。
3. 修改 Dockerfile 增加外层重试后，再执行 `docker compose build api`，第一次 `uv` 尝试下载 `langgraph-checkpoint==4.1.1` 超时，但第二次自动重试成功。

### 关键证据或命令

- 失败片段：`Failed to download openai==2.43.0`，`operation timed out`。
- 第二次构建中第一次尝试失败片段：`Failed to download langgraph-checkpoint==4.1.1`，随后外层重试继续安装。
- 成功命令：`docker compose build api`。

### 当前判断 / 根因

这是本地网络 / PyPI 下载波动问题，不是代码依赖声明错误。`uv` 自身已有单次请求重试，但单个依赖持续超时时，原 Dockerfile 会直接让整个镜像构建失败。

### 已做处理

- `Dockerfile` 中保留 apt 的 retry / timeout 参数。
- `Dockerfile` 中将 `uv pip install --system -e .` 包到最多 3 次的外层 shell 重试循环中。
- 已验证外层重试生效：第一次 `uv` 尝试失败后，第二次成功完成依赖安装和镜像构建。

### 剩余问题

- 如果 PyPI 或本地网络长时间不可用，3 次外层重试仍可能失败；届时应检查网络、代理或考虑配置稳定的 Python package mirror。

### 下次继续排查入口

优先查看 Docker build 日志中失败的具体 wheel 名称和 URL；如果持续集中在 PyPI 下载超时，检查本地代理、DNS、网络出口或为构建配置可用的 package index。

## 3. 订单进度 fact-only 路径最终回答落入默认政策建议模板

日期：2026-06-20

### 问题现象

本地 UI 中查询 `订单ORD-2024-001的退款进度如何？` 后，Agent 回复：

```text
建议：建议按已检索到的政策依据处理。
理由：已根据当前知识库证据生成建议。
```

该回复没有回答订单/退款进度，也没有展示已查询到的订单事实。

### 如何检测 / 复现

1. 从 UI 截图看到当前 run 的 timeline 走到 `order_status_inquiry` 相关路径，并执行了 `session_memory_load`、`extract_slots`、`investigate`。
2. 查询数据库 `agent_runs`，确认 run `5591965f-f82c-4c07-adf1-2a7a7bc3602d` 的 `final_response` 已持久化为上述默认模板，不是前端临时显示问题。
3. 查询 `agent_steps`，确认该 run 只走到 `investigate -> final_response`，没有 `generate_recommendation`。
4. 读取 LangGraph checkpoint，确认 state 中 `business_context.facts.order` 实际已有订单事实：
   - `order_no=ORD-2024-001`
   - `status=pending`
   - `amount=599.00 CNY`
   - `item_name=蓝牙降噪耳机 Pro`
   - `relation_hints.has_active_refund=true`
   - `relation_hints.has_open_ticket=true`

### 关键证据或命令

- `docker compose exec -T postgres psql -U moca -d moca -c "select id, input_query, final_status, left(coalesce(final_response,''), 220) as final_response from agent_runs order by started_at desc limit 8;"`
- `docker compose exec -T postgres psql -U moca -d moca -c "select run_id, step_index, node_name, status from agent_steps where run_id='5591965f-f82c-4c07-adf1-2a7a7bc3602d' order by step_index;"`
- 使用 `AsyncPostgresSaver` 读取对应 thread checkpoint，确认 `business_context.facts.order` 存在。

### 当前判断 / 根因

`order_status_inquiry` 是 fact-only 路径。路由层正确地在拿到业务事实后跳过 `generate_recommendation`，直接进入 `final_response`。但 `final_response` 缺少 `business_fact_response` 分支；当 `recommendation_draft=None` 时，它会调用 `_completed_response({})`，于是输出默认的“建议按已检索到的政策依据处理”模板。

同时，`_business_context_summary()` 只识别顶层 `business_context.order/refund_case/ticket`，但真实 `investigate` 输出是 `business_context.facts.order/refund_case/ticket`，导致已有业务事实无法被复用。

### 已做处理

- `src/agent/nodes/final_response.py` 新增 `order_status_inquiry` 的 business fact response 分支：当 intent 为 `order_status_inquiry`、operation 为 `read_status/advise`、无动作/审批/草稿状态、无 recommendation draft 且 business facts 存在时，直接返回业务事实摘要。
- `_business_context_summary()` 已支持真实的 `business_context.facts.*` 结构，同时保留旧的顶层结构兼容。
- 新增单元测试覆盖：`business_context.facts.order` 不再落入默认政策建议模板。
- 新增 graph 测试覆盖：`order_status_inquiry` fact-only 路径不执行 `generate_recommendation`，最终回答包含订单事实。

### 剩余问题

- 当前回答能展示订单层事实和关联退款/工单提示，但还没有继续根据 `relation_hints.latest_refund_case_id` 自动查询关联退款单详情。若产品期望“退款进度”必须包含退款单状态，需要后续增强 `investigate` 的多步业务事实追查能力。
- 对 fact-only 回答，右侧 Evidence 面板可能仍为空，因为最终回答没有引用政策证据；这不影响订单事实回答，但 UI 文案可以后续区分“政策证据”和“业务事实来源”。

### 下次继续排查入口

如订单进度回答仍不完整，优先检查 `src/agent/nodes/investigate.py` 是否应根据 `order.relation_hints` 自动追加 `get_refund_case` / `get_ticket`，以及 `get_refund_case` 当前是否支持通过内部关联 ID 查询。

### 验证结果

- `uv run pytest tests/agent/test_nodes/test_final_response.py tests/agent/test_phase22_final_response.py tests/agent/test_graph.py -q`：48 passed，1 warning。
- 新镜像下 `/api/v1/agent-runs` + SSE 路径复现通过：run_id=`fbd397d7-b26e-4c9c-a441-4f997c1812b8`，最终回答为：

```text
当前查询结果：
已查询到订单信息：订单号 ORD-2024-001，状态 pending，商品 蓝牙降噪耳机 Pro，金额 599.00 CNY，存在关联退款；存在未关闭工单。
```

## 4. 前端 demo token 失效后将 401 误显示为通用执行失败

日期：2026-06-20

### 问题现象

本地 UI 提交问题后显示：

```text
执行遇到问题，请重试。如问题持续，请联系管理员。
```

这条错误看起来像 agent 执行失败，但 timeline 没有新的有效 run 结果。

### 如何检测 / 复现

1. 查看 API 日志，发现最新前端请求是：
   - `POST /api/v1/agent-runs HTTP/1.1" 401 Unauthorized`
2. 同一时间没有新的 graph 执行异常，也没有新的 completed/error run 被创建。
3. 前端 `useAgentRun.submitQuery()` 在 `createRun()` 返回失败时直接显示通用错误文案。
4. 前端 auth 逻辑只在页面加载或切换角色时调用一次 `/auth/demo-token`，API 重启、token 过期或内存 token 失效后不会自动刷新。

### 关键证据或命令

- `docker compose logs api --tail=260`
- 日志中出现来自 frontend 容器的 `POST /api/v1/agent-runs` 两次 `401 Unauthorized`。

### 当前判断 / 根因

这是前端认证恢复问题，不是 agent graph、RAG、memory 或 final_response 逻辑失败。前端持有的 demo token 失效后，受保护接口返回 401；UI 将该错误统一渲染成“执行遇到问题”，导致误导排查方向。

### 已做处理

- `frontend/src/lib/api.ts` 新增 demo 用户名记录和 `refreshDemoToken()`。
- `apiFetch()` 对非 `/auth/demo-token` 的请求遇到 401 时，会自动调用 `/auth/demo-token` 刷新 demo token，并用新 token 重试原请求一次。
- `getDemoToken(username)` 会记录当前 demo 用户名，供后续自动刷新使用。
- 新增 `frontend/src/lib/api.test.ts` 覆盖：第一次 `/agent-runs` 返回 401 后，自动刷新 token，并用新 token 重试成功。
- 已重启 frontend 容器，确保 dev server 使用最新前端源码。

### 剩余问题

- 如果 `/auth/demo-token` 本身失败，前端仍会显示错误；这时应检查 demo auth 是否开启、用户是否存在、API 是否健康。
- 旧浏览器页面如果仍保持旧 JS 运行态，刷新页面一次即可加载新前端代码。

### 下次继续排查入口

遇到该通用错误时，优先查看 API 日志里的 HTTP 状态码：如果是 401，先查前端 token 刷新；如果 `/agent-runs/{id}/events` 已开始执行并返回 error，再排查 graph / node 异常。

### 验证结果

- `npm run build`：通过。
- `npm test`：2 files passed，4 tests passed。

## 5. 最终回答已有政策依据，但右侧 Evidence 面板为空

日期：2026-06-20

### 问题现象

本地 UI 查询 `平台的退款超时处理规则是什么？` 后，左侧 Agent 最终回答已经包含：

```text
依据：根据 merchant_faq / merchant_faq_000；根据 refund_time_limits / refund_time_limits_000；根据 refund_policy / refund_policy_000。
```

但右侧 Evidence Tab 仍显示：

```text
暂无证据
Agent 执行过程中将自动检索相关规则和证据
```

### 如何检测 / 复现

1. 从 UI 截图确认最终回答已有政策引用，但 Evidence Tab 为空。
2. 查询最新 run `87e03449-5df6-4e42-ae4b-0241b979c289`，确认 `agent_runs.final_response` 中确实持久化了政策引用。
3. 调用 `/api/v1/agent-runs/{run_id}/evidence`，返回 `evidence: []`。
4. 查询 `agent_steps`，发现该 run 的 `investigate`、`generate_recommendation`、`final_response` 步骤 `evidence_refs` 均为空。

### 当前判断 / 根因

右侧 Evidence Tab 是从 `/agent-runs/{id}/evidence` 读取持久化 trace step 的 `evidence_refs`。此前部分政策问答路径虽然在最终回答里渲染了 `draft.evidence_refs`，但 `final_response` 生成的 trace step 没有携带这些引用，导致后端 evidence endpoint 返回空。

另外，初次修复后同时返回了 `generate_recommendation` 的完整引用和 `final_response` 的简版引用，右侧会出现同一 `doc_key/chunk_id` 的重复卡片，因此需要同时做去重。

### 已做处理

- `src/agent/nodes/final_response.py` 的 final trace step 支持携带经过白名单过滤的安全 `evidence_refs`。
- final response 会优先把 `draft.evidence_refs` 的 `doc_key/chunk_id` 解析成 state 中完整的 `EvidenceRefV1` 安全投影，避免只落简版引用。
- `src/api/routers/agent_runs.py` 的 `_dedupe_evidence_refs()` 增强为按 `evidence_id` 保留不同版本，同时跳过后续同 `doc_key/chunk_id` 的简版重复投影。
- 测试覆盖了引用字段白名单、非 allow/action 场景不泄露 evidence_refs、以及完整 ref + 简版 ref 去重。

### 验证结果

- `uv run pytest tests/test_agent_runs_api.py tests/agent/test_phase22_final_response.py tests/agent/test_nodes/test_final_response.py -q`：47 passed，1 warning。
- `uv run pytest tests/test_agent_runs_api.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/rag_context/test_routing.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_graph.py tests/agent/test_nodes/test_final_response.py tests/agent/test_trace.py -q`：128 passed，1 warning。
- 新 API 镜像下真实 `/api/v1/agent-runs` + SSE 验证通过：run_id=`581ca30a-8e39-42ba-886f-09e31f4cd8c3`，`final_status=completed`，`/evidence` 返回 3 条证据：`merchant_faq_000`、`refund_time_limits_000`、`refund_policy_000`，无重复简版卡片。

## 6. VPN 慢导致 Docker build 反复下载超时，且容器启动时重复下载依赖

日期：2026-06-20

### 问题现象

本地重建 API 镜像时，PyPI wheel 下载经常超时。失败包包括 `pdfminer-six`、`pyyaml`、`langgraph-checkpoint`、`wheel` 等。即使镜像构建成功，API 容器启动日志还会出现：

```text
Creating virtual environment at: .venv
Downloading ...
```

说明 build 阶段装过依赖后，运行时又通过 `uv run` 建虚拟环境并重新下载依赖。

### 如何检测 / 复现

1. 执行 `docker compose build api` 或 `docker compose up -d --build api`。
2. Docker build 日志中多次出现 `operation timed out`，外层 3 次重试后仍可能失败。
3. 查看 `docker compose logs api --tail=80`，发现容器启动阶段又创建 `.venv` 并下载 Python 依赖。
4. 读取 `docker-entrypoint.sh` 和 `Dockerfile`，确认 entrypoint 使用 `uv run alembic upgrade head`，CMD 使用 `uv run uvicorn ...`。

### 当前判断 / 根因

这是网络与 Docker 构建方式叠加的问题：

- VPN 慢时，镜像内部每次重新下载 PyPI wheel 都容易超时。
- 原 Dockerfile 没有持久化 pip/uv 下载缓存，改代码导致依赖安装层重建时会重新下载。
- API 容器运行时使用 `uv run`，会在容器内创建 `.venv`，绕过 build 阶段已经安装到 system Python 的依赖，造成重复下载。

### 已做处理

- `Dockerfile` 为 `pip install uv` 增加 BuildKit cache mount：`/root/.cache/pip`。
- `Dockerfile` 为 `uv pip install --system -e .` 增加 BuildKit cache mount：`/root/.cache/uv`。
- `docker-compose.yml` 为 API build 增加 `PIP_INDEX_URL` 与 `UV_DEFAULT_INDEX` build args。
- 本地验证时使用：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
docker compose build api
```

- `docker-entrypoint.sh` 改为直接执行 `alembic upgrade head`。
- `Dockerfile` CMD 改为直接执行 `uvicorn ...`，不再通过 `uv run` 在容器启动时创建 `.venv`。

### 验证结果

- 使用清华 PyPI 镜像后，`pip install uv` 约 6 秒完成。
- `uv pip install --system -e .` 首次镜像源下载约 21 秒完成。
- 缓存热后重新 build，依赖安装层约 6 秒完成，整个 API build + recreate 约 20 秒量级。
- API 启动日志已不再出现 `.venv` 创建和依赖下载，只执行迁移并启动 Uvicorn。

### 下次继续排查入口

如果 Docker build 又慢，先确认是否设置了：

```bash
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
```

如果公司或 VPN 环境不适合清华源，可替换为当前网络更快的 PyPI 镜像；关键是同时配置 `PIP_INDEX_URL` 和 `UV_DEFAULT_INDEX`，否则 `pip install uv` 与 `uv pip install` 会走不同来源。

## 7. Agent Console 聊天历史被覆盖且 Timeline 节点重复显示

日期：2026-06-20

### 问题现象

本地 Agent Console 连续提交问题后，上一轮 Agent 回复会从聊天区消失，只保留用户 query 和当前 `finalResponse`。中间 Agent Timeline 会把同一节点的 `step_started` / `step_completed` 各显示一条，`final_response` 还会因最终 SSE 事件再重复一次。

同时，订单进度类 fact-only 回答右侧 Evidence 为空，容易被误解为回答缺少依据。

### 如何检测 / 复现

1. 打开 `localhost:3000`。
2. 连续提交 `平台的退款超时处理规则是什么？` 和 `订单ORD-2024-001的退款进度如何？`。
3. 观察聊天区：旧 Agent 回复被当前 `finalResponse` 覆盖。
4. 观察 Agent Timeline：同一节点有 running/completed 两条记录。
5. 查看 Evidence：订单事实回答没有政策 evidence，旧空状态文案没有说明 fact-only 场景。

### 关键证据或命令

- `frontend/src/components/chat/ChatPanel.tsx` 原先只在组件本地保存 `queries`，Agent 回复来自单个 `state.finalResponse`。
- `frontend/src/hooks/useAgentRun.ts` 原先对每个 SSE event 执行 `steps: [...current.steps, event]`。
- `frontend/src/components/details/EvidenceTab.tsx` 原先所有空 evidence 都显示“Agent 执行过程中将自动检索相关规则和证据”。

### 当前判断 / 根因

聊天区的数据模型不是完整 transcript，而是“用户 query 列表 + 当前 finalResponse”，所以新 run 会天然覆盖旧 Agent 消息。Timeline 没有按节点 identity 合并事件，而是逐帧 append SSE 事件。订单进度类回答没有政策 evidence 是正常 fact-only 路径，但 UI 文案没有区分“暂无政策证据”和“没有任何依据”。

后续复核发现，Timeline 即使前端改成同一行替换，页面仍可能直接显示 `completed`：后端 `_event_generator()` 原先消费的是 LangGraph `stream_mode="updates"`，该模式只在节点完成后返回 update，因此后端只能在节点已经结束后连续合成 `step_started` 和 `step_completed`。这不是前端渲染慢的问题，而是 SSE 事件源缺少真实节点 start/end 生命周期。

### 已做处理

- `useAgentRun` 新增 `messages` 状态，按 user/assistant 消息保留完整会话轮次。
- 新 query 只重置当前 run 的执行状态，不清空既有 `messages`；新对话仍会清空。
- `useAgentRun` 按节点 key 合并 timeline event：`run_started` / `receive_request` 合并为一条，`step_started` / `step_completed` 更新同一条，最终 `final_response` event 替换同一 final row。
- Timeline 单行状态过渡为：节点开始后显示 `running`，收到真实节点结束事件后同一行替换为 `completed`；不是直接显示完成态。
- `src/api/routers/agent_runs.py` 对真实 LangGraph 改为消费 `astream_events(version="v2")`：节点级 `on_chain_start` 发送 `step_started/running`，节点级 `on_chain_end` 发送 `step_completed/completed`。
- 后端只接收 `event.name == metadata.langgraph_node` 的节点级 lifecycle event，避免把节点内部 runnable/tool 事件误显示成 Timeline 步骤。
- 原 `stream_mode="updates"` 逻辑保留为测试/兼容 fallback，但不再作为真实 Agent Console 的主要事件源。
- 已移除前端 800ms 最小 running 展示窗口和后端最小 running 人为延迟，避免 UI 显示与真实执行状态不一致。
- 前端不再把每个节点的 `completed` 当作整个 run 已完成；只有最终回复、错误、审批等 run-level 事件改变整体终态。
- `EvidenceTab` 的空状态改为“暂无政策证据”，并说明订单、退款单、工单类回答可能基于业务事实，可到 Trace 查看查询步骤。

### 剩余问题

- 当前没有把业务事实来源单独做成 Evidence 卡片。若产品希望 Details 同时展示 order/refund/ticket fact refs，需要后续增加 Business Facts tab 或扩展 Evidence endpoint 的语义。
- Chrome 手动视觉验证过程中焦点切换到其他用户窗口，未继续操作用户浏览器；本次以自动化测试、lint 和 build 作为验证结论。

### 下次继续排查入口

如聊天历史或 timeline 再次异常，优先检查 `frontend/src/hooks/useAgentRun.ts` 的 `messages` 更新、`timelineEventKey()` 和 `upsertTimelineEvent()`；如 Evidence 为空引起误解，优先检查当前 run 是 policy evidence 路径还是 business fact-only 路径。

### 验证结果

- `cd frontend && npm test -- --run src/hooks/useAgentRun.test.ts src/lib/api.test.ts`：2 files passed，6 tests passed。
- `uv run pytest tests/test_agent_runs_api.py -q`：22 passed，1 warning。
- `uv run ruff check src/api/routers/agent_runs.py tests/test_agent_runs_api.py`：通过。
- `cd frontend && npm run lint`：通过。
- `cd frontend && npm run build`：通过。
- `PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple docker compose up -d --build api`：API 镜像已重建，容器健康。
- `docker compose restart frontend`：frontend dev 容器已重启并健康，确保浏览器刷新后加载最新前端 runtime。
- 真实 SSE 冒烟 run `8f4bd03c-e8f9-4cc3-abd0-a32d4990712e`：`investigate` 在 17.51s 收到 `step_started/running`，18.00s 收到同节点 `step_completed/completed`，随后立即进入 `final_response`。

## 8. 订单 follow-up 被误判为动作请求并要求提供操作类型

日期：2026-06-20

### 问题现象

本地 Agent Console 中，用户先问 `订单ORD-2024-001的退款进度如何？`，Agent 已返回订单事实；随后用户追问 `那这个订单下一步应该怎么处理？`，Agent 没有复用上一轮订单号继续查询，而是直接回复：

```text
请提供操作类型。
```

Timeline 只执行 `receive_request -> classify_intent -> clarification_gate -> final_response`，没有进入 `session_memory_load`、`extract_slots` 或 `investigate`。

### 如何检测 / 复现

1. 查询最新 run，确认 `c9e77d8c-62ef-4915-a9a1-fc2469cdd048` 的输入是 `那这个订单下一步应该怎么处理？`，最终回复是 `请提供操作类型。`
2. 读取该 run 的 checkpoint，确认分类结果：
   - `primary_intent=action_request`
   - `requested_operation=advise`
   - `intent_confidence=0.82`
   - `required_slots.all_of=["action_type"]`
   - `routing_hints.clarification_reason=missing_order_reference`
3. 查询 `session_memories`，确认同一 thread 中已有 `order_id=ORD-2024-001`，但该 slot 只兼容 `order_status_inquiry`，对本轮 `action_request` 不可用。

### 关键证据或命令

- `docker compose exec -T postgres psql -U moca -d moca -c "select id, input_query, final_status, left(coalesce(final_response,''), 240) as final_response, started_at from agent_runs order by started_at desc limit 8;"`
- 使用 `AsyncPostgresSaver.aget_tuple()` 读取 thread checkpoint，看到 `llm_outputs.intent_classification.raw.reason_codes=["action_handling_question","missing_context_reference"]`。
- `docker compose exec -T postgres psql -U moca -d moca -c "select thread_id, version, active_slots_json::text, unresolved_questions_json::text, last_intent, last_business_context_refs_json::text from session_memories where thread_id='demo-ec085b6d-9a03-4804-a4fa-d7f2127f578e' and deleted_at is null;"`

### 当前判断 / 根因

这是 intent 归一化和 session memory slot 兼容范围的问题，不是前端没有展示订单号。

LLM 把 `那这个订单下一步应该怎么处理？` 归为 `action_request + advise`，但该 intent 的规范 required slots 包含 `action_type`，于是路由直接进入 clarification。由于这一轮在 `clarification_gate` 前没有加载 session memory，`这个订单` 没有被解析回上一轮的 `ORD-2024-001`。

同时，上轮 `order_status_inquiry` 写入的 `order_id` 只兼容同一个 intent，后续退款排查/处理建议类 follow-up 即使加载 memory，也会被兼容性过滤掉。

另发现 `receive_request` 没有清理 `last_business_context_refs`，与其“每轮重置 ephemeral state”的注释不一致，导致 clarification run 可能把上一轮业务 ref 继续写回 memory。

### 已做处理

- `src/agent/intent_policy.py` 增加确定性归一化：对非执行、非补偿的 `action_request + advise` 且包含 `下一步/怎么处理/如何处理` 等处理建议语义的订单/退款 follow-up，归一为 `refund_troubleshooting + read_status`，避免强制要求 `action_type`。
- `src/agent/nodes/memory_write.py` 写入 `order_id/refund_case_id/ticket_id` 时按业务对象扩展兼容 intent；`action_type` 不跨 intent 复用，避免把 `inquiry` 当成真实动作类型。
- `src/memory/service.py` 读取 session memory 时兼容旧数据：旧 `order_status_inquiry` 写入的 `order_id` 可以在同线程退款排查 follow-up 中复用；`ticket_id` 仍按工单/投诉/申诉相关意图收窄，不会被退款排查误用。
- `src/agent/nodes/receive_request.py` 每轮重置 `last_business_context_refs`，避免 checkpoint 残留业务 ref 被误写入新 run。
- `src/agent/nodes/final_response.py` 调整 `manual_review` verifier 分支：先展示已查询到的订单/退款/工单业务事实，再说明当前不能给出具体处理动作和需要补充/复核的信息；不再把该场景压缩成“当前证据状态需要人工复核”一句话。
- 最终回复只从 `business_context` 渲染订单状态，避免采纳 recommendation draft 中可能不可靠的推理文本；例如业务事实为 `pending` 时，不会因 draft 文案误写成“已完成”。
- 新增回归测试覆盖 intent 归一化、旧 memory slot 兼容、以及整图 follow-up 不再问 `action_type`。

### 剩余问题

- 该修复只解决“下一步/怎么处理”这类非执行的处理建议 follow-up。若用户明确说“直接退款/发券/创建补偿”，仍应走动作/审批安全路径，不应静默执行。
- 如果 session memory 已过期或切换新对话，系统仍需要用户重新提供订单号/退款单号。

### 下次继续排查入口

如同类问题复现，优先检查：

- `src/agent/intent_policy.py` 的 `_is_next_step_advice_query()` 和 `resolve_intent_precedence()`。
- `src/memory/service.py` 的 `_slot_intent_compatible()`。
- `src/agent/nodes/memory_write.py` 的 `_compatible_intents_for_slot()`。

### 验证结果

- `uv run ruff check src/agent/intent_policy.py src/agent/nodes/memory_write.py src/memory/service.py src/agent/nodes/receive_request.py tests/agent/test_intent_routing.py tests/agent/test_memory_write_node.py tests/memory/test_session_memory_isolation.py tests/agent/test_session_memory_integration.py`：通过。
- `uv run pytest tests/agent/test_intent_routing.py tests/agent/test_memory_write_node.py tests/memory/test_session_memory_isolation.py tests/agent/test_session_memory_integration.py -q`：36 passed，1 warning。
- `uv run pytest tests/agent/test_graph.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_extract_slots.py -q`：30 passed，1 warning。
- `uv run pytest tests/memory/test_session_memory_isolation.py tests/agent/test_session_memory_integration.py tests/agent/test_memory_evidence_boundary.py -q`：13 passed，1 warning。
- `uv run ruff check src/agent/intent_policy.py src/agent/nodes/memory_write.py src/memory/service.py src/agent/nodes/receive_request.py src/agent/nodes/final_response.py tests/agent/test_intent_routing.py tests/agent/test_memory_write_node.py tests/memory/test_session_memory_isolation.py tests/agent/test_session_memory_integration.py tests/agent/test_phase22_final_response.py`：通过。
- `uv run pytest tests/agent/test_intent_routing.py tests/agent/test_memory_write_node.py tests/memory/test_session_memory_isolation.py tests/agent/test_session_memory_integration.py tests/agent/test_graph.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_extract_slots.py tests/agent/test_phase22_final_response.py tests/agent/test_nodes/test_final_response.py -q`：93 passed，1 warning。
- `PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple docker compose up -d --build api`：API 镜像已重建并启动。
- 新线程 live smoke `codex-smoke-1781951023142`：
  - 第一轮 run `438838b8-2690-4809-82d2-a7824ef48692` 查询 `订单ORD-2024-001的退款进度如何？`，返回订单 `pending`、商品、金额、关联退款和未关闭工单。
  - 第二轮 run `b2867dda-8244-4c86-8e28-9b22d097dec3` 查询 `那这个订单下一步应该怎么处理？`，trace 为 `receive_request -> classify_intent -> session_memory_load -> extract_slots -> investigate -> generate_recommendation -> final_response`，`investigate` 工具为 `get_order,search_policy`。
  - 第二轮最终回复包含 `ORD-2024-001`、`状态 pending`、关联退款/未关闭工单，并说明当前需要人工复核、未创建审批请求或动作草稿，以及需要补充/复核退款原因、诉求分类和证据材料。

## 9. `gsd-sdk query state.record-session` named args 误写 STATE.md

日期：2026-06-20

### 问题现象

执行 `$gsd-discuss-phase 24` 收尾时，按 workflow 文档调用：

```bash
gsd-sdk query state.record-session --stopped-at "Phase 24 context gathered" --resume-file ".planning/phases/24-agent-runs-short-term-memory-parity/24-CONTEXT.md"
```

命令返回 `recorded=true`，但 `.planning/STATE.md` 被误写：

- frontmatter 的 `milestone` 从 `v1.7` 变成 `v1.0`。
- `milestone_name` 变成 `milestone`。
- `Last session` 被写成 `--stopped-at`。
- `Resume file` 被写成 `--resume-file`。

### 如何检测 / 复现

查看 `git diff -- .planning/STATE.md` 可看到上述字段异常。随后读取 `gsd-tools.cjs` 和 `state.cjs`，确认底层工具期望 named args，但当前 `gsd-sdk query` 路径中的 `state.record-session` handler 对参数转发/解析存在偏差。

### 关键证据或命令

- `gsd-sdk query state.record-session --stopped-at "Phase 24 context gathered" --resume-file ".planning/phases/24-agent-runs-short-term-memory-parity/24-CONTEXT.md"`
- `git diff -- .planning/STATE.md`
- `sed -n '430,500p' /Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `sed -n '560,610p' /Users/ming/.codex/get-shit-done/bin/lib/state.cjs`

### 当前判断 / 根因

这是 GSD CLI/query handler 参数路径问题，不是 MOCA 业务代码问题。workflow 文档中的 named-args 调用在当前 `gsd-sdk query` 环境下会被误解析，导致 STATE.md 字段被错误替换。

### 已做处理

- 未提交错误状态。
- 使用最小 `apply_patch` 恢复 `.planning/STATE.md` 的 v1.7 frontmatter、Phase 24 context gathered 状态、真实 resume file 和下一步 `$gsd-plan-phase 24`。

### 剩余问题

- 尚未修复 GSD 工具本身。后续再次调用 `state.record-session` 时需要先确认当前工具版本是否已修复，或避免直接照 workflow 文档使用该 named-args 形式。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`
- `gsd-sdk query state.record-session`

### 验证结果

- 已用 `git diff -- .planning/STATE.md` 确认最终 diff 只包含预期 session 更新：`stopped_at=Phase 24 context gathered`、`last_activity=Gathered Phase 24 context`、`Resume file=.planning/phases/24-agent-runs-short-term-memory-parity/24-CONTEXT.md`、`Next=$gsd-plan-phase 24`。

## 10. Phase 24-04 补充验证误用不存在的 pytest 节点名

日期：2026-06-20

### 问题现象

执行 Phase 24-04 补充回归时，命令使用了不存在的测试节点：

```bash
uv run pytest tests/tools/test_tool_result_storage.py::test_tool_result_storage_layers_raw_result_and_prompt_summary tests/tools/test_tool_result_storage.py::test_prompt_summary_excludes_large_nested_data -q
```

pytest 返回 exit code 4，提示 `test_tool_result_storage_layers_raw_result_and_prompt_summary` 在 `tests/tools/test_tool_result_storage.py` 中不存在。

### 如何检测 / 复现

直接运行上述命令即可复现 collection error。随后用 `rg -n "def test_" tests/tools/test_tool_result_storage.py` 查到真实测试名。

### 关键证据或命令

- 错误命令：`uv run pytest tests/tools/test_tool_result_storage.py::test_tool_result_storage_layers_raw_result_and_prompt_summary tests/tools/test_tool_result_storage.py::test_prompt_summary_excludes_large_nested_data -q`
- 定位命令：`rg -n "def test_" tests/tools/test_tool_result_storage.py`
- 正确测试名：`test_tool_result_storage_keeps_four_layers_separate`

### 当前判断 / 根因

这是本地验证命令写错测试节点名，不是业务代码失败，也不是测试本身失败。

### 已做处理

改用真实节点名重新执行：

```bash
uv run pytest tests/tools/test_tool_result_storage.py::test_tool_result_storage_keeps_four_layers_separate tests/tools/test_tool_result_storage.py::test_prompt_summary_excludes_large_nested_data -q
```

### 剩余问题

无。该问题只影响一次补充验证命令。

### 下次继续排查入口

如果再次出现 pytest `not found`，先用 `rg -n "def test_" <test-file>` 核对节点名，再重跑 focused command。

### 验证结果

- 正确命令通过：`2 passed, 1 warning`。

## 11. Phase 24-05 新增 fail-closed 测试误用 `_create_run(thread_id=...)`

日期：2026-06-20

### 问题现象

执行 24-05 focused pytest 时，新增的 `test_agent_run_stream_fails_closed_when_user_message_missing` 失败：

```text
TypeError: _create_run() got an unexpected keyword argument 'thread_id'
```

同一命令中的 `test_create_agent_run_persists_exactly_one_user_message` 和 `test_agent_run_stream_passes_conversation_ids_to_graph_and_tools` 已通过。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/test_agent_runs_api.py::test_create_agent_run_persists_exactly_one_user_message tests/test_agent_runs_api.py::test_agent_run_stream_passes_conversation_ids_to_graph_and_tools tests/test_agent_runs_api.py::test_agent_run_stream_fails_closed_when_user_message_missing -q
```

### 关键证据或命令

- `rg -n "async def _create_run" -A40 tests/test_agent_runs_api.py`
- `_create_run` 只接受 `tenant_id`、`user_id`、`final_status`，内部已经生成唯一 `thread_id=f"sse-{run_id}"`。

### 当前判断 / 根因

这是新增测试误用了已有 helper 签名，不是 24-05 production 实现失败。

### 已做处理

移除测试中的 `thread_id=...` 参数，继续使用 `_create_run` 自带的唯一 thread id。

### 剩余问题

无。

### 下次继续排查入口

如果该测试再次失败，优先检查缺失 user message 分支是否在 `_claim_pending_run_for_stream` 后、graph 调用前执行，以及 run 是否被终止为 `error`。

### 验证结果

- 修正后重跑 24-05 focused pytest：`3 passed, 1 warning`。

## 12. Phase 24-05 后推进 GSD state 时里程碑字段再次回退到 v1.0

日期：2026-06-20

### 问题现象

执行 24-05 完成后的状态推进命令后，`.planning/STATE.md` frontmatter 中 `milestone` 被写回 `v1.0`、`milestone_name` 被写成 `milestone`，同时 Phase 24 进度表仍显示 `4/9`，与刚完成的 24-05 不一致。

### 如何检测 / 复现

运行：

```bash
gsd-sdk query state.advance-plan && gsd-sdk query state.update-progress
sed -n '1,220p' .planning/STATE.md
```

### 关键证据或命令

- `gsd-sdk query state.advance-plan` 返回 `current_plan: 6`、`completed: 5`。
- `sed -n '1,220p' .planning/STATE.md` 显示 `milestone: v1.0`、`milestone_name: milestone`、进度表 `4/9`。
- `rg -n "v1\\.7|Phase 24|Agent Runs Short-term Memory Parity" .planning/PROJECT.md .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/MILESTONES.md .planning/STATE.md` 确认当前权威里程碑是 `v1.7 Short-term Memory Unification`。

### 当前判断 / 根因

这是已知 GSD state 工具写入问题的再次触发，不是 MOCA 业务代码或 Phase 24 实现问题。工具的数值推进成功，但 STATE.md 的部分上下文字段被错误回填。

### 已做处理

用最小 `apply_patch` 修复 `.planning/STATE.md`：

- `milestone: v1.7`
- `milestone_name: Short-term Memory Unification`
- Phase 24 进度表改为 `5/9`

### 剩余问题

尚未修复 GSD 工具本身。后续每次调用 `state.advance-plan` / `state.update-progress` 后仍需检查 `.planning/STATE.md` 是否回退。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`
- `gsd-sdk query state.advance-plan`
- `gsd-sdk query state.update-progress`

### 验证结果

- 已重新读取 `.planning/STATE.md` 并确认当前 plan 为 6/9、完成 5/9，frontmatter 回到 v1.7。

## 13. Phase 24-06 SSE memory ordering 测试仍 monkeypatch 旧的 router 级 `memory_write`

日期：2026-06-20

### 问题现象

实现 24-06 finalizer service 后运行 focused pytest，`test_sse_final_response_after_bounded_memory_persistence_result` 失败。测试期望 `memory_results` 已包含 fake memory write 结果，但实际为空。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_updates_thread_summary_idempotently tests/test_agent_runs_api.py::test_sse_final_response_after_bounded_memory_persistence_result tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/memory/test_session_memory_service.py -q
```

### 关键证据或命令

- pytest 失败断言：`assert [] == [{"status": "completed", "reason_code": "memory_persisted"}]`
- 测试仍使用：`monkeypatch.setattr("src.api.routers.agent_runs.memory_write", fake_memory_write)`
- 24-06 实现后实际调用路径变为：`src.api.services.agent_run_memory.memory_write`

### 当前判断 / 根因

这是测试 monkeypatch 路径没有随 finalizer service 边界更新导致的验证失败，不是生产 finalizer ordering 失败。

### 已做处理

- 将测试 monkeypatch 路径改为 `src.api.services.agent_run_memory.memory_write`。
- 增加断言验证 finalizer 传入 `memory_write` 的 `tenant_id`、`user_id`、`thread_id`、`current_run_id`、`final_response` 和当前 DB session。
- 补充 lifecycle events 分支、非 completed skip、`_complete_run` 失败回滚测试。

### 剩余问题

无。旧 router 级 `_schedule_memory_write_after_response` helper 仍保留给 legacy `/agent/chat` 使用，但 `/agent-runs` completed final_response 路径不再调用它。

### 下次继续排查入口

- `src/api/services/agent_run_memory.py`
- `src/api/routers/agent_runs.py`
- `tests/test_agent_runs_api.py::test_sse_final_response_after_bounded_memory_persistence_result`
- `tests/test_agent_runs_api.py::test_sse_lifecycle_events_final_response_after_bounded_memory_persistence_result`

### 验证结果

- 修正后重跑 24-06 focused pytest：`19 passed, 1 warning`。
- `uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py tests/test_agent_runs_api.py tests/memory/test_session_memory_service.py` 通过。

## 14. Phase 24-06 后推进 GSD state 时里程碑字段再次回退到 v1.0

日期：2026-06-20

### 问题现象

执行 24-06 完成后的 `state.advance-plan` / `state.update-progress` 后，`.planning/STATE.md` frontmatter 再次从 `v1.7 Short-term Memory Unification` 回退到 `milestone: v1.0`、`milestone_name: milestone`，进度表仍显示 `5/9`，与命令返回的 `completed: 6` 不一致。

### 如何检测 / 复现

运行：

```bash
gsd-sdk query state.advance-plan && gsd-sdk query state.update-progress
sed -n '1,80p' .planning/STATE.md
```

### 关键证据或命令

- `state.advance-plan` 返回 `previous_plan: 6`、`current_plan: 7`。
- `state.update-progress` 返回 `completed: 6`、`percent: 67`。
- `sed -n '1,80p' .planning/STATE.md` 显示 frontmatter 回退到 `v1.0`，表格仍为 `5/9`。

### 当前判断 / 根因

这是 issue 12 中同一 GSD state 写入问题的再次触发。工具数值推进成功，但 STATE.md 部分上下文字段和人工可读表格没有保持当前 v1.7 语义。

### 已做处理

用最小 `apply_patch` 修复：

- `milestone: v1.7`
- `milestone_name: Short-term Memory Unification`
- Phase 24 进度表改为 `6/9`

### 剩余问题

GSD 工具本身仍未修复。后续完成 24-07、24-08、24-09 后还需继续检查并修复 STATE.md。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`
- `gsd-sdk query state.advance-plan`
- `gsd-sdk query state.update-progress`

### 验证结果

- 已重新读取 `.planning/STATE.md`，当前 plan 为 7/9、完成 6/9，frontmatter 已恢复 v1.7。

## 15. Phase 24-07 后推进 GSD state 时里程碑字段再次回退到 v1.0

日期：2026-06-20

### 问题现象

执行 24-07 完成后的 `state.advance-plan` / `state.update-progress` 后，`.planning/STATE.md` frontmatter 再次回退到 `milestone: v1.0`、`milestone_name: milestone`，进度表仍显示 `6/9`，与命令返回的 `completed: 7` 不一致。

### 如何检测 / 复现

运行：

```bash
gsd-sdk query state.advance-plan && gsd-sdk query state.update-progress
sed -n '1,70p' .planning/STATE.md
```

### 关键证据或命令

- `state.advance-plan` 返回 `previous_plan: 7`、`current_plan: 8`。
- `state.update-progress` 返回 `completed: 7`、`percent: 78`。
- `sed -n '1,70p' .planning/STATE.md` 显示 frontmatter 回退到 `v1.0`，表格仍为 `6/9`。

### 当前判断 / 根因

同 issue 12/14，是 GSD state 写入工具的上下文字段回填问题，不是 Phase 24 实现或验证问题。

### 已做处理

用最小 `apply_patch` 修复：

- `milestone: v1.7`
- `milestone_name: Short-term Memory Unification`
- Phase 24 进度表改为 `7/9`

### 剩余问题

GSD 工具本身仍未修复。后续完成 24-08、24-09 后仍需检查 STATE.md。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`
- `gsd-sdk query state.advance-plan`
- `gsd-sdk query state.update-progress`

### 验证结果

- 已重新读取 `.planning/STATE.md`，当前 plan 为 8/9、完成 7/9，frontmatter 已恢复 v1.7。

## 16. Phase 24-08 prompt context 安全测试发现 rolling summary / tool refs 泄漏禁用标记

日期：2026-06-20

### 问题现象

运行 24-08 focused pytest 时，`test_agent_runs_prompt_context_excludes_raw_tool_private_authority_and_debug_fields` 失败。组装后的 prompt 中仍包含 `raw_payload`、`private_reasoning`、`approval_authority_body`、`debug_trace`、`secret`、`EvidenceRefV1` 等禁用标记。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/conversation/test_service.py::test_agent_runs_prompt_context_loads_prior_summary_recent_messages_and_tool_summaries tests/agent/test_session_memory_integration.py::test_extract_slots_loads_agent_runs_prompt_context_from_trusted_config tests/agent/test_session_memory_integration.py::test_agent_runs_session_slots_explicit_current_turn_overrides_inherited tests/agent/test_session_memory_integration.py::test_agent_runs_session_memory_wrong_scope_fails_closed tests/agent/context/test_assembler.py::test_agent_runs_prompt_context_excludes_raw_tool_private_authority_and_debug_fields tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority tests/agent/test_required_slots.py -q
```

### 关键证据或命令

- 首次失败显示 `raw_payload` 从 `thread_rolling_summary` 进入 prompt。
- 修复 rolling summary / tool summary 后，第二次失败显示 `EvidenceRefV1` 从 `policy_evidence_refs` 进入 prompt。
- 涉及文件：`src/agent/context/assembler.py`、`src/agent/context/projectors.py`。

### 当前判断 / 根因

这是 prompt projector 边界不够严格：rolling summary 直接进入 `ContextAssembler`，tool refs 和通用 ref formatting 使用了基础 `_safe_scalar`，没有应用 Phase 24 的禁用标记过滤。

### 已做处理

- 新增 `project_thread_summary_for_prompt(...)` / `sanitize_prompt_context_text(...)`，保留安全摘要文本并移除禁用标记。
- `ContextAssembler` 对 `thread_rolling_summary` 先走 projector 再入 prompt block。
- `project_tool_result_summary(...)` 和通用 `_format_mapping(...)` 改用 prompt-safe scalar/filter。

### 剩余问题

无。该问题属于 prompt-safety 投影边界修复，不改变 evidence/business/action/replay authority 语义。

### 下次继续排查入口

- `src/agent/context/assembler.py`
- `src/agent/context/projectors.py`
- `tests/agent/context/test_assembler.py::test_agent_runs_prompt_context_excludes_raw_tool_private_authority_and_debug_fields`

### 验证结果

- 修正后重跑 24-08 focused pytest：`13 passed, 2 warnings`。
- `uv run ruff check src/agent/nodes/extract_slots.py src/agent/context/assembler.py src/agent/context/projectors.py tests/conversation/test_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py` 通过。

## 17. Phase 24-08 后推进 GSD state 时里程碑字段再次回退到 v1.0

日期：2026-06-20

### 问题现象

执行 24-08 完成后的 `state.advance-plan` / `state.update-progress` 后，`.planning/STATE.md` frontmatter 再次回退到 `milestone: v1.0`、`milestone_name: milestone`，Phase 24 进度表仍显示 `7/9`，与命令返回的 `completed: 8` 不一致。

### 如何检测 / 复现

运行：

```bash
gsd-sdk query state.advance-plan
gsd-sdk query state.update-progress
sed -n '1,70p' .planning/STATE.md
```

### 关键证据或命令

- `state.advance-plan` 返回 `previous_plan: 8`、`current_plan: 9`。
- `state.update-progress` 返回 `completed: 8`、`percent: 89`。
- `sed -n '1,70p' .planning/STATE.md` 显示 frontmatter 回退到 `v1.0`，Phase 24 表格仍为 `7/9`。

### 当前判断 / 根因

同 issue 12/14/15，是 GSD state 写入工具的上下文字段回填问题，不是 Phase 24 实现或验证问题。

### 已做处理

用最小 `apply_patch` 修复：

- `milestone: v1.7`
- `milestone_name: Short-term Memory Unification`
- Phase 24 进度表改为 `8/9`

### 剩余问题

GSD 工具本身仍未修复。后续完成 24-09 后仍需检查 STATE.md。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`
- `gsd-sdk query state.advance-plan`
- `gsd-sdk query state.update-progress`

### 验证结果

- 已重新读取 `.planning/STATE.md`，当前 plan 为 9/9、完成 8/9，frontmatter 已恢复 v1.7。

## 18. Phase 24-09 legacy/service focused gate 暴露同一 run 下重复 user message fixture

日期：2026-06-20

### 问题现象

执行 24-09 Task 1 focused pytest 时，`tests/conversation/test_service.py::test_load_prompt_context_returns_latest_committed_prior_turn_and_bounded_recent_messages` 失败，PostgreSQL 报 `uq_conversation_messages_active_tenant_run_role` 唯一约束冲突。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/test_agent_runs_api.py::test_agent_chat_only_token_invokes_legacy_chat_with_no_tool_permissions tests/conversation/test_service.py -q
```

### 关键证据或命令

- pytest 输出：`duplicate key value violates unique constraint "uq_conversation_messages_active_tenant_run_role"`。
- 冲突键：同一 `(tenant_id, run_id, role=user)`。
- 失败位置：`tests/conversation/test_service.py` 中 current turn fixture 对同一 `current_run_id` 连续调用两次 `append_user_message(...)`。

### 当前判断 / 根因

这是 Phase 24 新增 run/role 幂等唯一约束后的测试 fixture 过期，不是产品行为需要允许同一 run 多条 user message。当前契约是一次 run 至多一个 user message 和一个 assistant message；recent messages 仍可通过 user+assistant 组成。

### 已做处理

将该测试中第二条 current-turn recent message 从 `append_user_message(...)` 改为 `append_assistant_message(...)`，保留两条 recent message 的断言语义，同时符合 `(tenant, run, role)` 幂等约束。

### 剩余问题

无。已重跑 24-09 Task 1 focused pytest 验证通过。

### 下次继续排查入口

- `tests/conversation/test_service.py::test_load_prompt_context_returns_latest_committed_prior_turn_and_bounded_recent_messages`
- `src/conversation/service.py::append_or_get_user_message_for_run`
- DB 唯一约束 `uq_conversation_messages_active_tenant_run_role`

### 验证结果

- 修正后重跑同一 focused pytest 命令：`10 passed, 1 warning`。

## 19. Phase 24-09 focused regression gate 暴露 agent-runs stream 权限测试绕过 create 契约

日期：2026-06-20

### 问题现象

执行 24-09 Task 3 focused pytest gate 时，`tests/test_agent_runs_api.py::test_agent_chat_only_token_streams_with_no_tool_permissions` 失败：期望 SSE 返回 200，实际返回 409。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q
```

### 关键证据或命令

- pytest 输出：`assert 409 == 200`。
- 失败测试通过 `_create_run(...)` 直接插入 `AgentRun`，没有创建 Phase 24 现在要求的 run 级 user `ConversationMessage`。
- SSE 入口已在 Plan 24-05/24-07 中 fail closed：缺少 user conversation message 时返回 `RUN_CONVERSATION_MESSAGE_MISSING` / 409，避免无可信会话身份执行图。

### 当前判断 / 根因

这是测试 fixture 过期，不是 SSE 权限逻辑问题。Phase 24 后 `/api/v1/agent-runs/{run_id}/events` 的正确前置条件是通过 `/api/v1/agent-runs` create 路径创建 run 和 user message，再打开 SSE。

### 已做处理

将该权限测试改为先调用 `POST /api/v1/agent-runs` 创建 pending run，再调用 `/events`，保留原有断言：只有 `agent:chat` scope 时 trusted tool permissions 为空列表。

### 剩余问题

无。已重跑 24-09 focused regression gate 验证通过。

### 下次继续排查入口

- `tests/test_agent_runs_api.py::test_agent_chat_only_token_streams_with_no_tool_permissions`
- `src/api/routers/agent_runs.py::stream_agent_run_events`
- `RUN_CONVERSATION_MESSAGE_MISSING`

### 验证结果

- 单独重跑失败测试：`1 passed, 1 warning`。
- 重跑 24-09 focused pytest gate：`91 passed, 9 warnings`。

## 20. Phase 24-09 后推进 GSD state 时里程碑字段再次回退到 v1.0

日期：2026-06-20

### 问题现象

执行 24-09 完成后的 `state.advance-plan` / `state.update-progress` 后，`.planning/STATE.md` frontmatter 再次回退到 `milestone: v1.0`、`milestone_name: milestone`，Phase 24 进度表仍显示 `8/9`，与命令返回的 `completed: 9` 不一致。

### 如何检测 / 复现

运行：

```bash
gsd-sdk query state.advance-plan
gsd-sdk query state.update-progress
sed -n '1,70p' .planning/STATE.md
```

### 关键证据或命令

- `state.advance-plan` 返回 `advanced: false`、`reason: last_plan`、`current_plan: 9`、`total_plans: 9`。
- `state.update-progress` 返回 `completed: 9`、`percent: 100`。
- `sed -n '1,70p' .planning/STATE.md` 显示 frontmatter 回退到 `v1.0`，Phase 24 表格仍为 `8/9`。

### 当前判断 / 根因

同 issue 12/14/15/17，是 GSD state 写入工具的上下文字段回填问题，不是 Phase 24 实现或验证问题。

### 已做处理

用最小 `apply_patch` 修复：

- `milestone: v1.7`
- `milestone_name: Short-term Memory Unification`
- Phase 24 进度表改为 `9/9 | Verifying`

### 剩余问题

GSD 工具本身仍未修复。后续执行 `phase.complete` 后仍需再次检查 STATE.md。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`
- `gsd-sdk query state.advance-plan`
- `gsd-sdk query state.update-progress`
- `gsd-sdk query phase.complete 24`

### 验证结果

- 已重新读取 `.planning/STATE.md`，当前完成 9/9，frontmatter 已恢复 v1.7。

## 21. Phase 24 `phase.complete` 后 tracking 文档出现完成态不一致

日期：2026-06-20

### 问题现象

执行 `gsd-sdk query phase.complete 24` 后，命令返回 Phase 24 已完成且无 warning，但 tracking 文档仍出现不一致：

- `.planning/STATE.md` 进度被写成 `completed_phases: 2` / `total_phases: 1` / `percent: 200`。
- `.planning/STATE.md` 正文仍残留 `Stopped at: Phase 24 context gathered`、`Plan: Not started`、`Pending Todos: Execute Phase 24 implementation`、Phase 24 表格 `Verifying`。
- `.planning/ROADMAP.md` 中 v1.7 仍是 `[ ] Current milestone`，Phase 24 `Status: Planned`，Current Status 仍提示执行 discuss/plan。
- `.planning/REQUIREMENTS.md` traceability 已是 Complete，但主需求清单仍是未勾选。
- `.planning/PROJECT.md` 仍把 v1.7 写成 Current Milestone，Active requirements 未移动到 Validated，且 Next Milestone Setup 仍写 “after v1.6 archive”。

### 如何检测 / 复现

运行：

```bash
gsd-sdk query phase.complete 24
sed -n '1,120p' .planning/STATE.md
sed -n '1,120p' .planning/ROADMAP.md
sed -n '1,90p' .planning/REQUIREMENTS.md
sed -n '1,170p' .planning/PROJECT.md
```

### 关键证据或命令

- `phase.complete` 返回 `plans_executed: "9/9"`、`is_last_phase: true`、`roadmap_updated: true`、`state_updated: true`、`requirements_updated: true`、`has_warnings: false`。
- `git diff -- .planning/STATE.md .planning/ROADMAP.md .planning/REQUIREMENTS.md .planning/PROJECT.md` 显示 STATE 进度为 `200%`，ROADMAP/PROJECT 仍保留未完成叙述。

### 当前判断 / 根因

这是 GSD completion/tracking 写入逻辑的状态合并问题，不是 Phase 24 实现或验证失败。`phase.complete` 部分更新了 traceability 和 plan checkboxes，但没有把最后一个 phase 的 milestone/current-state 文案和 PROJECT 演进步骤完整同步；STATE 的 phase counter 也出现了重复计数。

### 已做处理

用最小 `apply_patch` 修复：

- `.planning/STATE.md`：进度改为 `1/1`、`100%`，Phase 24 表格改为 `Complete`，session continuity 改为 Phase 24 complete，下一步改为 `$gsd-new-milestone`。
- `.planning/ROADMAP.md`：v1.7 标为 completed，Phase 24 `Status: Complete`，Current Status 和 Next Step 改为完成态/新 milestone。
- `.planning/REQUIREMENTS.md`：STM-01 到 STM-14 主需求清单勾选为完成，并更新 footer。
- `.planning/PROJECT.md`：v1.7 移到 Last Shipped Milestone，Phase 24 active requirements 移到 Validated，Current Milestone 改为无 active milestone，Next Milestone Setup 改为 v1.7 完成后。

### 剩余问题

GSD 工具本身仍未修复。后续每次 `state.*` 或 `phase.complete` 后仍需检查 `.planning/STATE.md` / `.planning/ROADMAP.md` / `.planning/PROJECT.md` 是否漂移。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`
- `gsd-sdk query phase.complete 24`
- `gsd-sdk query state.update-progress`
- execute-phase workflow `update_roadmap` / `update_project_md`

### 验证结果

- 已重新读取四个 tracking 文档并检查 diff，完成态叙述一致；后续将仅提交这些 planning tracking 文件，不提交其它已有脏改。

## 22. 全量 `git diff --check` 被既有 study_plan 尾随空格挡住

日期：2026-06-21

### 问题现象

完成 Phase 24 review 修复和 Phase 24.1 facade 后，执行全量 `git diff --check` 失败，但失败位置不在本次代码改动范围内。

### 如何检测 / 复现

运行：

```bash
git diff --check
```

### 关键证据或命令

命令输出：

```text
study_plan/deep-research-report (1).md:261: trailing whitespace.
```

### 当前判断 / 根因

这是仓库既有 dirty worktree 中 `study_plan/deep-research-report (1).md` 的尾随空格问题，不是 Phase 24 review 修复或 Phase 24.1 新增文件引入的问题。

### 已做处理

未修改该 study_plan 文档，避免触碰用户已有改动。改为对本次触达文件运行范围限定的 diff check：

```bash
git diff --check -- src/api/routers/agent_runs.py src/api/services/agent_run_memory.py src/memory/schemas.py src/memory/session_bundle.py src/memory/__init__.py tests/test_agent_runs_api.py tests/memory/test_session_memory_bundle.py .planning/phases/24-agent-runs-short-term-memory-parity/24-REVIEW-FIX.md .planning/phases/24.1-session-memory-bundle-naming-and-read-model-facade/24.1-SUMMARY.md
```

范围限定检查通过。

### 剩余问题

`study_plan/deep-research-report (1).md:261` 仍有尾随空格；如果后续要提交该文档，应单独清理。

### 下次继续排查入口

- `study_plan/deep-research-report (1).md:261`
- `git diff --check`

### 验证结果

- 本次触达文件 `git diff --check -- ...` 通过。
- `uv run ruff check ...` 通过。
- `uv run pytest tests/test_agent_runs_api.py tests/memory/test_session_memory_bundle.py -q` 通过。

## 23. 并行调用 `gsd-sdk query phase.insert` 导致小数 phase 编号和名称错配

日期：2026-06-21

### 问题现象

准备追加 Phase 24.2、24.3、24.4 时，并行调用三次 `gsd-sdk query phase.insert 24 ...`，返回结果发生竞态：预期的 24.2 `Unified Session Memory Bundle Read Path` 被分配成 24.4，预期的 24.4 `Memory Eval MVP` 被分配成 24.2。

### 如何检测 / 复现

运行后检查：

```bash
rg -n "24\\.2|24\\.3|24\\.4|Unified Session|Memory Write Isolation|Memory Eval" .planning/ROADMAP.md .planning/STATE.md
find .planning/phases -maxdepth 1 -type d | sort | rg "24\\.[234]"
```

### 关键证据或命令

并发执行的三条命令分别返回：

```text
24.4 Unified Session Memory Bundle Read Path
24.3 Memory Write Isolation Policy and Observability MVP
24.2 Memory Eval MVP
```

### 当前判断 / 根因

`phase.insert` 会根据现有 decimal phase 计算下一个编号；并行调用时多个进程同时读取/写入 roadmap 和目录，导致编号分配顺序不可控。这是本地操作方式造成的问题，不是 MOCA 代码实现问题。

### 已做处理

- 将目录修正为：
  - `.planning/phases/24.2-unified-session-memory-bundle-read-path`
  - `.planning/phases/24.3-memory-write-isolation-policy-and-observability-mvp`
  - `.planning/phases/24.4-memory-eval-mvp`
- 手动修正 `.planning/ROADMAP.md` 中 Phase 24.2-24.4 的顺序、名称和 next step。
- 更新 `.planning/STATE.md`，把当前焦点切到 Phase 24.2-24.4 follow-up。

### 剩余问题

GSD `phase.insert` 本身没有并发锁；后续插入多个小数 phase 时必须顺序调用，不能并行。

### 下次继续排查入口

- `gsd-sdk query phase.insert`
- `/Users/ming/.codex/get-shit-done/workflows/insert-phase.md`
- `.planning/ROADMAP.md`

### 验证结果

已重新读取 `.planning/ROADMAP.md` 和 `.planning/phases/24.2-*` / `24.3-*` / `24.4-*` 目录，确认编号与名称恢复为预期。

## 24. Phase 24.2 初次验证发现 bundle projector 对轻量 PromptContext fake 过于严格

日期：2026-06-21

### 问题现象

Phase 24.2 将 prompt 节点改为通过 `SessionMemoryBundle` 读取上下文后，focused pytest 中两条既有 prompt assembly 测试失败，prompt 中缺少 `thread_rolling_summary` / `thread_rolling` 内容。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q
```

### 关键证据或命令

失败测试：

```text
tests/agent/test_nodes/test_generate_recommendation.py::test_generate_recommendation_prompt_uses_context_assembly_and_excludes_raw_payloads
tests/agent/test_nodes/test_assess_risk_and_approval.py::test_assess_risk_prompt_uses_context_assembly_and_excludes_raw_payloads
```

失败断言显示 prompt 里没有旧 fake `ConversationService.load_prompt_context(...)` 返回的 rolling summary 内容。

### 当前判断 / 根因

`SessionMemoryBundleService` 的 projector 按真实 DB model 读取 `id/run_id/message_index/created_at` 等字段；既有测试 fake 只提供 `summary_text/content/prompt_summary`。bundle projector 抛出异常后，agent context adapter fail-closed 返回空 prompt context。

### 已做处理

- `src/memory/session_bundle.py` projector 改为对缺失 `id/run_id/message_index/created_at` 的轻量对象使用稳定 fallback。
- `src/agent/context/session_memory_bundle.py` 仍保持 fail-closed，不把异常暴露给 prompt 节点。
- 新增 existing bundle 优先级回归，确保 state 中已有 bundle 时不会再调用旧 conversation service。

### 剩余问题

无。真实 DB row 路径不受影响，轻量 fake 和未来 adapter 对象也能通过同一 bundle read path。

### 下次继续排查入口

- `src/memory/session_bundle.py`
- `src/agent/context/session_memory_bundle.py`
- `tests/agent/test_nodes/test_generate_recommendation.py`

### 验证结果

修复后：

```bash
uv run pytest tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q
uv run ruff check src/agent/context/session_memory_bundle.py src/memory/session_bundle.py src/agent/nodes/session_memory_load.py src/agent/nodes/extract_slots.py src/agent/nodes/generate_recommendation.py src/agent/nodes/assess_risk_and_approval.py tests/agent/test_session_memory_load.py tests/agent/test_nodes/test_generate_recommendation.py tests/memory/test_session_memory_bundle.py
```

均通过。

## 29. Phase 24 review-fix 文档提交前 whitespace check 发现 EOF 多余空行

日期：2026-06-21

### 问题现象

准备提交 Phase 24 review-fix 时，`git diff --cached --check` 失败，提示 `.planning/phases/24-agent-runs-short-term-memory-parity/24-REVIEW-FIX.md` 文件末尾存在多余空行。

### 如何检测 / 复现

在 stage review-fix 相关代码和文档后运行：

```bash
git diff --cached --check
```

### 关键证据或命令

```text
.planning/phases/24-agent-runs-short-term-memory-parity/24-REVIEW-FIX.md:27: new blank line at EOF.
```

### 当前判断 / 根因

新增 Markdown 文档末尾多留了一个空白行，触发 git whitespace check。

### 已做处理

已删除该 EOF 空白行，并保留 review-fix 文档内容不变。

### 剩余问题

无。

### 下次继续排查入口

- `.planning/phases/24-agent-runs-short-term-memory-parity/24-REVIEW-FIX.md`
- `git diff --cached --check`

## 30. Phase 24.1 summary 文档提交前 whitespace check 发现 EOF 多余空行

日期：2026-06-21

### 问题现象

准备提交 Phase 24.1 summary 文档时，`git diff --cached --check` 失败，提示文档末尾存在多余空行。

### 如何检测 / 复现

在 stage Phase 24.1 summary 后运行：

```bash
git diff --cached --check
```

### 关键证据或命令

```text
.planning/phases/24.1-session-memory-bundle-naming-and-read-model-facade/24.1-SUMMARY.md:32: new blank line at EOF.
```

### 当前判断 / 根因

新增 summary 文档末尾多留了一个空白行，触发 git whitespace check。

### 已做处理

已删除该 EOF 空白行，文档内容保持不变。

### 剩余问题

无。

### 下次继续排查入口

- `.planning/phases/24.1-session-memory-bundle-naming-and-read-model-facade/24.1-SUMMARY.md`
- `git diff --cached --check`

## 31. 前端定点测试初跑使用错误相对路径导致 Vitest 找不到测试文件

日期：2026-06-21

### 问题现象

在 `frontend/` 工作目录下运行前端定点测试时，命令仍带 `frontend/` 路径前缀，Vitest 没有匹配到测试文件并以 code 1 退出。

### 如何检测 / 复现

在 `/Users/ming/projects/MOCA/frontend` 下运行：

```bash
npm test -- --run frontend/src/hooks/useAgentRun.test.ts frontend/src/lib/api.test.ts
```

### 关键证据或命令

```text
No test files found, exiting with code 1
filter: frontend/src/hooks/useAgentRun.test.ts, frontend/src/lib/api.test.ts
```

### 当前判断 / 根因

命令在 frontend 子目录执行，测试路径应使用 `src/...` 相对路径；带上 `frontend/` 前缀后路径变成不存在的嵌套目录。

### 已做处理

改用正确路径重跑：

```bash
npm test -- --run src/hooks/useAgentRun.test.ts src/lib/api.test.ts
```

结果通过：2 个测试文件、6 个测试全部通过。

### 剩余问题

无。

### 下次继续排查入口

- `frontend/src/hooks/useAgentRun.test.ts`
- `frontend/src/lib/api.test.ts`
- `frontend/package.json`

## 32. study_plan 文档剩余 dirty diff 仅为尾部空格

日期：2026-06-21

### 问题现象

整理剩余工作区时，`study_plan/deep-research-report (1).md` 仍显示 dirty，但 diff 只是在最后一行新增了尾部空格，且无文件内容语义变化。

### 如何检测 / 复现

运行：

```bash
git diff --check -- 'study_plan/deep-research-report (1).md'
```

### 关键证据或命令

```text
study_plan/deep-research-report (1).md:261: trailing whitespace.
```

### 当前判断 / 根因

这是文档尾部 whitespace 噪声，不属于当前后端、前端、Docker 或记忆机制收口范围；直接提交会污染提交边界。

### 已做处理

未纳入本轮提交。保留该工作区变更，等待用户确认是否清理或保留。

### 剩余问题

该文件仍会在 `git status --short` 中显示为 modified。

### 下次继续排查入口

- `study_plan/deep-research-report (1).md`
- `git diff --check -- 'study_plan/deep-research-report (1).md'`

## 28. 宽后端 smoke 初跑暴露旧 direct session memory fixture 与新 bundle fail-closed 语义不一致

日期：2026-06-21

### 问题现象

24.2-24.4 code review 修复后跑宽后端 smoke，出现 2 个失败：

- `tests/agent/test_graph.py::test_same_thread_session_memory_active_slots_feed_investigate`
- `tests/agent/test_session_memory_integration.py::test_extract_slots_loads_agent_runs_prompt_context_from_trusted_config`

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/agent tests/memory tests/conversation tests/test_agent_runs_api.py -q
```

初跑结果：`2 failed, 610 passed, 33 warnings`。

### 关键证据或命令

第一个失败：

```text
KeyError: 'order_id'
tests/agent/test_graph.py:377
```

第二个失败：

```text
calls 包含 max_recent_messages=8，测试仍断言旧的 load_prompt_context 参数集合。
```

### 当前判断 / 根因

第一个失败不是生产回归，而是测试 fixture 仍用 `session=object()` 加 monkeypatch `MemoryService` 来模拟旧的 direct slot-continuity read。24.2 code review 后已改为 bundle fail-closed：没有真实 session identity / bundle path 时不再绕回旧 `MemoryService.load_session_memory`。

第二个失败是 24.2 bundle facade 统一传入 `max_recent_messages=8` 后，旧断言未更新。

### 已做处理

- `tests/agent/test_graph.py` 改为 fake `SessionMemoryBundleService`，并给 fake session 暴露 `execute`，使测试走 bundle read path；
- wrong-thread / stale 参数测试也改为通过 fake bundle 注入 slot continuity，避免“没有读到 memory 所以通过”的假阳性；
- `tests/agent/test_session_memory_integration.py` 更新 `load_prompt_context` 调用断言，包含 `max_recent_messages=8`。

### 剩余问题

无。

### 下次继续排查入口

- `tests/agent/test_graph.py::_session_memory_bundle_service`
- `src/agent/nodes/session_memory_load.py`
- `src/agent/context/session_memory_bundle.py`

### 验证结果

修复后 focused tests：

```bash
uv run pytest tests/agent/test_graph.py::test_same_thread_session_memory_active_slots_feed_investigate tests/agent/test_graph.py::test_wrong_thread_or_stale_session_memory_routes_to_clarification tests/agent/test_session_memory_integration.py::test_extract_slots_loads_agent_runs_prompt_context_from_trusted_config -q
uv run ruff check tests/agent/test_graph.py tests/agent/test_session_memory_integration.py
```

结果：`4 passed, 4 warnings`；ruff 通过。

随后重跑宽后端 smoke：

```bash
uv run pytest tests/agent tests/memory tests/conversation tests/test_agent_runs_api.py -q
```

结果：`612 passed, 33 warnings`。

## 27. Session Memory Bundle 初次补 `tool_name` 时未从 `ToolCallRecord` 关系读取真实工具名

日期：2026-06-21

### 问题现象

24.2-24.4 code review 期间发现 bundle prompt adapter 会从 `prompt_summary` 首词推断 `tool_name`。补字段后，focused 测试失败：`bundle.tool_summaries[0].tool_name` 仍为 `None`，没有保留真实 `get_order`。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/memory/test_session_memory_bundle.py tests/agent/test_nodes/test_generate_recommendation.py -q
```

### 关键证据或命令

失败断言：

```text
assert bundle.tool_summaries[0].tool_name == "get_order"
E       AssertionError: assert None == 'get_order'
```

代码核对显示 `ToolResultRecord` 表没有 `tool_name` 列，真实工具名在关联的 `ToolCallRecord.tool_name`。

### 当前判断 / 根因

初始补丁只尝试从 `ToolResultRecord.tool_name` 读取，但当前数据模型把工具名保存在 `ToolCallRecord`。如果不预加载关系，bundle adapter 会继续退回到从 prompt summary 文本猜工具名，造成 prompt 中 `tool=` 字段不稳定。

### 已做处理

- `ConversationRepository.list_recent_tool_prompt_summaries(...)` 和 summary tool-result 查询增加 `selectinload(ToolResultRecord.tool_call)`；
- `SessionToolSummaryView` 增加可选 `tool_name`；
- `SessionMemoryBundleService` 从 `record.tool_call.tool_name` 投影真实工具名；
- prompt adapter 优先使用 bundle 中的 `tool_name`，仅在缺失时保留原 fallback；
- 测试补充 `tool_name == "get_order"` 和 prompt 中 `tool=get_order` 的断言。

### 剩余问题

无。

### 下次继续排查入口

- `src/conversation/repository.py::list_recent_tool_prompt_summaries`
- `src/memory/session_bundle.py::_tool_summary_views`
- `src/agent/context/session_memory_bundle.py::_tool_prompt_summary_from_bundle`

### 验证结果

修复后：

```bash
uv run pytest tests/memory/test_session_memory_bundle.py tests/agent/test_nodes/test_generate_recommendation.py -q
uv run ruff check src/conversation/repository.py src/agent/context/session_memory_bundle.py src/memory/session_bundle.py src/memory/schemas.py tests/memory/test_session_memory_bundle.py tests/agent/test_nodes/test_generate_recommendation.py
```

结果：`23 passed, 1 warning`；ruff 通过。

## 26. 合并 pytest 中 chat 背景 memory 测试的硬时间阈值产生误报

日期：2026-06-21

### 问题现象

Phase 24.2-24.4 合并相关测试时，`tests/test_agent_runs_api.py::test_chat_memory_write_background_returns_final_response_before_slow_hook` 失败。响应耗时约 0.19s，超过测试写死的 `<0.15s` 阈值。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/test_agent_runs_api.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/memory/test_write_isolation.py tests/agent/test_memory_write_node.py tests/memory/test_memory_eval_mvp.py tests/agent/test_memory_evidence_boundary.py -q
```

### 关键证据或命令

失败断言：

```text
assert (1165396.4678485 - 1165396.277157333) < 0.15
```

同一测试后续状态断言显示 slow hook 已启动但未完成，说明响应没有等待慢 memory hook 完成。

### 当前判断 / 根因

这是测试的硬时间阈值在 full suite 压力下过于脆弱，不是 `/agent/chat` 背景 memory 语义回归。该测试真正要验证的是“响应返回时后台 hook 已启动但还没完成”，已有 `started.is_set()` 和 `not finished.is_set()` 能更稳定表达。

### 已做处理

删除 `<0.15s` 硬时间断言，保留语义断言：

- response status 和 final response 正确；
- memory hook 被调度并启动；
- response 返回时 slow hook 尚未完成。

### 剩余问题

无。

### 下次继续排查入口

- `tests/test_agent_runs_api.py::test_chat_memory_write_background_returns_final_response_before_slow_hook`
- `src/api/routers/agent.py::_schedule_memory_write_after_response`

### 验证结果

修复后合并测试通过：

```bash
uv run pytest tests/test_agent_runs_api.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/memory/test_write_isolation.py tests/agent/test_memory_write_node.py tests/memory/test_memory_eval_mvp.py tests/agent/test_memory_evidence_boundary.py -q
```

结果：初次修复后为 `93 passed, 3 warnings`；轻量复核又补充 bundle 失败回退测试后，最终相关合并测试为 `94 passed, 3 warnings`。

随后范围 ruff 和 diff check 也通过。

## 25. Phase 24.4 初次验证中 `model_copy(update=...)` 未重新验证嵌套 `source_ref`

日期：2026-06-21

### 问题现象

新增 Memory Eval MVP 测试后，`test_memory_eval_tombstoned_long_term_memory_does_not_revive` 失败，`LongTermMemoryService.write_memory(...)` 内部访问 `candidate.source_ref.model_dump(...)` 时发现 `source_ref` 是 dict。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/memory/test_memory_eval_mvp.py tests/agent/test_memory_evidence_boundary.py -q
```

### 关键证据或命令

失败堆栈：

```text
AttributeError: 'dict' object has no attribute 'model_dump'
src/memory/long_term.py:528
```

### 当前判断 / 根因

测试使用 `candidate.model_copy(update={...})` 修改嵌套 `source_ref`；Pydantic 的 `model_copy` 不会对 `update` 的嵌套 dict 重新做模型验证，因此 `source_ref` 从 `MemorySourceRefV1` 变成了裸 dict。这是测试 fixture 构造问题，不是生产代码问题。

### 已做处理

改为通过 `candidate.model_dump(mode="python")` 生成数据、更新字段后再调用 `LongTermMemoryWriteCandidate.model_validate(...)`，确保嵌套 `source_ref` 被重新验证成模型对象。

### 剩余问题

无。

### 下次继续排查入口

- `tests/memory/test_memory_eval_mvp.py`
- `src/memory/long_term.py::_source_ref_json`

### 验证结果

修复后：

```bash
uv run pytest tests/memory/test_memory_eval_mvp.py tests/agent/test_memory_evidence_boundary.py -q
uv run ruff check tests/memory/test_memory_eval_mvp.py
```

均通过。

## 33. 目标架构文档修订验证中发现 Markdown fence 残留与命令 quoting 问题

日期：2026-06-22

### 问题现象

修订 `docs/target-agent-platform-architecture-plan.md` 后做文档一致性检查时，发现 `TrustedContext` 小节在非 canonical 字段表后残留一个多余的三反引号 code fence，会导致后续 Markdown 渲染错位。检查过程中还出现本地验证命令写法问题：`rg` pattern 里误用了 literal `\n`，shell 命令中的反引号被 zsh 当作命令替换，以及 zsh 中使用只读变量名 `status` 导致逐文件 fence 检查失败。

### 如何检测 / 复现

运行关键残留词和 code fence 检查时发现：

```bash
rg -n 'request_id|effective_at|channel|policy_versions|canonical TrustedContext' docs/target-agent-platform-architecture-plan.md
awk '/^```/{c++} END{print c}' docs/target-agent-platform-architecture-plan.md
```

### 关键证据或命令

本地命令曾返回：

```text
rg: the literal "\n" is not allowed in a regex
zsh:1: parse error near `|'
zsh:1: read-only variable: status
```

随后人工查看 `TrustedContext` 片段确认多余 fence。

### 当前判断 / 根因

多余 fence 是文档 patch 时从旧 code block 结构残留的格式错误。`rg` / zsh 报错是验证命令 quoting 和变量命名写法问题，不是仓库代码问题。

### 已做处理

删除了多余 fence，并用单引号重跑关键 `rg` 检查；逐文件 fence 检查改用 `fence_state` 变量名后通过。目标文档当前 code fence 数量为偶数，关键冲突词未再命中。

### 剩余问题

无。

### 下次继续排查入口

- `docs/target-agent-platform-architecture-plan.md` §7.1
- `docs/target-agent-platform-architecture-plan.md` §3.1

### 验证结果

文档一致性检查通过；本次只修改文档，没有修改代码文件。

## 34. GSD init.new-milestone 读取到旧 v1.0/v1.6 元数据

日期：2026-06-22

### 问题现象

启动 v1.9 Agent Platform Foundation 后，`gsd-sdk query init.new-milestone` 仍返回 `current_milestone: v1.0`、`current_milestone_name: milestone`、`latest_completed_milestone: v1.6`。这会误导后续 `$gsd-new-milestone` 或相关初始化流程，尤其是 phase archive path 和当前 milestone 判断。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk query init.new-milestone
gsd-sdk query state.load
gsd-sdk query roadmap.analyze
```

### 关键证据或命令

修复前 `init.new-milestone` 返回旧值：

```text
current_milestone: v1.0
current_milestone_name: milestone
latest_completed_milestone: v1.6
```

`state.load` 同时把当前进度重建成 15 phases / 5 completed phases，说明它把旧 Phase 24.x/25 和新 Phase 26-35 混在同一个当前 milestone 里。

### 当前判断 / 根因

GSD SDK 的 `getMilestoneInfo()` 不识别 ROADMAP 里的 `- [ ] **v1.9 ...**` active milestone 写法，只识别 `🚧 **vX.Y Name**` 或带版本号的 heading；找不到后 fallback 到 ROADMAP 里第一次出现的 `v1.0`。`extractCurrentMilestone()` 还要求当前 milestone 有可匹配的 heading，否则会扫描整个非 details ROADMAP 内容。`latest_completed_milestone` 则来自 `.planning/MILESTONES.md` 顶部第一个 `## vX.Y ... (Shipped:)`，该文件此前最新只到 v1.6。

### 已做处理

- 在 `.planning/ROADMAP.md` 的 v1.9 milestone 行加入 GSD SDK 可识别的 `🚧` marker。
- 为 v1.9 phase 列表增加 `### v1.9 Agent Platform Foundation` heading。
- 把已完成的 Phase 24/24.2/24.3/24.4/25 明细放入 `<details>`，避免 SDK 当前 milestone 扫描误计旧 phase。
- 在 `.planning/MILESTONES.md` 顶部补充 v1.8 和 v1.7 closeout 摘要，使 latest completed milestone 更新到 v1.8。
- 将 v1.9 Phase 26-35 的 `Requirements` / `Success Criteria` 标题统一成 SDK 可解析格式。

### 剩余问题

`gsd-sdk query validate.health` 仍会报告非阻断 warning：当前 `.planning/phases` 里还保留旧 Phase 24/25 目录，而 Phase 26-35 目录尚未创建。这个不影响 `init.new-milestone`、`state.load`、`roadmap.analyze`、`init.plan-phase 26` 的当前 milestone 判断；后续可在 Phase 26 planning 或单独 cleanup/archive 步骤处理。

### 下次继续排查入口

- `.planning/ROADMAP.md`
- `.planning/MILESTONES.md`
- `/opt/homebrew/lib/node_modules/@gsd-build/sdk/dist/query/roadmap.js`
- `/opt/homebrew/lib/node_modules/@gsd-build/sdk/dist/query/init.js`

### 验证结果

修复后：

```text
init.new-milestone: current_milestone=v1.9, latest_completed_milestone=v1.8
state.load: milestone=v1.9, total_phases=10, completed_phases=0
roadmap.analyze: phase_count=10, next_phase=26
init.plan-phase 26: phase_found=true, phase_req_ids=APF-01, APF-02
```

## 35. GSD state.planned-phase 只更新了部分 STATE 元数据

日期：2026-06-22

### 问题现象

Phase 26 plan-checker 通过后运行 `gsd-sdk query state.planned-phase --phase 26 --name "Architecture Contract Baseline" --plans 1`，命令返回 `updated: true`，但 `.planning/STATE.md` 只追加了 `Planned Phase` 记录，正文仍显示 `Plan: not started`、`Current focus` 仍是 ready for planning、Phase 26 表格仍是 `0/1 Pending`。同时 frontmatter 的 `progress.total_plans` 被改成 `1`，与 v1.9 10 个 phase plans 的 milestone 目标不一致。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk query state.planned-phase --phase 26 --name "Architecture Contract Baseline" --plans 1
nl -ba .planning/STATE.md | sed -n '1,160p'
gsd-sdk query state.load
```

### 关键证据或命令

命令返回：

```text
{
  "updated": true,
  "phase": "26",
  "name": "Architecture Contract Baseline",
  "plans": "1"
}
```

但随后 `STATE.md` 中仍能看到：

```text
Plan: not started
| 26. Architecture Contract Baseline | 0/1 | Pending |
- Start Phase 26 planning with GSD plan-phase.
```

### 当前判断 / 根因

`state.planned-phase` 的 writer 只更新了 frontmatter 的部分统计和文件底部 planned marker，没有同步正文里的当前焦点、当前 plan、phase 表格、pending todo 和 session continuity。`progress.total_plans` 也被解释成当前已规划 plan 数，而不是 v1.9 milestone 目标 plan 总数。

### 已做处理

手动修正 `.planning/STATE.md`：保留 v1.9 milestone，恢复 `progress.total_plans: 10`，将 Phase 26 状态更新为 `26-01-PLAN.md ready` / `1/1 planned`，把 pending todo 从“开始 Phase 26 planning”改为“显式请求后执行 Phase 26 plan”，并保留旧 phase 目录归档为独立 cleanup todo。

### 剩余问题

`gsd-sdk query validate.health` 仍会报告非阻断 warning：旧 STATE phase 引用、未来 Phase 27-35 目录未创建、旧 Phase 24/25 summary/archive 状态，以及 Phase 26 在 execute 前没有 SUMMARY。这些不影响 Phase 26 plan ready 状态。

### 下次继续排查入口

- `.planning/STATE.md`
- `/opt/homebrew/lib/node_modules/@gsd-build/sdk/dist/query/state.js`
- `.planning/phases/26-architecture-contract-baseline/26-01-PLAN.md`

### 验证结果

Phase 26 plan-checker 已返回 `## VERIFICATION PASSED`；本次仅修正 `.planning` 元数据，没有修改运行时代码。

## 36. GSD state.begin-phase 参数解析与正文同步错误

日期：2026-06-22

### 问题现象

进入 Phase 26 execute-phase 时按 GSD workflow 文档运行 `gsd-sdk query state.begin-phase --phase 26 --name "Architecture Contract Baseline" --plans 1`，命令返回的 JSON 把 `--phase` 当成 phase 值、把 `26` 当成 name、把 `--name` 当成 plan_count。随后 `.planning/STATE.md` 被写成 `Phase --phase`、`Plan: 1 of --name`、`Current focus: Phase --phase — 26`。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk query state.begin-phase --phase 26 --name "Architecture Contract Baseline" --plans 1
nl -ba .planning/STATE.md | sed -n '1,170p'
gsd-sdk query state.load
```

### 关键证据或命令

命令返回：

```text
{
  "phase": "--phase",
  "name": "26",
  "plan_count": "--name"
}
```

`STATE.md` 同步出现：

```text
Current focus: Phase --phase — 26
Phase: --phase (26) — EXECUTING
Plan: 1 of --name
```

### 当前判断 / 根因

`state.begin-phase` 当前 SDK 接口与 workflow 文档中的 flag 调用格式不一致，实际解析疑似使用 positional 参数。该 writer 还会覆盖 `progress.total_plans`，与 v1.9 milestone 目标 10 个 phase plans 的人工状态不一致。

### 已做处理

手动修正 `.planning/STATE.md`：设置为 Phase 26 Architecture Contract Baseline executing、`Plan: 1 of 1 executing`、Phase 26 表格为 `0/1 executed | Executing`，并恢复 `progress.total_plans: 10`。

### 剩余问题

后续本 session 不再依赖 `state.begin-phase` 自动写正文状态。Phase 执行完成时如果必须调用 GSD completion writer，也需要调用后立即人工核对 `.planning/STATE.md`、`.planning/ROADMAP.md`、`.planning/REQUIREMENTS.md`。

### 下次继续排查入口

- `.planning/STATE.md`
- `/opt/homebrew/lib/node_modules/@gsd-build/sdk/dist/query/state.js`
- `/Users/ming/.codex/get-shit-done/workflows/execute-phase.md`

### 验证结果

本次仅修正 `.planning` 元数据，没有修改运行时代码。

## 37. GSD validate.health 需要通过 query 入口调用

日期：2026-06-22

### 问题现象

Phase 26 收尾验证时直接运行 `gsd-sdk validate.health`，命令失败并提示当前 CLI 只接受 `run`、`auto`、`init`、`query` 等顶层命令。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk validate.health
```

### 关键证据或命令

失败输出提示：

```text
Error: Expected "gsd-sdk run <prompt>", "gsd-sdk auto", "gsd-sdk init [input]", or "gsd-sdk query <command>"
```

随后使用正确入口：

```bash
gsd-sdk query validate.health
```

该命令成功返回 health report。

### 当前判断 / 根因

`validate.health` 是 GSD query handler，不是顶层 CLI command。正确调用格式必须带 `query`。

### 已做处理

改用 `gsd-sdk query validate.health` 重跑验证。结果为 `degraded` 且 `errors: []`，仅剩已知的旧 `STATE.md` phase 引用、Phase 27-35 未来目录未创建、旧 Phase 24/25 summary/archive 状态 warning。

### 剩余问题

无新的 Phase 26 阻断问题。上述 warning 已作为旧 GSD 元数据/未来 phase 目录 caveat 记录在 Phase 26 checklist 和 summary 中。

### 下次继续排查入口

- `.planning/LOCAL-VALIDATION-ISSUES.md`
- `gsd-sdk query validate.health`
- `.planning/phases/26-architecture-contract-baseline/26-BASELINE-CHECKLIST.md`

### 验证结果

本次仅修正文档和 `.planning` 记录，没有修改运行时代码。

## 41. 27-02 额外运行 seam-migration boundary test 仍为预期 RED

日期：2026-06-23

### 问题现象

执行 Phase 27 plan 27-02 时，额外运行了 plan 明确排除的 seam-migration boundary 断言：

```bash
uv run pytest tests/architecture/test_trusted_context_boundaries.py::test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors -q
```

该测试失败，报告当前 search、agent route、graph node、tool executor seam 仍直接构造或未消费 trusted-context projection helpers。

### 如何检测 / 复现

在项目根目录运行上面的 pytest 单测即可复现。

### 关键证据或命令

失败测试为：

```text
tests/architecture/test_trusted_context_boundaries.py::test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors
```

失败首项为 `src/api/routers/search.py does not use trusted-context projection helpers`，并列出多个当前 seam 仍未迁移。

### 当前判断 / 根因

这是 27-02 的已知边界，不是本 plan 的实现失败。27-02 只实现 `TrustedContextFactory`、projection helpers 和 read-only registries；search、agent routes、graph nodes、tool executors 的 seam migration 由 27-03 负责。

### 已做处理

27-02 的 required gates 已通过：

```bash
uv run pytest tests/platform -q
uv run pytest tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py::test_only_platform_module_defines_trusted_context_models tests/architecture/test_trusted_context_boundaries.py::test_prompt_projectors_do_not_import_trusted_context_authority -q
uv run ruff check src/platform src/agent/intent_policy.py tests/platform tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py
```

27-02 summary 会把该 seam-migration RED 明确记录为 27-03 scope。

### 剩余问题

27-03 需要迁移当前 seam 并让 `test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors` 变绿。

### 下次继续排查入口

- `.planning/phases/27-trustedcontextfactory-and-projections/27-03-PLAN.md`
- `tests/architecture/test_trusted_context_boundaries.py`
- `src/api/routers/search.py`
- `src/api/routers/agent.py`
- `src/api/routers/agent_runs.py`
- `src/agent/nodes/investigate.py`
- `src/agent/nodes/action_draft.py`
- `src/tools/executors/knowledge.py`

### 验证结果

本次记录的是 27-03-owned RED test；27-02 required verification 已通过。

## 39. Phase 27 planning 探测命令中的 zsh glob 与缺省 config 噪音

日期：2026-06-22

### 问题现象

为 Phase 27 生成 context 时，两个本地探测命令产生了非阻塞错误输出：

- `ls .planning/phases/27-trustedcontextfactory-and-projections/.continue-here.md .planning/phases/27-trustedcontextfactory-and-projections/*-SPEC.md 2>/dev/null` 在 zsh 下因不存在的 `*-SPEC.md` glob 直接报 `no matches found`。
- 直接运行 `gsd-sdk query config-get context_window`、`workflow.security_enforcement`、`workflow.pattern_mapper` 时返回 `Error: Key not found`。

### 如何检测 / 复现

在 MOCA 项目根目录运行上述命令即可复现。Phase 27 当前没有 phase 目录内的 SPEC 文件，且这些 GSD config key 未显式设置。

### 关键证据或命令

可容错探测命令：

```bash
find .planning/phases/27-trustedcontextfactory-and-projections -maxdepth 1 \( -name '.continue-here.md' -o -name '*-SPEC.md' \) -print 2>/dev/null
```

GSD workflow 原始说明本身也对缺省 config 使用 fallback，例如 `config-get ... 2>/dev/null || echo "true"` 或 `|| echo "200000"`。

### 当前判断 / 根因

这是探测命令写法和未设置 config 的噪音，不是 Phase 27 阻塞问题。zsh 默认会在命令执行前展开 glob，未匹配时直接报错；GSD config key 缺失属于默认配置路径，workflow 应使用 fallback。

### 已做处理

改用 `find` 做 SPEC / handoff 文件探测；对缺省 config 按 workflow 默认值处理：`context_window=200000`、`security_enforcement=true`、`pattern_mapper=true`。

### 剩余问题

无阻塞问题。后续在 zsh 中探测可选文件时应使用 `find`、quoted glob、`noglob` 或 `setopt NULL_GLOB`，不要直接把可选 glob 传给命令。

### 下次继续排查入口

- `$HOME/.codex/get-shit-done/workflows/discuss-phase.md`
- `$HOME/.codex/get-shit-done/workflows/plan-phase.md`
- `.planning/phases/27-trustedcontextfactory-and-projections/`

### 验证结果

本次仅新增 Phase 27 planning artifacts 和本地验证问题记录，没有修改运行时代码。

## 40. plan-phase UI gate 正则会被 Requirements 误触发

日期：2026-06-22

### 问题现象

执行 Phase 27 planning gate 预检时，workflow 中的 UI 检测正则包含裸 `UI`：

```bash
grep -iE "UI|interface|frontend|component|layout|page|screen|view|form|dashboard|widget"
```

Phase 27 是后端/平台契约 phase，但 `ROADMAP.md` phase section 里的 `Requirements` 含有连续字母 `ui`，导致正则误判为 UI phase。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk query roadmap.get-phase 27 | rg -i "UI|interface|frontend|component|layout|page|screen|view|form|dashboard|widget"
```

该命令会输出整段 Phase 27 JSON section，即使 phase 本身没有 frontend/UI 工作。

### 关键证据或命令

Phase 27 的 roadmap scope 是 `TrustedContextFactory and Projections`，目标是 canonical trusted identity/scope/run context 和服务 projection；没有 frontend、screen、component 或 layout 交付。

### 当前判断 / 根因

UI gate 使用裸 `UI` 子串匹配，大小写不敏感时会匹配 `Requirements` 这类普通英文词。这个 gate 应该使用词边界或更明确的 frontend 语义，例如 `\bUI\b|frontend|component|layout|page|screen|view|form|dashboard|widget`，并避免对 JSON key/value 整段做过宽匹配。

### 已做处理

本次 Phase 27 planning 将该命中视为误报，按非 UI phase 继续，不要求生成 `UI-SPEC.md`。

### 剩余问题

GSD workflow 源文件仍有误触发风险；后续可在 GSD 工具层修正正则。

### 下次继续排查入口

- `$HOME/.codex/get-shit-done/workflows/plan-phase.md`
- `.planning/ROADMAP.md` Phase 27

### 验证结果

本次仅新增 Phase 27 planning artifacts 和本地验证问题记录，没有修改运行时代码。

## 39. GSD state.load 输出与 STATE.md frontmatter 不一致

日期：2026-06-22

### 问题现象

Phase 26 external review warning 修复后，`.planning/STATE.md` frontmatter 明确写着 v1.9 有 10 个 phase、10 个 plans、已完成 1 个 phase / 1 个 plan、进度 10%。但 `gsd-sdk query state.load` 输出把 `total_plans` 解析为 1、`percent` 解析为 100，并把 `status` 显示为 `planning`。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
nl -ba .planning/STATE.md | sed -n '1,75p'
gsd-sdk query state.load
```

### 关键证据或命令

`.planning/STATE.md` 当前 frontmatter：

```text
status: ready_for_phase_27
progress:
  total_phases: 10
  completed_phases: 1
  total_plans: 10
  completed_plans: 1
  percent: 10
```

`state.load` 输出：

```text
"status": "planning"
"total_plans": 1
"completed_plans": 1
"percent": 100
```

### 当前判断 / 根因

`state.load` 当前 parser/normalizer 仍会根据 Phase 26 plan index 或内部状态重新解释 plan 统计，而不是忠实读取 `.planning/STATE.md` frontmatter。该问题与之前记录的 `state.planned-phase` / `state.begin-phase` writer 行为同类，属于 GSD metadata query caveat。

### 已做处理

确认 `state.load` 没有改写 `.planning/STATE.md` 文件本身；以文件内容作为本次状态权威。`roadmap.analyze --pick next_phase` 正确返回 `"27"`，`phase-plan-index 26` 显示 26-01 有 summary 且 incomplete 为空。

### 剩余问题

`gsd-sdk query validate.health` 仍会因 STATE 里引用 Phase 27、ROADMAP 中 Phase 27-35 目录尚未创建、旧 Phase 24/25 summary/archive 状态而返回 `degraded`。这些不阻塞 Phase 27 planning。

### 下次继续排查入口

- `.planning/STATE.md`
- `gsd-sdk query state.load`
- `gsd-sdk query roadmap.analyze --pick next_phase`

### 验证结果

本次仅修正文档和 `.planning` 记录，没有修改运行时代码。

## 40. Phase 27 复现 GSD state.begin-phase 参数解析与统计覆盖问题

日期：2026-06-23

### 问题现象

执行 Phase 27 `gsd-execute-phase` 初始化时，按 workflow 文档运行 `gsd-sdk query state.begin-phase --phase "27" --name "trustedcontextfactory-and-projections" --plans "3"` 后，SDK 将 flag token 当作 positional 值解析，导致 `.planning/STATE.md` 一度出现 `Phase --phase`、`Plan: 1 of --name`。随后改用 positional 调用 `gsd-sdk query state.begin-phase 27 trustedcontextfactory-and-projections 3` 后，phase/name 被部分修正，但 `progress.total_plans` 被覆盖为 `4`、`percent` 被覆盖为 `25`，与 v1.9 里程碑 10 个 phase plans / 10% 进度不一致。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk query state.begin-phase --phase "27" --name "trustedcontextfactory-and-projections" --plans "3"
gsd-sdk query state.begin-phase 27 trustedcontextfactory-and-projections 3
git diff -- .planning/STATE.md
```

### 关键证据或命令

`git diff -- .planning/STATE.md` 显示 `status` 进入 executing 后，正文和 frontmatter 曾被写成错误 phase 或错误统计：

```text
Current focus: Phase --phase - 27
Phase: --phase (27) - EXECUTING
Plan: 1 of --name
total_plans: 4
percent: 25
```

### 当前判断 / 根因

`execute-phase.md` 中 documented flag syntax 与当前 `gsd-sdk query state.begin-phase` 实际 parser 不一致；positional 形式也会按当前 phase plan 数覆盖 milestone 级进度统计，不能作为 MOCA v1.9 的权威状态写入器直接信任。

### 已做处理

手动修正 `.planning/STATE.md`，保留 Phase 27 正在执行状态，但恢复 v1.9 里程碑统计为 `total_plans: 10`、`completed_plans: 1`、`percent: 10`，并将 Current Position 改为 `Phase 27 - TrustedContextFactory and Projections`、`Plan: 0 of 3 planned`。

### 剩余问题

本 session 后续不再依赖 `state.begin-phase` 自动写正文状态。Phase 完成阶段如果必须调用 `phase.complete` 或其他 GSD writer，需要调用后立即核对 `.planning/STATE.md`、`.planning/ROADMAP.md`、`.planning/REQUIREMENTS.md`。

### 下次继续排查入口

- `.planning/STATE.md`
- `gsd-sdk query state.begin-phase`
- `/Users/ming/.codex/get-shit-done/workflows/execute-phase.md`

### 验证结果

本次仅修正 GSD 状态文档和本地验证问题记录，尚未修改运行时代码。

## 41. Phase 27 regression gate 暴露旧 graph 测试缺少 trusted_context

日期：2026-06-23

### 问题现象

Phase 27 code review fix 后执行 prior Phase 24 regression command 时，`tests/agent/test_session_memory_integration.py` 有 4 个用例失败。失败共同点是 `active_slots` 已正确解析，但 `business_context.facts.order` 缺失，说明 graph 没有执行 `get_order` 工具。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py tests/agent/context/test_assembler.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q
```

### 关键证据或命令

失败用例：

```text
tests/agent/test_session_memory_integration.py::test_same_thread_vague_turn_inherits_session_order_and_reruns_investigation
tests/agent/test_session_memory_integration.py::test_agent_runs_session_slots_explicit_current_turn_overrides_inherited
tests/agent/test_session_memory_integration.py::test_next_step_followup_reuses_prior_order_status_memory_instead_of_action_type_clarification
tests/agent/test_session_memory_integration.py::test_unresolved_question_carryover_keeps_current_turn_slot_authoritative
```

共同失败断言：

```text
KeyError: 'order'
assert final_state["business_context"]["facts"]["order"]["order_no"] == ...
```

### 当前判断 / 根因

Phase 27 后 `investigate` 正确要求 `configurable["trusted_context"]` 才能执行工具，并在缺失时 fail closed。生产 route 已通过 `TrustedContextFactory` 注入 canonical `trusted_context`，但旧的低层 graph 测试 helper `tests/agent/test_graph.py::_config` 仍只传 legacy `permissions` / `merchant_scope` / `trace_id`，没有传 canonical `trusted_context`。因此这些复用 `_config` 的 session memory 集成测试走到 `investigate` 后被 fail closed。

### 已做处理

修复 `tests/agent/test_graph.py::_config`：构造 canonical `TrustedContext` 并写入 `configurable["trusted_context"]`，同时保留 legacy compatibility fields。没有放宽生产 fail-closed 行为。

### 剩余问题

当前只确认 4 个失败用例已恢复通过；完整 prior-phase regression command 需要重跑并确认。

### 下次继续排查入口

- `tests/agent/test_graph.py::_config`
- `src/agent/nodes/investigate.py::_trusted_context_from_config`
- `tests/agent/test_session_memory_integration.py`

### 验证结果

已重跑失败用例：

```bash
uv run pytest tests/agent/test_session_memory_integration.py::test_same_thread_vague_turn_inherits_session_order_and_reruns_investigation tests/agent/test_session_memory_integration.py::test_agent_runs_session_slots_explicit_current_turn_overrides_inherited tests/agent/test_session_memory_integration.py::test_next_step_followup_reuses_prior_order_status_memory_instead_of_action_type_clarification tests/agent/test_session_memory_integration.py::test_unresolved_question_carryover_keeps_current_turn_slot_authoritative -q
```

结果：`4 passed, 5 warnings`。

## 42. Phase 27 verifier subagent 因 Codex 用量限制中断

日期：2026-06-23

### 问题现象

Phase 27 执行到 phase goal verification gate 时，已启动的 `gsd-verifier` subagent 在写出 `27-VERIFICATION.md` 前失败，返回 Codex usage limit 错误。

### 如何检测 / 复现

在 Phase 27 完成 plans、code review fix、regression gates 后启动 `gsd-verifier`：

```text
Verify Phase 27 goal achievement...
verification_path: .planning/phases/27-trustedcontextfactory-and-projections/27-VERIFICATION.md
```

### 关键证据或命令

subagent notification 返回：

```text
You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at 2:26 AM.
```

随后检查 artifact：

```bash
test -f .planning/phases/27-trustedcontextfactory-and-projections/27-VERIFICATION.md && sed -n '1,220p' .planning/phases/27-trustedcontextfactory-and-projections/27-VERIFICATION.md || echo NO_VERIFICATION
```

结果：`NO_VERIFICATION`。

### 当前判断 / 根因

这是外部 Codex usage quota / runtime 限制，不是 Phase 27 代码或测试失败。由于所有 plan summary、key-link、schema drift、code review fix、focused gates 和 prior regression gates 已完成，可由 orchestrator 根据已验证证据补齐 verification artifact。

### 已做处理

关闭失败的 verifier agent 后，由 orchestrator inline 生成 `.planning/phases/27-trustedcontextfactory-and-projections/27-VERIFICATION.md`，并在报告中明确记录 `gsd-verifier` usage-limit fallback。验证结论基于已执行通过的命令和 committed artifacts。

### 剩余问题

无代码阻塞。若需要原生 verifier agent 的独立文本，可在用量恢复后重新运行 `$gsd-verify-work 27` 或对应 verifier workflow 复核。

### 下次继续排查入口

- `.planning/phases/27-trustedcontextfactory-and-projections/27-VERIFICATION.md`
- `.planning/phases/27-trustedcontextfactory-and-projections/27-REVIEW.md`
- `.planning/phases/27-trustedcontextfactory-and-projections/27-REVIEW-FIX.md`

### 验证结果

Inline verification artifact 已生成，状态为 `passed`，并列出 APF-03/APF-04、code review fix、focused regression、prior regression、key-link、schema drift 证据。

## 43. Phase 27 phase.complete 后 STATE.md 统计和正文不同步

日期：2026-06-23

### 问题现象

Phase 27 verification 通过后执行 `gsd-sdk query phase.complete 27`，命令返回 `roadmap_updated: true`、`state_updated: true`、`requirements_updated: true` 且无 warnings。但 `.planning/STATE.md` 被写成不一致状态：frontmatter `completed_phases` 变成 `3`，`percent` 变成 `30`，正文 Current focus 仍写 Phase 27 execution in progress，Performance Metrics 表中 Phase 27 仍是 `2/3 | In Progress`。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk query phase.complete 27
git diff -- .planning/STATE.md .planning/ROADMAP.md .planning/REQUIREMENTS.md
sed -n '1,75p' .planning/STATE.md
```

### 关键证据或命令

`phase.complete` 返回：

```json
{
  "completed_phase": "27",
  "plans_executed": "3/3",
  "next_phase": "28",
  "roadmap_updated": true,
  "state_updated": true,
  "requirements_updated": true,
  "warnings": []
}
```

但 `.planning/STATE.md` 显示：

```text
completed_phases: 3
percent: 30
Current focus: ... Phase 27 execution in progress
| 27. TrustedContextFactory and Projections | 2/3 | In Progress |
```

### 当前判断 / 根因

`phase.complete` writer 同时混用了 phase-count 和 plan-count 统计语义，并且正文表格没有同步到 Phase 27 的 3/3 complete。该问题与此前 `state.begin-phase`、`state.load` 的 GSD state writer/parser drift 同类。

### 已做处理

手动修正 `.planning/STATE.md`：

- `completed_phases: 2`（v1.9 当前完成 Phase 26 和 Phase 27）
- `completed_plans: 4`（Phase 26 的 1 个 plan + Phase 27 的 3 个 plans）
- `percent: 40`（按当前 STATE 的 plan-count 进度语义）
- Current focus 改为 Phase 28 planning ready
- Current Position 改为 `Phase: 28 - Decision Event Foundation`
- Performance Metrics 中 Phase 27 改为 `3/3 complete | Complete`

### 剩余问题

后续调用 GSD phase/state writer 后仍需人工核对 `.planning/STATE.md` frontmatter 和正文表格。`phase.complete` 对 ROADMAP/REQUIREMENTS 的更新本次看起来正确。

### 下次继续排查入口

- `.planning/STATE.md`
- `gsd-sdk query phase.complete 27`
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`

### 验证结果

修正后 `.planning/STATE.md` 指向 Phase 28 planning ready，并保留 v1.9 10 plans / 4 completed plans / 40% 进度语义。

## 38. Markdown 围栏 parity 检查需要只统计行首围栏

日期：2026-06-22

### 问题现象

Phase 26 最终验证时使用 `rg -o '```'` 统计 Markdown 代码围栏，`.planning/LOCAL-VALIDATION-ISSUES.md` 被误报为奇数围栏。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
rg -o '```' .planning/LOCAL-VALIDATION-ISSUES.md | wc -l
```

该命令会把正文或命令片段里的三反引号也计入，不等价于 Markdown fenced code block 计数。

### 关键证据或命令

用行首规则检查：

```bash
rg -n '^```' .planning/LOCAL-VALIDATION-ISSUES.md
```

结果显示行首围栏为偶数；非行首命中来自历史记录中的检查命令文本：

```text
awk '/^```/{c++} END{print c}' docs/target-agent-platform-architecture-plan.md
```

### 当前判断 / 根因

`rg -o '```'` 适合查找所有三反引号片段，不适合做 Markdown fence parity。正确检查应只统计以三反引号开头的围栏行。

### 已做处理

改用行首围栏规则重跑所有相关 Markdown 文件：

```bash
for f in docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline/26-BASELINE-CHECKLIST.md .planning/phases/26-architecture-contract-baseline/26-01-SUMMARY.md .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md .planning/LOCAL-VALIDATION-ISSUES.md; do n=$(rg -n '^```' "$f" | wc -l | tr -d ' '); if [ $((n % 2)) -ne 0 ]; then echo "$f has odd line-start fence count: $n"; exit 1; fi; done
```

检查通过。

### 剩余问题

无。后续做 Markdown 围栏 parity 验证时应使用行首规则。

### 下次继续排查入口

- `.planning/LOCAL-VALIDATION-ISSUES.md`
- `.planning/phases/26-architecture-contract-baseline/26-BASELINE-CHECKLIST.md`

### 验证结果

本次仅修正文档和 `.planning` 记录，没有修改运行时代码。

## 44. Phase 27 收尾检查中裸 zsh glob 导致可选上下文检查失败

日期：2026-06-23

### 问题现象

Phase 27 收尾 sanity check 中尝试检查 Phase 28 是否已有 `28-CONTEXT.md`，命令使用了裸 glob：

```bash
ls .planning/phases/*28*/28-CONTEXT.md 2>/dev/null || true
```

在 zsh 下，glob 没有匹配时会先触发 `no matches found`，不会进入 `ls` 或后续 `|| true`，导致该并行检查返回失败。

### 如何检测 / 复现

在 MOCA 项目根目录运行上述命令，如果当前没有匹配的 `28-CONTEXT.md`，zsh 会输出：

```text
zsh:1: no matches found: .planning/phases/*28*/28-CONTEXT.md
```

### 关键证据或命令

失败输出来自 Phase 27 最终 sanity check 的可选上下文探测。改用不依赖 shell glob 展开的 `find` 重跑：

```bash
find .planning/phases -path '*/28-CONTEXT.md' -print
```

该命令正常返回空输出，表示当前没有 Phase 28 context 文件。

### 当前判断 / 根因

这是验证命令写法问题，不是 Phase 27 实现或 GSD 状态问题。zsh 的默认 `nomatch` 行为会在命令执行前拦截未匹配的 glob。

### 已做处理

已用 `find` 替代裸 glob 完成检查，确认当前仓库没有 `28-CONTEXT.md`。

### 剩余问题

无。后续可选文件检查避免在 zsh 中使用未保护的裸 glob。

### 下次继续排查入口

- `.planning/phases/`
- `.planning/phases/27-trustedcontextfactory-and-projections/27-VERIFICATION.md`

### 验证结果

该问题只影响收尾检查命令本身。Phase 27 已完成的验证、测试、ROADMAP / REQUIREMENTS / STATE 结论不受影响。

## 45. `gsd-sdk query state.json` 的 progress 口径与 STATE.md 里程碑口径不一致

日期：2026-06-23

### 问题现象

Phase 27 完成后为判断下一步执行 `gsd-sdk query state.json`，输出的 `stopped_at` 曾读取到 `STATE.md` Session Continuity 的旧断点，且 `progress.total_plans/completed_plans/percent` 显示为 `4/4/100%`。这与 `STATE.md` frontmatter 和正文中 v1.9 里程碑口径的 `10/4/40%` 不一致。

### 如何检测 / 复现

在 MOCA 项目根目录运行：

```bash
gsd-sdk query state.json
sed -n '1,35p' .planning/STATE.md
sed -n '138,146p' .planning/STATE.md
```

### 关键证据或命令

`STATE.md` frontmatter 和正文显示：

```text
status: ready_to_plan
stopped_at: Phase 27 verified and complete; Phase 28 planning ready
total_plans: 10
completed_plans: 4
percent: 40
```

但 `gsd-sdk query state.json` 仍显示：

```json
{
  "status": "planning",
  "progress": {
    "total_plans": 4,
    "completed_plans": 4,
    "percent": 100
  }
}
```

### 当前判断 / 根因

`state.json` 的 progress 看起来按当前已存在/已执行 plan 文件统计，而不是按 v1.9 milestone 的目标 10 个 phase plans 统计；同时它会读取 `STATE.md` 的 Session Continuity 断点文本。前者是口径差异，后者是本地 STATE 正文残留。

### 已做处理

已修正 `.planning/STATE.md` 的 Session Continuity：

```text
Stopped at: Phase 27 verified and complete; Phase 28 planning ready
```

修正后 `state.json` 的 `stopped_at` 已同步为 Phase 28 ready，但 progress 仍保持 `4/4/100%` 口径。

### 剩余问题

后续判断 Phase 28 下一步时不要只看 `gsd-sdk query state.json` 的 `percent`。以 `.planning/STATE.md`、`.planning/ROADMAP.md`、实际 phase 目录和 plan/summary 文件为准。

### 下次继续排查入口

- `.planning/STATE.md`
- `.planning/ROADMAP.md`
- `gsd-sdk query state.json`
- `$gsd-next`

### 验证结果

`STATE.md` 已明确指向 Phase 28 planning ready；该问题不改变 Phase 27 已完成结论，但会影响自动 next 路由时展示的 progress 解释。

## 46. 手工 code review API 测试初跑使用了不存在的 pytest 节点名

日期：2026-06-23

### 问题现象

手工 code review 阶段，为覆盖 Phase 27 API 入口尝试运行一个混合 pytest 命令，其中两个 `tests/test_approval_api.py` 节点名写错，pytest 以 `not found` 退出：

```text
ERROR: not found: /Users/ming/projects/MOCA/tests/test_approval_api.py::test_decide_approval_persists_decision_and_resumes_graph
ERROR: not found: /Users/ming/projects/MOCA/tests/test_approval_api.py::test_reject_decision_resumes_graph_without_action_permission
```

### 如何检测 / 复现

运行包含上述两个节点名的 pytest 命令即可复现。pytest 没有执行目标测试用例，退出码为 4。

### 关键证据或命令

用 `rg` 查到真实测试名：

```bash
rg -n "async def test_.*resume|async def test_.*decision|without_action_permission|permissions\\] == \\[\\]" tests/test_approval_api.py
```

真实节点为：

```text
tests/test_approval_api.py::test_decide_approve_builds_command_from_authenticated_actor_and_resumes_with_service_payload
tests/test_approval_api.py::test_decide_reject_resumes_graph_with_trusted_rejected_result
```

### 当前判断 / 根因

这是手工验证命令的 pytest 节点名错误，不是代码回归。

### 已做处理

已用真实节点名重跑同一组入口测试：

```bash
uv run pytest tests/test_search_integration.py tests/test_agent_runs_api.py::test_agent_chat_only_token_invokes_legacy_chat_with_no_tool_permissions tests/test_agent_runs_api.py::test_agent_run_stream_graph_config_contains_canonical_trusted_context tests/test_approval_api.py::test_decide_approve_builds_command_from_authenticated_actor_and_resumes_with_service_payload tests/test_approval_api.py::test_decide_reject_resumes_graph_with_trusted_rejected_result -q
```

结果为 `10 passed, 1 warning`。

### 剩余问题

无。后续手工挑选 pytest 节点时先用 `rg -n "def test_"` 确认真实函数名。

### 下次继续排查入口

- `tests/test_approval_api.py`
- `tests/test_agent_runs_api.py`
- `tests/test_search_integration.py`

### 验证结果

修正后的 API 入口测试集合通过。该问题只影响本次手工 code review 验证命令，不影响 Phase 27 代码结论。

## 47. 并行启动多个 pytest 进程会争用同一 Postgres 测试 schema

日期：2026-06-23

### 问题现象

修复 Phase 27 手工 code review 问题时，同时并行启动了三个独立 `uv run pytest ...` 进程。legacy chat 单测在 fixture 建表阶段失败，报 PostgreSQL type/table 名称冲突：

```text
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "pg_type_typname_nsp_index"
DETAIL: Key (typname, typnamespace)=(tenants, ...) already exists.
```

### 如何检测 / 复现

同时启动多个会执行 `Base.metadata.create_all` 的 pytest 进程，且它们复用同一测试数据库/schema 时，可能复现该错误。

### 关键证据或命令

失败发生在 `tests/conftest.py` 的 `Base.metadata.create_all` setup 阶段，不是测试断言阶段。将同一测试串行重跑：

```bash
uv run pytest tests/test_agent_runs_api.py::test_agent_chat_persists_trusted_run_id_when_graph_returns_stale_current_run_id -q
```

结果为 `1 passed, 1 warning`。

### 当前判断 / 根因

这是本地验证并发方式问题。多个 pytest 进程同时创建同一批 SQLAlchemy metadata，Postgres catalog 上出现建表/类型竞争。

### 已做处理

改为串行重跑受影响测试，确认测试通过。

### 剩余问题

无。后续涉及数据库建表 fixture 的 pytest 命令不要用多个独立进程并行跑；可以串行运行，或使用 pytest 自身隔离好的并发机制。

### 下次继续排查入口

- `tests/conftest.py`
- `Base.metadata.create_all`
- `tests/test_agent_runs_api.py::test_agent_chat_persists_trusted_run_id_when_graph_returns_stale_current_run_id`

### 验证结果

串行重跑通过。该问题只影响本地验证方式，不影响本次代码修复结论。

## 48. 裸 pytest 命中系统 Python 3.9 导致 datetime.UTC ImportError

日期：2026-06-23

### 问题现象

验证 Search API Trusted Context Boundary 时，直接运行 `pytest ...` 没有进入项目虚拟环境，而是命中系统旧 Python 3.9，加载 `tests/conftest.py` 失败：

```text
ImportError: cannot import name 'UTC' from 'datetime' (/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/datetime.py)
```

### 如何检测 / 复现

在当前 shell 直接运行：

```bash
pytest tests/test_search_integration.py::test_search_uses_factory_projected_knowledge_context_and_rejects_request_identity_override -q
```

可能复现该错误，具体取决于 PATH 中 `pytest` 指向哪个解释器。

### 关键证据或命令

项目配置要求 Python 3.12 以上：

```text
pyproject.toml: requires-python = ">=3.12"
.python-version: 3.12
Makefile: uv run pytest
```

直接运行 `pytest` 时，trace 指向系统 Python 3.9；改用项目入口后命令通过：

```bash
uv run pytest tests/test_search_integration.py::test_search_uses_factory_projected_knowledge_context_and_rejects_request_identity_override tests/test_search_integration.py::test_search_returns_api_response tests/test_search_integration.py::test_search_tenant_isolation tests/architecture/test_trusted_context_boundaries.py -q
```

结果为 `7 passed, 1 warning`。

### 当前判断 / 根因

这是本地验证入口问题，不是业务代码回归。裸 `pytest` 使用了不满足项目要求的系统 Python 3.9；`datetime.UTC` 从 Python 3.11 起可用，项目本身要求 Python 3.12。

### 已做处理

改用 `uv run pytest` 重跑 Search API trusted context boundary 相关测试，确认通过。

### 剩余问题

无。后续 MOCA 本地验证默认使用 `uv run pytest ...` 或 `.venv/bin/pytest ...`，不要用裸 `pytest`。

### 下次继续排查入口

- `pyproject.toml`
- `.python-version`
- `Makefile`
- `tests/conftest.py`

### 验证结果

修正验证入口后，Search API trusted context boundary 相关测试通过。该问题只影响本地命令选择，不影响 checkpoint 结论。

## 49. 直接 python 临时脚本导入测试 helper 时触发 conversation/memory 循环导入

日期：2026-06-23

### 问题现象

验证 Tool Nodes trusted context boundary 时，使用 `uv run python -` 直接导入 `tests.agent.test_nodes.test_investigate` helper，触发循环导入：

```text
ImportError: cannot import name 'ConversationService' from partially initialized module 'src.conversation.service'
```

### 如何检测 / 复现

运行临时脚本，直接从测试模块导入 helper：

```bash
uv run python - <<'PY'
from tests.agent.test_nodes.test_investigate import _state
PY
```

在当前导入顺序下可能复现。

### 关键证据或命令

失败链路为：

```text
src.agent.nodes.investigate
-> src.conversation.repository
-> src.conversation.service
-> src.tools.contracts
-> src.tools.__init__
-> src.tools.manager
-> src.tools.executors.memory
-> src.memory.session_bundle
-> src.conversation.service partially initialized
```

同一测试通过 `uv run pytest ...` 正常执行；临时脚本改为先导入 `src.tools.manager` 后也可正常运行。

### 当前判断 / 根因

这是临时验证脚本的导入顺序问题，不是本次 checkpoint 的业务断言失败。`src.tools.__init__` eager import `UnifiedToolManager`，在直接脚本路径下更容易暴露 conversation/memory 的循环导入。

### 已做处理

改用项目 pytest 入口验证正式测试，并在临时脚本中先导入 `src.tools.manager` 后重跑 missing trusted context 分支：

```text
investigate_termination unrecoverable_error
investigate_error MISSING_TRUSTED_CONTEXT
investigate_manager_calls 0
action_draft_error MISSING_TRUSTED_CONTEXT
```

### 剩余问题

无。后续临时脚本不要直接导入测试 helper 作为首个 import；优先使用 `uv run pytest`，或先导入稳定入口规避导入顺序影响。

### 下次继续排查入口

- `src/tools/__init__.py`
- `src/conversation/service.py`
- `src/memory/session_bundle.py`
- `tests/agent/test_nodes/test_investigate.py`

### 验证结果

正式 pytest 验证和修正后的临时函数级验证均通过。该问题只影响临时验证脚本导入方式，不影响 checkpoint 结论。

## 50. `gsd-sdk query state.planned-phase` 更新 Phase 28 时误改 STATE 汇总指标

日期：2026-06-23

### 问题现象

Phase 28 PLAN 写完后，运行 `gsd-sdk query state.planned-phase --phase 28 --name "Decision Event Foundation" --plans 1` 虽然追加了 Planned Phase 记录，但同时把 `.planning/STATE.md` frontmatter 中的汇总指标改成不符合当前 v1.9 状态的值：`completed_phases: 2`、`total_plans: 5`、`percent: 80`，并把 `last_activity` 回退成 Phase 27 UAT。

### 如何检测 / 复现

运行命令后检查 state diff：

```bash
gsd-sdk query state.planned-phase --phase 28 --name "Decision Event Foundation" --plans 1
git diff -- .planning/STATE.md
```

### 关键证据或命令

`git diff -- .planning/STATE.md` 显示 `completed_phases` 从 3 变成 2，`total_plans` 从 10 变成 5，`percent` 从 30 变成 80，且 `last_activity` 不是 Phase 28 planned。

### 当前判断 / 根因

这是 GSD state writer 在 planned-phase 路径下重新计算汇总指标时的本地元数据漂移问题，类似 Phase 26 记录过的 state writer 输出问题。它不影响 Phase 28 PLAN 文件本身，但如果不修正会误导后续进度判断。

### 已做处理

手动把 `.planning/STATE.md` frontmatter 汇总指标恢复为命令前的值，并只保留 Phase 28 已计划的真实状态：`status: ready_to_execute`、`stopped_at: Phase 28 planned`、`last_activity: 2026-06-23 -- Phase 28 planned`、`Plan: 28-01 planned`。

### 剩余问题

未修复 `gsd-sdk` 本身。后续再次运行 `state.planned-phase` 后需要检查 `.planning/STATE.md` diff，确认汇总指标未漂移。

### 下次继续排查入口

- `gsd-sdk query state.planned-phase`
- `.planning/STATE.md`
- Phase 26 的 `state.begin-phase` 本地记录

### 验证结果

Phase 28 PLAN 的 `frontmatter.validate` 和 `verify.plan-structure` 均通过；STATE 已恢复为 Phase 28 ready-to-execute 的一致状态。

## 51. Phase 28 RED 测试文件误留下 patch 标记导致 pytest 语法错误

日期：2026-06-23

### 问题现象

新增 `tests/replay/test_decision_events.py` 后运行 RED gate，pytest 在 collection 阶段失败，报 `SyntaxError: invalid syntax`，位置是文件末尾的 `*** End Patch`。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/replay/test_decision_events.py -q
```

### 关键证据或命令

pytest 输出显示：

```text
File "/Users/ming/projects/MOCA/tests/replay/test_decision_events.py", line 414
  *** End Patch
  ^^
SyntaxError: invalid syntax
```

### 当前判断 / 根因

这是手工 `apply_patch` 时把补丁结束标记误写入测试文件内容导致的本地编辑污染，不是 Phase 28 契约测试预期失败。

### 已做处理

删除文件末尾的 `*** End Patch` 标记，并准备重跑 RED gate，确认失败原因回到缺少计划中的 `src.replay.decision_events` 模块或符号。

### 剩余问题

无。后续新增大文件后先用 `tail` 或 pytest collection 快速确认没有补丁标记残留。

### 下次继续排查入口

- `tests/replay/test_decision_events.py`
- Phase 28 Task 1 RED gate

## 52. 并行运行共享 PostgreSQL test DB 的 pytest suites 导致 create_all 冲突

日期：2026-06-23

### 问题现象

Phase 28 Task 3 验证时，将两条都会使用 `tests/conftest.py::test_engine` 的 pytest 命令并行执行，两个进程同时 drop/create `moca_test` schema，导致 PostgreSQL 报 `duplicate key value violates unique constraint "pg_type_typname_nsp_index"`。

### 如何检测 / 复现

同时运行以下两条命令即可复现：

```bash
uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py tests/agent/test_memory_write_node.py -q
uv run pytest tests/replay/test_sequence_allocator.py tests/platform/test_context_projections.py -q
```

### 关键证据或命令

pytest setup 阶段失败在 `tests/conftest.py:72` 的 `Base.metadata.create_all`，PostgreSQL 错误为：

```text
UniqueViolationError: duplicate key value violates unique constraint "pg_type_typname_nsp_index"
DETAIL: Key (typname, typnamespace)=(tenants, ...) already exists.
```

### 当前判断 / 根因

这是验证命令调度问题，不是 Phase 28 代码问题。两个 pytest 进程共享同一个 `moca_test` 数据库，而 test fixture 每个进程都会 drop/create 全量 metadata，不能并行跑。

### 已做处理

改为顺序运行两组 targeted suites：

```bash
uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py tests/agent/test_memory_write_node.py -q
uv run pytest tests/replay/test_sequence_allocator.py tests/platform/test_context_projections.py -q
```

顺序执行后分别通过：第一组 `73 passed`，第二组 `11 passed`。

### 剩余问题

无。后续可以并行 `rg`/`sed` 等只读命令，但不要并行运行会重建共享 PostgreSQL test DB 的 pytest 进程。

### 下次继续排查入口

- `tests/conftest.py::test_engine`
- Phase 28 targeted pytest commands

## 53. PLAN key_links pattern 带字面单引号导致 verify.key-links 误报 0/4

日期：2026-06-23

### 问题现象

Phase 28 phase-goal verification 时运行 `gsd-sdk query verify.key-links .planning/phases/28-decision-event-foundation/28-01-PLAN.md`，工具返回 `all_verified: false`，4 条 key link 全部未找到。

### 如何检测 / 复现

运行：

```bash
gsd-sdk query verify.key-links .planning/phases/28-decision-event-foundation/28-01-PLAN.md
```

### 关键证据或命令

失败输出里的 pattern 包含字面单引号，例如：

```text
Pattern "'ReplayService\\(session\\)\\.append_event'" not found
```

而源码实际存在 `ReplayService(session).append_event`、`DecisionEventEnvelopeV1.model_validate`、`emit_decision_event` 和 `guard_resource_refs(resource_refs)`。

### 当前判断 / 根因

PLAN frontmatter 中 `key_links.pattern` 使用了单引号包裹 regex，当前 `verify.key-links` 工具没有按 YAML 语义剥离这些单引号，而是把单引号当成 regex 内容，导致误报。

### 已做处理

把 `.planning/phases/28-decision-event-foundation/28-01-PLAN.md` 中 4 个 `key_links.pattern` 改为无字面单引号的 plain scalar。重跑后结果为 `all_verified: true`、`verified: 4`、`total: 4`。

### 剩余问题

未修复 `gsd-sdk verify.key-links` 对带引号 pattern 的解析行为。后续 PLAN key_links 的 regex pattern 直接写 plain scalar，避免工具误把引号纳入匹配。

### 下次继续排查入口

- `gsd-sdk query verify.key-links`
- `.planning/phases/*/*-PLAN.md` 的 `key_links.pattern`

## 54. Phase 28 post-review regression 测试误把既有 trace row 当成 invalid append 写入

日期：2026-06-23

### 问题现象

修复 Phase 28 code review blocker 后运行 focused suite，新增测试 `test_append_minimal_event_validates_before_flush_on_operation_id_failure` 失败，断言 `row_count == 0`，实际为 `1`。

### 如何检测 / 复现

运行：

```bash
uv run pytest tests/replay/test_decision_events.py tests/agent/test_events.py tests/agent/test_memory_write_node.py tests/replay/test_sequence_allocator.py tests/replay/test_replay_service.py -q
```

### 关键证据或命令

失败输出：

```text
FAILED tests/replay/test_decision_events.py::test_append_minimal_event_validates_before_flush_on_operation_id_failure
E       assert 1 == 0
```

### 当前判断 / 根因

测试断言错误，不是修复逻辑错误。`_create_run()` 会通过 `write_agent_run()` 预先写入一条 run trace row，因此 invalid minimal append 失败后按 run 统计仍然会有 1 条既有记录。真正要验证的是 invalid append 被 catch 后再 commit 不会新增 `AgentTraceEvent`。

### 已做处理

把测试改为记录 append 前的 `before_count`，catch 后 commit，再断言当前 count 等于 `before_count`。重跑 focused suite 通过：`90 passed, 1 warning`；重跑 `tests/replay` 通过：`100 passed, 1 warning`。

### 剩余问题

无。

### 下次继续排查入口

- `tests/replay/test_decision_events.py::test_append_minimal_event_validates_before_flush_on_operation_id_failure`
- `src/replay/service.py::ReplayService.append_event`

## 55. Codex Default mode 下 `request_user_input` 不可用导致 discuss-phase 选择器回退文本模式

日期：2026-06-23

### 问题现象

执行 `$gsd-discuss-phase 29` 时，workflow 要求用交互选择器询问灰区选择，但 Codex 当前处于 Default mode，`request_user_input` 工具不可用，调用返回 `request_user_input is unavailable in Default mode`。

### 如何检测 / 复现

在 Default mode 下按 `gsd-discuss-phase` workflow 的 AskUserQuestion 映射调用 `request_user_input`。

### 关键证据或命令

工具返回：

```text
request_user_input is unavailable in Default mode
```

### 当前判断 / 根因

这是运行模式限制，不是 Phase 29 内容问题。`gsd-discuss-phase` skill adapter 已定义 execute/default 不可用时回退为普通文本编号选择。

### 已做处理

改用 plain-text 编号问题继续讨论，并把阶段性决策写入 `.planning/phases/29-tool-platform-boundary/29-DISCUSS-CHECKPOINT.json` 防止中断丢失。

### 剩余问题

无阻塞。后续在 Default mode 执行交互式 GSD workflow 时继续使用文本编号回退。

### 下次继续排查入口

- `/Users/ming/.codex/skills/gsd-discuss-phase/SKILL.md`
- `/Users/ming/.codex/get-shit-done/workflows/discuss-phase.md`

## 56. `state.record-session` 在本轮调用中写坏 STATE.md Session Continuity 字段

日期：2026-06-23

### 问题现象

生成 Phase 29 context 后按 workflow 更新 STATE：

```bash
gsd-sdk query state.record-session --stopped-at "Phase 29 context gathered" --resume-file ".planning/phases/29-tool-platform-boundary/29-CONTEXT.md"
```

工具返回 `recorded: true`，但 `.planning/STATE.md` 的 `Session Continuity` 字段被写成错误值，并且 frontmatter 的 `status` / `stopped_at` / `progress` 也发生漂移。第一次 flag 形式写入后出现：

```text
Last session: --stopped-at
Stopped at: Phase 29 context gathered
Resume file: --resume-file
```

随后尝试 positional fallback：

```bash
gsd-sdk query state.record-session "Phase 29 context gathered" ".planning/phases/29-tool-platform-boundary/29-CONTEXT.md"
```

结果仍不正确：

```text
Last session: Phase 29 context gathered
Stopped at: .planning/phases/29-tool-platform-boundary/29-CONTEXT.md
Resume file: None
```

### 如何检测 / 复现

运行上述 `state.record-session` 命令后检查：

```bash
sed -n '136,146p' .planning/STATE.md
```

### 关键证据或命令

`gsd-sdk query state.record-session` 两次都返回成功，但 `STATE.md` 正文内容错误。相关 handler 位于：

```text
/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs
/Users/ming/.codex/get-shit-done/bin/lib/state.cjs
```

### 当前判断 / 根因

当前判断是 GSD `state.record-session` 在 `gsd-sdk query` 调用链中的参数传递或字段替换存在缺陷：返回成功并不代表 `Session Continuity` 三行语义正确。`state.patch` 也不适合修复本问题，因为目标字段名包含空格，不能稳定作为 flag 名传递。

### 已做处理

用最小补丁修复 `.planning/STATE.md` 正文：

```text
Last session: 2026-06-23T13:40:00+08:00
Stopped at: Phase 29 context gathered
Resume file: .planning/phases/29-tool-platform-boundary/29-CONTEXT.md
```

同时恢复 frontmatter：

```yaml
status: ready_to_plan
stopped_at: Phase 29 context gathered
last_updated: "2026-06-23T13:40:00+08:00"
last_activity: 2026-06-23 -- Phase 29 context gathered
progress:
  total_phases: 10
  completed_phases: 4
  total_plans: 10
  completed_plans: 5
  percent: 40
```

### 剩余问题

未修复 GSD 工具本身。后续使用 `state.record-session` 后必须立刻检查 `.planning/STATE.md` 的 frontmatter 和 `Session Continuity` 三行。

### 下次继续排查入口

- `gsd-sdk query state.record-session`
- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs::cmdStateRecordSession`

## 57. Phase 29 plan-phase UI heuristic 将 `ToolView` 误判为 UI 工作

### 问题现象

运行 `$gsd-plan-phase 29` 初始化后，GSD UI 检测启发式因为 Phase 29 文档中大量出现 `ToolView` / planner view 字样，将本阶段误判为包含 UI 工作。

### 如何检测 / 复现

执行 Phase 29 plan-phase 初始化流程并检查 UI gate 结果；Phase 29 的目标是工具平台边界和 planner-visible capability view，不是前端 UI。

### 关键证据或命令

Phase 29 roadmap goal：

```text
Replace scattered tool allowlists with descriptor-driven planner views, runtime authorization, result projection, and decision events.
```

相关文本中的 `view` 指 `ToolViewV1` 契约，不是 browser/frontend UI。

### 当前判断 / 根因

当前判断是 GSD UI heuristic 使用了过宽关键词匹配，未区分 contract/model 名称里的 `View` 与真实 UI/前端工作。

### 已做处理

本轮将其作为 false positive 处理，未触发 UI-SPEC/UI auditor 流程；Phase 29 计划仍按 backend/platform boundary 处理，并由 validation/threat model 覆盖 prompt-safe `ToolView` 契约。

### 剩余问题

未修复 GSD heuristic 本身。后续包含 `ToolView`、`ProjectionView`、`ViewModel` 等后端契约名的阶段仍可能误触发 UI gate。

### 下次继续排查入口

- `$gsd-plan-phase 29`
- `/Users/ming/.codex/get-shit-done/workflows/plan-phase.md`
- GSD UI detection / HAS_UI heuristic

## 58. `state.planned-phase` 在 Phase 29 计划完成时回退 STATE.md 元数据

### 问题现象

运行：

```bash
gsd-sdk query state.planned-phase --phase "29" --name "Tool Platform Boundary" --plans "4"
```

工具返回 `updated: true`，但 `.planning/STATE.md` 的 frontmatter 和正文状态出现回退/不一致：

```yaml
status: planning
last_activity: 2026-06-23 -- Phase 28 complete
progress:
  completed_phases: 3
  total_plans: 9
  percent: 56
```

正文仍显示：

```text
Plan: Not planned
Status: Ready to plan
```

同时追加了 Phase 29 planned 记录，导致同一文件里“已计划”和“未计划”并存。

### 如何检测 / 复现

运行上述 `state.planned-phase` 后检查：

```bash
sed -n '1,80p' .planning/STATE.md
git diff -- .planning/STATE.md
```

### 关键证据或命令

工具返回：

```json
{
  "updated": true,
  "phase": "29",
  "name": "Tool Platform Boundary",
  "plans": "4"
}
```

随后 `git diff -- .planning/STATE.md` 显示它把 `completed_phases` 从 4 改为 3，把 `last_activity` 改回 Phase 28 complete，并未更新 Current Position 为 ready to execute。

### 当前判断 / 根因

当前判断是 GSD `state.planned-phase` 使用了过期或不完整的 state 模板/统计逻辑，只追加 planned entry，但没有同步正文状态，并且会回退 frontmatter 统计字段。这个问题与上一条 `state.record-session` 的 STATE 写入漂移属于同类风险。

### 已做处理

手动修复 `.planning/STATE.md`：

```yaml
status: ready_to_execute
stopped_at: Phase 29 planned
last_updated: "2026-06-23T14:57:58+08:00"
last_activity: 2026-06-23 -- Phase 29 planned
progress:
  total_phases: 10
  completed_phases: 4
  total_plans: 10
  completed_plans: 5
  percent: 40
```

并同步正文：

```text
Plan: 29-01 through 29-04 planned
Status: Ready to execute
Next: Execute Phase 29 Tool Platform Boundary
```

### 剩余问题

未修复 GSD 工具本身。后续使用 `state.planned-phase` 后必须立刻检查 `.planning/STATE.md` 的 frontmatter、Current Position、Performance Metrics 和 Session Continuity。

### 下次继续排查入口

- `gsd-sdk query state.planned-phase`
- `/Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs`
- `/Users/ming/.codex/get-shit-done/bin/lib/state.cjs`

## 2026-06-23 16:01 CST - Phase 29 plan 修复复核时 `rg` 正则引号错误

### 问题现象

复核 Phase 29 plan/spec 修复时，一个用于确认旧 `UnifiedToolManager` graph-facing 文本是否残留的 `rg` 命令失败，shell 输出：

```text
zsh:1: unmatched "
```

### 如何检测 / 复现

在仓库根目录运行包含未转义反引号和双引号混用的旧复核命令会触发 zsh 解析失败。

### 关键证据或命令

失败命令意图是搜索 `docs/contract-spec.md` 和 `.planning/phases/29-tool-platform-boundary` 中的旧 manager 边界文本；失败原因来自命令本身的 quoting，而不是仓库内容。

### 当前判断 / 根因

复核命令的正则字符串里包含 markdown 反引号，放在双引号 shell 字符串中后被 zsh 当作命令替换边界解析，导致 unmatched quote。

### 已做处理

改用单引号包裹正则并移除反引号敏感片段后重跑：

```bash
rg -n 'UnifiedToolManager 是 graph-facing|唯一 node-facing|UnifiedToolManager read/retrieval|UnifiedToolManager\.invoke.*执行单次|UnifiedToolManager\.invoke.*必须|UnifiedToolManager\.visible_tools.*输出|execute_action.*UnifiedToolManager' docs/contract-spec.md .planning/phases/29-tool-platform-boundary
```

该命令无匹配，说明旧 graph-facing manager 文本已经清除。

### 剩余问题

无。后续写 markdown/regex 混合复核命令时，优先用单引号或拆分查询，避免反引号触发 shell 解析。

### 下次继续排查入口

- `docs/contract-spec.md`
- `.planning/phases/29-tool-platform-boundary/29-*-PLAN.md`

## 2026-06-23 16:47 CST - 并行运行 DB-backed pytest 导致测试库建表竞争

### 问题现象

复核 GLM 5.2 执行的 Phase 29-01 RED 测试时，并行运行多个 `uv run pytest ...` 命令，其中两个 DB-backed 测试在 fixture setup 阶段报错：

```text
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "pg_type_typname_nsp_index"
DETAIL: Key (typname, typnamespace)=(tenants, ...) already exists.
```

### 如何检测 / 复现

在同一仓库/同一测试库上同时运行多个需要 `tests/conftest.py` 初始化数据库 schema 的 pytest 进程，可能复现建表竞争。

### 关键证据或命令

并行触发的命令包括：

```bash
uv run pytest tests/replay/test_tool_policy_events.py::test_tool_policy_event_rejects_raw_descriptor_and_arg_payload -q
uv run pytest tests/conversation/test_service.py::test_append_tool_result_stores_projector_normalized_data_without_raw_sentinels -q
```

失败栈显示两者都在 `tests/conftest.py` 的 `Base.metadata.create_all` 附近创建 `tenants` 表时冲突。

### 当前判断 / 根因

当前判断是本地验证方式问题：多个 DB-backed pytest 进程并发使用同一 Postgres 测试 schema / database，`create_all` 并发导致 catalog/type 约束冲突。不是 Phase 29-01 测试内容本身的直接证据。

### 已做处理

本轮 code review 中不把该错误计入 GLM 代码问题；后续 DB-backed 测试改为串行运行，或使用隔离测试库/schema。

### 剩余问题

未排查测试 fixture 是否能自动隔离并发 pytest。若未来需要并行 DB 测试，应修 fixture 或给每个进程独立 database/schema。

### 下次继续排查入口

- `tests/conftest.py`
- `tests/replay/test_tool_policy_events.py`
- `tests/conversation/test_service.py`

## 2026-06-23 17:23 CST - 复核 Phase 29-02 时并行 DB-backed pytest 再次触发测试库建表竞争

### 问题现象

复核 `test/xiaomi-phase29-02` 的 29-02 实现时，并行运行两组 pytest，其中包含 DB-backed `tests/replay/test_decision_events.py` 和 `tests/replay/test_tool_policy_events.py`。第一组测试出现 `UniqueViolationError`、`UndefinedTableError` 等 fixture setup/teardown 级错误。

### 如何检测 / 复现

在同一 Postgres 测试库上并行运行多个需要 `tests/conftest.py` 初始化/清理 schema 的 pytest 进程，可能复现。

### 关键证据或命令

并行触发的命令包括：

```bash
uv run pytest tests/tools/test_tool_platform.py::test_tool_view_exposes_only_prompt_safe_fields tests/tools/test_tool_platform.py::test_prompt_safe_schema_projection_strips_descriptor_policy_and_adapter_metadata tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope tests/tools/test_tool_platform.py::test_visibility_stage_forbids_runtime_only_reason_codes tests/replay/test_decision_events.py -q
uv run pytest tests/replay/test_tool_policy_events.py tests/replay/test_replay_migration_contract.py -q
```

错误栈包含：

```text
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "pg_type_typname_nsp_index"
asyncpg.exceptions.UndefinedTableError: relation "agent_runs" does not exist
```

### 当前判断 / 根因

当前判断仍是本地验证方式问题：多个 DB-backed pytest 进程并发共享同一测试库，schema create/drop 互相踩踏。不是 29-02 实现本身的证据。

### 已做处理

改为串行重跑 29-02 第一组 verify 命令，结果 `57 passed`；第二组 verify 在并行批次中已完成 `16 passed`。后续 DB-backed pytest 继续避免并行执行。

### 剩余问题

测试 fixture 仍不支持同库并发 pytest。若后续希望并行跑 DB 测试，需要给每个 pytest 进程隔离 database/schema，或在 fixture 层串行化 schema lifecycle。

### 下次继续排查入口

- `tests/conftest.py`
- `tests/replay/test_decision_events.py`
- `tests/replay/test_tool_policy_events.py`

## 2026-06-23 17:25 CST - Phase 29-02 变更文件 ruff 检查发现未使用 import

### 问题现象

对 29-02 变更文件运行 ruff 时失败，提示 `tests/replay/test_replay_migration_contract.py` 中 `pytest` import 未使用。

### 如何检测 / 复现

```bash
uv run ruff check src/tools/contracts.py src/tools/policy.py src/replay/decision_events.py src/replay/validators.py src/db/models.py src/db/migrations/versions/017_tool_policy_events.py tests/replay/test_replay_migration_contract.py
```

### 关键证据或命令

```text
F401 [*] `pytest` imported but unused
 --> tests/replay/test_replay_migration_contract.py:6:8
```

### 当前判断 / 根因

29-01 RED 测试里曾用 `pytest.fail(...)` 标记缺失 migration；29-02 实现后该分支被删除，但 `import pytest` 没有同步删除。

### 已做处理

本轮仅做 code review，未修改小米模型提交；该问题列入 review finding，建议后续修复时删除 unused import。

### 剩余问题

无。删除 unused import 后应重新运行 ruff。

### 下次继续排查入口

- `tests/replay/test_replay_migration_contract.py`

## 2026-06-27 18:02 CST - Phase 29.5 Plan 02 Task 1 verify 暴露 investigate 既有架构边界红灯

### 问题现象

执行 Phase 29.5 Plan 02 Task 1 的 verify 命令时，`tests/platform/test_trusted_context_factory.py` 和 `tests/platform/test_trusted_context.py` 均通过，但 `tests/architecture/test_trusted_context_boundaries.py` 有 1 个失败。

### 如何检测 / 复现

```bash
uv run pytest tests/platform/test_trusted_context_factory.py tests/platform/test_trusted_context.py tests/architecture/test_trusted_context_boundaries.py -q
```

### 关键证据或命令

失败断言：

```text
tests/architecture/test_trusted_context_boundaries.py::test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors
AssertionError: ['src/agent/nodes/investigate.py still directly constructs service context'] == []
```

定位命令：

```bash
rg -n 'ToolCallContext\(|KnowledgeContext\(' src/agent/nodes/investigate.py
```

命中：

```text
src/agent/nodes/investigate.py:295:    return ToolCallContext(
```

### 当前判断 / 根因

当前判断为既有架构边界红灯，不是 Plan 02 本轮 `TrustedContextFactory` / `require_merchant_access` 变更引入。Phase 29.5 Plan 05 已把 `src/agent/nodes/investigate.py` missing trusted context / wildcard fallback 收敛列为执行范围，因此本轮不提前改 Plan 05 文件，避免跨 wave scope creep。

### 已做处理

Plan 02 本轮只完成 factory role matrix 和 route-level merchant helper。Plan-level 验证命令已通过：

```bash
uv run pytest tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py -q
```

结果：`42 passed`。Task 1 broader verify 中的 architecture 红灯已记录为 Plan 05 入口。

### 剩余问题

执行 Phase 29.5 Plan 05 时，需要移除或重构 `src/agent/nodes/investigate.py` 中直接构造 `ToolCallContext` 的路径，并让 architecture boundary test 重新通过。

### 下次继续排查入口

- `src/agent/nodes/investigate.py`
- `tests/architecture/test_trusted_context_boundaries.py`
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-05-PLAN.md`

## 2026-06-27 19:40 CST - Phase 29.5 Plan 05 approval integration fixture 仍使用旧工具注入 seam

### 问题现象

执行 Phase 29.5 Plan 05 Task 1 红测集合时，除预期的 approval admin-only / resume wildcard 失败外，`tests/test_approval_integration.py` 的高风险 approval 流程一度无法生成 `approval_id`，低风险 policy 查询也出现 `insufficient_evidence`。

### 如何检测 / 复现

```bash
uv run pytest tests/test_approval_integration.py -q --tb=short
```

### 关键证据或命令

PDB 查看高风险 chat payload 时，trace 显示只执行了 `get_order` / `get_refund_case` / `get_ticket` 或 `get_order` / `search_policy`，但没有稳定进入 approval interrupt：

```text
"nodes_executed": ["receive_request", "classify_intent", "session_memory_load", "extract_slots", "investigate", "final_response"]
"final_status": "insufficient_evidence"
```

直接调用 fixture platform 曾返回：

```text
invalid_response [] ... INVALID_EXECUTOR_RESPONSE
```

### 当前判断 / 根因

Phase 29 后 `investigate.py` 通过 `ToolPlatform.with_defaults(...)` 获取 graph-facing 工具平台；旧 fixture 仍尝试 monkeypatch `UnifiedToolManager.with_defaults`，后来又误把 `ToolPlatform.with_defaults` 类方法全局替换，导致 `action_draft` 也拿到只有 read/retrieval executor 的 fake platform。另有一次缩进错误让 fake `search_policy` executor 构造 evidence 后没有返回 `ToolResultV2`。

### 已做处理

在 `tests/conftest.py` 中把 approval graph fixture 改为只替换 `investigate` 模块内的 `ToolPlatform` 符号，直接提供测试用 `ToolPlatform` / business executor / knowledge executor，并 stub `MaterialClaimVerifier` 为 allow，避免 Phase 33 claim-verifier 细节干扰 Plan 05 approval resume 覆盖。随后验证：

```bash
uv run pytest tests/test_approval_integration.py -q --tb=short
```

结果：`5 passed`。

### 剩余问题

无本轮阻塞问题。该 fixture 仍是 approval integration 专用 mock；Phase 33 重新深化 RAG / claim verification 时应避免把此 allow stub 误当成 verifier 行为覆盖。

### 下次继续排查入口

- `tests/conftest.py::mock_graph`
- `tests/test_approval_integration.py`
- `src/agent/nodes/investigate.py`
- `src/agent/nodes/action_draft.py`

## 2026-06-27 21:54 CST - Phase 29.5 review-fix 直接 pytest 再次命中系统 Python 3.9

### 问题现象

执行 WR-01 focused regression 时，直接运行 `pytest` 在加载 `tests/conftest.py` 阶段失败，未进入测试用例。

### 如何检测 / 复现

```bash
pytest tests/business/test_service.py::test_merchant_can_access_rejects_forged_admin_context
```

### 关键证据或命令

```text
ImportError: cannot import name 'UTC' from 'datetime' (/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/datetime.py)
```

环境定位：

```text
which pytest -> /Users/ming/Library/Python/3.9/bin/pytest
which python3.12 -> /Users/ming/.local/bin/python3.12
which uv -> /Users/ming/.local/bin/uv
```

### 当前判断 / 根因

本地 PATH 中的 `pytest` 仍指向 Python 3.9 用户安装版本；MOCA 声明 Python 3.12+，并使用 `datetime.UTC`，因此这是命令入口错误，不是本次 authz 修复逻辑失败。

### 已做处理

改用项目惯用命令重跑 focused regression：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py::test_merchant_can_access_rejects_forged_admin_context -q --tb=short
```

结果：`1 passed, 1 warning`。WR-02 的 focused integration regressions 也通过 `uv run` 验证。

### 剩余问题

无本轮阻塞问题。直接运行裸 `pytest` 仍可能复现该环境坑。

### 下次继续排查入口

- `.planning/LOCAL-VALIDATION-ISSUES.md` 中既有 “直接运行 pytest 命中了系统 Python 3.9” 条目
- `pyproject.toml`
- `.venv/bin/python`

## 2026-06-27 22:26 CST - Phase 29.5 verify-work focused suite 暴露 raw tool mock authz seam

### 问题现象

执行 Phase 29.5 非交互式 verify-work focused regression suite 时，5 个 raw demo business tool 的旧 success 测试失败；另外检查 SECURITY artifact 时直接使用 zsh glob，空匹配触发 `no matches found`。

### 如何检测 / 复现

空 glob 问题：

```bash
ls .planning/phases/29.5-merchant-scope-role-model-alignment/*-SECURITY.md 2>/dev/null || true
```

focused suite 问题：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py tests/integration/test_orders.py tests/integration/test_refund_cases.py tests/integration/test_tickets.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/business/test_service.py tests/knowledge/test_service.py tests/agent/test_tools/test_unified_tool_manager.py tests/test_approval_api.py tests/approvals/test_single_level_runtime.py tests/approvals/test_hash_binding.py tests/approvals/test_events.py tests/approvals/test_needs_info_resume.py tests/test_approval_integration.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/agent/test_nodes/test_investigate.py tests/tools/test_merchant_scope_static.py -q --tb=short
```

### 关键证据或命令

空 glob 证据：

```text
zsh:1: no matches found: .planning/phases/29.5-merchant-scope-role-model-alignment/*-SECURITY.md
```

focused suite 首次结果：

```text
5 failed, 333 passed, 11 warnings
FAILED tests/agent/test_tools/test_get_order.py::test_get_order_success
FAILED tests/agent/test_tools/test_get_order.py::test_get_order_no_messages_field
FAILED tests/agent/test_tools/test_get_refund_case.py::test_get_refund_case_success
FAILED tests/agent/test_tools/test_get_ticket.py::test_get_ticket_by_ticket_no_success
FAILED tests/agent/test_tools/test_get_ticket.py::test_get_ticket_by_uuid_success
```

失败 warning 中还出现：

```text
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

### 当前判断 / 根因

空 glob 是 zsh 默认 `nomatch` 行为；检查可选 artifact 应改用 `find` 或关闭 nomatch，而不是裸 glob。

5 个测试失败是 test seam 与 Phase 29.5 review-fix 后的 authz 语义不一致：WR-01 修复后 `merchant_can_access()` 即使对 `role="admin"` 也会查询真实 active same-tenant `User` 并校验 stored role。旧 success tests 同时 mock repository 和传入 `AsyncMock()` session，只想覆盖 response shaping / repository routing，却没有 stub 新的 DB-backed authz helper，因此 helper 访问 AsyncMock session 后落入 raw tool 的 broad `DB_ERROR` 捕获。

### 已做处理

- SECURITY artifact 检查改用 `find .planning/phases/29.5-merchant-scope-role-model-alignment -maxdepth 1 -name '*-SECURITY.md' -type f -print`，确认当前没有 SECURITY artifact。
- 在 5 个 isolated raw tool success tests 中显式 monkeypatch 对应模块的 `merchant_can_access` 为 `AsyncMock(return_value=True)`；真实 DB-backed admin/merchant-bound allow/deny 行为仍由 seeded-session tests 覆盖。
- 重跑失败点：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_get_order.py::test_get_order_success tests/agent/test_tools/test_get_order.py::test_get_order_no_messages_field tests/agent/test_tools/test_get_refund_case.py::test_get_refund_case_success tests/agent/test_tools/test_get_ticket.py::test_get_ticket_by_ticket_no_success tests/agent/test_tools/test_get_ticket.py::test_get_ticket_by_uuid_success -q --tb=short
```

结果：`5 passed, 1 warning`。

- 重跑完整 Phase 29.5 focused suite：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py tests/integration/test_orders.py tests/integration/test_refund_cases.py tests/integration/test_tickets.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/business/test_service.py tests/knowledge/test_service.py tests/agent/test_tools/test_unified_tool_manager.py tests/test_approval_api.py tests/approvals/test_single_level_runtime.py tests/approvals/test_hash_binding.py tests/approvals/test_events.py tests/approvals/test_needs_info_resume.py tests/test_approval_integration.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/replay/test_replay_api.py tests/agent/test_nodes/test_investigate.py tests/tools/test_merchant_scope_static.py -q --tb=short
```

结果：`338 passed, 6 warnings`。

### 剩余问题

无本轮阻塞问题。当前 Phase 29.5 仍缺 SECURITY artifact；security enforcement 为 `true`，后续推进 phase 前应跑 `$gsd-secure-phase 29.5`。

### 下次继续排查入口

- `tests/agent/test_tools/test_get_order.py`
- `tests/agent/test_tools/test_get_refund_case.py`
- `tests/agent/test_tools/test_get_ticket.py`
- `src/integrations/demo_business/authz.py`
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-UAT.md`

## 2026-06-27 23:51 CST - gsd-next pending spike/sketch 空 glob 检查触发 zsh nomatch

### 问题现象

执行 `$gsd-next` 的 exploratory work notice 检查时，仓库当前没有 `.planning/spikes/*/README.md` 或 `.planning/sketches/*/README.md` 匹配文件；直接在 zsh 中展开 glob 触发 `no matches found`。命令后续仍输出计数 `0`，但 stderr 出现环境噪音。

### 如何检测 / 复现

```bash
grep -rl 'verdict: PENDING' .planning/spikes/*/README.md 2>/dev/null | wc -l | tr -d ' '
grep -rl 'winner: null' .planning/sketches/*/README.md 2>/dev/null | wc -l | tr -d ' '
```

### 关键证据或命令

```text
zsh:1: no matches found: .planning/spikes/*/README.md
0

zsh:1: no matches found: .planning/sketches/*/README.md
0
```

### 当前判断 / 根因

这是 zsh 默认 `nomatch` 行为；workflow 文档里的 shell 片段假设空 glob 可以被 `grep ... 2>/dev/null` 吞掉，但在 zsh 中 glob 展开发生在命令执行前，stderr 不会被该重定向处理。

### 已做处理

改用目录存在性判断包装检查，避免空 glob：

```bash
if [ -d .planning/spikes ]; then grep -rl 'verdict: PENDING' .planning/spikes/*/README.md 2>/dev/null | wc -l | tr -d ' '; else printf '0'; fi
if [ -d .planning/sketches ]; then grep -rl 'winner: null' .planning/sketches/*/README.md 2>/dev/null | wc -l | tr -d ' '; else printf '0'; fi
```

结果：pending spike/sketch 计数均为 `0`。

### 剩余问题

无本轮阻塞问题。后续在 zsh 中检查可选 glob 文件时仍应避免裸 glob，优先用 `find`、目录存在性判断或显式 `noglob`。

### 下次继续排查入口

- `$HOME/.codex/get-shit-done/workflows/next.md`
- `.planning/spikes/`
- `.planning/sketches/`

## 2026-06-27 23:56 CST - gsd-next prior-phase completeness gate 误判历史 summary 命名

### 问题现象

重新执行 `$gsd-next` 前的 prior-phase completeness scan 时，`gsd-sdk query find-phase` 将历史阶段 24.2、24.3、24.4、25 标记为 `incomplete_plans`。这些阶段实际已有 summary 和验证记录，但 summary 文件使用了阶段级命名，例如 `24.2-SUMMARY.md`、`25-SUMMARY.md`，没有采用当前 SDK 匹配规则需要的 plan 级命名 `*-01-SUMMARY.md`。

### 如何检测 / 复现

```bash
for n in 24.2 24.3 24.4 25; do
  gsd-sdk query find-phase "$n"
done
```

### 关键证据或命令

```text
24.2 incomplete_plans: ["24.2-01-PLAN.md"]
24.3 incomplete_plans: ["24.3-01-PLAN.md"]
24.4 incomplete_plans: ["24.4-01-PLAN.md"]
25 incomplete_plans: ["25-01-PLAN.md"]
```

同时人工读取确认这些文件均为对应唯一 plan 的完成总结：

```text
.planning/phases/24.2-unified-session-memory-bundle-read-path/24.2-SUMMARY.md
.planning/phases/24.3-memory-write-isolation-policy-and-observability-mvp/24.3-SUMMARY.md
.planning/phases/24.4-memory-eval-mvp/24.4-SUMMARY.md
.planning/phases/25-intent-routing-safety-hardening/25-SUMMARY.md
```

### 当前判断 / 根因

这是历史 GSD 文档命名与当前 `gsd-sdk find-phase` plan-summary 配对规则不一致，不是这些历史阶段真的缺少收尾总结。当前规则期望 `N-01-PLAN.md` 对应 `N-01-SUMMARY.md`。

### 已做处理

使用 `git mv` 将历史 summary 改为当前 SDK 可识别的 plan 级命名：

```text
24.2-SUMMARY.md -> 24.2-01-SUMMARY.md
24.3-SUMMARY.md -> 24.3-01-SUMMARY.md
24.4-SUMMARY.md -> 24.4-01-SUMMARY.md
25-SUMMARY.md -> 25-01-SUMMARY.md
```

同步更新 Phase 25 中指向旧 summary 文件名的引用。随后应重新运行 `gsd-sdk query find-phase 24.2/24.3/24.4/25` 确认 `incomplete_plans: []`。

### 剩余问题

无本轮代码阻塞问题。若后续还有更早历史阶段使用阶段级 summary 命名，可能在类似安全门中再次暴露，需要按同样方式确认后修正。

### 下次继续排查入口

- `$HOME/.codex/get-shit-done/workflows/next.md`
- `gsd-sdk query find-phase <phase>`
- `.planning/phases/24.2-unified-session-memory-bundle-read-path/`
- `.planning/phases/24.3-memory-write-isolation-policy-and-observability-mvp/`
- `.planning/phases/24.4-memory-eval-mvp/`
- `.planning/phases/25-intent-routing-safety-hardening/`

## 2026-06-28 00:07 CST - gsd-sdk state.record-session flag 调用写错 STATE 会话字段

### 问题现象

按 `$HOME/.codex/get-shit-done/workflows/discuss-phase.md` 中的示例执行 `gsd-sdk query state.record-session --stopped-at ... --resume-file ...` 后，`.planning/STATE.md` 的 Session Continuity 字段被错误写入：

```text
Last session: --stopped-at
Resume file: --resume-file
```

### 如何检测 / 复现

```bash
gsd-sdk query state.record-session --stopped-at "Phase 30 context gathered" --resume-file ".planning/phases/30-businessfactservice-boundary/30-CONTEXT.md"
rg -n "Last session|Stopped at|Resume file" .planning/STATE.md
```

### 关键证据或命令

```bash
sed -n '1190,1215p' "$HOME/.codex/get-shit-done/workflows/discuss-phase.md"
sed -n '620,675p' /opt/homebrew/lib/node_modules/@gsd-build/sdk/dist/query/state-mutation.js
```

当前 workflow 文档使用 flag 风格调用；本机 `/opt/homebrew` 安装的 `gsd-sdk query state.record-session` handler 注释和实现实际为 positional 参数：`args[0]` timestamp、`args[1]` stopped-at、`args[2]` resume file。

### 当前判断 / 根因

这是 GSD workflow 文档与当前本机 `gsd-sdk query` handler 实现不一致导致的本地工具调用坑，不是 Phase 30 context 内容问题。flag 风格参数被 query handler 当作普通 positional token 消费，因此 `--stopped-at` 和 `--resume-file` 被写入了 `STATE.md`。

### 已做处理

用 positional 形式重跑并修正 `STATE.md`：

```bash
gsd-sdk query state.record-session "" "Phase 30 context gathered" ".planning/phases/30-businessfactservice-boundary/30-CONTEXT.md"
```

修正后确认：

```text
Last session: 2026-06-27T16:06:56.258Z
Stopped at: Phase 30 context gathered
Resume file: .planning/phases/30-businessfactservice-boundary/30-CONTEXT.md
```

### 剩余问题

Phase 30 本轮流程无阻塞。后续在当前本机 `gsd-sdk query state.record-session` 下应使用 positional 调用，或先核对 SDK 版本是否已修正文档 / handler 行为。

### 下次继续排查入口

- `$HOME/.codex/get-shit-done/workflows/discuss-phase.md`
- `/opt/homebrew/lib/node_modules/@gsd-build/sdk/dist/query/state-mutation.js`
- `.planning/STATE.md`

## 2026-06-28 00:23 CST - skill-creator 脚本执行与校验依赖问题

### 问题现象

为创建 `$gsd-phase-autopilot` skill 时，skill-creator 的初始化和校验脚本暴露三个本地环境/参数问题：

1. 直接执行 `init_skill.py --help` 返回 `permission denied`。
2. `init_skill.py` 初次运行时因 `short_description` 超过 64 字符而中止，但已经创建了 skill 目录和 `SKILL.md`。
3. `quick_validate.py` 因当前 `python3` 环境缺少 `yaml` 模块而无法运行。

### 如何检测 / 复现

```bash
/Users/ming/.codex/skills/.system/skill-creator/scripts/init_skill.py --help
python3 /Users/ming/.codex/skills/.system/skill-creator/scripts/init_skill.py gsd-phase-autopilot --path /Users/ming/.codex/skills --resources references --interface short_description='Run a single GSD phase through dual-AI plan review, execution, and post-phase audits.'
python3 /Users/ming/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/ming/.codex/skills/gsd-phase-autopilot
```

### 关键证据或命令

```text
zsh:1: permission denied: /Users/ming/.codex/skills/.system/skill-creator/scripts/init_skill.py
[ERROR] short_description must be 25-64 characters (got 85).
ModuleNotFoundError: No module named 'yaml'
```

同时确认当前默认 Python 为 `/opt/homebrew/bin/python3`，导入 `yaml` 失败：

```bash
which -a python3 python
python3 - <<'PY'
import yaml
PY
```

### 当前判断 / 根因

`init_skill.py` 没有可执行权限，需要通过 `python3` 调用。`agents/openai.yaml` 的 `short_description` 有 25-64 字符限制。skill-creator 的校验/元数据生成脚本依赖 `PyYAML`，但当前 Homebrew Python 环境未安装该模块。

### 已做处理

改用 `python3` 调用初始化脚本，并将 `short_description` 缩短到限制内。`generate_openai_yaml.py` 也因缺 `yaml` 无法读取 frontmatter，已通过显式传入 `--name gsd-phase-autopilot` 绕过读取并成功生成 `agents/openai.yaml`：

```bash
python3 /Users/ming/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py /Users/ming/.codex/skills/gsd-phase-autopilot --name gsd-phase-autopilot --interface display_name='GSD Phase Autopilot' --interface short_description='Automate a full GSD phase lifecycle' --interface default_prompt='$gsd-phase-autopilot 30'
```

由于 `quick_validate.py` 仍缺 `PyYAML`，本轮执行了等价轻量校验：确认 `SKILL.md` frontmatter 存在、`name` 为 `gsd-phase-autopilot`、`description` 非空且包含 29.5 workflow 触发语义，并确认 `references/workflow.md` 与 `agents/openai.yaml` 均存在。

### 剩余问题

官方 `quick_validate.py` 尚未在当前 Python 环境跑通。后续若要使用官方校验脚本，应在合适环境安装 `PyYAML`，或使用已有 conda 环境中带 `yaml` 的 Python。

### 下次继续排查入口

- `/Users/ming/.codex/skills/.system/skill-creator/scripts/init_skill.py`
- `/Users/ming/.codex/skills/.system/skill-creator/scripts/quick_validate.py`
- `/Users/ming/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py`
- `/Users/ming/.codex/skills/gsd-phase-autopilot/`

## 2026-06-28 02:39 CST - `state.begin-phase` 位置参数误用

### 问题现象

启动 Phase 30 执行时，误把 `gsd-sdk query state.begin-phase` 当成 flag API 调用，导致 `.planning/STATE.md` 临时出现 `Phase --phase`、`Plan: 1 of --name` 等错误状态。

### 如何检测 / 复现

```bash
gsd-sdk query state.begin-phase --phase "30" --name "businessfactservice-boundary" --plans "3"
git diff -- .planning/STATE.md
```

### 关键证据或命令

```text
{
  "phase": "--phase",
  "name": "30",
  "plan_count": "--name"
}
```

### 当前判断 / 根因

`state.begin-phase` 当前接受 positional 参数，不接受 `--phase` / `--name` / `--plans` flag 形式。workflow 示例使用 flag 风格，和实际 SDK handler 行为不一致。

### 已做处理

立即用 positional 参数重跑，覆盖错误状态：

```bash
gsd-sdk query state.begin-phase "30" "businessfactservice-boundary" "3"
```

### 剩余问题

Phase 30 执行无阻塞。后续调用 `state.begin-phase` 时继续使用 positional 参数，或修正 GSD workflow 文档 / SDK handler 之一。

### 下次继续排查入口

- `/Users/ming/.codex/get-shit-done/workflows/execute-phase.md`
- `/opt/homebrew/lib/node_modules/@gsd-build/sdk/dist/query/state-mutation.js`
- `.planning/STATE.md`

## 2026-06-28 03:14 CST - Phase 30-02 BusinessFactService compatibility / ToolPlatform RED failures

### 问题现象

执行 Phase 30-02 时，Task 1 GREEN 首轮验证仍有 1 个兼容性失败；Task 2 RED 验证按预期暴露 executor 未显式引用 `BusinessFactService`、`ToolPolicyEngine.resource_scope_binding` 仍序列化 order/refund/ticket 原始 identifier。

### 如何检测 / 复现

```bash
uv run pytest tests/business/test_service.py tests/business/test_adapters.py -q --tb=short
uv run pytest tests/tools/test_tool_platform.py -q --tb=short
```

### 关键证据或命令

- Task 1 剩余失败：`test_fetch_context_mixed_results_is_partial_and_lists_missing_fact` 期望旧 adapter not-found code `NOT_FOUND`，wrapper 初版输出 `BUSINESS_FACT_NOT_FOUND`。
- Task 2 RED 失败：`test_business_tool_executor_source_uses_business_fact_service_boundary` 未找到 `BusinessFactService`；order/refund/ticket marker 测试发现 `resource_scope_binding` 额外包含 `order_no` / `refund_case_no` / `ticket_id`。

### 当前判断 / 根因

Task 1 是兼容 facade 迁移时未保留 not-found 聚合错误码；Task 2 是 Phase 29 marker 仍偏向 runtime binding 调试信息，未按 Phase 30 no-leak 要求只暴露 domain-scope proof marker。

### 已做处理

`BusinessToolService` 已通过 `BusinessFactService` 包装 `BusinessFactResultV1`，并对 not-found 保留 adapter safe error code。`BusinessToolExecutor` 已显式构造 `BusinessFactService`，`ToolPolicyEngine` 对 order/refund/ticket domain lookup identifier 只保留 `requires_domain_scope_check` marker，不再序列化原始 identifier。

### 剩余问题

无阻塞。`BusinessFactService.fetch_context(...).tool_results=[]` 仍是 domain-service 侧有意保留的空 tool-result 列表；兼容 facade `BusinessToolService.fetch_context(...)` 已返回 wrapped `ToolResultV2`。

### 下次继续排查入口

- `src/business/service.py`
- `src/tools/executors/business.py`
- `src/tools/policy.py`
- `tests/business/test_service.py`
- `tests/tools/test_tool_platform.py`

## 2026-06-28 03:30 CST - Phase 30 code review pytest entrypoint used Python 3.9

### 问题现象

执行 Phase 30 code review 验证时，直接运行 `pytest ...` 失败，报错为 `ImportError: cannot import name 'UTC' from 'datetime'`。

### 如何检测 / 复现

```bash
pytest tests/business/test_service.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py tests/business/test_schemas.py -q
```

### 关键证据或命令

```text
tests/conftest.py:3: in <module>
    from datetime import UTC, datetime, timedelta
E   ImportError: cannot import name 'UTC' from 'datetime' (/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/datetime.py)
```

`pyproject.toml` 声明 `requires-python = ">=3.12"`；`python --version` 和 `python3 --version` 均为 3.13.3，但 shell 上的裸 `pytest` 入口实际指向 Xcode Python 3.9 环境。

### 当前判断 / 根因

这是本机命令入口环境不一致，不是 Phase 30 代码失败。项目测试应通过 `uv run pytest ...` 使用项目虚拟环境。

### 已做处理

改用以下命令重跑同一测试集合并通过：

```bash
uv run pytest tests/business/test_service.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py tests/business/test_schemas.py -q
```

结果：`147 passed, 1 warning in 38.71s`。

### 剩余问题

无代码阻塞。后续本项目验证避免使用裸 `pytest`，优先使用 `uv run pytest`。

### 下次继续排查入口

- `pyproject.toml`
- `.venv/`
- shell PATH 中的 `pytest` 入口

## 2026-06-28 03:36 CST - Phase 30 code review direct business imports fail

### 问题现象

Phase 30 code review 中做最小导入验证时，直接导入新增 business package / module 失败：`import src.business`、`import src.business.schemas`、`import src.business.service` 都触发 circular import。

### 如何检测 / 复现

```bash
uv run python -c "import src.business"
uv run python -c "import src.business.schemas"
uv run python -c "import src.business.service"
```

### 关键证据或命令

```text
ImportError: cannot import name 'BusinessContextV1' from partially initialized module 'src.business.schemas'
```

调用链为：`src.business.__init__ -> src.business.schemas -> src.tools.contracts -> src.tools.__init__ -> src.tools.manager -> src.tools.executors.business -> src.business.service -> src.business.schemas`。

### 当前判断 / 根因

`src.tools.__init__` eager-export `UnifiedToolManager`，导致任何 `src.tools.contracts` 导入都会先执行 tool manager / executor 导入；新增 `src.business.schemas` 又依赖 `src.tools.contracts`，形成 package import 顺序敏感的循环。

### 已做处理

未在 code review 阶段修改源码；已作为 `.planning/phases/30-businessfactservice-boundary/30-REVIEW.md` 的 Critical finding 记录。

### 剩余问题

需要修复导入边界，建议把 `src.tools.__init__` 中的 `UnifiedToolManager` 改成 lazy export，或移除 package-level eager import。

### 下次继续排查入口

- `src/business/__init__.py`
- `src/business/schemas.py`
- `src/tools/__init__.py`
- `src/tools/manager.py`
- `src/tools/executors/business.py`

## 2026-06-28 07:55 CST - CR-01 tenant-scope fix initially dropped action business-fact diagnostic

### 问题现象

Phase 30 CR-01 修复后运行 authority boundary 目标测试时，`test_action_recommendation_rejects_wrong_tenant_business_ref` 失败。action recommendation 已 fail closed，但 `reason_codes` 少了既有测试期望的 `business_fact_ref_required`。

### 如何检测 / 复现

```bash
uv run pytest tests/agent/rag_context/test_authority_boundaries.py -q
```

### 关键证据或命令

```text
AssertionError: assert {'business_fact_ref_required', 'tenant_scope_invalid'} <= {'tenant_scope_invalid'}
```

### 当前判断 / 根因

新增 tenant-scope 早退路径在 `_verify_action_recommendation_claim()` 中直接返回 `UNAUTHORIZED`，没有先保留 wrong-tenant business ref 场景原本由 business authority 检查追加的诊断码。

### 已做处理

在 tenant-scope 早退前补充 `_business_authority_passed()` 检查；业务事实 authority 不通过且尚未包含 `business_fact_ref_required` 时追加该 reason code。随后重跑目标测试通过。

### 剩余问题

无。该问题是本次修复过程中的诊断码回归，已在提交前处理。

### 下次继续排查入口

- `src/agent/rag_context/verifier.py`
- `tests/agent/rag_context/test_authority_boundaries.py`

## 2026-06-28 08:25 CST - Phase 30 clean re-review again hit bare pytest Python 3.9 entrypoint

### 问题现象

Phase 30 clean re-review 过程中，初次使用系统默认 `pytest` 入口运行目标测试时在环境加载阶段失败；随后切换到项目 `.venv` 的 Python 3.12 测试入口后通过。

### 如何检测 / 复现

```bash
pytest -q tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/business/test_schemas.py tests/business/test_service.py tests/tools/test_tool_platform.py
```

### 关键证据或命令

`30-REVIEW.md` clean re-review 记录显示：系统默认 `pytest` 指向 Python 3.9，因项目代码使用 `datetime.UTC` 且要求 Python 3.12+，初次运行在环境加载阶段失败；改用以下命令通过：

```bash
.venv/bin/pytest -q tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_nodes/test_investigate.py tests/agent/test_policy_retrieval_ownership.py tests/business/test_schemas.py tests/business/test_service.py tests/tools/test_tool_platform.py
```

结果：`160 passed, 1 warning`。

### 当前判断 / 根因

这是已知本机 PATH / 测试入口问题的复发，不是 Phase 30 代码回归。裸 `pytest` 仍可能绕过项目虚拟环境并命中旧 Python 3.9。

### 已做处理

使用 `.venv/bin/pytest` 重新运行同一聚焦测试集合并通过；clean re-review 报告已记录验证结果。

已把该复发升级为项目级硬规则写入 `AGENTS.md`：MOCA 测试禁止裸 `pytest` / 裸 `python -m pytest`，review、verification、clean re-review、GSD agent 和外部 AI 提示词里的测试命令都必须显式使用 `uv run pytest ...` 或 `.venv/bin/pytest ...`；裸 pytest 结果视为无效验证，必须用项目入口重跑。

### 剩余问题

无代码阻塞。后续 MOCA 本地验证继续避免裸 `pytest`，优先使用 `uv run pytest` 或 `.venv/bin/pytest`。

### 下次继续排查入口

- `.planning/phases/30-businessfactservice-boundary/30-REVIEW.md`
- `.venv/bin/pytest`
- shell PATH 中的 `pytest` 入口

## 2026-06-28 08:32 CST - Phase 30 verify-work security artifact check hit zsh no-match glob

### 问题现象

Phase 30 自检时用 `ls .planning/phases/30-businessfactservice-boundary/*-SECURITY.md 2>/dev/null || true` 检查 security artifact，命令在 zsh 下因 glob 无匹配直接报 `no matches found`，没有进入 `ls`。

### 如何检测 / 复现

```bash
ls .planning/phases/30-businessfactservice-boundary/*-SECURITY.md 2>/dev/null || true
```

### 关键证据或命令

```text
zsh:1: no matches found: .planning/phases/30-businessfactservice-boundary/*-SECURITY.md
```

### 当前判断 / 根因

这是 zsh 默认 `nomatch` 行为导致的本地验证命令问题，不是 Phase 30 代码或 planning artifact 失败。未匹配的 glob 在 zsh 中会先被 shell 拦截，`2>/dev/null` 不能捕获。

### 已做处理

改用 `find` 检查同一目录：

```bash
find .planning/phases/30-businessfactservice-boundary -name '*-SECURITY.md' -type f -maxdepth 1
```

结果为空，确认 Phase 30 当前没有 `SECURITY.md` artifact。

### 剩余问题

无代码阻塞。后续在 zsh 下检查可选文件时避免裸 glob，优先使用 `find`、`rg --files` 或加引号/显式 nullglob 处理。

### 下次继续排查入口

- `.planning/phases/30-businessfactservice-boundary/`
- `$HOME/.codex/get-shit-done/workflows/verify-work.md`

## 2026-06-28 09:10 CST - Phase 30 secure-phase stale gate scan included nonexistent prior verification files

### 问题现象

Phase 30 security artifact 提交后，收尾检查用一条 `rg` 同时扫描 Phase 30 目录和 Phase 29 / 29.5 verification 文件，命令因 Phase 29 / 29.5 没有对应 `*-VERIFICATION.md` 文件返回退出码 2。

### 如何检测 / 复现

```bash
rg -n "SECURITY.md|security_review_required|Security Gate|secure-phase|security review" .planning/phases/30-businessfactservice-boundary .planning/phases/29-tool-platform-boundary/29-VERIFICATION.md .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-VERIFICATION.md
```

### 关键证据或命令

```text
rg: .planning/phases/29-tool-platform-boundary/29-VERIFICATION.md: No such file or directory (os error 2)
rg: .planning/phases/29.5-merchant-scope-role-model-alignment/29.5-VERIFICATION.md: No such file or directory (os error 2)
.planning/phases/30-businessfactservice-boundary/30-VERIFICATION.md:13:security_review_required: true
.planning/phases/30-businessfactservice-boundary/30-VERIFICATION.md:133:No `30-SECURITY.md` artifact exists.
```

### 当前判断 / 根因

这是收尾验证命令范围写得过宽导致的本地检查问题，不是 Phase 30 实现或 security artifact 失败。该命令同时暴露了 `30-VERIFICATION.md` 中 security gate 文本已经因新建 `30-SECURITY.md` 变成 stale。

### 已做处理

改为只读取当前 Phase 30 verification 片段，确认 stale gate 后更新 `30-VERIFICATION.md`：`security_review_required` 改为 `false`，Security Gate 改为引用 `30-SECURITY.md`，并记录 12/12 threats closed、0 open、auditor verdict `SECURED`。

### 剩余问题

无代码阻塞。Phase 29 / 29.5 没有 `*-VERIFICATION.md` 属于历史 artifact 差异，不影响 Phase 30 secure-phase 结果。

### 下次继续排查入口

- `.planning/phases/30-businessfactservice-boundary/30-SECURITY.md`
- `.planning/phases/30-businessfactservice-boundary/30-VERIFICATION.md`
- `find .planning/phases -maxdepth 2 -name '*-VERIFICATION.md' -type f`

## 2026-06-28 09:24 CST - Phase 30 validate-phase test infrastructure scan hit zsh no-match glob

### 问题现象

Phase 30 Nyquist validation 的测试基础设施扫描命令包含未加引号的 `jest.config.*` / `vitest.config.*` glob，在 zsh 下因没有匹配文件触发 `no matches found`，导致该命令提前报错。

### 如何检测 / 复现

```bash
find . -name "pytest.ini" -o -name "jest.config.*" -o -name "vitest.config.*" -o -name "pyproject.toml" 2>/dev/null | head -10
```

### 关键证据或命令

```text
zsh:1: no matches found: jest.config.*
```

### 当前判断 / 根因

这是 zsh 默认 `nomatch` 行为导致的本地验证命令问题，不是 Phase 30 代码、测试或 validation artifact 失败。未匹配 glob 在命令执行前由 shell 拦截，`find` 本身没有机会处理该模式。

### 已做处理

改用加引号并加括号的 `find` 重新扫描：

```bash
find . \( -name 'pytest.ini' -o -name 'jest.config.*' -o -name 'vitest.config.*' -o -name 'pyproject.toml' \) -not -path '*/.venv/*' 2>/dev/null | head -20
```

结果找到 `./pyproject.toml`。随后继续完成 Phase 30 validation audit，focused suite 结果为 `203 passed, 1 warning`，ruff 和 `git diff --check` 均通过。

### 剩余问题

无代码阻塞。后续在 zsh 下写 `find -name` 多模式命令时，所有带 `*` 的 pattern 都应加单引号或用 `rg --files` 替代。

### 下次继续排查入口

- `.planning/phases/30-businessfactservice-boundary/30-VALIDATION.md`
- `pyproject.toml`
- `$HOME/.codex/get-shit-done/workflows/validate-phase.md`

## 2026-06-28 10:36 CST - Phase 31 discuss-phase memory model scan included nonexistent path

### 问题现象

Phase 31 discuss-phase 期间，为核对 memory scope / model 字段，第一次 `rg` 扫描命令包含不存在的 `src/models` 路径，导致 `rg` 返回退出码 2。命令仍输出了部分匹配结果，但不能作为完整验证结果直接引用。

### 如何检测 / 复现

```bash
rg -n "scope_type|scope_id|review_status|pii_classification|deleted_at|expires_at" src/memory src/models src/db src
```

### 关键证据或命令

```text
rg: src/models: No such file or directory (os error 2)
```

### 当前判断 / 根因

这是本地验证命令路径写错导致的扫描问题，不是 Phase 31 代码或规划 artifact 的问题。MOCA 的 SQLAlchemy 持久化模型实际集中在 `src/db/models.py`，不存在 `src/models` 目录。

### 已做处理

改用实际存在的路径重新核对：`src/db/models.py`、`src/memory/*`、`src/db/migrations/versions/013_long_term_case_memory.py`、`tests/memory/*`。确认 `SessionMemory`、`LongTermMemory`、`CaseMemory`、`MemoryTombstone`、`MemoryWriteEvent` 位于 `src/db/models.py`，long-term/case/tombstone/write-event 已有 scope、review、PII、deleted/expired、identity/hash 等字段和测试基础。

### 剩余问题

无代码阻塞。后续扫描模型路径时应优先使用 `src/db/models.py` 或 `rg --files src/db src/memory` 确认实际文件结构。

### 下次继续排查入口

- `src/db/models.py`
- `src/memory/long_term.py`
- `src/memory/case_memory.py`
- `tests/memory/test_long_term_memory_service.py`
- `tests/memory/test_case_memory_retrieval.py`

## 2026-06-28 10:52 CST - Phase 31 plan-phase artifact scan hit zsh no-match glob

### 问题现象

Phase 31 plan-phase 初始化后，为检查是否已有 PLAN / RESEARCH / VALIDATION / PATTERNS artifact，命令直接传入多个未加引号的 `*.md` glob。由于 Phase 31 当时尚未生成这些文件，zsh 的 `nomatch` 行为在命令执行前报错，导致检查命令退出。

### 如何检测 / 复现

```bash
ls .planning/phases/31-memory-platform-boundary/*-PLAN.md .planning/phases/31-memory-platform-boundary/*-RESEARCH.md .planning/phases/31-memory-platform-boundary/*-VALIDATION.md .planning/phases/31-memory-platform-boundary/*-PATTERNS.md 2>/dev/null || true
```

### 关键证据或命令

```text
zsh:1: no matches found: .planning/phases/31-memory-platform-boundary/*-PLAN.md
```

### 当前判断 / 根因

这是本地 artifact 检查命令写法问题，不是 Phase 31 planning artifact 缺失异常。zsh 会在 `ls` 执行前展开 glob；没有匹配项时直接报 `no matches found`，`2>/dev/null || true` 无法捕获这个 shell 展开错误。

### 已做处理

改用 `find` 检查目录内容，确认当时 Phase 31 目录只有 `31-CONTEXT.md` 和 `31-DISCUSSION-LOG.md`，符合 plan-phase 前置状态。随后继续 research / planning 流程。

### 剩余问题

无代码阻塞。后续在 zsh 下检查可选 artifact 时，应使用 `find`、`rg --files` 或给 glob 加 `noglob` / 引号后由工具内部处理。

### 下次继续排查入口

- `.planning/phases/31-memory-platform-boundary/`
- `$HOME/.codex/get-shit-done/workflows/plan-phase.md`

## 2026-06-28 11:20 CST - Phase 31 research parallel DB-backed pytest caused shared test database race

### 问题现象

Phase 31 research 期间，为快速验证 memory 相关现有测试，我把多个 DB-backed `uv run pytest ...` 命令并行启动。MOCA 的 pytest fixture 使用共享 PostgreSQL 测试库 `moca_test`，并在 `test_engine` fixture 中执行 `Base.metadata.drop_all/create_all`。并行命令互相重置同一个 schema，导致 setup 阶段出现 PostgreSQL catalog / table / lock 相关失败。

### 如何检测 / 复现

并行运行以下两组或更多 DB-backed 测试命令容易复现：

```bash
uv run pytest tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/agent/test_memory_evidence_boundary.py -q
uv run pytest tests/memory/test_long_term_memory_repository.py tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py -q
```

### 关键证据或命令

```text
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "pg_type_typname_nsp_index"
asyncpg.exceptions.UndefinedTableError: relation "tenants" does not exist
asyncpg.exceptions.DeadlockDetectedError: deadlock detected
```

### 当前判断 / 根因

这是验证命令调度错误，不是 Phase 31 生产代码结论。`tests/conftest.py` 固定使用 `postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test`，每个 DB-backed pytest 进程都会 drop/create 全部 metadata；并行进程会互相删除或锁住同一批表。

### 已做处理

停止把 DB-backed pytest 组并行作为结论来源。Phase 31 research 后续只把这些失败记录为环境/验证坑，计划中的测试命令必须串行运行，或者先改造 fixture 使用进程隔离数据库名。

### 剩余问题

`tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority` 在并行失败输出中还出现一次断言差异：期望 `VerificationOutcome.UNSUPPORTED`，实际 `INSUFFICIENT`。该测试不依赖 DB race，后续应单独用串行命令重跑确认是当前仓库真实回归还是并行污染后的附带现象。

### 下次继续排查入口

- `tests/conftest.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `src/agent/rag_context/verifier.py`
- `.planning/phases/31-memory-platform-boundary/31-RESEARCH.md`

## 2026-06-28 11:27 CST - Phase 31 research confirmed memory authority-boundary test outcome drift

### 问题现象

串行单测确认 `tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority` 当前失败。测试期望 memory-supported action dependency 使 action claim outcome 为 `VerificationOutcome.UNSUPPORTED`，实际返回 `VerificationOutcome.INSUFFICIENT`。

### 如何检测 / 复现

```bash
uv run pytest tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority -q
```

### 关键证据或命令

```text
E       AssertionError: assert <Verification...insufficient'> == <Verification...'unsupported'>
E         - unsupported
E         + insufficient
```

同轮串行 smoke：

```bash
uv run pytest tests/agent/test_session_memory_load.py -q
```

结果为 `6 passed`，说明基础 `session_memory_load` 非 DB 单测可运行。

### 当前判断 / 根因

这是当前仓库真实测试期望与 verifier 行为不一致，不是并行 DB fixture 污染。Phase 31 正好要求“Tests prove memory cannot satisfy policy evidence, current business fact, approval/action snapshot, or replay truth requirements”，因此计划阶段应把该断言语义纳入 RED/repair：要么修正 verifier outcome 到 expected `UNSUPPORTED`，要么若项目决策认为 `INSUFFICIENT` 是正确分类，则同步测试和 Phase 31 acceptance wording，但不能静默忽略。

### 已做处理

已记录为 Phase 31 research 的验证发现；未修改生产代码或测试。

### 剩余问题

需要在 Phase 31 计划中安排一个具体任务处理该 authority-boundary outcome drift，并用串行 `uv run pytest ...` 重跑确认。

### 下次继续排查入口

- `tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority`
- `src/agent/rag_context/verifier.py`
- `src/agent/rag_context/claims.py`

## 2026-06-28 11:10 CST - Phase 31 plan-phase UI gate regex matched backend word Platform

### 问题现象

Phase 31 plan-phase UI design gate 使用简单关键词正则扫描 phase section，返回 `HAS_UI_EXIT=0`，看起来像命中了 frontend/UI phase。但 Phase 31 是 Memory Platform backend/platform boundary，不涉及 UI。进一步定位发现命中来自 `Memory Platform Boundary` 中的 `Platform` 包含 `form` 子串。

### 如何检测 / 复现

```bash
PHASE_SECTION=$(gsd-sdk query roadmap.get-phase "31" 2>/dev/null)
printf '%s' "$PHASE_SECTION" | grep -iE "UI|interface|frontend|component|layout|page|screen|view|form|dashboard|widget" >/dev/null 2>&1
echo HAS_UI_EXIT=$?

gsd-sdk query roadmap.get-phase "31" 2>/dev/null | rg -in "UI|interface|frontend|component|layout|page|screen|view|form|dashboard|widget"
```

### 关键证据或命令

```text
HAS_UI_EXIT=0
4:  "phase_name": "Memory Platform Boundary",
12:  "section": "### Phase 31: Memory Platform Boundary...
```

### 当前判断 / 根因

这是 plan-phase UI gate 关键词正则的假阳性，不是 Phase 31 缺少 UI-SPEC。关键词 `form` 没有单词边界，导致 `Platform` 被误判为 UI/form 相关。

### 已做处理

人工核对 Phase 31 roadmap/context/research，确认该 phase 范围是 memory platform service/API boundary，不涉及 frontend/UI、screen、form 或 dashboard。继续 plan-phase，不要求 `$gsd-ui-phase 31`。

### 剩余问题

workflow 层面后续可考虑把 UI gate 关键词改为带单词边界的匹配，或排除 `platform` 这类常见 backend 词。

### 下次继续排查入口

- `$HOME/.codex/get-shit-done/workflows/plan-phase.md`
- `.planning/ROADMAP.md`

## 2026-06-28 11:31 CST - Phase 31 planning audit regex accidentally triggered bare pytest

### 问题现象

Phase 31 plan 文件自查时，用 `rg -v "uv run pytest|bare \`pytest\`|..."` 过滤文本。由于 zsh 执行了双引号内的反引号，命令意外触发裸 `pytest`，随后命中本机 Python 3.9，出现 `datetime.UTC` import 失败。该输出不是有效测试结论。

### 如何检测 / 复现

```bash
rg -n "\bpytest\b|python -m pytest" .planning/phases/31-memory-platform-boundary/31-*-PLAN.md | rg -v "uv run pytest|bare `pytest`|bare pytest|pytest\\.mark|No validation conclusion"
```

### 关键证据或命令

```text
ImportError while loading conftest '/Users/ming/projects/MOCA/tests/conftest.py'.
tests/conftest.py:3: in <module>
    from datetime import UTC, datetime, timedelta
E   ImportError: cannot import name 'UTC' from 'datetime' (/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/datetime.py)
```

### 当前判断 / 根因

这是命令 quoting 错误导致 shell 执行反引号中的 `pytest`。裸 pytest 命中了系统 Python 3.9，不是 MOCA 项目虚拟环境，也不是 Phase 31 plan 文件或应用代码失败。

### 已做处理

未采信该输出作为验证结果。后续 plan 文本检查改用单引号或避免反引号。Phase 31 PLAN.md 内的自动化验证命令仍显式使用 `uv run pytest ...`。

### 剩余问题

无应用侧剩余问题。后续所有 review/verification 命令仍必须避免裸 `pytest` / 裸 `python -m pytest`。

### 下次继续排查入口

- `AGENTS.md` 本地验证命令环境硬规则
- `.planning/phases/31-memory-platform-boundary/31-*-PLAN.md`

## 2026-06-28 11:44 CST - Codex app server / CLI 在 Documents 权限被 macOS TCC 拦截

### 问题现象

通过 Codex app server 启动 fresh session 失败，报：

```text
thread/start failed during TUI bootstrap: thread/start failed: failed to load configuration: Operation not permitted (os error 1)
Error: turn/start failed in TUI
```

同一环境中直接访问 `~/Documents` 也失败：

```text
ls: /Users/ming/Documents: Operation not permitted
```

### 如何检测 / 复现

```bash
ls -lde@ /Users/ming/Documents
ls /Users/ming/Documents
stat -f '%Sp %Su:%Sg %N' /Users/ming/Documents
```

### 关键证据或命令

```text
drwx------@ 9 ming  staff  288 Jun 24 12:02 /Users/ming/Documents
        com.apple.macl  -1
 0: group:everyone deny delete

ls: /Users/ming/Documents: Operation not permitted
drwx------ ming:staff /Users/ming/Documents
```

`codex --version` 正常返回 `codex-cli 0.142.3`，且在 `/Users/ming/projects/MOCA` 用伪终端启动 `codex --yolo` 可以进入 TUI；说明二进制和 MOCA 项目配置本身不是直接故障点。

### 当前判断 / 根因

这是 macOS TCC 隐私权限拦截，不是 Unix 文件权限或 MOCA 代码问题。`~/Documents` 属于受保护目录；当启动 Codex 的外层 app（如 Codex App app-server、iTerm、Terminal、VS Code）没有 Documents Folder / Full Disk Access 权限时，子进程里的 `codex` 和普通 `ls` 都会收到 `Operation not permitted`。

如果只给某一个 Codex 入口授权，另一个入口仍可能失败：CLI 继承 iTerm/Terminal/VS Code 的权限；Codex app server 继承 `/Applications/Codex.app` 的权限。授权后也需要完全退出并重新启动相关 app/server，旧进程不会自动拿到新 TCC 授权。

### 已做处理

已确认：

- `/Users/ming/.codex/config.toml` 和 `/Users/ming/.codex/auth.json` owner/权限正常；
- `/Users/ming/projects/MOCA` 下的 TUI 启动路径可用；
- 当前进程无法读取 `/Users/ming/Documents`，最小复现与 app server 报错方向一致。

### 剩余问题

需要在 macOS 系统设置里给实际启动入口授权并重启相关进程。建议同时检查：

- `Codex.app`
- `iTerm.app` 或 `Terminal.app`
- 如果从编辑器终端启动，还包括 `Visual Studio Code.app` / Cursor 等编辑器

优先使用 Full Disk Access；至少需要 Files and Folders 中的 Documents Folder 权限。

### 下次继续排查入口

- System Settings -> Privacy & Security -> Full Disk Access
- System Settings -> Privacy & Security -> Files and Folders
- `ls /Users/ming/Documents`
- `codex --yolo`
- Codex app server 进程：`/Applications/Codex.app/Contents/Resources/codex app-server`
## 2026-06-28 13:05 CST - rg pattern 中 Markdown 反引号触发 zsh 命令替换

### 问题现象

在复核 Phase 31 plan 修订文本时，`rg` pattern 使用双引号包裹，pattern 内包含 Markdown 反引号形式的 `` `memory_context` ``，zsh 将反引号内容当作命令替换执行，出现：

```text
zsh:1: command not found: memory_context
```

### 如何检测 / 复现

在 zsh 中运行包含双引号和反引号的 grep/rg pattern，例如：

```bash
rg -n "structured `memory_context` projection" .planning/phases/31-memory-platform-boundary/31-*.md
```

### 关键证据或命令

失败后改用单引号重新运行：

```bash
rg -n 'structured `memory_context` projection|permissive/strict bare DTO parse|projection sanitizer' .planning/phases/31-memory-platform-boundary/31-*.md
```

正确引用后的 `rg` 命令返回目标 plan 行；`git diff --check` 通过。

### 当前判断 / 根因

这是 shell quoting 问题，不是 plan 内容或应用代码问题。zsh 在双引号内仍会执行反引号命令替换；包含 Markdown code span 的搜索 pattern 应使用单引号或转义反引号。

### 已做处理

已用单引号重跑文本核对命令，并确认 Phase 31 plan 修订内容可被 `rg` 正确匹配。

### 剩余问题

无应用侧剩余问题。

### 下次继续排查入口

- 复核命令中的 shell quoting
- `.planning/phases/31-memory-platform-boundary/31-*-PLAN.md`

## 2026-06-28 13:47 CST - `state.begin-phase` 文档化 flag 形式在本地 SDK 中参数错位

### 问题现象

执行 `$gsd-execute-phase 31` 的初始化步骤时，按 workflow 文档运行：

```bash
gsd-sdk query state.begin-phase --phase 31 --name memory-platform-boundary --plans 6
```

SDK 返回的 JSON 出现参数错位：

```json
{
  "phase": "--phase",
  "name": "31",
  "plan_count": "--name"
}
```

### 如何检测 / 复现

在 MOCA 仓库根目录运行上述命令，然后检查 `.planning/STATE.md` 的 Phase / Plan 字段是否被写成异常值。

### 关键证据或命令

正确可用的本地调用形式是位置参数：

```bash
gsd-sdk query state.begin-phase 31 memory-platform-boundary 6
```

该命令返回：

```json
{
  "phase": "31",
  "name": "memory-platform-boundary",
  "plan_count": "6"
}
```

### 当前判断 / 根因

当前本地 `gsd-sdk` 的 `state.begin-phase` 子命令与 workflow 文档中的 flag 形式不一致；本地实现按位置参数解析，导致 flag token 被当成业务参数写入。

### 已做处理

已立即用位置参数形式重跑 `state.begin-phase`，并手动修正 `.planning/STATE.md` 中被 SDK 连带漂移的 `total_phases` 与 Phase 31 显示名。Phase 31 执行继续使用修正后的状态。

### 剩余问题

GSD workflow 文档或 SDK 参数解析仍存在不一致，后续继续执行阶段初始化时应优先用位置参数形式，或先确认当前 SDK help/实现。

### 下次继续排查入口

- `$HOME/.codex/get-shit-done/workflows/execute-phase.md`
- `gsd-sdk query state.begin-phase`
- `.planning/STATE.md`

## 2026-06-28 13:49 CST - `phase-plan-index` 将 Phase 31 依赖计划错误归入同一执行 wave

### 问题现象

执行 `$gsd-execute-phase 31` 时，`gsd-sdk query phase-plan-index 31` 返回的 wave 分组把 `31-01`、`31-02`、`31-03` 同放入 Wave 1。

但 `31-03-PLAN.md` frontmatter 明确写有：

```yaml
wave: 1
depends_on:
  - 31-01
  - 31-02
```

`31-01-PLAN.md` 与 `31-02-PLAN.md` 则是 `wave: 0` RED 测试计划。若按 SDK 分组并行执行，`31-03` 会与其前置 RED 测试计划并行，违背计划依赖和 TDD 顺序。

### 如何检测 / 复现

```bash
gsd-sdk query phase-plan-index 31
sed -n '1,40p' .planning/phases/31-memory-platform-boundary/31-03-PLAN.md
```

### 关键证据或命令

`phase-plan-index` 输出中：

```json
"waves": {
  "1": ["31-01", "31-02", "31-03"]
}
```

计划 frontmatter 中：

```yaml
plan: 31-03
wave: 1
depends_on:
  - 31-01
  - 31-02
```

### 当前判断 / 根因

当前 SDK wave index 可能把 `wave: 0` 归一化到 Wave 1，但没有同时提升依赖计划的 wave 或按 `depends_on` 重新拓扑排序，导致 Wave 0/1 被折叠成同一执行批次。

### 已做处理

本次 Phase 31 执行不采信该分组；按 plan frontmatter 和 `depends_on` 手动拓扑排序为：

- Wave 0: `31-01`, `31-02`
- Wave 1: `31-03`
- Wave 2: `31-04`
- Wave 3: `31-05`
- Wave 4: `31-06`

### 剩余问题

SDK `phase-plan-index` 的 wave 归一化/依赖拓扑逻辑仍需后续修复；在修复前，遇到 `wave: 0` 和 `depends_on` 混用的 phase 时必须回读计划 frontmatter 验证。

### 下次继续排查入口

- `gsd-sdk query phase-plan-index 31`
- `.planning/phases/31-memory-platform-boundary/31-*-PLAN.md`

## 2026-06-28 13:51 CST - zsh 中使用 `status` 变量导致 acceptance 检查命令自身失败

### 问题现象

执行 31-01 Task 1 的 `xfail|skip(` acceptance 检查时，命令没有实际完成检查，而是被 shell 报错中断：

```text
zsh:1: read-only variable: status
```

### 如何检测 / 复现

在 zsh 中运行包含 `status=$?` 赋值的检查命令：

```bash
set +e; rg -n "xfail|skip\\(" tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py; status=$?
```

### 关键证据或命令

失败输出：

```text
zsh:1: read-only variable: status
```

修正后重跑：

```bash
set +e; rg -n "xfail|skip\\(" tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py; rg_status=$?; if [ "$rg_status" -eq 1 ]; then echo 'NO_MATCHES'; exit 0; fi; exit "$rg_status"
```

输出：

```text
NO_MATCHES
```

### 当前判断 / 根因

zsh 中 `status` 是只读特殊参数，不能用作普通 shell 变量名。该问题属于验证命令入口错误，不是测试代码或项目行为失败。

### 已做处理

将变量名改为 `rg_status` 后立即重跑，acceptance 检查通过，确认本次 Task 1 未引入 `xfail` 或 `skip(`。

### 剩余问题

无。后续在 zsh 下编写一次性验证命令时避免使用 `status` 作为变量名。

### 下次继续排查入口

- 31-01 Task 1 acceptance checks
- zsh 特殊参数文档

## 2026-06-28 14:00 CST - 31-02 RED 边界测试 fixture 缺少 LongTermMemory.confidence

### 问题现象

执行 31-02 Task 1 RED 验证时，预期是新测试因计划中的生产模块尚未实现而失败，但其中一个 DB-backed fixture 在 flush 阶段先失败：

```text
asyncpg.exceptions.NotNullViolationError: null value in column "confidence" of relation "long_term_memories" violates not-null constraint
```

### 如何检测 / 复现

运行 31-02 Task 1 RED 验证命令：

```bash
bash -lc 'set +e; uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_session_memory_isolation.py -q; status=$?; test "$status" -ne 0'
```

### 关键证据或命令

失败点在 `tests/memory/test_reviewed_memory_context_boundary.py::_long_term_row(...)` 直接构造 `LongTermMemory` 行时未设置 `confidence`，与 `src/db/models.py` 中该字段非空约束不一致。

### 当前判断 / 根因

这是 31-02 新增 RED 测试 fixture 的建模错误，不是目标生产实现缺失导致的预期 RED 失败。直接插入 ORM 行时需要与现有 long-term memory 测试 helper 一样设置 `confidence=Decimal("0.9000")`。

### 已做处理

已在 `_long_term_row(...)` 中补充 `confidence=Decimal("0.9000")`，并重跑同一 RED 命令。重跑后失败原因只剩计划内缺失模块：

- `src.agent.nodes.reviewed_memory_context_retrieve`
- `src.memory.context_service`
- `src.agent.nodes.session_context_load`

### 剩余问题

无。当前 RED 失败符合 31-02 计划目标。

### 下次继续排查入口

- `tests/memory/test_reviewed_memory_context_boundary.py::_long_term_row`
- 31-02 Task 1 RED pytest 命令

## 2026-06-28 14:19 CST - 31-03 并行运行 DB-backed pytest 导致测试库 schema setup 冲突

### 问题现象

31-03 计划级验证时，错误地通过并行工具同时启动了两个包含 DB-backed fixture 的 `uv run pytest` 命令。两个 pytest 进程共享 `moca_test` 测试库并同时执行 metadata drop/create，导致一个命令出现 `pg_type_typname_nsp_index` 重复键与 `relation "tenants" does not exist`，另一个命令出现 PostgreSQL deadlock。

### 如何检测 / 复现

并行启动以下两个命令即可复现该类问题：

```bash
uv run pytest tests/memory/test_context_refs.py tests/agent/test_memory_evidence_boundary.py -q
uv run pytest tests/memory/test_context_refs.py tests/memory/test_session_memory_bundle.py -q
```

### 关键证据或命令

失败输出包含：

```text
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "pg_type_typname_nsp_index"
asyncpg.exceptions.UndefinedTableError: relation "tenants" does not exist
asyncpg.exceptions.DeadlockDetectedError: deadlock detected
```

### 当前判断 / 根因

这是本地验证入口错误，不是 31-03 代码行为失败。Phase 31 的 `31-VALIDATION.md` 已明确 DB-backed pytest groups 必须 serial，因为当前共享 `moca_test` fixture 会 drop/recreate metadata；本次并行执行违反了该规则。

### 已做处理

停止使用并行 pytest 验证，改为串行重跑同一组 `uv run pytest` 命令，并以串行结果作为有效结论。

### 剩余问题

无代码问题待修。后续 Phase 31 验证命令不得并行启动 DB-backed pytest。

### 下次继续排查入口

- `.planning/phases/31-memory-platform-boundary/31-VALIDATION.md`
- `tests/conftest.py::test_engine`

## 2026-06-28 16:17 CST - `phase.complete 31` 错误选择 backlog phase `999.1` 作为下一阶段

### 问题现象

Phase 31 验证通过后执行：

```bash
gsd-sdk query phase.complete 31
```

SDK 返回成功，但结果中的下一阶段为 backlog/parking-lot 项：

```json
{
  "completed_phase": "31",
  "next_phase": "999.1",
  "next_phase_name": "evaluate-mem0-as-optional-backend-behind-memorycontextservic"
}
```

同时 `.planning/STATE.md` 被写成 `Phase: 999.1`，而 v1.9 正常路线中 Phase 31 之后应进入 Phase 32 Intent Graph Migration。

### 如何检测 / 复现

```bash
gsd-sdk query phase.complete 31
sed -n '1,80p' .planning/STATE.md
rg -n '### Phase 31|### Phase 32|999.1' .planning/ROADMAP.md .planning/STATE.md
```

### 关键证据或命令

`phase.complete` 输出明确显示 `next_phase: "999.1"`；ROADMAP 中 Phase 31 后的正常顺序是：

```text
### Phase 32: Intent Graph Migration
```

### 当前判断 / 根因

当前 `phase.complete` 的 next-phase 选择逻辑把 backlog/parking-lot 编号 `999.1` 纳入了主线 phase 排序，且优先于 Phase 32。该行为不符合 MOCA v1.9 主线 roadmap。

### 已做处理

已手动修正 `.planning/STATE.md`，将当前阶段与下一路线恢复为 Phase 32；同时修正 `.planning/ROADMAP.md` 中 Phase 31 状态为 Complete，并保留 `.planning/REQUIREMENTS.md` 中 APF-09/APF-10 的完成状态。

### 剩余问题

SDK next-phase 选择逻辑仍需后续修复。后续运行 `phase.complete` 后必须核对 `next_phase` 是否跳入 backlog/parking-lot 编号。

### 下次继续排查入口

- `gsd-sdk query phase.complete 31`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`

## 2026-06-28 16:20 CST - zsh 裸 glob 检查缺失可选 GSD 文件时触发 `no matches found`

### 问题现象

Phase 31 收尾检查可选 artifact 时运行：

```bash
ls .planning/phases/31-memory-platform-boundary/*-SECURITY.md
ls .planning/phases/31-memory-platform-boundary/*-LEARNINGS.md
```

由于目标文件不存在，zsh 在执行 `ls` 前直接报错：

```text
zsh:1: no matches found: .planning/phases/31-memory-platform-boundary/*-SECURITY.md
zsh:1: no matches found: .planning/phases/31-memory-platform-boundary/*-LEARNINGS.md
```

### 如何检测 / 复现

在 zsh 下对不存在的匹配项使用未转义 glob 即可复现。

### 关键证据或命令

改用 `find` 后得到预期的空输出且 exit 0：

```bash
find .planning/phases/31-memory-platform-boundary -maxdepth 1 -name '*-SECURITY.md' -print
find .planning/phases/31-memory-platform-boundary -maxdepth 1 -name '*-LEARNINGS.md' -print
```

### 当前判断 / 根因

这是 zsh `nomatch` 行为导致的命令入口问题，不是 GSD artifact 或应用代码问题。

### 已做处理

已用 `find` 重查，确认 Phase 31 当前没有 `*-SECURITY.md` 或 `*-LEARNINGS.md`。

### 剩余问题

无代码问题。后续检查可选文件时优先使用 `find` 或显式关闭/处理 zsh `nomatch`。

### 下次继续排查入口

- 可选 artifact 检查命令
- `.planning/phases/31-memory-platform-boundary/`

## 2026-06-28 18:46 CST - zsh 裸 glob 检查缺失可选 UI-SPEC 文件时触发 `no matches found`

### 问题现象

执行 Phase 31 verify-work 自验前检查可选 UI spec artifact 时运行：

```bash
ls .planning/phases/31-memory-platform-boundary/*-UI-SPEC.md 2>/dev/null || true
```

由于目标文件不存在，zsh 在执行 `ls` 前直接报错：

```text
zsh:1: no matches found: .planning/phases/31-memory-platform-boundary/*-UI-SPEC.md
```

### 如何检测 / 复现

在 zsh 下对不存在的 `*-UI-SPEC.md` 使用未转义裸 glob 即可复现。

### 关键证据或命令

改用 `find` 后得到预期空输出且 exit 0：

```bash
find .planning/phases/31-memory-platform-boundary -maxdepth 1 -name '*-UI-SPEC.md' -type f -print
```

### 当前判断 / 根因

这是 zsh `nomatch` 行为导致的可选文件检查命令入口问题，不是 Phase 31 artifact 缺失错误，也不是应用代码问题。

### 已做处理

已改用 `find` 重新确认 Phase 31 没有 UI spec，因此 `verify-work` 的自动 UI 验证分支不适用。

### 剩余问题

无代码问题。后续检查可选 artifact 时继续使用 `find`，或显式处理 zsh `nomatch`。

### 下次继续排查入口

- `.planning/phases/31-memory-platform-boundary/`
- verify-work 自动 UI artifact 检查命令

## 2026-06-28 20:50 CST - Phase 32 research 文本检查命令中未转义 Markdown 反引号触发裸 `pytest`

### 问题现象

在检查 `.planning/phases/32-intent-graph-migration/32-RESEARCH.md` 中 pytest 命令写法时，执行了包含 Markdown 反引号的 zsh 双引号命令，zsh 先把 `` `pytest` `` 当作命令替换执行，导致裸 `pytest` 被触发并命中本机 Python 3.9。

报错片段：

```text
ImportError while loading conftest '/Users/ming/projects/MOCA/tests/conftest.py'.
tests/conftest.py:3: in <module>
    from datetime import UTC, datetime, timedelta
E   ImportError: cannot import name 'UTC' from 'datetime' (/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/datetime.py)
```

### 如何检测 / 复现

在 zsh 下使用双引号包裹含 Markdown 反引号的搜索模式即可复现，例如模式文本里包含 ``bare `pytest` `` 时，反引号内容会先作为 shell 命令执行。

### 关键证据或命令

触发问题的意图是搜索 research 文档中的测试命令文本；因为搜索模式包含未转义反引号，实际先执行了裸 `pytest`，再执行 `rg`。

修正后的安全写法使用单引号包裹搜索模式，避免反引号命令替换：

```bash
rg -n 'pytest|python -m pytest' .planning/phases/32-intent-graph-migration/32-RESEARCH.md
```

### 当前判断 / 根因

这是 shell 引号/反引号处理导致的命令入口错误，不是 Phase 32 research 内容本身的测试失败，也不是应用代码问题。它再次证明 MOCA 不能把裸 `pytest` 输出当作有效验证结论。

### 已做处理

已将 `32-RESEARCH.md` 中的测试命令文档检查改为使用单引号搜索模式，并继续要求所有可执行测试命令使用 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` 或 `.venv/bin/pytest ...`。

### 剩余问题

无代码问题。该次裸 `pytest` 输出无效，不作为验证结论。

### 下次继续排查入口

- `.planning/phases/32-intent-graph-migration/32-RESEARCH.md`
- `AGENTS.md` 本地验证命令环境硬规则
- zsh 搜索命令中的 Markdown 反引号转义
