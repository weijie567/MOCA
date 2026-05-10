from __future__ import annotations

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
