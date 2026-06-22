# 本地验证问题记录

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
