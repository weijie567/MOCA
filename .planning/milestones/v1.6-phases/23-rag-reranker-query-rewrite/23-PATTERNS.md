# Phase 23: RAG Reranker + Query Rewrite - Pattern Map

**Mapped:** 2026-06-20
**Files analyzed:** 17 new/modified files plus 1 generated eval artifact
**Analogs found:** 18 / 18 classified entries

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/knowledge/rewrite.py` | service/utility | transform, request-response | `src/knowledge/retrieval.py` | role-match |
| `src/knowledge/rerank.py` | service | batch, transform | `src/knowledge/retrieval.py` | exact |
| `src/knowledge/diagnostics.py` | model/utility | transform, report-only | `src/api/schemas/search.py` + `src/knowledge/service.py` | role-match |
| `src/knowledge/config.py` | config | request-response | `src/knowledge/config.py` | exact |
| `src/knowledge/retrieval.py` | service | request-response, batch fan-out | `src/knowledge/retrieval.py` | exact |
| `src/knowledge/service.py` | service/facade | request-response | `src/knowledge/service.py` | exact |
| `src/knowledge/schemas.py` | model | request-response | `src/knowledge/schemas.py` | exact |
| `tests/knowledge/test_query_rewrite.py` | test | transform, request-response | `tests/knowledge/test_retrieval.py` | role-match |
| `tests/knowledge/test_reranker.py` | test | batch, transform | `tests/knowledge/test_hybrid_retrieval.py` | exact |
| `tests/knowledge/test_retrieval_diagnostics.py` | test | report-only, request-response | `tests/knowledge/test_phase21_boundaries.py` | exact |
| `tests/knowledge/test_retrieval_budgets.py` | test | timeout/fallback, request-response | `tests/knowledge/test_retrieval.py` | role-match |
| `tests/knowledge/test_hybrid_retrieval.py` | test | request-response, batch fan-out | `tests/knowledge/test_hybrid_retrieval.py` | exact |
| `tests/knowledge/test_phase21_boundaries.py` | test | static guard | `tests/knowledge/test_phase21_boundaries.py` | exact |
| `tests/agent/rag_context/test_leakage.py` | test | leakage regression | `tests/agent/rag_context/test_leakage.py` | exact |
| `tests/test_rag_ablation_eval.py` | test | batch, file-I/O | `tests/test_rag_eval.py` | role-match |
| `scripts/eval_rag_ablation.py` | utility/script | batch, file-I/O | `scripts/eval_rag.py` + `scripts/eval_rag_hit_at_5.py` | role-match |
| `evaluation/golden/rag_cases.jsonl` | eval data | file-I/O, batch | `evaluation/golden/rag_cases.jsonl` | exact |
| `evaluation/reports/rag_ablation.json` | eval artifact | file-I/O, batch | `scripts/eval_rag.py` | role-match |

## Pattern Assignments

### `src/knowledge/rewrite.py` (service/utility, transform/request-response)

**Analog:** `src/knowledge/retrieval.py` for rule-first query analysis and skip baseline; `src/knowledge/schemas.py` for Pydantic DTO style.

**Imports pattern** (`src/knowledge/retrieval.py` lines 1-7; `src/knowledge/schemas.py` lines 11-15):

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field
```

**Rule-first token pattern** (`src/knowledge/retrieval.py` lines 36-37, 59-80):

```python
_ALNUM_PATTERN = re.compile(r"[a-z0-9]+")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")

def query_terms(text: str) -> set[str]:
    normalized = text.lower()
    terms = set(_ALNUM_PATTERN.findall(normalized))

    for segment in _CJK_PATTERN.findall(normalized):
        terms.update(segment)
        for size in (2, 3, 4):
            if len(segment) >= size:
                terms.update(segment[index : index + size] for index in range(len(segment) - size + 1))

    return {term for term in terms if term.strip()}
```

**Deterministic skip gate** (`src/knowledge/retrieval.py` lines 98-104, 356-364):

```python
def has_domain_anchor(query: str) -> bool:
    return any(anchor in query for anchor in _DOMAIN_ANCHORS)

def has_candidate_overlap(query_terms_value: set[str], chunk: object) -> bool:
    candidate_text = f"{chunk.document.title} {chunk.section} {chunk.content}"
    return overlap_ratio(query_terms_value, candidate_text) > 0

if has_domain_anchor(query):
    results = fused_results[:limit]
else:
    terms = query_terms(query)
    results = [
        candidate
        for candidate in fused_results
        if candidate.confidence >= STRONG_EVIDENCE_THRESHOLD and has_candidate_overlap(terms, candidate.chunk)
    ][:limit]
```

**DTO pattern** (`src/knowledge/service.py` lines 62-96):

```python
class VerifiedEvidenceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_ref: EvidenceRefV1
    content: str
    policy_document_version: int
    current_policy_version: str
    merchant_ids: list[str] = Field(default_factory=list)

class VerifiedEvidenceDetailsResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    included: dict[str, VerifiedEvidenceDetail] = Field(default_factory=dict)
    excluded: list[VerifiedEvidenceExclusion] = Field(default_factory=list)
```

**Apply:** Define a bounded `QueryRewritePlan`-style DTO with `model_config = ConfigDict(extra="forbid", frozen=True)`. Do not include tenant, merchant, role, doc type, risk, effective-date, policy-scope, or knowledge-scope fields.

---

### `src/knowledge/rerank.py` (service, batch/transform)

**Analog:** `src/knowledge/retrieval.py`

**Candidate and trace shape** (`src/knowledge/retrieval.py` lines 107-156):

```python
@dataclass(frozen=True)
class PolicyRetrievalHit:
    doc_key: str
    chunk_id: str
    title: str
    section: str
    policy_version: str
    text: str
    score: float
    rank: int
    selected_by: tuple[str, ...] = ()
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fuzzy_rank: int | None = None
    rrf_score: float | None = None
    filter_status: str = "passed"

@dataclass
class _FusedCandidate:
    chunk: object
    dense_score: float | None = None
    sparse_score: float | None = None
    fuzzy_score: float | None = None
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fuzzy_rank: int | None = None
    rrf_score: float = 0.0
```

