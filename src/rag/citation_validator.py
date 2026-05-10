from __future__ import annotations

from src.rag.schemas import CitationValidation, RetrievalResult


def validate_citations(
    cited_chunk_ids: list[str],
    retrieval_result: RetrievalResult,
) -> CitationValidation:
    """
    Validate that all cited chunk_ids exist in the retrieval results.
    Simple field matching - no LLM judge (D-06e).
    """
    if not cited_chunk_ids:
        return CitationValidation(
            is_valid=False,
            invalid_citations=[],
            reason="No citations provided - every policy answer must include citations (D-06a)",
        )

    retrieved_ids = {item.chunk_id for item in retrieval_result.evidence}
    invalid = [chunk_id for chunk_id in cited_chunk_ids if chunk_id not in retrieved_ids]

    if invalid:
        return CitationValidation(
            is_valid=False,
            invalid_citations=invalid,
            reason=f"Citations reference chunk_ids not in retrieval results: {invalid}",
        )

    return CitationValidation(is_valid=True)
