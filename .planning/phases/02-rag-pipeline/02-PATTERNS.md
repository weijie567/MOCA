# Phase 02: rag-pipeline - Pattern Map

**Mapped:** 2026-05-11
**Mode:** gap_closure
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `eval/golden_rag_queries.jsonl` | test data | batch | `scripts/eval_rag_hit_at_5.py` + `src/rag/chunker.py` | exact |
| `scripts/eval_rag_hit_at_5.py` | utility/eval | batch request-response | existing file | exact |
| `src/rag/retriever.py` | service | request-response | existing file + `tests/test_retriever.py` | exact |
| `src/repositories/policy_chunk_repo.py` | repository | vector search CRUD | existing file + `tests/test_search_integration.py` | exact |
| `data/policies/*.md` | knowledge content | file-I/O transform | `scripts/ingest_policies.py` + `src/rag/chunker.py` | exact |
| `src/rag/chunker.py` | utility | file-I/O transform | existing file + `tests/test_chunker.py` | exact |
| `tests/test_retriever.py` | test | request-response | existing file | exact |
| `tests/test_search_integration.py` | test | request-response + DB vector search | existing file | exact |

## Pattern Assignments

### `eval/golden_rag_queries.jsonl` (test data, batch)

**Analog:** `scripts/eval_rag_hit_at_5.py`, `src/rag/chunker.py`, current `data/policies/*.md`

**Golden-set contract** (`eval/golden_rag_queries.jsonl` lines 1-14):
```json
{"query": "用户申请仅退款但商家已经发货，客服应该怎么处理？", "expected_doc_ids": ["refund_policy"], "expected_chunk_ids": ["refund_policy_005"], "category": "refund_rule", "difficulty": "medium", "should_fallback": false}
{"query": "用户问如何更换银行卡绑定手机号？", "expected_doc_ids": [], "expected_chunk_ids": [], "category": "fallback", "difficulty": "easy", "should_fallback": true}
```

**Eval hit logic to satisfy** (`scripts/eval_rag_hit_at_5.py` lines 128-164):
```python
for case in cases:
    result = await retriever.search(query=case["query"], tenant_id=tenant_id, top_k=5)
    retrieved_ids = {evidence.chunk_id for evidence in result.evidence}

    if case.get("should_fallback"):
        hit = result.retrieval_status == "no_evidence"
        ...
        continue

    expected = set(case["expected_chunk_ids"])
    matched = bool(expected & retrieved_ids)
```

**Chunk ID source of truth** (`src/rag/chunker.py` lines 46-68):
```python
if len(body) <= max_chars:
    chunks.append(
        ChunkResult(
            doc_key=doc_key,
            chunk_id=f"{doc_key}_{chunk_index:03d}",
            section=section,
            content=body,
            chunk_index=chunk_index,
        )
    )
```

**Observed generated chunk map for golden labels:**
```text
refund_policy_001 -> 七天无理由退货退款
refund_policy_005 -> 已发货仅退款
quality_issue_policy_001 -> 质量问题定义
refund_policy_004 -> 举证标准
merchant_faq_007 -> 对平台判责不认可怎么办
cross_border_refund_004 -> 争议处理
return_shipping_002 -> 运费承担标准
digital_goods_refund_003 -> 已使用限制
partial_refund_rules_001 -> 适用场景
```

**Gap-closure guidance:** When changing golden cases, preserve JSONL shape and `should_fallback` semantics. Exact `expected_chunk_ids` should match `chunk_markdown` output after ingestion, not manually assumed heading order. If one query reasonably maps to multiple chunks, add all acceptable chunk IDs instead of weakening eval logic.

---

### `scripts/eval_rag_hit_at_5.py` (utility/eval, batch)

**Analog:** existing script

**Imports and wiring pattern** (lines 15-30):
```python
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant
from src.db.session import SessionLocal
from src.rag.embedder import EmbeddingService
from src.rag.retriever import Retriever
from src.repositories.policy_chunk_repo import PolicyChunkRepository
```

