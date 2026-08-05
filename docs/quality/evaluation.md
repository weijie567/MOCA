<!-- generated-by: gsd-doc-writer -->
# MOCA 当前评测与质量门禁

| 元数据 | 值 |
| --- | --- |
| 文档类型 | CURRENT |
| 描述范围 | 当前评测资产、指标阈值、执行入口与质量门禁证据 |
| 最后核验 | 2026-08-04（当前工作区） |
| 权威来源 | 当前评测脚本、golden 数据、manifest schema、测试和 Makefile |
| 更新触发 | golden 数据、指标/阈值、评测脚本、报告 schema 或 gate policy 变化 |

## 阅读边界

本文区分三种事实：golden/manifest 定义的**评测契约**、脚本定义的**通过阈值**、一次实际运行产生的**实测结果**。阈值不是成绩，manifest 能被 schema 测试读取也不等于生产门禁已经运行。

截至核验日，[`evaluation/reports/`](../../evaluation/reports/.gitkeep) 只有占位文件 `.gitkeep`，不存在 `latest.json`、`latest.md`、专项报告或 `baseline.json`。因此当前仓库**没有可引用的最新实测指标或 baseline 比较**；下文所有数值均为数据规模或代码中的门槛。

## 评测资产总览

`evaluation/golden/` 是脚本型评测数据，`eval/intent/` 与 `eval/replay/` 是 hash-owned contract/gate manifests。当前非空记录数如下：

| 资产 | 数量 | 主要用途 | 执行入口 |
| --- | ---: | --- | --- |
| [`agent_cases.jsonl`](../../evaluation/golden/agent_cases.jsonl) | 35 | 意图、工具、引用、审批与安全关键路由 | [`eval_agent.py`](../../scripts/eval_agent.py) |
| [`rag_cases.jsonl`](../../evaluation/golden/rag_cases.jsonl) | 22 | 官方 top-5 chunk 命中与 no-evidence fallback | [`eval_rag.py`](../../scripts/eval_rag.py) |
| [`phase22_hallucination_cases.jsonl`](../../evaluation/golden/phase22_hallucination_cases.jsonl) | 24 | claim/citation 支持、拒答、泄漏与 fail-closed | [`eval_phase22_hallucination.py`](../../scripts/eval_phase22_hallucination.py) |
| [`phase61_ux_cases.jsonl`](../../evaluation/golden/phase61_ux_cases.jsonl) | 15 | UX fixture 覆盖、角色、no-leak 与 caveat 约束 | [`eval_phase61_ux.py`](../../scripts/eval_phase61_ux.py) |
| [`phase62_business_query_cases.jsonl`](../../evaluation/golden/phase62_business_query_cases.jsonl) | 9 | business-query fixture、drilldown、projection/no-leak | [`eval_phase62_business_query.py`](../../scripts/eval_phase62_business_query.py) |
| [`intent-golden.v1.json`](../../eval/intent/intent-golden.v1.json) | 91 | 58 个 positive、33 个 hard-negative 的 intent contract | [`intent_manifest.py`](../../src/agent/intent_manifest.py) |
| [`release-smoke-cases.v1.json`](../../eval/replay/release-smoke-cases.v1.json) | 3 | intent、RAG claim、approval/action 的有限 smoke 引用 | manifest schema 测试；不是统计样本 |

Agent golden 的中文 substring、ID 和 FakeLLM 映射规则见 [`MATCHING_RULES.md`](../../evaluation/golden/MATCHING_RULES.md)。该文件明确限定：deterministic CI 验证 harness、fixture schema 与路由契约，不测真实模型的语言理解能力。

## 执行模式与依赖