**Deterministic lexical rerank pattern** (`src/knowledge/retrieval.py` lines 83-95):

```python
def rerank_candidates(query: str, raw_results: list[tuple[object, float]]) -> list[tuple[object, float]]:
    terms = query_terms(query)
    scored = []

    for rank, (chunk, vector_score) in enumerate(raw_results):
        title_section = f"{chunk.document.title} {chunk.section}"
        title_section_boost = TITLE_SECTION_BOOST * overlap_ratio(terms, title_section)
        content_boost = CONTENT_OVERLAP_BOOST * overlap_ratio(terms, chunk.content)
        hybrid_score = vector_score + title_section_boost + content_boost
        scored.append((chunk, vector_score, hybrid_score, rank))

    scored.sort(key=lambda item: (-item[2], item[3]))
    return [(chunk, vector_score) for chunk, vector_score, _, _ in scored]
```

**Confidence pattern** (`src/knowledge/retrieval.py` lines 147-156, 159-160):

```python
@property
def confidence(self) -> float:
    scores = []
    if self.dense_score is not None:
        scores.append(_clamp_score(self.dense_score))
    if self.sparse_score is not None:
        scores.append(normalize_sparse_score(self.sparse_score))
    if self.fuzzy_score is not None:
        scores.append(_clamp_score(self.fuzzy_score))
    return max(scores, default=0.0)

def normalize_sparse_score(raw_score: float) -> float:
    return _clamp_score(raw_score / SPARSE_SCORE_SCALE)
```

**Apply:** Keep default reranking local and deterministic. Rerank candidates or hit-like DTOs before evidence construction, preserve `score` confidence semantics, and put rerank components in diagnostics only.

---

### `src/knowledge/diagnostics.py` (model/utility, report-only transform)

**Analog:** `src/api/schemas/search.py` for public trace exclusion; `src/knowledge/service.py` for strict internal DTOs.

**Public exclusion pattern** (`src/api/schemas/search.py` lines 6-17):

```python
class EvidenceItem(BaseModel):
    doc_key: str
    chunk_id: str
    title: str
    section: str
    score: float = Field(ge=0.0, le=1.0)
    text: str
    selected_by: list[str] | None = Field(default=None, exclude=True)
    dense_rank: int | None = Field(default=None, exclude=True)
    sparse_rank: int | None = Field(default=None, exclude=True)
    fuzzy_rank: int | None = Field(default=None, exclude=True)
    rrf_score: float | None = Field(default=None, exclude=True)
```

**Strict internal DTO pattern** (`src/knowledge/service.py` lines 78-96):

```python
class VerifiedEvidenceExclusion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    reason_code: str
    reason_codes: list[str]
    doc_key: str | None = None
    chunk_id: str | None = None

class VerifiedEvidenceDetailsResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    included: dict[str, VerifiedEvidenceDetail] = Field(default_factory=dict)
    excluded: list[VerifiedEvidenceExclusion] = Field(default_factory=list)
```

**Apply:** New diagnostics DTOs should be strict, frozen, and internal/eval-only. They may include safe selected channels, rank deltas, config versions, fallback reasons, and selected candidate IDs; they must not include raw rewrite prompts, raw provider payloads, private reasoning, OCR/parser/source-block internals, business facts, or unbounded policy text.

---

### `src/knowledge/config.py` (config, request-response)

**Analog:** `src/knowledge/config.py`

**Current config pattern** (`src/knowledge/config.py` lines 1-14):

```python
from __future__ import annotations

# Single source for knowledge retrieval/rerank config version literals (RESEARCH GAP-3).
RETRIEVAL_CONFIG_VERSION = "retrieval.v3"
RERANK_CONFIG_VERSION = "rerank.v2"

# Thresholds used by the knowledge-owned retrieval engine.
STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55

# Prompt-only policy text bounds. Full chunk content remains the source for text_hash.
MAX_EVIDENCE_TEXT_CHARS = 1600
MAX_PROMPT_EVIDENCE_ITEMS = 5
MAX_PROMPT_EVIDENCE_TOTAL_CHARS = MAX_EVIDENCE_TEXT_CHARS * MAX_PROMPT_EVIDENCE_ITEMS
```

**Apply:** Add Phase 23 version/budget constants here, not as scattered literals. Use explicit names for rewrite stage timeout, rerank stage timeout, original depth, rewrite count, per-rewrite top-k, merged candidate cap, diagnostic top-k, snippet char limit, retry limit, and provider enabled/default-disabled flags.

---

### `src/knowledge/retrieval.py` (service, request-response/batch fan-out)

**Analog:** `src/knowledge/retrieval.py`

**Imports/dependency pattern** (`src/knowledge/retrieval.py` lines 1-20):

```python
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.config import (
    MIN_SIMILARITY_THRESHOLD,
    RETRIEVAL_CONFIG_VERSION,
    STRONG_EVIDENCE_THRESHOLD,
)
from src.knowledge.provenance import EvidenceProvenance
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext
from src.rag.embedder import EmbeddingService
from src.rag.search_text import build_policy_chunk_search_text, build_sparse_query_text
from src.repositories.policy_chunk_repo import PolicyChunkRepository
```

**Evidence construction boundary** (`src/knowledge/retrieval.py` lines 217-247):

```python
async def retrieve(
    self,
    *,
    query: str,
    context: KnowledgeContext,
    max_results: int,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> tuple[str, list[EvidenceRefV1], float]:
    status, hits, best_score = await self.retrieve_hits(
        query=query,
        context=context,
        max_results=max_results,
        doc_type=doc_type,
        risk_level=risk_level,
    )
    evidence_refs = [
        EvidenceRefV1.build(
            tenant_id=context.tenant_id,
            doc_key=hit.doc_key,
            chunk_id=hit.chunk_id,
            policy_version=hit.policy_version,
            text=hit.text,
            retrieved_at=context.effective_at,
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            score=hit.score,
            rank=hit.rank,
        )
        for hit in hits
    ]
    return status, evidence_refs, best_score
```