**Tenant resolution pattern** (lines 37-47):
```python
async def resolve_tenant_id(session: AsyncSession, tenant_id_str: str | None) -> UUID:
    if tenant_id_str:
        return UUID(tenant_id_str)

    stmt = select(Tenant).where(Tenant.status == "active").order_by(Tenant.created_at.asc()).limit(1)
    tenant = (await session.execute(stmt)).scalar_one_or_none()
    if tenant is None:
        print("ERROR: No active tenants in database. Run scripts/seed_demo.py first or pass --tenant-id.")
        sys.exit(1)
    return tenant.id
```

**Failure reporting pattern** (lines 89-97, 155-162):
```python
if failed_cases:
    print(f"\nFailed cases ({len(failed_cases)}):")
    for failed in failed_cases:
        print(f"  - {failed['query']}... | {failed['reason']}")
        if "expected" in failed:
            print(f"    expected: {failed['expected']}")
            print(f"    got:      {failed['got']}")
```

**Exit threshold pattern** (lines 166-177):
```python
hit_at_5 = hits / non_fallback if non_fallback else 0.0
fallback_acc = fallback_correct / fallback_total if fallback_total else 1.0

_print_report(len(cases), hit_at_5, fallback_acc, args.threshold, per_category, failed_cases)

if hit_at_5 < args.threshold or fallback_acc < args.threshold:
    print("\nFAIL: Below threshold")
    sys.exit(1)
```

**Gap-closure guidance:** It is safe to add diagnostic output that shows ranked `(chunk_id, score)` per failed case. Do not change the pass criterion from "any expected chunk in top 5" unless the phase requirement changes. Keep non-zero exit on Hit@5 or fallback accuracy below threshold.

---

### `src/rag/retriever.py` (service, request-response)

**Analog:** existing retriever and `tests/test_retriever.py`

**Imports and thresholds** (`src/rag/retriever.py` lines 3-12):
```python
from uuid import UUID

from src.rag.embedder import EmbeddingService
from src.rag.schemas import EvidenceItem, RetrievalResult
from src.repositories.policy_chunk_repo import PolicyChunkRepository

STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55
FALLBACK_MESSAGE = "当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"
```

**Core retrieval pattern** (`src/rag/retriever.py` lines 20-37):
```python
async def search(
    self,
    query: str,
    tenant_id: UUID,
    top_k: int = 5,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> RetrievalResult:
    query_embedding = await self.embedder.embed_query(query)

    results = await self.chunk_repo.search_similar(
        query_embedding=query_embedding,
        tenant_id=tenant_id,
        top_k=top_k,
        min_similarity=MIN_SIMILARITY_THRESHOLD,
        doc_type=doc_type,
        risk_level=risk_level,
    )
```

**Evidence shape pattern** (`src/rag/retriever.py` lines 39-49):
```python
evidence = [
    EvidenceItem(
        doc_key=chunk.document.doc_key,
        chunk_id=chunk.chunk_id,
        title=chunk.document.title,
        section=chunk.section,
        score=score,
        text=chunk.content[:300],
    )
    for chunk, score in results
]
```

**Fallback status pattern** (`src/rag/retriever.py` lines 51-64):
```python
best_score = max((item.score for item in evidence), default=0.0)
if not evidence or best_score < MIN_SIMILARITY_THRESHOLD:
    status = "no_evidence"
elif best_score >= STRONG_EVIDENCE_THRESHOLD:
    status = "strong_evidence"
else:
    status = "partial_evidence"
```

**Tests to copy when changing ranking/status** (`tests/test_retriever.py` lines 55-96):
```python
result = await retriever.search("仅退款怎么处理？", tenant_id=uuid4())
assert result.retrieval_status == "strong_evidence"

result = await retriever.search("退款规则是什么？", tenant_id=uuid4())
assert result.retrieval_status == "partial_evidence"

result = await retriever.search("如何更换银行卡绑定手机号？", tenant_id=uuid4())
assert result.retrieval_status == "no_evidence"
assert result.fallback_message == FALLBACK_MESSAGE
```

