# MOCA RAG 文档质量与检索优化计划

| 属性 | 内容 |
| --- | --- |
| 文档性质 | 进行中计划；描述目标态和实施顺序，不代表全部能力已经实现 |
| 当前焦点 | 格式等价评测基础（Format Parity Evaluation Foundation） |
| 当前状态 | 3 份 canonical 政策及 9 个格式 fixture 已准备；gold、evaluator 和 baseline 待建设 |
| Phase 状态 | 应独立立项；正式编号尚未写入 `.planning/ROADMAP.md` |
| 最后更新 | 2026-08-05 |

## 1. 计划目标

本计划的目标是把 MOCA 当前以短 Markdown demo 为主的政策知识库，升级为一条结构感知、来源可追溯、检索策略可比较、质量收益可量化的 RAG 流程。

目标链路如下：

```text
Markdown / 数字 PDF / 扫描 PDF / DOCX
                ↓
      格式识别、原生解析与 OCR
                ↓
     统一 Block、确定性清洗与溯源
                ↓
 Section / Procedure / Table / Parent-child Chunking
                ↓
 Dense + Sparse + Fuzzy 多路召回
                ↓
          RRF 融合与 Rerank
                ↓
       证据组装、回答与来源引用
                ↓
 Parser / Retrieval / Answer 分层评测
```

计划完成后，MOCA 应当能够回答四个问题：

1. 同一政策换成不同文件格式后，关键事实、表格和来源信息是否仍然完整。
2. 多份相似政策同时入库时，正确证据是否能够稳定进入 Top-K。
3. 调整清洗、Chunking、检索或重排策略后，质量究竟提高还是下降。
4. 文档、Chunk、页码和表格来源能否支持回答引用、问题定位与结果复现。

## 2. 范围边界

### 2.1 当前范围

- Markdown、数字 PDF、扫描 PDF 和 DOCX。
- 标题、正文、列表、操作步骤和普通表格。
- PDF 页码、bbox、OCR 置信度、表格元数据和 source block 引用。
- 确定性文本清洗、页眉页脚处理、错误换行和英文断词修复。
- Section-aware、procedure-aware、table-aware 和 parent-child Chunking。
- Dense、sparse、fuzzy、RRF、query rewrite 和 reranker 的组合评测。
- tenant、文档类型、有效时间和版本等可信过滤条件。
- parser parity、retrieval parity、mixed retrieval 和端到端引用评测。

### 2.2 当前不做

- XLS、XLSX、PPT 或 PPTX 文件解析。
- 特定行业术语库、行业参数模型和结构化工程参数索引。
- 复杂公式识别、工程图纸解析和通用图片语义理解。
- 为展示格式数量而引入与 MOCA 政策知识库无关的 parser。
- 在缺少 baseline 的情况下直接凭经验调整 Chunk 大小或检索权重。

“表格支持”指保留 PDF、DOCX 和 Markdown 文档中的表名、表头、数据行、单位、说明和来源位置，不等同于实现 Excel 工作簿处理。

## 3. 当前仓库基线

### 3.1 已有能力

当前代码已经具备以下基础：

- Parser registry 支持 Markdown、纯文本、PDF、DOCX 和图片输入。
- PDF 支持数字文本解析，并在缺少可用文字层时进入 OCR fallback。
- Parsed block 可以携带页码、bbox、表格、OCR 和 parser provenance。
- Block chunker 已经能够按标题组织正文，并对表格执行行组切分和表头重复。
- 检索链路已经包含 dense、sparse、fuzzy、RRF、query rewrite 和 reranker。
- 现有 RAG golden 集包含 22 个 case，当前官方门槛包括 Hit@5 和 fallback accuracy。

这些能力是后续改造的基础，不代表格式等价、复杂表格、长文档混合检索和 Chunk 消融已经得到评测证明。

### 3.2 已准备的格式等价语料

[`evaluation/rag_sources/`](../../evaluation/rag_sources/README.md) 当前包含 3 个 canonical 政策族：

1. 国内普通实物订单退款与退货。
2. 质量问题与补偿审批。
3. 跨境订单与数字商品退款例外。

每个政策族包含：

- 1 份 Markdown source of truth；
- 1 份约 5 页的数字 PDF；
- 1 份约 5 页、无文字层的扫描 PDF。

合计 9 个 fixture。当前 [`format_parity_manifest.jsonl`](../../evaluation/rag_sources/format_parity_manifest.jsonl) 记录逻辑文档、variant、路径、checksum、页数和文字层统计。

### 3.3 当前缺口

