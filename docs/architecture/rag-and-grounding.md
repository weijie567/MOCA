<!-- generated-by: gsd-doc-writer -->
# MOCA RAG 与 Grounding 当前架构

> 文档类型：CURRENT
> 描述范围：当前政策摄取、hybrid retrieval、证据包、引用与 claim grounding
> 最后核验：2026-08-04（当前工作区）
> 权威来源：当前源码、数据库迁移、配置、测试与[跨边界契约](../reference/contracts.md)
> 更新触发：parser/OCR、block/chunk、embedding/search、检索阈值、rewrite/RRF/rerank、证据契约、scope/effective-time、claim verifier 或路由变化

## 总览

MOCA 不把“召回到的文本”直接当作事实。当前链路是：

```text
政策文件
  -> allowlist / 安全检查 -> parser / OCR -> DocumentBlock
  -> PolicyChunk(content + search_text + embedding + source_block_refs)
  -> dense + sparse + fuzzy -> RRF -> rerank
  -> 候选 EvidenceRefV1
  -> tenant-scoped canonical re-fetch
  -> hash / version / effective-time / scope 校验
  -> VerifiedEvidencePackageV1
  -> bounded prompt citations + verifier context
  -> 待发布 MaterialClaimV1
  -> membership + authority + hard rules + support verification
  -> ClaimVerificationBundleV1
  -> final response / manual review / risk gate
```

