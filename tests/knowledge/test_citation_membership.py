from __future__ import annotations

from src.knowledge.citation import CITATION_VALIDATOR_VERSION, validate_membership

from .conftest import make_evidence_ref


def claim(*, claim_id: str = "claim-1", text: str = "Material claim", cited: list[str]) -> dict:
    return {
        "claim_id": claim_id,
        "claim_text": text,
        "cited_evidence_ids": cited,
    }


def test_present_evidence_id_passes_membership() -> None:
    evidence = make_evidence_ref()

    result = validate_membership([claim(cited=[evidence.evidence_id])], [evidence])

    assert result.validator_version == CITATION_VALIDATOR_VERSION
    assert result.is_valid is True
    assert result.claim_results[0].is_member is True
    assert result.claim_results[0].missing_evidence_ids == []


def test_absent_evidence_id_fails_membership() -> None:
    evidence = make_evidence_ref()
    absent_evidence_id = "policy_other/chunk_999@v1"

    result = validate_membership([claim(cited=[absent_evidence_id])], [evidence])

    assert result.is_valid is False
    assert result.claim_results[0].is_member is False
    assert result.claim_results[0].missing_evidence_ids == [absent_evidence_id]


def test_empty_citations_fail_membership() -> None:
    result = validate_membership([claim(cited=[])], [make_evidence_ref()])

    assert result.is_valid is False
    assert result.claim_results[0].is_member is False
    assert result.claim_results[0].missing_evidence_ids == []


def test_membership_keys_on_full_evidence_id_not_bare_chunk_id() -> None:
    present = make_evidence_ref(doc_key="policy-a", chunk_id="shared-chunk", policy_version="v1")
    wrong = make_evidence_ref(doc_key="policy-b", chunk_id="shared-chunk", policy_version="v2")

    result = validate_membership([claim(cited=[wrong.evidence_id])], [present])

    assert present.chunk_id == wrong.chunk_id
    assert present.evidence_id != wrong.evidence_id
    assert result.is_valid is False
    assert result.claim_results[0].missing_evidence_ids == [wrong.evidence_id]


def test_membership_does_not_infer_semantic_support() -> None:
    evidence = make_evidence_ref(text="This evidence discusses refund timing only.")

    result = validate_membership(
        [claim(text="The merchant receives a free vacation.", cited=[evidence.evidence_id])],
        [evidence],
    )

    assert result.is_valid is True
    assert result.claim_results[0].is_member is True


def test_mixed_claim_membership_fails_overall_validation() -> None:
    evidence = make_evidence_ref()
    missing_evidence_id = "policy-missing/chunk-2@v1"

    result = validate_membership(
        [
            claim(claim_id="claim-present", cited=[evidence.evidence_id]),
            claim(claim_id="claim-missing", cited=[missing_evidence_id]),
        ],
        [evidence],
    )

    assert [item.is_member for item in result.claim_results] == [True, False]
    assert result.is_valid is False


def test_empty_claim_list_fails_validation() -> None:
    result = validate_membership([], [make_evidence_ref()])

    assert result.claim_results == []
    assert result.is_valid is False