**Gap-closure guidance:** Preserve `top_k=5`, the `0.55` fallback threshold, and `0.70` strong threshold unless eval evidence proves threshold tuning is the minimal fix. Do not make retriever answer questions; it only returns evidence and status.

---

### `src/repositories/policy_chunk_repo.py` (repository, vector search CRUD)

**Analog:** existing repository and integration tests

**Imports pattern** (lines 3-9):
```python
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import PolicyChunk, PolicyDocument
```

**Vector search and tenant guard pattern** (lines 41-60):
```python
similarity_expr = 1 - PolicyChunk.embedding.cosine_distance(query_embedding)

stmt = (
    select(PolicyChunk, similarity_expr.label("score"))
    .join(
        PolicyDocument,
        and_(
            PolicyChunk.doc_id == PolicyDocument.id,
            PolicyDocument.tenant_id == tenant_id,
        ),
    )
    .options(selectinload(PolicyChunk.document))
    .where(
        and_(
            PolicyChunk.tenant_id == tenant_id,
            similarity_expr >= min_similarity,
        )
    )
    .order_by(PolicyChunk.embedding.cosine_distance(query_embedding))
    .limit(top_k)
)
```

**Metadata filter pattern** (lines 63-69):
```python
if doc_type:
    stmt = stmt.where(PolicyDocument.doc_type == doc_type)
if risk_level:
    stmt = stmt.where(PolicyChunk.risk_level == risk_level)

result = await self.session.execute(stmt)
return [(row[0], row[1]) for row in result.all()]
```

**Tenant-leak regression test pattern** (`tests/test_search_integration.py` lines 133-177):
```python
session.add(
    PolicyChunk(
        tenant_id=seeded_session["tenant"].id,
        doc_id=other_document.id,
        chunk_id="bad_cross_tenant_001",
        embedding=_unit_vector(0),
    )
)
...
assert payload["data"]["retrieval_status"] == "no_evidence"
assert payload["data"]["evidence"] == []
```

**Gap-closure guidance:** Ranking changes must keep both chunk tenant and joined document tenant filters. If adding reranking or diagnostics, keep the repository return type as `list[tuple[PolicyChunk, float]]` unless all callers/tests are updated.

---

### `data/policies/*.md` (knowledge content, file-I/O transform)

**Analog:** current corpus, `scripts/ingest_policies.py`, `src/rag/chunker.py`

**Manifest controls ingested files and metadata** (`scripts/ingest_policies.py` lines 26-42):
```python
DOCUMENT_MANIFEST = [
    {"file": "refund_policy.md", "doc_key": "refund_policy", "doc_type": "refund_rule", "risk_level": "high", "title": "退款规则"},
    {"file": "refund_sop.md", "doc_key": "refund_sop", "doc_type": "sop", "risk_level": "medium", "title": "退款处理SOP"},
    {"file": "merchant_faq.md", "doc_key": "merchant_faq", "doc_type": "faq", "risk_level": "low", "title": "商家FAQ"},
    {"file": "compensation_approval_sop.md", "doc_key": "compensation_approval_sop", "doc_type": "sop", "risk_level": "high", "title": "补偿审批SOP"},
]
```

**Markdown structure to preserve** (`data/policies/refund_policy.md` lines 1-16):
```markdown
# 退款规则

## 七天无理由退货退款
消费者在签收商品后七个自然日内申请退货退款，且商品保持完好、配件齐全、包装不影响二次销售的，客服可以受理。

## 已发货仅退款
订单已发货但消费者申请仅退款时，客服需先核对物流状态。
```

**Cross-document boundary example** (`data/policies/cross_border_refund.md` lines 6-13 and `data/policies/return_shipping.md` lines 6-7):
```markdown
## 时效与税费
跨境退货物流周期可延长至十五至三十日。已产生的税费、国际运费和清关服务费...

## 运费承担标准
七天无理由退货由用户承担寄回运费...质量问题、少件、破损、描述不符...由商家承担。
```

