# MOCA RAG 架构 Spec 与 Hallucination Control

> 状态：目标架构 spec。本文基于当前 MOCA 仓库代码、既有 contract 文档和前期 RAG 参考仓库调研整理。
>
> 契约边界：`docs/contract-spec.md` 是 MOCA 当前已接受契约的主要参考源。本文用于定义 RAG 子系统的目标设计、分层责任、演进路线和 hallucination control 要求；当本文与 `docs/contract-spec.md` 冲突时，后续 phase plan 必须显式提出 spec delta、MVP scope 或 defer 决策，不能静默偏离。
>
> 当前结论：MOCA 当前阶段采用 PostgreSQL + pgvector + PostgreSQL full-text + pg_trgm 构建生产形态的小型 RAG 后端；Vespa/OpenSearch 只保留为未来可替换 search backend，不进入当前实现主线。

## 1. 目标

MOCA 的 RAG 子系统不是 demo 级 `embedding + top_k + prompt`，而是客服系统中的可信知识能力。它必须服务于：

- Policy QA：政策问答，强 citation，是主能力。
- FAQ QA：高频问题回答，允许更短上下文，但仍需引用来源。
- Troubleshooting：结合业务事实和政策证据做多步判断。
- Business Data QA：订单、退款、账户、工单等结构化数据查询；该能力必须走 business tool/API/SQL，不走 RAG 猜测。
- 多语言：中文和英文都可支持，但中文必须有应用层分词和领域词典。
- 权限：multi-tenant、RBAC、merchant scope、document ACL 必须在检索前生效。

RAG 的核心目标不是“让模型看更多资料”，而是为每个关键结论构建可追溯、可校验、权限正确、时效正确的 evidence chain。

## 2. 当前仓库基线

当前实现已经有 RAG 的最小闭环，但仍偏 MVP。

| 能力 | 当前代码 | 当前事实 | 生产级缺口 |
| --- | --- | --- | --- |
| 文档 ingestion | `src/rag/ingestion.py` | 读取 UTF-8 文本文件；调用 `chunk_markdown`；embedding 后 delete/insert chunks；文档变更时 bump version | 不支持 PDF、Word、图片、OCR、layout、表格、异步状态机、parser version、ingestion audit |
| chunking | `src/rag/chunker.py` | Markdown `##`/`###` 标题切分；超长段按中文标点和字符 overlap 拆分 | 不支持 layout block、表格原子块、标题路径继承、token 计数、source block/page/bbox |
| embedding | `src/rag/embedder.py` | DashScope `text-embedding-v4`，OpenAI-compatible client，默认 1024 维 | 缺 embedding model/version 持久化、重建策略、批处理状态、失败恢复 |
| 数据模型 | `src/db/models.py` | `PolicyDocument`、`PolicyChunk`；chunk 有 `embedding vector(1024)`、tenant/doc/effective_date/risk_level | 缺 `search_text`、`tsvector`、trgm、language、ACL、page/bbox、source block、token_count、parser/OCR metadata |
| 索引 | `src/db/migrations/versions/002_rag_pipeline.py` | pgvector HNSW index；chunk_id index | 缺 full-text GIN、pg_trgm GIN、metadata/filter 复合索引 |
| 检索 | `src/knowledge/retrieval.py` + `src/repositories/policy_chunk_repo.py` | pgvector dense retrieval；metadata filter；轻量 query overlap rerank；threshold 控制 strong/partial/no evidence | 缺 sparse retrieval、trgm fallback、RRF fusion、query rewrite、cross-encoder/API rerank、conflict/freshness ranking |
| Knowledge facade | `src/knowledge/service.py` | `PolicyKnowledgeService.search`；merchant scope deny-all；partial/no evidence contract | 需要迁移到可插拔 `SearchBackend`，并扩展 hybrid tracing |
| citation | `src/knowledge/schemas.py` + `src/knowledge/citation.py` | `EvidenceRefV1`、`text_hash`、membership-only citation validation | 缺语义支持校验、逐 claim 支持关系、page/bbox 引用、冲突/过期证据标记 |
| Context assembly | `src/agent/context/assembler.py` | 已有 prompt block、priority、protected blocks；policy refs 可进入 protected context | 需要 RAG 专用 Context Builder，负责证据去重、token budget、citation map、冲突标记 |
| 生成约束 | `src/agent/prompts.py` + `src/agent/nodes/recommendation_generation.py`（共享实现仍在 `generate_recommendation.py`） | prompt 要求引用 evidence；生成后做 membership validation；失败时 `citation_invalid` 或 `insufficient_evidence` | 需要更强“只基于证据回答”、semantic verifier、高风险后置核查 |
| eval | `scripts/eval_rag_hit_at_5.py`、`eval/golden_rag_queries.jsonl`、`tests/test_rag_eval.py` | Hit@5、fallback accuracy、retrieval status 测试 | 需要 faithfulness、context recall、citation accuracy、permission safety、freshness correctness、hallucination rate |

## 3. 范围与非目标

### 3.1 当前目标规模

当前架构按以下规模优化：

- Phase 1：500-2000 chunks。
- 扩展阶段：5k-20k chunks。
- 压测模拟：50k+ chunks。

在该规模下，PostgreSQL + pgvector + full-text + pg_trgm 足够支撑生产形态的小型版本。

### 3.2 非目标

- 当前不引入 Vespa 作为主存储或主检索服务。
- 当前不引入 Elasticsearch/OpenSearch 作为必选依赖。
- 当前不把 LlamaIndex/LangChain RAG framework 作为核心抽象层；可以局部借鉴 splitter、parser、reranker 思路，但 MOCA 的 contract 和数据模型自管。
- Business Data QA 不通过 RAG 回答具体订单/退款/账户事实。

### 3.3 Vespa 兼容策略

Vespa 不是 OCR/parser，也不是事实源。未来如果 chunk 数、延迟或复杂 ranking profile 超出 PostgreSQL 承载范围，Vespa 可以作为 external search index：

- PostgreSQL 继续是 canonical source of truth。
- Vespa 保存 chunk/index copy，用于大规模 BM25、ANN、hybrid ranking profile。
- 上层只依赖 `SearchBackend` interface，不直接依赖 pgvector 或 Vespa。

## 4. 目标架构总览

