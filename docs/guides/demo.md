<!-- generated-by: gsd-doc-writer -->
# MOCA 本地演示指南

| 元数据 | 值 |
| --- | --- |
| 文档类型 | GUIDE |
| 描述范围 | 当前工作区可重复的本地演示准备、五个场景、预期信号与排障入口 |
| 最后核验 | 2026-08-04（当前工作区） |
| 权威来源 | 当前 Makefile/Compose、seed/demo 脚本、API 路由、前端与测试 |
| 更新触发 | 启动方式、seed 数据、演示账号、API/UI 路径或核心用户流程变化 |

## 演示边界

本指南使用本地合成商家、订单、退款单、政策和账号，展示“业务事实 → 政策证据 → 风险 → 人工审批 → action draft → trace/replay”。MOCA 当前不会真实付款、退款或发券；审批通过最多生成 `not_executed_demo` 草稿，且 `external_side_effect=false`。[seed](../../scripts/seed_demo.py) [trace 投影测试](../../tests/test_trace_api.py#L33)

## 环境准备与可重复 reset/seed

前置工具：Docker Compose、`jq`；若使用 Makefile 或运行定向测试，还需 Python 3.12 与 `uv`。Compose 会启动 PostgreSQL、API 和 Vite frontend；API entrypoint 自动执行 Alembic migration。[Compose](../../docker-compose.yml) [entrypoint](../../docker-entrypoint.sh) [Makefile](../../Makefile)

```bash
cp .env.example .env
# 将 .env 中的 DASHSCOPE_API_KEY placeholder 换成本机有效 key；不要提交或展示真实 key
docker compose up --build -d
curl --retry 20 --retry-delay 2 --retry-connrefused -sf http://localhost:8000/health | jq .
make seed
```

`make seed` 等价于 `uv run python scripts/seed_demo.py --reset`，会重建两个演示 tenant 及其 runtime/业务数据。没有 host `uv` 时可改用 `docker compose exec api python scripts/seed_demo.py --reset`。[reset 实现](../../scripts/seed_demo.py#L61)

仅在确认 PostgreSQL volume 完全可丢弃时，才做硬重置：`docker compose down -v`，再重跑上面的启动和 seed；该命令会删除本地 Compose 数据卷。

## 入口与账号

| 入口 | 地址/用途 |
| --- | --- |
| Agent Console | `http://localhost:3000` |
| OpenAPI | `http://localhost:8000/docs` |
| 健康检查 | `GET http://localhost:8000/health` |
| 同步 chat fallback | `POST /api/v1/agent/chat` |
| 当前 UI runtime | `POST /api/v1/agent-runs` + `GET /{run_id}/events` SSE |

Frontend 默认通过 `/api/v1/auth/demo-token` 切换本地角色；这要求 `ENABLE_DEMO_AUTH=true`。手工 API 使用 `/api/v1/auth/token`。以下密码 `moca2024` 只来自公开 seed，且仅适用于本地合成账号。[UI 角色映射](../../frontend/src/hooks/useAuth.ts#L3) [auth router](../../src/api/routers/auth.py#L73)

| 用户 | 角色与 merchant | 演示 scope/用途 |
| --- | --- | --- |
| `cs_zhang` | support，星河数码 | `agent:chat`、订单/退款/工单/知识读取；发起场景 |
| `mgr_li` | manager，星河数码 | support scopes + `approvals:review`；审核同 merchant 请求 |
| `admin_user` | admin，tenant 级 | 审批、管理与同 tenant trace 排障 |

每个场景先点“新对话”，避免上一场的 thread memory 影响结果。右侧 `Details` 提供 `Result / Evidence / Approval / Trace / Run Info`；等待审批时会自动切到 `Approval`。[DetailsPanel](../../frontend/src/components/details/DetailsPanel.tsx#L14)

## 场景一：退款进度

1. 选择“客服专员 (Support Agent)”，新建对话。
2. 输入：`订单ORD-2024-001退款为什么还没到账？`
3. 预期信号：状态完成；Timeline/Trace 出现订单事实查询；回答提到 `ORD-2024-001`；Evidence 可见 `not_shipped` 相关来源。[演示订单/退款单](../../scripts/seed_demo.py#L246) [golden case](../../evaluation/golden/agent_cases.jsonl#L4)
4. 不应出现：把 seed 中 `submitted` 的退款单说成已到账，或读取其他 merchant 的订单。

## 场景二：政策证据问答

1. 新建对话，输入：`平台的退款超时处理规则是什么？`
2. 打开 `Evidence`，查看 `doc_key`、chunk、confidence；再在 `Trace` 确认检索/验证路径。
3. 预期信号：政策回答、`evidence_count > 0`，目标来源包含 `refund_general`。[政策 seed](../../scripts/seed_demo.py#L445) [golden case](../../evaluation/golden/agent_cases.jsonl#L1)
4. 不应出现：无来源却给确定政策结论、展示 raw prompt/provider credential，或伪造订单事实。

## 场景三：补偿建议

1. 新建对话，输入：`订单ORD-2024-002屏幕破损，商家想赔付200元优惠券安抚，是否合适？`
2. 预期信号：intent 为补偿建议，读取 `ORD-2024-002`，结合 `damaged_after_delivery` 与 `coupon_compensation` 给建议；当前 golden expectation 不要求审批。[golden case](../../evaluation/golden/agent_cases.jsonl#L19)
3. 不应出现：宣称优惠券已发放、把建议当审批决定，或绕过 evidence/risk 直接生成外部结果。

## 场景四：高风险审批中断

1. 仍以 `cs_zhang` 新建对话，输入：`客户投诉订单ORD-2024-002延迟发货，要求补偿600元`。
2. 预期信号：`risk_level=high`、HR-01、状态 `waiting_approval`/`interrupted`，产生 `approval_id`，界面自动显示安全化 proposed action 与最新 decision context。[风险规则](../../rules/risk_rules.yaml) [interrupt payload](../../src/api/routers/agent.py#L269)
3. 不应出现：`action_draft` 先于审批、聊天回复声称已批准/已发券，或 support 用户出现可用“批准”按钮。
4. 不要在 chat 输入 `approve APR-...`；普通 chat 文本不是审批权威，必须使用 manager 的 `Approval` UI 或审批 API。[审批边界](../architecture/security-approval-and-actions.md)

## 场景五：审批恢复与 trace/replay

1. 保留当前 run，在顶部切换为“审批员 (Approver)”；打开 `Approval`，选择对应 pending request。
2. 复核风险、action、revision 与 hash，点击“批准”并在 modal 再确认。若提示 stale，先“刷新并复核最新审批”；不要重复提交旧决定。[前端审批序列化](../../frontend/src/lib/api.ts#L339)
3. 预期信号：持久化审批决定后恢复原 run；批准分支进入 `action_draft`。如果“决定已保存但恢复未完成”，只用“重试恢复运行”，它复用同一决定而非再次审批。
4. 切回 `cs_zhang` 查看 `Trace`；manager 不能查看 support 拥有的 run，admin 可查看同 tenant run。Frontend 当前没有 Replay tab，replay 使用下方 API fallback。[trace/replay router](../../src/api/routers/traces.py)
5. 最终只应看到 demo draft：`status=not_executed_demo`、`external_side_effect=false`；不应出现“真实发券/退款/付款成功”。驳回分支则不应生成 draft。[审批集成测试](../../tests/test_approval_integration.py)

## API fallback

先获取 owner 与 reviewer token；不要打印或保存完整 token：

```bash
export BASE_URL=http://localhost:8000
export AGENT_TOKEN="$(curl -sf -X POST "$BASE_URL/api/v1/auth/token" -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=cs_zhang&password=moca2024' | jq -r .access_token)"
export MANAGER_TOKEN="$(curl -sf -X POST "$BASE_URL/api/v1/auth/token" -H 'Content-Type: application/x-www-form-urlencoded' -d 'username=mgr_li&password=moca2024' | jq -r .access_token)"
```

创建高风险请求并捕获可信标识：

```bash
WAIT="$(curl -sf -X POST "$BASE_URL/api/v1/agent/chat" -H "Authorization: Bearer $AGENT_TOKEN" -H 'Content-Type: application/json' -d '{"query":"客户投诉订单ORD-2024-002延迟发货，要求补偿600元","thread_id":"demo-high-risk"}')"
export APPROVAL_ID="$(jq -r '.data.approval_id' <<<"$WAIT")"
export RUN_ID="$(jq -r '.data.run_id' <<<"$WAIT")"
jq '{success,status:.data.status,approval_id:.data.approval_id,run_id:.data.run_id,risk_level:.data.risk_level}' <<<"$WAIT"
```

审批 body 必须从 manager 刚读取的 `decision_context` 构造，不能猜 version/hash：[当前 schema](../../src/api/schemas/approvals.py#L12)

```bash
DETAIL="$(curl -sf "$BASE_URL/api/v1/approvals/$APPROVAL_ID" -H "Authorization: Bearer $MANAGER_TOKEN")"
BODY="$(jq -c '.data.decision_context | {decision_type:"approve",expected_request_version:.request_version,expected_level_version:.level_version,expected_assignment_version:.assignment_version,expected_revision:.revision,action_payload_hash,safety_snapshot_hash}' <<<"$DETAIL")"
curl -sf -X POST "$BASE_URL/api/v1/approvals/$APPROVAL_ID/decide" -H "Authorization: Bearer $MANAGER_TOKEN" -H 'Content-Type: application/json' -d "$BODY" | jq .
```

用 run owner 读取 trace/replay，并只检查安全投影：

```bash
curl -sf "$BASE_URL/api/v1/agent-runs/$RUN_ID/trace" -H "Authorization: Bearer $AGENT_TOKEN" | jq '.data | {final_status,approvals,action_drafts,timeline}'
curl -sf "$BASE_URL/api/v1/agent-runs/$RUN_ID/replay" -H "Authorization: Bearer $AGENT_TOKEN" | jq '.data | {schema_version,final_status,timeline}'
```

## 兼容脚本说明

`scripts/demo_phase6.sh` 是保留的兼容文件名，不代表本指南按历史阶段组织。其 preflight、auth、政策问答、退款问答和高风险 query 仍可作定位线索；但当前脚本的审批步骤仍发送 legacy `{"decision":...}`，而现行 API 要求 `decision_type`、versions、revision 与 hashes。因此不要把该脚本当作当前端到端审批的权威命令；请使用本页 UI 流程或动态 API fallback。[legacy payload](../../scripts/demo_phase6.sh#L204)

## 排障入口

- Compose 启动即报 `DASHSCOPE_API_KEY must be set`：检查本机 `.env`，不要把真实 key 写入文档或提交仓库。
- UI 显示 Demo token 失败：确认 `ENABLE_DEMO_AUTH=true`、seed 已执行，并检查 `docker compose logs --tail=100 api frontend`。
- 查不到账号/订单/审批：重跑 `make seed`；`cs_zhang` 与 `mgr_li` 都绑定星河数码，所以本指南只用 `ORD-2024-001/002`。
- Evidence 为空或 provider error：先看 API log，再核对 provider key；不得用无证据回答冒充正常结果。
- 审批返回 `409`：重新 GET approval，重新人工复核最新 context；不要重放旧 body。
- Trace 返回 `403`：使用 run owner `cs_zhang` 或同 tenant `admin_user`，不要用非 owner manager token。[可见性测试](../../tests/test_trace_api.py#L101)
- 定向验证命令（不要使用裸 `pytest`）：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_seed_demo.py tests/test_approval_integration.py tests/test_trace_api.py -q --tb=short
```

## 技术讲解重点

1. 先讲“权威分层”：业务事实、政策证据、LLM 建议、审批权与动作权彼此不可替代。
2. 展示同一 request 从 SSE timeline 到 trace/replay 的可观察性，而不是只展示最终文案。
3. 用 support 不能审批、manager 受 merchant scope 约束说明 defense in depth。
4. 用 HR-01 与 frozen decision context 说明风险确定性、stale/concurrency 防护和 interrupt/resume。
5. 以 `not_executed_demo` 收尾：本演示展示的是安全、可审计的 Agent workflow，不把模拟动作描述成已上线的真实履约系统。