**Gap-closure guidance:** Content edits should be narrowly phrased to make existing golden queries semantically present in the intended chunk. Do not add new documents unless `DOCUMENT_MANIFEST` is updated and dry-run/live ingestion are rerun. Keep `##`/`###` sections coherent; a single section becomes a single retrieval chunk unless oversized.

---

### `src/rag/chunker.py` (utility, file-I/O transform)

**Analog:** existing chunker and `tests/test_chunker.py`

**Heading split pattern** (lines 17-28, 73-92):
```python
_HEADING_PATTERN = re.compile(r"^#{2,3}\s+(.+?)\s*$", re.MULTILINE)

def chunk_markdown(
    content: str,
    doc_key: str,
    max_chars: int = 1200,
    target_chars: int = 800,
    overlap_chars: int = 100,
) -> list[ChunkResult]:
    """Split Markdown policy text into stable heading-based chunks."""
```

**Intro behavior** (lines 77-90):
```python
if not matches:
    body = content.strip()
    return [("intro", body)] if body else []

intro = content[: matches[0].start()].strip()
if intro:
    sections.append(("intro", intro))
```

**Stable ID test pattern** (`tests/test_chunker.py` lines 24-37):
```python
first = chunk_markdown(markdown, "refund_policy")
second = chunk_markdown(markdown, "refund_policy")

assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
assert [chunk.chunk_id for chunk in first] == ["refund_policy_000", "refund_policy_001"]
assert all(chunk.doc_key == "refund_policy" for chunk in first)
```

**Gap-closure guidance:** Changing intro handling or heading logic is high blast radius: it changes every `chunk_id`, requires re-ingestion, and invalidates golden IDs. Prefer golden/corpus alignment first. If chunker changes are unavoidable, update `tests/test_chunker.py`, `eval/golden_rag_queries.jsonl`, and re-run ingestion.

---

### `tests/test_retriever.py` (test, request-response)

**Analog:** existing retriever unit tests

**Mock pattern** (lines 29-32):
```python
def _retriever(results: list[tuple[object, float]]) -> tuple[Retriever, AsyncMock, AsyncMock]:
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    chunk_repo = SimpleNamespace(search_similar=AsyncMock(return_value=results))
    return Retriever(chunk_repo=chunk_repo, embedder=embedder), chunk_repo.search_similar, embedder.embed_query
```

**Evidence metadata assertion pattern** (lines 99-112):
```python
result = await retriever.search("仅退款怎么处理？", tenant_id=uuid4())

item = result.evidence[0]
assert item.doc_key == "refund_policy"
assert item.chunk_id == "refund_policy_001"
assert item.title == "退款规则"
assert item.section == "仅退款"
assert item.score == 0.8
assert item.text == content[:300]
```

**Tenant isolation assertion pattern** (lines 145-164):
```python
allowed_result = await retriever.search("仅退款", tenant_id=allowed_tenant_id)
other_result = await retriever.search("仅退款", tenant_id=other_tenant_id)

assert allowed_result.retrieval_status == "strong_evidence"
assert other_result.retrieval_status == "no_evidence"
assert chunk_repo.search_similar.await_count == 2
```

**Gap-closure guidance:** Add unit tests here for any retriever-side ranking/status behavior. Do not use live embeddings in unit tests; keep `AsyncMock` and deterministic scores.

---

### `tests/test_search_integration.py` (test, request-response + DB vector search)

**Analog:** existing endpoint integration tests

**Deterministic vector seed pattern** (lines 13-59):
```python
def _unit_vector(index: int, dimensions: int = 1024) -> list[float]:
    vector = [0.0] * dimensions
    vector[index] = 1.0
    return vector

session.add_all(
    [
        PolicyChunk(
            chunk_id="test_refund_001",
            section="七天无理由",
            content="七天无理由退款需要商品不影响二次销售。",
            embedding=_unit_vector(0),
        ),
        PolicyChunk(
            chunk_id="test_refund_002",
            section="质量问题",
            content="质量问题退款需要买家提供照片或检测证明。",
            embedding=_unit_vector(1),
        ),
    ]
)
```