```text
User Query
  -> TrustedContext / Auth Scope
  -> Query Router
      - intent classification
      - language detection
      - permission context projection
      - route: policy / faq / order / troubleshooting / action
  -> Retrieval Orchestrator
      - query normalization
      - optional query rewrite
      - language-specific tokenizer
      - search backend fan-out
  -> SearchBackend(Postgres)
      - dense retrieval: pgvector
      - sparse retrieval: PostgreSQL full-text
      - fuzzy retrieval: pg_trgm
      - mandatory pre-filter: tenant/RBAC/ACL/effective_at
  -> Hybrid Fusion
      - RRF by rank
      - metadata/freshness/authority adjustments
  -> Reranker(optional)
      - cross-encoder or rerank API
  -> Context Builder
      - evidence re-fetch
      - text_hash verification
      - dedup
      - token budget
      - citation map
      - conflict/freshness labels
  -> LLM Generator
      - structured answer/draft
      - mandatory citation for policy claims
  -> Evidence Verifier(optional/high-risk required)
      - citation membership
      - semantic support
      - conflict/staleness/permission check
  -> Final Response / Manual Review / Refuse
```

Ingestion 侧独立成流水线：

```text
Raw file upload/import
  -> ingestion job
  -> parser/OCR
  -> parsed blocks
  -> cleaning/normalization
  -> semantic chunking
  -> search_text/tokenization
  -> embedding
  -> PostgreSQL write
  -> hybrid index ready
```

### 4.1 Contract 与 implementation 分层

RAG 子系统必须区分“长期稳定的领域契约”和“当前实现策略”。

RAG 子系统目标内部契约收敛为 4 个。它们是本 spec 的设计目标，不表示已经写入 `docs/contract-spec.md` 成为全局 normative contract；跨 phase 消费前必须再同步进 `docs/contract-spec.md`：

- `DocumentBlock`
- `Chunk`
- `Evidence`
- `MaterialClaim`

其他对象不作为 core contract，而是 view / projection / debug artifact：

- `EvidenceRefV1`：现有 `docs/contract-spec.md` 定义的跨层 canonical evidence identity；runtime `Evidence` 必须包含 `ref: EvidenceRefV1`，但不得替代或弱化它。
- `SearchRequest` / `SearchHit`：retrieval runtime DTO，用于 backend 调用和 trace，不是领域核心对象。
- `ClaimVerificationResult`：verifier 输出视图，不独立成为上游依赖的核心对象。
- `ParserTrace` / `DocumentTable`：debug、review、OCR/table 质量追踪 artifact，可从 `DocumentBlock` 派生或关联。

可替换实现：

- Parser/OCR backend。
- 中文 tokenizer。
- embedding model。
- PostgreSQL dense/sparse/fuzzy SQL。
- RRF 参数。
- reranker provider。
- future Vespa/OpenSearch backend。

这样设计的原因是：PostgreSQL hybrid、某个 OCR 引擎或某个 reranker 都只是当前实现选择；而 document-to-chunk、chunk-to-evidence、evidence-to-claim 的链路应该在 RAG 子系统内部保持稳定。未来替换 search backend 或 parser backend 时，不应该牵动 Agent、approval、action snapshot 和 eval 的上层契约。

### 4.2 三个核心 kernel

RAG 子系统按 3 个 kernel 组织，而不是按工具/框架堆叠。

```text
Knowledge Kernel
  RawDocument -> DocumentBlock -> Chunk

Retrieval Kernel
  Chunk -> Evidence

Reasoning Kernel
  Evidence -> MaterialClaim -> Answer / Refusal / ManualReview
```

Kernel 边界：

- Knowledge Kernel 负责文档解析、OCR、清洗、chunking、索引状态。
- Retrieval Kernel 负责权限前置过滤、dense/sparse/fuzzy 召回、RRF/rerank、ranking explanation、Evidence 生成。
- Reasoning Kernel 负责 context assembly、claim 生成、分级 verification、拒答/人工复核策略。

这个划分比暴露大量并列 contract 更稳定。新增能力必须先判断属于哪个 kernel，不能绕过 kernel 直接把临时数据塞进上层 prompt 或 chunk store。

## 5. 目标数据模型

当前可以在 `PolicyDocument` / `PolicyChunk` 基础上演进，避免一次性替换所有表。

### 5.1 PolicyDocument 目标字段

现有字段保留：

- `id`
- `tenant_id`
- `doc_key`
- `doc_type`
- `title`
- `effective_date`
- `risk_level`
- `version`
- `content`

目标新增：

- `language`: `zh | en | mixed`
- `source_type`: `markdown | pdf | docx | image | html | api`
- `source_uri`
- `file_checksum`
- `content_hash`
- `visibility`: `internal | merchant | public | restricted`
- `acl_json`
- `authority_level`: 用于同类文档冲突时排序。
- `status`: `uploaded | parsing | parsed | chunking | embedding | indexed | failed | archived`
- `parser_name`
- `parser_version`
- `ocr_required`
- `ocr_engine`
- `last_indexed_at`
- `supersedes_doc_id`

### 5.2 DocumentBlock 目标表

当前仓库没有 parsed block 层。生产级 OCR/citation 需要它。

```text
DocumentBlock
  id
  tenant_id
  doc_id
  block_index
  page_number
  block_type: heading | paragraph | table | image | footer | header | list | code
  text
  normalized_text
  bbox_json
  ocr_confidence
  layout_confidence
  parent_heading_path
  table_json
  parser_name
  parser_version
  created_at
```

`DocumentBlock` 的职责是保存“解析后但未 chunk 的证据来源”。它不是临时中间结果，而是一等数据模型。chunk 可以合并多个 block，但必须保留 `source_block_ids`；否则 page/bbox、表格行列、OCR 低置信度、人工复审和视觉高亮都无法追溯。

表格、图片和 parser 调试信息可以在后续拆为更细表：

```text
DocumentTable
  id
  tenant_id
  doc_id
  block_id
  page_number
  table_json
  header_rows_json
  cell_bbox_json
  confidence

ParserTrace
  id
  tenant_id
  doc_id
  parser_name
  parser_version
  source_checksum
  warnings_json
  error_json
  rendered_preview_ref
  created_at
```

第一阶段可以先把这些字段放进 `DocumentBlock.table_json` / `metadata_json`，但 contract 上必须承认它们是 citation 和 OCR 质量控制的一部分。

### 5.3 Chunk / PolicyChunk 目标字段

现有字段保留：