- 9 个 fixture 尚未拥有正式 parser gold 和 retrieval gold。
- 尚无独立 parser parity evaluator。
- 尚无按照固定 tenant、固定 doc key、分轮重置执行的 retrieval parity runner。
- [`evaluation/reports/`](../../evaluation/reports/.gitkeep) 尚无可以引用的格式等价 baseline。
- `data/policies/` 仍然是 demo/smoke corpus，不能替代正式 mixed retrieval 数据集。
- 当前 Chunking 仍以统一 block chunk 流程为主，尚未形成可切换的策略注册表。

## 4. 评测和数据设计原则

### 4.1 一份物理文件池，两套数据定义

文件只保存一份，通过 manifest 组成不同评测集：

```text
evaluation/rag_sources/
├── fixtures/
├── format_parity_manifest.jsonl
└── mixed_retrieval_manifest.jsonl    # 后续新增
```

- `format_parity_manifest.jsonl` 定义同内容、不同格式的等价关系。
- `mixed_retrieval_manifest.jsonl` 定义一轮中需要同时入库的不同政策。
- 同一个物理文件可以被两个 manifest 引用。
- mixed retrieval 中，一个逻辑政策只能选择一个格式 variant，不能把三份等价文件同时入库。

### 4.2 Parser parity 与 Retrieval parity 分离

Parser parity：

- 直接调用 parser。
- 不需要 tenant、数据库、embedding 或外部 provider。
- 比较关键文本、标题、表格、页码、OCR 和 warning。

Retrieval parity：

- 使用固定 evaluation tenant。
- 同一 canonical 政策的三个 variant 使用相同 `doc_key`。
- Markdown、数字 PDF、扫描 PDF 分三轮摄取。
- 每轮开始前重置一次性测试数据库或独立 evaluation run。
- 每轮执行完全相同的问题和 gold 判断。

### 4.3 Gold 不绑定 Chunk ID

格式不同或 Chunk 策略变化时，Chunk ID 和边界可能变化。因此新的 parity gold 应绑定：

- canonical policy ID；
- expected section；
- expected evidence anchors；
- 表名、表头或关键数据行；
- 必要时的页码约束；
- 可判定的 no-answer 条件。

现有依赖 expected chunk ID 的 RAG golden 保留用于历史回归；新的 parity/mixed gold 使用语义证据，不直接替换旧基线。

### 4.4 一次只改变一个变量

优化实验依次改变：

```text
Baseline
→ 清洗策略
→ Chunk 大小
→ 标题上下文
→ 表格行组
→ Parent-child
→ 召回通道
→ RRF 参数
→ Reranker
```

每轮必须记录配置、数据集版本、embedding/reranker 版本、指标、延迟和失败案例，避免无法解释组合改动带来的结果。

## 5. 实施阶段

### 阶段 A：格式等价评测基础（当前焦点）

#### 目标

让现有 3 份 canonical 政策和 9 个 fixture 形成第一条可复现的 parser/retrieval parity 闭环，并产出第一份 baseline 报告。

#### 建议拆分

##### A1. 评测契约与 Gold

交付：

- parser parity gold schema 和数据；
- retrieval parity gold schema 和数据；
- 每个主题 8～12 个关键解析锚点；
- 每个主题 6～8 个检索问题；
- 表格、例外、金额/时间、跨章节和 no-answer 覆盖；
- schema validation tests。

每个 canonical 主题只维护一份事实 gold，三种格式共享。格式特有约束，例如 PDF 页码，可以作为可选 expectation，而不是复制三份完整答案。

##### A2. Parser Parity Evaluator

交付：

- 直接读取 format parity manifest；
- 逐 variant 调用 parser；
- 统计 parse success、anchor recall、标题、表格、页码、OCR 和 warning；
- 扫描 PDF 仅在匹配阶段进行空白规范化，不修改原始证据；
- JSON 和 Markdown 报告。

##### A3. Retrieval Parity Evaluator

交付：

- 一次性 evaluation tenant 或测试数据库隔离；
- 同 doc key 分轮摄取和清理；
- 相同 query 集运行 Markdown、数字 PDF 和扫描 PDF；
- 统计 Hit@1、Hit@3、Hit@5、MRR 和 evidence anchor coverage；
- 记录 parser、OCR、Chunking、embedding、融合或 rerank 的失败归因入口。

##### A4. Baseline 与回归门禁

交付：

- 第一份格式等价 baseline JSON/Markdown；
- 按主题、格式、问题类别展开的失败表；
- 可重复运行的命令和环境前提；
- 初始回归门槛；
- 是否进入阶段 B 的书面结论。

#### 初始完成标准

