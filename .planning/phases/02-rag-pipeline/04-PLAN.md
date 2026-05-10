---
phase: 2
plan: "04"
plan_id: "04"
type: execute
title: "Retriever + Citation Validator + Search Endpoint"
wave: 2
depends_on: ["01", "02", "03"]
files_modified:
  - src/rag/retriever.py
  - src/rag/citation_validator.py
  - src/api/routers/search.py
  - src/api/main.py
  - tests/test_retriever.py
autonomous: true
requirements: [RAG-04, RAG-06, RAG-07, EVAL-02]
must_haves:
  truths:
    - "Retriever implements three-tier confidence scoring: strong >= 0.70, partial from 0.55 to 0.70, and no_evidence below 0.55."
    - "Retriever evidence uses chunk.document.doc_key, not a UUID foreign key."
    - "Citation validator uses deterministic field matching with no LLM dependency."
    - "Search endpoint requires Security(get_current_user, scopes=[\"knowledge:read\"])."
    - "Search endpoint returns ApiResponse with trace_id rather than a custom wrapper."
    - "Search endpoint is registered under settings.api_v1_prefix at /search."
  artifacts:
    - path: "src/rag/retriever.py"
      provides: "Retriever and confidence scoring"
      contains: "STRONG_EVIDENCE_THRESHOLD"
    - path: "src/rag/citation_validator.py"
      provides: "Deterministic citation validation"
      contains: "validate_citations"
    - path: "src/api/routers/search.py"
      provides: "Authenticated search API endpoint"
      contains: "knowledge:read"
    - path: "src/api/main.py"
      provides: "Router registration"
      contains: "search"
    - path: "tests/test_retriever.py"
      provides: "Retriever and citation validator tests"
      contains: "no_evidence"
  key_links:
    - from: "src/api/routers/search.py"
      to: "src/rag/retriever.py"
      via: "endpoint delegates query handling to Retriever.search"
      pattern: "Retriever"
    - from: "src/rag/retriever.py"
      to: "src/repositories/policy_chunk_repo.py"
      via: "retriever uses repository vector search"
      pattern: "search_similar"
    - from: "src/api/routers/search.py"
      to: "src/rag/citation_validator.py"
      via: "endpoint validates returned evidence"
      pattern: "validate_citations"
---

# Plan 04: Retriever + Citation Validator + Search Endpoint

<objective>
Implement the retrieval service with three-tier confidence scoring, the citation validator, and the FastAPI search endpoint using existing project conventions (get_session, Security, ApiResponse, settings.api_v1_prefix).
</objective>

<tasks>

<task id="04.1">
<title>Implement retriever with confidence scoring</title>
<read_first>
- src/repositories/policy_chunk_repo.py
- src/rag/schemas.py
- src/rag/embedder.py
- src/db/models.py (PolicyChunk.document relationship)
- .planning/phases/02-rag-pipeline/02-CONTEXT.md (D-05 confidence thresholds, D-09 retrieval contract)
</read_first>
<action>
Create `src/rag/retriever.py`:

```python
from __future__ import annotations

from uuid import UUID

from src.rag.schemas import EvidenceItem, RetrievalResult
from src.rag.embedder import EmbeddingService
from src.repositories.policy_chunk_repo import PolicyChunkRepository

STRONG_EVIDENCE_THRESHOLD = 0.70
MIN_SIMILARITY_THRESHOLD = 0.55
FALLBACK_MESSAGE = "当前知识库中没有找到足够证据支持这个问题，建议转人工或补充规则文档。"


class Retriever:
    def __init__(self, chunk_repo: PolicyChunkRepository, embedder: EmbeddingService):
        self.chunk_repo = chunk_repo
        self.embedder = embedder

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

        evidence = [
            EvidenceItem(
                doc_key=chunk.document.doc_key,  # semantic stable ID via eager-loaded relationship
                chunk_id=chunk.chunk_id,
                title=chunk.document.title,
                section=chunk.section,
                score=score,
                text=chunk.content[:300],
            )
            for chunk, score in results
        ]

        best_score = max((e.score for e in evidence), default=0.0)

        if not evidence or best_score < MIN_SIMILARITY_THRESHOLD:
            status = "no_evidence"
        elif best_score >= STRONG_EVIDENCE_THRESHOLD:
            status = "strong_evidence"
        else:
            status = "partial_evidence"

        return RetrievalResult(
            query=query,
            retrieval_status=status,
            evidence=evidence,
            best_score=best_score,
            fallback_message=FALLBACK_MESSAGE if status == "no_evidence" else None,
        )
```