- `tenant_id`
- `doc_id`
- `chunk_id`
- `section`
- `content`
- `risk_level`
- `effective_date`
- `embedding`

目标新增：

- `language`
- `search_text`: 用于 full-text/trgm 的分词后文本。
- `embedding_text`: 用于 embedding 的上下文增强文本。
- `token_count`
- `page_start`
- `page_end`
- `bbox_json`
- `source_block_ids`
- `chunk_hash`
- `content_hash`
- `embedding_model`
- `embedding_dimensions`
- `embedding_version`
- `index_status`
- `metadata_json`

PostgreSQL 目标索引：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX ix_policy_chunks_embedding_hnsw
ON policy_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 128);

CREATE INDEX ix_policy_chunks_search_vector_gin
ON policy_chunks
USING gin (search_vector);

CREATE INDEX ix_policy_chunks_search_text_trgm
ON policy_chunks
USING gin (search_text gin_trgm_ops);

CREATE INDEX ix_policy_chunks_scope_filter
ON policy_chunks (tenant_id, effective_date, risk_level);
```

`search_vector` 可以使用 generated column：

```sql
search_vector tsvector
GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, ''))) STORED
```

注意：PostgreSQL full-text 的 `ts_rank` / `ts_rank_cd` 不是严格 BM25，只是适合小型生产版的 sparse keyword retrieval。文档和代码中应写作 `full-text sparse retrieval` 或 `BM25-like behavior`，不要声称是标准 BM25。

### 5.4 Evidence 运行时模型

`Evidence` 是 Retrieval Kernel 输出给 Reasoning Kernel 的唯一证据对象。它不是数据库表的简单镜像，而是“runtime selected + verified”的证据包。

```text
Evidence
  evidence_id
  ref: EvidenceRefV1
  chunk_id
  doc_id / doc_key
  tenant_id
  text
  text_hash
  citation_locator: page / bbox / source_block_ids
  retrieval_features
  ranking_explanation
  verification_level
  verification_status
```

`EvidenceRefV1` 是现有跨层 canonical evidence identity，用于 Knowledge result、AgentState、citation、snapshot/hash、replay；`Evidence` 必须包含 `ref: EvidenceRefV1`，并在 runtime 承载文本、定位、排序解释和校验状态。`Evidence` 不能替代 `EvidenceRefV1` 在 `docs/contract-spec.md` 中的 canonical 地位。

### 5.5 Indexing job 状态机

引入异步 ingestion 后，文档写入成功不等于三路检索索引都可用。目标状态机应显式区分：

```text
uploaded
  -> parsed
  -> cleaned
  -> chunked
  -> tokenized
  -> embedded
  -> indexed_dense
  -> indexed_sparse
  -> indexed_fuzzy
  -> ready
```

失败状态必须带阶段：

```text
parse_failed
clean_failed
chunk_failed
embedding_failed
dense_index_failed
sparse_index_failed
fuzzy_index_failed
```

最低要求：

- `ready` 才能进入默认检索。
- 单路索引失败时不得静默降级为“完整索引成功”。
- re-index 必须幂等，依赖 `file_checksum`、`content_hash`、`parser_version`、`embedding_model`。
- 每次检索 trace 必须能说明当前 evidence 来自哪个 `index_job_id` 或等价版本标识。

### 5.6 Ingestion job log 与事件模型

生产级 ingestion 需要可追踪的 job log 支撑 retry、partial failure、async OCR 和审计。RAG-1 只需要 `rag_ingestion_jobs` 或 `policy_index_jobs` 这类 job log；完整事件模型等 OCR 异步化后再拆。

RAG-1 job log 最低字段：

```text
job_id
tenant_id
doc_id
stage
status
error_code
error_message
retrieval_config_version
started_at
completed_at
```

RAG-2 以后可扩展为事件：

建议事件：

- `DocumentIngestedEvent`
- `BlockParsedEvent`
- `ChunkCreatedEvent`
- `EmbeddingCompletedEvent`
- `IndexUpdatedEvent`
- `IngestionFailedEvent`

事件最低字段：

```text
event_id
tenant_id
doc_id
index_job_id
event_type
stage
status
source_checksum
parser_version
embedding_model
error_code
created_at
```

事件模型的目标不是增加复杂度，而是让后续 async OCR、失败重试、局部重建索引和审计排障有事实依据。

## 6. Ingestion / OCR / Chunking

### 6.1 Parser 与 OCR

OCR 是生产级 RAG 的必选能力，不是可选增强。MOCA 的 ingestion 必须支持：

- Markdown / plain text：保留当前快速路径。
- PDF：提取文本、页码、layout、表格；扫描件或低文本质量页面进入 OCR。
- Word / DOCX：提取段落、标题、表格、图片文字。
- Image：OCR 输出 block。

解析输出必须是 structured blocks，而不是直接拼接成长字符串。

目标模块建议：

```text
src/rag/parsers/base.py
src/rag/parsers/markdown.py
src/rag/parsers/pdf.py
src/rag/parsers/docx.py
src/rag/parsers/ocr.py
src/rag/cleaning.py
src/rag/chunking.py
src/rag/jobs.py
```

短期可借鉴 RAGFlow deepdoc 的思路：OCR + layout + table-aware parsing；但不建议直接绑定 RAGFlow deepdoc 的内部实现作为 MOCA 核心依赖。MOCA 应定义自己的 `DocumentBlock` contract。

Parser/OCR backend 应是可插拔实现，而不是领域契约。候选后端可以通过 spike 评估，例如：

- 通用文档 parser：用于 PDF/DOCX/HTML/图片的统一结构化输出基线。
- OCR/结构化 parser：用于扫描件、复杂表格、多语言图片文本。
- RAGFlow deepdoc 类能力：用于学习 layout/table/page-bbox 的目标能力边界。

评估指标不看“人工观感”本身，而看四个硬结果：

- page/bbox 是否稳定。
- 表格结构是否保留表头、行列和单元格关系。
- 低置信度区域是否显式打标。
- chunk citation 是否能回到原始 block/table/cell。

### 6.2 清洗

清洗目标不是“把文本变短”，而是让检索和引用稳定。

必须处理：

- Unicode normalization。
- 控制字符、不可见字符、重复空白。
- PDF soft line break 合并。
- 页眉页脚/页码去重。
- 表格转 markdown 或结构化 table block。
- OCR 低置信度标记，不静默当作高质量文本。
- 文档标题、章节路径、版本、更新时间继承到 chunk metadata。

### 6.3 Chunking

禁止只按固定字符数一刀切作为主策略。目标 chunking 策略：

- 优先按标题层级、段落、列表、表格、语义边界切分。
- 表格默认保持原子性；超过限制时按行组切分并保留表头。
- chunk 必须继承 `doc_title / heading_path / section / effective_date / page range`。
- 相邻 chunk 可保留 10%-20% overlap，但 overlap 不应破坏 citation。
- 超长 policy section 可以做 parent-child chunk：parent 保存章节摘要，child 保存细粒度证据。
- chunk_id 必须稳定，可由 `doc_key + version + block span/chunk index` 生成；变更策略要可审计。

### 6.4 Embedding text 与 stored content 分离

当前 `IngestionService` 已经把标题/章节注入 embedding text，但数据库只保存 raw chunk content。这个方向是对的，目标态继续强化：

```text
content:
  用于回答、citation、text_hash。