**Timeout/fallback pattern** (`src/knowledge/retrieval.py` lines 249-270):

```python
async def retrieve_hits(
    self,
    *,
    query: str,
    context: KnowledgeContext,
    max_results: int,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> tuple[str, list[PolicyRetrievalHit], float]:
    try:
        return await asyncio.wait_for(
            self._retrieve_hits(
                query=query,
                context=context,
                max_results=max_results,
                doc_type=doc_type,
                risk_level=risk_level,
            ),
            timeout=RETRIEVAL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return "error", [], 0.0
```

**Channel fan-out with trusted filters** (`src/knowledge/retrieval.py` lines 305-340):

```python
effective_at = _parse_effective_at(context.effective_at)
effective_date = effective_at.date()
limit = max(max_results, 1)
query_embedding = await self.embedder.embed_query(f"{QUERY_PREFIX}{query}")
query_search_text = build_policy_chunk_search_text(title="", section="", content=query)
sparse_query_text = build_sparse_query_text(query)
dense_raw_results = await self.chunk_repo.search_similar(
    query_embedding=query_embedding,
    tenant_id=UUID(context.tenant_id),
    top_k=max(limit * CANDIDATE_MULTIPLIER, limit),
    min_similarity=INTERNAL_SEARCH_THRESHOLD,
    doc_type=doc_type,
    risk_level=risk_level,
    effective_date=effective_date,
)
sparse_raw_results = await _call_optional_channel(
    self.chunk_repo,
    "search_sparse",
    query_text=sparse_query_text,
    tenant_id=UUID(context.tenant_id),
    top_k=SPARSE_CANDIDATE_TOP_K,
    doc_type=doc_type,
    risk_level=risk_level,
    effective_date=effective_date,
)
```

**Fusion/dedupe pattern** (`src/knowledge/retrieval.py` lines 163-197, 427-428):

```python
def rrf_fuse_candidates(
    channel_results: dict[str, list[tuple[object, float]]],
) -> list[_FusedCandidate]:
    candidates: dict[tuple[str, str, str], _FusedCandidate] = {}

    for channel, results in channel_results.items():
        seen_in_channel: set[tuple[str, str, str]] = set()
        for rank, (chunk, raw_score) in enumerate(results, start=1):
            key = _candidate_key(chunk)
            if key in seen_in_channel:
                continue
            seen_in_channel.add(key)
            candidate = candidates.setdefault(key, _FusedCandidate(chunk=chunk))
            candidate.rrf_score += 1 / (RRF_K + rank)

    return sorted(
        candidates.values(),
        key=lambda candidate: (
            -candidate.rrf_score,
            -candidate.confidence,
            str(candidate.chunk.document.doc_key),
            str(candidate.chunk.chunk_id),
        ),
    )

def _candidate_key(chunk: object) -> tuple[str, str, str]:
    return (str(chunk.document.doc_key), str(chunk.chunk_id), _policy_version(chunk))
```

**Apply:** Extract a helper for one query expression's dense/sparse/fuzzy/RRF bundle, call it first for the original query, then for bounded rewrite expansions with identical trusted filters. Merge/dedupe by `_candidate_key()` before final rerank and before `EvidenceRefV1.build()`.

---

### `src/knowledge/service.py` (service/facade, request-response)

**Analog:** `src/knowledge/service.py`

**Facade auth gate and fail-closed pattern** (`src/knowledge/service.py` lines 103-154):

```python
async def search(
    self,
    request: KnowledgeSearchRequest,
    context: KnowledgeContext,
) -> KnowledgeSearchResult:
    merchant_id = request.filters.merchant_id
    merchant_scope = context.merchant_scope
    if not merchant_scope:
        return self._no_evidence_result()
    if merchant_id is not None and "*" not in merchant_scope and merchant_id not in merchant_scope:
        return self._no_evidence_result()

    doc_type = request.filters.policy_types[0] if request.filters.policy_types else None
    try:
        status, evidence_refs, best_score = await self.retriever.retrieve(
            query=request.query,
            context=context,
            max_results=request.max_results,
            doc_type=doc_type,
        )
    except asyncio.TimeoutError:
        return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
    except Exception:
        return self._error_result(
            "SEARCH_ERROR",
            "Failed to search policy evidence",
            retryable=False,
        )

    return KnowledgeSearchResult(
        status=status,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=best_score,
        threshold=MIN_SIMILARITY_THRESHOLD,
        evidence_refs=evidence_refs,
    )
```

**No-evidence/error result pattern** (`src/knowledge/service.py` lines 375-400):

```python
@staticmethod
def _no_evidence_result() -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        status="no_evidence",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=0.0,
        threshold=MIN_SIMILARITY_THRESHOLD,
        evidence_refs=[],
    )

@staticmethod
def _error_result(error_code: str, message: str, *, retryable: bool) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        status="error",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=0.0,
        threshold=MIN_SIMILARITY_THRESHOLD,
        evidence_refs=[],
        error={"error_code": error_code, "message": message, "retryable": retryable},
    )
```

**Apply:** Keep authorization outside rewrite. If `KnowledgeSearchResult.query_rewrite` is populated, pass only a safe summary/compatibility value; raw rewrite/rerank diagnostics belong in internal/eval DTOs.

---

### `src/knowledge/schemas.py` (model, request-response)

**Analog:** `src/knowledge/schemas.py`

**Evidence identity shape** (`src/knowledge/schemas.py` lines 31-69):

```python
class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
    score: float | None = None
    rank: int | None = Field(default=None, ge=1)

    @classmethod
    def build(
        cls,
        *,
        tenant_id: str,
        doc_key: str,
        chunk_id: str,
        policy_version: str,
        text: str,
        retrieved_at: str,
        retrieval_config_version: str,
        score: float | None = None,
        rank: int | None = None,
    ) -> EvidenceRefV1:
        return cls(
            tenant_id=tenant_id,
            evidence_id=f"{doc_key}/{chunk_id}@{policy_version}",
            doc_key=doc_key,
            chunk_id=chunk_id,
            policy_version=policy_version,
            text_hash=evidence_text_hash(text),
            retrieved_at=retrieved_at,
            retrieval_config_version=retrieval_config_version,
            score=score,
            rank=rank,
        )
```

