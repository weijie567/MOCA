from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Security
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.common import ApiResponse
from src.api.schemas.search import EvidenceItem, RetrievalResult, SearchRequest
from src.auth.permissions import get_current_user
from src.db.models import User
from src.db.session import get_session
from src.knowledge.retrieval import POLICY_NO_EVIDENCE_MESSAGE, PolicyRetrievalEngine
from src.platform.context_projections import project_to_knowledge_context
from src.platform.trusted_context import TrustedContextFactory
from src.rag.embedder import EmbeddingService


router = APIRouter(tags=["search"])


@router.post("/", response_model=ApiResponse)
async def search_knowledge_base(
    body: SearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["knowledge:read"]),
) -> ApiResponse:
    """Search knowledge base for relevant policy chunks. Scoped to user's tenant."""
    engine = PolicyRetrievalEngine(session, embedder=EmbeddingService())
    effective_at = datetime.now(UTC).isoformat()
    trusted_context = TrustedContextFactory.create_from_request(
        user=user,
        verified_token_scopes=getattr(request.state, "verified_token_scopes", None) or [],
        thread_id=str(getattr(request.state, "thread_id", "api-search")),
        run_id=str(getattr(request.state, "run_id", "api-search")),
        trace_id=getattr(request.state, "trace_id", None),
        locale=getattr(request.state, "locale", None),
    )
    status, hits, best_score = await engine.retrieve_hits(
        query=body.query,
        context=project_to_knowledge_context(trusted_context, effective_at=effective_at),
        max_results=body.top_k,
        doc_type=body.doc_type,
        risk_level=body.risk_level,
    )
    retrieval_status = status if status != "error" else "no_evidence"
    result = RetrievalResult(
        query=body.query,
        retrieval_status=retrieval_status,
        evidence=[
            EvidenceItem(
                doc_key=hit.doc_key,
                chunk_id=hit.chunk_id,
                title=hit.title,
                section=hit.section,
                score=hit.score,
                text=hit.text[:300],
            )
            for hit in hits
        ],
        best_score=best_score,
        fallback_message=POLICY_NO_EVIDENCE_MESSAGE if retrieval_status == "no_evidence" else None,
    )

    return ApiResponse(
        success=True,
        data=result.model_dump(),
        trace_id=request.state.trace_id,
    )