search_text:
  用于 full-text/trgm，允许分词、扩展同义词、注入领域词。

embedding_text:
  用于 embedding，允许注入 title、heading_path、doc_type、effective_date、locale。
```

禁止把 `embedding_text` 直接当作用户可见证据，因为它可能包含为了检索增强而注入的上下文。

## 7. 中文分词与多语言策略

MOCA 不能把中文 full-text 交给 PostgreSQL 默认 tokenization 后期待效果稳定。中文需要应用层分词。

### 7.1 search_text 生成

例子：

```text
content:
用户申请仅退款但商家已经发货时，客服应先核实物流状态。

search_text:
退款规则 仅退款 用户 申请 商家 已经 发货 已发货 客服 核实 物流 状态
```

query 侧使用同一 tokenizer：

```text
query:
商家已发货还能仅退款吗

query_terms:
商家 已发货 发货 仅退款 退款
```

推荐模块：

```text
src/knowledge/tokenization.py
```

### 7.2 领域词典

初始领域词典至少包含：

- `仅退款`
- `七天无理由`
- `二次销售`
- `商家举证`
- `高价值订单`
- `补偿券`
- `转人工`
- `退款时效`
- `跨境订单`
- `虚拟商品`
- `质量问题`
- `物流拦截`
- `拒收`
- `退货运费`

### 7.3 语言路由

不需要两套完全割裂的 pipeline。推荐策略是：

```text
统一 ingestion/retrieval interface
  -> language detection
  -> language-specific tokenizer
  -> language-specific search_text
  -> language-aware retrieval config
```

中文重点是 tokenizer 和领域词典；英文可以使用 PostgreSQL English config 或 simple config 加 stemming 策略。embedding 模型如果支持多语言，可以先统一；未来再按语言切换 embedding model。

## 8. SearchBackend 设计

上层不得直接依赖 pgvector 细节。当前 `PolicyKnowledgeService` 已经承担了 Agent-facing facade；RAG-1 不需要一次性引入完整 external-backend interface，只需要把现有 retriever protocol 演进成 `PostgresHybridRetriever` seam。

RAG-1 推荐形态：

```python
class PolicyRetriever(Protocol):
    async def retrieve(...) -> tuple[str, list[EvidenceRefV1], float]: ...
    async def get_contents_by_evidence_keys(...) -> dict[tuple[str, str], str]: ...
```

目标态 SearchBackend interface 留到 RAG-5 或 external backend shadow test 时固化：

```python
class SearchBackend:
    async def dense_search(self, request: SearchRequest) -> list[SearchHit]: ...
    async def sparse_search(self, request: SearchRequest) -> list[SearchHit]: ...
    async def fuzzy_search(self, request: SearchRequest) -> list[SearchHit]: ...
    async def hybrid_search(self, request: SearchRequest) -> list[SearchHit]: ...
    async def get_chunks(self, keys: list[EvidenceKey], scope: Scope) -> dict[EvidenceKey, ChunkText]: ...
```

这里的 `SearchRequest`、`SearchHit`、`EvidenceKey` 是 Retrieval Kernel 的 runtime DTO，不是 core contract。Reasoning Kernel 只消费 `Evidence`，不直接消费后端返回的 raw hit。

RAG-1 当前实现目标：

```text
PostgresHybridRetriever
  dense: pgvector cosine distance
  sparse: PostgreSQL full-text search
  fuzzy: pg_trgm similarity
  fusion: RRF
```

未来可替换：

```text
VespaSearchBackend
OpenSearchSearchBackend
```

## 9. Postgres Hybrid Retrieval

### 9.1 三路检索

Dense retrieval：

```sql
SELECT chunk.*, 1 - (embedding <=> :query_embedding) AS score
FROM policy_chunks chunk
JOIN policy_documents doc ON doc.id = chunk.doc_id
WHERE chunk.tenant_id = :tenant_id
  AND chunk.effective_date <= :effective_date
  AND chunk.embedding IS NOT NULL
  AND doc.doc_type = ANY(:doc_types)
  AND acl_allows(...)
ORDER BY embedding <=> :query_embedding
LIMIT :dense_top_k;
```

Sparse retrieval：

```sql
SELECT chunk.*, ts_rank_cd(search_vector, plainto_tsquery('simple', :query_terms)) AS score
FROM policy_chunks chunk
JOIN policy_documents doc ON doc.id = chunk.doc_id
WHERE chunk.tenant_id = :tenant_id
  AND chunk.effective_date <= :effective_date
  AND search_vector @@ plainto_tsquery('simple', :query_terms)
  AND acl_allows(...)
ORDER BY score DESC
LIMIT :sparse_top_k;
```

Fuzzy retrieval：

```sql
SELECT chunk.*, similarity(search_text, :query_text) AS score
FROM policy_chunks chunk
JOIN policy_documents doc ON doc.id = chunk.doc_id
WHERE chunk.tenant_id = :tenant_id
  AND chunk.effective_date <= :effective_date
  AND search_text % :query_text
  AND acl_allows(...)
