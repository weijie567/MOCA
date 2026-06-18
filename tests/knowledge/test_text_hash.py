from __future__ import annotations

import re

from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.text_hash import evidence_text_hash


def test_nfc_composed_and_decomposed_forms_hash_equal():
    assert evidence_text_hash("é") == evidence_text_hash("e\u0301")


def test_outer_whitespace_is_stripped():
    assert evidence_text_hash("  abc  ") == evidence_text_hash("abc")


def test_internal_newlines_are_unified():
    expected = evidence_text_hash("a\nb")

    assert evidence_text_hash("a\r\nb") == expected
    assert evidence_text_hash("a\rb") == expected


def test_policy_text_is_not_case_folded():
    assert evidence_text_hash("Policy") != evidence_text_hash("policy")


def test_hash_output_format_and_frozen_golden_literal():
    result = evidence_text_hash("退款超时")

    assert re.fullmatch(r"sha256:[0-9a-f]{64}", result)
    assert result == "sha256:14da429414366e3cf6996d34022943fe381b4901065dc785fdc66107402a1427"


def test_evidence_ref_text_hash_uses_chunk_content_not_search_text():
    content = "客服应先核实物流状态。"
    search_text = "退款规则 仅退款 source_block_id=block-001 客服应先核实物流状态。"

    ref = EvidenceRefV1.build(
        tenant_id="tenant-001",
        doc_key="refund_policy",
        chunk_id="refund_policy_000",
        policy_version="v1",
        text=content,
        retrieved_at="2026-06-05T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
    )

    assert ref.text_hash == evidence_text_hash(content)
    assert ref.text_hash != evidence_text_hash(search_text)