**Knowledge search contracts** (`src/knowledge/schemas.py` lines 94-117):

```python
class KnowledgeSearchRequest(BaseModel):
    schema_version: Literal["knowledge_search_request.v2"] = "knowledge_search_request.v2"
    query: str
    primary_intent: str | None = None
    business_context_refs: list[dict] = Field(default_factory=list)
    filters: KnowledgeSearchFilters
    retrieval_config_version: str
    rerank_config_version: str
    max_results: int = 5
    allow_partial_evidence: bool = True

class KnowledgeSearchResult(BaseModel):
    schema_version: Literal["knowledge_search_result.v2"] = "knowledge_search_result.v2"
    status: Literal["strong_evidence", "partial_evidence", "no_evidence", "error"]
    query_rewrite: str | None = None
    retrieval_config_version: str
    rerank_config_version: str
    best_score: float
    threshold: float
    evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    citation_validation: CitationValidationResult = Field(default_factory=CitationValidationResult)
    summary: str | None = None
    error: dict | None = None
```

**Apply:** Do not modify `EvidenceRefV1` fields. If new DTOs are needed, put internal rewrite/rerank/diagnostic DTOs in `src/knowledge/rewrite.py`, `src/knowledge/rerank.py`, or `src/knowledge/diagnostics.py`; keep `KnowledgeSearchResult.query_rewrite` safe-summary only.

---

### `tests/knowledge/test_query_rewrite.py` (test, transform/request-response)

**Analog:** `tests/knowledge/test_retrieval.py`

**Helper pattern** (`tests/knowledge/test_retrieval.py` lines 21-56):

```python
def _chunk(
    chunk_id: str = "refund_policy_001",
    doc_key: str = "refund_policy",
    title: str = "退款规则",
    section: str = "仅退款",
    content: str = "用户申请仅退款但商家已经发货时，客服应先核实物流状态和商家举证。",
):
    return SimpleNamespace(
        chunk_id=chunk_id,
        section=section,
        content=content,
        effective_date=date(2026, 1, 1),
        document=SimpleNamespace(doc_key=doc_key, title=title, version=1),
    )

def _context(tenant_id) -> KnowledgeContext:
    return KnowledgeContext(
        tenant_id=str(tenant_id),
        user_id="user-1",
        role="support_agent",
        merchant_scope=["*"],
        run_id="run-1",
        trace_id="trace-1",
        effective_at="2026-06-14T00:00:00+00:00",
    )
```

**Skip/no-evidence assertions** (`tests/knowledge/test_retrieval.py` lines 230-237):

```python
@pytest.mark.asyncio
async def test_out_of_domain_query_falls_back_even_with_weak_policy_matches():
    engine, _, _ = _engine([(_chunk(section="沟通话术", content="客服应说明证据缺口和申诉入口。"), 0.57)])

    status, hits, _ = await _retrieve_hits(engine, "用户问如何更换银行卡绑定手机号？", uuid4(), max_results=5)

    assert status == "no_evidence"
    assert hits == []
```

**Apply:** Use pure unit tests for `QueryRewritePlan`: original query preserved, bounded expansions, deterministic skip reasons, no trusted filter fields, and safe summary excludes raw prompt/provider/private fields.

---

### `tests/knowledge/test_reranker.py` (test, batch/transform)

**Analog:** `tests/knowledge/test_hybrid_retrieval.py`

**Mock engine pattern** (`tests/knowledge/test_hybrid_retrieval.py` lines 55-67):

```python
def _engine(
    *,
    dense: list[tuple[object, float]] | None = None,
    sparse: list[tuple[object, float]] | None = None,
    fuzzy: list[tuple[object, float]] | None = None,
) -> tuple[PolicyRetrievalEngine, object]:
    repo = SimpleNamespace(
        search_similar=AsyncMock(return_value=dense or []),
        search_sparse=AsyncMock(return_value=sparse or []),
        search_fuzzy=AsyncMock(return_value=fuzzy or []),
    )
    embedder = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2, 0.3]))
    return PolicyRetrievalEngine(chunk_repo=repo, embedder=embedder), repo
```

**RRF/score semantics assertions** (`tests/knowledge/test_hybrid_retrieval.py` lines 106-121):

```python
@pytest.mark.asyncio
async def test_rrf_score_does_not_replace_normalized_confidence_score() -> None:
    target = _chunk("refund_timeout_001", section="退款时效", content="退款时效超过48小时需要核实支付通道。")
    engine, _ = _engine(sparse=[(target, 0.16)])

    _, hits, best_score = await engine.retrieve_hits(
        query="退款时效超过48小时怎么办？",
        context=_context(),
        max_results=5,
    )

    assert hits[0].selected_by == ("sparse",)
    assert hits[0].score == pytest.approx(0.8)
    assert best_score == pytest.approx(0.8)
    assert hits[0].rrf_score != hits[0].score
    assert normalize_sparse_score(0.16) == pytest.approx(0.8)
```

**Trace-stays-internal assertion** (`tests/knowledge/test_hybrid_retrieval.py` lines 151-163):

```python
@pytest.mark.asyncio
async def test_retrieval_trace_stays_internal_to_hits() -> None:
    target = _chunk("refund_policy_001")
    engine, _ = _engine(dense=[(target, 0.82)], sparse=[(target, 0.12)])
    context = _context()

    _, hits, _ = await engine.retrieve_hits(query="仅退款怎么处理？", context=context, max_results=5)
    _, refs, _ = await engine.retrieve(query="仅退款怎么处理？", context=context, max_results=5)

    assert hits[0].selected_by == ("dense", "sparse")
    assert hits[0].rrf_score is not None
    assert "selected_by" not in refs[0].model_dump()
    assert "rrf_score" not in refs[0].model_dump()
```

**Apply:** Test deterministic ordering, identity preservation, bounded input snippets, provider disabled/timeout/error/malformed/budget fallback, and rerank-before-evidence behavior.

