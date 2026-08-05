"""Deterministic evidence_id citation membership validation.

This module implements membership-only validation per D-C1/D-C2. It does not
infer semantic claim support; that remains a separate deferred evaluation
described in docs/quality/evaluation.md and the canonical claim contracts.
"""

from __future__ import annotations

from src.knowledge.schemas import ClaimResult, CitationValidationResult, EvidenceRefV1

CITATION_VALIDATOR_VERSION = "citation_validator.v2"


def validate_membership(
    claims: list[dict],
    evidence_refs: list[EvidenceRefV1],
) -> CitationValidationResult:
    """Check cited evidence_id membership without inferring semantic support.

    Callers must pass evidence reference objects exposing ``evidence_id``, not
    bare evidence ID strings. Empty claims and claims without citations fail
    validation because policy answers require at least one validated material
    claim with evidence.
    """
    present = {ref.evidence_id for ref in evidence_refs}
    claim_results: list[ClaimResult] = []
    all_member = True

    for claim in claims:
        cited = list(claim.get("cited_evidence_ids") or [])
        missing = [evidence_id for evidence_id in cited if evidence_id not in present]
        is_member = bool(cited) and not missing
        if not is_member:
            all_member = False

        claim_results.append(
            ClaimResult(
                claim_id=str(claim.get("claim_id")),
                claim_text=str(claim.get("claim_text") or ""),
                cited_evidence_ids=cited,
                is_member=is_member,
                missing_evidence_ids=missing if cited else [],
            )
        )

    return CitationValidationResult(
        validator_version=CITATION_VALIDATOR_VERSION,
        claim_results=claim_results,
        is_valid=all_member and len(claim_results) > 0,
    )