ORDER BY score DESC
LIMIT :fuzzy_top_k;
```

`acl_allows(...)` 代表应用层生成的 SQL 条件，不代表数据库函数必须存在。

### 9.2 权限前置过滤

检索前必须过滤：

- `tenant_id`
- `merchant_scope`
- `role`
- `permissions`
- `doc_acl`
- `visibility`
- `effective_date`
- 可选 `region`

禁止先召回再过滤，因为这会造成：

- 无权限 chunk 进入 reranker 或 prompt。
- trace 中泄漏 unauthorized evidence。
- RRF 分数被无权限候选污染。

### 9.3 RRF Fusion

不推荐直接把 dense score、full-text score、trgm score 相加，因为分数尺度不同。

推荐使用 Reciprocal Rank Fusion：

```text
rrf_score(chunk) = sum(1 / (k + rank_i))
```

默认候选：

```text
dense top 50
sparse top 50
fuzzy top 20
  -> dedup by chunk_id
  -> RRF
  -> metadata/freshness adjustment
  -> optional reranker
  -> top-k context
```

默认 `k = 60`。RRF 后保留每一路命中信息，便于 eval 和 debug：

```json
{
  "chunk_id": "refund_policy_005",
  "rank_features": {
    "dense_rank": 4,
    "sparse_rank": 1,
    "fuzzy_rank": null,
    "rrf_score": 0.0317
  }
}
```

### 9.4 Ranking explainability

目标态检索不只返回排序结果，还应解释“为什么这个 chunk 被选中”。这不是 UI 装饰，而是 debug、eval、prompt tuning、召回策略调参的基础。

RAG-1 不以完整 `ranking_explanation` 作为阻塞项，只要求最小 retrieval trace：

```json
{
  "chunk_id": "refund_policy_005",
  "trace_features": {
    "selected_by": ["dense", "sparse"],
    "dense_rank": 4,
    "sparse_rank": 1,
    "fuzzy_rank": null,
    "rrf_score": 0.0317,
    "filter_status": "passed"
  }
}
```

RAG-3/4 可扩展为完整 ranking explanation：

```json
{
  "chunk_id": "refund_policy_005",
  "ranking_explanation": {
    "selected_by": ["dense", "sparse"],
    "matched_terms": ["仅退款", "发货", "物流"],
    "vector_similarity": 0.78,
    "keyword_rank": 1,
    "keyword_overlap": 0.42,
    "trigram_similarity": null,
    "rule_triggers": ["domain_anchor:仅退款", "effective_date_ok"],
    "acl_filter": "passed",
    "freshness": "current"
  }
}
```

完整 `ranking_explanation` 应进入 trace/eval，不一定进入 prompt。它用于回答工程问题：是向量召回命中、关键词命中、规则触发，还是 reranker 抬升。

### 9.5 Freshness / authority / conflict ranking

`effective_date`、`authority_level`、`supersedes_doc_id` 不能只停留在 metadata。它们必须在三个位置生效：

1. 召回前过滤：过期、未生效、无权限的 chunk 不进入任何一路检索。
2. Fusion / rerank：同主题候选中，较新版本、较高 authority、明确 supersedes 旧版本的文档应有排序偏置。
3. Context Builder：如果过滤和排序后仍存在冲突证据，必须打 `conflict` label，不允许模型静默裁决。

候选 trace 应保留 ranking features：

```json
{
  "chunk_id": "refund_policy_005",
  "rank_features": {
    "dense_rank": 4,
    "sparse_rank": 1,
    "fuzzy_rank": null,
    "rrf_score": 0.0317,
    "freshness_score": 0.9,
    "authority_level": 80,
    "supersedes_matched": true,
    "conflict_group": "refund_only_after_shipped"
  }
}
```

### 9.6 Reranker

Reranker 是推荐能力，不是第一阶段硬依赖。接口必须先留出：

```python
class Reranker:
    async def rerank(self, query: str, candidates: list[SearchHit]) -> list[RerankedHit]: ...