---

### `tests/knowledge/test_retrieval_diagnostics.py` (test, report-only/request-response)

**Analog:** `tests/knowledge/test_phase21_boundaries.py`

**Public serialization exclusion** (`tests/knowledge/test_phase21_boundaries.py` lines 196-239):

```python
def test_public_search_api_evidence_serialization_excludes_phase21_internal_fields() -> None:
    fields = set(EvidenceItem.model_fields)
    assert fields == {
        "doc_key",
        "chunk_id",
        "title",
        "section",
        "score",
        "text",
        "selected_by",
        "dense_rank",
        "sparse_rank",
        "fuzzy_rank",
        "rrf_score",
    }

    response = RetrievalResult(
        query="退款规则",
        retrieval_status="strong_evidence",
        evidence=[
            EvidenceItem(
                doc_key="refund-policy",
                chunk_id="chunk-001",
                title="退款规则",
                section="仅退款",
                score=0.91,
                text="Verified policy excerpt.",
                selected_by=["dense", "sparse"],
                dense_rank=1,
                sparse_rank=1,
                fuzzy_rank=None,
                rrf_score=0.42,
            )
        ],
        best_score=0.91,
    )

    dumped = response.model_dump()
    evidence = dumped["evidence"][0]
    assert "selected_by" not in evidence
    assert "rrf_score" not in evidence
```

**Evidence shape guard** (`tests/knowledge/test_phase21_boundaries.py` lines 175-193):

```python
def test_evidence_ref_v1_remains_the_only_policy_evidence_authority_shape() -> None:
    fields = set(EvidenceRefV1.model_fields)

    assert "evidence_id" in fields
    assert "text_hash" in fields
    assert fields == {
        "schema_version",
        "tenant_id",
        "evidence_id",
        "doc_key",
        "chunk_id",
        "policy_version",
        "text_hash",
        "retrieved_at",
        "retrieval_config_version",
        "score",
        "rank",
    }
```

**Apply:** Assert diagnostics contain only safe components and do not appear in `EvidenceRefV1`, public `model_dump()`, prompt/final/memory/replay/action surfaces, or business fact/tool payloads.

---

### `tests/knowledge/test_retrieval_budgets.py` (test, timeout/fallback)

**Analog:** `src/knowledge/retrieval.py` plus `tests/knowledge/test_retrieval.py`

**Timeout fallback source** (`src/knowledge/retrieval.py` lines 249-270):

```python
try:
    return await asyncio.wait_for(
        self._retrieve_hits(
            query=query,
            context=context,
            max_results=max_results,
            doc_type=doc_type,
            risk_level=risk_level,
        ),
        timeout=RETRIEVAL_TIMEOUT_SECONDS,
    )
except asyncio.TimeoutError:
    return "error", [], 0.0
```

**No-evidence status test pattern** (`tests/knowledge/test_retrieval.py` lines 99-118):

```python
@pytest.mark.asyncio
async def test_no_evidence_status():
    engine, _, _ = _engine([])

    status, hits, best_score = await _retrieve_hits(engine, "如何更换银行卡绑定手机号？", uuid4())

    assert status == "no_evidence"
    assert best_score == 0.0
    assert hits == []
```

**Apply:** Test explicit config constants and fallback behavior for rewrite timeout, rerank timeout, disabled provider, provider error, malformed output, and budget overflow.

---

### `tests/knowledge/test_hybrid_retrieval.py` (test, request-response/batch fan-out)

**Analog:** `tests/knowledge/test_hybrid_retrieval.py`

**Trusted filter propagation** (`tests/knowledge/test_hybrid_retrieval.py` lines 166-188):

```python
@pytest.mark.asyncio
async def test_each_hybrid_channel_receives_scope_filters() -> None:
    tenant_id = uuid4()
    engine, repo = _engine(dense=[(_chunk("refund_policy_001"), 0.82)])

    await engine.retrieve_hits(
        query="仅退款怎么处理？",
        context=_context(tenant_id),
        max_results=5,
        doc_type="refund_rule",
        risk_level="high",
    )

    for method_name in ("search_similar", "search_sparse", "search_fuzzy"):
        kwargs = getattr(repo, method_name).await_args.kwargs
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["doc_type"] == "refund_rule"
        assert kwargs["risk_level"] == "high"
        assert kwargs["effective_date"] == date(2026, 6, 14)
    assert repo.search_sparse.await_args.kwargs["top_k"] == SPARSE_CANDIDATE_TOP_K
    assert repo.search_fuzzy.await_args.kwargs["top_k"] == FUZZY_CANDIDATE_TOP_K
```

**Repository filter SQL pattern** (`tests/knowledge/test_hybrid_retrieval.py` lines 205-238):

```python
@pytest.mark.asyncio
async def test_repository_sparse_and_fuzzy_methods_apply_scope_filters() -> None:
    session = _RecordingSession()
    repo = PolicyChunkRepository(session)  # type: ignore[arg-type]
    tenant_id = uuid4()

    await repo.search_sparse(
        query_text="仅退款 商家举证",
        tenant_id=tenant_id,
        doc_type="refund_rule",
        risk_level="high",
        effective_date=date(2026, 6, 14),
    )
    await repo.search_fuzzy(
        query_text="仅退款 商家举证",
        tenant_id=tenant_id,
        doc_type="refund_rule",
        risk_level="high",
        effective_date=date(2026, 6, 14),
    )

    sparse_sql = str(session.statements[0].compile(compile_kwargs={"literal_binds": False})).lower()
    fuzzy_sql = str(session.statements[1].compile(compile_kwargs={"literal_binds": False})).lower()

    assert "@@" in sparse_sql
    assert "to_tsquery" in sparse_sql
    assert "similarity" in fuzzy_sql
```

**Apply:** Extend with original-plus-rewrite channel assertions. Inspect each call in `await_args_list`, not just the last call, so every rewritten channel proves identical tenant/doc/risk/effective-date filters.

---

### `tests/knowledge/test_phase21_boundaries.py` (test, static guard)

**Analog:** `tests/knowledge/test_phase21_boundaries.py`

