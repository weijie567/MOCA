"""Material claim contracts and dependency-map helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from src.agent.rag_context.schemas import (
    ClaimVerifierStatus,
    MaterialClaim,
    MaterialClaimAuthorityClass,
)
from src.knowledge.schemas import MaterialClaimV1


_AUTHORITY_CLASS_TO_CLAIM_TYPE = {
    "policy_claim": "policy",
    "business_fact_claim": "business_fact",
    "action_recommendation_claim": "action_recommendation",
}


def normalize_material_claim(value: MaterialClaim | Mapping[str, Any]) -> MaterialClaim:
    """Validate untrusted claim payloads at the rag_context boundary."""
    if isinstance(value, MaterialClaim):
        return value
    return MaterialClaim.model_validate(dict(value))


def normalize_material_claims(values: Iterable[MaterialClaim | Mapping[str, Any]]) -> list[MaterialClaim]:
    return [normalize_material_claim(value) for value in values]


def normalize_material_claim_v1(value: MaterialClaimV1 | MaterialClaim | Mapping[str, Any]) -> MaterialClaimV1:
    """Normalize target or legacy material-claim payloads into ``MaterialClaimV1``."""
    if isinstance(value, MaterialClaimV1):
        return value
    if isinstance(value, MaterialClaim):
        return _legacy_material_claim_to_v1(value)
    payload = dict(value)
    if "claim_type" in payload:
        return MaterialClaimV1.model_validate(payload)
    return _legacy_material_claim_to_v1(MaterialClaim.model_validate(payload))


def normalize_material_claims_v1(
    values: Iterable[MaterialClaimV1 | MaterialClaim | Mapping[str, Any]],
) -> list[MaterialClaimV1]:
    return [normalize_material_claim_v1(value) for value in values]


def _legacy_material_claim_to_v1(claim: MaterialClaim) -> MaterialClaimV1:
    return MaterialClaimV1(
        claim_id=claim.claim_id,
        claim_text=claim.claim_text,
        claim_type=_AUTHORITY_CLASS_TO_CLAIM_TYPE[claim.authority_class.value],
        cited_evidence_ids=list(claim.cited_evidence_ids),
        business_fact_refs=list(claim.business_fact_refs),
        risk_hints=list(claim.risk_hints),
        generated_from_step=_canonical_generated_from_step(claim.source_node),
    )


def _canonical_generated_from_step(source_node: str) -> str:
    if source_node in {"generate_recommendation", "recommendation_generation"}:
        return "recommendation_generation"
    return source_node


def claim_dependency_map_from_claims(
    claims: Sequence[MaterialClaimV1 | MaterialClaim | Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project claims to the existing state-level ``claim_dependency_map`` shape."""
    entries: list[dict[str, Any]] = []
    for claim in normalize_material_claims_v1(claims):
        depends_on_refs: list[dict[str, str]] = []
        depends_on_refs.extend(
            {"resource_type": "policy_evidence", "resource_id": evidence_id}
            for evidence_id in claim.cited_evidence_ids
            if evidence_id
        )
        depends_on_refs.extend(
            {
                "resource_type": f"business_fact:{ref.resource_type}",
                "resource_id": ref.resource_id,
            }
            for ref in claim.business_fact_refs
        )
        entries.append({"claim_id": claim.claim_id, "depends_on_refs": depends_on_refs})
    return entries


def normalize_claim_dependency_map(value: Any) -> list[dict[str, Any]]:
    """Return a validated dependency map or an empty fail-closed map."""
    if not valid_claim_dependency_map(value):
        return []
    normalized: list[dict[str, Any]] = []
    for entry in value:
        normalized.append(
            {
                "claim_id": entry["claim_id"],
                "depends_on_refs": [
                    {
                        "resource_type": ref["resource_type"],
                        "resource_id": ref["resource_id"],
                    }
                    for ref in entry["depends_on_refs"]
                ],
            }
        )
    return normalized


def valid_claim_dependency_map(value: Any) -> bool:
    """Mirror the state router's dependency-map validation for claim helpers."""
    if not isinstance(value, list) or not value:
        return False
    for entry in value:
        if not isinstance(entry, dict):
            return False
        if not isinstance(entry.get("claim_id"), str) or not entry["claim_id"]:
            return False
        refs = entry.get("depends_on_refs")
        if not isinstance(refs, list):
            return False
        for ref in refs:
            if not isinstance(ref, dict):
                return False
            if not isinstance(ref.get("resource_type"), str) or not ref["resource_type"]:
                return False
            if not isinstance(ref.get("resource_id"), str) or not ref["resource_id"]:
                return False
    return True


__all__ = [
    "ClaimVerifierStatus",
    "MaterialClaim",
    "MaterialClaimAuthorityClass",
    "claim_dependency_map_from_claims",
    "normalize_claim_dependency_map",
    "normalize_material_claim",
    "normalize_material_claims",
    "normalize_material_claim_v1",
    "normalize_material_claims_v1",
    "valid_claim_dependency_map",
]