`src/rag/` 负责把政策源变成可检索块，`src/knowledge/` 负责检索与 canonical 证据校验，`src/agent/rag_context/` 负责 prompt-safe context 和 claim grounding。[摄取入口](../../src/rag/ingestion.py#L126-L349) · [检索引擎](../../src/knowledge/retrieval.py#L234-L548) · [知识服务](../../src/knowledge/service.py#L122-L610) · [ContextBuilder](../../src/agent/rag_context/builder.py#L35-L205)

## 三层边界：candidate、verified evidence、user-visible claim

| 层 | 对象 | 当前含义 | 明确不代表 |
| --- | --- | --- | --- |
| 检索候选 | `EvidenceRefV1` | 某 tenant/doc/chunk/version 被召回；携带 `text_hash`、score、rank 和 retrieval config | 当前行仍有效；scope 正确；文本支持某个结论 |
| 已验证政策证据 | `VerifiedEvidencePackageV1` | 按 tenant 回查当前 chunk 后，通过 hash、版本、时效、scope 校验的 evidence/citation/prompt/verifier 投影 | 订单/退款等业务事实；action authority |
| 待发布声明 | `MaterialClaimV1` | 结构化的 policy、business fact 或 action recommendation claim | 已允许展示；只有 verification result 明确放行才可作为用户可见结论或动作依据 |

`EvidenceRefV1.evidence_id` 为 `{doc_key}/{chunk_id}@vN`。effective date 参与过滤但不参与 identity；`score >= 0.70` 仍只表示 strong retrieval candidate，不是 verified fact。[契约](../../src/knowledge/schemas.py#L19-L179) · [构造](../../src/knowledge/retrieval.py#L408-L421)

`BusinessFactRefV1` 是另一条 authority 链：policy claim 依赖 verified evidence，business fact claim 依赖当前 tool/service refs，action recommendation 必须同时有两侧已支持的依赖。[authority 校验](../../src/agent/rag_context/verifier.py#L484-L573)

## 摄取、OCR 与 chunk

`ParserRegistry` 只接受 Markdown、plain text、PDF、DOCX 和 PNG/JPEG/TIFF 政策源；订单、退款、工单、截图、tool result 等业务 artifact 在 parser 前拒绝。当前上限是 20 MiB/文件、50 页/PDF、8000 px/图片、parser 30 秒、OCR 15 秒/页；DOCX 另有 zip bomb 检查。[registry](../../src/rag/parsers/registry.py#L18-L104) · [安全实现](../../src/rag/parsers/safety.py#L11-L282) · [测试](../../tests/rag/test_ingestion_safety.py#L17-L183)

PDF 优先提取可见文本、page/bbox 和表格；无可用文本/表格的扫描页回退 OCR，可疑隐藏文本层不会被当作 OCR 触发条件。OCR 使用 Tesseract `chi_sim+eng`，保存 word boxes、平均置信度、引擎与 page/rotation；`>=80` 为 accepted，`55 <= confidence < 80` 为 review-needed，`<55` 为 rejected。[PDF parser](../../src/rag/parsers/pdf.py#L43-L183) · [OCR](../../src/rag/parsers/ocr.py#L16-L132)

Parser 统一输出有序 `ParsedBlock`：稳定 `source_block_id`、可见/normalized text、parser version、page/bbox、table/OCR metadata。`DocumentBlock` 持久化这些 provenance；`PolicyChunk` 保存 `content`、`search_text`、有序 source block refs、effective/risk metadata 与 1024 维 embedding。[parser contract](../../src/rag/parsers/base.py#L16-L102) · [模型](../../src/db/models.py#L197-L325) · [迁移](../../src/db/migrations/versions/015_rag_production_ingestion_ocr.py#L20-L126)

`chunk_blocks()` 默认 `max=1200`、`target=800`、`overlap=100`；heading 继承 section，超长正文保留 overlap，table 按行组切分并重复表头。chunk ID 为 `{doc_key}_{index:03d}`，分片追加 `_part_N`。[chunker](../../src/rag/chunker.py#L49-L279)

三种文本严格分离：

| 文本 | 用途 | 是否进入 evidence hash |
| --- | --- | --- |
| `content` | 回答、citation、canonical re-fetch | 是 |
| `search_text` | full-text/trigram；注入 title/section/metadata、领域词与中文 2/3/4-gram | 否 |
| embedding input | dense retrieval；注入 title/section/source block IDs | 否 |

摄取先完成 parsing、chunking、全部 embeddings，再锁定 document 并在短事务内替换 blocks/chunks；失败 rollback，不留下半套新索引。Embedding 当前为配置的 DashScope `text-embedding-v4`、1024 维、batch 最多 10。[摄取事务](../../src/rag/ingestion.py#L137-L349) · [文本投影](../../src/rag/ingestion.py#L634-L735) · [EmbeddingService](../../src/rag/embedder.py#L9-L67)

OCR confidence 目前只是质量 metadata，不自动替换 retrieval score，也没有在 SQL 中自动降权或剔除。[边界测试](../../tests/knowledge/test_hybrid_retrieval.py#L316-L359)

## Hybrid retrieval

PostgreSQL 通过 pgvector、`search_vector = to_tsvector('simple', search_text)`、full-text GIN 与 `pg_trgm` GIN 支撑三路检索。[迁移](../../src/db/migrations/versions/014_rag_hybrid_retrieval.py#L20-L55)

| 通道 | 当前实现 | 候选预算 / 门槛 |
| --- | --- | --- |
| dense | cosine similarity；query 加政策前缀 | 原查询最多 25、每条 rewrite 10；内部 `>=0.40` |
| sparse | bounded OR `to_tsquery` + `ts_rank_cd` | 50；rank `>0` |
| fuzzy | `pg_trgm similarity(search_text, query)` | 20；`>=0.10` |

Query rewrite 是本地确定性规则：保留原查询，最多附加 3 个、每个 160 字符的领域 alias；只扩展 query text，不改 trusted filters。缺可信 context、unsafe/out-of-domain 或已足够具体时跳过。[rewrite](../../src/knowledge/rewrite.py#L12-L185)

每条 query 的三路结果按 `(doc_key, chunk_id, policy_version)` 去重，用 `1/(60+rank)` 做 RRF；原查询与 rewrites 合并后最多 50 个。RRF 只决定顺序；candidate confidence 是 dense、归一化 sparse、fuzzy 三者最大值。[RRF](../../src/knowledge/retrieval.py#L152-L231) · [merge](../../src/knowledge/retrieval.py#L423-L461)

融合后要求 confidence `>=0.55`；无领域 anchor 时还要求 `>=0.70` 和 lexical overlap。Reranker 在 final top-k 前运行，默认 provider 关闭而使用 deterministic local fallback；其 `final_score` 只排序/诊断，`EvidenceRefV1.score` 与 strong/partial/no-evidence 状态仍使用 baseline confidence。[收口](../../src/knowledge/retrieval.py#L464-L548) · [reranker](../../src/knowledge/rerank.py#L59-L250)

三路 SQL 都在 top-k 前过滤 `tenant_id`、`effective_date <= context.effective_at.date()`，并传递可选 doc type/risk level。Facade 缺 `merchant_scope` 时返回 `no_evidence`；显式 merchant filter 不在 scope 时不调用 retriever。[repository](../../src/repositories/policy_chunk_repo.py#L193-L342) · [facade](../../src/knowledge/service.py#L126-L190)

## Verified evidence、ContextBuilder 与 provenance

`rag_context_build` 只接受完整 `EvidenceRefV1`，从 server runtime config 投影 `KnowledgeContext`；缺 trusted context/service 或异常时生成空 `build_error` package。[节点](../../src/agent/nodes/rag_context_build.py#L24-L55)

Canonical verification 对每个 candidate 执行：合法且匹配的 tenant、批内唯一 `(doc_key, chunk_id)`、tenant-scoped row 存在、当前 content hash 匹配、当前 `vN` 匹配、effective/expiry 有效、可选 merchant/doc type/risk scope 匹配。失败 ref 进入 typed exclusion，不进入 evidence map。[回查](../../src/repositories/policy_chunk_repo.py#L130-L191) · [校验](../../src/knowledge/service.py#L318-L413)

`ContextBuilder` 再按 canonical details 取内容、去重和预算化；默认最多 5 个 evidence items、单 snippet 220 字符、prompt 总计 8000 字符。它分离 prompt、verifier、debug 与各下游 safe projections；预算裁剪不会改变 evidence identity。[builder](../../src/agent/rag_context/builder.py#L54-L205) · [预算](../../src/agent/rag_context/builder.py#L319-L374)

详细 page/bbox/table/parser/OCR provenance 是旁路：先通过 tenant、唯一 key 与 hash 验证，再沿 source block refs 扩展 `DocumentBlock`。`EvidenceRefV1` 不携带 parser 字段；package 的 `source_locator` 目前也只有 doc/chunk，完整 locator 必须调用 verified provenance lookup。[provenance](../../src/knowledge/provenance.py#L45-L81) · [lookup](../../src/knowledge/service.py#L230-L290)

## Citation 与 MaterialClaim grounding

Recommendation 只从允许生成的 verified package 构造 citations。`validate_membership()` 要求每个 claim 至少引用一个、本轮 evidence set 中存在的完整 `evidence_id`；空 citation/空 claim list 失败。它刻意**不判断语义支持**。[membership](../../src/knowledge/citation.py#L15-L51) · [生成节点](../../src/agent/nodes/recommendation_generation.py#L170-L263)

通过 membership 后生成 `policy`、`business_fact`、`action_recommendation` 三类 `MaterialClaimV1`。`claim_verify` 随后：

1. 要求 package 存在且 status 为 `verified`、`partial` 或 `not_required`；
2. 先校验 policy/business claims，再校验 action dependencies；
3. 检查 verified-evidence membership、tenant 与 authority，拒绝 memory/model knowledge 冒充 policy/business authority；
4. 当前 canonical path 会执行基于文本的 negation gate；条件、金额、时间、exception 与 policy hierarchy 检查函数虽已存在，但依赖尚未由 `ContextBuilder` / Knowledge Service 投影的结构化 `domain_rule_metadata`，不能视为在线自动生效；
5. 对 policy claim 做 deterministic lexical support：完整 span 或 overlap `>=0.85` supported，`>=0.25` ambiguous，否则 unsupported；
6. business fact 必须由当前 tenant-matched `BusinessFactRefV1` 支持；action 必须同时依赖 supported policy 与 business claims。

只有无 blocked claims 的 bundle 才是 `verified + continue`；缺 authority/dependency、unsupported 或 error 进入 `final_response`，ambiguous/manual-review reason 进入人工复核。异常构造空安全 error bundle。[verifier](../../src/agent/rag_context/verifier.py#L265-L607) · [bundle 聚合](../../src/knowledge/service.py#L504-L610) · [节点](../../src/agent/nodes/claim_verify.py#L19-L112)

仓库另有 `SemanticSupportVerifier`，其 provider 缺失、timeout/error、畸形输出或预算超限均 `fail_closed`；但当前生产 `claim_verify -> verify_claims()` 链**没有调用它**。当前 canonical path 是 authority + 文本 negation gate + deterministic lexical support；其他 domain hard-rule helper 因缺少结构化 metadata producer 而未形成在线保证，也不能宣称在线运行 semantic judge。[semantic wrapper](../../src/agent/rag_context/verifier.py#L90-L263)

## Fail-closed 状态与路由

| Package 状态 | 当前语义 | Agent 路由 |
| --- | --- | --- |
| `verified` | 所有 candidates 通过 | recommendation |
| `partial` | 部分通过且没有更高优先级 hard reason | 仅低风险 advice/read 场景可继续；action/high-risk/unsafe refs 收口 |
| `no_evidence` | 无候选或无可用证据 | `final_response` |
| `unauthorized` | 明确 permission/ACL deny reason | `final_response` |
| `stale` | latest version、freshness 或 effective date 无效 | `final_response`；refs 进 `stale_refs` |
| `conflict` | 明确 policy/source conflict reason | `final_response`；refs 进 `conflict_refs` |
| `invalid_hash` | canonical content hash 不匹配 | `final_response` |
| `invalid_scope` | tenant/merchant/doc type/risk scope 无效 | `final_response` |
| `build_error` | 缺 trusted context、service/build exception | `final_response` |
| `not_required` | policy 明确不要求证据 | 仅 evidence policy/intent 确认不要求时继续 |

`route_after_rag_context()` 对未知状态和异常也默认 `final_response`。Claim bundle 必须同时满足无 blocked claims、`route=continue`、status 为 `verified/not_required`；有 proposed action 时还必须存在 `allows_action_recommendation=true`，随后仍进入 `risk_gate`。[package status](../../src/knowledge/service.py#L696-L755) · [RAG router](../../src/agent/routing.py#L1099-L1121) · [claim router](../../src/agent/routing.py#L1124-L1160)

```text
retrieval score            != verified evidence
candidate EvidenceRefV1    != verified fact
citation membership valid  != claim supported
verified policy evidence   != business fact or action authority
MaterialClaimV1 exists     != user-visible claim allowed
```

## 当前实现限制

- Repository SQL 尚无 document ACL、visibility、region 或 role/permission 条件；当前直接实现的是 tenant/effective/doc type/risk 过滤。
- Canonical row 当前投影 `merchant_ids=[]`、`expires_at=None`；`unauthorized`/`conflict` 契约和路由已存在，但 validator 尚不自动做 document ACL denial、supersedes/authority hierarchy 或 conflict detection。
- OCR confidence 尚未自动参与 retrieval/claim gate；完整 provenance 仍是单独 verified lookup。
- Rewrite 是规则表，rerank 默认 local；semantic wrapper 尚未接入 canonical claim path。

代表性验证入口：`tests/rag/test_ingestion_safety.py`、`tests/knowledge/test_hybrid_retrieval.py`、`tests/knowledge/test_verified_evidence_package.py`、`tests/agent/rag_context/test_context_builder.py`、`tests/agent/rag_context/test_verifier.py`、`tests/agent/rag_context/test_routing.py`。