**Forbidden patterns and allowlist shape** (`tests/knowledge/test_phase21_boundaries.py` lines 19-80):

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPLEMENTATION_PATTERNS = {
    "QueryRewriteService": "QueryRewriteService",
    "query_rewriter": "query_rewriter",
    "rewrite_query(": "rewrite_query(",
    "CrossEncoderReranker": "CrossEncoderReranker",
    "ExternalRerankClient": "ExternalRerankClient",
    "SearchBackend": "SearchBackend",
    "Vespa": "Vespa",
    "OpenSearch": "OpenSearch",
    "external_action_execution": "external_action_execution",
    "action_outbox_events": "action_outbox_events",
    "outbox_worker": "outbox_worker",
    "action_compensation_records": "action_compensation_records",
    "compensation_dispatch": "compensation_dispatch",
    "PolicySourceOperations": "PolicySourceOperations",
    "PolicySourceReviewUI": "PolicySourceReviewUI",
}

IGNORED_STATIC_GUARD_FILES = {
    Path("tests/knowledge/test_phase21_boundaries.py"),
}

ALLOWED_COMPATIBILITY_REFERENCES = {
    Path("src/knowledge/schemas.py"): {"query_rewrite", "rerank_config_version"},
    Path("src/knowledge/config.py"): {"RERANK_CONFIG_VERSION"},
    Path("src/knowledge/retrieval.py"): {"rerank_candidates"},
}
```

**Scanner pattern** (`tests/knowledge/test_phase21_boundaries.py` lines 94-121):

```python
def _implementation_python_files() -> list[Path]:
    files: list[Path] = []
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        files.extend(path for path in root.rglob("*.py") if path.is_file())
    return sorted(path for path in files if path.relative_to(REPO_ROOT) not in IGNORED_STATIC_GUARD_FILES)

def test_phase21_boundary_allows_phase22_claim_verifier_files_but_no_phase23_rag5_or_execution_surfaces() -> None:
    violations: list[str] = []

    for path in _implementation_python_files():
        relative = path.relative_to(REPO_ROOT)
        source = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_IMPLEMENTATION_PATTERNS.items():
            if _is_phase22_owned_surface(relative, label):
                continue
            if pattern in source:
                violations.append(f"{relative}: {label}")

    assert violations == []
```

**Apply:** Add a narrow Phase 23 owner allowlist for `src/knowledge/rewrite.py`, `src/knowledge/rerank.py`, `src/knowledge/diagnostics.py`, focused knowledge tests, and eval tests. Keep RAG-5 `SearchBackend`/Vespa/OpenSearch, Phase 17 execution/outbox/compensation, and Policy Source Operations UI patterns forbidden.

---

### `tests/agent/rag_context/test_leakage.py` (test, leakage regression)

**Analog:** `tests/knowledge/test_phase21_boundaries.py` and existing leakage tests.

**Replay/action leakage guard pattern** (`tests/knowledge/test_phase21_boundaries.py` lines 313-339, 359-374):

```python
def test_action_snapshot_ignores_parser_ocr_source_metadata_on_evidence_inputs() -> None:
    evidence_with_internal_metadata = _evidence_ref().model_dump() | {
        "source_block_id": "refund-policy:policy_pdf:text:0001",
        "parser_metadata_json": {"raw_payload": RAW_PARSER_PAYLOAD},
        "ocr_metadata_json": {"hidden_text": HIDDEN_PROMPT_INJECTION},
        "rag_ingestion_job_id": "job-001",
    }

    snapshot = build_action_safety_snapshot(
        tenant_id="tenant-001",
        run_id="run-001",
        snapshot_id="snap-001",
        snapshot_ref="snapshot:snap-001",
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        retrieval_config_version="retrieval.v3",
        evidence=[evidence_with_internal_metadata],
        action_payload_hash="sha256:" + "a" * 64,
        created_at="2026-06-15T00:00:00.000Z",
    )

    dumped = snapshot.model_dump(mode="json")
    assert HIDDEN_PROMPT_INJECTION not in str(dumped)
    assert RAW_PARSER_PAYLOAD not in str(dumped)
```

**Apply:** If Phase 23 adds diagnostics to any object consumed by prompt/final/memory/replay/action paths, extend leakage sentinels for raw rewrite prompt, raw provider payload, private reasoning, full ranking trace, and unbounded policy text.

---

### `tests/test_rag_ablation_eval.py` (test, batch/file-I/O)

**Analog:** `tests/test_rag_eval.py`

**Eval test helper pattern** (`tests/test_rag_eval.py` lines 7-47):

```python
def _result(
    *,
    status: str = "strong_evidence",
    evidence: list[EvidenceItem] | None = None,
) -> RetrievalResult:
    items = evidence or []
    return RetrievalResult(
        query="test query",
        retrieval_status=status,
        evidence=items,
        best_score=max((item.score for item in items), default=0.0),
    )

def _evidence(
    *,
    doc_key: str = "refund_policy",
    chunk_id: str = "refund_policy_001",
    section: str = "七天无理由退货退款",
    score: float = 0.82,
    text: str = "消费者在签收商品后七个自然日内申请退货退款，且商品保持完好。",
    selected_by: list[str] | None = None,
    dense_rank: int | None = None,
    sparse_rank: int | None = None,
    fuzzy_rank: int | None = None,
    rrf_score: float | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        doc_key=doc_key,
        chunk_id=chunk_id,
        title="退款规则",
        section=section,
        score=score,
        text=text,
        selected_by=selected_by,
        dense_rank=dense_rank,
        sparse_rank=sparse_rank,
        fuzzy_rank=fuzzy_rank,
        rrf_score=rrf_score,
    )
```

**Metric assertions pattern** (`tests/test_rag_eval.py` lines 49-95):

```python
def test_score_case_hits_when_expected_chunk_is_in_top5():
    case = {
        "query": "七天无理由退款怎么处理？",
        "expected_doc_ids": ["refund_policy"],
        "expected_chunk_ids": ["refund_policy_001"],
        "should_fallback": False,
    }

    score = _score_case(case, _result(evidence=[_evidence()]))

    assert score["hit"] is True
    assert score["reason"] == "expected_chunk_in_top5"
    assert score["expected_doc_id_hit"] is True
    assert score["got_chunks"] == ["refund_policy_001"]
