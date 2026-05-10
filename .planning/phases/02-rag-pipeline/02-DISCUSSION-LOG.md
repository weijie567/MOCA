# Phase 2: RAG Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 02-rag-pipeline
**Areas discussed:** Chunking strategy, Embedding model, Confidence & fallback, Golden set & eval

---

## Chunking Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| 按标题结构切块 | 按 Markdown 标题拆分，每个 section 一个 chunk。适合结构化规则文档。 | |
| 固定 token 大小切块 | 固定 token 窗口 + overlap。简单通用但可能切断规则条目。 | |
| 混合：标题优先 + 长度兜底 | 先按标题切，超长 section 再按 token 二次切割。 | ✓ |

**User's choice:** 混合策略 — 标题优先 + 长度兜底
**Notes:** 用户提供了详细规格：目标 400-800 中文字符，上限 1200-1500，overlap 80-150 字符仅同 section 内。二次切割保留 parent metadata + part_index。禁止盲目切全文、混入不相关规则、切断单条退款条件。

---

## Embedding Model

| Option | Description | Selected |
|--------|-------------|----------|
| OpenAI text-embedding-3-small | 1536 维，中文效果好，API 简单，成本低 | |
| OpenAI text-embedding-3-large | 3072 维，精度更高但向量更大 | |
| 本地开源模型（BGE 系列） | 无 API 依赖，可离线运行，但需要 GPU | |
| DashScope text-embedding-v4 | 1024 维，阿里云百炼，OpenAI-compatible API，适合中文 | ✓ |

**User's choice:** DashScope text-embedding-v4 (用户自选，非预设选项)
**Notes:** 用户指定阿里云百炼 text-embedding-v4，1024 维 dense output。OpenAI-compatible endpoint。不用 v3，不用本地 BGE。还补充了工程细节：batch 16, retry 3 次 + backoff, 不混用模型 embedding。

---

## Confidence & Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| 硬阈值切断 | 固定余弦相似度阈值，低于则触发 fallback | |
| 返回分数 + Agent 判断 | 返回 top-5 + 置信度分数，Agent 自己判断 | |
| 混合：硬阈值过滤 + 分数透传 | 两层：检索层硬阈值过滤明显不相关的，剩余带分数交给 Agent | ✓ |

**User's choice:** 混合策略
**Notes:** 用户定义了三级置信度：≥0.70 strong, 0.55-0.70 partial, <0.55 no_evidence。Retriever 只返回 evidence + score + status，不编答案。还补充了 citation validator 规格：每个回答必须有 citation，缺失或 chunk_id 不在检索结果中则 invalid。Phase 2 用简单校验器。

---

## Golden Set & Eval

| Option | Description | Selected |
|--------|-------------|----------|
| 手动编写 | 手写 10-15 条高质量测试 query，精确可控 | |
| LLM 生成 + 人工校验 | 自动生成再审核，数量多但质量不可控 | |
| 混合：手写核心 + 后续扩展 | 先手写核心 10 条，Phase 6 再 LLM 扩展 | ✓ |

**User's choice:** 混合策略 — Phase 2 手写 10-15 条，Phase 6 扩展
**Notes:** 用户提供了完整 JSONL 格式规格、分布要求（退款 5 + SOP 3 + FAQ 2 + 边界 2 + fallback 2）、Hit@5 判定规则、验收阈值（≥80%）。还补充了 eval 脚本输出格式和 CI 边界（fake embeddings, 不依赖真实 API）。

---

## Claude's Discretion

- HNSW index 参数
- Ingestion CLI 参数设计
- Retrieval endpoint URL path
- Chunk overlap 精确字符数
- Eval 脚本输出格式

## Deferred Ideas

- LLM 生成 golden set 扩展 — Phase 6
- Reranker — 后续优化
- RBAC-scoped retrieval — Phase 3/4
- PDF/网页解析 — v2
- Redis 缓存检索结果 — Phase 3+