- 9 个 fixture 全部成功解析。
- Markdown 和数字 PDF 的关键事实锚点命中率为 100%。
- 扫描 PDF 在匹配空白规范化后，关键锚点命中率不低于 95%。
- 所有关键表头和关键数据行得到保留。
- PDF 关键证据能够追溯到页码。
- retrieval evidence Hit@5 不低于 90%。
- 三种格式之间的 Hit@5 差距不超过 10 个百分点。
- 所有失败均能落入明确类别，而不是只输出总分。

这些数值是第一版目标门槛。第一次 baseline 运行后，如需调整，必须同时记录数据、原因和新旧门槛，不能静默修改。

### 阶段 B：混合检索语料与基线

#### 目标

评测多份长政策、相似政策、不同版本和干扰文档同时存在时的真实召回与排序能力。

#### 数据规模

- 20～30 份内容不同的政策文档。
- 普通文档约 3～6 页，核心政策约 5～10 页，少量长文档约 10～15 页。
- 可以复用 parity 文件池中的 3 个文件，但每个政策族只选一个 variant。
- 现有短 Markdown demo 可以作为内容种子，扩充后才进入正式 mixed corpus。
- 60～100 个 gold query，覆盖直接规则、例外、金额/时限、表格、流程、跨章节、版本冲突和无答案。

#### 交付

- `mixed_retrieval_manifest.jsonl`；
- mixed retrieval gold；
- 文档版本和近似干扰设计；
- mixed retrieval baseline；
- 按问题类型和文档格式切片的指标报告。

### 阶段 C：解析、清洗和表格保真

#### 目标

统一不同 parser 的输出，让引用证据保持原文忠实，同时生成独立的检索派生文本。

#### 重点工作

- 明确 raw、normalized 和 search 三层文本职责。
- 恢复标题层级、段落和阅读顺序。
- 识别重复页眉、页脚和页码。
- 修复错误换行和英文断词。
- 保留金额、日期、比例、否定词、政策编号和风险等级原值。
- 为表格保存表名、表头、数据行、说明、页码和 source block。
- 对 OCR 低置信度内容标记质量，而不是静默猜测或覆盖。
- 在 V1 parity 稳定后，为 DOCX 增加对应结构保真回归；不扩大为 XLSX/PPTX 支持。

#### 数据职责

```json
{
  "raw_text": "解析器原始结果",
  "normalized_text": "确定性清洗结果",
  "search_text": "标题和结构上下文增强后的检索文本"
}
```

只有 `raw_text` 或可验证的 canonical 内容可以作为最终引用证据；`search_text` 只用于召回，不能冒充原文。

### 阶段 D：结构感知 Chunking

#### 目标

将当前统一 block chunk 流程演进为可配置、可对比的 Chunk 策略，同时保持稳定的来源引用。

#### 策略

- `section_aware`：按标题层级和段落边界切分。
- `procedure_aware`：尽量保持前置条件、注意事项、步骤、例外和处理结果完整。
- `table_aware`：生成表级 Chunk 和重复表头的行组 Chunk。
- `parent_child`：小 Chunk 用于检索，大 Parent 用于回答上下文。

建议第一轮消融配置：

| 配置 | 子 Chunk 目标 | 最大长度 | Overlap | Parent |
| --- | ---: | ---: | ---: | ---: |
| Small | 500 | 800 | 80 | 无 |
| Medium | 800 | 1200 | 100 | 无 |
| Large | 1200 | 1800 | 150 | 无 |
| Parent-child | 300～500 | 800 | 按结构 | 1200～2000 |

最终参数由 parity 和 mixed retrieval 指标决定，不将表中建议值直接视为生产最优值。

### 阶段 E：混合检索和重排优化

#### 目标

在保留现有 dense、sparse、fuzzy、RRF、query rewrite 和 reranker 架构的基础上，提高正确证据召回和排序质量。

#### 重点工作

- 查询规范化和可信 metadata filter。
- 政策名称、编号、金额、天数、比例和日期的精确词法召回。
- 标题路径、表名和表头进入 retrieval-only `search_text`。
- 多路召回候选规模和 RRF 参数消融。
- Top-N reranker 的收益、延迟和 fallback 评测。
- 同一文档相邻 Chunk 合并、父 Chunk 扩展和重复结果抑制。
- 新旧政策版本选择和失效文档过滤。
- OCR 低质量证据降权和 no-evidence 阈值。

候选召回阶段主要优化 Recall；重排、去重和证据选择阶段主要优化 Precision。

### 阶段 F：端到端评测和生产门禁

#### 目标

形成能够定位回归来源的分层指标，并让 parser、Chunking 或 retrieval 变化都必须通过同一套质量门禁。

#### 指标层次