```

**Apply:** Unit-test ablation report helpers without DB credentials. Assert variants include dense-only, sparse-only, fuzzy-only, RRF, rewrite, reranker, and rewrite-plus-reranker; report metrics include Hit@K, MRR/rank quality, citation-support compatibility, no-evidence precision, unsafe retrieval rate, fallback rate, and latency percentiles.

---

### `scripts/eval_rag_ablation.py` (utility/script, batch/file-I/O)

**Analog:** `scripts/eval_rag.py` for structured JSON output; `scripts/eval_rag_hit_at_5.py` for hybrid trace diagnostics.

**CLI and defaults pattern** (`scripts/eval_rag.py` lines 1-11, 36-65):

```python
"""RAG evaluation script.

Usage:
    uv run python scripts/eval_rag.py
    uv run python scripts/eval_rag.py --golden-set evaluation/golden/rag_cases.jsonl
    uv run python scripts/eval_rag.py --threshold 0.85
    uv run python scripts/eval_rag.py --tenant-id <uuid>

Requires a running PostgreSQL database with ingested policy documents.
Exits non-zero if Hit@5 or fallback accuracy is below the threshold.
"""

DEFAULT_GOLDEN_SET = "evaluation/golden/rag_cases.jsonl"
DEFAULT_OUTPUT = "evaluation/reports/rag_eval.json"
DEFAULT_THRESHOLD = 0.85

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG Hit@5 Evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET, help="Path to JSONL golden set")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Minimum accepted score")
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first active tenant)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write JSON report")
    parser.add_argument("--diagnostic-top-k", type=int, default=5)
    return parser
```

**Structured scoring/report pattern** (`scripts/eval_rag.py` lines 94-118, 172-202):

```python
def _score_case(case: dict[str, Any], result: RetrievalResult) -> dict[str, Any]:
    expected_chunks = list(case.get("expected_chunk_ids", []))
    expected_docs = set(case.get("expected_doc_ids", []))
    got_chunks = [evidence.chunk_id for evidence in result.evidence]
    got_docs = {evidence.doc_key for evidence in result.evidence}
    expected_doc_id_hit = bool(expected_docs & got_docs)
    ranked_evidence = _ranked_evidence(result)

    if case.get("should_fallback"):
        hit = result.retrieval_status == "no_evidence"
        reason = "fallback_no_evidence" if hit else "should_fallback_but_got_results"
    else:
        hit = bool(set(expected_chunks) & set(got_chunks))
        reason = "expected_chunk_in_top5" if hit else "expected_chunk_not_in_top5"

    return {
        "hit": hit,
        "reason": reason,
        "expected_chunks": expected_chunks,
        "got_chunks": got_chunks,
        "expected_doc_id_hit": expected_doc_id_hit,
        "ranked_evidence": ranked_evidence,
        "retrieval_status": result.retrieval_status,
    }

def _build_report(...) -> dict[str, Any]:
    return {
        "eval_type": "rag",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "thresholds": {"hit_at_5": threshold, "fallback_accuracy": threshold},
        "metrics": {
            "hit_at_5": hit_at_5,
            "fallback_accuracy": fallback_acc,
            "total_cases": total_cases,
        },
        "per_category": _finalize_category_rates(per_category),
        "failed_cases": failed_cases,
    }