| 入口 | 模式 | 实际执行内容 | 外部依赖 |
| --- | --- | --- | --- |
| `eval_agent.py --mode ci` | deterministic | 35 个 case 由 expected 字段构造 deterministic state；另对 4 类代表 case 编译 LangGraph，并 patch LLM/tool/knowledge 依赖 | 不调用外部模型；使用 `MemorySaver` 与内存 fake services |
| `eval_agent.py --mode live` | live graph | 每个 case 运行真实 graph、PostgreSQL checkpointer 与 DB session，记录 latency/token | PostgreSQL、seed 数据、`DASHSCOPE_API_KEY`、provider/network |
| `eval_rag.py` | DB/provider-backed | 固定 `top_k=5` 检索，按 expected chunk 或 fallback 状态评分 | 活动 tenant、policy chunks、PostgreSQL/pgvector、DashScope embedding |
| `eval_all.py` | mixed | 先跑 RAG，再跑 Agent；默认 Agent 为 `ci`，两者都 pass 才整体 pass | 默认仍因 RAG 需要 DB 与 embedding provider |
| hallucination 脚本 | local deterministic | 19 个 local fixture + 5 个 `production_verifier` fixture 路径；后者使用真实 ContextBuilder/verifier，但 canonical rows 来自 golden adapter | 不调用 live LLM/provider，不需要生产 DB |
| UX / business-query 脚本 | fixture validation | 校验类别、字段、角色、drilldown、no-leak 和禁止 raw payload；错误即非零退出 | 不执行 Agent graph、数据库或模型 |
| Playwright | mocked / live UI | mocked desktop/mobile，或 live backend；full-live prompt matrix 另需显式开关 | Node/browser；live/full-live 依赖后端，full-live 还依赖 provider |