| 层次 | 核心指标 |
| --- | --- |
| Parser | parse success、anchor recall、标题/表格保留率、页码准确率、OCR 质量 |
| Chunk | evidence containment、表头携带率、步骤完整度、冗余率、平均长度 |
| Retrieval | Recall@5/10、Precision@5、MRR、nDCG、正确版本命中率 |
| Answer | answer correctness、context precision/recall、faithfulness、引用准确率、拒答率 |
| Engineering | ingestion/retrieval/rerank latency、embedding 数量、token 和 OCR 成本、失败率 |

#### 生产化收尾

- ingestion 幂等和可恢复重试；
- parser、OCR、Chunk strategy、embedding 和 reranker 版本记录；
- 文档重解析与索引重建；
- 低质量文档阻止入库或进入人工检查；
- tenant 隔离、版本替换和失效文档测试；
- baseline comparison 和回归阻断策略；
- 评测报告记录命令、数据集 hash、运行模式、环境和生成时间。

## 6. Phase 关系与建议拆分

这项工作应独立立项，不能回填到已经交付的历史 RAG Phase，也不应混入当前 Phase 64.2。

Phase 64.2 正在处理证据身份、重摄取、不可变回放和记忆 provenance；格式轮换摄取和引用比较依赖这些身份语义稳定。因此，第一项 RAG 质量 Phase 应依赖 Phase 64.2，但不改变 Phase 64.2 的既定范围。

如果该计划在 Phase 64.2 之后立即执行，可以作为插入的 Phase 64.3；如果保持当前 Phase 65～71 的既定顺序，则作为 Phase 72 或后续新 milestone 的第一项。正式编号和依赖调整必须单独更新 `.planning/ROADMAP.md`，本文不擅自修改当前 roadmap 状态。

不应把阶段 A～F 写成一个巨大 PLAN。建议的 phase-level 切分是：

1. RAG Format Parity Evaluation Foundation。
2. RAG Mixed Retrieval Corpus And Evaluation。
3. RAG Parsing, Cleaning And Table Fidelity。
4. RAG Structure-aware Chunking Optimization。
5. RAG Retrieval Quality Optimization。
6. RAG End-to-End Quality Gates。

每个 Phase 再按契约、实现、集成和验证拆成多个编号 plan，避免数据集、parser、数据库、Chunking、retrieval 和报告门禁在一个 plan 中同时大改。

## 7. 建议目录

```text
evaluation/
├── rag_sources/
│   ├── fixtures/
│   ├── format_parity_manifest.jsonl
│   └── mixed_retrieval_manifest.jsonl
├── golden/
│   ├── rag_parser_parity.jsonl
│   ├── rag_retrieval_parity.jsonl
│   └── rag_mixed_retrieval.jsonl
└── reports/
    ├── rag_format_parity_baseline.json
    ├── rag_format_parity_baseline.md
    └── rag_mixed_retrieval_baseline.json

scripts/
├── eval_rag_parser_parity.py
├── eval_rag_retrieval_parity.py
└── eval_rag_mixed_retrieval.py
```

目录是目标布局；不存在的文件均为计划交付物，不表示当前仓库已经具备。

## 8. 总体完成定义

满足以下条件后，可以认为本计划完成：

- Markdown、数字 PDF、扫描 PDF 和 DOCX 进入统一的可追溯解析与 Chunking 流程。
- PDF、DOCX 和 Markdown 中的关键表格能够保留表头、数据行和来源语义。
- 同一 canonical 政策的不同格式在 parser 和 retrieval 指标上达到约定等价门槛。
- 20～30 份长短不一、含版本和干扰项的政策同时入库后，检索指标达到正式门槛。
- 正文、表格、流程、跨章节、版本冲突和 no-answer 问题都有对应 gold。
- Chunking、融合和 reranker 的每项优化都有独立消融结果。
- 回答能够引用正确文档、章节和 PDF 页码；证据不足时能够安全拒答。
- parser、Chunking、embedding 或 retrieval 配置变化能够通过自动 baseline comparison 发现回归。

## 9. 下一执行入口

当前只执行阶段 A。下一步依次是：

1. 为三个 canonical 主题定义 parser/retrieval gold schema。
2. 编写每个主题的解析锚点和 6～8 个检索问题。
3. 实现无数据库依赖的 parser parity evaluator。
4. 实现固定 tenant、同 doc key、分轮重置的 retrieval parity evaluator。
5. 生成并审查第一份格式等价 baseline。
6. 根据失败归因决定进入 parser/cleaning 修复，还是开始阶段 B 的 mixed corpus。

在 baseline 生成前，不开始 Chunk 参数、检索权重或 reranker 的主观调优。