**Embedding patch pattern** (lines 75-87):
```python
with patch("src.api.routers.search.EmbeddingService") as embedding_service:
    embedding_service.return_value.embed_query = AsyncMock(return_value=_unit_vector(0))
    response = await _post_search(client, auth_headers, "七天无理由退款怎么处理？")

payload = response.json()
assert response.status_code == 200
assert payload["data"]["retrieval_status"] == "strong_evidence"
assert payload["data"]["evidence"][0]["chunk_id"] == "test_refund_001"
```

**Fallback integration pattern** (lines 100-114):
```python
with patch("src.api.routers.search.EmbeddingService") as embedding_service:
    embedding_service.return_value.embed_query = AsyncMock(return_value=_unit_vector(2))
    response = await _post_search(client, auth_headers, "如何更换银行卡绑定手机号？")

payload = response.json()
assert payload["data"]["retrieval_status"] == "no_evidence"
assert payload["data"]["evidence"] == []
assert payload["data"]["fallback_message"] is not None
```

**Gap-closure guidance:** Use this file for deterministic DB-level regression coverage if repository ranking/filtering changes. It should not call DashScope.

## Shared Patterns

### Safe Edit Boundaries

**Apply to:** all gap closure work

Current verified state from `02-VERIFICATION.md` and `02-HUMAN-UAT.md`: live ingestion passed, live endpoint passed, fallback accuracy is 100%, but live Hit@5 is 58.3%. Therefore:

- Prefer minimal fixes in `eval/golden_rag_queries.jsonl` and `data/policies/*.md` when failures are caused by expected chunk labeling or insufficient corpus wording.
- Preserve tenant scoping in `PolicyChunkRepository.search_similar`.
- Preserve fallback threshold behavior unless the eval diagnostics show threshold tuning is required and fallback remains >= 80%.
- Do not introduce reranker, LLM judge, LangChain, PDF parsing, or broad architecture changes.
- Re-run ingestion after corpus or chunker changes because DB embeddings are generated from file content.

### Authentication And API Boundary

**Source:** `src/api/routers/search.py`
**Apply to:** search endpoint callers/tests
```python
user: User = Security(get_current_user, scopes=["knowledge:read"]),
...
result = await retriever.search(
    query=body.query,
    tenant_id=user.tenant_id,
    top_k=body.top_k,
    doc_type=body.doc_type,
    risk_level=body.risk_level,
)
```

### Evaluation Commands

**Source:** `02-HUMAN-UAT.md`
**Apply to:** final verification after gap closure
```bash
set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7
set -a; source .env; set +a; UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/eval_rag_hit_at_5.py --tenant-id f078f8b4-01cc-5d39-b90c-fd0eea01bad7
```

### Deterministic Test Pattern

**Source:** `tests/test_search_integration.py`
**Apply to:** CI-safe tests
```python
with patch("src.api.routers.search.EmbeddingService") as embedding_service:
    embedding_service.return_value.embed_query = AsyncMock(return_value=_unit_vector(0))
    response = await _post_search(client, auth_headers, "七天无理由退款怎么处理？")
```

## No Analog Found

None. The gap closure should use the existing RAG eval, retrieval, repository, chunking, ingestion, and test patterns.

## Metadata

**Analog search scope:** `src/rag/`, `src/repositories/`, `src/api/routers/search.py`, `scripts/`, `tests/`, `eval/`, `data/policies/`
**Project instructions:** `CLAUDE.md` not present
**Project skills:** no project-local `.claude/skills/` or `.agents/skills/` found
**Files scanned:** 40+ from `src`, `tests`, `scripts`, `eval`, and `data/policies`
**Pattern extraction date:** 2026-05-11
