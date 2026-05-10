# Phase 2: RAG Pipeline - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

知识文档（退款规则、SOP、FAQ）切块、embedding 生成、pgvector 入库与检索。提供搜索端点，返回带元数据过滤、置信度评分和 citation 校验的相关规则 chunks。建立 RAG 评估基线（Hit@5）。

</domain>

<decisions>
## Implementation Decisions

### D-01: 文档来源与格式
- **D-01a:** 知识文档使用本地 Markdown 文件作为 source of truth
- **D-01b:** 文档目录：`data/policies/`
- **D-01c:** 文档类型：退款规则、客服 SOP、商家 FAQ
- **D-01d:** Phase 2 不引入 PDF 解析或网页爬取

### D-02: 切块策略
- **D-02a:** 主策略：按 Markdown 标题（##/###）切块，每个 section 一个 chunk
- **D-02b:** 存储：document title + section path + chunk text + chunk_index
- **D-02c:** 兜底策略：超长 section 二次切割，保留 parent title 和 section metadata
- **D-02d:** 二次切割添加 part_index（如 "退货退款规则 / 七天无理由 / part 1"）
- **D-02e:** 仅同 section 内使用 overlap（80-150 中文字符）
- **D-02f:** 目标 chunk 大小：400-800 中文字符
- **D-02g:** 最大 chunk 大小：1200-1500 中文字符
- **D-02h:** 禁止：盲目按固定 token 切全文、一个 chunk 混入多条不相关规则、切断单条退款条件

### D-03: Embedding 模型
- **D-03a:** 模型：DashScope text-embedding-v4
- **D-03b:** 维度：1024, output_type: dense
- **D-03c:** Provider: Alibaba Cloud Bailian (DashScope)
- **D-03d:** API: OpenAI-compatible endpoint `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **D-03e:** Env var: `DASHSCOPE_API_KEY`
- **D-03f:** 不用 text-embedding-v3（除非 v4 不可用），不用本地 BGE

### D-04: Embedding 工程细节
- **D-04a:** Ingestion batch size: 10 chunks/request（DashScope API 硬限制 max 10，可配置 `EMBEDDING_BATCH_SIZE`）
- **D-04b:** Query-time embedding: 单条
- **D-04c:** Retry: 最多 3 次 + exponential backoff
- **D-04d:** 失败不静默跳过，ingestion 明确报告失败的 documents/chunks
- **D-04e:** 向量存储：`policy_chunks.embedding` (pgvector, 1024 维)。注意：当前 models.py 中为 Vector(1536)，Phase 2 需通过 migration 修正为 Vector(1024)
- **D-04f:** 记录 embedding_model 和 embedding_provider 元数据（schema 支持则入表，否则 config/logs）
- **D-04g:** 不混用不同模型的 embedding，模型变更需重新 embed

### D-05: 置信度与 Fallback
- **D-05a:** 混合策略：硬阈值过滤 + 分数透传
- **D-05b:** top_k = 5
- **D-05c:** min_similarity_threshold = 0.55（初始值，后续通过 eval 调优）
- **D-05d:** strong_evidence_threshold = 0.70
- **D-05e:** ≥0.70 → strong evidence → Agent 正常引用回答
- **D-05f:** 0.55-0.70 → partial evidence → Agent 谨慎回答 + 标注不确定性
- **D-05g:** <0.55 → no_evidence → Agent 禁止用通用知识回答
- **D-05h:** Fallback 文案："当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"
- **D-05i:** Retriever 只返回 evidence + score + fallback status，不编答案

### D-06: Citation Validator
- **D-06a:** 每个 policy 回答必须包含 citations
- **D-06b:** Citation 格式：doc_id, chunk_id, title, section, score
- **D-06c:** Agent 产出无 citation 的回答 → invalid
- **D-06d:** cited chunk_id 不在检索结果中 → invalid
- **D-06e:** Phase 2 用简单校验器（字段匹配），不用 LLM judge

### D-07: Stable IDs
- **D-07a:** policy_documents 使用稳定 doc_id（如 refund_policy, refund_sop, refund_faq）
- **D-07b:** policy_chunks 使用稳定 chunk_id（doc_id + section_path + chunk_index 生成）
- **D-07c:** 不用随机 UUID，因为 eval 需要稳定的 expected_chunk_ids

### D-08: Ingestion 幂等性
- **D-08a:** 多次运行 ingestion 脚本不产生重复 documents/chunks
- **D-08b:** 文档变更时替换其 chunks
- **D-08c:** Phase 2 使用 delete-and-reinsert per document 策略

### D-09: Retrieval API Contract
- **D-09a:** Retriever 返回结构化输出，非纯文本
- **D-09b:** 每个 evidence item 包含：doc_id, chunk_id, title, section, score, text excerpt
- **D-09c:** 返回 retrieval_status: strong_evidence | partial_evidence | no_evidence

### D-10: Scope & Permissions
- **D-10a:** 检索必须按 tenant_id 过滤（schema 已有 tenant_id）
- **D-10b:** Phase 2 不跨租户检索
- **D-10c:** RBAC-scoped retrieval 如未就绪，记录为 Phase 3/4 扩展

### D-11: Golden Set & Eval
- **D-11a:** Phase 2 手写 10-15 条高质量 golden queries
- **D-11b:** 格式：JSONL（`eval/golden_rag_queries.jsonl`）
- **D-11c:** 每条包含：query, expected_doc_ids, expected_chunk_ids, category, difficulty, should_fallback
- **D-11d:** 分布：退款规则 5 + SOP 3 + FAQ 2 + 边界 2 + no-evidence 2
- **D-11e:** Hit@5 判定：非 fallback query 至少一个 expected_chunk_id 出现在 top-5
- **D-11f:** Fallback 判定：retriever 返回 no_evidence 或 best_score < min_similarity_threshold
- **D-11g:** Fail 条件：expected chunk 不在 top-5、fallback query 返回高置信无关结果、citation metadata 缺失
- **D-11h:** Phase 6 再用 LLM 扩展到 25-40 条（需人工审核）

### D-12: Eval 脚本
- **D-12a:** Golden set 文件：`eval/golden_rag_queries.jsonl`
- **D-12b:** Eval 脚本：`scripts/eval_rag_hit_at_5.py`
- **D-12c:** 输出：total query count, Hit@5 score, fallback accuracy, per-category result, failed cases detail
- **D-12d:** Hit@5 或 fallback accuracy 低于验收阈值时 exit non-zero
- **D-12e:** 验收阈值：Hit@5 ≥ 80%, Fallback accuracy ≥ 80%, citation metadata 完整

### D-13: CI 边界
- **D-13a:** CI 运行 unit tests + lightweight retrieval tests
- **D-13b:** CI 不依赖真实 DashScope/Bailian API
- **D-13c:** CI 使用 deterministic fake embeddings
- **D-13d:** 真实 embedding ingestion 和完整 golden set eval 为本地/手动步骤
- **D-13e:** CI 不引入 reranker、LLM judge、外部模型依赖

### Claude's Discretion
- HNSW index 参数（m, ef_construction）
- Ingestion CLI 的具体参数设计
- Retrieval endpoint 的具体 URL path 设计
- Chunk overlap 的精确字符数（80-150 范围内）
- Eval 脚本的具体输出格式（表格 vs JSON）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `.planning/ARCHITECTURE.md` — Design Contract, DB schema (policy_documents, policy_chunks tables), directory structure

### Requirements
- `.planning/REQUIREMENTS.md` — RAG-01 to RAG-07, EVAL-01, EVAL-02, INFR-06

### Prior Phase Context
- `.planning/phases/01-foundation/01-CONTEXT.md` — D-05 (DB schema), D-06 (tenant_id scoping), D-10 (error format), D-04 (API language)

### Data Model
- `src/db/models.py` — Existing PolicyDocument and PolicyChunk model definitions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/db/models.py`: PolicyDocument and PolicyChunk models already defined with pgvector Vector column
- `src/repositories/`: Repository pattern established — new PolicyDocumentRepository and PolicyChunkRepository follow same pattern
- `src/auth/`: JWT auth + tenant_id scoping already working — retrieval endpoint reuses same auth dependency
- `scripts/seed_demo.py`: Existing seed script pattern — ingestion CLI can follow same structure