Key fixes from review:
- Uses `chunk.document.doc_key` (not chunk.doc_id which is UUID FK)
- Relies on eager-loaded relationship from PolicyChunkRepository.search_similar (selectinload)
</action>
<acceptance_criteria>
- src/rag/retriever.py exists
- File contains `class Retriever`
- File contains `STRONG_EVIDENCE_THRESHOLD = 0.70`
- File contains `MIN_SIMILARITY_THRESHOLD = 0.55`
- File contains `chunk.document.doc_key` (uses eager-loaded relationship, not chunk.doc_id)
- File contains FALLBACK_MESSAGE with "当前知识库中没有找到足够证据"
- File returns `RetrievalResult` with three states: strong_evidence, partial_evidence, no_evidence
</acceptance_criteria>
</task>

<task id="04.2">
<title>Implement citation validator</title>
<read_first>
- src/rag/schemas.py (CitationValidation model)
- .planning/phases/02-rag-pipeline/02-CONTEXT.md (D-06 citation validator rules)
</read_first>
<action>
Create `src/rag/citation_validator.py`:

```python
from __future__ import annotations

from src.rag.schemas import CitationValidation, RetrievalResult


def validate_citations(
    cited_chunk_ids: list[str],
    retrieval_result: RetrievalResult,
) -> CitationValidation:
    """
    Validate that all cited chunk_ids exist in the retrieval results.
    Simple field matching — no LLM judge (D-06e).
    """
    if not cited_chunk_ids:
        return CitationValidation(
            is_valid=False,
            invalid_citations=[],
            reason="No citations provided — every policy answer must include citations (D-06a)",
        )

    retrieved_ids = {e.chunk_id for e in retrieval_result.evidence}
    invalid = [cid for cid in cited_chunk_ids if cid not in retrieved_ids]

    if invalid:
        return CitationValidation(
            is_valid=False,
            invalid_citations=invalid,
            reason=f"Citations reference chunk_ids not in retrieval results: {invalid}",
        )

    return CitationValidation(is_valid=True)
```
</action>
<acceptance_criteria>
- src/rag/citation_validator.py exists
- File contains `def validate_citations(`
- Checks for empty cited_chunk_ids (returns invalid)
- Checks each cited_chunk_id against retrieval evidence
- Returns `CitationValidation` object
- No LLM judge logic
</acceptance_criteria>
</task>

<task id="04.3">
<title>Create search API endpoint matching project conventions</title>
<read_first>
- src/api/routers/orders.py (MUST follow this exact pattern: imports, Security, ApiResponse, get_session, request.state.trace_id)
- src/api/main.py (router registration with settings.api_v1_prefix)
- src/api/schemas/common.py (ApiResponse)
- src/auth/permissions.py (get_current_user)
- src/db/session.py (get_session)
</read_first>
<action>
Create `src/api/routers/search.py` following the EXACT pattern of orders.py:

