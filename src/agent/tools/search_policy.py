from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.rag.embedder import EmbeddingService
from src.rag.retriever import Retriever
from src.repositories.policy_chunk_repo import PolicyChunkRepository


def _tool_success(data: dict) -> dict:
    return {"status": "success", "data": data, "error": {}}


def _tool_error(error_code: str, message: str, retryable: bool, should_stop: bool = False) -> dict:
    return {
        "status": "error",
        "data": {},
        "error": {
            "error_code": error_code,
            "message": message,
            "retryable": retryable,
            "should_stop": should_stop,
        },
    }


async def search_policy(
    query: str,
    tenant_id: str,
    user_id: str,
    role: str,
    session: AsyncSession,
    top_k: int = 5,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> dict:
    """Search tenant-scoped policy evidence. Read-only."""
    del user_id, role

    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        return _tool_error("VALIDATION_ERROR", "Invalid tenant_id", retryable=False)

    try:
        chunk_repo = PolicyChunkRepository(session)
        retriever = Retriever(chunk_repo=chunk_repo, embedder=EmbeddingService())
        result = await asyncio.wait_for(
            retriever.search(query, tenant_uuid, top_k, doc_type, risk_level),
            timeout=15.0,
        )
        return _tool_success(
            {
                "retrieval_status": result.retrieval_status,
                "best_score": result.best_score,
                "evidence": [
                    {
                        "doc_key": item.doc_key,
                        "chunk_id": item.chunk_id,
                        "title": item.title,
                        "section": item.section,
                        "score": item.score,
                        "text": item.text,
                    }
                    for item in result.evidence
                ],
                "fallback_message": result.fallback_message,
            }
        )
    except asyncio.TimeoutError:
        return _tool_error("DB_TIMEOUT", "Policy search timeout", retryable=True)
    except Exception:
        return _tool_error("SEARCH_ERROR", "Failed to search policy evidence", retryable=False)