### Established Patterns
- SQLAlchemy 2.0 mapped_column style with UUID PKs and TimestampMixin
- Repository layer with tenant_id scoping via current_user dependency
- Unified error response format: `{"success", "data", "error"}` with trace_id
- uv + ruff + pytest toolchain

### Integration Points
- `policy_chunks.embedding` column (Vector type) already in schema — needs HNSW index
- FastAPI router pattern in `src/api/` — add retrieval endpoint here
- Docker Compose postgres service already has pgvector extension

</code_context>

<specifics>
## Specific Ideas

- 知识文档内容全中文（退款规则、补偿规则、客服 SOP、商家 FAQ）
- doc_id 使用语义化稳定标识（refund_policy, refund_sop）而非随机 UUID
- chunk_id 格式示例：`refund_policy_003`, `refund_sop_001_part_1`
- Golden set query 示例："用户申请仅退款但商家已经发货，客服应该怎么处理？"
- Fallback query 示例："用户问如何更换银行卡绑定手机号？"（超出知识库范围）

</specifics>

<deferred>
## Deferred Ideas

- LLM 生成 golden set 扩展到 25-40 条 — Phase 6
- Reranker（cross-encoder 二次排序）— 后续优化
- RBAC-scoped retrieval（按角色限制可检索文档）— Phase 3/4
- PDF/网页文档解析 — v2
- Embedding 模型 A/B 测试 — v2
- Redis 缓存热门 query 的检索结果 — Phase 3+

</deferred>

---

*Phase: 02-rag-pipeline*
*Context gathered: 2026-05-10*