```python
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request, Security
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import ApiResponse
from src.auth.permissions import get_current_user
from src.db.models import User
from src.db.session import get_session
from src.rag.embedder import EmbeddingService
from src.rag.retriever import Retriever
from src.rag.schemas import SearchRequest
from src.repositories.policy_chunk_repo import PolicyChunkRepository


router = APIRouter(tags=["search"])


@router.post("/", response_model=ApiResponse)
async def search_knowledge_base(
    body: SearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["knowledge:read"]),
) -> ApiResponse:
    """Search knowledge base for relevant policy chunks. Scoped to user's tenant."""
    start = time.perf_counter()

    embedder = EmbeddingService()
    chunk_repo = PolicyChunkRepository(session)
    retriever = Retriever(chunk_repo=chunk_repo, embedder=embedder)

    result = await retriever.search(
        query=body.query,
        tenant_id=user.tenant_id,
        top_k=body.top_k,
        doc_type=body.doc_type,
        risk_level=body.risk_level,
    )

    return ApiResponse(
        success=True,
        data=result.model_dump(),
        trace_id=request.state.trace_id,
    )
```

Then register in `src/api/main.py`:
- Add import: `from src.api.routers import search`
- Add registration: `app.include_router(search.router, prefix=f"{settings.api_v1_prefix}/search")`
</action>
<acceptance_criteria>
- src/api/routers/search.py exists
- File imports from `src.api.schemas.common import ApiResponse` (not custom SearchResponse)
- File imports from `src.auth.permissions import get_current_user`
- File imports from `src.db.session import get_session`
- File uses `Security(get_current_user, scopes=["knowledge:read"])`
- File returns `ApiResponse(success=True, data=..., trace_id=request.state.trace_id)`
- File uses `user.tenant_id` for scoping
- src/api/main.py contains `include_router(search.router, prefix=f"{settings.api_v1_prefix}/search")`
</acceptance_criteria>
</task>

<task id="04.4">
<title>Unit tests for retriever and citation validator</title>
<read_first>
- src/rag/retriever.py
- src/rag/citation_validator.py
- tests/conftest.py (existing fixtures)
- tests/ (existing test patterns)
</read_first>
<action>
Create `tests/test_retriever.py` with tests using mock embeddings (D-13c):

1. `test_strong_evidence_status` — best score >= 0.70 → "strong_evidence"
2. `test_partial_evidence_status` — best score 0.55-0.70 → "partial_evidence"
3. `test_no_evidence_status` — no results or best < 0.55 → "no_evidence" with fallback_message
4. `test_evidence_item_has_doc_key` — Each item has doc_key (not UUID), chunk_id, title, section, score, text
5. `test_citation_valid` — All cited chunk_ids in results → valid
6. `test_citation_invalid_missing` — Cited chunk_id not in results → invalid with list
7. `test_citation_empty` — No citations → invalid with "must include citations" reason
8. `test_tenant_isolation` — Mock repo only returns chunks for matching tenant_id

Use `unittest.mock.AsyncMock` to mock PolicyChunkRepository and EmbeddingService.
Do NOT call real DashScope API.
</action>
<acceptance_criteria>
- tests/test_retriever.py exists
- File contains at least 7 test functions
- File uses AsyncMock or patch (no real API calls)
- File tests all three retrieval_status values
- File tests citation validation (valid, invalid, empty)
- `uv run pytest tests/test_retriever.py -q` exits 0
</acceptance_criteria>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_retriever.py -q` passes all tests
- `uv run python -c "from src.rag.retriever import Retriever; print('OK')"` exits 0
- `uv run python -c "from src.rag.citation_validator import validate_citations; print('OK')"` exits 0
- `uv run python -c "from src.api.routers.search import router; print('OK')"` exits 0
</verification>

<must_haves>
- Three-tier confidence scoring (strong >= 0.70, partial 0.55-0.70, no_evidence < 0.55)
- Retriever uses chunk.document.doc_key (eager-loaded, not UUID FK)
- Citation validator: simple field matching, no LLM
- Search endpoint uses Security(get_current_user, scopes=["knowledge:read"])
- Search endpoint returns ApiResponse with trace_id (not custom wrapper)
- Registered at settings.api_v1_prefix/search
- depends_on includes Plan 03 (for repositories)
</must_haves>