Agent CI 的 `FakeLLM`、patched graph harness 与 live 分支分别见 [`eval_agent.py`](../../scripts/eval_agent.py#L68-L86)、[`eval_agent.py`](../../scripts/eval_agent.py#L759-L840) 和 [`eval_agent.py`](../../scripts/eval_agent.py#L950-L992)。CI case scorer 直接从期望值构造 state，所以它不能替代 live-model accuracy 或端到端数据质量验证。

RAG 评测会调用 [`EmbeddingService`](../../src/rag/embedder.py#L12-L67)，缺 provider key 会失败；`--diagnostic-top-k` 只扩展失败诊断，官方评分仍固定 top 5。统一入口只合并 Agent 与 RAG，不会自动运行 hallucination、UX、business-query、intent/replay manifest 或前端 E2E（[`eval_all.py`](../../scripts/eval_all.py#L32-L59)）。

## 指标与阻断阈值

### Agent 与 RAG

| 评测 | 阻断指标 | 当前默认阈值 | 判定 |
| --- | --- | ---: | --- |
| Agent | `intent_accuracy` | `>= 0.90` | 35 个 case 的 intent exact match 比例 |
| Agent | `tool_selection_accuracy` | `>= 0.85` | expected tools 必须是实际 tools 的子集 |
| Agent | `citation_rate` | `>= 0.85` | 有 expected evidence 的 case 中至少命中一个 doc key |
| Agent | `safety_critical_pass_rate` | `= 1.00` | approval/permission 安全类别必须整例通过 |
| RAG | `hit_at_5` | `>= 0.85` | 非 fallback case 的 expected chunk top-5 命中率 |
| RAG | `fallback_accuracy` | `>= 0.85` | fallback case 必须返回 `no_evidence` |

Agent 还报告 `task_completion_rate`、`approval_accuracy`、平均 latency、tokens 和 per-category rate，但当前 `_passes_thresholds()` 不用这些字段阻断；deterministic graph contract failure 会额外令整份 Agent report 失败（[`eval_agent.py`](../../scripts/eval_agent.py#L1125-L1224)）。RAG 的 `--threshold` 会同时覆盖两个默认 `0.85` 门槛（[`eval_rag.py`](../../scripts/eval_rag.py#L31-L47)）。

### Hallucination control

| 指标 | 阈值 |
| --- | ---: |
| `claim_support_accuracy` / `citation_support_accuracy` | `>= 0.95` |
| `refusal_manual_review_routing_accuracy` | `>= 1.00` |
| `unsafe_answer_rate` / `business_data_hallucination_rate` | `<= 0.00` |
| `leakage_count` | `<= 0` |
| `fail_closed_rate` | `>= 1.00` |

脚本另记录 level-3 trigger、timeout 和 case count，但它们不是 blocking threshold。只有带 `--fail-thresholds` 时，report 的 `status=fail` 才转成 shell exit 1；门槛来源是 [`src/agent/rag_context/metrics.py`](../../src/agent/rag_context/metrics.py#L19-L43)。UX 与 business-query validator 没有数值阈值，契约错误列表必须为空。

## Intent 与 Replay gate manifests

| Gate 层 | 当前资产事实 | 当前能证明什么 | 不能证明什么 |
| --- | --- | --- | --- |
| intent contract | dataset/coverage/consistency hash 一致；每个 ordinary intent 至少 5 positive + 3 hard-negative | fixture 完整性、deterministic helper 与路由契约 | live classifier accuracy |
| intent statistical release | 4 个安全敏感类别要求每类 `n >= 300`、observed false negatives 为 `0`，且单侧 95% Wilson false-negative upper `<= 0.01` | 公式与 schema 已实现 | corpus 尚未收集，状态为 `statistical_gate_not_demonstrated` |
| Replay dev-contract | 9 类 gate、14 个 forbidden-behavior case、coverage matrix hash 与具体 test paths | schema/hash、redaction、权限、事件顺序及禁行路径的 deterministic backstops | release-scale 统计表现 |
| Replay release | 3 个 smoke reference；每项 required min `300`、`statistical_n=0` | manifest 格式和缺口被显式记录 | 当前 coverage 为 incomplete，不是已通过 release gate |
| Replay monitoring | 6 个 metric schema，状态仅 `pending` 或 `sample_only` | 未来 telemetry 的字段与状态契约 | 没有生产聚合、趋势或自动 degrade 证据 |

Replay release manifest 当前把 `intent_hard_negatives`、`rag_claim_support`、`approval_action_safety` 三项的 `required_min_n` 都固定为每项 `300`。这是 release-scale 数据集契约，不是当前测量结果；三个 metric 的 `statistical_n` 都是 `0`，少量 smoke case 不能让 gate 通过。Intent 的 per-class zero-false-negative、Wilson upper 与 coverage precedence 仍以 [`contract-spec.md` §11.4](../contract-spec.md#114-confidence-threshold-and-calibration) 为详细权威来源。

Intent release 状态见 [`m6-statistical-gate.v1.json`](../../eval/intent/m6-statistical-gate.v1.json)，hash/覆盖和 Wilson 判定由 [`intent_manifest.py`](../../src/agent/intent_manifest.py#L112-L258) 校验。Replay 三层资产见 [`dev-contract-manifest.v1.json`](../../eval/replay/dev-contract-manifest.v1.json)、[`release-gate.v1.json`](../../eval/replay/release-gate.v1.json) 与 [`monitoring-gate.v1.json`](../../eval/replay/monitoring-gate.v1.json)。对应测试明确把 release/monitoring 视为格式契约，而非已经证明的生产门禁（[`test_phase35_release_monitoring_manifests.py`](../../tests/eval/test_phase35_release_monitoring_manifests.py)）。

## 运行入口

Agent deterministic 评测不需要 live provider：

```bash
make eval-agent
```

DB/provider-backed 入口应先准备 Python `>=3.12`、依赖、PostgreSQL/pgvector、迁移与 seed，并配置 `DASHSCOPE_API_KEY`：

```bash
uv sync --extra dev
docker compose up --build -d
make migrate
make seed
make eval-rag
make eval
make eval-live
```

`make eval` 默认是 RAG + deterministic Agent；`make eval-live` 才把 Agent 切到 live。命令映射以 [`Makefile`](../../Makefile) 为准，运行时版本与 pytest/ruff 配置见 [`pyproject.toml`](../../pyproject.toml)。

专项 deterministic 入口不会被 `make eval` 自动包含：

```bash
uv run python scripts/eval_phase22_hallucination.py --fail-thresholds --output evaluation/reports/phase22_hallucination_eval.json
uv run python scripts/eval_phase61_ux.py
uv run python scripts/eval_phase62_business_query.py
```

评测 contract、架构静态门禁和 intent manifests 可用项目虚拟环境入口验证：

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/ tests/architecture/ tests/agent/test_intent_manifest.py tests/agent/test_intent_golden_contract.py -q --tb=short
uv run ruff check .
uv run ruff format --check .
```

`tests/architecture/` 不是模型质量分数，而是源码结构门禁。Replay-by-rerun 检查扫描 replay-owned Python 与 traces router；并行事件 envelope 和真实外部执行 surface 检查扫描全部 `src/**/*.py`；“物理独立服务”标记则检查部署文件以及 Replay 文档/manifest。三者扫描面不同（[`test_phase35_replay_eval_boundaries.py`](../../tests/architecture/test_phase35_replay_eval_boundaries.py)）。

前端验证是独立 Node 工具链，不在当前 backend CI workflow 中：

```bash
cd frontend
npm test
npm run e2e
npm run e2e:live
```

`npm run e2e` 运行 mocked desktop/mobile；`e2e:live` 启动或连接真实后端。完整 provider prompt matrix 还要求 `MOCA_E2E_FULL_LIVE=1`（[开关读取](../../frontend/e2e/agent-console.spec.ts#L391-L392) · [`frontend/package.json`](../../frontend/package.json) · [`playwright.config.ts`](../../frontend/playwright.config.ts)）。

## 报告、baseline 与当前门禁状态

单项默认写入 `agent_eval.json`、`rag_eval.json`、UX/business-query JSON；hallucination 只有传 `--output` 才落盘。统一入口生成 `latest.json` 与 `latest.md`，`--timestamp` 额外写时间戳版本，`--save-baseline` 把本次 JSON 复制为 `baseline.json`（[`eval_all.py`](../../scripts/eval_all.py#L184-L224)）。

Baseline comparison 只是报告注释：它逐个比较数值、列出 regressions/improvements，不改变 `overall_status`，也没有 per-metric direction/tolerance policy。保存 baseline 前应人工确认本次 `overall_status=pass`，因为复制动作本身不要求 pass。

| 门禁面 | 仓库中的真实状态 |
| --- | --- |
| Backend CI | push/PR 到 `main` 时运行 `uv run ruff check .`、`uv run ruff format --check .` 和带 PostgreSQL service 的 `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short` |
| Eval scripts | 各脚本具备非零退出语义和 Makefile 入口，但当前 CI workflow 没有单独调用 `make eval*` |
| Dev-contract manifests | 对应 schema/hash/forbidden-behavior tests 位于默认 `tests/` 范围，属于当前静态/deterministic backstop |
| Release statistical gates | Intent 与 Replay 的 release-scale corpus/统计证据均未证明 |
| Monitoring gate | 只有 pending/sample-only schema，没有当前生产 report |
| UI/E2E | Vitest/Playwright 入口存在，但不在当前 backend CI workflow |

CI 事实源是 [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)；不要用 manifest 中的 `blocking` 字段反向宣称外部发布系统或生产监控已经接线。

## 维护规则

- 修改 golden 数据时重新核对非空 case 数、required categories、hash-owned manifest 和真实执行入口。
- 修改阈值时同步脚本常量、report schema、本文表格以及门禁测试；不要用历史 report 值替换 threshold。
- 评测结果必须附 mode、dataset/hash、命令、环境前提和生成时间；deterministic 与 live 结果不可混称。
- 新增专项 evaluator 时显式决定是否纳入 `eval_all.py`、Makefile、CI、release 或 monitoring，而不是仅新增脚本。
- `evaluation/reports/` 没有新产物时，文档必须继续声明“无当前实测报告”，不得从旧文档推断成绩。
