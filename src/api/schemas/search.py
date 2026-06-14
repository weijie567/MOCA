from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    doc_key: str
    chunk_id: str
    title: str
    section: str
    score: float = Field(ge=0.0, le=1.0)
    text: str


class RetrievalResult(BaseModel):
    query: str
    retrieval_status: str = Field(pattern="^(strong_evidence|partial_evidence|no_evidence)$")
    evidence: list[EvidenceItem]
    best_score: float
    fallback_message: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    doc_type: str | None = None
    risk_level: str | None = None
