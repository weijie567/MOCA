from __future__ import annotations

import json
from typing import Any

import pytest

from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1


TENANT_ID = "11111111-1111-1111-1111-111111111111"
RAW_TOOL_PAYLOAD = "SHOULD_NOT_LEAK_RAW_TOOL_PAYLOAD"
RETRIEVAL_DEBUG_FIELD = "SHOULD_NOT_LEAK_RETRIEVAL_DEBUG_FIELD"
VERIFIER_PROMPT_TRACE = "SHOULD_NOT_LEAK_VERIFIER_PROMPT_TRACE"
RAW_PROVENANCE_TRACE = "SHOULD_NOT_LEAK_RAW_PROVENANCE_TRACE"
SOURCE_BLOCK_ID = "refund-policy:policy_pdf:text:source-block-private"
OCR_RAW_METADATA = "SHOULD_NOT_LEAK_OCR_RAW_METADATA"
PRIVATE_REASONING = "SHOULD_NOT_LEAK_PRIVATE_REASONING"
UNBOUNDED_POLICY_TEXT = "SHOULD_NOT_LEAK_UNBOUNDED_POLICY_TEXT"
SAFE_OCR_LABEL = "ocr_low_confidence"
SAFE_PROVENANCE_LABEL = "source_locator_available"

LEAKAGE_SENTINELS = {
    RAW_TOOL_PAYLOAD,
    RETRIEVAL_DEBUG_FIELD,
    VERIFIER_PROMPT_TRACE,
    RAW_PROVENANCE_TRACE,
    SOURCE_BLOCK_ID,
    OCR_RAW_METADATA,
    PRIVATE_REASONING,
    UNBOUNDED_POLICY_TEXT,
}


def _load_context_api():
    from src.agent.rag_context.builder import ContextBuilder

    return ContextBuilder


def _evidence_ref() -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id=TENANT_ID,
        doc_key="policy_refund_timeout",
        chunk_id="chunk_001",
        policy_version="v2",
        text="Refund policy requires verified evidence before compensation.",
        retrieved_at="2026-06-19T00:00:00.000Z",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.91,
        rank=1,
    )


def _trusted_context() -> dict[str, Any]:
    return {
        "tenant_id": TENANT_ID,
        "run_id": "run-phase22-leakage",
        "thread_id": "thread-phase22-leakage",
        "effective_at": "2026-06-19T00:00:00+00:00",
        "scope": {"merchant_ids": ["merchant-001"]},
    }


class FakePolicyKnowledgeService:
    def __init__(self, evidence: EvidenceRefV1) -> None:
        self.evidence = evidence

    async def get_verified_evidence_contents(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, str]:
        return {
            ref.evidence_id: (
                "Refund policy requires verified evidence before compensation. "
                f"{UNBOUNDED_POLICY_TEXT} " * 120
            )
            for ref in evidence_refs
            if ref.tenant_id == tenant_id and ref.evidence_id == self.evidence.evidence_id
        }

    async def get_verified_evidence_provenance(
        self,
        *,
        tenant_id: str,
        evidence_refs: list[EvidenceRefV1],
    ) -> dict[str, dict[str, Any]]:
        return {
            ref.evidence_id: {
                "source_locators": [
                    {
                        "source_block_id": SOURCE_BLOCK_ID,
                        "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
                        "ocr": {"raw_words": OCR_RAW_METADATA, "average_confidence": 0.41},
                        "parser": {"raw_payload": RAW_PROVENANCE_TRACE},
                    }
                ]
            }
            for ref in evidence_refs
            if ref.tenant_id == tenant_id
        }


def _unsafe_risk_hints(evidence: EvidenceRefV1) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": evidence.evidence_id,
            "labels": [SAFE_OCR_LABEL, SAFE_PROVENANCE_LABEL],
            "raw_tool_payload": RAW_TOOL_PAYLOAD,
            "retrieval_debug": {
                "selected_by": ["dense", "sparse", "fuzzy"],
                "dense_rank": 1,
                "debug_blob": RETRIEVAL_DEBUG_FIELD,
            },
            "verifier_prompt_trace": VERIFIER_PROMPT_TRACE,
            "raw_provenance": RAW_PROVENANCE_TRACE,
            "source_block_id": SOURCE_BLOCK_ID,
            "ocr_raw_metadata": OCR_RAW_METADATA,
            "private_reasoning": PRIVATE_REASONING,
        }
    ]