```

**Hybrid trace diagnostic pattern** (`scripts/eval_rag_hit_at_5.py` lines 79-98, 149-165):

```python
def _ranked_evidence(result: RetrievalResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rank, evidence in enumerate(result.evidence, start=1):
        row: dict[str, object] = {
            "rank": rank,
            "doc_key": evidence.doc_key,
            "chunk_id": evidence.chunk_id,
            "section": evidence.section,
            "score": evidence.score,
            "text_snippet": evidence.text,
        }
        selected_by = getattr(evidence, "selected_by", None)
        if selected_by:
            row["selected_by"] = list(selected_by)
        for attr in ("dense_rank", "sparse_rank", "fuzzy_rank", "rrf_score"):
            value = getattr(evidence, attr, None)
            if value is not None:
                row[attr] = value
        rows.append(row)
    return rows
```

**Apply:** Prefer a new ablation script over overloading legacy Hit@5. Keep default no-live-provider behavior. Output machine-readable JSON under `evaluation/reports/`, with per-variant metrics, failed cases, safe diagnostic evidence, and latency percentiles.

---

### `evaluation/golden/rag_cases.jsonl` (eval data, file-I/O/batch)

**Analog:** `evaluation/golden/rag_cases.jsonl`

**Existing JSONL shape** (`evaluation/golden/rag_cases.jsonl` lines 1-5, 13-14):

```json
{"query": "买家申请七天无理由退款，商品已拆封但不影响二次销售，应该怎么处理？", "expected_doc_ids": ["refund_policy"], "expected_chunk_ids": ["refund_policy_001"], "category": "refund_rule", "difficulty": "easy", "should_fallback": false}
{"query": "订单超过15天买家申请退款，是否还在退款时效内？", "expected_doc_ids": ["refund_time_limits"], "expected_chunk_ids": ["refund_time_limits_001"], "category": "refund_rule", "difficulty": "easy", "should_fallback": false}
{"query": "用户问如何更换银行卡绑定手机号？", "expected_doc_ids": [], "expected_chunk_ids": [], "category": "fallback", "difficulty": "easy", "should_fallback": true}
```

**Apply:** Add deterministic Phase 23 categories without deleting existing cases: synonym/alias, ambiguous merchant-support wording, underspecified question, no-evidence/out-of-domain, stale/unauthorized evidence, ranking regression, rewrite-win, reranker-win.

---

### `evaluation/reports/rag_ablation.json` (eval artifact, file-I/O/batch)

**Analog:** `scripts/eval_rag.py`

**Artifact write pattern** (`scripts/eval_rag.py` lines 332-363):

```python
async def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    report = await run_rag_eval(
        golden_set_path=args.golden_set,
        threshold=args.threshold,
        tenant_id=args.tenant_id,
        diagnostic_top_k=args.diagnostic_top_k,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_report(report)

    if report["status"] == "fail":
        print(f"\nFAIL: Below threshold. JSON report written to {output_path}")
        sys.exit(1)

    print(f"\nPASS. JSON report written to {output_path}")
    sys.exit(0)
```

**Apply:** The artifact should be generated by the eval script, not handwritten during implementation. Keep it under `evaluation/reports/` and ensure it contains no raw provider payloads or unbounded policy text.

## Shared Patterns

### Authentication And Scope

**Source:** `src/knowledge/service.py` lines 103-125 and `src/repositories/policy_chunk_repo.py` lines 193-237, 239-342

**Apply to:** `src/knowledge/rewrite.py`, `src/knowledge/retrieval.py`, `src/knowledge/service.py`, diagnostics, and all channel tests.

```python
merchant_id = request.filters.merchant_id
merchant_scope = context.merchant_scope
if not merchant_scope:
    return self._no_evidence_result()
if merchant_id is not None and "*" not in merchant_scope and merchant_id not in merchant_scope:
    return self._no_evidence_result()

dense_raw_results = await self.chunk_repo.search_similar(
    tenant_id=UUID(context.tenant_id),
    doc_type=doc_type,
    risk_level=risk_level,
    effective_date=effective_date,
)
```

Rewrite must never derive or mutate scope. Every original and rewritten channel must reuse the same trusted `tenant_id`, `doc_type`, `risk_level`, and `effective_date` values.

### Error Handling And Fallback

**Source:** `src/knowledge/retrieval.py` lines 249-270; `src/knowledge/service.py` lines 119-154, 375-400

**Apply to:** Rewrite generation, rewritten-channel retrieval, rerank/provider adapters, service facade.

```python
try:
    return await asyncio.wait_for(..., timeout=RETRIEVAL_TIMEOUT_SECONDS)
except asyncio.TimeoutError:
    return "error", [], 0.0

except Exception:
    return self._error_result(
        "SEARCH_ERROR",
        "Failed to search policy evidence",
        retryable=False,
    )
```

Provider/rewrite/rerank failures should fall back to original-query hybrid retrieval or no-evidence/error behavior without weakening evidence validation.

### Evidence Identity Boundary

**Source:** `src/knowledge/schemas.py` lines 31-69; `src/knowledge/retrieval.py` lines 217-247; `tests/knowledge/test_phase21_boundaries.py` lines 175-193

**Apply to:** All runtime and tests.

```python
EvidenceRefV1.build(
    tenant_id=context.tenant_id,
    doc_key=hit.doc_key,
    chunk_id=hit.chunk_id,
    policy_version=hit.policy_version,
    text=hit.text,
    retrieved_at=context.effective_at,
    retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
    score=hit.score,
    rank=hit.rank,
)
```

Do not add rewrite, rerank, diagnostic, source-block, OCR, parser, verifier, claim, business fact, or provider fields to `EvidenceRefV1`.

### Public Surface Redaction

**Source:** `src/api/schemas/search.py` lines 6-17; `tests/knowledge/test_phase21_boundaries.py` lines 196-239

**Apply to:** Diagnostics, eval reports, API-facing DTOs, prompt/final/memory/replay/action regression tests.

```python
selected_by: list[str] | None = Field(default=None, exclude=True)
dense_rank: int | None = Field(default=None, exclude=True)
sparse_rank: int | None = Field(default=None, exclude=True)
fuzzy_rank: int | None = Field(default=None, exclude=True)
rrf_score: float | None = Field(default=None, exclude=True)
```

Safe diagnostics may exist internally or in eval reports, but ordinary public serialization should exclude retrieval traces.

### Static Boundary Guard

**Source:** `tests/knowledge/test_phase21_boundaries.py` lines 19-80, 109-147

**Apply to:** Any new Phase 23 symbols and files.

Keep a narrow allowlist for Phase 23-owned query rewrite/reranker terms. Continue to block:

- RAG-5 backend replacement: `SearchBackend`, `Vespa`, `OpenSearch`.
- Phase 17 execution: `external_action_execution`, outbox, compensation dispatch.
- Policy Source Operations UI: upload/review/lifecycle/source-document viewer terms.

### Eval Report

**Source:** `scripts/eval_rag.py` lines 172-202, 332-363; `scripts/eval_rag_hit_at_5.py` lines 79-98

**Apply to:** `scripts/eval_rag_ablation.py`, `tests/test_rag_ablation_eval.py`, `evaluation/reports/rag_ablation.json`.

Use JSONL loading, deterministic scoring helpers, machine-readable JSON reports, explicit thresholds, per-category metrics, failed cases, and safe ranked evidence diagnostics. Add Phase 23 variants and latency metrics without requiring live provider credentials.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | - | - | Every planned Phase 23 file has a close local analog. Live provider-specific rewrite/rerank adapters have no selected provider analog in this repo; implement only a disabled-by-default protocol/fake path if planned. |

## Boundary Notes For Planner

- Keep Phase 23 inside `src/knowledge`, tests, `scripts/eval*`, and `evaluation/` artifacts.
- Do not map to RAG-5 `SearchBackend`, Vespa, OpenSearch, or new vector DB work.
- Do not map to Phase 17 external execution, outbox, compensation, or AgentState cleanup.
- Do not change `EvidenceRefV1` identity or field set.
- ContextBuilder and MaterialClaimVerifier remain downstream authority gates; rerank/rewrite scores are relevance diagnostics only.

## Metadata

**Analog search scope:** `src/knowledge`, `src/api/schemas`, `src/repositories`, `tests/knowledge`, `tests/agent/rag_context`, `scripts`, `evaluation/golden`, `eval`
**Files scanned:** 97
**Primary analog families:** retrieval engine, knowledge schemas/config, service facade, boundary/leakage tests, RAG eval scripts
**Pattern extraction date:** 2026-06-20