```

可选实现：

- cross-encoder reranker。
- 外部 rerank API。
- 当前 lightweight lexical rerank 作为 fallback。

Reranker 输入不得包含无权限 chunk。

## 10. Query Router

MOCA 已经有 intent classifier 和 `search_policy` tool 路由基础。目标 RAG Router 输出：

```json
{
  "type": "policy | faq | order | troubleshooting | action | unsupported",
  "language": "zh | en",
  "require_citation": true,
  "requires_business_data": false,
  "requires_policy_evidence": true,
  "permissions": {
    "tenant_id": "uuid",
    "role": "support_agent",
    "merchant_scope": ["*"]
  },
  "retrieval_config": {
    "dense_top_k": 50,
    "sparse_top_k": 50,
    "fuzzy_top_k": 20,
    "final_top_k": 5
  }
}
```

路由原则：

- Policy/FAQ 走 RAG。
- Order/refund/account status 走 Business API/SQL。
- Troubleshooting 同时需要 Business facts + Policy evidence。
- Action request 必须先有 business facts、policy evidence、risk/approval，再进入 action draft。
- Unsupported 或低置信度走澄清/拒答，不进入幻觉式补全。

## 11. Context Builder

Context Builder 是生产级 RAG 的关键组件，不应散落在各节点中。

目标职责：

- 按 evidence refs 回读 chunk content。
- 使用 `text_hash` 校验证据未变更。
- 去重相邻或重复 chunk。
- 合并 parent/child chunk。
- 按 token budget 裁剪，但 protected citation metadata 不可裁掉。
- 生成 citation map。
- 标记证据 freshness、authority、ACL、OCR confidence。
- 标记冲突证据，不让模型静默选择。

目标输出：

```json
[
  {
    "citation_id": "E1",
    "evidence_id": "refund_policy/refund_policy_005@v2",
    "doc_key": "refund_policy",
    "chunk_id": "refund_policy_005",
    "title": "退款规则",
    "section": "仅退款已发货",
    "page_start": 3,
    "page_end": 3,
    "bbox": null,
    "effective_date": "2026-01-01",
    "authority_level": 80,
    "text_hash": "sha256:...",
    "text": "用户申请仅退款但商家已经发货时..."
  }
]
```

当前 `recommendation_generation.py` 通过共享实现已经做了 evidence re-fetch 和 hash 校验，这是正确方向。目标是把它下沉为可复用 `ContextBuilder`，供 recommendation、final response、verifier 共用。

## 12. Hallucination Control

### 12.1 定义

MOCA 对 RAG hallucination 的定义：

> RAG hallucination 是系统生成的答案没有被当前可用、有效、授权、最新的证据链充分支撑。

它不同于原生 LLM 幻觉。原生 LLM 幻觉常表现为模型在知识缺失、采样、上下文误读、训练偏差或指令冲突下编造答案；RAG hallucination 更隐蔽，因为即使检索到了文档，系统仍可能在数据、检索、上下文、生成或校验任一层失败。

### 12.2 风险分类

| 风险 | 例子 | 控制点 |
| --- | --- | --- |
| 数据解析幻觉 | OCR 把金额/日期识别错；PDF 表格错列；Word 表格丢标题 | OCR confidence、layout/table parser、parsed block audit |
| Chunk 幻觉 | `该接口 QPS 限制为 100` 被切出上下文，模型不知道接口名称 | heading path、parent context、semantic chunking |
| 检索缺失 | 正确政策没有被召回 | dense+sparse+fuzzy、多 query rewrite、context recall eval |
| 检索噪声 | 召回语义相似但规则无关的 chunk | RRF、reranker、threshold、domain anchors |
| 权限幻觉 | 模型引用了无权限文档 | SQL pre-filter、scope contract、permission safety eval |
| 过期证据 | 新旧政策同时被召回，模型选了旧政策 | effective_at filter、freshness/authority ranking、supersedes relation |
| 冲突证据 | 两份政策结论相反，模型静默选择错误依据 | conflict detection、authority level、manual review route |
| 生成不忠实 | 检索到了正确证据，但模型用预训练知识给出相反答案 | evidence-only prompt、structured citations、semantic verifier |
| Citation 伪造 | 模型引用了不存在或未召回的 chunk | membership validation、allowed citation objects |
| Business data 幻觉 | 模型根据政策猜测订单退款状态 | business tool/API 强制分离 |

### 12.3 数据层控制

必须实现：

- Parser/OCR 输出 `DocumentBlock`，保留 page/bbox/confidence。
- 低 OCR confidence 的 block 进入人工 review 或降权检索。
- 表格保持结构，不能拆断表头和数据行关系。
- chunk 保存 `source_block_ids`，citation 可回溯到原始 page/bbox。
- 文档版本、parser version、embedding version 写入 metadata。
- 旧文档不删除审计事实，但默认检索只召回当前有效版本。

验收指标：

- OCR 低置信 block 不得作为 high-confidence evidence 直接支撑高风险结论。
- 表格类 golden case 的 expected row/column 必须能被 citation 定位。
- 文档重建索引后，旧 `text_hash` 不得被误判为仍有效。

### 12.4 检索层控制

必须实现：

- Query rewrite：短、模糊 query 可以扩展为多个检索表达。
- Dense + sparse + fuzzy 三路召回。
- RRF fusion。
- 前置权限过滤。
- effective_at / effective_date 过滤。
- no evidence / partial evidence / strong evidence 状态清晰。

禁止行为：

- 只依赖向量 top_k。
- 后过滤权限。
- 把 `partial_evidence` 当作足以执行高风险 action 的依据。
- 检索失败时继续让模型“凭经验回答”。

### 12.5 Context 层控制

必须实现：

- evidence content re-fetch。
- `text_hash` 验证。
- citation map。
- token budget 不裁掉 citation metadata。
- 冲突证据标记。
- 同 doc 相邻 chunk 去重/合并。

当前仓库已有 `get_verified_evidence_contents` 和 membership validation 的基础，目标是增加语义支持与冲突判断。

### 12.6 生成层控制

系统 prompt 必须表达强边界：

```text
只允许根据提供的 evidence 回答政策性结论。
不得使用外部知识补全政策细节。
找不到足够证据时必须说明知识库不足或转人工。
每个 material policy claim 必须引用 allowed citation object。
证据冲突时必须说明冲突，不得自行裁决。
业务事实必须来自 business tool，不得由政策文本推断。
```

结构化输出必须保留：

- material claims。
- cited evidence ids。
- recommended action。
- missing info。
- confidence。
- risk level。

生成器不应只输出一段自由文本。目标输出必须包含结构化 `MaterialClaim`，供 citation validation、semantic verifier、UI 高亮和人工复核使用：

```json
{
  "material_claims": [
    {
      "claim_id": "claim-1",
      "claim_type": "policy_rule",
      "claim_text": "商家已发货后，客服应先核实物流状态和商家举证，再判断是否支持仅退款。",
      "risk_level": "medium",
      "cited_evidence_ids": ["refund_policy/refund_policy_005@v2"],
      "business_fact_refs": []
    }
  ]
}
```

`claim_type` 建议枚举：

- `policy_rule`
- `policy_exception`
- `business_fact`
- `recommended_action`
- `risk_assessment`
- `missing_information`
- `conflict_notice`

其中 `business_fact` 必须引用 business fact refs，不能只引用 policy evidence；`policy_rule` / `policy_exception` 必须引用 evidence refs；`recommended_action` 必须同时满足所需的 policy evidence 和 business facts。

### 12.7 后置校验

当前 `validate_membership` 只检查 cited `evidence_id` 是否存在于 retrieved evidence，不判断 claim 是否被证据语义支持。目标不是把 verification 做成每次都全量执行的 mini pipeline，而是把 verifier 做成 policy engine：规则优先、轻模型辅助、阈值触发。

分级执行策略：

| Level | 触发条件 | 校验内容 | 目标 |
| --- | --- | --- | --- |
| Level 1 | always | membership、ACL/scope、freshness、必要时 hash | 防 citation 伪造、越权、过期证据 |
| Level 2 | normal retrieval path | RRF、rerank、ranking explanation、threshold | 降低检索噪声，提升证据质量 |
| Level 3 | risk only | semantic support、conflict detection、manual review routing | 防高风险场景不忠实生成 |

Level 1 是轻量 gate，必须始终执行。Level 2 属于 Retrieval Kernel。Level 3 只在风险触发时执行，不应成为所有 FAQ/低风险 policy QA 的固定成本。

高风险场景必须启用 semantic support verifier：

- 退款责任判断。
- 赔付/补偿建议。
- 高价值订单。
- 商家处罚、申诉、解封。
- 合规/风控类政策。
- 证据冲突或过期风险。

Verifier 执行原则：

- 先规则，后模型：membership、scope、freshness、hash、risk trigger 必须用确定性代码判断。
- 语义支持可以使用轻模型/LLM judge，但只能在 Level 3 场景触发。
- verifier 输出驱动 allow / regenerate / refuse / manual_review，不直接重排 retrieval 结果。
- reranker 负责“相关性排序”；verifier 负责“能否支撑 claim”。二者不得混用同一个分数字段。

Verifier 输出：

```json
{
  "status": "supported | unsupported | conflicting | stale | insufficient",
  "claim_results": [
    {
      "claim_id": "claim-1",
      "claim_type": "policy_rule",
      "claim_text": "已发货后仅退款需先核实物流状态",
      "cited_evidence_ids": ["refund_policy/refund_policy_005@v2"],
      "support_status": "supported",
      "risk_level": "medium",
      "reason": "citation text contains the same required condition and handling step"
    }
  ],
  "action": "allow | regenerate | refuse | manual_review"
}
```

校验层必须区分：

- `membership_valid`: 引用是否来自本轮 allowed evidence。
- `hash_valid`: 引用 text_hash 是否仍匹配当前 chunk content。
- `scope_valid`: 引用是否在当前 tenant/RBAC/ACL scope 内。
- `freshness_valid`: 引用是否符合 `effective_at` 和 supersedes 关系。
- `semantic_support`: claim 是否被 citation text 支持。

Level 3 中，只有前四项通过，才允许进入 semantic support 判断。任何 scope/hash/freshness 失败都应直接拒绝或重新检索，而不是交给模型自行解释。

### 12.8 Business Data hallucination 控制

Business Data QA 属于 Tool System，不属于 RAG subsystem。业务事实必须来自 tool/API/SQL：

- 订单状态。
- 退款进度。
- 工单内容。
- 用户账户状态。
- 补偿券发放记录。

硬边界：

- RAG never accesses business facts。
- Tool results never go into chunk store。
- Business tool summary 可以进入 prompt，但不能被 embedding 成 policy chunk。
- Policy chunk 可以说明“规则如何处理”，不能说明“某个订单当前是什么状态”。
- Troubleshooting 必须显式区分 business fact refs 和 policy evidence refs。

RAG 只能回答政策和 FAQ，不得推断具体业务对象状态。Troubleshooting 的答案必须同时引用：

- business fact refs。
- policy evidence refs。

如果任一侧缺失，输出必须降级为缺信息、澄清或转人工。

### 12.9 Evidence strength 与拒答策略

`no_evidence`、`partial_evidence`、`strong_evidence` 不能只是内部状态，还必须驱动最终产品行为。

| 场景 | no evidence | partial evidence | strong evidence |
| --- | --- | --- | --- |
| 低风险 FAQ | 拒答或建议补充知识库 | 可回答，但必须标注不确定性和引用范围 | 正常回答并引用 |
| Policy QA | 拒答/转人工 | 只给流程性建议或说明证据不足，不给确定政策结论 | 正常回答并引用 |
| Troubleshooting | 请求业务事实或转人工 | 可说明已查到的事实和缺口，不给最终责任判断 | 结合 business refs + policy evidence 回答 |
| Action / compensation | 禁止 action draft | 禁止高风险 action draft；低风险也需人工确认或补证据 | 仍需 risk/approval gate |
| 高风险合规/处罚 | 转人工 | 转人工 | 通过 semantic verifier 后才可输出建议 |

拒答不是失败路径，而是 hallucination control 的正常输出。eval 必须单独统计：

- refusal accuracy。
- unsafe answer rate。
- high-risk manual-review rate。
- partial-evidence overclaim rate。

## 13. Evaluation

当前已有 Hit@5 和 fallback accuracy。目标 eval 必须扩展为 evidence-chain 评估。

### 13.1 Retrieval eval

- Hit@5。
- Context recall：正确证据是否被召回。
- Context precision：召回噪声比例。
- Fallback accuracy：无政策证据时是否 no evidence。
- Hybrid ablation：dense-only、sparse-only、hybrid 对比。
- 中文分词覆盖：领域词是否提升 sparse recall。

### 13.2 Hallucination eval

- Faithfulness：答案是否被证据支持。
- Citation accuracy：引用 chunk 是否真实支持对应句子。
- Citation membership：引用是否来自 retrieved evidence。
- Conflict handling：冲突政策是否触发冲突说明/人工 review。
- Freshness correctness：新旧政策同时存在时是否使用最新有效版本。
- Permission safety：无权限文档是否绝不被召回、引用、进入 prompt。
- Refusal accuracy：无证据时是否拒答或转人工。
- Business data grounding：订单/退款事实是否只来自 business refs。

### 13.3 Golden set 扩展

建议新增 golden categories：

- `policy_exact_rule`
- `policy_conflict`
- `policy_stale_version`
- `faq_short_query`
- `ocr_table_rule`
- `permission_denied_evidence`
- `no_evidence_refusal`
- `business_fact_required`
- `hybrid_keyword_required`
- `semantic_support_failure`

每个 case 至少标注：

```json
{
  "query": "商家已发货还能仅退款吗？",
  "expected_route": "policy_qa",
  "language": "zh",
  "expected_doc_ids": ["refund_policy"],
  "expected_chunk_ids": ["refund_policy_005"],
  "forbidden_doc_ids": [],
  "expected_answer_claims": [
    {
      "claim_type": "policy_rule",
      "claim": "已发货场景需先核实物流状态和商家举证",
      "supported_by": ["refund_policy_005"],
      "expected_support_status": "supported"
    }
  ],
  "should_fallback": false,
  "requires_business_data": false,
  "requires_citation": true
}
```

## 14. Observability

每次 RAG 检索必须记录可审计的低敏摘要：

- query id / run id / trace id。
- router decision。
- language。
- search backend name/version。
- index job/version id。
- retrieval config version。
- tokenizer version。
- embedding model/version。
- dense/sparse/fuzzy 候选数。
- RRF top candidates。
- RAG-1 minimal retrieval trace；RAG-3/4 optional ranking explanation。
- reranker model/version。
- final evidence refs。
- retrieval status。
- best score / threshold。
- no evidence reason。
- latency breakdown。

禁止把 tenant_id/user_id/run_id/thread_id 等高基数字段作为 Prometheus label；它们可进入 structured log 或 trace attribute，但指标 label 必须低基数。

## 15. 迁移路线

### Phase RAG-1：最小生产 Hybrid Retrieval

目标：

- 保留 `PolicyKnowledgeService` 和 `EvidenceRefV1` 作为跨层 contract，不在本阶段冻结 `DocumentBlock` / `Evidence` / `MaterialClaim`。
- 增加 `search_text` / `search_vector` / pg_trgm。
- 增加中文 tokenizer 和领域词典。
- 在现有 retriever protocol 上演进出 `PostgresHybridRetriever` seam，不引入完整 external `SearchBackend` interface。
- 实现 dense + sparse + fuzzy + RRF。
- 保留当前 lightweight lexical rerank 作为过渡 fallback，但不再把它称为完整 hybrid。
- 增加最小 retrieval trace：`selected_by`、channel ranks、`rrf_score`、`filter_status`。
- 实现 `effective_date` / ACL / tenant / role 前置过滤。
- 如果需要记录索引重建状态，使用 `policy_index_jobs` / `rag_ingestion_jobs` job log；不在本阶段拆完整事件模型。
- 不实现 OCR、`DocumentBlock` 持久化、`MaterialClaim`、semantic verifier、完整 ranking explanation。
- 扩展 eval：hybrid Hit@5、fallback、permission pre-filter、effective_date、RRF ordering。

### Phase RAG-2：Production Ingestion + OCR

目标：

- 增加 parser/OCR abstraction。
- 支持 PDF/DOCX/image。
- 通过 spike 对比至少两类 parser/OCR backend，选择默认实现和 fallback 实现。
- 增加 `DocumentBlock`。
- 增加 parser trace / OCR confidence / table metadata。
- 增加 cleaning pipeline。
- 增加 page/bbox/source_block_ids。
- 增加 `source_block_ids`、page range、token_count、embedding model/version。
- 先使用 job log；OCR 异步化后再拆 ingestion event。
- 扩展 OCR/table golden cases。

### Phase RAG-3：Context Builder + Hallucination Control

目标：

- 下沉 evidence re-fetch/hash validation 到 `ContextBuilder`。
- 增加 citation map。
- 增加 conflict/freshness labels。
- 增加 `MaterialClaim` 结构化输出；它是 Reasoning Kernel runtime object，不替代 `EvidenceRefV1`。
- 增加分级 verifier policy engine：Level 1 always，Level 2 retrieval normal path，Level 3 risk only。
- 增加 evidence strength -> response/refusal/manual review 策略。
- 高风险场景启用 verifier。
- 扩展 faithfulness/citation accuracy eval。

### Phase RAG-4 / MOCA Phase 23：Reranker 与 Query Rewrite

目标：

- 增加 query rewrite。
- 增加 reranker interface。
- 支持 cross-encoder 或外部 rerank API。
- 增加 ablation eval 和 latency budget。

### Phase RAG-5：Optional External Search Backend

触发条件：

- chunk 数超过 PostgreSQL 低延迟能力。
- hybrid/ranking profile 复杂度明显增加。
- 多 tenant 并发检索压测不达标。

此时再评估 Vespa/OpenSearch。PostgreSQL 仍保留 canonical source of truth。

## 16. 验收标准

RAG-1 最小生产 hybrid retrieval 的验收标准：

- RAG-1 最低标准是可运行、可评估、权限安全的 Postgres hybrid retrieval；目标内部契约不等于已冻结全局 contract。
- `EvidenceRefV1` 继续是跨层 canonical evidence identity；任何 runtime `Evidence` 不得替代或弱化它。
- PostgreSQL hybrid search 可用：dense + sparse + fuzzy + RRF。
- RAG-1 retrieval trace 至少包含 selected_by、channel ranks、RRF score 和 filter status；完整 ranking explanation 可后移。
- 权限过滤发生在每一路 SQL 检索前。
- `effective_date` 至少进入检索前过滤；freshness/authority/supersedes 的完整排序和冲突标记可后移。
- 中文 query 和 content 都走同一应用层 tokenizer。
- `PolicyKnowledgeService` 对 Agent 只暴露 evidence contract，不暴露 DB/retriever 细节。
- RAG-1 不要求 OCR、`DocumentBlock`、`MaterialClaim`、semantic verifier 或完整 external `SearchBackend`。

目标态 RAG 子系统验收标准：

- 系统按 Knowledge Kernel、Retrieval Kernel、Reasoning Kernel 分层，临时 DTO 不穿透 kernel 边界。
- Markdown/PDF/DOCX/image 至少有统一 ingestion contract；OCR 路径可用。
- `DocumentBlock` 是持久化一等模型或等价持久化结构，不是 parser 临时输出。
- chunk 有 page/source metadata，policy citation 可追溯。
- indexing job 能区分 parse/chunk/embed/dense/sparse/fuzzy 各阶段状态。
- ingestion 有 job log 或事件支撑 retry、partial failure 和 async OCR。
- freshness、authority、supersedes 至少进入排序或冲突标记逻辑，不只作为无用 metadata。
- `ContextBuilder` 对 evidence 做回读、hash 验证、去重、token budget 和 citation map。
- policy answer 的 material claims 必须结构化输出并带 citation。
- verifier 采用分级 policy engine，低风险不强制走重型 semantic verifier。
- no evidence、citation invalid、semantic unsupported 不得生成确定动作建议。
- 高风险业务建议必须通过 Level 3 verifier 或转人工。
- Business Data QA 属于 Tool System；RAG 不访问业务事实，tool result 不进入 chunk store，也不得被编码成 `EvidenceRefV1`。
- eval 覆盖 retrieval、citation、faithfulness、permission、freshness、business grounding。

## 17. 关键设计决策

1. 当前阶段选 PostgreSQL hybrid，不选 Vespa。
   - 原因：当前规模小，PostgreSQL 可降低系统复杂度；接口上保留未来替换。

2. OCR 是必选能力。
   - 原因：真实客服知识常来自 PDF、扫描件、截图、Word 附件；不做 OCR 就不是生产级 RAG。

3. Business Data QA 不属于 RAG。
   - 原因：订单/退款/账户状态是结构化事实，必须从 business tool/API/SQL 获取。

4. Citation membership 不等于 semantic support。
   - 原因：当前 membership validation 只能证明引用来自候选 evidence，不能证明 claim 被 evidence 支持。

5. `content`、`search_text`、`embedding_text` 必须分离。
   - 原因：回答证据、关键词检索和向量语义增强的文本目标不同，混在一起会破坏 citation 和审计。

6. Hallucination control 是 evidence-chain 工程，不是 prompt 技巧。
   - 原因：数据层、检索层、上下文层、生成层、校验层任一层失败，都会造成 RAG hallucination。