def _json_text(value: Any) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, default=str, sort_keys=True)
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _ordinary_surface_text(bundle: Any) -> str:
    ordinary_surfaces = {
        "prompt": bundle.prompt_context,
        "final_response": bundle.final_response_context,
        "memory": bundle.memory_context,
        "replay": bundle.replay_context,
        "business_fact": bundle.business_fact_context,
        "action_snapshot": bundle.action_snapshot_context,
    }
    return _json_text(ordinary_surfaces)


@pytest.mark.asyncio
async def test_prompt_final_memory_replay_business_fact_and_action_surfaces_exclude_raw_internals() -> None:
    """CTX-06/BND-05: ordinary surfaces do not leak raw tool/debug/provenance/verifier data."""
    ContextBuilder = _load_context_api()
    evidence = _evidence_ref()

    bundle = await ContextBuilder(
        policy_service=FakePolicyKnowledgeService(evidence),
        max_snippet_chars=120,
    ).build(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[],
        trusted_context=_trusted_context(),
        risk_hints=_unsafe_risk_hints(evidence),
    )

    ordinary_text = _ordinary_surface_text(bundle)

    for sentinel in LEAKAGE_SENTINELS:
        assert sentinel not in ordinary_text
    assert SAFE_OCR_LABEL in ordinary_text
    assert SAFE_PROVENANCE_LABEL in ordinary_text
    assert "text_hash" not in _json_text(bundle.prompt_context)
    assert "parser_metadata_json" not in ordinary_text
    assert "ocr_metadata_json" not in ordinary_text


@pytest.mark.asyncio
async def test_verifier_debug_material_stays_out_of_user_facing_final_response() -> None:
    """RTE-05/BND-05: verifier traces and raw reason payloads stay out of final responses."""
    ContextBuilder = _load_context_api()
    evidence = _evidence_ref()

    bundle = await ContextBuilder(policy_service=FakePolicyKnowledgeService(evidence)).build(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[],
        trusted_context=_trusted_context(),
        risk_hints=_unsafe_risk_hints(evidence),
    )

    final_text = _json_text(bundle.final_response_context)
    debug_text = _json_text(bundle.debug_context)

    assert VERIFIER_PROMPT_TRACE in debug_text
    assert RAW_PROVENANCE_TRACE in debug_text
    assert VERIFIER_PROMPT_TRACE not in final_text
    assert RAW_PROVENANCE_TRACE not in final_text
    assert PRIVATE_REASONING not in final_text
    assert SOURCE_BLOCK_ID not in final_text
    assert final_text


@pytest.mark.asyncio
async def test_source_block_and_ocr_internals_may_only_be_projected_as_prompt_safe_labels() -> None:
    """CTX-06: OCR/provenance can produce labels, never raw source-block or OCR payloads."""
    ContextBuilder = _load_context_api()
    evidence = _evidence_ref()

    bundle = await ContextBuilder(policy_service=FakePolicyKnowledgeService(evidence)).build(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[],
        trusted_context=_trusted_context(),
        risk_hints=_unsafe_risk_hints(evidence),
    )

    prompt_text = _json_text(bundle.prompt_context)
    action_text = _json_text(bundle.action_snapshot_context)
    replay_text = _json_text(bundle.replay_context)

    assert SAFE_OCR_LABEL in prompt_text
    assert SAFE_PROVENANCE_LABEL in prompt_text
    assert SOURCE_BLOCK_ID not in prompt_text
    assert SOURCE_BLOCK_ID not in action_text
    assert SOURCE_BLOCK_ID not in replay_text
    assert OCR_RAW_METADATA not in prompt_text
    assert OCR_RAW_METADATA not in action_text
    assert OCR_RAW_METADATA not in replay_text


@pytest.mark.asyncio
async def test_unbounded_policy_text_is_not_copied_to_any_ordinary_surface() -> None:
    """D-20/EVAL-04: unbounded policy bodies stay out of prompts, answers, memory, replay, and actions."""
    ContextBuilder = _load_context_api()
    evidence = _evidence_ref()

    bundle = await ContextBuilder(
        policy_service=FakePolicyKnowledgeService(evidence),
        max_snippet_chars=80,
    ).build(
        candidate_evidence_refs=[evidence],
        business_fact_refs=[],
        trusted_context=_trusted_context(),
        risk_hints=_unsafe_risk_hints(evidence),
    )

    ordinary_text = _ordinary_surface_text(bundle)

    assert UNBOUNDED_POLICY_TEXT not in ordinary_text
    assert "Refund policy requires verified evidence" in ordinary_text
